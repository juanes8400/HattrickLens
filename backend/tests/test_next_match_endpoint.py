"""GET /teams/{id}/next-match/analysis — HL-2xx.

Antes esta vista tenía su propio pipeline en vivo (players.xml + matches.xml
+ matchlineup.xml del rival), separado del que ya usa la ficha completa de
rival (`/rivals/{id}/scouting`) — duplicaba llamadas a CHPP y usaba un filtro
de tipo de partido más viejo, que todavía dejaba pasar Selección nacional
como "oficial". Ahora comparte `fetch_rival_matches_and_lineups` con
`rivals.py`; este test verifica que ese reuso sigue sirviendo datos
correctos de punta a punta, con los mismos fixtures reales que ya motivaron
la ficha de rival.
"""
import asyncio
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from sqlalchemy import select

from app.infrastructure.db import models as m
from app.infrastructure.security.jwt import create_session_token
from tests.test_rivals_endpoint import FakeCHPP, OWN_HT_TEAM_ID, RIVAL_HT_TEAM_ID, seeded  # noqa: F401


def test_next_match_analysis_reuses_the_rival_scouting_pipeline(seeded) -> None:
    client, user_id, team_id, factory = seeded
    client.cookies.set("htlens_session", create_session_token(user_id))

    async def add_upcoming_match() -> None:
        async with factory() as s:
            players = list((await s.execute(
                select(m.Player)
                .where(m.Player.team_id == team_id, m.Player.left_team_at.is_(None))
                .order_by(m.Player.id)
                .limit(11)
            )).scalars())
            s.add(m.Match(
                ht_match_id=999_001, played_at=datetime.now(UTC) + timedelta(days=2),
                match_type=1, status="UPCOMING",
                home_team_ht_id=OWN_HT_TEAM_ID, away_team_ht_id=RIVAL_HT_TEAM_ID,
                home_team_name="Pulgas Arrechas", away_team_name="etbenianos1",
                source_system="hattrick", orders_given=True,
                submitted_lineup_json=json.dumps([
                    {"ht_player_id": player.ht_player_id, "role_id": 100 + index, "behaviour": 0}
                    for index, player in enumerate(players)
                ]),
                submitted_tactic_type=2, submitted_tactic_skill=19,
                submitted_rating_midfield=18,
                submitted_rating_right_def=70, submitted_rating_central_def=90,
                submitted_rating_left_def=65, submitted_rating_right_att=28,
                submitted_rating_central_att=32, submitted_rating_left_att=56,
            ))
            await s.commit()

    asyncio.run(add_upcoming_match())

    with patch("app.api.v1.endpoints.next_match.CHPPClient", lambda *_a, **_kw: FakeCHPP()):
        resp = client.get(f"/api/v1/teams/{team_id}/next-match/analysis")

    assert resp.status_code == 200
    body = resp.json()
    assert body["match"]["rivalHtTeamId"] == RIVAL_HT_TEAM_ID
    assert body["rival"]["name"] == "etbenianos1"
    # Nombre real vía matchlineup, TSI real vía players.xml — el mismo
    # fixture que usa la ficha completa: confirma que comparte el pipeline.
    assert body["rival"]["matchesAnalysed"] > 0
    assert len(body["rival"]["probableLineup"]) > 0
    assert body["own"]["conditionSource"] == "submitted_orders"
    assert body["own"]["condition"]["players"] == 11
    assert len(body["own"]["submittedOrders"]["lineup"]) == 11
    assert body["own"]["submittedOrders"]["tacticSkill"] == 19
    assert body["own"]["submittedOrders"]["ratings"]["centralDef"] == 90


def test_next_match_analysis_without_an_upcoming_match_says_so(seeded) -> None:
    client, user_id, team_id, _factory = seeded
    client.cookies.set("htlens_session", create_session_token(user_id))

    with patch("app.api.v1.endpoints.next_match.CHPPClient", lambda *_a, **_kw: FakeCHPP()):
        resp = client.get(f"/api/v1/teams/{team_id}/next-match/analysis")

    assert resp.status_code == 200
    body = resp.json()
    assert body["match"] is None
    assert "sync" in body["message"].lower()
