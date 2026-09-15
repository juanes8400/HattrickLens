"""GET /teams/{id}/league/comparison, HL-090+ a nivel HTTP.

No solo el próximo rival: dónde queda la plantilla frente a TODA la serie.
Usa el mismo límite ya verificado en el scouting de un solo rival (TSI real,
nombres/skills ocultos por CHPP), agregado a varios equipos a la vez."""
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.sync_team import SyncTeamCommand, SyncTeamHandler
from app.infrastructure.chpp.parsers import get_parser
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.security.jwt import create_session_token
from app.infrastructure.security.tokens import encrypt_token
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures"
OWN_HT_TEAM_ID = 537758
SERIES_HT_ID = 34162
SEASON = 84
ROUND = 1

RIVAL_A_ID, RIVAL_B_ID = 600001, 600002
CUP_RIVAL_ID = 600003

# TSI reales pero anónimos, como responde CHPP de verdad para un equipo ajeno.
RIVAL_ROSTERS = {
    RIVAL_A_ID: [
        {"ht_player_id": 900000 + i, "first_name": "", "last_name": "", "age_years": 25,
         "age_days": 0, "tsi": tsi, "form": 5, "stamina": 0, "experience": 5, "salary": 1000,
         "specialty": 0, "injury_level": -1, "is_transfer_listed": False,
         "skills": {"keeper": 0, "defending": 0, "playmaking": 0, "winger": 0,
                    "passing": 0, "scoring": 0, "set_pieces": 0}}
        for i, tsi in enumerate([50000, 40000, 30000])
    ],
    RIVAL_B_ID: [
        {"ht_player_id": 910000 + i, "first_name": "", "last_name": "", "age_years": 25,
         "age_days": 0, "tsi": tsi, "form": 5, "stamina": 0, "experience": 5, "salary": 1000,
         "specialty": 0, "injury_level": -1, "is_transfer_listed": False,
         "skills": {"keeper": 0, "defending": 0, "playmaking": 0, "winger": 0,
                    "passing": 0, "scoring": 0, "set_pieces": 0}}
        for i, tsi in enumerate([5000, 4000, 3000])
    ],
    CUP_RIVAL_ID: [
        {"ht_player_id": 920000 + i, "first_name": "", "last_name": "", "age_years": 25,
         "age_days": 0, "tsi": tsi, "form": 6, "stamina": 7, "experience": 4, "salary": 1000,
         "specialty": 0, "injury_level": -1, "is_transfer_listed": False,
         "form_is_read": True, "stamina_is_read": True, "experience_is_read": True,
         "skills": {"keeper": 0, "defending": 0, "playmaking": 0, "winger": 0,
                    "passing": 0, "scoring": 0, "set_pieces": 0}}
        for i, tsi in enumerate([20000, 10000, 5000])
    ],
}


class FakeCHPP:
    """`teamID == OWN_HT_TEAM_ID` sincroniza el propio equipo (roster real
    del fixture); cualquier otro id es un rival de la serie."""

    async def fetch(self, file: str, version: str = "latest", **params: Any) -> dict[str, Any]:
        if file == "players" and params.get("teamID") != OWN_HT_TEAM_ID:
            return {"players": RIVAL_ROSTERS[params["teamID"]]}
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
                ht_team_id=OWN_HT_TEAM_ID, name="Pulgas Arrechas", owner_user_id=user.id,
                series_name="V.92", currency_rate=10.0, currency_name="US$",
            )
            s.add(team)
            await s.flush()
            s.add(m.CHPPToken(
                user_id=user.id, oauth_token_enc=encrypt_token("tok"),
                oauth_secret_enc=encrypt_token("sec"), status="active", ht_user_id=999,
            ))
            captured = datetime.now(UTC)
            sync = m.Sync(user_id=user.id, team_id=team.id, kind="manual",
                          status="completed", started_at=captured)
            s.add(sync)
            await s.flush()
            for ht_id, name, points in [
                (OWN_HT_TEAM_ID, "Pulgas Arrechas", 3),
                (RIVAL_A_ID, "Rival Fuerte", 6),
                (RIVAL_B_ID, "Rival Débil", 0),
            ]:
                s.add(m.Standing(
                    sync_id=sync.id, series_ht_id=SERIES_HT_ID, season=SEASON,
                    match_round=ROUND, captured_at=captured, team_ht_id=ht_id,
                    team_name=name, position=0, played=1, won=0, draws=0, lost=0,
                    goals_for=0, goals_against=0, points=points,
                ))
            await s.commit()
            team_id = team.id

        uow = SqlAlchemyUnitOfWork(factory)
        handler = SyncTeamHandler(uow, FakeCHPP())
        # Solo el roster propio: DEFAULT_FILES incluye leaguedetails, que
        # escribiría los Standing del fixture real por encima de los que
        # este test siembra a mano para su propia serie de prueba.
        await handler.execute(
            SyncTeamCommand(
                user_id=1, team_id=team_id, ht_team_id=OWN_HT_TEAM_ID,
                files=["players", "training", "economy"],
            )
        )
        return user.id, team_id

    user_id, team_id = asyncio.run(setup())

    async def override_get_session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    yield client, user_id, team_id, factory
    app.dependency_overrides.clear()


