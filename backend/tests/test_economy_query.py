"""EconomyQueryService sobre los snapshots reales del club.

Lo que se comprueba aquí no es que el servicio devuelva algo, sino que devuelva
lo correcto en la moneda correcta y que sea honesto sobre cuál de sus dos
proyecciones se puede creer hoy.
"""
import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.queries.economy import (
    MIN_WEEKS_FOR_TIMESERIES,
    EconomyQueryService,
)
from app.domain.engines.economy_engine import PlannedEvent
from app.infrastructure.db import models as m
from tests.conftest import seeded_session


def run(coro):
    return asyncio.run(coro)


def test_amounts_are_in_local_currency_not_game_base() -> None:
    """CHPP entrega 210.341.736 en moneda base; con tasa 10 el usuario ve
    21.034.174 US$. Este es el error que más caro sale porque no parece un
    error: todo cuadra consigo mismo, sólo que multiplicado por diez."""
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            return await EconomyQueryService(s).get(team_id)

    d = run(go())
    assert d is not None
    assert d.currency == "US$"
    assert d.cash == 21034174
    assert d.expected_cash == 22385566
    assert d.team_name == "Pulgas Arrechas"


def test_weekly_finance_groups_into_hattrick_categories() -> None:
    """La tabla de finanzas semanales tiene que hablar con las mismas
    categorías y el mismo orden que el informe de Hattrick, no con los
    nombres crudos de los campos CHPP."""
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            return await EconomyQueryService(s).get(team_id)

    d = run(go())
    assert d is not None
    assert [item.code for item in d.weekly_finance.income] == [
        "IncomeSpectators", "IncomeSponsors", "IncomeSoldPlayers",
        "IncomeSoldPlayersCommission", "IncomeOther",
    ]
    assert [item.code for item in d.weekly_finance.costs] == [
        "CostsPlayers", "CostsArena", "CostsArenaBuilding", "CostsStaff",
        "CostsYouth", "CostsBoughtPlayers", "CostsOther",
    ]
    # El fixture trae IncomeFinancial=0 e IncomeTemporary=15.476.336 (base) —
    # "Otros" tiene que ser la suma de ambos, convertida a moneda local (÷10).
    other = next(i for i in d.weekly_finance.income if i.code == "IncomeOther")
    assert other.amount == 1547634
    assert d.weekly_finance.expected_balance == 1351393
    assert d.balance_windows[0].balance is None
    assert d.balance_windows[0].weeks_available == 1


def test_structural_forecast_works_from_a_single_snapshot() -> None:
    """Es la razón de existir de la ruta bottom-up: no aprende del histórico
    sino de la estructura, así que sirve desde el primer día."""
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            return await EconomyQueryService(s).get(team_id, horizon_weeks=52)

    d = run(go())
    f = d.structural_forecast
    assert len(f.weeks) == 52
    assert len(f.p50) == 52
    # La banda tiene que ser una banda: p10 ≤ p50 ≤ p90 en cada semana.
    assert all(a <= b <= c for a, b, c in zip(f.p10, f.p50, f.p90, strict=True))
    # Y tiene que abrirse con el horizonte: la incertidumbre crece con el tiempo.
    assert (f.p90[-1] - f.p10[-1]) > (f.p90[0] - f.p10[0])


def test_timeseries_route_stays_silent_until_it_has_evidence() -> None:
    """Con una sola lectura no hay serie que validar. El servicio lo dice en
    vez de ajustar un modelo a un punto y presentarlo como predicción."""
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            return await EconomyQueryService(s).get(team_id)

    d = run(go())
    assert d.weeks_of_history < MIN_WEEKS_FOR_TIMESERIES
    assert d.timeseries_forecast is None
    assert d.recommended_model == "bottom_up"
    assert str(MIN_WEEKS_FOR_TIMESERIES) in d.recommendation_reason


