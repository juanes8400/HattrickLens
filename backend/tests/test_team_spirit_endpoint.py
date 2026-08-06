"""GET /teams/{id}/lineup/team-spirit — HL-142.

Tabla estática de referencia (Manual no Escrito), no ligada al Espíritu real
de este equipo — solo un test end-to-end de que el endpoint la sirve bien.
"""
import asyncio

from fastapi.testclient import TestClient

from app.infrastructure.db.session import get_session
from app.main import app
from tests.conftest import seeded_session


def test_team_spirit_endpoint_returns_the_ten_rows() -> None:
    factory, team_id = asyncio.run(seeded_session())

    async def override_get_session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    try:
        client = TestClient(app)
        resp = client.get(f"/api/v1/teams/{team_id}/lineup/team-spirit")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["rows"]) == 10
        assert body["rows"][0]["spirit"] == "Muy agresivos"
        assert body["rows"][0]["pic"] < body["rows"][0]["normal"] < body["rows"][0]["mots"]
        assert "no coinciden" in body["note"]
    finally:
        app.dependency_overrides.clear()
