import asyncio
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.queries.sync_comparison import build_sync_comparison
from app.infrastructure.db import models as m


def _player_snapshot(sync_id: int, player_id: int, captured_at: datetime, **updates):
    values = {
        "sync_id": sync_id,
        "player_id": player_id,
        "captured_at": captured_at,
        "age_years": 24,
        "age_days": 10,
        "tsi": 10_000,
        "form": 5,
        "stamina": 7,
        "experience": 4,
        "loyalty": 5,
        "salary": 50_000,
        "keeper": 2,
        "defending": 6,
        "playmaking": 7,
        "winger": 5,
        "passing": 6,
        "scoring": 4,
        "set_pieces": 3,
        "content_hash": bytes([sync_id]) * 32,
    }
    values.update(updates)
    return m.PlayerSnapshot(**values)


def _training(
    sync_id: int,
    team_id: int,
    captured_at: datetime,
    morale: int,
    confidence: int = 5,
):
    return m.TrainingSnapshot(
        sync_id=sync_id,
        team_id=team_id,
        captured_at=captured_at,
        training_type=8,
        training_level=100,
        new_training_level=100,
        stamina_part=15,
        last_training_type=8,
        last_training_level=100,
        last_stamina_part=15,
        trainer_ht_id=1,
        trainer_name="Entrenador",
        morale=morale,
        self_confidence=confidence,
        content_hash=bytes([sync_id]) * 32,
    )


def _economy(sync_id: int, team_id: int, captured_at: datetime, fans: int):
    return m.EconomySnapshot(
        sync_id=sync_id,
        team_id=team_id,
        captured_at=captured_at,
        cash=1_000_000,
        expected_cash=1_100_000,
        sponsors_popularity=0,
        supporters_popularity=9,
        fan_club_size=fans,
        income_spectators=0,
        income_sponsors=0,
        income_financial=0,
        income_temporary=0,
        income_sum=0,
        costs_arena=0,
        costs_players=0,
        costs_financial=0,
        costs_staff=0,
        costs_temporary=0,
        costs_youth=0,
        costs_sum=0,
        expected_weeks_total=0,
        last_income_sum=0,
        last_costs_sum=0,
        last_weeks_total=0,
        content_hash=bytes([sync_id]) * 32,
    )


