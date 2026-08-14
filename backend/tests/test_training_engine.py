"""Training Engine. Spec: docs/spec/TRAINING_ENGINE.md."""
import pytest

from app.domain.engines.training_engine import (
    TrainingSetup,
    age_factor,
    assistant_factor,
    coach_factor,
    compare_training_types,
    default_setup,
    forecast_level_chain,
    forecast_pops,
    model_info,
    training_exposure,
    weeks_to_next_level,
)

# The validation squad: two assistant coaches at level 5, so the SUM OF THEIR
# LEVELS is 10 — the game's ceiling. Excellent coach, 100% intensity. The
# stamina share is the one quantity the data cannot separate from the coach
# factor; 12.5% is what an excellent coach implies.
PULGAS = TrainingSetup(
    skill="passing", intensity=100, stamina_share=12.5,
    coach_level=8, coach_is_excellent=True, assistant_level_sum=10,
)

SQUAD = [
    {"name": "Florin Tilvar", "ht_player_id": 1, "age_years": 20, "age_days": 83,
     "skills": {"passing": 4}},
    {"name": "Aydin Davey", "ht_player_id": 2, "age_years": 22, "age_days": 20,
     "skills": {"passing": 5}},
    {"name": "Raúl Cobos", "ht_player_id": 3, "age_years": 28, "age_days": 68,
     "skills": {"passing": 15}},
]


# ── The canonical formula ───────────────────────────────────────────────────

def test_formula_terms_behave_as_specified() -> None:
    # 1 + Σlevels × 3.5% is a speed multiplier, where Σlevels is the sum of the levels of at
    # most two assistants — 5+5, 3+2, 1+0 — and never a head-count.
    assert assistant_factor(0) == 1.0
    assert assistant_factor(10) == pytest.approx(1.35, rel=1e-6)
    assert assistant_factor(5 + 5) == assistant_factor(10)
    assert assistant_factor(3 + 2) == assistant_factor(5)
    assert assistant_factor(1 + 0) == assistant_factor(1)

    # 1 + 10% × max(7 − level, 0) − 5% if excellent.
    # The penalty applies BELOW the reference level; above it the term is zero,
    # which is what keeps the excellent bonus from being counted twice.
    assert coach_factor(7, False) == pytest.approx(1.0)
    assert coach_factor(7, True) == pytest.approx(0.95)
    assert coach_factor(5, False) == pytest.approx(1.20)      # weak coach costs
    assert coach_factor(8, False) == pytest.approx(1.00)      # no extra reward
    assert coach_factor(8, True) == coach_factor(7, True)     # bonus only once

    # 1 + 6% × (age − 17)
    assert age_factor(17) == pytest.approx(1.0)
    assert age_factor(27) == pytest.approx(1.60)


def test_age_is_the_dominant_factor() -> None:
    young = weeks_to_next_level("passing", 8, 20, setup=PULGAS).weeks_to_next_level
    old = weeks_to_next_level("passing", 8, 28, setup=PULGAS).weeks_to_next_level
    assert old > young * 1.3


def test_current_level_does_not_affect_the_canonical_formula() -> None:
    """A deliberate property: the formula has no level term."""
    low = weeks_to_next_level("passing", 3, 24, setup=PULGAS).weeks_to_next_level
    high = weeks_to_next_level("passing", 17, 24, setup=PULGAS).weeks_to_next_level
    assert low == high


def test_alternative_model_reintroduces_a_level_effect() -> None:
    low = weeks_to_next_level(
        "passing", 3, 24, setup=PULGAS, use_alternative_age_model=True
    ).weeks_to_next_level
    high = weeks_to_next_level(
        "passing", 17, 24, setup=PULGAS, use_alternative_age_model=True
    ).weeks_to_next_level
    assert high > low


# ── Per-skill base times: the gap the first implementation had ──────────────

def test_each_skill_has_its_own_base_time() -> None:
    keeper = weeks_to_next_level("keeper", 5, 17, setup=TrainingSetup("keeper"))
    defending = weeks_to_next_level("defending", 5, 17, setup=TrainingSetup("defending"))
    assert defending.base_weeks == 2 * keeper.base_weeks
    assert defending.weeks_to_next_level > keeper.weeks_to_next_level


