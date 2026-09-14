"""Los sectores de cada equipo de la serie, para la flor del Dashboard.

2026-09-13, definido por el usuario: cada pétalo de la flor es
(X − mínimo de la serie) / (máximo − mínimo). Tres de esos pétalos salen de
los ratings de los partidos --medio campo, defensa y ataque en HatStats-- y se
resumen con la MEDIA DE LOS ÚLTIMOS CINCO PARTIDOS OFICIALES de cada equipo,
el tuyo incluido, para que todos se midan igual: de los rivales la app guarda
justo esa ventana (`RivalMatch`), así que con más partidos tuyos que suyos la
comparación sería desigual.

La normalización no se hace aquí sino en la pantalla, que junta estos tres con
TSI, forma, experiencia y condición de la comparativa de liga y con el puesto
esperado de la simulación.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.engines.prediccion import TIPOS_OFICIALES
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


def _media(valores: list[float]) -> float | None:
    return round(sum(valores) / len(valores), 2) if valores else None


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
        lecturas: list[tuple[float, float, float]] = []
        if es_propio:
            # Los tuyos, de tus partidos: `match_ratings` guarda los dos lados
            # y el tuyo es el de tu id (fiable en oficiales; sólo escaleras y
            # duelos usan ids efímeros, y no entran).
            filas = (
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
            filas = (  # type: ignore[assignment]
                await session.execute(
                    select(m.RivalMatch)
                    .where(
                        m.RivalMatch.team_ht_id == fila.team_ht_id,
                        m.RivalMatch.match_type.in_(TIPOS_OFICIALES),
                        m.RivalMatch.midfield.is_not(None),
                    )
                    .order_by(m.RivalMatch.played_at.desc())
                    .limit(PARTIDOS)
                )
            ).scalars()
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
