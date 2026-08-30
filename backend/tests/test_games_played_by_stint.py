"""Contrato del censo de partidos jugados con el club, por etapa."""

import asyncio
from datetime import datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.sync_team import SyncTeamHandler
from app.infrastructure.db import models as m
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

TEAM_HT_ID = 537758
PLAYER_HT_ID = 488209001


class FakeCensusCHPP:
    def __init__(
        self,
        archives: dict[tuple[str, str], list[dict[str, Any]]] | None = None,
        lineups: dict[int, list[dict[str, Any]]] | None = None,
        fail_lineups: set[int] | None = None,
    ) -> None:
        self.archives = archives or {}
        self.lineups = lineups or {}
        self.fail_lineups = fail_lineups or set()
        self.archive_calls: list[tuple[str, str]] = []
        self.lineup_calls: list[int] = []

    async def fetch(self, file: str, version: str, **params: Any) -> dict[str, Any]:
        if file == "matchesarchive":
            key = (params["FirstMatchDate"], params["LastMatchDate"])
            self.archive_calls.append(key)
            return {"matches": self.archives.get(key, [])}
        if file == "matchlineup":
            match_id = params["matchID"]
            self.lineup_calls.append(match_id)
            if match_id in self.fail_lineups:
                raise RuntimeError("fallo transitorio de matchlineup")
            return {"players": self.lineups.get(match_id, [])}
        raise AssertionError(f"llamada CHPP inesperada: {file}")


async def _database() -> tuple[Any, int]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        team = m.Team(ht_team_id=TEAM_HT_ID, name="Pulgas Arrechas")
        session.add(team)
        await session.flush()
        team_id = team.id
        await session.commit()
    return factory, team_id


async def _player(
    factory: Any,
    team_id: int,
    *,
    legacy_games: int | None = None,
    legacy_computed: datetime | None = None,
    purchased_at: datetime | None = datetime(2026, 8, 20, 15, 56),
    sold_at: datetime = datetime(2026, 8, 28, 12, 51),
) -> int:
    async with factory() as session:
        player = m.Player(
            team_id=team_id,
            ht_player_id=PLAYER_HT_ID,
            first_name="Jose Vicente",
            last_name="Alvargonzalez",
            purchased_at=purchased_at,
            sold_at=sold_at,
            left_team_at=sold_at,
            games_played_for_us=legacy_games,
            games_played_for_us_computed_at=legacy_computed,
        )
        session.add(player)
        await session.flush()
        player_id = player.id
        await session.commit()
    return player_id


def _entry(stars: float) -> dict[str, Any]:
    return {"ht_player_id": PLAYER_HT_ID, "rating_stars": stars}


def test_pending_census_looks_at_the_closed_stint_not_the_legacy_flag() -> None:
    async def run() -> None:
        factory, team_id = await _database()
        marked = datetime(2026, 8, 28, 14, 38)
        player_id = await _player(
            factory,
            team_id,
            legacy_games=1,
            legacy_computed=marked,
        )
        async with factory() as session:
            session.add(
                m.PlayerStint(
                    player_id=player_id,
                    ht_player_id=PLAYER_HT_ID,
                    team_id=team_id,
                    arrived_at=datetime(2026, 8, 20, 15, 56),
                    left_at=datetime(2026, 8, 28, 12, 51),
                )
            )
            await session.commit()

        uow = SqlAlchemyUnitOfWork(factory)
        handler = SyncTeamHandler(uow, FakeCensusCHPP())
        async with uow:
            pending = await handler.pendientes_de_ficha(uow, team_id)
        assert PLAYER_HT_ID in pending["censo"]

    asyncio.run(run())


