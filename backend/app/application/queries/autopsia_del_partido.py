"""La autopsia del último partido (2026-11-22, pedido del usuario: «hacerle una
autopsia completa al partido como tal y a la predicción»).

Vive debajo del parte de Partidos → Último partido. El parte dice «esto
dijimos y esto pasó»; la autopsia abre el porqué, en tres capas del MISMO
motor de predicción:

  1. Lo que dijimos: la fila guardada antes del pitido (`MatchPrediction`).
  2. Con lo real tuyo y lo supuesto del rival: tus valoraciones y tu táctica
     tal como salieron, con el rival como lo suponíamos. Sólo existe si al
     predecir se guardó lo supuesto (`supuesto_json`, desde la 7.1.0).
  3. Con lo real de los dos: lo que habría dicho el motor sabiendo lo que de
     verdad salió al campo.

De 1 a 2 se mueve lo que cambió tu equipo; de 2 a 3, lo que cambió el rival.
Si con lo real lo más probable era lo que pasó, el fallo fue de INFORMACIÓN;
si ni con lo real lo era, pasó lo improbable.

LÍMITE QUE LA PANTALLA DICE: en un solo partido no se distingue «el motor se
equivocó» de «mala suerte». Y esto NUNCA se usa para ajustar el motor: la
regla del 14 de agosto de 2026 prohíbe ajustar modelos con los partidos del
propietario. Aquí sólo se vuelve a pasar el motor, que es comprobar.

Como el parte, DEVUELVE CLAVES Y NÚMEROS, NO FRASES: la pantalla escribe el
veredicto, para que se pueda traducir.
"""

import json
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.application.queries.parte_del_partido import ultimo_partido_jugado
from app.domain.engines.prediccion import (
    CAMPOS,
    TIPOS_DE_COPA,
    Probabilidades,
    factor_de_tactica,
    marcador_mas_probable,
    probabilidades_de_copa,
    probabilidades_del_motor,
)
from app.infrastructure.db import models as m

Resultado = Literal["gana", "empate", "pierde"]

#: Los siete sectores de campo, los que se enseñan. Las dos indirectas a balón
#: parado entran en el motor pero no en la tabla: Hattrick no las prevé con
#: las órdenes, así que lo «supuesto» de ellas casi nunca es una suposición.
SECTORES = (
    "midfield",
    "left_def",
    "central_def",
    "right_def",
    "left_att",
    "central_att",
    "right_att",
)

#: Los duelos de un partido, desde el sector PROPIO: con quién se cruza.
DUELOS: tuple[tuple[str, str], ...] = (
    ("midfield", "midfield"),
    ("left_att", "right_def"),
    ("central_att", "central_def"),
    ("right_att", "left_def"),
    ("left_def", "right_att"),
    ("central_def", "central_att"),
    ("right_def", "left_att"),
)

#: «Por debajo de su media»: una estrella o más por debajo de la media de sus
#: partidos anteriores, y con al menos tres de ellos para que haya media.
ESTRELLAS_POR_DEBAJO = 1.0
PARTIDOS_PARA_MEDIA = 3
#: Cuántos partidos anteriores entran en la media: los últimos diez.
VENTANA_DE_LA_MEDIA = 10


def _valoraciones(fila: m.MatchRating) -> dict[str, float]:
    """Los nueve números del motor desde una fila guardada. Sin indirectas
    queda `None` en vez de cero: un cero no es «bajo», es no saber."""
    return {
        "midfield": float(fila.midfield or 0),
        "left_def": float(fila.left_def or 0),
        "central_def": float(fila.central_def or 0),
        "right_def": float(fila.right_def or 0),
        "left_att": float(fila.left_att or 0),
        "central_att": float(fila.central_att or 0),
        "right_att": float(fila.right_att or 0),
        **({} if fila.set_pieces_def is None else {"sp_def": float(fila.set_pieces_def)}),
        **({} if fila.set_pieces_att is None else {"sp_att": float(fila.set_pieces_att)}),
    }


