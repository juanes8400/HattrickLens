"""Estado e historial del club y cuerpo técnico.

Hattrick Control separaba esta información en Club, Gráfico y Empleados.  En
Lens sale de los snapshots CHPP que ya se guardan en cada sincronización: no
requiere una llamada adicional ni infiere estados que Hattrick no entregue.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.weekly import latest_per_iso_week
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

TRAINER_TYPES = {0: "Defensivo", 1: "Ofensivo", 2: "Equilibrado"}
POPULARITY = {
    0: "muy baja", 1: "furiosos", 2: "irritados", 3: "calmados",
    4: "contentos", 5: "satisfechos", 6: "eufóricos", 7: "muy alta",
    8: "bailando en las calles", 9: "enviando poemas de amor",
}


def _date(value: Any) -> str:
    return value.isoformat() if value is not None else ""


def _staff_levels(row: m.StaffSnapshot) -> list[dict[str, Any]]:
    return [
        {"key": key, "label": label, "level": int(getattr(row, key) or 0)}
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
                "sponsors": (
                    {
                        "popularity": latest_economy.sponsors_popularity,
                        "popularityLabel": POPULARITY.get(latest_economy.sponsors_popularity, "Sin dato"),
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
                for row in latest_per_iso_week(training, lambda item: item.captured_at)
            ],
            "supporterHistory": [
                {
                    "capturedAt": _date(row.captured_at),
                    "fanClubSize": row.fan_club_size,
                    "supportersPopularity": row.supporters_popularity,
                    "sponsorsPopularity": row.sponsors_popularity,
                }
                for row in latest_per_iso_week(economy, lambda item: item.captured_at)
            ],
            "staffHistory": [
                {
                    "capturedAt": _date(row.captured_at),
                    "roles": _staff_levels(row),
                    "trainerSkillLevel": row.trainer_skill_level,
                }
                for row in latest_per_iso_week(staff, lambda item: item.captured_at)
            ],
            "notes": [
                "Los valores actuales vienen de club, training, stafflist y economy del CHPP.",
                "El histórico empieza con la primera sincronización de Hattrick Lens; no se inventan semanas anteriores.",
            ],
        }