@pytest.mark.parametrize("legacy_games", [0, 1])
def test_single_stint_repairs_from_legacy_without_chpp(legacy_games: int) -> None:
    async def run() -> None:
        factory, team_id = await _database()
        marked = datetime(2026, 8, 28, 14, 38)
        player_id = await _player(
            factory,
            team_id,
            legacy_games=legacy_games,
            legacy_computed=marked,
        )
        async with factory() as session:
            stint = m.PlayerStint(
                player_id=player_id,
                ht_player_id=PLAYER_HT_ID,
                team_id=team_id,
                arrived_at=datetime(2026, 8, 20, 15, 56),
                left_at=datetime(2026, 8, 28, 12, 51),
            )
            session.add(stint)
            await session.commit()
            stint_id = stint.id

        chpp = FakeCensusCHPP()
        uow = SqlAlchemyUnitOfWork(factory)
        handler = SyncTeamHandler(uow, chpp)
        async with uow:
            assert await handler._censar_partidos_del_stint(
                uow, team_id, PLAYER_HT_ID
            )
            await uow.commit()

        async with factory() as session:
            stint = await session.get(m.PlayerStint, stint_id)
            assert stint is not None
            assert stint.games_played_for_us == legacy_games
            assert stint.games_computed_at == marked
        assert chpp.archive_calls == []
        assert chpp.lineup_calls == []

    asyncio.run(run())


def test_two_stints_are_counted_in_their_own_windows() -> None:
    async def run() -> None:
        factory, team_id = await _database()
        player_id = await _player(factory, team_id)
        first = (datetime(2025, 1, 1), datetime(2025, 6, 1))
        second = (datetime(2026, 6, 1), datetime(2026, 8, 1))
        async with factory() as session:
            session.add_all(
                [
                    m.PlayerStint(
                        player_id=player_id,
                        ht_player_id=PLAYER_HT_ID,
                        team_id=team_id,
                        arrived_at=first[0],
                        left_at=first[1],
                    ),
                    m.PlayerStint(
                        player_id=player_id,
                        ht_player_id=PLAYER_HT_ID,
                        team_id=team_id,
                        arrived_at=second[0],
                        left_at=second[1],
                    ),
                ]
            )
            await session.commit()

        key1 = ("2025-01-01 00:00:00", "2025-06-01 00:00:00")
        key2 = ("2026-06-01 00:00:00", "2026-08-01 00:00:00")
        chpp = FakeCensusCHPP(
            archives={
                key1: [
                    {"ht_match_id": 1, "match_type": 1},
                    {"ht_match_id": 2, "match_type": 4},
                ],
                key2: [
                    {"ht_match_id": 3, "match_type": 1},
                    {"ht_match_id": 4, "match_type": 3},
                    {"ht_match_id": 5, "match_type": 62},
                ],
            },
            lineups={
                1: [_entry(5.0)],
                2: [_entry(0.0)],
                3: [_entry(4.5)],
                4: [_entry(3.0)],
            },
        )
        uow = SqlAlchemyUnitOfWork(factory)
        handler = SyncTeamHandler(uow, chpp)
        async with uow:
            assert await handler._censar_partidos_del_stint(
                uow, team_id, PLAYER_HT_ID
            )
            await uow.commit()

        async with factory() as session:
            stints = list(
                (
                    await session.execute(
                        select(m.PlayerStint)
                        .where(m.PlayerStint.player_id == player_id)
                        .order_by(m.PlayerStint.arrived_at)
                    )
                )
                .scalars()
                .all()
            )
            player = await session.get(m.Player, player_id)
            assert [s.games_played_for_us for s in stints] == [1, 2]
            assert player is not None
            assert player.games_played_for_us == 3
        assert chpp.archive_calls == [key1, key2]
        assert chpp.lineup_calls == [1, 2, 3, 4]

    asyncio.run(run())


def test_lineup_failure_does_not_freeze_a_partial_count() -> None:
    async def run() -> None:
        factory, team_id = await _database()
        player_id = await _player(factory, team_id)
        async with factory() as session:
            stint = m.PlayerStint(
                player_id=player_id,
                ht_player_id=PLAYER_HT_ID,
                team_id=team_id,
                arrived_at=datetime(2026, 8, 20),
                left_at=datetime(2026, 8, 28),
            )
            session.add(stint)
            await session.commit()
            stint_id = stint.id

        key = ("2026-08-20 00:00:00", "2026-08-28 00:00:00")
        chpp = FakeCensusCHPP(
            archives={
                key: [
                    {"ht_match_id": 1, "match_type": 1},
                    {"ht_match_id": 2, "match_type": 3},
                ]
            },
            lineups={1: [_entry(5.0)]},
            fail_lineups={2},
        )
        uow = SqlAlchemyUnitOfWork(factory)
        handler = SyncTeamHandler(uow, chpp)
        with pytest.raises(RuntimeError, match="fallo transitorio"):
            async with uow:
                await handler._censar_partidos_del_stint(
                    uow, team_id, PLAYER_HT_ID
                )

        async with factory() as session:
            stint = await session.get(m.PlayerStint, stint_id)
            assert stint is not None
            assert stint.games_played_for_us is None
            assert stint.games_computed_at is None

        retry_uow = SqlAlchemyUnitOfWork(factory)
        retry_handler = SyncTeamHandler(retry_uow, FakeCensusCHPP())
        async with retry_uow:
            pending = await retry_handler.pendientes_de_ficha(retry_uow, team_id)
        assert PLAYER_HT_ID in pending["censo"]

    asyncio.run(run())


