"""Sesión de acceso + refresco (HL-2xx).

Antes solo existía el token de acceso, corto a propósito
(`jwt_access_ttl_minutes`) — `jwt_refresh_ttl_days` estaba declarado en
`settings` pero ningún código lo usaba, así que la sesión moría de verdad
cada pocos minutos sin renovado silencioso. Estos tests cubren el par
acceso/refresco: la claim `type` que evita que uno sirva donde va el otro,
y el endpoint `/auth/chpp/refresh` que el frontend llama solo ante un 401.
"""
from datetime import UTC, datetime

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.infrastructure.security.jwt import (
    COOKIE_NAME,
    REFRESH_COOKIE_NAME,
    SessionTokenError,
    create_refresh_token,
    create_session_token,
    read_user_id,
)
from app.main import app


def test_access_and_refresh_tokens_carry_distinct_type_claims() -> None:
    access = create_session_token(42)
    refresh = create_refresh_token(42)

    assert read_user_id(access, expected_type="access") == 42
    assert read_user_id(refresh, expected_type="refresh") == 42


def test_a_refresh_token_does_not_authenticate_as_access() -> None:
    refresh = create_refresh_token(42)
    with pytest.raises(SessionTokenError):
        read_user_id(refresh, expected_type="access")


def test_an_access_token_does_not_work_at_the_refresh_endpoint() -> None:
    access = create_session_token(42)
    with pytest.raises(SessionTokenError):
        read_user_id(access, expected_type="refresh")


def test_a_token_without_a_type_claim_is_treated_as_legacy_access() -> None:
    """Tokens emitidos antes de esta claim (si alguno sigue vivo) no deben
    quedar huérfanos — sin `type`, se asume "access", el único tipo que
    existía entonces."""
    now = datetime.now(UTC)
    legacy = pyjwt.encode(
        {"sub": "7", "iat": now}, settings.secret_key, algorithm="HS256"
    )
    assert read_user_id(legacy, expected_type="access") == 7


@pytest.fixture
def seeded_user() -> tuple[TestClient, int]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def setup() -> int:
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)
        async with factory() as s:
            user = m.User(ht_user_id=555, login_name="tester", created_at=datetime.now(UTC))
            s.add(user)
            await s.flush()
            team = m.Team(
                ht_team_id=537758,
                owner_user_id=user.id,
                name="Pulgas Arrechas",
                league_name="Colombia",
                series_name="V.92",
            )
            s.add(team)
            other = m.User(ht_user_id=777, login_name="other", created_at=datetime.now(UTC))
            s.add(other)
            await s.flush()
            s.add(m.Team(
                ht_team_id=999999,
                owner_user_id=other.id,
                name="Otro club",
                league_name="España",
                series_name="VI.1",
            ))
            s.add(m.CHPPToken(
                user_id=user.id,
                oauth_token_enc=b"test-token",
                oauth_secret_enc=b"test-secret",
                status="active",
                ht_user_id=555,
            ))
            await s.flush()
            now = datetime.now(UTC)
            s.add(m.Sync(
                user_id=user.id,
                team_id=team.id,
                kind="initial",
                status="completed",
                started_at=now,
                finished_at=now,
            ))
            await s.commit()
            return user.id

    import asyncio
    user_id = asyncio.run(setup())

    async def override_get_session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    yield client, user_id
    app.dependency_overrides.clear()


def test_refresh_endpoint_rotates_both_cookies(
    seeded_user: tuple[TestClient, int],
) -> None:
    client, user_id = seeded_user
    client.cookies.set(REFRESH_COOKIE_NAME, create_refresh_token(user_id))

    resp = client.post("/api/v1/auth/chpp/refresh")

    assert resp.status_code == 204
    new_access = resp.cookies.get(COOKIE_NAME)
    new_refresh = resp.cookies.get(REFRESH_COOKIE_NAME)
    assert new_access is not None
    assert new_refresh is not None
    assert read_user_id(new_access, expected_type="access") == user_id
    assert read_user_id(new_refresh, expected_type="refresh") == user_id


def test_refresh_endpoint_without_a_cookie_is_401(
    seeded_user: tuple[TestClient, int],
) -> None:
    client, _user_id = seeded_user
    resp = client.post("/api/v1/auth/chpp/refresh")
    assert resp.status_code == 401


def test_refresh_endpoint_rejects_an_access_token_in_the_refresh_slot(
    seeded_user: tuple[TestClient, int],
) -> None:
    client, user_id = seeded_user
    client.cookies.set(REFRESH_COOKIE_NAME, create_session_token(user_id))
    resp = client.post("/api/v1/auth/chpp/refresh")
    assert resp.status_code == 401


def test_refresh_endpoint_rejects_an_unknown_user(
    seeded_user: tuple[TestClient, int],
) -> None:
    client, _user_id = seeded_user
    client.cookies.set(REFRESH_COOKIE_NAME, create_refresh_token(999_999))
    resp = client.post("/api/v1/auth/chpp/refresh")
    assert resp.status_code == 401


def test_session_profile_lists_owned_clubs_and_import_state(
    seeded_user: tuple[TestClient, int],
) -> None:
    client, user_id = seeded_user
    client.cookies.set(COOKIE_NAME, create_session_token(user_id))

    resp = client.get("/api/v1/auth/chpp/session")

    assert resp.status_code == 200
    body = resp.json()
    # `isAdmin` se anadio el 2026-08-26 para la pantalla de uso. Aqui es False
    # porque este usuario (555) no es el de `ADMIN_HT_USER_ID`; que el candado
    # de verdad funciona se comprueba en `test_uso_endpoint.py`.
    assert body["user"] == {
        "id": user_id, "htUserId": 555, "loginName": "tester", "isAdmin": False,
    }
    assert body["connectionStatus"] == "active"
    assert len(body["teams"]) == 1
    assert body["teams"][0]["name"] == "Pulgas Arrechas"
    assert body["teams"][0]["seriesName"] == "V.92"
    assert body["teams"][0]["hasImportedData"] is True
    assert body["teams"][0]["syncedAt"] is not None


def test_session_profile_requires_an_authenticated_manager(
    seeded_user: tuple[TestClient, int],
) -> None:
    client, _user_id = seeded_user
    resp = client.get("/api/v1/auth/chpp/session")
    assert resp.status_code == 401
