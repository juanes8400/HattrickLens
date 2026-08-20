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