def test_un_sync_repetido_no_reensena_el_informe_anterior() -> None:
    async def scenario() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        now = datetime.now(UTC)
        async with factory() as session:
            team = m.Team(ht_team_id=537758, name="Pulgas Arrechas")
            session.add(team)
            await session.flush()
            player = m.Player(
                ht_player_id=123,
                team_id=team.id,
                first_name="Jugador",
                last_name="Prueba",
            )
            session.add(player)
            await session.flush()

            old_sync = m.Sync(
                user_id=1,
                team_id=team.id,
                kind="players,training,economy",
                status="completed",
                started_at=now,
                finished_at=now,
            )
            session.add(old_sync)
            await session.flush()
            session.add_all(
                [
                    _player_snapshot(old_sync.id, player.id, now),
                    _training(old_sync.id, team.id, now, morale=7),
                    _economy(old_sync.id, team.id, now, fans=2_408),
                ]
            )

            # La comparación de snapshots es semanal: el cambio debe ocurrir
            # en la semana siguiente para ser un diff visible.
            changed_at = now + timedelta(days=7)
            changed_sync = m.Sync(
                user_id=1,
                team_id=team.id,
                kind="players,training,economy",
                status="completed",
                started_at=changed_at,
                finished_at=changed_at,
            )
            session.add(changed_sync)
            await session.flush()
            session.add_all(
                [
                    _player_snapshot(
                        changed_sync.id,
                        player.id,
                        changed_at,
                        tsi=11_000,
                        form=6,
                        playmaking=8,
                        loyalty=6,
                    ),
                    _training(changed_sync.id, team.id, changed_at, morale=6),
                    _economy(changed_sync.id, team.id, changed_at, fans=2_409),
                    m.SyncChange(
                        sync_id=changed_sync.id,
                        team_id=team.id,
                        category="jugadores",
                        summary="Jugador Prueba: Jugadas subió de 7 a 8",
                        created_at=changed_at,
                    ),
                    # Formato defectuoso que dejaron versiones anteriores:
                    # la consulta debe reconstruirlo desde los snapshots.
                    m.SyncChange(
                        sync_id=changed_sync.id,
                        team_id=team.id,
                        category="entrenamiento",
                        summary="Espíritu del equipo: -1 -> Contentos",
                        created_at=changed_at,
                    ),
                    m.SyncChange(
                        sync_id=changed_sync.id,
                        team_id=team.id,
                        category="entrenamiento",
                        summary="Confianza: -1 -> Sólida",
                        created_at=changed_at,
                    ),
                ]
            )

            repeated_at = changed_at + timedelta(hours=2)
            repeated_sync = m.Sync(
                user_id=1,
                team_id=team.id,
                kind="players,training,economy",
                status="completed",
                started_at=repeated_at,
                finished_at=repeated_at,
            )
            session.add(repeated_sync)
            await session.flush()
            session.add(
                m.Sync(
                    user_id=1,
                    team_id=team.id,
                    kind="playerdetails:123",
                    status="completed",
                    started_at=repeated_at + timedelta(minutes=1),
                    finished_at=repeated_at + timedelta(minutes=1),
                )
            )
            await session.commit()

            report = await build_sync_comparison(session, team.id)
            # Navegación por fecha (2026-08-15): pedir explícitamente el sync
            # con cambios devuelve esa comparación; pedir uno inexistente o
            # sin cambios cae al último, no revienta.
            picked = await build_sync_comparison(session, team.id, changed_sync.id)
            fallback_repeated = await build_sync_comparison(session, team.id, repeated_sync.id)
            fallback_unknown = await build_sync_comparison(session, team.id, 999_999)

        # Sólo los syncs que movieron algo entran en el selector: el repetido
        # (que confirmó que todo seguía igual) sería ruido.
        assert [r["syncId"] for r in report["availableReports"]] == [changed_sync.id]
        assert report["availableReports"][0]["changeCount"] == 3

        # 2026-08-24: "la vida de las notificaciones es ÚNICA". El sync
        # repetido no movió nada, así que NO reenseña el informe anterior:
        # se queda vacío. Lo que fue, fue.
        assert report["syncId"] == repeated_sync.id
        assert report["reportSyncId"] == repeated_sync.id
        assert report["reportIsLatest"] is True
        assert report["changes"] == []
        assert report["reportChanges"] == []
        assert report["playerRows"] == []
        # `clubChanges` es el estado del club, no una lista de cambios: sigue
        # ahi, pero sin movimiento entre el antes y el ahora.
        assert all(c["before"] == c["current"] for c in report["clubChanges"])
        assert fallback_repeated["reportSyncId"] == repeated_sync.id
        assert fallback_unknown["reportSyncId"] == repeated_sync.id

        # Pero el archivo sigue ahí: pedir esa fecha devuelve lo suyo entero.
        assert picked["reportSyncId"] == changed_sync.id
        assert picked["reportIsLatest"] is False
        assert {
            item["summary"]
            for item in picked["reportChanges"]
            if item["category"] == "entrenamiento"
        } == {"Espíritu del equipo: Encantados -> Contentos"}
        assert picked["playerRows"][0]["tsiDelta"] == 1_000
        assert {c["key"] for c in picked["playerRows"][0]["changes"]} == {
            "form",
            "loyalty",
            "playmaking",
        }
        metrics = {metric["key"]: metric for metric in picked["summary"]}
        assert metrics["tsi"]["upCount"] == 1
        assert metrics["tsi"]["upTotal"] == 1_000
        assert metrics["playmaking"]["net"] == 1
        assert metrics["loyalty"]["net"] == 1
        club = {change["key"]: change for change in picked["clubChanges"]}
        assert club["team_spirit"]["before"] == 7
        assert club["team_spirit"]["current"] == 6
        assert club["fan_club_size"]["delta"] == 1
        await engine.dispose()

    asyncio.run(scenario())


