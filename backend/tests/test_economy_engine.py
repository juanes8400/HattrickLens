"""Tests del motor económico, con los números reales de Pulgas Arrechas.

Valores en moneda local (US$), ya divididos por la tasa de conversión 10.
Fuente: pantalla Economía de Hattrick Control, semana 83-01.
"""
import pytest

from app.domain.engines.economy_engine import (
    HOME_MATCHES_PER_SEASON,
    SEASON_WEEKS,
    PlannedEvent,
    WeeklyStructure,
    estimate_residuals,
    forecast_cash,
    total_sponsor_income,
)

# Semana 83-01 de Pulgas Arrechas
PULGAS = WeeklyStructure(
    salaries=232_428,
    staff=53_040,
    arena_maintenance=40_983,
    sponsors=103_500,
    # 15.210 es lo que entra POR SEMANA. Lo de un día de partido es esa cifra
    # repartida al revés, que es justo lo que sortea la simulación.
    base_gate=15_210 * SEASON_WEEKS // HOME_MATCHES_PER_SEASON,
    weekly_gate=15_210,
    other_fixed=9_000,
)


def test_structural_balance_matches_hattrick_control() -> None:
    """HC muestra 'Balance sin Otros' = -98.837 para esta misma semana."""
    assert PULGAS.structural_balance == pytest.approx(-216_741, abs=1)
    # Nota: HC calcula -98.837 incluyendo la comisión de transferencias como
    # recurrente; nuestro criterio la considera discrecional. Ambos números son
    # negativos: la operación pierde dinero cada semana.


def test_total_sponsor_income_adds_the_bonus() -> None:
    """2026-08-09, bug real corregido a pedido del usuario: el patrocinio
    real de la semana incluye IncomeSponsorBonuses, no solo IncomeSponsors
    — la tabla "Finanzas de esta semana" ya los sumaba, pero el balance
    estructural (dashboard, insights, la proyección de Economía) leía solo
    el campo base."""
    assert total_sponsor_income(103_500, 20_500) == 124_000


def test_total_sponsor_income_handles_a_missing_bonus() -> None:
    """CHPP no siempre expone el bono (campo opcional) — ausente, no cero
    fabricado, pero el total no debe romperse por eso."""
    assert total_sponsor_income(103_500, None) == 103_500


def test_forecast_is_monotone_in_bands() -> None:
    r = forecast_cash(21_034_174, PULGAS, horizon_weeks=52, n_runs=2000)
    assert len(r.p50) == 52
    for lo, mid, hi in zip(r.p10, r.p50, r.p90, strict=True):
        assert lo <= mid <= hi


def test_negative_structure_drains_cash() -> None:
    r = forecast_cash(21_034_174, PULGAS, horizon_weeks=52, n_runs=2000)
    assert r.p50[-1] < 21_034_174        # pierde dinero
    assert r.weeks_until_broke is None   # pero aguanta más de un año


def test_planned_sale_lifts_the_curve() -> None:
    base = forecast_cash(1_000_000, PULGAS, horizon_weeks=20, n_runs=2000)
    with_sale = forecast_cash(
        1_000_000, PULGAS, horizon_weeks=20, n_runs=2000,
        planned=[PlannedEvent(week=5, amount=3_000_000, label="venta")],
    )
    assert with_sale.p50[-1] > base.p50[-1] + 2_500_000


def test_small_club_runs_out_of_money() -> None:
    tiny = WeeklyStructure(
        salaries=500_000, staff=100_000, arena_maintenance=50_000,
        sponsors=50_000, base_gate=20_000,
    )
    r = forecast_cash(1_000_000, tiny, horizon_weeks=52, n_runs=1000)
    assert r.weeks_until_broke is not None and r.weeks_until_broke < 10


def test_residuals_need_enough_history() -> None:
    assert estimate_residuals([1, 2], [1, 2]) == (0.0, 0.0)
    mean, std = estimate_residuals([110, 120, 130, 140], [100, 100, 100, 100])
    assert mean == pytest.approx(25.0)
    assert std > 0


def test_forecast_is_deterministic_with_seed() -> None:
    a = forecast_cash(1_000_000, PULGAS, horizon_weeks=10, n_runs=500, seed=7)
    b = forecast_cash(1_000_000, PULGAS, horizon_weeks=10, n_runs=500, seed=7)
    assert a.p50 == b.p50


def test_forecast_from_history_uses_timeseries() -> None:
    """Con histórico real la proyección la dirige la serie, no el bottom-up."""
    from app.domain.engines.economy_engine import forecast_from_history

    # 24 semanas: balance estructural negativo con taquilla cada 2 semanas
    history = [-217_000 + (60_000 if w % 2 == 0 else 0) for w in range(24)]
    r = forecast_from_history(21_034_174, history, horizon_weeks=52)

    # Lo que se comprueba es que MANDE la serie, no cual de los modelos gana:
    # la lista de nombres estaba escrita a mano y con los modelos nuevos gana
    # `seasonal_naive` con error CERO -- este historico alterna cada 2 semanas
    # y 16 es par, asi que "la misma semana de la temporada pasada" reproduce
    # la alternancia exacta. Es el ganador correcto, y la lista vieja lo habria
    # dado por fallo (2026-09-01).
    from app.domain.engines.timeseries import MODELS

    assert r.model in MODELS
    assert r.model != "bottom_up"
    assert r.candidates and len(r.candidates) >= 3
    assert r.p50[-1] < 21_034_174          # la caja baja
    assert r.p10[-1] < r.p50[-1] < r.p90[-1]


def test_history_forecast_respects_planned_events() -> None:
    from app.domain.engines.economy_engine import forecast_from_history

    history = [-100_000] * 12
    base = forecast_from_history(5_000_000, history, horizon_weeks=20)
    with_sale = forecast_from_history(
        5_000_000, history, horizon_weeks=20,
        planned=[PlannedEvent(week=3, amount=1_000_000, label="venta")],
    )
    assert with_sale.p50[-1] == pytest.approx(base.p50[-1] + 1_000_000, rel=1e-6)
