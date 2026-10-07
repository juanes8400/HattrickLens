"""Ficha de jugador.

Sale de partir `teams.py`, que tenia 1179 lineas y se abria
entera para tocar cualquiera de sus rutas. El `__init__.py` del paquete
monta `router` con todos estos, asi que las URL no cambian.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_squad_service,
    require_team_owner,
)
from app.application.dto.squad import PositionRatingDTO
from app.application.queries.squad import SquadQueryService
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session

router = APIRouter()


class SetManualPurchasePriceBody(BaseModel):
    price: int
    purchased_at: str | None = None


@router.put(
    "/{team_id}/players/{ht_player_id}/purchase-price",
    status_code=200,
    dependencies=[Depends(require_team_owner)],
)
async def set_manual_purchase_price(
    team_id: int,
    ht_player_id: int,
    body: SetManualPurchasePriceBody,
    session: AsyncSession = Depends(get_session),
    user: m.User = Depends(get_current_user),
) -> dict[str, Any]:
    """HL-161: precio de compra escrito a mano, solo para cuando ni
    `transfersteam.xml` ni `transfersplayer.xml` traen una compra real
    (jugador anterior a cualquier historial que CHPP guarde). Nunca
    sobrescribe un precio real ya conocido, bórralo primero si de verdad
    quieres reemplazarlo."""
    team = await session.get(m.Team, team_id)
    if team is None:
        raise HTTPException(404, f"team {team_id} not found")
    if team.owner_user_id != user.id:
        raise HTTPException(403, "este equipo no está conectado a tu sesión")

    player = await session.scalar(
        select(m.Player).where(m.Player.ht_player_id == ht_player_id, m.Player.team_id == team_id)
    )
    if player is None:
        raise HTTPException(404, f"player {ht_player_id} not found on team {team_id}")
    if player.purchase_price is not None:
        raise HTTPException(
            409,
            "ya hay un precio de compra real (transfersteam/transfersplayer), "
            "no se puede sobrescribir con uno manual",
        )

    player.purchase_price_manual = body.price
    if body.purchased_at:
        player.purchased_at_manual = datetime.fromisoformat(body.purchased_at).replace(tzinfo=UTC)
    await session.commit()
    return {"htPlayerId": ht_player_id, "purchasePriceManual": body.price}


CONFIRMABLE_CAREER_STAGES = {"promesa", "pico", "veterano", "rotacion", "declive"}


class ConfirmCareerStageBody(BaseModel):
    # None = borrar la confirmación y volver a mostrar la sugerencia de la app.
    stage: str | None = None


@router.post(
    "/{team_id}/players/{ht_player_id}/career-stage",
    summary="Confirmar (o borrar, el momento de carrera sugerido por la app, HL-15x #93",
    dependencies=[Depends(require_team_owner)],
)
async def confirm_career_stage(
    team_id: int,
    ht_player_id: int,
    body: ConfirmCareerStageBody,
    session: AsyncSession = Depends(get_session),
    user: m.User = Depends(get_current_user),
) -> dict[str, Any]:
    """La app SUGIERE el momento de carrera (career_stage_engine, con sus
    señales reales); el usuario CONFIRMA aquí, nunca se sobreescribe solo
    en un sync posterior."""
    team = await session.get(m.Team, team_id)
    if team is None:
        raise HTTPException(404, f"team {team_id} not found")
    if team.owner_user_id != user.id:
        raise HTTPException(403, "este equipo no está conectado a tu sesión")
    if body.stage is not None and body.stage not in CONFIRMABLE_CAREER_STAGES:
        raise HTTPException(
            400, f"etapa desconocida: {body.stage}, válidas: {sorted(CONFIRMABLE_CAREER_STAGES)}"
        )

    player = await session.scalar(
        select(m.Player).where(m.Player.ht_player_id == ht_player_id, m.Player.team_id == team_id)
    )
    if player is None:
        raise HTTPException(404, f"player {ht_player_id} not found in team {team_id}")

    player.confirmed_career_stage = body.stage
    player.confirmed_career_stage_at = datetime.now(UTC) if body.stage is not None else None
    await session.commit()

    return {
        "htPlayerId": ht_player_id,
        "confirmedStage": player.confirmed_career_stage,
        "confirmedAt": (
            player.confirmed_career_stage_at.isoformat()
            if player.confirmed_career_stage_at is not None
            else None
        ),
    }


@router.get(
    "/players/{ht_player_id}/positions",
    response_model=list[PositionRatingDTO],
    response_model_by_alias=True,
    summary="Las 19 variantes de posición de un jugador (HL-020)",
)
async def player_positions(
    ht_player_id: int,
    svc: SquadQueryService = Depends(get_squad_service),
) -> list[PositionRatingDTO]:
    data = await svc.player_positions(ht_player_id)
    if data is None:
        raise HTTPException(404, f"player {ht_player_id} not found")
    return data
