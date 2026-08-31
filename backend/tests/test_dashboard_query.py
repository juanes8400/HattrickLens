"""Costura completa: sync (fixtures reales) → DB → query service → DTO."""
import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.sync_team import SyncTeamCommand, SyncTeamHandler
from app.application.queries.dashboard import DashboardQueryService
from app.application.queries.economy import EconomyQueryService
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
        # Convertido a moneda local (tasa de Colombia = 10), igual que finance.cash.
        assert d.squad.total_salary == 220728
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
        assert d.top_salaries[0].salary == 72312
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


def test_sin_los_salarios_de_la_semana_anterior_no_se_inventa_un_cero() -> None:
    """`last_costs_players` es NULLABLE y en la base real hay filas sin el.

    2026-08-26, encontrado por mypy: `costs_players + last_costs_players`
    reventaba con TypeError, y en la pantalla de INICIO. Y ponerle un 0
    tampoco vale: la migracion 0021, que creo esas columnas, lo dejo escrito
    --"NULL dice 'no se sabe', nunca cero"-- y la pantalla habria pintado
    "0 US$ · 0,0% de los ingresos", que es afirmar que no se pagaron salarios.
    """
    from app.application.dto.dashboard import FinanceSummary

    # El contrato: los dos campos admiten "no se sabe", y por defecto lo dicen.
    resumen = FinanceSummary(
        cash=0, expected_cash=0, weekly_delta=0, income_sum=0, costs_sum=0,
        costs_players=0, fan_club_size=0, last_weeks_total=0,
    )
    assert resumen.biweekly_salaries is None
    assert resumen.salary_share_pct is None


async def _con_dos_cierres() -> tuple[async_sessionmaker, int]:
    """El fixture trae UNA sola lectura, así que `weekly_closes` sólo ve un
    cierre y lo bisemanal sale vacío --rama legítima, pero no la interesante--.

    Esto añade una segunda lectura posterior con flujos `last_*` distintos,
    que es exactamente la señal por la que Hattrick pasa de semana.
    """
    factory, team_id = await _seeded()
    async with factory() as s:
        vieja = (
            await s.execute(
                m.EconomySnapshot.__table__.select()
                .where(m.EconomySnapshot.team_id == team_id)
                .order_by(m.EconomySnapshot.captured_at.desc())
                .limit(1)
            )
        ).mappings().one()

        campos = {k: v for k, v in vieja.items() if k != "id"}
        campos["captured_at"] = vieja["captured_at"] + timedelta(days=7)
        # Los flujos de la semana que acaba de cerrar: otros números, o
        # `weekly_closes` lo lee como la misma foto repetida.
        campos["last_income_sum"] = 1_000_000
        campos["last_costs_sum"] = 1_500_000
        campos["last_weeks_total"] = -500_000
        campos["last_costs_players"] = 400_000
        s.add(m.EconomySnapshot(**campos))
        await s.commit()
    return factory, team_id


def test_lo_bisemanal_son_dos_semanas_CERRADAS() -> None:
    """El Panel y Economía tienen que decir lo mismo para el mismo periodo.

    2026-08-30. El Panel sumaba `income_sum + last_income_sum`: la semana EN
    CURSO más una cerrada, bajo la etiqueta «las dos semanas cerradas».
    Economía, que sí usa los dos cierres, decía -826.194 donde el Panel decía
    -437.404. Además, mezclar una semana a medias rompe la garantía por la que
    se eligieron dos --que siempre entre una taquilla--: el KPI se hundía los
    días sin partido jugado y se recuperaba solo después.

    Este test fija el HECHO, no las cifras: sea cual sea el fixture, las dos
    pantallas coinciden y ninguna de las dos mira la semana en curso.
    """

    async def go() -> tuple[Any, Any]:
        factory, team_id = await _con_dos_cierres()
        async with factory() as s:
            panel = await DashboardQueryService(s).get(team_id)
            eco = await EconomyQueryService(s).get(team_id)
        return panel, eco

    panel, eco = asyncio.run(go())
    assert panel is not None and panel.finance is not None
    assert eco is not None

    bisemanal = next(w for w in eco.balance_windows if w.weeks_requested == 2)
    assert bisemanal.balance is not None, "el fixture tiene que dar dos cierres"

    assert panel.finance.biweekly_balance == bisemanal.balance
    assert panel.finance.biweekly_income == bisemanal.income
    # Y la prueba de que no entra la semana en curso: si entrara, los ingresos
    # del Panel llevarían encima los de la semana viva.
    assert panel.finance.biweekly_income != bisemanal.income + panel.finance.income_sum


def test_el_balance_sin_transferencias_es_el_mismo_en_las_tres_pantallas() -> None:
    """Panel, Economía y la alerta de déficit tenían tres sumas distintas.

    2026-08-30. `economy_engine.structural_balance` dice en su propio docstring
    ser «la única fuente de verdad», pero el Panel y la alerta la llamaban con
    los campos de la semana EN CURSO --taquilla en 0 hasta que se juega en
    casa-- y sin los gastos juveniles ni los financieros, mientras Economía
    promediaba las dos semanas cerradas e incluía ambos. Salían -414.969 y
    -435.347 para lo mismo, y ese número es el que decide cuántas semanas de
    caja se le anuncian al usuario.
    """

    async def go() -> tuple[Any, Any]:
        factory, team_id = await _con_dos_cierres()
        async with factory() as s:
            return (
                await DashboardQueryService(s).get(team_id),
                await EconomyQueryService(s).get(team_id),
            )

    panel, eco = asyncio.run(go())
    assert panel is not None and panel.finance is not None
    assert eco is not None
    assert panel.finance.structural_balance == eco.structural_balance


def test_sin_dos_cierres_lo_bisemanal_no_se_inventa() -> None:
    """Un 0 diría que el club no ingresó ni gastó nada. Se dice que no se sabe."""

    async def go() -> Any:
        factory, team_id = await _seeded()
        async with factory() as s:
            return await DashboardQueryService(s).get(team_id)

    panel = asyncio.run(go())
    assert panel is not None and panel.finance is not None
    assert panel.finance.biweekly_balance is None
    assert panel.finance.biweekly_income is None
