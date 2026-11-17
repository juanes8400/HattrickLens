"""La plantilla.

Sale de partir `analysis.py`, que tenia 2309 lineas y se abria
entera para tocar cualquiera de sus rutas. El `__init__.py` del paquete
monta `router` con todos estos, asi que las URL no cambian.
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.squad import SquadQueryService, jugador_para_el_motor
from app.infrastructure.db import models as m

router = APIRouter()


async def roster(session: AsyncSession, team_id: int) -> tuple[list[dict[str, Any]], m.Team]:
    team = await session.get(m.Team, team_id)
    if team is None:
        raise HTTPException(404, f"team {team_id} not found")
    rows = await SquadQueryService(session)._latest(team_id)
    players = [jugador_para_el_motor(snap, ident) for snap, ident in rows]
    return players, team
