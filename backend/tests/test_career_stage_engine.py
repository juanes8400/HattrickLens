"""Tests del motor puro de preclasificación de jugadores — HL-15x #87."""
from app.domain.engines.career_stage_engine import classify_career_stage


def test_insufficient_history_overrides_everything() -> None:
    result = classify_career_stage(
        age_years=25, age_days=0, skills_rising=5, skills_falling=0, skills_stable=2,
        has_sufficient_history=False, squad_percentile=90.0, leadership=5, loyalty=10,
    )
    assert result.stage == "sin_historial"
    assert "snapshots" in result.rationale.lower()


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
