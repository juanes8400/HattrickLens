"""El próximo partido OFICIAL del equipo, para el Dashboard (2026-11-18).

Pedido del usuario: «El partido featureado en "Próximo Partido" de Dashboard,
debe ser el Próximo Partido Oficial (Liga, Copa, Copa Desafío, Hattrick
Masters, Promoción), no simplemente el próximo de Liga». Antes el panel
salía del modelo de liga, así que un cruce de copa el mismo día no aparecía.

Sale de los partidos ya guardados por la sincronización, sin llamar a
Hattrick. Oficial = ni amistoso ni torneo/duelo/escalera/preparación, la
misma regla que el resto de la app (`is_competitive_match_type`).
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.nombre_del_torneo import nombre_del_torneo, nombres_de_copa
from app.domain.value_objects.ht_constants import is_competitive_match_type
from app.infrastructure.db import models as m


@dataclass(frozen=True)
class ProximoPartidoOficial:
    ht_match_id: int
    match_type: int
    tournament: str
    played_at: datetime
    home: str
    away: str
    is_home: bool
    rival_ht_id: int
    #: Si Hattrick dice que ya hay órdenes enviadas; None si no lo dijo.
    orders_given: bool | None
    #: Jornada, sólo en liga.
    round: int | None


async def proximo_partido_oficial(
    session: AsyncSession, team_id: int, ahora: datetime | None = None
) -> ProximoPartidoOficial | None:
    team = await session.get(m.Team, team_id)
    if team is None:
        return None
    momento = ahora or datetime.now(UTC)
    pendientes = (
        (
            await session.execute(
                select(m.Match)
                .where(
                    or_(
                        m.Match.home_team_ht_id == team.ht_team_id,
                        m.Match.away_team_ht_id == team.ht_team_id,
                    ),
                    m.Match.status == "UPCOMING",
                    m.Match.played_at >= momento,
                )
                .order_by(m.Match.played_at)
                .limit(20)
            )
        )
        .scalars()
        .all()
    )
    siguiente = next((x for x in pendientes if is_competitive_match_type(x.match_type)), None)
    if siguiente is None:
        return None
    en_casa = siguiente.home_team_ht_id == team.ht_team_id
    return ProximoPartidoOficial(
        ht_match_id=siguiente.ht_match_id,
        match_type=siguiente.match_type,
        tournament=nombre_del_torneo(
            siguiente.match_type,
            siguiente.cup_level,
            siguiente.cup_level_index,
            await nombres_de_copa(session, team),
        ),
        played_at=siguiente.played_at,
        home=siguiente.home_team_name,
        away=siguiente.away_team_name,
        is_home=en_casa,
        rival_ht_id=siguiente.away_team_ht_id if en_casa else siguiente.home_team_ht_id,
        orders_given=siguiente.orders_given,
        round=siguiente.match_round,
    )
