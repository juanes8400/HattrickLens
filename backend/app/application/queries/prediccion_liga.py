"""Los ratings por zona de un equipo, para el modelo de predicción.

DE DÓNDE SALEN. La aplicación guarda los ratings de los partidos PROPIOS; de
la serie sólo tiene el calendario y los marcadores. Así que los de los rivales
se piden en vivo, uno por partido jugado, igual que hace la ficha de rival.

LO GUARDADO VA PRIMERO (2026-09-13). El sync ya deja en `rival_matches` los
últimos cinco oficiales de cada contrincante, y se leen de ahí. Sólo se piden
en vivo los partidos más viejos que esa ventana, y ésos no se guardan: se
sostienen con la memoria corta de más abajo.

CUÁNTO CUESTA. Una serie de ocho equipos con seis jornadas jugadas son 24
partidos, de los que seis son propios y ya están guardados: 18 llamadas.
Medido el 2026-09-06, una llamada tarda 0,24 segundos, así que son unos cuatro
segundos la primera vez y cero las siguientes mientras dure la memoria.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.engines.prediccion import CAMPOS
from app.infrastructure.db import models as m

_log = logging.getLogger(__name__)

#: Cómo se llama cada rating en lo que devuelve el lector de partidos. Siete
#: coinciden con los nombres del motor y los dos de Balón Parado no.
#:
#: El mapa existe porque su ausencia ya costó un error: pedir `sp_def` a un
#: diccionario que lo llama `set_pieces_def` no falla, devuelve nada, y se
#: guarda un cero. Un cero ahí no es un rating bajo, es no saber, y la
#: proporción `A/(A+B)` lo convierte en 0,000, o sea en afirmar que el rival
#: gana ese duelo entero. En una prueba real eso dio 90,8 % de victoria donde
#: los datos de verdad daban 44,5 %.
DEL_LECTOR: dict[str, str] = {
    **{c: c for c in CAMPOS},
    "sp_def": "set_pieces_def",
    "sp_att": "set_pieces_att",
}

#: Cuánto dura la memoria corta. Es "no repitas 18 llamadas mientras el usuario
#: mueve los controles de la pantalla", no un caché de verdad: los ratings de
#: una jornada nueva tienen que entrar en cuanto se juegue.
_TTL_SEGUNDOS = 600
_memoria: dict[tuple[int, int, int], tuple[float, dict[int, list[dict[str, float]]]]] = {}


def reparto_de_tacticas(lecturas: list[dict[str, float]]) -> dict[int, float]:
    """Cuántas veces usó cada táctica en los partidos vistos.

    Es lo que alimenta `factor_de_tactica` cuando hay que adivinar: en vez de
    apostar por la más frecuente, se promedian los factores por su frecuencia.
    """
    cuenta: dict[int, float] = {}
    for lectura in lecturas:
        tactica = lectura.get("tactic_type")
        if tactica is None:
            continue
        cuenta[int(tactica)] = cuenta.get(int(tactica), 0.0) + 1.0
    return cuenta


def _de_fila(fila: m.MatchRating) -> dict[str, float]:
    """Los nueve ratings de una fila ya guardada, y con qué táctica se jugó."""
    return {
        "midfield": float(fila.midfield or 0),
        "left_def": float(fila.left_def or 0),
        "central_def": float(fila.central_def or 0),
        "right_def": float(fila.right_def or 0),
        "left_att": float(fila.left_att or 0),
        "central_att": float(fila.central_att or 0),
        "right_att": float(fila.right_att or 0),
        "sp_def": float(fila.set_pieces_def or 0),
        "sp_att": float(fila.set_pieces_att or 0),
        # La táctica viaja con la lectura: la corrección por táctica la
        # necesita, y sacarla después obligaría a volver a leer el partido.
        "tactic_type": float(fila.tactic_type or 0),
        # Y de qué partido es: el Resumen de Liga nombra el partido concreto
        # con el que pronostica cada lado.
        "ht_match_id": float(fila.ht_match_id),
        # Y dónde se jugó: la corrección de sede la necesita, y sin el
        # dato no se inventa --la lectura sale sin la clave--.
        **({} if fila.is_home is None else {"en_casa": 1.0 if fila.is_home else 0.0}),
    }


def _de_fila_rival(fila: m.RivalMatch) -> dict[str, float]:
    """Lo mismo que `_de_fila`, desde un partido guardado de un equipo ajeno.

    La fila guarda el lado DEL RIVAL, así que la sede sale de comparar su
    identificador con el del local.
    """
    return {
        "midfield": float(fila.midfield or 0),
        "left_def": float(fila.left_def or 0),
        "central_def": float(fila.central_def or 0),
        "right_def": float(fila.right_def or 0),
        "left_att": float(fila.left_att or 0),
        "central_att": float(fila.central_att or 0),
        "right_att": float(fila.right_att or 0),
        "sp_def": float(fila.set_pieces_def or 0),
        "sp_att": float(fila.set_pieces_att or 0),
        "tactic_type": float(fila.tactic_type or 0),
        "ht_match_id": float(fila.ht_match_id),
        **(
            {"en_casa": 1.0 if fila.home_team_ht_id == fila.team_ht_id else 0.0}
            if fila.home_team_ht_id
            else {}
        ),
    }


async def lecturas_de_la_serie(
    session: AsyncSession,
    client: Any,
    version_matchdetails: str,
    serie_ht_id: int,
    jugados: list[m.Match],
) -> dict[int, list[dict[str, float]]]:
    """Una lectura por equipo y partido jugado, del más viejo al más reciente.

    El orden importa: quien resuma por «el último partido» necesita que el
    último de la lista sea el último de verdad.

    Un partido que no devuelva ratings se salta sin ruido: pasa con los que
    aún no se han jugado y con las no comparecencias, y ninguno de los dos
    dice nada de la fuerza de un equipo.
    """
    if not jugados:
        return {}
    clave = (serie_ht_id, len(jugados), max(p.ht_match_id for p in jugados))
    guardado = _memoria.get(clave)
    if guardado is not None and time.monotonic() - guardado[0] < _TTL_SEGUNDOS:
        return guardado[1]

    ids = [p.ht_match_id for p in jugados]
    propios = {
        (r.ht_match_id, r.team_ht_id): r
        for r in (
            await session.execute(select(m.MatchRating).where(m.MatchRating.ht_match_id.in_(ids)))
        ).scalars()
    }
    # LOS QUE EL SYNC YA GUARDÓ DE CADA RIVAL (2026-09-13). El sync deja en
    # `rival_matches` los últimos cinco oficiales de cada contrincante y va
    # añadiendo la jornada nueva; esta cuenta los volvía a pedir a Hattrick
    # igualmente. Ahora se leen de ahí y sólo se paga lo que no está.
    guardados = {
        (r.ht_match_id, r.team_ht_id): r
        for r in (
            await session.execute(select(m.RivalMatch).where(m.RivalMatch.ht_match_id.in_(ids)))
        ).scalars()
    }

    lecturas: dict[int, list[dict[str, float]]] = {}
    for p in sorted(jugados, key=lambda x: x.ht_match_id):
        lados = (p.home_team_ht_id, p.away_team_ht_id)
        faltan = [
            t
            for t in lados
            if (p.ht_match_id, t) not in propios and (p.ht_match_id, t) not in guardados
        ]
        for equipo in lados:
            fila = propios.get((p.ht_match_id, equipo))
            if fila is not None:
                lecturas.setdefault(equipo, []).append(_de_fila(fila))
                continue
            guardada = guardados.get((p.ht_match_id, equipo))
            if guardada is not None and guardada.midfield:
                lecturas.setdefault(equipo, []).append(_de_fila_rival(guardada))
        if not faltan:
            continue
        try:
            d = await client.fetch("matchdetails", version_matchdetails, matchID=p.ht_match_id)
        except Exception as e:  # noqa: BLE001, un partido que falle no tumba la pantalla
            # A propósito no se propaga: la pantalla de Liga tiene que salir
            # aunque Hattrick no conteste por uno de los dieciocho partidos.
            # Se anota para poder verlo si un equipo sale con menos historia
            # de la que le toca.
            _log.info("sin ratings del partido %s: %s", p.ht_match_id, type(e).__name__)
            continue
        for lado in ("home", "away"):
            bloque = d.get(lado) or {}
            de_quien = bloque.get("team_id")
            if de_quien not in faltan:
                continue
            r = bloque.get("ratings") or {}
            if not r.get("midfield"):
                continue
            lecturas.setdefault(int(de_quien), []).append(
                {campo: float(r.get(DEL_LECTOR[campo]) or 0) for campo in CAMPOS}
                | {
                    "tactic_type": float(bloque.get("tactic_type") or 0),
                    "ht_match_id": float(p.ht_match_id),
                    "en_casa": 1.0 if lado == "home" else 0.0,
                }
            )

    _memoria[clave] = (time.monotonic(), lecturas)
    return lecturas


# ── Equipos de fuera de mi serie ────────────────────────────────────────────
#
# Un rival de Copa juega en otra serie, así que sus partidos NO están en
# `matches`: esa tabla sólo tiene los míos y el calendario de mi serie. Para
# tener su historia hay que descubrirla primero.
#
# `matchesarchive.xml` lo resuelve en UNA llamada por equipo, y desde la
# versión 1.5 trae `CupLevel`/`CupLevelIndex`, que es lo que permite separar
# liga de copa sin pedir nada más. La ventana la marca quien llama.

#: Cuánto dura la memoria del descubrimiento. Más larga que la de los ratings
#: porque una lista de partidos jugados sólo cambia cuando se juega otro, y
#: aquí el coste de equivocarse es pedirla de nuevo, no enseñar un dato viejo:
#: los ratings, que son lo que se ve, siguen con su TTL corto.
_TTL_ARCHIVO = 1800
_memoria_archivo: dict[tuple[int, str, str], tuple[float, list[dict[str, Any]]]] = {}


async def partidos_de_un_equipo(
    client: Any,
    version_archivo: str,
    ht_team_id: int,
    desde: datetime,
    hasta: datetime,
    tipos: tuple[int, ...],
) -> list[dict[str, Any]]:
    """Los partidos oficiales de un equipo cualquiera entre dos fechas.

    Sirve para equipos que NO son de mi serie --un rival de Copa, o cualquiera
    que se mire en Rivales--, cuyos partidos no están en la base.

    `tipos` es `TIPOS_DE_LIGA` o `TIPOS_DE_COPA`: el resumen de un equipo sale
    de UNA competición, y filtrar aquí evita traer ratings que luego habría
    que descartar.

    Devuelve `[]` si Hattrick no contesta. Una ficha sin historia se enseña
    sin predicción; nunca se tumba la pantalla por esto.
    """
    clave = (ht_team_id, desde.strftime("%Y-%m-%d"), ",".join(map(str, tipos)))
    guardado = _memoria_archivo.get(clave)
    if guardado is not None and time.monotonic() - guardado[0] < _TTL_ARCHIVO:
        return guardado[1]
    try:
        archivo = await client.fetch(
            "matchesarchive",
            version_archivo,
            teamID=ht_team_id,
            FirstMatchDate=desde.strftime("%Y-%m-%d %H:%M:%S"),
            LastMatchDate=hasta.strftime("%Y-%m-%d %H:%M:%S"),
        )
    except Exception as e:  # noqa: BLE001, sin historia se sigue sin predicción
        _log.info("sin archivo del equipo %s: %s", ht_team_id, type(e).__name__)
        return []
    out = [mt for mt in archivo.get("matches", []) if mt.get("match_type") in tipos]
    _memoria_archivo[clave] = (time.monotonic(), out)
    return out


async def lecturas_de_un_equipo(
    session: AsyncSession,
    client: Any,
    version_matchdetails: str,
    version_archivo: str,
    ht_team_id: int,
    desde: datetime,
    hasta: datetime,
    tipos: tuple[int, ...],
) -> list[dict[str, float]]:
    """Los nueve ratings de un equipo en cada uno de sus partidos, ordenados.

    Junta las dos fuentes en el orden correcto: lo que ya está guardado no se
    vuelve a pedir --mis propios partidos, y los de un rival contra mí, que el
    sync sí trae-- y sólo se pagan llamadas por lo que falta.
    """
    partidos = await partidos_de_un_equipo(client, version_archivo, ht_team_id, desde, hasta, tipos)
    if not partidos:
        return []
    ids = [mt["ht_match_id"] for mt in partidos]
    guardadas = {
        r.ht_match_id: r
        for r in (
            await session.execute(
                select(m.MatchRating).where(
                    m.MatchRating.ht_match_id.in_(ids),
                    m.MatchRating.team_ht_id == ht_team_id,
                )
            )
        ).scalars()
    }
    out: list[dict[str, float]] = []
    for mt in sorted(partidos, key=lambda x: x["ht_match_id"]):
        fila = guardadas.get(mt["ht_match_id"])
        if fila is not None:
            out.append(_de_fila(fila))
            continue
        try:
            d = await client.fetch("matchdetails", version_matchdetails, matchID=mt["ht_match_id"])
        except Exception as e:  # noqa: BLE001, un partido que falle no tumba nada
            _log.info("sin ratings del partido %s: %s", mt["ht_match_id"], type(e).__name__)
            continue
        for lado in ("home", "away"):
            bloque = d.get(lado) or {}
            if bloque.get("team_id") != ht_team_id:
                continue
            r = bloque.get("ratings") or {}
            # Sin mediocampo la lectura no sirve: una no comparecencia o un
            # partido que Hattrick devuelve a medias entraría con nueve ceros,
            # y un cero no es un rating bajo, es no saber.
            if not r.get("midfield"):
                continue
            out.append(
                {campo: float(r.get(DEL_LECTOR[campo]) or 0) for campo in CAMPOS}
                | {
                    "tactic_type": float(bloque.get("tactic_type") or 0),
                    "ht_match_id": float(mt["ht_match_id"]),
                    "en_casa": 1.0 if lado == "home" else 0.0,
                }
            )
    return out
