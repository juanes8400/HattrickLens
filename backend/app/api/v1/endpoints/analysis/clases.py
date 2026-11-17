"""Clases de Jugador: la plantilla partida de cuatro formas, y los grupos
propios del usuario (crear, renombrar, borrar y poner a cada jugador en uno).

Las reglas viven en `domain/engines/clases_de_jugador.py`.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_team_owner
from app.application.queries.clases_de_jugador import (
    ClasesDeJugadorQueryService,
    grupos_del_equipo,
)
from app.domain.engines.career_stage_engine import (
    PEAK_MAX_AGE,
    ROTATION_BELOW_PERCENTILE,
    YOUNG_MAX_AGE,
)
from app.domain.engines.clases_de_jugador import TOPE_DE_UNA_ETAPA, Once
from app.domain.engines.lineup_optimizer import _positions
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session

router = APIRouter()

#: Los colores que se pueden elegir para un grupo propio. La pantalla tiene
#: la misma lista; cualquier otro valor se rechaza.
COLORES = ("blue", "red", "green", "orange", "purple", "teal", "gray")
#: Más grupos que esto no caben en la pantalla de un vistazo.
MAX_GRUPOS = 12


def _once(o: Once) -> dict[str, Any]:
    etiquetas = _positions()
    return {
        "formation": o.formation,
        "slots": [
            {
                "slot": c.slot,
                "base": c.base,
                "position": c.position,
                "label": etiquetas.get(c.position, "") if c.position else None,
                "htPlayerId": c.ht_player_id,
                "rating": c.rating,
            }
            for c in o.casillas
        ],
    }


@router.get(
    "/teams/{team_id}/player-classes",
    summary="Clases de Jugador: titularidad, rentabilidad deportiva, etapa y grupos propios",
    dependencies=[Depends(require_team_owner)],
)
async def player_classes(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if await session.get(m.Team, team_id) is None:
        raise HTTPException(404, f"team {team_id} not found")
    c = await ClasesDeJugadorQueryService(session).get(team_id)
    return {
        "formations": list(c.formations),
        "experience": c.experience,
        "starters": [_once(o) for o in c.onces_titular],
        "substitutes": [_once(o) for o in c.onces_suplencia],
        "medians": (
            {"htms28": c.corte.mediana_htms28, "salary": c.corte.mediana_sueldo}
            if c.corte
            else None
        ),
        "currency": c.currency,
        "groups": [{"id": g.id, "groupName": g.name, "color": g.color} for g in c.groups],
        # Los cortes de la Etapa de carrera, para que la pantalla los explique
        # con los números del motor y no con una copia que se quede vieja.
        "stageRules": {
            "youngMaxAge": YOUNG_MAX_AGE,
            "peakMaxAge": PEAK_MAX_AGE,
            "rotationBelowPercentile": ROTATION_BELOW_PERCENTILE,
            "splitAbove": TOPE_DE_UNA_ETAPA,
        },
        "players": [
            {
                "htPlayerId": j.ht_player_id,
                "name": j.name,
                "shortName": j.short_name,
                "ageYears": j.age_years,
                "ageDays": j.age_days,
                "htms": j.htms,
                "htms28": j.htms28,
                "salary": j.salary,
                "titularidad": j.titularidad,
                "rentabilidad": j.rentabilidad,
                "etapa": {
                    "stage": j.etapa.stage,
                    "confirmed": j.etapa.confirmed,
                    "percentile": j.etapa.percentile,
                    "rising": j.etapa.rising,
                    "falling": j.etapa.falling,
                    "hasSufficientHistory": j.etapa.has_sufficient_history,
                    "side": j.etapa.lado,
                },
                "groupId": j.group_id,
            }
            for j in c.players
        ],
    }


class GrupoBody(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    color: str


class GrupoCambio(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    color: str | None = None


class MiembroBody(BaseModel):
    #: None devuelve al jugador a «Sin grupo». En la petición se llama
    #: `groupId`, como el resto de campos que lee la pantalla.
    group_id: int | None = Field(alias="groupId")


def _color_valido(color: str) -> None:
    if color not in COLORES:
        raise HTTPException(400, f"color desconocido: {color}, válidos: {', '.join(COLORES)}")


async def _grupo(session: AsyncSession, team_id: int, group_id: int) -> m.PlayerGroup:
    grupo = await session.get(m.PlayerGroup, group_id)
    if grupo is None or grupo.team_id != team_id:
        raise HTTPException(404, f"grupo {group_id} no existe en este equipo")
    return grupo


@router.post(
    "/teams/{team_id}/player-groups",
    summary="Crear un grupo propio",
    dependencies=[Depends(require_team_owner)],
)
async def crear_grupo(
    team_id: int, body: GrupoBody, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    _color_valido(body.color)
    if len(await grupos_del_equipo(session, team_id)) >= MAX_GRUPOS:
        raise HTTPException(400, f"como mucho {MAX_GRUPOS} grupos")
    grupo = m.PlayerGroup(
        team_id=team_id, name=body.name.strip(), color=body.color, created_at=datetime.now(UTC)
    )
    session.add(grupo)
    await session.commit()
    return {"id": grupo.id, "groupName": grupo.name, "color": grupo.color}


@router.patch(
    "/teams/{team_id}/player-groups/{group_id}",
    summary="Renombrar o cambiar el color de un grupo propio",
    dependencies=[Depends(require_team_owner)],
)
async def cambiar_grupo(
    team_id: int, group_id: int, body: GrupoCambio, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    grupo = await _grupo(session, team_id, group_id)
    if body.name is not None:
        grupo.name = body.name.strip()
    if body.color is not None:
        _color_valido(body.color)
        grupo.color = body.color
    await session.commit()
    return {"id": grupo.id, "groupName": grupo.name, "color": grupo.color}


@router.delete(
    "/teams/{team_id}/player-groups/{group_id}",
    summary="Borrar un grupo propio; sus jugadores vuelven a «Sin grupo»",
    dependencies=[Depends(require_team_owner)],
)
async def borrar_grupo(
    team_id: int, group_id: int, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    grupo = await _grupo(session, team_id, group_id)
    await session.execute(
        update(m.Player)
        .where(m.Player.team_id == team_id, m.Player.player_group_id == group_id)
        .values(player_group_id=None)
    )
    await session.delete(grupo)
    await session.commit()
    return {"deleted": group_id}


@router.put(
    "/teams/{team_id}/player-groups/members/{ht_player_id}",
    summary="Poner a un jugador en un grupo propio, o sacarlo",
    dependencies=[Depends(require_team_owner)],
)
async def poner_en_grupo(
    team_id: int,
    ht_player_id: int,
    body: MiembroBody,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if body.group_id is not None:
        await _grupo(session, team_id, body.group_id)
    jugador = await session.scalar(
        select(m.Player).where(m.Player.ht_player_id == ht_player_id, m.Player.team_id == team_id)
    )
    if jugador is None:
        raise HTTPException(404, f"player {ht_player_id} not found in team {team_id}")
    jugador.player_group_id = body.group_id
    await session.commit()
    return {"htPlayerId": ht_player_id, "groupId": body.group_id}
