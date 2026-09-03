"""Contrato HTTP del optimizador de alineacion.

La seleccion matematica se prueba en ``test_lineup_optimizer.py``. Aqui se
comprueba que la API conserva la orden elegida y que una plantilla corta es
un estado representable, no una excepcion que tumba la pagina.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.api.v1.endpoints import analysis as analysis_endpoint
from app.infrastructure.chpp.parsers import parse_players
from app.infrastructure.db.session import get_session
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures"
ROSTER = parse_players((FIXTURES / "players.xml").read_bytes())["players"]


@contextmanager
def _client_with_roster(
    monkeypatch: MonkeyPatch,
    players: list[dict[str, Any]],
) -> Iterator[TestClient]:
    async def fake_roster(
        _session: object,
        _team_id: int,
    ) -> tuple[list[dict[str, Any]], object]:
        named_players = [
            {
                **player,
                "name": f"{player.get('first_name', '')} {player.get('last_name', '')}".strip(),
            }
            for player in players
        ]
        return named_players, object()

    async def no_session() -> AsyncIterator[None]:
        yield None

    monkeypatch.setattr(analysis_endpoint, "roster", fake_roster)
    app.dependency_overrides[get_session] = no_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_lineup_response_exposes_the_recommended_behaviour_and_objective(
    monkeypatch: MonkeyPatch,
) -> None:
    with _client_with_roster(monkeypatch, deepcopy(ROSTER)) as client:
        response = client.get("/api/v1/teams/1/lineup?formation=4-4-2")

    assert response.status_code == 200
    body = response.json()
    assert body["warning"] is None
    assert body["availableCount"] == len(ROSTER)
    assert body["requiredCount"] == 11
    assert body["optimizationObjective"] == {
        "key": "max_total_positional_contribution",
        "label": "Maximizar la suma del índice de aporte posicional",
        "value": body["totalRating"],
    }

    assert len(body["lineup"]) == 11
    assert all("behaviour" in assignment for assignment in body["lineup"])
    assert all("behaviourLabel" in assignment for assignment in body["lineup"])
    assert {assignment["behaviour"] for assignment in body["lineup"]} >= {
        "normal",
        "offensive",
        "defensive",
    }


def test_a_roster_under_eleven_returns_an_empty_structured_result(
    monkeypatch: MonkeyPatch,
) -> None:
    with _client_with_roster(monkeypatch, deepcopy(ROSTER[:10])) as client:
        response = client.get("/api/v1/teams/1/lineup?formation=3-5-2")

    assert response.status_code == 200
    body = response.json()
    assert body["formation"] == "3-5-2"
    assert body["availableCount"] == 10
    assert body["requiredCount"] == 11
    assert "10 jugadores disponibles" in body["warning"]
    assert body["lineup"] == []
    assert body["bench"] == []
    assert body["formationRanking"] == {}
    assert body["totalRating"] == 0
    assert body["optimizationObjective"]["value"] == 0
    assert len(body["sectorRatings"]["ratings"]) == 5
    assert all(item["value"] == 0 for item in body["sectorRatings"]["ratings"])
    assert all(
        item["topContributors"] == [] for item in body["sectorRatings"]["ratings"]
    )


def test_injuries_are_included_in_the_available_count_before_optimizing(
    monkeypatch: MonkeyPatch,
) -> None:
    players = deepcopy(ROSTER[:11])
    players[-1]["injury_level"] = 1

    with _client_with_roster(monkeypatch, players) as client:
        response = client.get("/api/v1/teams/1/lineup")

    assert response.status_code == 200
    assert response.json()["availableCount"] == 10
    assert response.json()["lineup"] == []


def test_excluding_a_player_down_to_ten_is_also_non_exceptional(
    monkeypatch: MonkeyPatch,
) -> None:
    players = deepcopy(ROSTER[:11])
    excluded_id = players[0]["ht_player_id"]

    with _client_with_roster(monkeypatch, players) as client:
        response = client.get(f"/api/v1/teams/1/lineup?exclude={excluded_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["availableCount"] == 10
    assert body["requiredCount"] == 11
    assert body["lineup"] == []