def test_base_weeks_match_the_specification() -> None:
    assert model_info()["baseWeeks"] == {
        "stamina": 1, "keeper": 4, "defending": 8, "playmaking": 7,
        "passing": 5, "winger": 5, "scoring": 6, "set_pieces": 2,
    }


# ── Setup modifiers ─────────────────────────────────────────────────────────

def test_the_assistant_term_spans_exactly_the_games_range() -> None:
    """From 0 to 5+5, assistants add up to 35% training speed."""
    def at(n: int) -> float:
        return weeks_to_next_level(
            "passing", 8, 24, setup=TrainingSetup("passing", assistant_level_sum=n)
        ).weeks_to_next_level

    assert at(10) / at(0) == pytest.approx(1 / 1.35, rel=0.01)  # weeks are rounded
    assert at(0) > at(5) > at(10)


def test_the_level_sum_cannot_exceed_two_assistants_at_level_five() -> None:
    """A head-count passed where a level sum belongs is a silent, expensive
    error: every forecast shifts and nothing looks wrong. So it raises."""
    TrainingSetup("passing", assistant_level_sum=10)          # 5+5, the ceiling
    for impossible in (11, 13, 27):
        with pytest.raises(ValueError, match="SUM OF LEVELS"):
            TrainingSetup("passing", assistant_level_sum=impossible)
    with pytest.raises(ValueError):
        TrainingSetup("passing", assistant_level_sum=-1)


def test_the_bonus_coefficient_has_the_correct_ceiling_speed() -> None:
    """5+5 assistants yield the documented 35% speed bonus."""
    assert pytest.approx(0.35) == 10 * 0.035
    assert assistant_factor(10) == pytest.approx(1.35)


def test_excellent_coach_is_five_percent_faster() -> None:
    plain = weeks_to_next_level(
        "passing", 8, 24, setup=TrainingSetup("passing", coach_is_excellent=False)
    ).weeks_to_next_level
    excellent = weeks_to_next_level(
        "passing", 8, 24, setup=TrainingSetup("passing", coach_is_excellent=True)
    ).weeks_to_next_level
    assert excellent < plain


def test_stamina_share_lengthens_the_main_skill_wait() -> None:  # noqa: D401
    """The primary skill receives only the capacity left after stamina work."""
    full = weeks_to_next_level(
        "passing", 8, 24, setup=TrainingSetup("passing", stamina_share=0)
    ).weeks_to_next_level
    shared = weeks_to_next_level(
        "passing", 8, 24, setup=TrainingSetup("passing", stamina_share=25)
    ).weeks_to_next_level
    assert shared == pytest.approx(full / 0.75, rel=0.02)


def test_lower_intensity_adds_weeks() -> None:
    full = weeks_to_next_level(
        "passing", 8, 24, setup=TrainingSetup("passing", intensity=100)
    ).weeks_to_next_level
    reduced = weeks_to_next_level(
        "passing", 8, 24, setup=TrainingSetup("passing", intensity=80)
    ).weeks_to_next_level
    assert reduced > full


# ── Fallback setup ───────────────────────────────────────────────────────────
# HL-2xx, 2026-08-14: four call sites used to hardcode
# `coach_level=8, coach_is_excellent=True, assistant_level_sum=10` (one of
# them with `stamina_share=0`, silently contradicting the yaml's own
# `default_stamina_share`). `default_setup()` is the single place that now
# owns those compatibility defaults.

def test_default_setup_reads_its_defaults_from_config() -> None:
    setup = default_setup("passing")
    assert setup.assistant_level_sum == 10   # default_assistant_level_sum in training.yaml
    assert setup.coach_level == 8
    assert setup.coach_is_excellent is True
    assert setup.intensity == 100
    assert setup.stamina_share == pytest.approx(12.5)  # default_stamina_share in training.yaml