def test_league_comparison_requires_a_session(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    client, _user_id, team_id, _factory = seeded
    resp = client.get(f"/api/v1/teams/{team_id}/league/comparison")
    assert resp.status_code == 401


def test_league_comparison_ranks_all_teams_in_the_series(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    client, user_id, team_id, _factory = seeded
    client.cookies.set("htlens_session", create_session_token(user_id))

    with patch("app.api.v1.endpoints.league.CHPPClient", lambda *_a, **_kw: FakeCHPP()):
        resp = client.get(f"/api/v1/teams/{team_id}/league/comparison")

    assert resp.status_code == 200
    body = resp.json()
    assert body["teamsInSeries"] == 3
    assert body["seriesName"] == "V.92"

    names = {r["teamName"]: r["rank"] for r in body["ranking"]}
    # El TSI total suma toda la plantilla: nuestros 24 jugadores reales del
    # fixture superan por mucho a los rivales sintéticos de 3 jugadores cada
    # uno, y entre esos dos, Rival Fuerte queda por delante de Rival Débil.
    assert names["Pulgas Arrechas"] == 1
    assert names["Rival Fuerte"] == 2
    assert names["Rival Débil"] == 3
    assert body["ownRank"] == 1

    own_row = next(r for r in body["ranking"] if r["isOwn"])
    assert own_row["playerCount"] == 24

    assert len(body["tsiHistogram"]["rivalValues"]) == 6  # 3 + 3 de los dos rivales
    assert any("no se publican" in c for c in body["caveats"])


def test_league_comparison_top11_restricts_own_and_rival_samples(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    client, user_id, team_id, _factory = seeded
    client.cookies.set("htlens_session", create_session_token(user_id))

    with patch("app.api.v1.endpoints.league.CHPPClient", lambda *_a, **_kw: FakeCHPP()):
        resp = client.get(f"/api/v1/teams/{team_id}/league/comparison?top11=true")

    assert resp.status_code == 200
    body = resp.json()
    own_row = next(r for r in body["ranking"] if r["isOwn"])
    assert own_row["playerCount"] == 11  # el once real, no la plantilla de 24
    rival_row = next(r for r in body["ranking"] if r["teamName"] == "Rival Fuerte")
    assert rival_row["playerCount"] == 3  # ya tenía menos de 11, top11 no lo cambia


def test_league_comparison_adds_the_cup_rival_apart_only_when_asked(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    """2026-09-15, para la flor del Dashboard: el próximo rival de Copa llega en
    `cupRival`, fuera del ranking, del histograma y del puesto propio, que
    siguen siendo de la serie. Sin `incluir_copa`, ni se pide."""
    import asyncio

    client, user_id, team_id, factory = seeded
    client.cookies.set("htlens_session", create_session_token(user_id))

    async def siembra_copa() -> None:
        async with factory() as s:
            team = await s.get(m.Team, team_id)
            team.still_in_cup = True
            team.current_cup_name = "Copa Cocuy Rubí"
            s.add(m.Match(
                ht_match_id=9_800_001, played_at=datetime(2000, 1, 1, tzinfo=UTC),
                match_type=3, status="UPCOMING", home_team_ht_id=CUP_RIVAL_ID,
                away_team_ht_id=OWN_HT_TEAM_ID, home_team_name="Rival de Copa",
                away_team_name="Pulgas Arrechas", home_goals=-1, away_goals=-1,
            ))
            await s.commit()

    asyncio.run(siembra_copa())

    with patch("app.api.v1.endpoints.league.CHPPClient", lambda *_a, **_kw: FakeCHPP()):
        sin = client.get(f"/api/v1/teams/{team_id}/league/comparison?top11=true")
        con = client.get(
            f"/api/v1/teams/{team_id}/league/comparison?top11=true&incluir_copa=true"
        )

    assert sin.status_code == 200 and con.status_code == 200
    assert sin.json()["cupRival"] is None

    body = con.json()
    assert body["teamsInSeries"] == 3
    assert all(r["teamName"] != "Rival de Copa" for r in body["ranking"])
    assert len(body["tsiHistogram"]["rivalValues"]) == 6  # sólo los de la serie
    copa = body["cupRival"]
    assert copa["teamName"] == "Rival de Copa"
    assert copa["cupName"] == "Copa Cocuy Rubí"
    assert copa["totalTsi"] == 35000
    assert copa["avgForm"] == 6.0 and copa["avgStamina"] == 7.0
    assert copa["rank"] is None
