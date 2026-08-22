"""Cada intento de venta, con su final.

2026-08-22, pedido por el usuario. Antes la app solo contaba cuántas veces se
había listado a alguien; un intento de venta tiene además un plazo, un
resultado y un dato que Hattrick NO entrega por CHPP: cuántas veces miraron al
jugador. Eso solo aparece en el texto de la noticia al cerrarse la puja, así
que lo teclea el usuario.
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
            equipo = m.Team(
                ht_team_id=537758, name="Pulgas Arrechas",
                currency_name="US$", currency_rate=10.0,
            )
            s.add(equipo)
            await s.flush()
            jugador = m.Player(
                ht_player_id=1, team_id=equipo.id,
                first_name="Stănel", last_name="Didoiu",
            )
            s.add(jugador)
            await s.flush()
            terminado = m.PlayerListingAttempt(
                player_id=jugador.id, ht_player_id=1,
                detected_at=datetime(2026, 8, 19, 8, 0),
                deadline=datetime(2026, 8, 22, 8, 1),
                ended_at=datetime(2026, 8, 22, 8, 5),
                sold=False, last_highest_bid=None,
            )
            abierto = m.PlayerListingAttempt(
                player_id=jugador.id, ht_player_id=1,
                detected_at=datetime(2026, 8, 23, 9, 0),
                deadline=datetime(2026, 8, 26, 9, 0),
                last_highest_bid=7230000,
            )
            s.add_all([terminado, abierto])
            await s.commit()
            return equipo.id, terminado.id, abierto.id

    team_id, terminado, abierto = asyncio.run(preparar())

    async def sesion() -> Any:
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = sesion
    app.dependency_overrides[require_team_owner] = lambda: None
    return TestClient(app), team_id, terminado, abierto


def test_each_attempt_is_a_row_with_its_own_ending() -> None:
    client, team_id, terminado, abierto = _montar()
    try:
        cuerpo = client.get(f"/api/v1/teams/{team_id}/transfer-attempts").json()
        assert len(cuerpo["rows"]) == 2

        por_id = {r["id"]: r for r in cuerpo["rows"]}
        assert por_id[terminado]["open"] is False
        assert por_id[terminado]["sold"] is False
        assert por_id[abierto]["open"] is True
        # La puja llega en moneda local, como el resto de la pantalla.
        assert por_id[abierto]["highestBid"] == 723000
    finally:
        app.dependency_overrides.clear()


def test_only_finished_attempts_without_an_answer_are_asked_about() -> None:
    """El aviso es para lo que ya no se puede averiguar de otra forma. Una puja
    todavía abierta no tiene visitas que contar, y una ya respondida tampoco
    debe volver a preguntarse."""
    client, team_id, terminado, abierto = _montar()
    try:
        cuerpo = client.get(f"/api/v1/teams/{team_id}/transfer-attempts").json()
        pendientes = [r["id"] for r in cuerpo["pendingQuestion"]]
        assert pendientes == [terminado]
        assert abierto not in pendientes
    finally:
        app.dependency_overrides.clear()


def test_the_user_can_write_down_the_visits() -> None:
    """Del mensaje real de Hattrick: "este jugador fue visto 8 veces mientras
    estaba en la lista de transferibles"."""
    client, team_id, terminado, _ = _montar()
    try:
        r = client.patch(
            f"/api/v1/teams/{team_id}/transfer-attempts/{terminado}",
            json={"times_seen": 8},
        )
        assert r.status_code == 200
        assert r.json()["timesSeen"] == 8

        cuerpo = client.get(f"/api/v1/teams/{team_id}/transfer-attempts").json()
        assert cuerpo["pendingQuestion"] == []
    finally:
        app.dependency_overrides.clear()


def test_ignoring_the_question_stops_it_from_coming_back() -> None:
    """Se puede no contestar. Lo que no puede pasar es que el aviso vuelva a
    salir en cada visita a Cambios."""
    client, team_id, terminado, _ = _montar()
    try:
        r = client.patch(
            f"/api/v1/teams/{team_id}/transfer-attempts/{terminado}",
            json={"dismissed": True},
        )
        assert r.status_code == 200
        assert r.json()["timesSeen"] is None
        assert r.json()["asked"] is True

        cuerpo = client.get(f"/api/v1/teams/{team_id}/transfer-attempts").json()
        assert cuerpo["pendingQuestion"] == []
    finally:
        app.dependency_overrides.clear()


def test_an_attempt_of_another_team_is_not_reachable() -> None:
    client, team_id, terminado, _ = _montar()
    try:
        r = client.patch(
            f"/api/v1/teams/{team_id + 99}/transfer-attempts/{terminado}",
            json={"times_seen": 3},
        )
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()
