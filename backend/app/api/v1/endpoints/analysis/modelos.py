"""Calibraciones que la aplicacion ensena por transparencia.

Sale de partir `analysis.py`, que tenia 2309 lineas y se abria
entera para tocar cualquiera de sus rutas. El `__init__.py` del paquete
monta `router` con todos estos, asi que las URL no cambian.
"""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_team_owner
from app.api.v1.endpoints.analysis.plantilla import roster
from app.application.queries.player_history import PlayerHistoryQueryService
from app.domain.engines.experience_engine import (
    calibrate,
)
from app.domain.engines.experience_engine import model_info as experience_model_info
from app.domain.engines.loyalty_engine import model_info as loyalty_model_info
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session

router = APIRouter()


@router.get(
    "/teams/{team_id}/experience/calibration",
    summary="Puntos por nivel medidos, no declarados (HL-041)",
    dependencies=[Depends(require_team_owner)],
)
async def experience_calibration(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """How many experience points a level actually costs, measured from history.

    The specification says 28. Rather than assert that, the engine watches every
    fully observed interval between two experience level-ups, totals the real
    matches played in that interval, and reports their mean together with the
    standard deviation, the part that says whether the mean can be trusted.

    Until enough crossings have accumulated the configured 28 stands and the
    response says so plainly, along with how many more are needed. Nothing here
    pretends to a precision it does not have.
    """
    await roster(session, team_id)  # 404s on an unknown team

    history = PlayerHistoryQueryService(session)
    level_ups, crossings_seen = await history.experience_level_up_observations(team_id)

    cal = calibrate(level_ups)
    info = experience_model_info(cal)
    minimum = 5
    info["observationsNeeded"] = max(minimum - cal.observations, 0)
    info["crossingsSeen"] = crossings_seen
    info["discardedCrossings"] = crossings_seen - len(level_ups)
    info["distinctReadings"] = int(
        await session.scalar(
            select(func.count(m.PlayerSnapshot.id))
            .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
            .where(m.Player.team_id == team_id)
        )
        or 0
    )
    info["levelUps"] = [
        {
            "player": lu.player,
            "fromLevel": lu.from_level,
            "toLevel": lu.to_level,
            "pointsAccumulated": lu.points_accumulated,
        }
        for lu in level_ups
    ]

    # Subidas confirmadas por Hattrick (trainingevents). Importante: validan la
    # fórmula de ENTRENAMIENTO (habilidades entrenadas), no los puntos por nivel
    # de EXPERIENCIA, que dependen de partidos jugados. Se declaran aquí para
    # que no se confundan las dos mecánicas.
    confirmed = await session.scalar(
        select(func.count(m.SkillUp.id)).where(m.SkillUp.team_id == team_id)
    )
    info["confirmedSkillUps"] = int(confirmed or 0)
    info["confirmedSkillUpsNote"] = (
        "Las subidas confirmadas de trainingevents validan la fórmula de "
        "entrenamiento (ver /training/formula), no estos puntos de experiencia: "
        "son mecánicas distintas. La experiencia se calibra con partidos."
    )
    return info


@router.get(
    "/teams/{team_id}/loyalty/model",
    summary="Fórmula de Fidelidad según los días transcurridos desde la compra",
    dependencies=[Depends(require_team_owner)],
)
async def loyalty_model(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Expone la única regla usada por la ficha y sus umbrales enteros."""
    await roster(session, team_id)  # 404s on an unknown team
    return loyalty_model_info()
