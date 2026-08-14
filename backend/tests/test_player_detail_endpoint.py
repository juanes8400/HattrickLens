"""GET /teams/{id}/players/{ht_player_id} — ficha de jugador.

No hay test HTTP previo para este endpoint (solo se probaban los motores por
separado); este cubre el campo nuevo `salaryEstimate` end-to-end, sobre la
plantilla real de Pulgas Arrechas.
"""
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.domain.engines.loyalty_engine import loyalty_decimal
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.main import app
from tests.conftest import seeded_session

PLAYER_HT_ID = 468921494  # DefenderSkill 4, SetPiecesSkill 9 en el fixture real
KEEPER_HT_ID = 476719421  # KeeperSkill 15 en el fixture real


def _client(*, purchased_days_ago: int | None = None) -> tuple[TestClient, int]:
    import asyncio

    factory, team_id = asyncio.run(seeded_session())

    if purchased_days_ago is not None:
        async def set_purchase_date() -> None:
            async with factory() as s:
                player = await s.scalar(
                    select(m.Player).where(m.Player.ht_player_id == PLAYER_HT_ID)
                )
                assert player is not None
                player.purchased_at = datetime.now(UTC) - timedelta(days=purchased_days_ago)
                await s.commit()

        asyncio.run(set_purchase_date())

    async def override_get_session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app), team_id


def test_player_detail_includes_a_salary_estimate() -> None:
    client, team_id = _client()
    try:
        resp = client.get(f"/api/v1/teams/{team_id}/players/{PLAYER_HT_ID}")
        assert resp.status_code == 200
        body = resp.json()

        est = body["salaryEstimate"]
        assert est["weeklySalary"] > 0
        assert est["mainSkill"] in {
            "defending", "playmaking", "passing", "winger", "scoring",
        }
        assert "no oficial de CHPP" in est["confidence"]
        # El sueldo real (de CHPP) sigue siendo el que se muestra arriba, la
        # estimación no lo reemplaza.
        assert body["salary"] > 0
    finally:
        app.dependency_overrides.clear()


def test_player_detail_omits_salary_estimate_for_goalkeepers() -> None:
    """El manual no publica la fórmula de sueldo de Arquero — devolver algo
    aquí sería inventar un número, así que el campo va en null."""
    client, team_id = _client()
    try:
        resp = client.get(f"/api/v1/teams/{team_id}/players/{KEEPER_HT_ID}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["positions"][0]["position"] == "keeper"
        assert body["salaryEstimate"] is None
    finally:
        app.dependency_overrides.clear()


def test_player_detail_projects_salary_after_the_next_pop_when_trainable() -> None:
    client, team_id = _client()
    try:
        resp = client.get(f"/api/v1/teams/{team_id}/players/{PLAYER_HT_ID}")
        body = resp.json()
        est = body["salaryEstimate"]
        if body["training"]["trainedSkill"] in {
            "defending", "playmaking", "passing", "winger", "scoring",
        }:
            assert est["afterNextPop"] is not None
            assert est["afterNextPop"] >= est["weeklySalary"]
    finally:
        app.dependency_overrides.clear()


def test_player_detail_loyalty_decimal_uses_purchase_date_formula() -> None:
    """El decimal depende únicamente de hoy menos la fecha de compra."""
    client, team_id = _client(purchased_days_ago=91)
    try:
        resp = client.get(f"/api/v1/teams/{team_id}/players/{PLAYER_HT_ID}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["purchasedAt"] is not None
        purchased = datetime.fromisoformat(body["purchasedAt"]).date()
        days = max((datetime.now(UTC).date() - purchased).days, 0)
        assert body["loyaltyDecimal"] == loyalty_decimal(days)
    finally:
        app.dependency_overrides.clear()


def test_player_detail_stamina_forecast_shape_when_present() -> None:
    """`staminaForecast` es `None` sin WorldContext propio (no hay forma de
    etiquetar semanas futuras); cuando existe, sus tres listas/campos deben
    venir bien formados y del mismo tamaño."""
    client, team_id = _client()
    try:
        resp = client.get(f"/api/v1/teams/{team_id}/players/{PLAYER_HT_ID}")
        assert resp.status_code == 200
        forecast = resp.json()["staminaForecast"]
        if forecast is not None:
            assert len(forecast["seasonWeeks"]) == len(forecast["levels"])
            assert all(3 <= lvl <= 9 for lvl in forecast["levels"])
            assert isinstance(forecast["trainingPct"], (int, float))
    finally:
        app.dependency_overrides.clear()
