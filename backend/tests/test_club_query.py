"""La página Club debe mostrar sólo observaciones CHPP, incluso con una sola lectura."""
import asyncio

from app.application.queries.club import ClubQueryService
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
    assert {role["key"] for role in data["staff"]["roles"]} == {
        "assistant_trainer_levels", "form_coach_levels", "medic_levels",
        "sport_psychologist_levels", "tactical_assistant_levels",
        "financial_director_levels", "spokesperson_levels",
    }
    # Sólo hay una captura de cada fuente en el fixture: el servicio no crea
    # puntos intermedios para simular una evolución que no conoce.
    assert len(data["moodHistory"]) == 1
    assert len(data["supporterHistory"]) == 1
    assert len(data["staffHistory"]) == 1