def test_default_setup_prefers_a_real_reading_over_the_default() -> None:
    """`stamina_share=0` from a real sync must NOT be treated as "missing" —
    only `None` (no training.xml at all) falls back to the config default."""
    real = default_setup("passing", intensity=90, stamina_share=0)
    assert real.intensity == 90
    assert real.stamina_share == 0

    missing = default_setup("passing", stamina_share=None)
    assert missing.stamina_share == pytest.approx(12.5)


# ── Minutes and position ────────────────────────────────────────────────────

def test_training_exposure_follows_the_ninety_minute_rule() -> None:
    assert training_exposure(90, "full") == 1.0
    assert training_exposure(45, "full") == 0.5
    assert training_exposure(90, "partial") == 0.5
    assert training_exposure(90, "none") == 0.0
    assert training_exposure(120, "full") == 1.0


def test_partial_exposure_doubles_the_wait() -> None:
    full = weeks_to_next_level("passing", 8, 24, setup=PULGAS, exposure=1.0)
    half = weeks_to_next_level("passing", 8, 24, setup=PULGAS, exposure=0.5)
    assert half.weeks_to_next_level == pytest.approx(full.weeks_to_next_level * 2, rel=0.02)


# ── Forecast ────────────────────────────────────────────────────────────────

def test_forecast_orders_by_soonest_pop() -> None:
    out = forecast_pops(SQUAD, PULGAS)
    assert out[0].player == "Florin Tilvar"          # youngest
    assert out == sorted(out, key=lambda f: f.weeks_remaining)


def test_forecast_declares_missing_history() -> None:
    assert all(f.confidence == "no_history" for f in forecast_pops(SQUAD, PULGAS))
    with_history = forecast_pops(SQUAD, PULGAS, weeks_already_trained={1: 3.0})
    first = next(f for f in with_history if f.player == "Florin Tilvar")
    assert first.confidence == "estimated"
    assert 0 < first.progress < 1


def test_older_players_are_expensive_to_train() -> None:
    weeks = {f.player: f.weeks_remaining for f in forecast_pops(SQUAD, PULGAS)}
    assert weeks["Raúl Cobos"] > weeks["Florin Tilvar"] * 1.3


# ── Cascading multi-level forecast (HL-2xx, "Previsión subidas") ───────────

def test_forecast_level_chain_climbs_one_level_at_a_time() -> None:
    chain = forecast_level_chain("passing", 14, 27, 0, PULGAS, max_levels=6)
    assert [m.level for m in chain] == [15, 16, 17, 18, 19, 20]


def test_forecast_level_chain_stops_at_the_top_of_the_scale() -> None:
    """Level 20 ("divino") is the last real name in SKILL_LEVELS — cascading
    a forecast past it would compound a guess, so the chain stops there
    even if the caller asks for more levels."""
    chain = forecast_level_chain("passing", 18, 27, 0, PULGAS, max_levels=15)
    assert [m.level for m in chain] == [19, 20]

    already_there = forecast_level_chain("passing", 20, 27, 0, PULGAS, max_levels=5)
    assert already_there == []


def test_forecast_level_chain_weeks_and_age_compound() -> None:
    """Age feeds back into each next level's speed — a real property of the
    formula, not just cumulative addition — so later levels must cost more
    weeks than the first, and the projected age must climb through the
    chain (never reset or go backwards)."""
    chain = forecast_level_chain("passing", 10, 20, 0, PULGAS, max_levels=5)
    weeks_per_level = [m.weeks_for_this_level for m in chain]
    assert weeks_per_level == sorted(weeks_per_level)  # strictly non-decreasing
    assert weeks_per_level[-1] > weeks_per_level[0]

    cumulative = [m.weeks_from_now for m in chain]
    assert cumulative == sorted(cumulative)

    ages = [(m.age_years, m.age_days) for m in chain]
    assert ages == sorted(ages)


# ── Choosing what to train ──────────────────────────────────────────────────

def test_compare_training_types_ranks_by_speed() -> None:
    ranking = compare_training_types(SQUAD, PULGAS)
    assert set(ranking) == set(model_info()["baseWeeks"])
    assert list(ranking.values()) == sorted(ranking.values())
    assert next(iter(ranking)) == "stamina"          # cheapest base time
