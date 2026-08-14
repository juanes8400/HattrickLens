"""Tabla de referencia de Resistencia (Federación Ocerin)."""
from app.domain.value_objects.stamina_reference import (
    age_after_weeks,
    stamina_forecast_level,
)


def test_looks_up_exact_bucket() -> None:
    # Edad 20, columna "16%-20%" (índice 2) = 8 (Excelente).
    assert stamina_forecast_level(20, 18.0) == 8
    # Misma edad, columna "5%-10%" (índice 0) = 6 (Aceptable).
    assert stamina_forecast_level(20, 7.0) == 6


def test_bucket_lower_bound_is_inclusive() -> None:
    # 11 es el límite inferior exacto del bucket "11%-15%".
    assert stamina_forecast_level(20, 11.0) == stamina_forecast_level(20, 15.0)
    assert stamina_forecast_level(20, 10.9) != stamina_forecast_level(20, 11.0)


def test_percentage_outside_table_range_clamps_to_nearest_bucket() -> None:
    """Menos o más esfuerzo real del que cubre la tabla cae al extremo
    conocido más cercano, en vez de quedarse sin previsión."""
    assert stamina_forecast_level(20, 0.0) == stamina_forecast_level(20, 5.0)
    assert stamina_forecast_level(20, 99.0) == stamina_forecast_level(20, 30.0)


def test_age_outside_table_returns_none_instead_of_extrapolating() -> None:
    assert stamina_forecast_level(16, 20.0) is None
    assert stamina_forecast_level(37, 20.0) is None
    assert stamina_forecast_level(17, 20.0) is not None
    assert stamina_forecast_level(36, 20.0) is not None


def test_higher_training_never_yields_a_worse_level_at_the_same_age() -> None:
    """La tabla original es monótona por columnas — más esfuerzo real de
    resistencia nunca empeora el nivel esperado a la misma edad."""
    for age in range(17, 37):
        levels = [stamina_forecast_level(age, pct) for pct in (5, 11, 16, 21, 26)]
        assert levels == sorted(levels)


def test_age_after_weeks_advances_using_the_112_day_ht_year() -> None:
    assert age_after_weeks(29, 50, 2) == (29, 64)
    # 16 semanas (una temporada completa) suman exactamente un año.
    assert age_after_weeks(29, 50, 16) == (30, 50)


def test_age_after_weeks_carries_years_forward() -> None:
    years, days = age_after_weeks(29, 110, 1)
    assert (years, days) == (30, 5)