def _completas(real: dict[str, float], respaldo: dict[str, float] | None) -> dict[str, float]:
    """Las indirectas que falten salen de lo supuesto, y si tampoco hay, de la
    media de los siete sectores: el motor necesita los nueve."""
    completas = dict(real)
    media = sum(real[c] for c in SECTORES) / len(SECTORES)
    for campo in CAMPOS:
        if campo not in completas:
            completas[campo] = float((respaldo or {}).get(campo, media))
    return completas


def _capa(
    clave: str,
    mio: dict[str, float],
    suyo: dict[str, float],
    factor_mio: float,
    factor_suyo: float,
    copa: bool,
) -> dict[str, Any]:
    terna: Probabilidades = (
        probabilidades_de_copa(mio, suyo, factor_mio, factor_suyo)
        if copa
        else probabilidades_del_motor(mio, suyo, factor_mio, factor_suyo)
    )
    marcador = marcador_mas_probable(mio, suyo, factor_mio, factor_suyo)
    return {
        "clave": clave,
        "gana": round(terna.victoria, 4),
        "empate": round(terna.empate, 4),
        "pierde": round(terna.derrota, 4),
        "marcador": f"{marcador[0]}-{marcador[1]}",
    }


def _favorito(capa: dict[str, Any]) -> Resultado:
    opciones: list[tuple[float, Resultado]] = [
        (capa["gana"], "gana"),
        (capa["empate"], "empate"),
        (capa["pierde"], "pierde"),
    ]
    return max(opciones, key=lambda o: o[0])[1]


#: Por debajo de esto un duelo no «pesó»: medio punto de probabilidad.
PESO_MINIMO = 0.005


def lo_que_mas_peso(
    propio: dict[str, float],
    rival: dict[str, float],
    factor_propio: float,
    factor_rival: float,
    copa: bool,
) -> dict[str, dict[str, Any] | None]:
    """Qué duelo pesó más a favor y cuál frenó más (2026-11-22, pedido del
    usuario: «¿por qué eso es lo que más afecta?»).

    Antes se nombraba el duelo con el reparto más desigual, que dice dónde
    hubo más ventaja pero no cuánto importó: un carril por el que apenas se
    ataca puede ir 77 % – 23 % sin mover el resultado, y el medio campo pesa
    más que cualquier carril. Ahora se IGUALA cada duelo --los dos sectores a
    su media, 50 % – 50 %-- y se vuelve a pasar el mismo motor: lo que baja tu
    probabilidad de ganar al igualarlo es lo que te ayudó, y lo que la sube es
    lo que te frenó. No se ajusta nada: es el motor de siempre, preguntado.
    """
    base = _capa("real", propio, rival, factor_propio, factor_rival, copa)["gana"]
    pesos: list[tuple[float, str, str, float]] = []
    for mio, suyo in DUELOS:
        media = (propio[mio] + rival[suyo]) / 2
        igualado = _capa(
            "igualado",
            {**propio, mio: media},
            {**rival, suyo: media},
            factor_propio,
            factor_rival,
            copa,
        )["gana"]
        pesos.append((base - igualado, mio, suyo, igualado))

    def describir(peso: tuple[float, str, str, float]) -> dict[str, Any]:
        return {
            "sector": peso[1],
            "contra": peso[2],
            "gana": round(base, 4),
            "igualado": round(peso[3], 4),
        }

    a_favor = max(pesos)
    en_contra = min(pesos)
    return {
        "aFavor": describir(a_favor) if a_favor[0] >= PESO_MINIMO else None,
        "enContra": describir(en_contra) if en_contra[0] <= -PESO_MINIMO else None,
    }


