"""Club y cuerpo tecnico.

Sale de partir `teams.py`, que tenia 1179 lineas y se abria
entera para tocar cualquiera de sus rutas. El `__init__.py` del paquete
monta `router` con todos estos, asi que las URL no cambian.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    require_team_owner,
)
from app.application.queries.club import ClubQueryService
from app.infrastructure.db.session import get_session

router = APIRouter()


@router.get(
    "/{team_id}/club",
    summary="Estado, evolución y cuerpo técnico del club",
    dependencies=[Depends(require_team_owner)],
)
async def club(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Equivalente moderno de Club, Gráfico y Empleados de Hattrick Control.

    Expone sólo observaciones CHPP y conserva las tres series separadas para
    no convertir una lectura puntual en una tendencia ficticia.
    """
    data = await ClubQueryService(session).get(team_id)
    if data is None:
        raise HTTPException(404, f"team {team_id} not found")
    return data