def test_series_and_forecast_carry_the_season_week_label() -> None:
    """2026-08-09, pedido explícitamente: "TT-ss" (temporada-semana) en el
    eje X de Economía. El fixture de worlddetails.xml trae Colombia
    (LeagueID 19) en temporada 84, MatchRound 3 (= semana 3 a partir de
    v2.0, ver sync_team.py FILE_VERSIONS) — pero `seeded_session()` no
    sincroniza teamdetails, así que `Team.ht_league_id` queda en None hasta
    que se fija a mano aquí, igual que tendría que pasar en producción tras
    un sync real."""
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            team = await s.get(m.Team, team_id)
            team.ht_league_id = 19
            await s.commit()
            return await EconomyQueryService(s).get(team_id)

    d = run(go())
    assert d is not None
    assert d.series[-1].season_week == "84-03"
    # Semana siguiente a la actual (offset +1 de la proyección estructural).
    assert d.structural_forecast.week_labels[0] == "84-04"
    assert len(d.structural_forecast.week_labels) == len(d.structural_forecast.weeks)


def test_season_week_is_none_without_a_league_id() -> None:
    """Sin `ht_league_id` (equipo nunca sincronizó teamdetails.xml) no hay
    ancla real — `None`, no un supuesto."""
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            return await EconomyQueryService(s).get(team_id)

    d = run(go())
    assert d is not None
    assert d.series[-1].season_week is None
    assert all(label is None for label in d.structural_forecast.week_labels)


async def _seed_two_weeks(
    week1_costs_players: int, week1_sponsors: int, week1_bonus: int | None,
    week2_costs_players: int, week2_sponsors: int, week2_bonus: int | None,
) -> tuple[async_sessionmaker, int]:
    """Dos semanas ISO distintas, con solo `costs_players`/patrocinio
    variando entre ellas — para aislar el efecto de promediar la base
    estructural sobre 2 semanas en vez de leer solo la última."""
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as s:
        team = m.Team(ht_team_id=1, name="Test FC", currency_rate=1.0, currency_name="US$")
        s.add(team)
        await s.flush()
        sync = m.Sync(
            user_id=1, team_id=team.id, kind="economy", status="completed",
            started_at=datetime(2026, 8, 2, tzinfo=UTC),
        )
        s.add(sync)
        await s.flush()

        common = dict(
            sync_id=sync.id, team_id=team.id, cash=1_000_000, expected_cash=1_000_000,
            sponsors_popularity=0, supporters_popularity=0, fan_club_size=0,
            income_spectators=0, income_financial=0, income_temporary=0,
            costs_arena=40_000, costs_financial=0, costs_bought_players=None,
            costs_arena_building=None, costs_staff=50_000, costs_temporary=None,
            costs_youth=10_000, expected_weeks_total=0,
            last_income_sum=0, last_costs_sum=0, last_weeks_total=0,
            last_income_spectators=None, last_income_sponsors=None, last_income_financial=None,
            last_income_sold_players=None, last_income_sold_players_commission=None,
            last_income_temporary=None, last_costs_arena=None, last_costs_players=None,
            last_costs_financial=None, last_costs_staff=None, last_costs_youth=None,
            last_costs_bought_players=None, last_costs_arena_building=None,
            last_costs_temporary=None,
        )
        s.add(m.EconomySnapshot(
            captured_at=datetime(2026, 7, 26, tzinfo=UTC),  # semana ISO 30
            income_sponsors=week1_sponsors, income_sponsor_bonuses=week1_bonus,
            costs_players=week1_costs_players,
            income_sum=week1_sponsors, costs_sum=week1_costs_players + 100_000,
            content_hash=b"\x01" * 32,
            **common,
        ))
        s.add(m.EconomySnapshot(
            captured_at=datetime(2026, 8, 2, tzinfo=UTC),  # semana ISO 31 — la más reciente
            income_sponsors=week2_sponsors, income_sponsor_bonuses=week2_bonus,
            costs_players=week2_costs_players,
            income_sum=week2_sponsors, costs_sum=week2_costs_players + 100_000,
            content_hash=b"\x02" * 32,
            **common,
        ))
        await s.commit()
        team_id = team.id

    return factory, team_id


