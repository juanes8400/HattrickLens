"""Club y cuerpo tecnico.

Sale de partir `teams.py`, que tenia 1179 lineas y se abria
entera para tocar cualquiera de sus rutas. El `__init__.py` del paquete
monta `router` con todos estos, asi que las URL no cambian.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cache_por_sync import por_sync
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

    # GUARDADO HASTA EL PRÓXIMO SYNC (2026-11-21): 36 consultas en cada
    # visita a Club y a Entrenamiento, de datos que sólo cambian al sincronizar.
    async def calcular() -> dict[str, Any] | None:
        return await ClubQueryService(session).get(team_id)

    data: dict[str, Any] | None = await por_sync(session, team_id, "club", (), calcular)
    if data is None:
        raise HTTPException(404, f"team {team_id} not found")
    return data
