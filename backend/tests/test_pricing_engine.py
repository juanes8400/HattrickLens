"""HL-141 · Sueldo semanal estimado y factor de edad.

2026-08-11: se retiró el modelo de valor de mercado (`value_player` y todo
lo derivado de él) — sus coeficientes eran un supuesto propio sin ventas
reales que lo respalden. Lo que queda aquí es lo verificable: la curva de
edad (reutilizada por `career_stage_engine`) y la fórmula de sueldo del
Manual no Escrito.
"""
import pytest

from app.domain.engines.pricing_engine import age_factor, estimate_salary


def test_age_factor_peaks_young_and_decays_with_age() -> None:
    assert age_factor(17) > age_factor(25) > age_factor(31)


def test_age_factor_keeps_decaying_past_the_table() -> None:
    """Más allá del último año de la tabla (35), el factor debe seguir
    cayendo de forma monótona. Un fallback constante recalculado cada año
    producía un diente de sierra: el valor subía en cada cumpleaños en vez
    de seguir bajando, lo que hacía parecer rentable esperar solo por el
    efecto del redondeo de edad."""
    factors = [age_factor(years, 0) for years in range(35, 46)]
    assert factors == sorted(factors, reverse=True)
    assert factors[-1] > 0  # nunca llega a cero


def test_estimate_salary_matches_the_published_table_for_a_single_skill() -> None:
    """Manual no Escrito, tabla de sueldos: Defensa Bueno (nivel 7) ~ $330,
    Defensa Excelente (nivel 8) ~ $450, con el resto de habilidades en 0."""
    bueno = estimate_salary({"defending": 7})
    assert bueno.weekly_salary == pytest.approx(330, abs=15)
    assert bueno.main_skill == "defending"

    excelente = estimate_salary({"defending": 8})
    assert excelente.weekly_salary == pytest.approx(450, abs=15)
    assert excelente.weekly_salary > bueno.weekly_salary


def test_estimate_salary_picks_the_skill_with_the_highest_component_as_main() -> None:
    """La habilidad principal es la que paga más, no la de nivel más alto —
    Lateral 12 paga menos que Jugadas 12 según la tabla del manual."""
    est = estimate_salary({"winger": 12, "playmaking": 12})
    assert est.main_skill == "playmaking"


def test_estimate_salary_set_pieces_bonus_increases_salary() -> None:
    base = estimate_salary({"scoring": 10})
    with_pp = estimate_salary({"scoring": 10}, set_pieces=15)
    assert with_pp.weekly_salary > base.weekly_salary


def test_estimate_salary_with_no_skills_is_just_the_base() -> None:
    est = estimate_salary({})
    assert est.weekly_salary == 250
