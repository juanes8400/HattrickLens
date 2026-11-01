"""Lo que ha costado la gente parecida a un jugador tuyo.

No gasta cuota de Hattrick: sirve lo que dejó el paso del mercado, así
que se puede abrir y recalcular tantas veces como haga falta.
"""

from dataclasses import asdict
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_team_owner
from app.api.v1.endpoints.arena import _camel
from app.application.queries.precio_comparable import precio_de, precios_de_la_plantilla
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
    entre qué precios se pagó, y con qué filtros los buscó el propio Hattrick.

    Es una descripción del mercado, no una predicción sobre tu jugador: no se
    corrige por forma, experiencia, especialidad ni bonos de club. Una subasta
    abierta se enseña y se vigila, pero no promedia: una puja no es un precio,
    y por eso viaja `provisionales`.
    """
    datos = await precio_de(session, team_id, ht_player_id)
    if datos is None:
        raise HTTPException(404, f"el jugador {ht_player_id} no es del equipo {team_id}")
    return cast(dict[str, Any], _camel(asdict(datos)))


@router.get(
    "/teams/{team_id}/precios-comparables",
    summary="Lo que ha costado gente parecida a cada uno de tus jugadores",
    dependencies=[Depends(require_team_owner)],
)
async def precios_comparables(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Una fila por jugador de la plantilla, con su precio comparable.

    EN PLURAL A PROPÓSITO: el fondo del mercado es del equipo, así que se lee
    una vez y se mide contra todos. Pedirlo jugador a jugador leería las mismas
    ventas veinticinco veces y abriría la puerta a que la tabla y la ficha
    dieran dos números distintos del mismo jugador.

    Sin ventas cerradas parecidas la media llega `null`, nunca cero: cero diría
    que no vale nada y lo que pasa es que todavía no se sabe.
    """
    return cast(dict[str, Any], _camel(asdict(await precios_de_la_plantilla(session, team_id))))
