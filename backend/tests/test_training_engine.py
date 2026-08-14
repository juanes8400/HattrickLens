"""Public HT-Tools training formula and Lens' CHPP adapters."""
import pytest

from app.domain.engines.training_engine import (
    TrainingSetup,
    age_clock,
    age_factor,
    assistant_factor,
    coach_factor,
    compare_training_types,
    default_setup,
    forecast_level_chain,
    forecast_pops,
    inverse_age_clock,
    model_info,
    skill_cost,
    training_coefficient,
    training_exposure,
    training_mode,
    weeks_to_next_level,
)

PULGAS = TrainingSetup(
    skill="passing",
    training_type=10,
    intensity=100,
    stamina_share=12.5,
    coach_level=8,
    coach_is_excellent=True,
    assistant_level_sum=10,
)

SQUAD = [
    {"name": "Florin Tilvar", "ht_player_id": 1, "age_years": 20, "age_days": 83,
     "skills": {"passing": 4}},
    {"name": "Aydin Davey", "ht_player_id": 2, "age_years": 22, "age_days": 20,
     "skills": {"passing": 5}},
    {"name": "Raúl Cobos", "ht_player_id": 3, "age_years": 28, "age_days": 68,
     "skills": {"passing": 15}},
]


def test_public_formula_coefficients_are_ported_exactly() -> None:
    assert assistant_factor(0) == pytest.approx(0.66)
    assert assistant_factor(5) == pytest.approx(0.82)
    assert assistant_factor(10) == pytest.approx(0.98)
    assert coach_factor(4) == pytest.approx(0.774)
    assert coach_factor(7) == pytest.approx(1.0)
    assert coach_factor(8) == pytest.approx(1.045)
    assert age_factor(17) == pytest.approx(1.0)
    assert age_factor(27) == pytest.approx(0.83)


def test_piecewise_skill_cost_matches_the_published_equations() -> None:
    low = (8**1.72 - 1) / (6.0896 * 1.72)
    high = 2.45426 + (14 - 5) ** 1.96 / (4.7371 * 1.96)
    assert skill_cost(8) == pytest.approx(low)
    assert skill_cost(14) == pytest.approx(high)
    assert skill_cost(15) - skill_cost(14) > skill_cost(6) - skill_cost(5)


def test_age_clock_interpolates_and_is_invertible() -> None:
    assert age_clock(17) == pytest.approx(0)
    assert age_clock(18) == pytest.approx(16)
    assert age_clock(18.5) == pytest.approx((16 + 31.704) / 2)
    for age in (17.0, 20.75, 28.2, 34.0, 41.25):
        assert inverse_age_clock(age_clock(age)) == pytest.approx(age)


def test_current_skill_level_now_changes_the_wait() -> None:
    low = weeks_to_next_level("passing", 5, 24, setup=PULGAS).weeks_to_next_level
    high = weeks_to_next_level("passing", 14, 24, setup=PULGAS).weeks_to_next_level
    assert high > low * 2


def test_age_makes_the_same_level_slower() -> None:
    young = weeks_to_next_level("passing", 8, 20, setup=PULGAS).weeks_to_next_level
    old = weeks_to_next_level("passing", 8, 28, setup=PULGAS).weeks_to_next_level
    assert old > young


def test_chpp_training_type_selects_the_specific_mode() -> None:
    assert training_mode("passing", 7) == "short_passes"
    assert training_mode("passing", 10) == "through_passes"
    assert training_coefficient("passing", 7) == pytest.approx(0.237)
    assert training_coefficient("passing", 10) == pytest.approx(0.178)

    short = weeks_to_next_level(
        "passing", 8, 20, setup=TrainingSetup("passing", training_type=7)
    )
    through = weeks_to_next_level(
        "passing", 8, 20, setup=TrainingSetup("passing", training_type=10)
    )
    assert short.training_mode == "short_passes"
    assert through.training_mode == "through_passes"
    assert through.weeks_to_next_level > short.weeks_to_next_level


def test_sublevel_shortens_the_remaining_wait_without_fitting_it() -> None:
    integer_only = weeks_to_next_level("passing", 8, 20, setup=PULGAS)
    half_level = weeks_to_next_level(
        "passing", 8, 20, setup=PULGAS, current_sublevel=0.5
    )
    assert half_level.weeks_to_next_level < integer_only.weeks_to_next_level
    assert half_level.current_skill == pytest.approx(8.5)
    with pytest.raises(ValueError, match="sublevel"):
        weeks_to_next_level("passing", 8, 20, setup=PULGAS, current_sublevel=1)


