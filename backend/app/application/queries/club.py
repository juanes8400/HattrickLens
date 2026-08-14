"""Estado e historial del club y cuerpo técnico.

Hattrick Control separaba esta información en Club, Gráfico y Empleados.  En
Lens sale de los snapshots CHPP que ya se guardan en cada sincronización: no
requiere una llamada adicional ni infiere estados que Hattrick no entregue.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.weekly import (
    changes_only,
    season_week_label,
    season_week_offset_for,
)
from app.domain.engines.staff_effects import STAFF_FIELD_TO_EFFECT_FN
from app.domain.value_objects.ht_constants import CONFIDENCE, TEAM_SPIRIT
from app.infrastructure.db import models as m


STAFF_FIELDS: tuple[tuple[str, str], ...] = (
    ("assistant_trainer_levels", "Asistentes de entrenador"),
    ("form_coach_levels", "Entrenadores de forma"),
    ("medic_levels", "Médicos"),
    ("sport_psychologist_levels", "Psicólogos deportivos"),
    ("tactical_assistant_levels", "Asistentes tácticos"),
    ("financial_director_levels", "Directores financieros"),
    ("spokesperson_levels", "Portavoces"),
)
# HL-2xx, 2026-08-12: el mismo código StaffType de stafflist.xml usado para
# sumar las columnas de arriba (ver STAFF_TYPE_TO_FIELD en sync_team.py),
# aquí para agrupar el roster real (nombres) bajo cada rol.
STAFF_FIELD_TO_TYPE: dict[str, int] = {
    "assistant_trainer_levels": 1, "medic_levels": 2, "spokesperson_levels": 3,
    "sport_psychologist_levels": 4, "form_coach_levels": 5,
    "financial_director_levels": 6, "tactical_assistant_levels": 7,
}

TRAINER_TYPES = {0: "Defensivo", 1: "Ofensivo", 2: "Equilibrado"}
POPULARITY = {
    0: "muy baja", 1: "furiosos", 2: "irritados", 3: "calmados",
    4: "contentos", 5: "satisfechos", 6: "eufóricos", 7: "muy alta",
    8: "bailando en las calles", 9: "enviando poemas de amor",
}


def _date(value: Any) -> str:
    return value.isoformat() if value is not None else ""


def _staff_members(row: m.StaffSnapshot) -> list[dict[str, Any]]:
    if not row.staff_members_json:
        return []
    try:
        return list(json.loads(row.staff_members_json))
    except (ValueError, TypeError):
        return []


def _staff_levels(row: m.StaffSnapshot) -> list[dict[str, Any]]:
    members = _staff_members(row)
    return [
        {
            "key": key,
            "label": label,
            "level": int(getattr(row, key) or 0),
            "members": [
                {"name": mem.get("name", ""), "level": mem.get("level", 0)}
                for mem in members
                if mem.get("staff_type") == STAFF_FIELD_TO_TYPE[key]
            ],
            # HL-2xx, 2026-08-12, pedido explícito: el aporte real de este
            # puesto según las tablas oficiales de Hattrick — `None` para
            # Portavoz, que ya no está entre las categorías vigentes que
            # documentó el usuario, así que no hay tabla real que aplicar.
            "effect": (
                STAFF_FIELD_TO_EFFECT_FN[key](int(getattr(row, key) or 0))
                if key in STAFF_FIELD_TO_EFFECT_FN else None
            ),
        }
        for key, label in STAFF_FIELDS
    ]


class ClubQueryService:
    """Read-only club view composed from append-only CHPP snapshots."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, team_id: int) -> dict[str, Any] | None:
        team = await self._s.get(m.Team, team_id)
        if team is None:
            return None

        training = list((await self._s.execute(
            select(m.TrainingSnapshot)
            .where(m.TrainingSnapshot.team_id == team_id)
            .order_by(m.TrainingSnapshot.captured_at)
        )).scalars())
        economy = list((await self._s.execute(
            select(m.EconomySnapshot)
            .where(m.EconomySnapshot.team_id == team_id)
            .order_by(m.EconomySnapshot.captured_at)
        )).scalars())
        staff = list((await self._s.execute(
            select(m.StaffSnapshot)
            .where(m.StaffSnapshot.team_id == team_id)
            .order_by(m.StaffSnapshot.captured_at)
        )).scalars())

        # "TT-ss" para "Evolución del staff" — mismo patrón que economy.py:
        # ancla al WorldContext del país del equipo (por ht_league_id), no
        # inventa temporada/semana si worlddetails no se ha sincronizado.
        world = (
            await self._s.scalar(
                select(m.WorldContext).where(m.WorldContext.ht_league_id == team.ht_league_id)
            )
            if team.ht_league_id is not None else None
        )

        latest_training = training[-1] if training else None
        latest_economy = economy[-1] if economy else None
        latest_staff = staff[-1] if staff else None

        current_staff = (
            {
                "capturedAt": _date(latest_staff.captured_at),
                "trainer": {
                    "skillLevel": latest_staff.trainer_skill_level,
                    "type": latest_staff.trainer_type,
                    "typeLabel": TRAINER_TYPES.get(latest_staff.trainer_type, "—"),
                    "leadership": latest_staff.trainer_leadership,
                },
                "roles": _staff_levels(latest_staff),
                "totalLevels": sum(item["level"] for item in _staff_levels(latest_staff)),
                "youthInvestment": latest_staff.youth_investment,
                "youthLevel": latest_staff.youth_level,
            }
            if latest_staff is not None
            else None
        )

        return {
            "teamName": team.name,
            "current": {
                "spirit": (
                    {
                        "level": latest_training.morale,
                        "label": TEAM_SPIRIT.get(latest_training.morale, "Sin dato"),
                    }
                    if latest_training is not None else None
                ),
                "confidence": (
                    {
                        "level": latest_training.self_confidence,
                        "label": CONFIDENCE.get(latest_training.self_confidence, "Sin dato"),
                    }
                    if latest_training is not None else None
                ),
                "supporters": (
                    {
                        "fanClubSize": latest_economy.fan_club_size,
                        "popularity": latest_economy.supporters_popularity,
                        "popularityLabel": POPULARITY.get(latest_economy.supporters_popularity, "Sin dato"),
                    }
                    if latest_economy is not None else None
                ),
            },
            "staff": current_staff,
            "moodHistory": [
                {
                    "capturedAt": _date(row.captured_at),
                    "spirit": row.morale,
                    "confidence": row.self_confidence,
                }
                # HL-2xx, 2026-08-12: un punto por CAMBIO real de espíritu o
                # confianza, no uno por semana ISO — si dos syncs seguidos
                # leen el mismo valor, no es un dato nuevo.
                for row in changes_only(
                    training, lambda item: item.captured_at,
                    lambda item: (item.morale, item.self_confidence),
                )
            ],
            "supporterHistory": [
                {
                    "capturedAt": _date(row.captured_at),
                    "fanClubSize": row.fan_club_size,
                    "supportersPopularity": row.supporters_popularity,
                }
                for row in changes_only(
                    economy, lambda item: item.captured_at,
                    lambda item: (item.fan_club_size, item.supporters_popularity),
                )
            ],
            "staffHistory": [
                {
                    "capturedAt": _date(row.captured_at),
                    "seasonWeek": season_week_label(
                        world, weeks_offset=season_week_offset_for(world, row.captured_at)
                    ),
                    "roles": _staff_levels(row),
                    "trainerSkillLevel": row.trainer_skill_level,
                }
                for row in changes_only(
                    staff, lambda item: item.captured_at,
                    lambda item: tuple(getattr(item, key) for key, _ in STAFF_FIELDS),
                )
            ],
            "notes": [
                "Los valores actuales vienen de club, training, stafflist y economy del CHPP.",
                "El histórico empieza con la primera sincronización de Hattrick Lens; no se inventan semanas anteriores.",
            ],
        }
