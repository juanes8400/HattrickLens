"""POST /teams/{id}/sync — el primer test HTTP real del proyecto.

Hasta ahora toda la suite ejercitaba `SyncTeamHandler` directamente; este
endpoint es distinto porque le añade sesión y ownership por encima, y ese es
justo el código nuevo que hay que proteger: sin sesión, con sesión de otro
usuario, y con sesión válida pero un token CHPP falso (mismo patrón de fixtures
reales que usa el resto de la suite, nunca red de verdad).
"""
import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.infrastructure.chpp.parsers import get_parser
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.infrastructure.security.jwt import create_session_token
from app.infrastructure.security.tokens import encrypt_token
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures"


class FakeCHPPClient:
    """Mismo doble que el resto de la suite: sirve el fixture real, nunca red."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    async def fetch(self, file: str, version: str = "latest", **_params: Any) -> dict[str, Any]:
        if file == "matchorders" and _params.get("actionType") == "predictratings":
            predicted = get_parser(file)(
                (FIXTURES / "matchorders_predictratings.xml").read_bytes()
            )
            predicted["ht_match_id"] = _params["matchID"]
            return predicted
        return get_parser(file)((FIXTURES / f"{file}.xml").read_bytes())

    async def aclose(self) -> None:
        pass


@pytest.fixture
def seeded() -> tuple[TestClient, int, int, async_sessionmaker]:
    import asyncio

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
            team = m.Team(
                ht_team_id=537758, name="Pulgas Arrechas", owner_user_id=user.id,
                currency_rate=10.0, currency_name="US$",
            )
            s.add(team)
            await s.flush()
            s.add(m.CHPPToken(
                user_id=user.id, oauth_token_enc=encrypt_token("tok"),
                oauth_secret_enc=encrypt_token("sec"), status="active", ht_user_id=999,
            ))
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


def test_sync_without_session_cookie_is_rejected(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    client, _user_id, team_id, _factory = seeded
    resp = client.post(f"/api/v1/teams/{team_id}/sync")
    assert resp.status_code == 401


def test_sync_for_a_team_you_do_not_own_is_forbidden(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    client, user_id, team_id, _factory = seeded
    other_team_id = team_id + 1  # no existe / no es tuyo
    client.cookies.set("htlens_session", create_session_token(user_id))
    resp = client.post(f"/api/v1/teams/{other_team_id}/sync")
    assert resp.status_code == 404


def test_sync_runs_for_real_with_a_valid_session(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    client, user_id, team_id, factory = seeded
    client.cookies.set("htlens_session", create_session_token(user_id))

    with (
        patch("app.api.v1.endpoints.teams.CHPPClient", FakeCHPPClient),
        patch("app.api.v1.endpoints.teams.SessionLocal", factory),
    ):
        resp = client.post(f"/api/v1/teams/{team_id}/sync")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    # 24 jugadores + training + economy + teamdetails + leaguedetails (1 jornada)
    # + 17 partidos + 1 compra propia en transfersteam + 2 partidos de liga
    # que leaguefixtures.xml backfillea con series_ht_id/match_round (HL-090)
    # + worlddetails (2026-08-04: entró a DEFAULT_FILES para mantener la
    # temporada actual fresca — ver sync_team.py) = 49, MÁS lo que ahora se
    # sincroniza automáticamente en cada sync (2026-08-05: "sincroniza todos
    # los xml que importen cada vez que sincronizamos"): 24 playerdetails
    # (LastMatch/Caps, primera vez que se ve = todos cuentan como cambio) +
    # hasta 24 transfersplayer (precio de compra/TSI para quien no lo tenía
    # resuelto, "una vez por jugador para siempre" — cae a ~0 en syncs
    # siguientes) + 3 matchdetails (2 MatchRating + 1 StadiumHistory del
    # único partido cuyo matchID coincide con el fixture estático).
    # +2 (2026-08-12: club + stafflist entraron a DEFAULT_FILES — antes sólo
    # se sincronizaban una vez a mano al conectar la cuenta, nunca de nuevo
    # con el "Sincronizar" normal) + 5 pops confirmados de trainingevents
    # (2026-08-14: por fin entró materialmente en DEFAULT_FILES) = 107
    # +2 juveniles (2026-08-15: `youthplayerlist` entró a DEFAULT_FILES — el
    # módulo de Juveniles estaba completo pero nadie descargaba el fichero,
    # así que la pantalla leía de una tabla vacía) = 109.
    assert body["syncId"] > 0
    # 86 y no 109 desde 2026-08-21: el relleno del pasado (ficha, precio
    # antiguo y pais destino de cada ex-jugador) salio de la
    # sincronizacion normal y vive en su propio boton, por lotes.
    assert body["snapshotsWritten"] == 86
    assert body["errors"] == []
    # primer sync: 24 fichajes nuevos, sin "antes" que comparar en economía/
    # training/liga/partidos (nada de eso anuncia nada en la primera vez)
    assert all(c["category"] == "jugadores" for c in body["changes"])


def test_sync_response_includes_changes_and_get_endpoint_reflects_them(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    client, user_id, team_id, factory = seeded
    client.cookies.set("htlens_session", create_session_token(user_id))

    with (
        patch("app.api.v1.endpoints.teams.CHPPClient", FakeCHPPClient),
        patch("app.api.v1.endpoints.teams.SessionLocal", factory),
    ):
        client.post(f"/api/v1/teams/{team_id}/sync")  # primer sync: siembra el "antes"
        second = client.post(f"/api/v1/teams/{team_id}/sync")

    assert second.status_code == 200
    # mismo fixture dos veces: nada cambió, así que no hay changes nuevos
    assert second.json()["changes"] == []

    changes_resp = client.get(f"/api/v1/teams/{team_id}/sync/changes")
    assert changes_resp.status_code == 200
    body = changes_resp.json()
    assert body["syncId"] is not None
    assert body["changes"] == []  # refleja el último sync (el segundo, sin cambios)


class FakeMatchDetailsCHPP(FakeCHPPClient):
    """Como el CHPP real: el `matchdetails` devuelto es del partido pedido,
    no siempre el mismo — si no, cada partido pendiente escribiría el rating
    de uno solo por encima del anterior."""

    async def fetch(self, file: str, version: str = "latest", **params: Any) -> dict[str, Any]:
        payload = await super().fetch(file, version, **params)
        if file == "matchdetails" and "matchID" in params:
            payload["ht_match_id"] = params["matchID"]
        return payload


def test_match_details_sync_fills_in_the_pending_matches(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    """2026-08-05, pedido explícitamente: "sincroniza todos los xml que
    importen cada vez que sincronizamos" — `matchdetails.xml` (HatStats,
    ratings por sector) ya no espera al botón "Sincronizar detalles" de
    Partidos: el sync normal (`matches` en DEFAULT_FILES) lo rellena solo
    para cualquier partido terminado sin ratings. El botón manual sigue
    existiendo por si algo quedó pendiente (p. ej. un error puntual de CHPP),
    pero contra una cuenta sana debe encontrar 0 partidos por procesar."""
    from sqlalchemy import select

    client, user_id, team_id, factory = seeded
    client.cookies.set("htlens_session", create_session_token(user_id))

    async def count_ratings() -> int:
        async with factory() as s:
            rows = (await s.execute(select(m.MatchRating))).scalars().all()
            return len(rows)

    with (
        # FakeMatchDetailsCHPP, no el genérico: como el CHPP real, cada
        # matchID pedido trae SU propio partido — necesario para que el
        # backfill automático, que pide varios matchID distintos en un
        # mismo sync, procese los 16 realmente (ver su docstring arriba).
        patch("app.api.v1.endpoints.teams.CHPPClient", FakeMatchDetailsCHPP),
        patch("app.api.v1.endpoints.teams.SessionLocal", factory),
    ):
        client.post(f"/api/v1/teams/{team_id}/sync")  # DEFAULT_FILES incluye "matches"

    # 2 MatchRating (casa+fuera) por cada partido finalizado — 16 de
    # matches.xml (17 en el fixture, 1 sigue "UPCOMING") + 1 más que
    # leaguefixtures.xml (HL-090, corre antes que "matches" en DEFAULT_FILES)
    # backfillea con series_ht_id/match_round y que también resulta
    # finalizado — ya completo tras el sync normal.
    assert asyncio.run(count_ratings()) == 34

    with (
        patch("app.api.v1.endpoints.teams.CHPPClient", FakeMatchDetailsCHPP),
        patch("app.api.v1.endpoints.teams.SessionLocal", factory),
    ):
        resp = client.post(f"/api/v1/teams/{team_id}/matches/details/sync")

    assert resp.status_code == 200
    body = resp.json()
    assert body["matchesProcessed"] == 0  # el sync normal ya lo dejó completo
    assert body["errors"] == []
    assert asyncio.run(count_ratings()) == 34  # sin duplicados
