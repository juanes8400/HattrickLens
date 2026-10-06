"""Lo que ha costado la gente parecida a un jugador tuyo.

No gasta cuota de Hattrick: sirve lo que dejó el paso semanal del mercado, así
que se puede abrir y recalcular tantas veces como haga falta.
"""

from dataclasses import asdict
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_team_owner
from app.api.v1.endpoints.arena import _camel
from app.application.queries.precio_comparable import precio_de
from app.infrastructure.db.session import get_session

router = APIRouter()


@router.get(
    "/teams/{team_id}/players/{ht_player_id}/precio-comparable",
    summary="Lo que ha costado la gente parecida a este jugador",
    dependencies=[Depends(require_team_owner)],
)
async def precio_comparable(
    team_id: int,
    ht_player_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Media y mediana ponderadas de ventas CERRADAS de jugadores parecidos,
    con la horquilla de lo que de verdad se pagó.

    Es una descripción del mercado, no una predicción sobre tu jugador: no se
    corrige por forma, experiencia, especialidad ni bonos de club. Mientras una
    subasta no haya cerrado su precio es la puja, que se queda corta, y por eso
    viaja `provisionales`.
    """
    datos = await precio_de(session, team_id, ht_player_id)
    if datos is None:
        raise HTTPException(404, f"el jugador {ht_player_id} no es del equipo {team_id}")
    return cast(dict[str, Any], _camel(asdict(datos)))