def test_assistant_level_sum_is_capped_by_validation() -> None:
    TrainingSetup("passing", assistant_level_sum=10)
    for impossible in (11, 13, 27, -1):
        with pytest.raises(ValueError):
            TrainingSetup("passing", assistant_level_sum=impossible)


def test_more_assistants_and_a_better_coach_reduce_weeks() -> None:
    no_assistants = weeks_to_next_level(
        "passing", 8, 24, setup=TrainingSetup("passing", assistant_level_sum=0)
    ).weeks_to_next_level
    max_assistants = weeks_to_next_level(
        "passing", 8, 24, setup=TrainingSetup("passing", assistant_level_sum=10)
    ).weeks_to_next_level
    assert max_assistants < no_assistants

    level_4 = weeks_to_next_level(
        "passing", 8, 24, setup=TrainingSetup("passing", coach_level=4)
    ).weeks_to_next_level
    level_5 = weeks_to_next_level(
        "passing", 8, 24, setup=TrainingSetup("passing", coach_level=8)
    ).weeks_to_next_level
    assert level_5 < level_4


def test_intensity_stamina_and_exposure_have_the_right_direction() -> None:
    full = weeks_to_next_level(
        "passing", 8, 24,
        setup=TrainingSetup("passing", intensity=100, stamina_share=0),
    ).weeks_to_next_level
    reduced_intensity = weeks_to_next_level(
        "passing", 8, 24,
        setup=TrainingSetup("passing", intensity=80, stamina_share=0),
    ).weeks_to_next_level
    stamina_diversion = weeks_to_next_level(
        "passing", 8, 24,
        setup=TrainingSetup("passing", intensity=100, stamina_share=25),
    ).weeks_to_next_level
    half_exposure = weeks_to_next_level(
        "passing", 8, 24,
        setup=TrainingSetup("passing", intensity=100, stamina_share=0), exposure=0.5,
    ).weeks_to_next_level
    assert reduced_intensity > full
    assert stamina_diversion > full
    assert half_exposure > full


def test_default_setup_uses_config_and_preserves_real_zero() -> None:
    setup = default_setup("passing")
    assert setup.assistant_level_sum == 10
    assert setup.coach_level == 8
    assert setup.stamina_share == pytest.approx(12.5)

    real = default_setup("passing", training_type=10, intensity=90, stamina_share=0)
    assert real.training_type == 10
    assert real.intensity == 90
    assert real.stamina_share == 0


def test_training_exposure_follows_the_ninety_minute_rule() -> None:
    assert training_exposure(90, "full") == 1.0
    assert training_exposure(45, "full") == 0.5
    assert training_exposure(90, "partial") == 0.5
    assert training_exposure(90, "none") == 0.0
    assert training_exposure(120, "full") == 1.0


def test_forecast_orders_by_soonest_pop_and_declares_unknown_sublevel() -> None:
    out = forecast_pops(SQUAD, PULGAS)
    assert out == sorted(out, key=lambda forecast: forecast.weeks_remaining)
    assert all(forecast.confidence == "integer_level_only" for forecast in out)
    with_history = forecast_pops(SQUAD, PULGAS, weeks_already_trained={1: 1.0})
    observed = next(forecast for forecast in with_history if forecast.player == "Florin Tilvar")
    assert observed.confidence == "estimated_from_pop"
    assert 0 < observed.progress < 1


def test_forecast_level_chain_compounds_skill_cost_and_age() -> None:
    chain = forecast_level_chain("passing", 14, 27, 0, PULGAS, max_levels=6)
    assert [milestone.level for milestone in chain] == [15, 16, 17, 18, 19, 20]
    assert [m.weeks_from_now for m in chain] == sorted(m.weeks_from_now for m in chain)
    assert chain[-1].weeks_for_this_level > chain[0].weeks_for_this_level
    assert forecast_level_chain("passing", 20, 27, 0, PULGAS) == []


def test_compare_training_types_uses_only_supported_technical_skills() -> None:
    ranking = compare_training_types(SQUAD, PULGAS)
    assert set(ranking) == {
        "keeper", "defending", "playmaking", "passing", "winger", "scoring", "set_pieces"
    }
    assert list(ranking.values()) == sorted(ranking.values())


def test_model_metadata_declares_source_and_limits() -> None:
    info = model_info()
    assert info["engine"] == "HT-Tools community formula"
    assert info["reference"]["status"] == "ported"
    assert "private-data fitting" in info["reference"]["numeric_profile"]
    assert any("subnivel" in limitation.lower() for limitation in info["limitations"])
