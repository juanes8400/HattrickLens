"""Saldo neto por jugador. HL-161."""
from dataclasses import asdict
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.arena import _camel
from app.application.queries.player_balance import PlayerBalanceQueryService
from app.application.queries.transfer_attempts import TransferAttemptsQueryService
from app.api.deps import require_team_owner
from app.domain.value_objects.ht_constants import SKILL_LABELS
from app.infrastructure.db import models as m
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


class EdicionDeEtapa(BaseModel):
    """Lo que el usuario puede atribuir de una etapa ya cerrada.

    Solo huecos: si Hattrick da el dato de verdad, gana el de verdad. Y solo de
    ex-jugadores — la plantilla de hoy se sincroniza sola, no se teclea.
    """

    training_type: int | None = Field(
        None, ge=0, le=12, description="Qué se entrenaba cuando se fue"
    )
    top_skill: str | None = Field(
        None, description="Su habilidad más alta en ese momento"
    )
    age_years: int | None = Field(None, ge=15, le=50)
    age_days: int | None = Field(None, ge=0, le=111)
    excluded: bool | None = Field(
        None, description="Sacar esta etapa de todos los cálculos de Transferencias"
    )


@router.patch(
    "/teams/{team_id}/stints/{stint_id}",
    summary="Atribuir a mano lo que falta de una etapa, o excluirla",
    dependencies=[Depends(require_team_owner)],
)
async def edit_stint(
    team_id: int,
    stint_id: int,
    edicion: EdicionDeEtapa,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    etapa = await session.get(m.PlayerStint, stint_id)
    if etapa is None or etapa.team_id != team_id:
        raise HTTPException(404, "esa etapa no es de este equipo")
    if etapa.left_at is None:
        raise HTTPException(
            409,
            "esta etapa sigue abierta: mientras el jugador esté en la plantilla "
            "sus datos vienen de Hattrick y no se escriben a mano.",
        )

    if edicion.top_skill is not None and edicion.top_skill not in SKILL_LABELS:
        raise HTTPException(400, f"«{edicion.top_skill}» no es una habilidad")

    campos = edicion.model_dump(exclude_unset=True)
    if "training_type" in campos:
        etapa.training_type_manual = campos["training_type"]
    if "top_skill" in campos:
        etapa.top_skill_manual = campos["top_skill"]
    if "age_years" in campos:
        etapa.age_years_manual = campos["age_years"]
    if "age_days" in campos:
        etapa.age_days_manual = campos["age_days"]
    if "excluded" in campos and campos["excluded"] is not None:
        etapa.excluded = campos["excluded"]
    await session.commit()

    return {
        "stintId": etapa.id,
        "trainingType": etapa.training_type_manual,
        "topSkill": etapa.top_skill_manual,
        "ageYears": etapa.age_years_manual,
        "ageDays": etapa.age_days_manual,
        "excluded": etapa.excluded,
    }


@router.get(
    "/teams/{team_id}/transfer-attempts",
    summary="Cada intento de venta, con su final",
    dependencies=[Depends(require_team_owner)],
)
async def transfer_attempts(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Una fila por intento: cuándo salió al mercado, cuándo cerró la puja, si
    terminó en venta y cuántas veces lo miraron.

    Lo de las visitas no lo da CHPP por ningún lado — Hattrick solo lo cuenta
    en el texto de la noticia al cerrarse la puja —, así que lo teclea el
    usuario y aquí se sirve tal cual."""
    data = await TransferAttemptsQueryService(session).get(team_id)
    if data is None:
        raise HTTPException(404, f"team {team_id} not found")
    return cast(dict[str, Any], _camel(asdict(data)))


class VisitasDelIntento(BaseModel):
    times_seen: int | None = Field(
        None, ge=0, description="Cuántas veces lo miraron mientras estaba listado"
    )
    dismissed: bool = Field(
        False, description="Ignorar la pregunta: no volver a preguntar por este intento"
    )


@router.patch(
    "/teams/{team_id}/transfer-attempts/{attempt_id}",
    summary="Anotar cuántas veces vieron al jugador, o ignorar la pregunta",
    dependencies=[Depends(require_team_owner)],
)
async def set_times_seen(
    team_id: int,
    attempt_id: int,
    visitas: VisitasDelIntento,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    intento = await session.get(m.PlayerListingAttempt, attempt_id)
    if intento is None:
        raise HTTPException(404, "ese intento no existe")
    jugador = await session.get(m.Player, intento.player_id)
    if jugador is None or jugador.team_id != team_id:
        raise HTTPException(404, "ese intento no es de este equipo")

    if visitas.times_seen is not None:
        intento.times_seen = visitas.times_seen
    # Preguntado queda preguntado, se responda o se ignore: si no, el aviso
    # volveria a salir en cada visita a Cambios.
    intento.times_seen_asked = True
    await session.commit()
    return {
        "id": intento.id,
        "timesSeen": intento.times_seen,
        "asked": intento.times_seen_asked,
    }
