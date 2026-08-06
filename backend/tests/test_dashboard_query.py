"""Costura completa: sync (fixtures reales) → DB → query service → DTO."""
import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.sync_team import SyncTeamCommand, SyncTeamHandler
from app.application.queries.dashboard import DashboardQueryService
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


def test_dashboard_reflects_synced_data() -> None:
    async def run() -> None:
        factory, team_id = await _seeded()
        async with factory() as s:
            d = await DashboardQueryService(s).get(team_id)

        assert d is not None
        assert d.team_name == "Pulgas Arrechas"
        assert d.series_name == "V.92"
        assert d.stale is False          # sync recién hecho
        assert d.sync_id is not None

        assert d.squad is not None
        assert d.squad.player_count == 24
        assert d.squad.total_tsi == 1197060
        assert d.squad.total_salary == 2207280
        assert d.squad.injured_count == 0
        assert 27.0 < d.squad.avg_age < 27.5

        assert d.finance is not None
        # Convertido a moneda local: CHPP da 210.341.736 en moneda base y la
        # tasa de Colombia es 10 → 21.034.174 US$, que es lo que ve el usuario.
        assert d.finance.cash == 21034174
        assert d.finance.weekly_delta == 1351393
        assert d.finance.currency == "US$"
        assert d.finance.fan_club_size == 2406        # cantidad, no dinero
        # La operación pierde dinero cada semana aunque el titular sea positivo
        assert d.finance.structural_balance < 0

        assert d.training is not None
        assert d.training.type_id == 10
        # TrainingType 10 es el tipo CHPP "Passing (Defenders + Midfielders)".
        assert d.training.type_name == "Pases (defensas y centrocampistas)"
        assert d.training.trainer_name == "Volodymyr Manakin"
        assert d.training.morale_name == "Serenos"
        assert d.training.confidence_name == "Sólida"

        # top salarios ordenado desc, con nombres resueltos desde la identidad
        assert d.top_salaries[0].name == "Alberto Gutiérrez Caviedes"
        assert d.top_salaries[0].salary == 723120
        assert d.top_salaries[0].skills["scoring"] == 18
        assert d.top_salaries[0].skills["setPieces"] == 9  # contrato camelCase

    asyncio.run(run())


def test_dashboard_marks_stale_when_sync_is_old() -> None:
    async def run() -> None:
        factory, team_id = await _seeded()
        future = datetime.now(UTC) + timedelta(days=2)
        async with factory() as s:
            d = await DashboardQueryService(s).get(team_id, now=future)
        assert d is not None and d.stale is True
        assert any(a.kind == "sync" for a in d.alerts)

    asyncio.run(run())


def test_dashboard_returns_none_for_unknown_team() -> None:
    async def run() -> None:
        factory, _ = await _seeded()
        async with factory() as s:
            assert await DashboardQueryService(s).get(9999) is None

    asyncio.run(run())


def test_dashboard_serializes_camelcase() -> None:
    async def run() -> None:
        factory, team_id = await _seeded()
        async with factory() as s:
            d = await DashboardQueryService(s).get(team_id)
        payload = d.model_dump(by_alias=True)  # type: ignore[union-attr]
        assert "teamName" in payload and "topSalaries" in payload
        assert "weeklyDelta" in payload["finance"]
        assert "player_count" not in payload["squad"]

    asyncio.run(run())