def test_academy_first_stint_uses_the_age_floor_after_a_return() -> None:
    async def run() -> None:
        factory, team_id = await _database()
        final_sale = datetime(2026, 8, 1)
        player_id = await _player(factory, team_id, sold_at=final_sale)
        async with factory() as session:
            player = await session.get(m.Player, player_id)
            assert player is not None
            player.age_years_at_sale = 19
            player.age_days_at_sale = 0
            session.add_all(
                [
                    m.PlayerStint(
                        player_id=player_id,
                        ht_player_id=PLAYER_HT_ID,
                        team_id=team_id,
                        from_academy=True,
                        arrived_at=None,
                        left_at=datetime(2026, 1, 1),
                    ),
                    m.PlayerStint(
                        player_id=player_id,
                        ht_player_id=PLAYER_HT_ID,
                        team_id=team_id,
                        arrived_at=datetime(2026, 6, 1),
                        left_at=final_sale,
                        games_played_for_us=2,
                        games_computed_at=datetime(2026, 8, 2),
                    ),
                ]
            )
            await session.commit()

        seventeenth_birthday = final_sale - timedelta(days=2 * 112)
        key = (
            seventeenth_birthday.strftime("%Y-%m-%d %H:%M:%S"),
            "2026-01-01 00:00:00",
        )
        chpp = FakeCensusCHPP(
            archives={key: [{"ht_match_id": 1, "match_type": 1}]},
            lineups={1: [_entry(4.0)]},
        )
        uow = SqlAlchemyUnitOfWork(factory)
        handler = SyncTeamHandler(uow, chpp)
        async with uow:
            assert await handler._censar_partidos_del_stint(
                uow, team_id, PLAYER_HT_ID
            )
            await uow.commit()

        async with factory() as session:
            stints = list(
                (
                    await session.execute(
                        select(m.PlayerStint)
                        .where(m.PlayerStint.player_id == player_id)
                        .order_by(m.PlayerStint.left_at)
                    )
                )
                .scalars()
                .all()
            )
            player = await session.get(m.Player, player_id)
            assert [s.games_played_for_us for s in stints] == [1, 2]
            assert player is not None
            assert player.games_played_for_us == 3
        assert chpp.archive_calls == [key]

    asyncio.run(run())


def test_a_completed_zero_is_not_fetched_again() -> None:
    async def run() -> None:
        factory, team_id = await _database()
        marked = datetime(2026, 8, 28, 14, 38)
        player_id = await _player(
            factory,
            team_id,
            legacy_games=0,
            legacy_computed=marked,
        )
        async with factory() as session:
            session.add(
                m.PlayerStint(
                    player_id=player_id,
                    ht_player_id=PLAYER_HT_ID,
                    team_id=team_id,
                    arrived_at=datetime(2026, 8, 20),
                    left_at=datetime(2026, 8, 28),
                    games_played_for_us=0,
                    games_computed_at=marked,
                )
            )
            await session.commit()

        uow = SqlAlchemyUnitOfWork(factory)
        handler = SyncTeamHandler(uow, FakeCensusCHPP())
        async with uow:
            pending = await handler.pendientes_de_ficha(uow, team_id)
            wrote = await handler._censar_partidos_del_stint(
                uow, team_id, PLAYER_HT_ID
            )
        assert PLAYER_HT_ID not in pending["censo"]
        assert wrote is False

    asyncio.run(run())