def test_historical_report_ignores_each_placeholder_and_same_time_future_rows() -> None:
    async def scenario() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        initial_at = datetime.now(UTC) - timedelta(days=7)
        changed_at = initial_at + timedelta(days=7)
        async with factory() as session:
            team = m.Team(ht_team_id=537758, name="Pulgas Arrechas")
            session.add(team)
            await session.flush()

            initial = m.Sync(
                user_id=1,
                team_id=team.id,
                kind="players,training",
                status="completed",
                started_at=initial_at,
                finished_at=initial_at,
            )
            session.add(initial)
            await session.flush()
            session.add(_training(initial.id, team.id, initial_at, morale=7, confidence=5))

            target = m.Sync(
                user_id=1,
                team_id=team.id,
                kind="players,training",
                status="completed",
                started_at=changed_at,
                finished_at=changed_at,
            )
            session.add(target)
            await session.flush()
            session.add_all(
                [
                    _training(target.id, team.id, changed_at, morale=-1, confidence=6),
                    m.SyncChange(
                        sync_id=target.id,
                        team_id=team.id,
                        category="entrenamiento",
                        summary="Confianza: -1 -> Alta",
                        created_at=changed_at,
                    ),
                ]
            )

            # Una captura posterior con la misma hora no puede filtrarse hacia
            # atrás en el informe seleccionado. El ID desambigua el instante.
            later = m.Sync(
                user_id=1,
                team_id=team.id,
                kind="training",
                status="completed",
                started_at=changed_at,
                finished_at=changed_at,
            )
            session.add(later)
            await session.flush()
            session.add(_training(later.id, team.id, changed_at, morale=4, confidence=-1))
            await session.commit()

            report = await build_sync_comparison(session, team.id, target.id)

        training_changes = [
            item for item in report["reportChanges"] if item["category"] == "entrenamiento"
        ]
        assert [item["summary"] for item in training_changes] == ["Confianza: Sólida -> Alta"]
        assert all(
            item["detail"].get(key) != -1
            for item in training_changes
            for key in ("before", "after")
        )
        club = {item["key"]: item for item in report["clubChanges"]}
        assert club["team_spirit"]["current"] == 7
        assert club["self_confidence"]["current"] == 6
        await engine.dispose()

    asyncio.run(scenario())


def test_player_report_converts_salary_from_base_currency_to_local() -> None:
    """CHPP siempre da salario en la moneda base del juego, no en la local
    (Colombia = tasa 10). El reporte debe dividir por la tasa del equipo,
    igual que ya hace squad.py, si no, el salario se ve 10x inflado."""

    async def scenario() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        now = datetime.now(UTC)
        async with factory() as session:
            team = m.Team(ht_team_id=537758, name="Pulgas Arrechas", currency_rate=10.0)
            session.add(team)
            await session.flush()
            player = m.Player(
                ht_player_id=123,
                team_id=team.id,
                first_name="Jugador",
                last_name="Prueba",
            )
            session.add(player)
            await session.flush()

            old_sync = m.Sync(
                user_id=1,
                team_id=team.id,
                kind="players",
                status="completed",
                started_at=now,
                finished_at=now,
            )
            session.add(old_sync)
            await session.flush()
            session.add(_player_snapshot(old_sync.id, player.id, now, salary=100_000))

            changed_at = now + timedelta(days=7)
            changed_sync = m.Sync(
                user_id=1,
                team_id=team.id,
                kind="players",
                status="completed",
                started_at=changed_at,
                finished_at=changed_at,
            )
            session.add(changed_sync)
            await session.flush()
            session.add(_player_snapshot(changed_sync.id, player.id, changed_at, salary=150_000))
            await session.commit()

            report = await build_sync_comparison(session, team.id)

        row = report["playerRows"][0]
        assert row["salary"] == 15_000
        assert row["salaryDelta"] == 5_000
        summary = {metric["key"]: metric for metric in report["summary"]}
        assert summary["salary"]["net"] == 5_000
        await engine.dispose()

    asyncio.run(scenario())


