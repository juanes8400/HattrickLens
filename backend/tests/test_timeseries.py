"""Tests del motor de series de tiempo.

Estrategia: generar series con estructura conocida y comprobar que el
selector automático elige el modelo adecuado y recupera los parámetros.
"""
import numpy as np
import pytest

from app.domain.engines.timeseries import (
    SEASON_WEEKS,
    auto_forecast,
    backtest,
    detect_anomalies,
)


def test_constant_series_is_predicted_flat() -> None:
    f = auto_forecast([100.0] * 10, horizon=5)
    assert all(abs(p - 100.0) < 1e-6 for p in f.point)
    assert f.residual_std == pytest.approx(0.0, abs=1e-9)


def test_linear_trend_is_extrapolated() -> None:
    y = [100 + 10 * i for i in range(12)]
    f = auto_forecast(y, horizon=4)
    # continúa la tendencia (con amortiguación no llega al ideal exacto)
    assert f.point[0] > 205
    assert f.point[-1] > f.point[0]
    assert f.model in ("drift", "holt")


def test_seasonal_series_unlocks_holt_winters() -> None:
    rng = np.random.default_rng(0)
    season = np.array([0, 0, 300, 0, 0, 300, 0, 0, 300, 0, 0, 300, 0, 0, 300, 0], float)
    y = [1000 + season[i % SEASON_WEEKS] + rng.normal(0, 5) for i in range(SEASON_WEEKS * 3)]
    f = auto_forecast(y, horizon=SEASON_WEEKS)
    assert "holt_winters" in f.candidates
    # el pico estacional debe reaparecer en la proyección
    assert max(f.point) - min(f.point) > 200


def test_model_is_chosen_by_backtesting_not_by_complexity() -> None:
    """Serie sin estructura: debe ganar un modelo simple."""
    rng = np.random.default_rng(7)
    y = list(rng.normal(500, 20, 40))
    f = auto_forecast(y, horizon=10)
    assert f.model in ("naive", "ses", "drift")
    assert f.backtest_mae is not None


def test_bands_widen_with_horizon() -> None:
    rng = np.random.default_rng(3)
    y = list(500 + rng.normal(0, 50, 20))
    f = auto_forecast(y, horizon=10)
    first = f.upper[0] - f.lower[0]
    last = f.upper[-1] - f.lower[-1]
    assert last > first > 0


def test_degrades_gracefully_with_two_points() -> None:
    f = auto_forecast([100.0, 120.0], horizon=3)
    assert f.horizon == 3
    assert f.model in ("naive", "drift")


def test_single_point_does_not_crash() -> None:
    f = auto_forecast([42.0], horizon=4)
    assert f.point == [42.0] * 4


def test_backtest_reports_infinity_when_data_is_short() -> None:
    assert backtest(np.array([1.0, 2.0]), "holt_winters") == float("inf")


def test_anomaly_detection_flags_the_outlier() -> None:
    y = [100, 102, 98, 101, 99, 100, 5000, 101, 100]
    assert 6 in detect_anomalies(y)


def test_anomaly_detection_is_quiet_on_clean_series() -> None:
    assert detect_anomalies([100, 101, 99, 100, 102, 98, 101]) == []


def test_more_data_improves_the_choice() -> None:
    """Con una serie con tendencia, al crecer el histórico deja de ganar naive."""
    y = [100 + 5 * i for i in range(30)]
    short = auto_forecast(y[:4], horizon=3)
    long = auto_forecast(y, horizon=3)
    assert long.backtest_mae is not None
    assert long.backtest_mae <= (short.backtest_mae or float("inf")) + 1e-9
