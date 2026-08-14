"""2026-08-09, pedido explícitamente: caso real (Volodymyr Manakin) probó
que `LastMatch` de playerdetails.xml puede ser de hace más de un año, no
"la última semana" — `SquadQueryService` debe ocultar posición/rating de
último partido cuando no cayó dentro de los últimos 7 días respecto a HOY.
"""
import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.queries.squad import SquadQueryService
from app.infrastructure.db import models as m

NOW = datetime.now(UTC)


async def _seed(*, last_match_played_at: datetime | None) -> tuple[async_sessionmaker, int]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as s:
        team = m.Team(ht_team_id=537758, name="Pulgas Arrechas")
        s.add(team)
        await s.flush()

        sync = m.Sync(user_id=1, team_id=team.id, kind="players", status="completed", started_at=NOW)
        s.add(sync)
        await s.flush()

        player = m.Player(ht_player_id=434712334, team_id=team.id, first_name="Volodymyr", last_name="Manakin")
        s.add(player)
        await s.flush()

        s.add(m.PlayerSnapshot(
            sync_id=sync.id, player_id=player.id, captured_at=NOW,
            age_years=44, age_days=72, tsi=0, form=3, stamina=1, experience=16,
            salary=0, specialty=0, injury_level=-1, is_transfer_listed=False,
            loyalty=20, leadership=3, agreeability=0, aggressiveness=0, honesty=0,
            content_hash=b"\x00" * 32,
            last_match_ht_id=747026268, last_match_position_code=103,
            last_match_behaviour_code=0, last_match_played_minutes=92,
            last_match_rating=1.0, last_match_played_at=last_match_played_at,
        ))
        await s.commit()
        team_id = team.id

    return factory, team_id


def test_a_last_match_from_more_than_a_week_ago_is_hidden() -> None:
    """Caso real: 2025-04-02, más de un año antes de hoy."""
    async def run() -> None:
        factory, team_id = await _seed(
            last_match_played_at=datetime(2025, 4, 2, 23, 40, tzinfo=UTC),
        )
        async with factory() as s:
            resp = await SquadQueryService(s).get(team_id)
        assert resp is not None
        player = next(p for p in resp.players if p.ht_player_id == 434712334)
        assert player.last_match_position is None
        assert player.last_match_rating is None
        assert player.last_match_played_minutes is None

    asyncio.run(run())


def test_a_last_match_within_the_last_week_is_shown() -> None:
    async def run() -> None:
        factory, team_id = await _seed(last_match_played_at=NOW - timedelta(days=3))
        async with factory() as s:
            resp = await SquadQueryService(s).get(team_id)
        assert resp is not None
        player = next(p for p in resp.players if p.ht_player_id == 434712334)
        assert player.last_match_position == "DC"
        assert player.last_match_rating == 1.0
        assert player.last_match_played_minutes == 92

    asyncio.run(run())


def test_a_missing_last_match_date_is_treated_as_not_recent() -> None:
    """Snapshots viejos (de antes de esta corrección) no tienen esta fecha
    guardada — deben tratarse como "no reciente", nunca mostrar el dato a
    ciegas."""
    async def run() -> None:
        factory, team_id = await _seed(last_match_played_at=None)
        async with factory() as s:
            resp = await SquadQueryService(s).get(team_id)
        assert resp is not None
        player = next(p for p in resp.players if p.ht_player_id == 434712334)
        assert player.last_match_position is None

    asyncio.run(run())
