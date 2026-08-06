"""Estadio. HL-060, HL-061, HL-063, HL-064."""
from dataclasses import asdict
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.arena import ArenaQueryService
from app.infrastructure.db.session import get_session

router = APIRouter()


@router.get("/teams/{team_id}/arena", summary="Ocupación, demanda censurada y ampliación")
async def arena(
    team_id: int,
    fill_rate: float | None = Query(
        None, ge=0.0, le=1.0,
        description=(
            "Fracción de los asientos NUEVOS que se espera vender. Si se omite "
            "se usa la ocupación media observada, que sólo es una estimación "
            "válida cuando ningún sector se agotó."
        ),
    ),
    include_non_official: bool = Query(
        False, description="Incluir Escaleras/Duelos (no son partidos oficiales)"
    ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """El estadio, con la censura de demanda declarada en vez de escondida.

    Cuando un sector se agota, la asistencia deja de medir cuánta gente quería
    entrar y pasa a medir cuántos asientos hay. Decidir una ampliación con esa
    media es decidir con un número que no puede decirte que te quedaste corto,
    así que la respuesta marca qué sectores están censurados y trata su
    ocupación como un suelo.
    """
    data = await ArenaQueryService(session).get(
        team_id, fill_rate=fill_rate, include_non_official=include_non_official
    )
    if data is None:
        raise HTTPException(404, f"no stadium history for team {team_id}")
    return cast(dict[str, Any], _camel(asdict(data)))


def _camel(d: Any) -> Any:
    if isinstance(d, dict):
        # Claves no-string (p.ej. posición -> probabilidad en la distribución
        # de la liga) no son identificadores: no tiene sentido camelCasearlas,
        # y k.split("_") sobre un int crashea.
        return {(_key(k) if isinstance(k, str) else k): _camel(v) for k, v in d.items()}
    if isinstance(d, list):
        return [_camel(v) for v in d]
    return d


def _key(k: str) -> str:
    head, *rest = k.split("_")
    return head + "".join(w.capitalize() for w in rest)
