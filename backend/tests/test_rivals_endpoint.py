"""GET /teams/{id}/rivals/{rivalId}/scouting — HL-099 a nivel HTTP.

Usa los mismos fixtures reales que motivaron la funcionalidad: el partido
765274387 entre Pulgas Arrechas (537758) y etbenianos1 (2688899), con
`matchlineup` real de ambos lados (nombre real, posición real) y `players`
del rival con TSI real pero nombres ocultos — exactamente como responde CHPP
de verdad para un equipo que no es el tuyo."""
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.rivals import _days_since_last_login
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
RIVAL_HT_TEAM_ID = 2688899
HT_MATCH_ID = 765274387

RIVAL_PLAYERS = {
    "players": [
        {
            "ht_player_id": pid, "first_name": "", "last_name": "", "age_years": 25,
            "age_days": 0, "tsi": tsi, "form": 5, "form_is_read": True,
            "stamina": 0, "stamina_is_read": True, "experience": 5, "experience_is_read": True,
            "salary": 3000, "specialty": 0, "injury_level": -1, "is_transfer_listed": False,
            "leadership": 0, "player_trainer_skill_level": 0, "player_trainer_type": 0,
            "skills": {"keeper": 0, "defending": 0, "playmaking": 0, "winger": 0,
                       "passing": 0, "scoring": 0, "set_pieces": 0},
        }
        for pid, tsi in [
            (498576155, 3020), (499280214, 2840), (498629801, 1850), (498059665, 310),
            (498059668, 1070), (498059677, 2180), (481249171, 16550), (480991404, 9420),
            (498059669, 260), (485337184, 4710), (498059678, 3870),
        ]
    ]
}


class FakeCHPP:
    """`teamID == OWN_HT_TEAM_ID` es el propio equipo (sync inicial, roster
    real); cualquier otro teamID es "un equipo ajeno" — como CHPP de verdad,
    da igual cuál sea, siempre se ve igual de poco (TSI real, skills ocultas,
    nombre oculto salvo en matchlineup)."""

    async def fetch(self, file: str, version: str = "latest", **params: Any) -> dict[str, Any]:
        if file == "players" and params.get("teamID") != OWN_HT_TEAM_ID:
            return RIVAL_PLAYERS
        if file == "stafflist" and params.get("teamID") != OWN_HT_TEAM_ID:
            return get_parser(file)((FIXTURES / "stafflist_rival.xml").read_bytes())
        if file == "teamdetails" and params.get("teamID") != OWN_HT_TEAM_ID:
            return {"ht_user_id": 445566, "login_name": "manager-rival", "teams": []}
        if file == "managercompendium":
            login_time = (
                "2026-08-06 08:00:00"
                if params.get("userID") == 999
                else "2026-07-30 08:00:00"
            )
            return {
                "ht_user_id": params.get("userID", 0),
                "last_logins": [login_time],
                "fetched_at": "2026-08-06 12:00:00",
            }
        if file == "matches" and params.get("teamID") not in {OWN_HT_TEAM_ID, RIVAL_HT_TEAM_ID}:
            return {"matches": []}
        if file == "matchlineup":
            fname = (
                "matchlineup.xml" if params.get("teamID") == RIVAL_HT_TEAM_ID
                else "matchlineup_home.xml"
            )
            return get_parser(file)((FIXTURES / fname).read_bytes())
        return get_parser(file)((FIXTURES / f"{file}.xml").read_bytes())

    async def aclose(self) -> None:
        pass


