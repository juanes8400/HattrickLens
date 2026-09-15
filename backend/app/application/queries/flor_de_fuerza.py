"""Los sectores de cada equipo de la serie, para la flor del Dashboard.

2026-09-13, definido por el usuario: cada pétalo de la flor es
(X − mínimo de la serie) / (máximo − mínimo). Tres de esos pétalos salen de
los ratings de los partidos --medio campo, defensa y ataque en HatStats-- y se
resumen con la MEDIA DE LOS ÚLTIMOS CINCO PARTIDOS OFICIALES de cada equipo,
el tuyo incluido, para que todos se midan igual: de los rivales la app guarda
justo esa ventana (`RivalMatch`), así que con más partidos tuyos que suyos la
comparación sería desigual.

2026-09-15, también del usuario: mientras sigas en la Copa, tu PRÓXIMO rival de
Copa entra en la flor como uno más, marcado como de Copa. Va aparte de
`sectores_de_la_serie` a propósito: Habilidades (Profundidad) usa esa función
para medirte contra tu serie, y un equipo de otra serie ahí no pinta nada.

La normalización no se hace aquí sino en la pantalla, que junta estos tres con
TSI, forma, experiencia y resistencia de la comparativa de liga y con el puesto
esperado de la simulación.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.nombre_del_torneo import nombre_del_torneo, nombres_de_copa
from app.domain.engines.prediccion import TIPOS_OFICIALES
from app.domain.value_objects.ht_constants import MATCH_TYPE_CUP
from app.infrastructure.db import models as m

#: Partidos que entran en la media de cada equipo. Es la ventana que se guarda
#: de cada rival; más no habría para ellos.
PARTIDOS = 5


@dataclass(frozen=True)
class SectoresDeEquipo:
    ht_team_id: int
    nombre: str
    es_propio: bool
    partidos: int
    #: Medias de los últimos `partidos` oficiales. `None` si no hay ninguno.
    medio: float | None
    #: Defensa y ataque en HatStats: la suma de sus tres sectores.
    defensa: float | None
    ataque: float | None
    #: El próximo rival de Copa, que no es de tu serie.
    es_copa: bool = False
    #: Qué copa: «Copa Cocuy Rubí». Sólo con `es_copa`.
    copa: str | None = None


@dataclass(frozen=True)
class RivalDeCopa:
    ht_team_id: int
    nombre: str
    copa: str | None


def _media(valores: list[float]) -> float | None:
    return round(sum(valores) / len(valores), 2) if valores else None


def _resumen(filas: Iterable[Any]) -> list[tuple[float, float, float]]:
    """Medio campo, defensa y ataque de cada partido con mediocampo."""
    lecturas: list[tuple[float, float, float]] = []
    for r in filas:
        if r.midfield is None:
            continue
        lecturas.append(
            (
                float(r.midfield),
                float((r.left_def or 0) + (r.central_def or 0) + (r.right_def or 0)),
                float((r.left_att or 0) + (r.central_att or 0) + (r.right_att or 0)),
            )
        )
    return lecturas


async def _ultimos_de_un_rival(session: AsyncSession, ht_team_id: int) -> Iterable[Any]:
    return (
        await session.execute(
            select(m.RivalMatch)
            .where(
                m.RivalMatch.team_ht_id == ht_team_id,
                m.RivalMatch.match_type.in_(TIPOS_OFICIALES),
                m.RivalMatch.midfield.is_not(None),
            )
            .order_by(m.RivalMatch.played_at.desc())
            .limit(PARTIDOS)
        )
    ).scalars()


async def sectores_de_la_serie(session: AsyncSession, team: m.Team) -> list[SectoresDeEquipo]:
    """Una fila por equipo de la clasificación más reciente de tu serie."""
    propia = await session.scalar(
        select(m.Standing)
        .where(m.Standing.team_ht_id == team.ht_team_id)
        .order_by(m.Standing.captured_at.desc(), m.Standing.match_round.desc())
        .limit(1)
    )
    if propia is None:
        return []
    tabla = list(
        (
            await session.execute(
                select(m.Standing).where(
                    m.Standing.series_ht_id == propia.series_ht_id,
                    m.Standing.season == propia.season,
                    m.Standing.match_round == propia.match_round,
                )
            )
        ).scalars()
    )

    salida: list[SectoresDeEquipo] = []
    for fila in sorted(tabla, key=lambda s: s.position):
        es_propio = fila.team_ht_id == team.ht_team_id
        if es_propio:
            # Los tuyos, de tus partidos: `match_ratings` guarda los dos lados
            # y el tuyo es el de tu id (fiable en oficiales; sólo escaleras y
            # duelos usan ids efímeros, y no entran).
            filas: Iterable[Any] = (
                await session.execute(
                    select(m.MatchRating)
                    .join(m.Match, m.Match.ht_match_id == m.MatchRating.ht_match_id)
                    .where(
                        m.MatchRating.team_ht_id == team.ht_team_id,
                        m.Match.match_type.in_(TIPOS_OFICIALES),
                        m.Match.home_goals >= 0,
                    )
                    .order_by(m.Match.played_at.desc())
                    .limit(PARTIDOS)
                )
            ).scalars()
        else:
            filas = await _ultimos_de_un_rival(session, fila.team_ht_id)
        lecturas = _resumen(filas)
        salida.append(
            SectoresDeEquipo(
                ht_team_id=fila.team_ht_id,
                nombre=fila.team_name,
                es_propio=es_propio,
                partidos=len(lecturas),
                medio=_media([x[0] for x in lecturas]),
                defensa=_media([x[1] for x in lecturas]),
                ataque=_media([x[2] for x in lecturas]),
            )
        )
    return salida


async def rival_de_copa(session: AsyncSession, team: m.Team) -> RivalDeCopa | None:
    """Tu próximo rival de Copa, mientras sigas en ella; si no, nada.

    Sólo la Copa de verdad (tipo 3): el Hattrick Masters no es «Copa». Si
    Hattrick ya dijo que estás fuera (`still_in_cup` falso) no hay rival aunque
    quede un partido viejo sin marcar como jugado en el calendario.
    """
    if team.still_in_cup is False:
        return None
    proximo = await session.scalar(
        select(m.Match)
        .where(
            (m.Match.home_team_ht_id == team.ht_team_id)
            | (m.Match.away_team_ht_id == team.ht_team_id),
            m.Match.match_type == MATCH_TYPE_CUP,
            func.upper(m.Match.status) != "FINISHED",
        )
        .order_by(m.Match.played_at)
        .limit(1)
    )
    if proximo is None:
        return None
    en_casa = proximo.home_team_ht_id == team.ht_team_id
    rival_id = proximo.away_team_ht_id if en_casa else proximo.home_team_ht_id
    if not rival_id:
        return None
    copa = (
        team.current_cup_name
        if team.still_in_cup and team.current_cup_name
        else nombre_del_torneo(
            proximo.match_type,
            proximo.cup_level,
            proximo.cup_level_index,
            await nombres_de_copa(session, team),
        )
    )
    return RivalDeCopa(
        ht_team_id=rival_id,
        nombre=proximo.away_team_name if en_casa else proximo.home_team_name,
        copa=copa,
    )


async def sectores_del_rival_de_copa(
    session: AsyncSession, team: m.Team, de_la_serie: set[int]
) -> SectoresDeEquipo | None:
    """La fila de tu próximo rival de Copa, con la misma regla que los de liga.

    Si ese rival es de tu propia serie ya está en la flor como equipo de liga,
    y repetirlo lo contaría dos veces.
    """
    copa = await rival_de_copa(session, team)
    if copa is None or copa.ht_team_id in de_la_serie:
        return None
    lecturas = _resumen(await _ultimos_de_un_rival(session, copa.ht_team_id))
    return SectoresDeEquipo(
        ht_team_id=copa.ht_team_id,
        nombre=copa.nombre,
        es_propio=False,
        partidos=len(lecturas),
        medio=_media([x[0] for x in lecturas]),
        defensa=_media([x[1] for x in lecturas]),
        ataque=_media([x[2] for x in lecturas]),
        es_copa=True,
        copa=copa.copa,
    )
