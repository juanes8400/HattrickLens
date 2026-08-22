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


def test_attempts_that_missed_their_closing_moment_get_repaired() -> None:
    """La regla normal de cierre se dispara en la TRANSICIÓN: estaba listado, ya
    no lo está. Los intentos anteriores a esa regla se perdieron ese instante y
    quedaban abiertos para siempre — en la cuenta del usuario, 15 figuraban "en
    el mercado" cuando solo 4 jugadores lo estaban.

    La reparación cierra cada uno con lo mejor que se sepa, sin inventar fechas.
    """
    from app.application.commands.sync_team import SyncTeamHandler
    from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

    async def run() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://", poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        async with factory() as s:
            equipo = m.Team(ht_team_id=537758, name="Pulgas Arrechas")
            s.add(equipo)
            await s.flush()
            vendido = m.Player(
                ht_player_id=1, team_id=equipo.id, first_name="Se", last_name="Vendio",
                sold_at=datetime(2026, 7, 5), sale_price=500000,
                left_team_at=datetime(2026, 7, 5),
            )
            relistado = m.Player(
                ht_player_id=2, team_id=equipo.id, first_name="Se", last_name="Quedo",
            )
            s.add_all([vendido, relistado])
            await s.flush()
            # La salida buena es la de SU etapa: un jugador que se vendió y
            # volvió tiene una venta vieja en su ficha que no tiene nada que
            # ver con el intento que se está cerrando.
            s.add(m.PlayerStint(
                player_id=vendido.id, ht_player_id=1, team_id=equipo.id,
                arrived_at=datetime(2026, 1, 1), arrival_price=100000,
                left_at=datetime(2026, 7, 5), sale_price=500000,
            ))
            s.add_all([
                # Salió al mercado y acabó vendido.
                m.PlayerListingAttempt(
                    player_id=vendido.id, ht_player_id=1,
                    detected_at=datetime(2026, 6, 30),
                ),
                # Dos intentos del mismo: el primero tuvo que acabar antes del
                # segundo.
                m.PlayerListingAttempt(
                    player_id=relistado.id, ht_player_id=2,
                    detected_at=datetime(2026, 8, 1),
                ),
                m.PlayerListingAttempt(
                    player_id=relistado.id, ht_player_id=2,
                    detected_at=datetime(2026, 8, 10),
                ),
            ])
            await s.commit()
            team_id = equipo.id

        uow = SqlAlchemyUnitOfWork(factory)
        handler = SyncTeamHandler(uow, None)  # type: ignore[arg-type]
        async with uow as u:
            cerrados = await handler._reparar_intentos_abiertos(u, team_id, set())
            await u.commit()
        assert cerrados == 3

        async with factory() as s:
            intentos = (await s.execute(
                select(m.PlayerListingAttempt).order_by(m.PlayerListingAttempt.detected_at)
            )).scalars().all()
            # El que se vendió cierra el día de la venta, y como vendido.
            assert intentos[0].ended_at == datetime(2026, 7, 5)
            assert intentos[0].sold is True
            # El primero del otro cierra cuando volvió a salir al mercado.
            assert intentos[1].ended_at == datetime(2026, 8, 10)
            assert intentos[1].sold is False
            # Y el último, con lo único seguro: hoy ya no está listado.
            assert intentos[2].ended_at is not None
            assert intentos[2].sold is False
            # El plazo real nunca se vio: no se inventa.
            assert all(i.deadline is None for i in intentos)

    asyncio.run(run())


def test_a_player_still_listed_today_is_left_alone() -> None:
    """La reparación no puede cerrar una puja que sigue viva."""
    from app.application.commands.sync_team import SyncTeamHandler
    from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

    async def run() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://", poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)
        async with factory() as s:
            equipo = m.Team(ht_team_id=537758, name="Pulgas Arrechas")
            s.add(equipo)
            await s.flush()
            jugador = m.Player(
                ht_player_id=7, team_id=equipo.id, first_name="En", last_name="Venta",
            )
            s.add(jugador)
            await s.flush()
            s.add(m.PlayerListingAttempt(
                player_id=jugador.id, ht_player_id=7, detected_at=datetime(2026, 8, 20),
            ))
            await s.commit()
            team_id = equipo.id

        uow = SqlAlchemyUnitOfWork(factory)
        handler = SyncTeamHandler(uow, None)  # type: ignore[arg-type]
        async with uow as u:
            cerrados = await handler._reparar_intentos_abiertos(u, team_id, {7})
            await u.commit()
        assert cerrados == 0

        async with factory() as s:
            intento = await s.scalar(select(m.PlayerListingAttempt))
            assert intento.ended_at is None

    asyncio.run(run())
