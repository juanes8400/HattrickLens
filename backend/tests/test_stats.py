"""Tests del motor de estadística genérica (HL-15x) — extraído de
rival_scouting.py para reutilizarlo en distribuciones de plantilla."""
from app.domain.engines.stats import kde_grid, percentile_rank


def test_percentile_rank_of_median_value() -> None:
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert percentile_rank(values, 30.0) == 60.0  # 3 de 5 son <= 30


def test_percentile_rank_of_min_and_max() -> None:
    values = [10.0, 20.0, 30.0]
    assert round(percentile_rank(values, 10.0), 2) == 33.33
    assert percentile_rank(values, 30.0) == 100.0


def test_percentile_rank_empty_values() -> None:
    assert percentile_rank([], 5.0) == 0.0


def test_percentile_rank_ties_count_as_below_or_equal() -> None:
    values = [5.0, 5.0, 5.0, 10.0]
    assert percentile_rank(values, 5.0) == 75.0


def test_kde_grid_has_padding_around_values() -> None:
    values = [10.0, 20.0, 30.0]
    grid = kde_grid(values, grid_points=50)
    assert len(grid) == 50
    assert grid[0] < 10.0
    assert grid[-1] > 30.0


def test_kde_grid_handles_single_value() -> None:
    grid = kde_grid([42.0], grid_points=10)
    assert len(grid) == 10
    assert grid[0] < 42.0 < grid[-1]


def test_kde_grid_handles_empty_values() -> None:
    grid = kde_grid([], grid_points=10)
    assert len(grid) == 10