def veredicto(
    resultado: Resultado,
    capas: dict[str, dict[str, Any]],
    propio: dict[str, float],
    rival: dict[str, float],
    supuesto: dict[str, Any] | None,
) -> dict[str, Any]:
    """De qué fue el partido, en claves. Lo que más pesó va aparte, en
    `lo_que_mas_peso`, y la pantalla lo pinta detrás en todos los casos.

    · `sinPrediccion`: no guardamos qué dijimos.
    · `esperado`: pasó lo que dábamos como más probable.
    · `informacion`: con lo real, lo más probable ERA lo que pasó. El fallo
      estuvo en lo que suponíamos; `culpa` dice de qué lado se movió más la
      probabilidad de lo que pasó, y `sector` qué sector de ese lado salió
      más distinto de lo supuesto.
    · `azar`: ni con lo real era lo más probable.
    """
    dicho = capas.get("dicho")
    if dicho is None:
        return {"tipo": "sinPrediccion", "culpa": None, "sector": None}
    if _favorito(dicho) == resultado:
        return {"tipo": "esperado", "culpa": None, "sector": None}
    if _favorito(capas["real"]) != resultado:
        return {"tipo": "azar", "culpa": None, "sector": None}
    intermedia = capas.get("realPropio")
    if intermedia is None or supuesto is None:
        return {"tipo": "informacion", "culpa": None, "sector": None}
    lo_mio = abs(intermedia[resultado] - dicho[resultado])
    lo_suyo = abs(capas["real"][resultado] - intermedia[resultado])
    culpa: Literal["propio", "rival"] = "propio" if lo_mio >= lo_suyo else "rival"
    real, antes = (propio, supuesto["propio"]) if culpa == "propio" else (rival, supuesto["rival"])
    sector = max(SECTORES, key=lambda s: abs(real[s] - float(antes.get(s, real[s]))))
    return {"tipo": "informacion", "culpa": culpa, "sector": sector}


async def _por_debajo_de_su_media(
    session: AsyncSession, team_id: int, ht_match_id: int
) -> list[dict[str, Any]]:
    """Los jugadores propios que en este partido sacaron una estrella o más
    por debajo de la media de sus partidos anteriores. Es descriptivo: una
    media y una resta, nada ajustado."""
    filas = (
        await session.execute(
            select(m.PlayerMatchRating, m.Player)
            .join(m.Player, m.Player.id == m.PlayerMatchRating.player_id)
            .where(
                m.PlayerMatchRating.ht_match_id == ht_match_id,
                m.Player.team_id == team_id,
                m.PlayerMatchRating.rating > 0,
            )
        )
    ).all()
    flojos: list[dict[str, Any]] = []
    for nota, jugador in filas:
        antes = (
            await session.scalars(
                select(m.PlayerMatchRating.rating)
                .where(
                    m.PlayerMatchRating.player_id == jugador.id,
                    m.PlayerMatchRating.ht_match_id != ht_match_id,
                    m.PlayerMatchRating.captured_at <= nota.captured_at,
                    m.PlayerMatchRating.rating > 0,
                )
                .order_by(m.PlayerMatchRating.captured_at.desc())
                .limit(VENTANA_DE_LA_MEDIA)
            )
        ).all()
        if len(antes) < PARTIDOS_PARA_MEDIA:
            continue
        media = sum(antes) / len(antes)
        if nota.rating <= media - ESTRELLAS_POR_DEBAJO:
            flojos.append(
                {
                    "htPlayerId": jugador.ht_player_id,
                    "nombre": f"{jugador.first_name} {jugador.last_name}".strip(),
                    "estrellas": nota.rating,
                    "media": round(media, 1),
                    "partidos": len(antes),
                }
            )
    flojos.sort(key=lambda f: f["estrellas"] - f["media"])
    return flojos


