"""loyalty_level_up_observations / loyalty_level_started_at — sobre datos
sincronizados reales.

Mismo criterio de "salto limpio" que `experience_level_up_observations`
(HL-041), pero para `loyalty`: el intervalo se mide en días reales
transcurridos, no en puntos de partidos — Fidelidad no depende de partidos
jugados, solo de tiempo en el club.
"""
import asyncio
from datetime import timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.sync_team import SyncTeamCommand, SyncTeamHandler
from app.application.queries.player_history import PlayerHistoryQueryService
from app.domain.engines.loyalty_engine import calibrate
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


def test_one_sync_yields_no_loyalty_observations() -> None:
    """Una sola lectura por jugador no puede contener un cruce de nivel."""
    async def run() -> None:
        factory, team_id = await _seeded()
        async with factory() as s:
            observations, crossings = (
                await PlayerHistoryQueryService(s).loyalty_level_up_observations(team_id)
            )
        assert observations == []
        assert crossings == 0
        assert calibrate(observations).transitions == {}

    asyncio.run(run())


def test_a_clean_single_level_jump_becomes_a_calibration_sample() -> None:
    """La primera subida vista NUNCA es una observación (no sabemos cuándo
    empezó ese nivel anterior — pudo ser antes de sincronizar) pero SÍ
    ancla el siguiente intervalo. Solo la segunda subida limpia, con esa
    ancla, produce una muestra real de calibración — mismo criterio que
    `experience_level_up_observations`."""
    async def run() -> None:
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
            started_at = first.captured_at + timedelta(days=7)
            popped_at = first.captured_at + timedelta(days=28)

            for captured_at, loyalty in (
                (started_at, (first.loyalty or 0) + 1),
                (popped_at, (first.loyalty or 0) + 2),
            ):
                s.add(
                    m.PlayerSnapshot(
                        sync_id=first.sync_id, player_id=player.id,
                        captured_at=captured_at,
                        age_years=first.age_years, age_days=first.age_days,
                        tsi=first.tsi, form=first.form, stamina=first.stamina,
                        experience=first.experience, salary=first.salary,
                        loyalty=loyalty,
                        injury_level=first.injury_level,
                        content_hash=bytes([loyalty]) * 32,
                    )
                )
            await s.commit()

            history = PlayerHistoryQueryService(s)
            observations, crossings = await history.loyalty_level_up_observations(team_id)
            level_started_at = await history.loyalty_level_started_at(player.ht_player_id)

        assert crossings == 2
        assert len(observations) == 1
        obs = observations[0]
        assert obs.from_level == (first.loyalty or 0) + 1
        assert obs.to_level == (first.loyalty or 0) + 2
        assert obs.days_elapsed == 21

        cal = calibrate(observations)
        transition = cal.for_level((first.loyalty or 0) + 1)
        assert transition is not None
        assert transition.avg_days == 21.0
        assert transition.observations == 1

        # El anclaje del nivel ACTUAL de este jugador es el mismo instante
        # en que se observó ese último salto limpio.
        assert level_started_at == popped_at

    asyncio.run(run())


def test_a_multi_level_jump_is_seen_but_discarded() -> None:
    """Un salto de más de un nivel cuenta como cruce, pero no produce una
    observación limpia — no hay forma honesta de repartir los días entre
    los niveles intermedios."""
    async def run() -> None:
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

            s.add(
                m.PlayerSnapshot(
                    sync_id=first.sync_id, player_id=player.id,
                    captured_at=first.captured_at + timedelta(days=21),
                    age_years=first.age_years, age_days=first.age_days,
                    tsi=first.tsi, form=first.form, stamina=first.stamina,
                    experience=first.experience, salary=first.salary,
                    loyalty=(first.loyalty or 0) + 2,
                    injury_level=first.injury_level, content_hash=b"\x03" * 32,
                )
            )
            await s.commit()

            history = PlayerHistoryQueryService(s)
            observations, crossings = await history.loyalty_level_up_observations(team_id)
            started_at = await history.loyalty_level_started_at(player.ht_player_id)

        assert crossings == 1
        assert observations == []
        # Sin un salto limpio hacia el nivel actual, no hay ancla honesta.
        assert started_at is None

    asyncio.run(run())

