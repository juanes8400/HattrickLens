"""Saldo neto por jugador. HL-161."""
from dataclasses import asdict
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.arena import _camel
from app.application.queries.player_balance import PlayerBalanceQueryService
from app.api.deps import require_team_owner
from app.infrastructure.db.session import get_session

router = APIRouter()


@router.get(
    "/teams/{team_id}/player-balance",
    summary="Saldo neto por jugador (compra, salario, venta)",
    dependencies=[Depends(require_team_owner)],
)
async def player_balance(
    team_id: int,
    session: AsyncSession = Depends(get_session),
    season: str | None = Query(
        default=None,
        description=(
            'Filtro general de temporadas (p. ej. "Temporada 83"), omitido o '
            '"all" trae toda la historia, como antes.'
        ),
    ),
) -> dict[str, Any]:
    """Precio de compra + salario acumulado + coste de cada intento de
    venta, contra el precio real de venta menos la comisión del agente —
    más la comisión EXACTA de club anterior (HL-161, 2026-08-14) de
    cualquier reventa detectada de un ex-jugador nuestro. Nunca usa una
    valoración de mercado hipotética para un jugador que sigue sin
    venderse: esa cifra es 0 hasta que la venta sea real."""
    data = await PlayerBalanceQueryService(session).get(team_id, season=season)
    if data is None:
        raise HTTPException(404, f"team {team_id} not found")
    return cast(dict[str, Any], _camel(asdict(data)))