async def autopsia_del_partido(session: AsyncSession, team_id: int) -> dict[str, Any] | None:
    """La autopsia del mismo partido que el parte. `None` si no hay partido;
    `sinValoraciones` si aún no llegaron las valoraciones de los dos lados."""
    team = await session.scalar(
        select(m.Team)
        .options(load_only(m.Team.id, m.Team.ht_team_id, raiseload=True))
        .where(m.Team.id == team_id)
    )
    if team is None:
        return None
    partido = await ultimo_partido_jugado(session, team.ht_team_id)
    if partido is None:
        return None

    en_casa = partido.home_team_ht_id == team.ht_team_id
    filas = (
        await session.scalars(
            select(m.MatchRating).where(m.MatchRating.ht_match_id == partido.ht_match_id)
        )
    ).all()
    propia = next((f for f in filas if f.team_ht_id == team.ht_team_id), None)
    suya = next((f for f in filas if f.team_ht_id != team.ht_team_id), None)
    base = {"htMatchId": partido.ht_match_id}
    if propia is None or suya is None:
        return {**base, "sinValoraciones": True}

    goles = (partido.home_goals, partido.away_goals)
    mios, suyos = goles if en_casa else goles[::-1]
    resultado: Resultado = "gana" if mios > suyos else "pierde" if mios < suyos else "empate"
    copa = partido.match_type in TIPOS_DE_COPA

    dicho_fila = await session.scalar(
        select(m.MatchPrediction).where(
            m.MatchPrediction.ht_match_id == partido.ht_match_id,
            m.MatchPrediction.team_id == team_id,
        )
    )
    supuesto: dict[str, Any] | None = None
    if dicho_fila is not None and dicho_fila.supuesto_json:
        try:
            supuesto = json.loads(dicho_fila.supuesto_json)
        except ValueError:
            supuesto = None

    real_propio = _completas(_valoraciones(propia), supuesto and supuesto.get("propio"))
    real_rival = _completas(_valoraciones(suya), supuesto and supuesto.get("rival"))
    factor_propio = factor_de_tactica(exacta=propia.tactic_type)
    factor_rival = factor_de_tactica(exacta=suya.tactic_type)

    capas: dict[str, dict[str, Any]] = {}
    if dicho_fila is not None:
        # Guardada desde el LOCAL: se pone del lado propio.
        gana, pierde = (
            (dicho_fila.home_win, dicho_fila.away_win)
            if en_casa
            else (dicho_fila.away_win, dicho_fila.home_win)
        )
        marcador = dicho_fila.most_likely_score
        if not en_casa and "-" in marcador:
            local, visita = marcador.split("-", 1)
            marcador = f"{visita}-{local}"
        capas["dicho"] = {
            "clave": "dicho",
            "gana": round(gana, 4),
            "empate": round(dicho_fila.draw, 4),
            "pierde": round(pierde, 4),
            "marcador": marcador,
        }
    if supuesto is not None:
        capas["realPropio"] = _capa(
            "realPropio",
            real_propio,
            _completas(supuesto["rival"], None),
            factor_propio,
            float(supuesto.get("factorRival", 1.0)),
            copa,
        )
    capas["real"] = _capa("real", real_propio, real_rival, factor_propio, factor_rival, copa)

    comparacion = (
        []
        if supuesto is None
        else [
            {
                "lado": lado,
                "sector": s,
                "supuesto": round(float(antes[s]), 2),
                "real": round(real[s], 2),
            }
            for lado, antes, real in (
                ("propio", supuesto["propio"], real_propio),
                ("rival", supuesto["rival"], real_rival),
            )
            for s in SECTORES
            if s in antes
        ]
    )

    return {
        **base,
        "sinValoraciones": False,
        "resultado": resultado,
        "copa": copa,
        "fuente": None if dicho_fila is None else dicho_fila.source,
        "capas": list(capas.values()),
        "supuestoVsReal": comparacion,
        "veredicto": veredicto(resultado, capas, real_propio, real_rival, supuesto),
        "loQueMasPeso": lo_que_mas_peso(real_propio, real_rival, factor_propio, factor_rival, copa),
        "porDebajoDeSuMedia": await _por_debajo_de_su_media(session, team_id, partido.ht_match_id),
    }
