"""Los ratings de todos los equipos de la serie, para el modelo de zonas.

DE DÓNDE SALEN. La aplicación guarda los ratings de los partidos PROPIOS; de
la serie sólo tiene el calendario y los marcadores. Así que los de los rivales
se piden en vivo, uno por partido jugado, igual que hace la ficha de rival.

NO SE GUARDAN, y es a propósito: son partidos de cuentas ajenas, y la misma
decisión que ya vive en la ficha de rival vale aquí. Se pagan las llamadas cada
vez y se sostienen con la memoria corta de más abajo.

CUÁNTO CUESTA. Una serie de ocho equipos con seis jornadas jugadas son 24
partidos, de los que seis son propios y ya están guardados: 18 llamadas.
Medido el 2026-09-06, una llamada tarda 0,24 segundos, así que son unos cuatro
segundos la primera vez y cero las siguientes mientras dure la memoria.
"""

from __future__ import annotations

import logging
import time
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
#: guarda un cero. Un cero ahí no es un rating bajo — es no saber — y la
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


def _de_fila(fila: m.MatchRating) -> dict[str, float]:
    """Los nueve ratings de una fila ya guardada."""
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

    lecturas: dict[int, list[dict[str, float]]] = {}
    for p in sorted(jugados, key=lambda x: x.ht_match_id):
        lados = (p.home_team_ht_id, p.away_team_ht_id)
        faltan = [t for t in lados if (p.ht_match_id, t) not in propios]
        for equipo in lados:
            fila = propios.get((p.ht_match_id, equipo))
            if fila is not None:
                lecturas.setdefault(equipo, []).append(_de_fila(fila))
        if not faltan:
            continue
        try:
            d = await client.fetch("matchdetails", version_matchdetails, matchID=p.ht_match_id)
        except Exception as e:  # noqa: BLE001 — un partido que falle no tumba la pantalla
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
            )

    _memoria[clave] = (time.monotonic(), lecturas)
    return lecturas
