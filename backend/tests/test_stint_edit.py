"""Atribuir a mano lo que Hattrick ya no da, o sacar una etapa de las cuentas.

2026-08-22, pedido por el usuario. De un jugador que se fue hace temporadas no
queda ni qué entrenaba, ni cuál era su mejor habilidad, ni su edad: son
justamente los tres cortes de los desgloses, y con "?" no se puede analizar
nada. La regla que lo hace seguro: lo escrito a mano SOLO rellena huecos.
"""
import asyncio
from datetime import datetime
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import require_team_owner
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.main import app


def _montar() -> tuple[TestClient, int, int, int]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def preparar() -> tuple[int, int, int]:
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)
        async with factory() as s:
            equipo = m.Team(ht_team_id=537758, name="Pulgas Arrechas")
            s.add(equipo)
            await s.flush()
            jugador = m.Player(
                ht_player_id=1, team_id=equipo.id, first_name="Ex", last_name="Jugador",
            )
            s.add(jugador)
            await s.flush()
            cerrada = m.PlayerStint(
                player_id=jugador.id, ht_player_id=1, team_id=equipo.id,
                arrived_at=datetime(2020, 1, 1), arrival_price=1000,
                left_at=datetime(2021, 1, 1), sale_price=5000,
            )
            abierta = m.PlayerStint(
                player_id=jugador.id, ht_player_id=1, team_id=equipo.id,
                arrived_at=datetime(2026, 1, 1), arrival_price=9000,
            )
            s.add_all([cerrada, abierta])
            await s.commit()
            return equipo.id, cerrada.id, abierta.id

    team_id, cerrada_id, abierta_id = asyncio.run(preparar())

    async def sesion() -> Any:
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = sesion
    app.dependency_overrides[require_team_owner] = lambda: None
    return TestClient(app), team_id, cerrada_id, abierta_id


def test_the_three_fields_can_be_attributed_by_hand() -> None:
    client, team_id, cerrada, _ = _montar()
    try:
        r = client.patch(
            f"/api/v1/teams/{team_id}/stints/{cerrada}",
            json={"training_type": 3, "top_skill": "scoring", "age_years": 24,
                  "age_days": 40},
        )
        assert r.status_code == 200, r.text
        assert r.json()["trainingType"] == 3
        assert r.json()["topSkill"] == "scoring"
        assert r.json()["ageYears"] == 24
    finally:
        app.dependency_overrides.clear()


def test_a_stint_still_open_cannot_be_typed_in() -> None:
    """Mientras el jugador esté en la plantilla, sus datos vienen de Hattrick.
    Dejar escribirlos a mano seria abrir la puerta a que un dato inventado
    pisara uno real en la siguiente sincronizacion."""
    client, team_id, _, abierta = _montar()
    try:
        r = client.patch(
            f"/api/v1/teams/{team_id}/stints/{abierta}", json={"age_years": 30}
        )
        assert r.status_code == 409
        assert "sigue abierta" in r.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_a_made_up_skill_is_rejected() -> None:
    client, team_id, cerrada, _ = _montar()
    try:
        r = client.patch(
            f"/api/v1/teams/{team_id}/stints/{cerrada}", json={"top_skill": "carisma"}
        )
        assert r.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_a_stint_of_another_team_is_not_reachable() -> None:
    client, team_id, cerrada, _ = _montar()
    try:
        r = client.patch(f"/api/v1/teams/{team_id + 99}/stints/{cerrada}", json={})
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_excluding_a_stint_takes_it_out_of_the_table() -> None:
    """Excluir es lo que permite al usuario limpiar una media que un dato
    falso o irrepetible estaba ensuciando."""
    from app.application.queries.player_balance import PlayerBalanceQueryService

    client, team_id, cerrada, _ = _montar()
    try:
        antes = client.get(f"/api/v1/teams/{team_id}/player-balance").json()
        assert any(f["stintId"] == cerrada for f in antes["players"])

        r = client.patch(
            f"/api/v1/teams/{team_id}/stints/{cerrada}", json={"excluded": True}
        )
        assert r.status_code == 200 and r.json()["excluded"] is True

        despues = client.get(f"/api/v1/teams/{team_id}/player-balance").json()
        assert not any(f["stintId"] == cerrada for f in despues["players"])
        assert PlayerBalanceQueryService is not None
    finally:
        app.dependency_overrides.clear()
