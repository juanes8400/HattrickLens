"""El panel de inicio.

Sale de partir `teams.py`, que tenia 1179 lineas y se abria
entera para tocar cualquiera de sus rutas. El `__init__.py` del paquete
monta `router` con todos estos, asi que las URL no cambian.
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    require_team_owner,
)
from app.application.dto.dashboard import DashboardResponse
from app.application.queries.dashboard import DashboardQueryService
from app.infrastructure.db.session import get_session

router = APIRouter()


async def dashboard_guardado(session: AsyncSession, team_id: int) -> DashboardResponse | None:
    """El Dashboard, calculado una vez por sync (2026-09-14).

    Medido en producción: 5 segundos en cada visita aunque nada hubiera
    cambiado. Tope de 15 minutos porque «datos desactualizados» mira el reloj.
    Lo usan el endpoint y el precalentado del final del sync.
    """
    from app.api.cache_por_sync import TTL_CON_RELOJ, por_sync

    data: DashboardResponse | None = await por_sync(
        session,
        team_id,
        "dashboard",
        (),
        lambda: DashboardQueryService(session).get(team_id),
        ttl=TTL_CON_RELOJ,
    )
    return data


@router.get(
    "/{team_id}/dashboard",
    response_model=DashboardResponse,
    response_model_by_alias=True,
    dependencies=[Depends(require_team_owner)],
)
async def dashboard(
    team_id: int,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> DashboardResponse:
    data = await dashboard_guardado(session, team_id)
    if data is None:
        raise HTTPException(404, f"team {team_id} not found")
    # Cache barato: el payload solo cambia cuando cambia el sync (docs/04)
    if data.sync_id is not None:
        response.headers["ETag"] = f'W/"dash-{team_id}-{data.sync_id}"'
        response.headers["Cache-Control"] = "private, max-age=30"
    return data