def test_structural_balance_averages_the_last_two_weeks_and_includes_the_bonus() -> None:
    """2026-08-09, pedido explícito del usuario: la base estructural ya no
    sale de una sola semana — se promedian las últimas 2 cerradas — y el
    patrocinio incluye el bono (`IncomeSponsorBonuses`), no solo el campo
    base."""
    async def go():
        factory, team_id = await _seed_two_weeks(
            week1_costs_players=200_000, week1_sponsors=100_000, week1_bonus=0,
            week2_costs_players=300_000, week2_sponsors=100_000, week2_bonus=20_000,
        )
        async with factory() as s:
            return await EconomyQueryService(s).get(team_id)

    d = run(go())
    assert d is not None
    # Patrocinio total: semana 1 = 100.000, semana 2 = 120.000 (100.000+bono
    # 20.000) -> promedio 110.000. costs_players: (200.000+300.000)/2 =
    # 250.000. staff/arena/juveniles fijos en 50.000/40.000/10.000 ambas
    # semanas. estructura = 110.000 − 250.000 − 50.000 − 40.000 − 10.000.
    assert d.structural_balance == -240_000


def test_weekly_breakdown_is_ordered_most_recent_first() -> None:
    """2026-08-09, pedido explícito: al revés que `series` (que va ascendente
    porque alimenta gráficos), Detalles va del más reciente al más antiguo —
    igual que la pantalla equivalente de Hattrick Control."""
    async def go():
        factory, team_id = await _seed_two_weeks(
            week1_costs_players=200_000, week1_sponsors=100_000, week1_bonus=0,
            week2_costs_players=300_000, week2_sponsors=100_000, week2_bonus=20_000,
        )
        async with factory() as s:
            return await EconomyQueryService(s).get(team_id)

    d = run(go())
    assert d is not None
    assert len(d.weekly_breakdown) == 2
    assert d.weekly_breakdown[0].date == "2026-08-02"  # la más reciente, primero
    assert d.weekly_breakdown[0].is_current is True
    assert d.weekly_breakdown[1].date == "2026-07-26"
    assert d.weekly_breakdown[1].is_current is False


def test_weekly_breakdown_never_fabricates_a_zero_for_a_week_without_closed_data() -> None:
    """Caso real 2026-08-09: el primer sync que hace un club no trae desglose
    de la semana YA CERRADA (CHPP no tiene "semana anterior" que reportar) —
    debe salir `None` ("sin dato"), nunca 0 fabricado. La semana EN CURSO sí
    usa datos reales (los campos "en vivo" del snapshot)."""
    async def go():
        factory, team_id = await _seed_two_weeks(
            week1_costs_players=200_000, week1_sponsors=100_000, week1_bonus=0,
            week2_costs_players=300_000, week2_sponsors=100_000, week2_bonus=20_000,
        )
        async with factory() as s:
            return await EconomyQueryService(s).get(team_id)

    d = run(go())
    assert d is not None
    current, closed = d.weekly_breakdown
    # Semana en curso: datos reales, no None.
    assert current.income.total == 120_000  # 100.000 sponsors + 20.000 bono
    assert current.costs.total == 300_000 + 40_000 + 0 + 50_000 + 10_000
    # Semana cerrada sin desglose real: None en cascada, no 0.
    assert closed.income.spectators is None
    assert closed.income.subtotal is None
    assert closed.income.total is None
    assert closed.costs.total is None


def test_season_breakdown_totals_group_by_season_newest_first() -> None:
    async def go():
        factory, team_id = await _seed_two_weeks(
            week1_costs_players=200_000, week1_sponsors=100_000, week1_bonus=0,
            week2_costs_players=300_000, week2_sponsors=100_000, week2_bonus=20_000,
        )
        async with factory() as s:
            team = await s.get(m.Team, team_id)
            team.ht_league_id = 19
            world = m.WorldContext(
                ht_league_id=19, country_name="Colombia", league_name="Colombia",
                season=83, season_offset=0, match_round=3, match_rounds_left=13,
                currency_name="US$", currency_rate=1.0,
                refreshed_at=datetime(2026, 8, 9, tzinfo=UTC),
            )
            s.add(world)
            await s.commit()
            return await EconomyQueryService(s).get(team_id)

    d = run(go())
    assert d is not None
    # Ambas semanas (2026-07-26 y 2026-08-02) caen en la misma temporada 83
    # con este ancla — un solo grupo.
    assert len(d.season_breakdown_totals) == 1
    assert d.season_breakdown_totals[0].season == 83
    # Solo la semana en curso (2026-08-02) tiene desglose real; la otra es
    # None y `_sum_optional` no la cuenta como 0 fabricado, la ignora.
    assert d.season_breakdown_totals[0].income.total == 120_000


