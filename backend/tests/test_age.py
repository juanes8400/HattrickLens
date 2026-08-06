"""Age (edad Hattrick: años + días, 112 días/año). Sin tests hasta ahora
pese a usarse en varios motores (pricing, academy, training) — HL-161 añade
`add_days` (retroceder en el tiempo) y merece cobertura propia."""
import pytest

from app.domain.value_objects.skill import Age


def test_add_weeks_forward() -> None:
    # 20a 100d + 2 semanas (14 días) = 114 días totales extra -> cruza el año
    assert Age(20, 100).add_weeks(2) == Age(21, 2)


def test_add_days_backward_reconstructs_past_age() -> None:
    """HL-161: edad de hoy menos los días transcurridos desde una fecha
    pasada = edad en esa fecha pasada — confirmado por el usuario 2026-08-04
    (Aydin Davey: 22a 35d hoy, vendido hace 11 días -> 22a 24d en la venta)."""
    today = Age(22, 35)
    assert today.add_days(-11) == Age(22, 24)


def test_add_days_backward_across_a_year_boundary() -> None:
    assert Age(20, 5).add_days(-10) == Age(19, 107)


def test_add_days_negative_result_raises() -> None:
    with pytest.raises(ValueError):
        Age(0, 0).add_days(-1)
