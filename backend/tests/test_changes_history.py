import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.queries.changes_history import build_changes_history
from app.infrastructure.db import models as m


def _snapshot(sync_id: int, player_id: int, captured_at: datetime, **updates):
    values = {
        "sync_id": sync_id,
        "player_id": player_id,
        "captured_at": captured_at,
        "age_years": 25,
        "age_days": 0,
        "tsi": 10_000,
        "form": 5,
        "stamina": 7,
        "experience": 4,
        "salary": 5_000,
        "keeper": 1,
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


def test_changes_history_uses_all_real_snapshot_deltas_and_selected_series() -> None:
    async def scenario() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        now = datetime.now(UTC)
        async with factory() as session:
            team = m.Team(ht_team_id=1, name="Equipo")
            session.add(team)
            await session.flush()
            player = m.Player(
                ht_player_id=11, team_id=team.id, first_name="Ana", last_name="Prueba"
            )
            session.add(player)
            await session.flush()

            first = m.Sync(user_id=1, team_id=team.id, kind="players", status="completed", started_at=now, finished_at=now)
            second_time = now + timedelta(days=7)
            second = m.Sync(user_id=1, team_id=team.id, kind="players", status="completed", started_at=second_time, finished_at=second_time)
            session.add_all([first, second])
            await session.flush()
            session.add_all(
                [
                    _snapshot(first.id, player.id, now),
                    _snapshot(second.id, player.id, second_time, passing=7, experience=5, form=6),
                ]
            )
            await session.commit()

            result = await build_changes_history(session, team.id, player.ht_player_id)

        assert result["selectedPlayerId"] == player.ht_player_id
        assert len(result["series"]) == 2
        assert [(event["key"], event["delta"]) for event in result["skillChanges"]] == [("passing", 1)]
        assert [(event["key"], event["delta"]) for event in result["experienceChanges"]] == [("experience", 1)]
        assert [(event["key"], event["delta"]) for event in result["formChanges"]] == [("form", 1)]
        await engine.dispose()

    asyncio.run(scenario())


def test_changes_history_uses_only_the_last_snapshot_of_each_iso_week() -> None:
    async def scenario() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        # Monday makes the boundary unambiguous: the 27th, 28th and 29th are
        # one ISO week; the following Monday is its next weekly close.
        monday = datetime(2026, 7, 27, 9, tzinfo=UTC)
        async with factory() as session:
            team = m.Team(ht_team_id=1, name="Equipo")
            session.add(team)
            await session.flush()
            player = m.Player(ht_player_id=11, team_id=team.id, first_name="Ana", last_name="Prueba")
            session.add(player)
            await session.flush()
            syncs = []
            for offset in (0, 1, 2, 7):
                at = monday + timedelta(days=offset)
                sync = m.Sync(user_id=1, team_id=team.id, kind="players", status="completed", started_at=at, finished_at=at)
                session.add(sync)
                await session.flush()
                syncs.append(sync)
            session.add_all([
                _snapshot(syncs[0].id, player.id, monday, passing=5),
                _snapshot(syncs[1].id, player.id, monday + timedelta(days=1), passing=6),
                _snapshot(syncs[2].id, player.id, monday + timedelta(days=2), passing=7),
                _snapshot(syncs[3].id, player.id, monday + timedelta(days=7), passing=8),
            ])
            await session.commit()
            result = await build_changes_history(session, team.id, player.ht_player_id)

        # Week 31 closes at 7; week 32 closes at 8. The intra-week 5→6 and
        # 6→7 transitions remain auditable in storage but are not UI diffs.
        assert [(event["before"], event["current"], event["delta"])
                for event in result["skillChanges"] if event["key"] == "passing"] == [(7, 8, 1)]
        assert [point["tsi"] for point in result["series"]] == [10_000, 10_000]
        await engine.dispose()

    asyncio.run(scenario())