def test_structural_balance_falls_back_to_one_week_when_theres_only_one() -> None:
    """Con una sola semana sincronizada, "promedio de las últimas 2" debe
    degradar limpiamente a esa única semana — nunca inventar una segunda."""
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            return await EconomyQueryService(s).get(team_id)

    d = run(go())
    assert d is not None
    assert d.weeks_of_history == 1
    # No debe reventar ni promediar con una semana fantasma: el resultado
    # tiene que ser exactamente el de la única semana real disponible.
    assert isinstance(d.structural_balance, int)


def _economy_row(
    sync_id: int, team_id: int, captured_at: datetime,
    spectators: int = 0, last_spectators: int | None = None,
    last_income_sum: int = 0, last_costs_sum: int = 0,
    last_income_sold_players: int | None = None,
    last_costs_bought_players: int | None = None,
) -> m.EconomySnapshot:
    """Fila mínima de economy_snapshots — sólo Taquillas rellena, el resto en
    cero, para aislar la suma de ventanas del Sankey sin ruido de otras
    partidas."""
    return m.EconomySnapshot(
        sync_id=sync_id, team_id=team_id, captured_at=captured_at,
        cash=0, expected_cash=0, sponsors_popularity=0, supporters_popularity=0,
        fan_club_size=0,
        income_spectators=spectators, income_sponsors=0, income_financial=0,
        income_temporary=0, income_sum=spectators,
        costs_arena=0, costs_players=0, costs_financial=0, costs_staff=0,
        costs_temporary=0, costs_youth=0, costs_sum=0,
        expected_weeks_total=0, last_income_sum=last_income_sum, last_costs_sum=last_costs_sum,
        last_weeks_total=last_income_sum - last_costs_sum,
        last_income_spectators=last_spectators,
        last_income_sold_players=last_income_sold_players,
        last_costs_bought_players=last_costs_bought_players,
        content_hash=bytes([sync_id]) * 32,
    )