@pytest.mark.parametrize(
    ("last_login", "expected"),
    [
        ("2026-08-06 00:01:00", 0),
        ("2026-08-05 23:59:00", 1),
        ("2026-07-23 12:00:00", 14),
        ("2026-06-01 12:00:00", 66),
    ],
)
def test_days_since_last_login_uses_calendar_days(last_login: str, expected: int) -> None:
    assert _days_since_last_login({
        "last_logins": [last_login],
        "fetched_at": "2026-08-06 12:00:00",
    }) == expected


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
                currency_rate=10.0, currency_name="US$",
            )
            s.add(team)
            await s.flush()
            s.add(m.CHPPToken(
                user_id=user.id, oauth_token_enc=encrypt_token("tok"),
                oauth_secret_enc=encrypt_token("sec"), status="active", ht_user_id=999,
            ))
            s.add(m.Match(
                ht_match_id=HT_MATCH_ID, played_at=datetime(2026, 7, 5, tzinfo=UTC),
                match_type=1, status="FINISHED",
                home_team_ht_id=OWN_HT_TEAM_ID, away_team_ht_id=RIVAL_HT_TEAM_ID,
                home_team_name="Pulgas Arrechas", away_team_name="etbenianos1",
                home_goals=1, away_goals=2,
            ))
            s.add(m.MatchRating(
                ht_match_id=HT_MATCH_ID, team_ht_id=RIVAL_HT_TEAM_ID, is_home=False,
                midfield=15, right_def=30, central_def=27, left_def=25,
                right_att=28, central_att=27, left_att=24,
            ))
            # Lado propio del mismo partido — mismos valores del HomeTeam real
            # de fixtures/matchdetails.xml, para poder probar el mapa de calor
            # de zonas del propio equipo sin pedir nada nuevo a CHPP (ya
            # sincronizado normalmente, a diferencia del rival).
            s.add(m.MatchRating(
                ht_match_id=HT_MATCH_ID, team_ht_id=OWN_HT_TEAM_ID, is_home=True,
                midfield=14, right_def=45, central_def=61, left_def=43,
                right_att=10, central_att=9, left_att=13,
            ))
            await s.commit()
            team_id = team.id

        uow = SqlAlchemyUnitOfWork(factory)
        handler = SyncTeamHandler(uow, FakeCHPP())
        await handler.execute(
            SyncTeamCommand(user_id=user.id, team_id=team_id, ht_team_id=OWN_HT_TEAM_ID)
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


def test_scouting_requires_a_session(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    client, _user_id, team_id, _factory = seeded
    resp = client.get(f"/api/v1/teams/{team_id}/rivals/{RIVAL_HT_TEAM_ID}/scouting")
    assert resp.status_code == 401


def test_scouting_returns_real_tsi_and_real_lineup_names(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    from unittest.mock import patch

    client, user_id, team_id, factory = seeded
    client.cookies.set("htlens_session", create_session_token(user_id))

    with (
        patch("app.api.v1.endpoints.rivals.CHPPClient", lambda *_a, **_kw: FakeCHPP()),
        patch("app.api.v1.endpoints.rivals.SessionLocal", factory, create=True),
    ):
        resp = client.get(f"/api/v1/teams/{team_id}/rivals/{RIVAL_HT_TEAM_ID}/scouting")

    assert resp.status_code == 200
    body = resp.json()
    assert body["rivalName"] == "etbenianos1"
    assert body["matchesAnalysed"] == 5

    # top 5 por TSI, aunque se identificaron más jugadores en los partidos vistos
    roster = body["rivalRosterSample"]
    assert len(roster) == 5
    assert [r["tsi"] for r in roster] == sorted((r["tsi"] for r in roster), reverse=True)
    names = [p["name"] for p in roster]
    assert "Sami Suutarinen" in names  # nombre real, viene de matchlineup, no de players.xml

    # -1: el arquero (Nereo Urquiza, position_code 1) se excluye por defecto
    assert len(body["tsiHistogram"]["rivalValues"]) == len(RIVAL_PLAYERS["players"]) - 1

    assert body["sideRotation"]["strongSide"] == "derecha"
    assert body["sideRotation"]["rotates"] is False

    assert body["manMarking"] is not None
    assert body["manMarking"]["targetName"] == "Sami Suutarinen"  # mayor TSI markable

    # HL-144: proyección explícita, separada de los hechos de arriba.
    wp = body["winProbability"]
    assert 0.0 <= wp["ownProbability"] <= 1.0
    assert wp["ownTsiTotal"] > 0
    assert wp["rivalTsiTotal"] == sum(
        sorted((p["tsi"] for p in RIVAL_PLAYERS["players"]), reverse=True)[:11]
    )
    assert "baja" in wp["confidence"]


def test_submitted_orders_drive_general_comparison_and_pitch_prediction(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    """El once enviado manda en KPIs y la cancha; el rival sigue histórico."""
    import asyncio
    from unittest.mock import patch

    from sqlalchemy import select

    client, user_id, team_id, factory = seeded
    client.cookies.set("htlens_session", create_session_token(user_id))

    async def add_submitted_match() -> None:
        async with factory() as s:
            players = list((await s.execute(
                select(m.Player)
                .where(m.Player.team_id == team_id, m.Player.left_team_at.is_(None))
                .order_by(m.Player.id)
                .limit(11)
            )).scalars())
            assert len(players) == 11
            s.add(m.Match(
                ht_match_id=900000001,
                played_at=datetime.now(UTC) + timedelta(days=2),
                match_type=1,
                status="UPCOMING",
                home_team_ht_id=OWN_HT_TEAM_ID,
                away_team_ht_id=RIVAL_HT_TEAM_ID,
                home_team_name="Pulgas Arrechas",
                away_team_name="etbenianos1",
                home_goals=-1,
                away_goals=-1,
                source_system="hattrick",
                orders_given=True,
                submitted_lineup_json=json.dumps([
                    {"ht_player_id": player.ht_player_id, "role_id": 100 + index, "behaviour": 0}
                    for index, player in enumerate(players)
                ]),
                submitted_tactic_type=2,
                submitted_tactic_skill=19,
                submitted_rating_midfield=18,
                submitted_rating_right_def=70,
                submitted_rating_central_def=90,
                submitted_rating_left_def=65,
                submitted_rating_right_att=28,
                submitted_rating_central_att=32,
                submitted_rating_left_att=56,
                submitted_ratings_captured_at=datetime.now(UTC),
            ))
            await s.commit()

    asyncio.run(add_submitted_match())
    with patch("app.api.v1.endpoints.rivals.CHPPClient", lambda *_a, **_kw: FakeCHPP()):
        resp = client.get(
            f"/api/v1/teams/{team_id}/rivals/{RIVAL_HT_TEAM_ID}/scouting?top11=true"
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["comparisonReference"] == {
        "ownSource": "submitted_orders",
        "ownLabel": "Alineación enviada · partido 900000001",
        "ownPlayers": 11,
        "rivalSource": "probable_recent_starters",
        "rivalLabel": "Once probable · recurrencia reciente",
        "rivalPlayers": 11,
    }
    assert body["pitchZoneSources"]["own"]["kind"] == "submitted_chpp_prediction"
    assert body["pitchZoneSources"]["own"]["tacticSkill"] == 19
    assert body["pitchZoneSources"]["rival"]["kind"] == "historical_observed"
    assert body["pitchZonesMatchesAnalysed"] == {"own": 1, "rival": 5}
    midfield = next(
        duel for duel in body["pitchZoneDuels"] if duel["half"] == "midfield"
    )
    assert midfield["ownValue"] == 18
    assert len(body["tsiHistogram"]["ownValues"]) == 11
    assert len(body["tsiHistogram"]["rivalValues"]) == 10  # arquero excluido


def test_comparison_reads_trainer_leadership_from_rival_stafflist(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    """TSI, forma, condición y experiencia son públicas de un rival
    (verificado en vivo contra CHPP real). El liderazgo del entrenador rival
    sale de su stafflist.xml versión 1.2 — verificado en vivo que esa
    versión expone al entrenador principal de cualquier equipo, propio o
    no (a diferencia de la 1.0/"latest" del mismo fichero, que sí deniega)."""
    import asyncio
    from unittest.mock import patch

    client, user_id, team_id, factory = seeded
    client.cookies.set("htlens_session", create_session_token(user_id))

    async def seed_staff() -> None:
        async with factory() as s:
            # 2026-08-12: club/stafflist ahora entran en el sync por defecto
            # (ver DEFAULT_FILES), así que el fixture `seeded` YA escribió un
            # StaffSnapshot real al conectar — este se sella con un
            # `captured_at` futuro para seguir siendo, sin ambigüedad, "el
            # más reciente" y así controlar el valor que ve el test.
            s.add(m.StaffSnapshot(
                sync_id=1, team_id=team_id,
                captured_at=datetime.now(UTC) + timedelta(days=365),
                assistant_trainer_levels=6, trainer_skill_level=4, trainer_type=2,
                trainer_leadership=7, youth_investment=0, youth_level=0,
                content_hash=b"\x01" * 32,
            ))
            await s.commit()

    asyncio.run(seed_staff())

    with patch("app.api.v1.endpoints.rivals.CHPPClient", lambda *_a, **_kw: FakeCHPP()):
        resp = client.get(f"/api/v1/teams/{team_id}/rivals/{RIVAL_HT_TEAM_ID}/scouting")

    assert resp.status_code == 200
    comparison = resp.json()["comparison"]

    assert comparison["tsi"]["own"] is not None and comparison["tsi"]["rival"] is not None
    assert comparison["form"]["rival"] == 5.0  # RIVAL_PLAYERS: form=5 en todos
    assert comparison["stamina"]["rival"] == 0.0  # form_is_read=True, 0 es un nivel real
    assert comparison["experience"]["rival"] == 5.0
    assert comparison["lastLoginDays"] == {"own": 0, "rival": 7}

    assert comparison["trainerLeadership"]["own"] == 7
    assert comparison["trainerLeadership"]["rival"] == 4  # stafflist_rival.xml: Leadership=4


def test_comparison_reads_trainer_leadership_from_a_rival_playing_coach(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    """Si stafflist.xml no trae al entrenador principal (p.ej. denegado esta
    vez) pero el rival entrena con uno de sus propios jugadores, ese jugador
    trae <TrainerData> en el MISMO players.xml público — su Leadership real
    es el liderazgo del entrenador, sin necesitar stafflist."""
    from unittest.mock import patch

    client, user_id, team_id, _factory = seeded
    client.cookies.set("htlens_session", create_session_token(user_id))

    players_with_coach = {
        "players": [
            {**p, "player_trainer_skill_level": 4, "player_trainer_type": 2, "leadership": 8,
             "first_name": "Fulano", "last_name": "Entrenador"}
            if i == 0 else p
            for i, p in enumerate(RIVAL_PLAYERS["players"])
        ]
    }

    class FakeCHPPWithPlayingCoach(FakeCHPP):
        async def fetch(self, file: str, version: str = "latest", **params: Any) -> dict[str, Any]:
            if file == "players" and params.get("teamID") != OWN_HT_TEAM_ID:
                return players_with_coach
            if file == "stafflist" and params.get("teamID") != OWN_HT_TEAM_ID:
                return {}  # stafflist.xml denegado esta vez: sin nodo StaffList
            return await super().fetch(file, version, **params)

    with patch(
        "app.api.v1.endpoints.rivals.CHPPClient", lambda *_a, **_kw: FakeCHPPWithPlayingCoach()
    ):
        resp = client.get(f"/api/v1/teams/{team_id}/rivals/{RIVAL_HT_TEAM_ID}/scouting")

    assert resp.status_code == 200
    body = resp.json()
    assert body["comparison"]["trainerLeadership"]["rival"] == 8


def test_comparison_trainer_leadership_is_none_when_both_sources_are_empty(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    """Cuando ni stafflist.xml (denegado esta vez) ni players.xml (sin
    jugador-entrenador) traen nada, el liderazgo del rival se queda en
    `None` — nunca se inventa un valor."""
    from unittest.mock import patch

    client, user_id, team_id, _factory = seeded
    client.cookies.set("htlens_session", create_session_token(user_id))

    class FakeCHPPWithoutTrainer(FakeCHPP):
        async def fetch(self, file: str, version: str = "latest", **params: Any) -> dict[str, Any]:
            if file == "stafflist" and params.get("teamID") != OWN_HT_TEAM_ID:
                return {}
            return await super().fetch(file, version, **params)

    with patch(
        "app.api.v1.endpoints.rivals.CHPPClient", lambda *_a, **_kw: FakeCHPPWithoutTrainer()
    ):
        resp = client.get(f"/api/v1/teams/{team_id}/rivals/{RIVAL_HT_TEAM_ID}/scouting")

    assert resp.status_code == 200
    assert resp.json()["comparison"]["trainerLeadership"]["rival"] is None


def test_scouting_without_matches_still_compares_tsi(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    from unittest.mock import patch

    client, user_id, team_id, factory = seeded
    client.cookies.set("htlens_session", create_session_token(user_id))
    other_rival = 999999

    with patch("app.api.v1.endpoints.rivals.CHPPClient", lambda *_a, **_kw: FakeCHPP()):
        resp = client.get(f"/api/v1/teams/{team_id}/rivals/{other_rival}/scouting")

    assert resp.status_code == 200
    body = resp.json()
    assert body["matchesAnalysed"] == 0
    assert body["manMarking"] is None
    assert body["sideRotation"] is None
    # sin partidos vistos no hay position_code de nadie: no se excluye a nadie
    # aunque el toggle esté activo (nunca se adivina quién es el arquero)
    assert len(body["tsiHistogram"]["rivalValues"]) == len(RIVAL_PLAYERS["players"])
    assert any("no tiene partidos oficiales recientes" in c for c in body["caveats"])


def test_non_official_matches_are_excluded_from_head_to_head_by_default(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    """Escaleras/Duelos (MatchType 50/62, HL-146) no cuentan como "partido ya
    jugado" contra este rival salvo que se pidan explícitamente."""
    import asyncio
    from unittest.mock import patch

    client, user_id, team_id, factory = seeded
    client.cookies.set("htlens_session", create_session_token(user_id))

    async def add_ladder_match():
        async with factory() as s:
            s.add(m.Match(
                ht_match_id=900_555, played_at=datetime(2026, 7, 10, tzinfo=UTC),
                match_type=50, status="finished",
                home_team_ht_id=OWN_HT_TEAM_ID, away_team_ht_id=RIVAL_HT_TEAM_ID,
                home_team_name="Pulgas Arrechas", away_team_name="etbenianos1",
                home_goals=1, away_goals=0,
            ))
            await s.commit()

    asyncio.run(add_ladder_match())

    with patch("app.api.v1.endpoints.rivals.CHPPClient", lambda *_a, **_kw: FakeCHPP()):
        default_resp = client.get(f"/api/v1/teams/{team_id}/rivals/{RIVAL_HT_TEAM_ID}/scouting")
        included_resp = client.get(
            f"/api/v1/teams/{team_id}/rivals/{RIVAL_HT_TEAM_ID}/scouting"
            "?include_non_official=true"
        )

    assert default_resp.json()["matchesAnalysed"] == 5
    assert any(
        "Duelos, Escaleras y partidos de Selección nacional nunca cuentan" in c for c in default_resp.json()["caveats"]
    )
    assert included_resp.json()["matchesAnalysed"] == 5


def test_top11_restricts_own_side_and_takes_highest_tsi_rivals(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    from unittest.mock import patch

    client, user_id, team_id, factory = seeded
    client.cookies.set("htlens_session", create_session_token(user_id))

    with patch("app.api.v1.endpoints.rivals.CHPPClient", lambda *_a, **_kw: FakeCHPP()):
        resp = client.get(
            f"/api/v1/teams/{team_id}/rivals/{RIVAL_HT_TEAM_ID}/scouting"
            "?top11=true&exclude_keeper=false"
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["tsiHistogram"]["top11"] is True
    # el once real (motor de posiciones) siempre tiene 11 jugadores
    assert len(body["tsiHistogram"]["ownValues"]) == 11
    # el rival: los 11 de mayor TSI, sin adivinar su once real
    rival_values = body["tsiHistogram"]["rivalValues"]
    assert len(rival_values) == 11
    assert sorted(rival_values, reverse=True) == sorted(
        [p["tsi"] for p in RIVAL_PLAYERS["players"]], reverse=True
    )[:11]
    assert any("Los 11 mejores" in c for c in body["caveats"])


def test_tactic_history_summarises_all_synced_matches_not_capped(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    """El historial de táctica usa TODOS los partidos con MatchRating del
    rival ya en la base — no el mismo cap de 5 que limita las llamadas en
    vivo a matchlineup (esas sí cuestan una petición a CHPP por partido)."""
    import asyncio
    from unittest.mock import patch

    client, user_id, team_id, factory = seeded
    client.cookies.set("htlens_session", create_session_token(user_id))

    async def add_second_match_with_tactic() -> None:
        async with factory() as s:
            s.add(m.Match(
                ht_match_id=900_777, played_at=datetime(2026, 7, 12, tzinfo=UTC),
                match_type=1, status="FINISHED",
                home_team_ht_id=RIVAL_HT_TEAM_ID, away_team_ht_id=OWN_HT_TEAM_ID,
                home_team_name="etbenianos1", away_team_name="Pulgas Arrechas",
                home_goals=0, away_goals=1,
            ))
            s.add(m.MatchRating(
                ht_match_id=900_777, team_ht_id=RIVAL_HT_TEAM_ID, is_home=True,
                midfield=15, right_def=30, central_def=27, left_def=25,
                right_att=28, central_att=27, left_att=24,
                tactic_type=4, attitude=1,
            ))
            # también la del fixture original: le damos un tactic_type real
            row = await s.get(m.MatchRating, 1)
            if row is not None:
                row.tactic_type = 4
                row.attitude = -1
            await s.commit()

    asyncio.run(add_second_match_with_tactic())

    with patch("app.api.v1.endpoints.rivals.CHPPClient", lambda *_a, **_kw: FakeCHPP()):
        resp = client.get(f"/api/v1/teams/{team_id}/rivals/{RIVAL_HT_TEAM_ID}/scouting")

    assert resp.status_code == 200
    body = resp.json()
    th = body["tacticHistory"]
    assert th is not None
    # 2 partidos con MatchRating del rival, aunque matchesAnalysed (matchlineup
    # en vivo) siga limitado por MAX_MATCHES_ANALYSED / lo que haya jugado.
    assert th["matchesAnalysed"] == 5
    assert th["mostCommonTactic"]["code"] == 4
    assert th["mostCommonTactic"]["label"] == "Atacar por las bandas"
    assert th["mostCommonTactic"]["count"] == 5
    assert th["mostCommonTactic"]["pct"] == 100.0
    # TacticSkill y Formation SÍ son públicos para el rival (a diferencia de
    # TeamAttitude) — fixtures/matchdetails.xml trae TacticSkill=11 y
    # Formation="4-4-2" también para el AwayTeam.
    assert th["avgTacticSkill"] == 11.0
    assert th["mostCommonFormation"] == {"formation": "4-4-2", "count": 5, "pct": 100.0}


def test_analyses_the_most_recent_matches_not_the_oldest(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    """MAX_MATCHES_ANALYSED=5 (HL-2xx corrección): con 6 partidos reales
    contra el rival, el endpoint debe quedarse con los 5 MÁS RECIENTES —
    antes tomaba los 5 más antiguos (order_by(asc) + limit), justo al
    revés de lo útil para marcaje/rotación de lado.

    Prueba directa: el partido original del fixture (2026-07-05, el más
    antiguo una vez añadimos 5 posteriores) se marca con un nombre de
    rival distinto ("ExcludedOldRival"). Si `rivalName` en la respuesta
    sigue siendo "etbenianos1" (el de los 5 partidos nuevos), es porque el
    más antiguo quedó fuera del cap, no dentro."""
    import asyncio
    from unittest.mock import patch

    client, user_id, team_id, factory = seeded
    client.cookies.set("htlens_session", create_session_token(user_id))

    async def rename_original_and_add_five_more_recent() -> None:
        async with factory() as s:
            original = await s.get(m.Match, 1)
            assert original is not None
            original.away_team_name = "ExcludedOldRival"
            for i in range(5):
                s.add(m.Match(
                    ht_match_id=910_000 + i,
                    played_at=datetime(2026, 7, 20 + i, tzinfo=UTC),
                    match_type=1, status="FINISHED",
                    home_team_ht_id=OWN_HT_TEAM_ID, away_team_ht_id=RIVAL_HT_TEAM_ID,
                    home_team_name="Pulgas Arrechas", away_team_name="etbenianos1",
                    home_goals=1, away_goals=0,
                ))
            await s.commit()

    asyncio.run(rename_original_and_add_five_more_recent())

    with patch("app.api.v1.endpoints.rivals.CHPPClient", lambda *_a, **_kw: FakeCHPP()):
        resp = client.get(f"/api/v1/teams/{team_id}/rivals/{RIVAL_HT_TEAM_ID}/scouting")

    assert resp.status_code == 200
    body = resp.json()
    assert body["matchesAnalysed"] == 5  # el cap se sigue respetando de 6 reales
    assert body["rivalName"] == "etbenianos1"  # NO "ExcludedOldRival": el más antiguo quedó fuera


def test_non_official_matches_never_feed_tactic_history_or_rotation(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    """Corrección HL-2xx: en Duelos/Escaleras `match_ratings.team_ht_id` es un
    ID efímero que nunca coincide con el ht_team_id real del rival (ni con el
    del equipo propio — comprobado con datos reales de la cuenta), así que
    hace falta resolver la fila del rival por posición (`MatchRating.is_home`
    frente a `Match.home_team_ht_id`/`away_team_ht_id`, que sí son reales
    incluso en Duelos — ver migración 0018). Aun con eso técnicamente
    resuelto, el historial de táctica y la rotación de lado siguen ignorando
    Duelos/Escaleras SIEMPRE — decisión de producto, no limitación técnica:
    esos partidos no representan cómo juega el rival normalmente (alineación
    rotada/reserva)."""
    import asyncio
    from unittest.mock import patch

    client, user_id, team_id, factory = seeded
    client.cookies.set("htlens_session", create_session_token(user_id))

    async def add_duel() -> None:
        async with factory() as s:
            s.add(m.Match(
                ht_match_id=920_000, played_at=datetime(2026, 7, 15, tzinfo=UTC),
                match_type=62, status="FINISHED",
                home_team_ht_id=OWN_HT_TEAM_ID, away_team_ht_id=RIVAL_HT_TEAM_ID,
                home_team_name="Pulgas Arrechas", away_team_name="etbenianos1",
                home_goals=3, away_goals=0,
            ))
            # team_ht_id efímero a propósito (así es en un duelo real): lo que
            # localizaría esta fila como la del rival, si algo la localizara,
            # es is_home=False — coherente con que el rival jugó como away.
            s.add(m.MatchRating(
                ht_match_id=920_000, team_ht_id=999_111_222, is_home=False,
                midfield=99, right_def=1, central_def=1, left_def=1,
                right_att=1, central_att=1, left_att=99,  # lado fuerte distinto, si contara
                tactic_type=8, attitude=1,  # táctica distinta, si contara
            ))
            s.add(m.MatchRating(
                ht_match_id=920_000, team_ht_id=999_333_444, is_home=True,
                midfield=50, right_def=50, central_def=50, left_def=50,
                right_att=50, central_att=50, left_att=50,
            ))
            await s.commit()

    asyncio.run(add_duel())

    with patch("app.api.v1.endpoints.rivals.CHPPClient", lambda *_a, **_kw: FakeCHPP()):
        resp = client.get(
            f"/api/v1/teams/{team_id}/rivals/{RIVAL_HT_TEAM_ID}/scouting"
            "?include_non_official=true"
        )

    assert resp.status_code == 200
    body = resp.json()
    # El duelo SÍ cuenta para nombres/posiciones (matchesAnalysed sube a 2)...
    assert body["matchesAnalysed"] == 5
    # ...pero el historial de táctica y la rotación de lado siguen viendo solo
    # el partido oficial original del fixture, aunque el duelo ahora SÍ se
    # podría resolver por posición (is_home) si se quisiera.
    assert body["tacticHistory"]["matchesAnalysed"] == 5
    assert body["sideRotation"]["matchesAnalysed"] == 5
    assert any(
        "Duelos, Escaleras y partidos de Selección nacional nunca cuentan" in c
        for c in body["caveats"]
    )


def test_national_team_matches_never_count_and_preseason_never_counts_either(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    """Decisión de producto confirmada con el usuario: los partidos de
    Selección nacional (tipo 10/11/12) nunca cuentan para la ficha de un
    rival, ni siquiera bajo el toggle competitivo — se juegan con otro
    cuerpo técnico, a veces otro país, y no dicen nada de cómo juega el
    CLUB rival. 2026-08-11, pedido explícito y más reciente: los de
    pretemporada (Preparación, tipo 80) tampoco cuentan nunca — junto con
    Torneo liga/playoff, Duelo y Escalera, son partidos de mentiras."""
    from unittest.mock import patch

    client, user_id, team_id, _factory = seeded
    client.cookies.set("htlens_session", create_session_token(user_id))

    custom_matches = {
        "matches": [
            {
                "ht_match_id": 700_001, "home_team_id": RIVAL_HT_TEAM_ID,
                "home_team_name": "etbenianos1", "away_team_id": 900_001,
                "away_team_name": "Selección rival", "match_date": "2026-07-01 00:00:00",
                "match_type": 10, "status": "FINISHED", "home_goals": 1, "away_goals": 0,
                "cup_level": -1, "cup_level_index": -1,
            },
            {
                "ht_match_id": 700_002, "home_team_id": RIVAL_HT_TEAM_ID,
                "home_team_name": "etbenianos1", "away_team_id": 900_002,
                "away_team_name": "Rival de pretemporada", "match_date": "2026-07-02 00:00:00",
                "match_type": 80, "status": "FINISHED", "home_goals": 2, "away_goals": 1,
                "cup_level": -1, "cup_level_index": -1,
            },
        ]
    }

    class FakeCHPPWithCustomMatches(FakeCHPP):
        async def fetch(
            self, file: str, version: str = "latest", **params: Any
        ) -> dict[str, Any]:
            if file == "matches" and params.get("teamID") == RIVAL_HT_TEAM_ID:
                return custom_matches
            return await super().fetch(file, version, **params)

    with patch(
        "app.api.v1.endpoints.rivals.CHPPClient", lambda *_a, **_kw: FakeCHPPWithCustomMatches()
    ):
        competitive_only = client.get(
            f"/api/v1/teams/{team_id}/rivals/{RIVAL_HT_TEAM_ID}/scouting"
            "?include_competitive=true&include_friendlies=false"
        )
        friendlies_only = client.get(
            f"/api/v1/teams/{team_id}/rivals/{RIVAL_HT_TEAM_ID}/scouting"
            "?include_competitive=false&include_friendlies=true"
        )

    assert competitive_only.status_code == 200
    assert friendlies_only.status_code == 200
    # Selección nacional (tipo 10) nunca cuenta, ni siquiera bajo "competitivo".
    assert competitive_only.json()["matchesAnalysed"] == 0
    # Preparación (tipo 80) tampoco cuenta nunca, ni siquiera bajo "Amistosos".
    assert friendlies_only.json()["matchesAnalysed"] == 0


def test_pitch_zone_duels_pair_mirrored_flanks_on_both_halves(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    """7 duelos cabeza a cabeza: 3 en tu campo (tu defensa vs. su ataque
    espejado), 3 en el campo rival (tu ataque vs. su defensa espejada), y
    medio campo. El rival sale de sus partidos en vivo; el propio equipo, de
    MatchRating ya sincronizado (sin llamada nueva a CHPP)."""
    from unittest.mock import patch

    client, user_id, team_id, _factory = seeded
    client.cookies.set("htlens_session", create_session_token(user_id))

    with patch("app.api.v1.endpoints.rivals.CHPPClient", lambda *_a, **_kw: FakeCHPP()):
        resp = client.get(f"/api/v1/teams/{team_id}/rivals/{RIVAL_HT_TEAM_ID}/scouting")

    assert resp.status_code == 200
    body = resp.json()
    duels = {(d["zone"], d["half"]): d for d in body["pitchZoneDuels"]}
    assert len(duels) == 7

    # Propio (único MatchRating sembrado, HomeTeam real): left_def=43,
    # central_def=61, right_def=45, midfield=14, left_att=13, central_att=9,
    # right_att=10. Rival (5 partidos en vivo, AwayTeam real): left_def=25,
    # central_def=27, right_def=30, midfield=15, left_att=24, central_att=27,
    # right_att=28.
    left_own = duels[("left", "own")]
    assert left_own["ownValue"] == 43 and left_own["rivalValue"] == 28  # own.left_def vs rival.right_att
    assert left_own["ownPct"] == round(43 / 71, 3)

    central_own = duels[("central", "own")]
    assert central_own["ownValue"] == 61 and central_own["rivalValue"] == 27

    right_own = duels[("right", "own")]
    assert right_own["ownValue"] == 45 and right_own["rivalValue"] == 24

    left_rival = duels[("left", "rival")]
    assert left_rival["ownValue"] == 13 and left_rival["rivalValue"] == 30  # own.left_att vs rival.right_def

    central_rival = duels[("central", "rival")]
    assert central_rival["ownValue"] == 9 and central_rival["rivalValue"] == 27

    right_rival = duels[("right", "rival")]
    assert right_rival["ownValue"] == 10 and right_rival["rivalValue"] == 25

    midfield = duels[("midfield", "midfield")]
    assert midfield["ownValue"] == 14 and midfield["rivalValue"] == 15
    assert midfield["ownPct"] == round(14 / 29, 3)
    assert round(midfield["ownPct"] + midfield["rivalPct"], 3) == 1.0

    assert body["pitchZonesMatchesAnalysed"] == {"own": 1, "rival": 5}


def test_pitch_zone_duels_are_none_without_matches_on_either_side(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    """Sin partidos con datos de sector de alguno de los dos lados, no se
    inventa ningún duelo — se queda en `None`."""
    from unittest.mock import patch

    client, user_id, team_id, _factory = seeded
    client.cookies.set("htlens_session", create_session_token(user_id))
    other_rival = 999999

    with patch("app.api.v1.endpoints.rivals.CHPPClient", lambda *_a, **_kw: FakeCHPP()):
        resp = client.get(f"/api/v1/teams/{team_id}/rivals/{other_rival}/scouting")

    assert resp.status_code == 200
    body = resp.json()
    assert body["pitchZoneDuels"] is None
    assert body["pitchZonesMatchesAnalysed"] == {"own": 1, "rival": None}


def test_pitch_zone_scope_selector_is_independent_from_page_toggles(
    seeded: tuple[TestClient, int, int, async_sessionmaker],
) -> None:
    """El selector local del panel de Duelos por zona (`pitch_zone_scope`)
    puede pedir "solo oficiales" o "solo amistosos" del RIVAL sin tocar los
    toggles globales de la página (que siguen determinando roster, marcaje,
    táctica...) — fixtures/matches.xml (reusado para el rival) tiene 2
    partidos de liga (tipo 1) y 6 amistosos internacionales (tipo 9)."""
    from unittest.mock import patch

    client, user_id, team_id, _factory = seeded
    client.cookies.set("htlens_session", create_session_token(user_id))

    with patch("app.api.v1.endpoints.rivals.CHPPClient", lambda *_a, **_kw: FakeCHPP()):
        mixed = client.get(f"/api/v1/teams/{team_id}/rivals/{RIVAL_HT_TEAM_ID}/scouting")
        official = client.get(
            f"/api/v1/teams/{team_id}/rivals/{RIVAL_HT_TEAM_ID}/scouting"
            "?pitch_zone_scope=official"
        )
        friendly = client.get(
            f"/api/v1/teams/{team_id}/rivals/{RIVAL_HT_TEAM_ID}/scouting"
            "?pitch_zone_scope=friendly"
        )

    assert mixed.status_code == official.status_code == friendly.status_code == 200
    # "mixed" (por defecto) es exactamente el comportamiento de siempre: 5,
    # mezclando liga y amistosos según los toggles globales (ambos on).
    assert mixed.json()["pitchZonesMatchesAnalysed"]["rival"] == 5
    assert mixed.json()["pitchZoneScope"] == "mixed"
    # "official": solo los 2 partidos de liga (tipo 1) del rival.
    assert official.json()["pitchZonesMatchesAnalysed"]["rival"] == 2
    assert official.json()["pitchZoneScope"] == "official"
    # "friendly": los 5 más recientes de los 6 amistosos internacionales.
    assert friendly.json()["pitchZonesMatchesAnalysed"]["rival"] == 5
    assert friendly.json()["pitchZoneScope"] == "friendly"

    # Nada del resto de la ficha (roster, marcaje, matchesAnalysed global)
    # cambia por el selector local — sigue atado a los toggles de arriba.
    assert (
        mixed.json()["matchesAnalysed"]
        == official.json()["matchesAnalysed"]
        == friendly.json()["matchesAnalysed"]
        == 5
    )
