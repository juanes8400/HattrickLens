"""GET /teams/{id}/experience/calibration — sobre datos sincronizados reales.

El test que importa aquí no es que el endpoint responda 200. Es que, con una
sola sincronización y por tanto sin ninguna subida de nivel observada, el
endpoint diga exactamente eso: que sigue usando el valor configurado, cuántas
observaciones le faltan, y que no se ha inventado una media.
"""
import asyncio
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.sync_team import SyncTeamCommand, SyncTeamHandler
from app.application.queries.player_history import PlayerHistoryQueryService
from app.domain.engines.experience_engine import calibrate, detect_level_ups
from app.infrastructure.chpp.parsers import get_parser
from app.infrastructure.db import models as m
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

FIXTURES = Path(__file__).parent / "fixtures"


class FakeCHPP:
    async def fetch(self, file: str, version: str, **params: Any) -> dict[str, Any]:
        return get_parser(file)((FIXTURES / f"{file}.xml").read_bytes())


async def _seeded() -> tuple[async_sessionmaker, int]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        team = m.Team(ht_team_id=537758, name="Pulgas Arrechas",
                      league_name="Colombia", series_name="V.92",
                      currency_rate=10.0, currency_name="US$")
        s.add(team)
        await s.commit()
        team_id = team.id
    handler = SyncTeamHandler(SqlAlchemyUnitOfWork(factory), FakeCHPP())
    await handler.execute(SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758))
    return factory, team_id


def test_one_sync_yields_no_observations_and_the_engine_says_so() -> None:
    """Una sola lectura por jugador no puede contener un cruce de nivel."""
    async def run() -> None:
        from sqlalchemy import select

        factory, team_id = await _seeded()
        async with factory() as s:
            rows = (
                await s.execute(
                    select(
                        m.Player.first_name,
                        m.Player.last_name,
                        m.PlayerSnapshot.experience,
                        m.PlayerSnapshot.captured_at,
                    )
                    .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
                    .where(m.Player.team_id == team_id)
                    .order_by(m.PlayerSnapshot.captured_at)
                )
            ).all()

        assert len(rows) == 24                     # la plantilla real
        snapshots = [(f"{first} {last}", int(e), 0.0) for first, last, e, _ in rows]
        assert detect_level_ups(snapshots) == []

        cal = calibrate([])
        assert cal.source == "configured"
        assert cal.points_per_level == 100
        assert cal.observations == 0
        assert cal.std_dev is None
        assert cal.confidence_interval is None

    asyncio.run(run())


def test_a_second_sync_with_a_level_up_is_detected_from_stored_history() -> None:
    """Y en cuanto la historia contiene un cruce, aparece. Es el mecanismo por
    el que la calibración mejora sola con cada sincronización."""
    async def run() -> None:
        from sqlalchemy import select

        factory, team_id = await _seeded()
        async with factory() as s:
            player = (
                await s.execute(
                    select(m.Player).where(m.Player.team_id == team_id).limit(1)
                )
            ).scalar_one()
            snap = (
                await s.execute(
                    select(m.PlayerSnapshot)
                    .where(m.PlayerSnapshot.player_id == player.id)
                    .limit(1)
                )
            ).scalar_one()

            # Segunda lectura del mismo jugador, un nivel de experiencia arriba.
            from datetime import timedelta

            s.add(
                m.PlayerSnapshot(
                    sync_id=snap.sync_id, player_id=player.id,
                    captured_at=snap.captured_at + timedelta(days=7),
                    age_years=snap.age_years, age_days=snap.age_days,
                    tsi=snap.tsi, form=snap.form, stamina=snap.stamina,
                    experience=snap.experience + 1, salary=snap.salary,
                    injury_level=snap.injury_level, content_hash=b"\x01" * 32,
                )
            )
            await s.commit()

            rows = (
                await s.execute(
                    select(
                        m.Player.first_name, m.Player.last_name,
                        m.PlayerSnapshot.experience, m.PlayerSnapshot.captured_at,
                    )
                    .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
                    .where(m.Player.team_id == team_id)
                    .order_by(m.PlayerSnapshot.captured_at)
                )
            ).all()

        found = detect_level_ups(
            [(f"{first} {last}", int(e), 0.0) for first, last, e, _ in rows]
        )
        assert len(found) == 1
        assert found[0].to_level == found[0].from_level + 1

        # Un solo cruce sigue sin ser evidencia: el valor configurado se mantiene.
        assert calibrate(found).source == "configured"

    asyncio.run(run())


def test_real_matches_between_two_observed_pops_feed_calibration() -> None:
    """The API must pass measured match points, never the former hard-coded 0.

    The first pop establishes a trustworthy start boundary. The next one is
    then a usable interval: one league, one friendly and one international
    friendly are 4.55 experience points in the configured model (Hattrick's
    real scale, 2026-08-05 — see experience.yaml).
    """
    async def run() -> None:
        from datetime import timedelta

        from sqlalchemy import select

        factory, team_id = await _seeded()
        async with factory() as s:
            player = (
                await s.execute(
                    select(m.Player).where(m.Player.team_id == team_id).limit(1)
                )
            ).scalar_one()
            first = (
                await s.execute(
                    select(m.PlayerSnapshot)
                    .where(m.PlayerSnapshot.player_id == player.id)
                    .limit(1)
                )
            ).scalar_one()
            started = first.captured_at + timedelta(days=7)
            popped = first.captured_at + timedelta(days=28)

            for captured_at, experience in (
                (started, first.experience + 1),
                (popped, first.experience + 2),
            ):
                s.add(
                    m.PlayerSnapshot(
                        sync_id=first.sync_id, player_id=player.id,
                        captured_at=captured_at,
                        age_years=first.age_years, age_days=first.age_days,
                        tsi=first.tsi, form=first.form, stamina=first.stamina,
                        experience=experience, salary=first.salary,
                        injury_level=first.injury_level, content_hash=bytes([experience]) * 32,
                    )
                )

            for match_id, days_after_start, match_type in (
                (900001, 2, 1),   # league: 1.0
                (900002, 5, 4),   # friendly: 0.1
                (900003, 9, 8),   # international friendly: 0.2
            ):
                played_at = started + timedelta(days=days_after_start)
                s.add(m.Match(
                    ht_match_id=match_id, played_at=played_at, match_type=match_type,
                    status="FINISHED", home_team_ht_id=537758, away_team_ht_id=987654,
                    home_team_name="Pulgas Arrechas", away_team_name="Rival",
                ))
                s.add(m.PlayerMatchRating(
                    player_id=player.id, ht_match_id=match_id, position_code=7,
                    played_minutes=90, rating=6.0, captured_at=played_at,
                ))
            await s.commit()

            observations, crossings = await PlayerHistoryQueryService(s).experience_level_up_observations(team_id)

        assert crossings == 2
        assert len(observations) == 1
        assert observations[0].from_level == first.experience + 1
        assert observations[0].to_level == first.experience + 2
        assert observations[0].points_accumulated == 4.55
        # A single observation is retained as evidence but, correctly, cannot
        # yet replace the configured 100-point prior.
        assert calibrate(observations).observations == 1
        assert calibrate(observations).source == "configured"

    asyncio.run(run())
