"""Habilidades: mapa de la plantilla, profundidad y cuello de botella."""

from dataclasses import asdict
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_team_owner
from app.api.v1.endpoints.arena import _camel
from app.application.queries.habilidades import HabilidadesQueryService
from app.infrastructure.db.session import get_session

router = APIRouter()


@router.get(
    "/teams/{team_id}/skills",
    summary="Equipo: mapa de la plantilla, profundidad y cuello de botella",
    dependencies=[Depends(require_team_owner)],
)
async def skills(
    team_id: int,
    formation: str | None = Query(
        None, description="Formación para Profundidad. Sin ella, la del último partido oficial"
    ),
    central_defenders: int | None = Query(None, description="Defensas Centrales de esa formación"),
    inner_midfielders: int | None = Query(None, description="Mediocentros de esa formación"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    data = await HabilidadesQueryService(session).get(
        team_id, formation, central_defenders, inner_midfielders
    )
    if data is None:
        raise HTTPException(404, f"team {team_id} not found")
    return cast(dict[str, Any], _camel(asdict(data)))
