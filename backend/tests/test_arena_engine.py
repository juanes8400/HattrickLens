"""Tests del motor de estadio con los datos reales del Chapecoense (60.002)."""
import pytest

from app.domain.engines.arena_engine import (
    TICKET_PRICES,
    ArenaCapacity,
    Attendance,
    analyse_expansion,
    analyse_match,
    estimate_true_demand,
)

CAP = ArenaCapacity(general=34_130, preferentes=13_639, tribunas=10_808, palcos=1_425)
# Liga vs etbenianos1, 2026-07-05
LEAGUE = Attendance(general=34_130, preferentes=13_639, tribunas=5_785, palcos=1_425)
# Amistoso vs Fc Aittakorven, 2026-07-19
FRIENDLY = Attendance(general=1_441, preferentes=505, tribunas=692, palcos=61)


def test_capacity_matches_screen() -> None:
    assert CAP.total == 60_002


def test_roof_ticket_price_is_exactly_nineteen() -> None:
    """Derivado de la diferencia entre ingresos reales y a estadio lleno."""
    assert TICKET_PRICES["tribunas"] == 19.0
    diff_seats = CAP.tribunas - LEAGUE.tribunas
    assert diff_seats * TICKET_PRICES["tribunas"] == pytest.approx(630_527 - 535_090)


def test_league_match_sells_out_three_sectors() -> None:
    r = analyse_match(CAP, LEAGUE)
    assert set(r.sold_out) == {"general", "preferentes", "palcos"}
    assert r.demand_is_censored is True
    assert r.total_occupancy == pytest.approx(91.6, abs=0.1)
    assert r.occupancy["tribunas"] == pytest.approx(53.5, abs=0.1)


def test_friendly_barely_fills_the_stadium() -> None:
    r = analyse_match(CAP, FRIENDLY)
    assert r.sold_out == []
    assert r.demand_is_censored is False
    assert r.total_occupancy < 6


def test_revenue_left_on_table_is_reported() -> None:
    r = analyse_match(CAP, LEAGUE)
    assert r.revenue_left_on_table > 0
    assert r.revenue < r.revenue_if_full


def test_demand_is_flagged_as_censored_when_sold_out() -> None:
    mean, censored = estimate_true_demand(CAP, [LEAGUE, LEAGUE], "general")
    assert censored is True          # la media subestima la demanda real
    mean_roof, censored_roof = estimate_true_demand(CAP, [LEAGUE], "tribunas")
    assert censored_roof is False    # ahí sí observamos la demanda completa
    assert mean_roof == 5_785


def test_expansion_pays_off_when_demand_exists() -> None:
    r = analyse_expansion(
        added_seats={"general": 10_000},
        build_cost_per_seat={"general": 450.0},
        weekly_maintenance_per_seat=0.7,
        expected_fill_rate=0.95,       # sector agotado: se llenaría casi entero
        home_matches_per_season=7,
    )
    assert r.net_per_season > 0
    assert r.payback_weeks is not None
    assert "amortiza" in r.verdict


def test_expansion_rejected_when_seats_stay_empty() -> None:
    r = analyse_expansion(
        added_seats={"tribunas": 10_000},
        build_cost_per_seat={"tribunas": 1_000.0},
        weekly_maintenance_per_seat=3.0,
        expected_fill_rate=0.05,       # ya sobran asientos en ese sector
        home_matches_per_season=7,
    )
    assert r.net_per_season < 0
    assert r.payback_weeks is None
    assert "no compensa" in r.verdict
