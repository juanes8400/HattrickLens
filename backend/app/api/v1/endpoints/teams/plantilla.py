"""La plantilla.

Sale de partir `teams.py`, que tenia 1179 lineas y se abria
entera para tocar cualquiera de sus rutas. El `__init__.py` del paquete
monta `router` con todos estos, asi que las URL no cambian.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cache_por_sync import TTL_CON_RELOJ, por_sync
from app.api.deps import (
    get_squad_service,
    require_team_owner,
)
from app.application.dto.squad import SquadResponse
from app.application.queries.squad import SquadQueryService
from app.infrastructure.db.session import get_session

router = APIRouter()


async def plantilla_guardada(
    session: AsyncSession,
    team_id: int,
    position: str | None = None,
    comparison_window: str | None = None,
    svc: SquadQueryService | None = None,
) -> SquadResponse | None:
    """La plantilla, guardada (2026-11-21: la piden Plantilla, Posiciones,
    Alineación, Transferencias, Novedades y la ficha de cada jugador, y cada
    una la recalculaba entera). Con reloj --edades y días--, así que dura como
    mucho `TTL_CON_RELOJ`; y es editable, así que una edición la olvida."""

    async def calcular() -> SquadResponse | None:
        return await (svc or SquadQueryService(session)).get(team_id, position, comparison_window)

    resultado: SquadResponse | None = await por_sync(
        session,
        team_id,
        "plantilla",
        (position, comparison_window),
        calcular,
        ttl=TTL_CON_RELOJ,
    )
    return resultado


@router.get(
    "/{team_id}/squad",
    response_model=SquadResponse,
    response_model_by_alias=True,
    summary="Plantilla con rating de posición (HL-021, HL-022)",
    dependencies=[Depends(require_team_owner)],
)
async def squad(
    team_id: int,
    position: str | None = Query(
        None,
        description="Si se indica, la plantilla se ordena por el rendimiento en esa posición",
    ),
    comparison_window: str | None = Query(
        None,
        description=(
            "Contra qué se miran las diferencias: change (el último cambio de cada "
            "jugador, por defecto), w1, w2, w4, w8, w16 o all"
        ),
    ),
    svc: SquadQueryService = Depends(get_squad_service),
    session: AsyncSession = Depends(get_session),
) -> SquadResponse:
    try:
        data = await plantilla_guardada(session, team_id, position, comparison_window, svc)
    except KeyError as exc:
        raise HTTPException(400, str(exc)) from exc
    if data is None:
        raise HTTPException(404, f"team {team_id} not found")
    return data
