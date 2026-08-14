import asyncio
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


def _training(sync_id: int, team_id: int, captured_at: datetime, morale: int):
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
        self_confidence=5,
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


def test_report_keeps_last_meaningful_comparison_and_aggregates_real_snapshots() -> None:
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

        assert report["syncId"] == repeated_sync.id
        assert report["changes"] == []
        assert report["reportSyncId"] == changed_sync.id
        assert report["reportIsLatest"] is False
        assert report["playerRows"][0]["tsiDelta"] == 1_000
        assert {c["key"] for c in report["playerRows"][0]["changes"]} == {
            "form",
            "playmaking",
        }
        metrics = {metric["key"]: metric for metric in report["summary"]}
        assert metrics["tsi"]["upCount"] == 1
        assert metrics["tsi"]["upTotal"] == 1_000
        assert metrics["playmaking"]["net"] == 1
        club = {change["key"]: change for change in report["clubChanges"]}
        assert club["team_spirit"]["before"] == 7
        assert club["team_spirit"]["current"] == 6
        assert club["fan_club_size"]["delta"] == 1
        await engine.dispose()

    asyncio.run(scenario())


def test_player_report_converts_salary_from_base_currency_to_local() -> None:
    """CHPP siempre da salario en la moneda base del juego, no en la local
    (Colombia = tasa 10). El reporte debe dividir por la tasa del equipo,
    igual que ya hace squad.py — si no, el salario se ve 10x inflado."""
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
                ht_player_id=123, team_id=team.id, first_name="Jugador", last_name="Prueba",
            )
            session.add(player)
            await session.flush()

            old_sync = m.Sync(
                user_id=1, team_id=team.id, kind="players", status="completed",
                started_at=now, finished_at=now,
            )
            session.add(old_sync)
            await session.flush()
            session.add(_player_snapshot(old_sync.id, player.id, now, salary=100_000))

            changed_at = now + timedelta(days=7)
            changed_sync = m.Sync(
                user_id=1, team_id=team.id, kind="players", status="completed",
                started_at=changed_at, finished_at=changed_at,
            )
            session.add(changed_sync)
            await session.flush()
            session.add(
                _player_snapshot(changed_sync.id, player.id, changed_at, salary=150_000)
            )
            await session.commit()

            report = await build_sync_comparison(session, team.id)

        row = report["playerRows"][0]
        assert row["salary"] == 15_000
        assert row["salaryDelta"] == 5_000
        summary = {metric["key"]: metric for metric in report["summary"]}
        assert summary["salary"]["net"] == 5_000
        await engine.dispose()

    asyncio.run(scenario())