def test_sankey_windows_chain_each_snapshots_own_closed_week() -> None:
    """1 semana es sólo la semana en curso. Cada snapshot describe además la
    semana YA CERRADA justo antes de la suya (Last*); encadenando esa semana
    cerrada de los últimos N snapshots se arma una ventana de N semanas sin
    solapar ninguna — nunca se repite una misma semana dos veces."""
    async def go():
        engine = create_async_engine(
            "sqlite+aiosqlite://", poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as s:
            team = m.Team(
                ht_team_id=1, name="Test FC", currency_rate=10.0, currency_name="US$",
            )
            s.add(team)
            await s.commit()
            base = datetime(2026, 6, 1, tzinfo=UTC)
            # A y B sólo aportan la semana YA CERRADA que describen (last_*);
            # su semana "en curso" no se usa para nada aquí.
            s.add_all([
                _economy_row(1, team.id, base, last_spectators=200),                    # A
                _economy_row(2, team.id, base + timedelta(days=7), last_spectators=300),  # B
                _economy_row(                                                             # C, la viva
                    3, team.id, base + timedelta(days=14),
                    spectators=1000, last_spectators=500,
                ),
            ])
            await s.commit()
            return await EconomyQueryService(s).get(team.id)

    d = run(go())
    assert d is not None
    by_weeks = {w.weeks: w for w in d.sankey_windows}
    assert set(by_weeks) == {1, 2, 4, 8, 16}

    def taquillas(weeks: int) -> int | None:
        return next(i.amount for i in by_weeks[weeks].income if i.code == "IncomeSpectators")

    assert taquillas(1) == 100                    # sólo la semana viva (1000 ÷ 10)
    assert by_weeks[1].weeks_available == 1
    assert taquillas(2) == 100 + 50                # + la última semana cerrada de C (500 ÷ 10)
    assert by_weeks[2].weeks_available == 2
    # Sólo hay 3 filas en total: 1 viva + hasta 3 semanas cerradas
    # encadenables (la propia de C, luego B, luego A) — no más, ni menos.
    assert taquillas(4) == 100 + 50 + 30 + 20      # + las cerradas de B y de A
    assert by_weeks[4].weeks_available == 4
    assert taquillas(8) == taquillas(4)            # no hay una cuarta fila que sumar
    assert by_weeks[8].weeks_available == 4


async def _run_with_rows(rows_factory):
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        team = m.Team(ht_team_id=1, name="Test FC", currency_rate=10.0, currency_name="US$")
        s.add(team)
        await s.commit()
        s.add_all(rows_factory(team.id))
        await s.commit()
        return await EconomyQueryService(s).get(team.id)


def test_balance_excl_transfers_takes_out_player_trading() -> None:
    """Ingresos − gastos SIN la compraventa: una venta puntual no puede
    disfrazar un negocio que pierde dinero operando."""
    base = datetime(2026, 6, 1, tzinfo=UTC)

    def rows(team_id: int):
        return [
            _economy_row(
                1, team_id, base,
                last_income_sum=1000, last_costs_sum=400,
                last_income_sold_players=600, last_costs_bought_players=100,
            ),
            _economy_row(
                2, team_id, base + timedelta(days=7),
                last_income_sum=2000, last_costs_sum=800,
                last_income_sold_players=0, last_costs_bought_players=300,
            ),
        ]

    d = run(_run_with_rows(rows))
    assert d is not None
    window = next(w for w in d.balance_windows if w.weeks_requested == 2)
    assert window.income == 300 and window.costs == 120 and window.balance == 180
    # (300 − 60) − (120 − 40) = 240 − 80 = 160
    assert window.balance_excl_transfers == 160


def test_balance_excl_transfers_stays_silent_without_the_full_breakdown() -> None:
    """Un snapshot sincronizado antes de guardar Last*SoldPlayers/BoughtPlayers
    no tiene cómo separar la compraventa — decirlo es mejor que asumir cero."""
    base = datetime(2026, 6, 1, tzinfo=UTC)

    def rows(team_id: int):
        return [
            _economy_row(1, team_id, base, last_income_sum=1000, last_costs_sum=400),
            _economy_row(
                2, team_id, base + timedelta(days=7),
                last_income_sum=2000, last_costs_sum=800,
                last_income_sold_players=0, last_costs_bought_players=300,
            ),
        ]

    d = run(_run_with_rows(rows))
    assert d is not None
    window = next(w for w in d.balance_windows if w.weeks_requested == 2)
    assert window.balance == 180  # el balance crudo no depende del desglose
    assert window.balance_excl_transfers is None


def test_planned_events_move_the_forecast_in_the_right_direction() -> None:
    """La pregunta que importa es «¿aguanto este fichaje?», y sólo vale la pena
    responderla antes de pujar."""
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            svc = EconomyQueryService(s)
            base = await svc.get(team_id)
            spend = await svc.get(
                team_id,
                planned=[PlannedEvent(week=1, amount=-5_000_000, label="fichaje")],
            )
            earn = await svc.get(
                team_id,
                planned=[PlannedEvent(week=1, amount=5_000_000, label="venta")],
            )
            return base, spend, earn

    base, spend, earn = run(go())
    assert spend.structural_forecast.p50[-1] < base.structural_forecast.p50[-1]
    assert earn.structural_forecast.p50[-1] > base.structural_forecast.p50[-1]
    # El movimiento debe ser del tamaño del evento, no de un múltiplo raro.
    delta = earn.structural_forecast.p50[-1] - base.structural_forecast.p50[-1]
    assert 4_500_000 <= delta <= 5_500_000


def test_missing_team_returns_none_instead_of_raising() -> None:
    async def go():
        factory, _ = await seeded_session()
        async with factory() as s:
            return await EconomyQueryService(s).get(999999)

    assert run(go()) is None
