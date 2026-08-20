"""Fidelidad: una sola fórmula basada en días desde la compra."""
from math import floor, sqrt

from app.domain.engines.loyalty_engine import (
    days_for_level,
    loyalty_decimal,
    loyalty_level,
    loyalty_progress_pct,
    model_info,
)


def test_known_squad_points_fit_the_formula() -> None:
    expected = {
        1: 2,
        5: 3,
        6: 3,
        9: 4,
        12: 4,
        18: 5,
        21: 5,
        27: 6,
        43: 7,
        91: 10,
        172: 14,
        275: 18,
        459: 20,
        650: 20,
        1801: 20,
    }
    assert {days: loyalty_level(days) for days in expected} == expected


def test_integer_level_thresholds() -> None:
    expected_days = [
        0, 1, 4, 9, 15, 24, 34, 46, 60, 76,
        94, 113, 135, 158, 183, 210, 239, 269, 302, 336,
    ]
    assert [days_for_level(level) for level in range(1, 21)] == expected_days
    for level, day in enumerate(expected_days, start=1):
        assert loyalty_level(day) == level
        if day > 0:
            assert (loyalty_level(day - 1) or 0) < level


def test_level_is_clamped_between_one_and_twenty() -> None:
    assert loyalty_level(None) is None
    assert loyalty_level(-50) == 1
    assert loyalty_level(0) == 1
    assert loyalty_level(336) == 20
    assert loyalty_level(10_000) == 20


def test_decimal_is_the_same_curve_before_floor() -> None:
    value = loyalty_decimal(91)
    assert value is not None
    assert int(value) == loyalty_level(91)
    assert loyalty_decimal(0) == 1.0
    assert loyalty_decimal(336) == 20.0
    assert loyalty_decimal(10_000) == 20.0
    for level in range(2, 21):
        day_before = days_for_level(level) - 1
        value_before = loyalty_decimal(day_before)
        assert value_before is not None
        assert int(value_before) == loyalty_level(day_before)


def test_progress_bar_preserves_decimals_from_the_continuous_curve() -> None:
    raw = 1 + 19 * sqrt(277 / 336)
    assert loyalty_progress_pct(277) == round((raw - floor(raw)) * 100, 2)
    assert loyalty_progress_pct(277) != round(loyalty_progress_pct(277) or 0)
    assert loyalty_progress_pct(336) == 100.0


def test_model_info_exposes_formula_and_all_thresholds() -> None:
    info = model_info()
    assert info["fullDays"] == 336
    assert info["seasons"] == 3
    assert info["maxLevel"] == 20
    assert len(info["thresholds"]) == 20
    assert info["thresholds"][-1] == {"level": 20, "day": 336}
    assert info["reference"]["status"] == "structural"