def test_una_venta_llega_con_su_ingreso_su_gasto_y_su_roi() -> None:
    """2026-09-09, pedido del usuario: «cuando un jugador se vende en Cambios
    dice Cambio, debe decir venta y reportar Ingresos, Gastos y ROI».

    La etiqueta ya venía bien del servidor --era la pantalla la que la
    ignoraba-- pero las tres cifras no venían. Salen de la MISMA fuente que
    Transferencias, así que aquí se comprueba que llegan y que cuadran entre
    ellas: ingresos - gastos = saldo. Si algún día alguien recalcula alguna
    por su cuenta, esa resta deja de dar.
    """

    async def scenario() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        now = datetime.now(UTC)
        comprado = now - timedelta(days=30)
        async with factory() as session:
            team = m.Team(ht_team_id=537758, name="Pulgas Arrechas", currency_rate=1.0)
            session.add(team)
            await session.flush()
            vendido = m.Player(
                ht_player_id=777,
                team_id=team.id,
                first_name="Vendido",
                last_name="Deprueba",
                purchase_price=100_000,
                purchased_at=comprado,
                sale_price=200_000,
                sold_at=now,
                left_team_at=now,
            )
            session.add(vendido)
            await session.flush()

            sync = m.Sync(
                user_id=1,
                team_id=team.id,
                kind="players",
                status="completed",
                started_at=now,
                finished_at=now,
            )
            session.add(sync)
            await session.flush()
            session.add(
                m.SyncChange(
                    sync_id=sync.id,
                    team_id=team.id,
                    category="jugadores",
                    summary="Vendido Deprueba se vendió por 200.000 US$",
                    detail_json=json.dumps(
                        {
                            "metric": "sale",
                            "label": "Venta",
                            "subject": "Vendido Deprueba",
                            "after": 200_000,
                            "kind": "money",
                            "currency": "US$",
                            "htPlayerId": 777,
                        }
                    ),
                    created_at=now,
                )
            )
            await session.commit()

        async with factory() as session:
            data = await build_sync_comparison(session, 1)

        venta = next(c for c in data["changes"] if (c.get("detail") or {}).get("metric") == "sale")
        # La etiqueta, que es lo primero que el usuario vio mal.
        assert venta["detail"]["label"] == "Venta"

        economia = venta["economia"]
        # Ingresos NETOS: 200.000 menos la comisión del agente, así que menos
        # que el precio. Es justo lo que el precio a secas no contaba.
        assert 0 < economia["ingresos"] < 200_000
        assert economia["gastos"] >= 100_000  # la compra, más el sueldo
        # Las tres cifras cuadran entre sí, que es la garantía que importa.
        assert round(economia["ingresos"] - economia["gastos"], 2) == round(economia["saldo"], 2)
        assert economia["roiPct"] == round(economia["saldo"] / economia["gastos"] * 100, 2)

    asyncio.run(scenario())


def test_un_cambio_que_no_es_venta_no_arrastra_economia() -> None:
    """La consulta de saldos sólo se paga cuando hay una venta en el informe,
    y nada más lleva el bloque económico colgando."""

    async def scenario() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        now = datetime.now(UTC)
        async with factory() as session:
            team = m.Team(ht_team_id=537758, name="Pulgas Arrechas", currency_rate=1.0)
            session.add(team)
            await session.flush()
            sync = m.Sync(
                user_id=1,
                team_id=team.id,
                kind="players",
                status="completed",
                started_at=now,
                finished_at=now,
            )
            session.add(sync)
            await session.flush()
            session.add(
                m.SyncChange(
                    sync_id=sync.id,
                    team_id=team.id,
                    category="jugadores",
                    summary="Alguien: TSI 100 -> 200",
                    detail_json=json.dumps(
                        {"metric": "tsi", "label": "TSI", "before": 100, "after": 200}
                    ),
                    created_at=now,
                )
            )
            await session.commit()

        async with factory() as session:
            data = await build_sync_comparison(session, 1)

        assert all("economia" not in c for c in data["changes"])

    asyncio.run(scenario())
