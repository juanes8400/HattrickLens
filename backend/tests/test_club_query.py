"""La página Club debe mostrar sólo observaciones CHPP, incluso con una sola lectura."""
import asyncio
from datetime import timedelta

from sqlalchemy import select

from app.application.queries.club import ClubQueryService
from app.infrastructure.db import models as m
from tests.conftest import seeded_session


def test_club_query_reunites_mood_supporters_and_staff_without_fabricating_history() -> None:
    async def scenario():
        factory, team_id = await seeded_session()
        async with factory() as session:
            return await ClubQueryService(session).get(team_id)

    data = asyncio.run(scenario())

    assert data is not None
    assert data["teamName"] == "Pulgas Arrechas"
    assert data["current"]["spirit"] is not None
    assert data["current"]["confidence"] is not None
    assert data["current"]["supporters"]["fanClubSize"] > 0
    assert data["staff"] is not None
    assert data["staff"]["trainer"]["skillLevel"] > 0
    # Los seis puestos reales de Hattrick. "Portavoz" salió de aquí el
    # 2026-08-17: venía del club.xml viejo, no del juego.
    assert {role["key"] for role in data["staff"]["roles"]} == {
        "assistant_trainer_levels", "form_coach_levels", "medic_levels",
        "sport_psychologist_levels", "tactical_assistant_levels",
        "financial_director_levels",
    }
    assert all(role["effect"] is not None for role in data["staff"]["roles"])
    # Sólo hay una captura de cada fuente en el fixture: el servicio no crea
    # puntos intermedios para simular una evolución que no conoce.
    assert len(data["moodHistory"]) == 1
    assert len(data["supporterHistory"]) == 1
    assert len(data["staffHistory"]) == 1
    # "Patrocinadores" ya no existe como concepto en esta pantalla.
    assert "sponsors" not in data["current"]
    assert all("sponsorsPopularity" not in row for row in data["supporterHistory"])
    # El roster real (2 asistentes de nivel 5, no un agregado sin
    # procedencia) — bug real encontrado en vivo 2026-08-12.
    assistants = next(r for r in data["staff"]["roles"] if r["key"] == "assistant_trainer_levels")
    assert assistants["level"] == 10
    assert sorted(m["level"] for m in assistants["members"]) == [5, 5]

    # La pantalla reutiliza los 3,2 puntos por nivel de la fórmula HT-Tools:
    # 10 niveles combinados = +32 puntos de coeficiente.
    assert assistants["effect"]["trainingSpeedPct"] == 32.0
    medics = next(r for r in data["staff"]["roles"] if r["key"] == "medic_levels")
    assert medics["level"] == 2
    assert medics["effect"]["recoverySpeedPct"] == 40.0  # nivel 2
    # 2026-08-17: aquí se comprobaba que "Portavoz" no tuviera tabla de
    # efecto. Esa era la pista, no el comportamiento correcto: el puesto no
    # existe en Hattrick y ya no se enseña, así que la comprobación pasa a ser
    # que NO esté entre los roles.
    assert all(r["key"] != "spokesperson_levels" for r in data["staff"]["roles"])


def test_club_ignores_historical_minus_one_for_each_psychology_series() -> None:
    async def scenario():
        factory, team_id = await seeded_session()
        async with factory() as session:
            base = await session.scalar(
                select(m.TrainingSnapshot)
                .where(m.TrainingSnapshot.team_id == team_id)
                .order_by(m.TrainingSnapshot.captured_at.desc())
                .limit(1)
            )
            assert base is not None

            def copy_at(minutes: int, morale: int, confidence: int) -> m.TrainingSnapshot:
                return m.TrainingSnapshot(
                    sync_id=base.sync_id,
                    team_id=team_id,
                    captured_at=base.captured_at + timedelta(minutes=minutes),
                    training_type=base.training_type,
                    training_level=base.training_level,
                    new_training_level=base.new_training_level,
                    stamina_part=base.stamina_part,
                    last_training_type=base.last_training_type,
                    last_training_level=base.last_training_level,
                    last_stamina_part=base.last_stamina_part,
                    trainer_ht_id=base.trainer_ht_id,
                    trainer_name=base.trainer_name,
                    morale=morale,
                    self_confidence=confidence,
                    formation_xp_json=base.formation_xp_json,
                    content_hash=bytes([minutes]) * 32,
                )

            session.add_all(
                [
                    copy_at(1, -1, int(base.self_confidence) + 1),
                    copy_at(2, int(base.morale) + 1, -1),
                ]
            )
            await session.commit()
            return await ClubQueryService(session).get(team_id)

    data = asyncio.run(scenario())
    assert data is not None

    expected_spirit = data["moodHistory"][0]["spirit"] + 1
    expected_confidence = data["moodHistory"][0]["confidence"] + 1
    assert data["current"]["spirit"]["level"] == expected_spirit
    assert data["current"]["confidence"]["level"] == expected_confidence
    assert data["moodHistory"][-1]["spirit"] == expected_spirit
    assert data["moodHistory"][-1]["confidence"] == expected_confidence
    # El último placeholder no corta antes de tiempo la meseta del otro KPI.
    assert (
        data["psychology"]["confidence"]["readings"][-1]["at"]
        == data["moodHistory"][-1]["capturedAt"]
    )
    assert all(
        reading["level"] >= 0
        for series in (data["psychology"]["spirit"], data["psychology"]["confidence"])
        for reading in series["readings"]
    )
