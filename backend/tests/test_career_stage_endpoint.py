"""POST /teams/{id}/players/{ht_player_id}/career-stage — HL-15x #93: la app
sugiere, el usuario confirma. Mismo patrón de fixtures y sesión que
test_sync_endpoint_auth.py.
"""
import asyncio
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.infrastructure.security.jwt import create_session_token
from app.main import app

PLAYER_ID = 468921494


@pytest.fixture
def seeded() -> tuple[TestClient, int, int, async_sessionmaker]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def setup() -> tuple[int, int]:
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)
        async with factory() as s:
            user = m.User(ht_user_id=999, login_name="tester", created_at=datetime.now(UTC))
            s.add(user)
            await s.flush()
            team = m.Team(ht_team_id=537758, name="Pulgas Arrechas", owner_user_id=user.id)
            s.add(team)
            await s.flush()
            player = m.Player(
                ht_player_id=PLAYER_ID, team_id=team.id,
                first_name="Alberto", last_name="Gutiérrez Caviedes",
            )
            s.add(player)
            await s.commit()
            return user.id, team.id

    user_id, team_id = asyncio.run(setup())

    async def override_get_session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    yield client, user_id, team_id, factory
    app.dependency_overrides.clear()


def test_confirm_without_session_is_rejected(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    client, _user_id, team_id, _factory = seeded
    resp = client.post(
        f"/api/v1/teams/{team_id}/players/{PLAYER_ID}/career-stage", json={"stage": "pico"}
    )
    assert resp.status_code == 401


def test_confirm_for_a_team_you_do_not_own_is_forbidden(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    client, user_id, team_id, _factory = seeded
    client.cookies.set("htlens_session", create_session_token(user_id))
    other_team_id = team_id + 1
    resp = client.post(
        f"/api/v1/teams/{other_team_id}/players/{PLAYER_ID}/career-stage",
        json={"stage": "pico"},
    )
    assert resp.status_code == 404


def test_confirm_rejects_unknown_stage(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    client, user_id, team_id, _factory = seeded
    client.cookies.set("htlens_session", create_session_token(user_id))
    resp = client.post(
        f"/api/v1/teams/{team_id}/players/{PLAYER_ID}/career-stage",
        json={"stage": "leyenda_absoluta"},
    )
    assert resp.status_code == 400


def test_confirm_persists_and_can_be_cleared(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    client, user_id, team_id, _factory = seeded
    client.cookies.set("htlens_session", create_session_token(user_id))

    resp = client.post(
        f"/api/v1/teams/{team_id}/players/{PLAYER_ID}/career-stage",
        json={"stage": "veterano"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["confirmedStage"] == "veterano"
    assert body["confirmedAt"] is not None

    # borrar la confirmación: vuelve a sugerencia de la app
    resp2 = client.post(
        f"/api/v1/teams/{team_id}/players/{PLAYER_ID}/career-stage", json={"stage": None}
    )
    assert resp2.status_code == 200
    assert resp2.json()["confirmedStage"] is None
    assert resp2.json()["confirmedAt"] is None
