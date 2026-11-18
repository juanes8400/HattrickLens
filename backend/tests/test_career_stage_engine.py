"""Tests del motor puro de preclasificación de jugadores, HL-15x #87."""
from app.domain.engines.career_stage_engine import classify_career_stage


def _sin_historial(edad: int, percentil: float | None = 50.0, bajan: int = 0):
    return classify_career_stage(
        age_years=edad, age_days=0, skills_rising=0, skills_falling=bajan, skills_stable=7 - bajan,
        has_sufficient_history=False, squad_percentile=percentil, leadership=5, loyalty=10,
    )


def test_sin_historial_la_etapa_es_provisional_y_sale_de_la_edad() -> None:
    # 6.11.0: antes salía «sin_historial» a cualquier edad.
    joven, pico, veterano = _sin_historial(19), _sin_historial(25, 90.0), _sin_historial(31)
    assert (joven.stage, pico.stage, veterano.stage) == ("promesa", "pico", "veterano")
    assert joven.provisional and pico.provisional and veterano.provisional
    assert "provisional" in pico.confidence
    assert "percentil 90" in pico.rationale


def test_provisional_entre_22_y_27_usa_el_percentil() -> None:
    assert _sin_historial(24, 20.0).stage == "rotacion"
    assert _sin_historial(24, None).stage == "pico"


def test_sin_historial_nunca_sale_en_declive() -> None:
    # Bajar habilidades es justo lo que no se puede ver con una sola foto.
    assert _sin_historial(36, bajan=5).stage == "veterano"
    assert "En declive" in _sin_historial(36).rationale


def test_con_historial_no_es_provisional() -> None:
    result = classify_career_stage(
        age_years=25, age_days=0, skills_rising=1, skills_falling=0, skills_stable=6,
        has_sufficient_history=True, squad_percentile=70.0, leadership=3, loyalty=8,
    )
    assert not result.provisional


def test_young_player_with_rising_skills_is_promesa() -> None:
    result = classify_career_stage(
        age_years=18, age_days=0, skills_rising=4, skills_falling=0, skills_stable=3,
        has_sufficient_history=True, squad_percentile=50.0, leadership=1, loyalty=5,
    )
    assert result.stage == "promesa"
    assert "4" in result.rationale


def test_young_player_without_rising_skills_is_still_promesa_but_says_so() -> None:
    result = classify_career_stage(
        age_years=19, age_days=0, skills_rising=0, skills_falling=0, skills_stable=7,
        has_sufficient_history=True, squad_percentile=50.0, leadership=1, loyalty=5,
    )
    assert result.stage == "promesa"
    assert "no muestra subidas" in result.rationale


def test_peak_age_high_percentile_is_en_su_pico_alta_confianza() -> None:
    result = classify_career_stage(
        age_years=25, age_days=0, skills_rising=1, skills_falling=1, skills_stable=5,
        has_sufficient_history=True, squad_percentile=70.0, leadership=3, loyalty=8,
    )
    assert result.stage == "pico"
    assert result.confidence == "alta"


def test_peak_age_low_percentile_is_pieza_de_rotacion() -> None:
    result = classify_career_stage(
        age_years=25, age_days=0, skills_rising=1, skills_falling=1, skills_stable=5,
        has_sufficient_history=True, squad_percentile=20.0, leadership=3, loyalty=8,
    )
    assert result.stage == "rotacion"


def test_peak_age_without_percentile_falls_back_to_pico_with_lower_confidence() -> None:
    result = classify_career_stage(
        age_years=25, age_days=0, skills_rising=1, skills_falling=1, skills_stable=5,
        has_sufficient_history=True, squad_percentile=None, leadership=3, loyalty=8,
    )
    assert result.stage == "pico"
    assert result.confidence != "alta"


def test_veteran_with_falling_skills_and_low_age_factor_is_declive() -> None:
    result = classify_career_stage(
        age_years=32, age_days=0, skills_rising=0, skills_falling=3, skills_stable=4,
        has_sufficient_history=True, squad_percentile=40.0, leadership=5, loyalty=15,
    )
    assert result.stage == "declive"


def test_veteran_with_stable_skills_is_veterano_estable() -> None:
    result = classify_career_stage(
        age_years=32, age_days=0, skills_rising=2, skills_falling=1, skills_stable=4,
        has_sufficient_history=True, squad_percentile=40.0, leadership=5, loyalty=15,
    )
    assert result.stage == "veterano"


def test_signals_always_carry_the_raw_inputs() -> None:
    result = classify_career_stage(
        age_years=25, age_days=56, skills_rising=1, skills_falling=1, skills_stable=5,
        has_sufficient_history=True, squad_percentile=70.0, leadership=3, loyalty=8,
    )
    assert result.signals["ageYears"] == 25
    assert result.signals["ageDays"] == 56
    assert result.signals["squadPercentile"] == 70.0
    assert result.signals["leadership"] == 3
    assert result.signals["loyalty"] == 8
    assert 0.0 < result.signals["ageFactor"] < 2.0
