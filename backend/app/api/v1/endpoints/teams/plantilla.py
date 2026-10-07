"""La plantilla.

Sale de partir `teams.py`, que tenia 1179 lineas y se abria
entera para tocar cualquiera de sus rutas. El `__init__.py` del paquete
monta `router` con todos estos, asi que las URL no cambian.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import (
    get_squad_service,
    require_team_owner,
)
from app.application.dto.squad import SquadResponse
from app.application.queries.squad import SquadQueryService

router = APIRouter()


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
) -> SquadResponse:
    try:
        data = await svc.get(team_id, position, comparison_window)
    except KeyError as exc:
        raise HTTPException(400, str(exc)) from exc
    if data is None:
        raise HTTPException(404, f"team {team_id} not found")
    return data
