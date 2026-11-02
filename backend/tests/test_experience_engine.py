"""Experience Engine. Spec: docs/spec/EXPERIENCE_ENGINE.md

Two things are tested here and they differ in kind.

The per-match point values are *verified*: they reconstruct Hattrick Control's
"Suma" column for 19 real players with zero error, so they are asserted exactly
(now in Hattrick's own scale, points_per_level=100, see experience.yaml's
2026-08-05 cross-check note: same proportions as the old 28-point profile,
each match type just ×3.5).

The points needed per level is *measured*. The specification says 100; the engine
does not hardcode it. It reports the mean and standard deviation of the points
players actually held when they levelled, keeps the configured value while the
evidence is thin, and always says which of the two it used.
"""
import pytest

from app.domain.engines.experience_engine import (
    Measurement,
    LevelUp,
    MatchCount,
    measure,
    detect_level_ups,
    matches_to_next_level,
    model_info,
    points,
    progress,
    recommend_captain,
    weeks_to_next_level,
)

# Verified exactly against Hattrick Control's "Suma" column for 19 players:
# (international friendlies, league matches, expected points). Original
# Suma values (old 28-point scale) ×3.5, see module docstring.
HC_SUMS = [
    (2, 2, 8.4), (3, 2, 9.1), (3, 1, 5.6), (4, 1, 6.3), (4, 0, 2.8), (1, 1, 4.2),
    (2, 2, 8.4), (3, 2, 9.1), (2, 2, 8.4), (3, 1, 5.6), (2, 1, 4.9), (2, 0, 1.4),
    (3, 0, 2.1), (3, 0, 2.1), (2, 0, 1.4), (3, 0, 2.1), (4, 0, 2.8), (3, 0, 2.1),
    (4, 0, 2.8),
]


# ── Point values: verified, so asserted exactly ─────────────────────────────

@pytest.mark.parametrize(("intl", "league", "expected"), HC_SUMS)
def test_point_values_reconstruct_hattrick_control(
    intl: int, league: int, expected: float
) -> None:
    got = points(MatchCount(league=league, friendly_international=intl))
    assert got == pytest.approx(expected, abs=1e-9)


def test_match_values_follow_the_specification() -> None:
    assert points({"league": 1}) == pytest.approx(3.5)
    assert points({"friendly": 10}) == pytest.approx(3.5)
    assert points({"friendly_international": 1}) == pytest.approx(0.7)
    assert points({"cup": 1}) == pytest.approx(7.0)
    assert points({"cup_secondary": 1}) == pytest.approx(1.75)
    assert points({"qualification": 1}) == pytest.approx(7.0)
    assert points({"tournament": 20}) == 0.0


def test_new_match_types_from_tabla_experiencia() -> None:
    """2026-08-05: Masters, amistoso de selección y partidos juveniles,
    cotejados contra docs/reference/tabla_experiencia.html."""
    assert points({"masters": 1}) == pytest.approx(17.5)
    assert points({"national_team_friendly": 1}) == pytest.approx(3.5)
    assert points({"youth_league": 1}) == pytest.approx(3.5)
    assert points({"youth_friendly": 1}) == pytest.approx(0.35)


def test_match_count_and_plain_dict_agree() -> None:
    assert points(MatchCount(league=14, friendly_international=3)) == points(
        {"league": 14, "friendly_international": 3}
    )


# ── Measurement: reported NEXT TO the configured value, never instead ───────

def test_the_threshold_never_moves_however_many_level_ups_are_seen() -> None:
    """2026-11-02. Antes esto era al revés: con cinco subidas el motor
    sustituía el umbral por la media observada. Eso es ajustar el parámetro de
    una fórmula a los datos privados de la cuenta, prohibido desde el
    2026-08-14, y además innecesario con los 100 comprobados en el juego."""
    vacio = measure([])
    assert vacio.points_per_level == 100
    assert vacio.observations == 0
    assert vacio.observed_mean is None
    assert vacio.std_dev is None

    muchas = measure([LevelUp(f"p{i}", 4, 5, 26.0) for i in range(60)])
    assert muchas.points_per_level == 100          # ni con sesenta
    assert muchas.observed_mean == pytest.approx(26.0)
    assert muchas.observations == 60


def test_what_was_observed_travels_beside_it() -> None:
    med = measure([
        LevelUp("A", 3, 4, 96.0), LevelUp("B", 5, 6, 104.0),
        LevelUp("C", 4, 5, 98.0), LevelUp("D", 6, 7, 102.0),
    ])
    assert med.points_per_level == 100
    assert med.observed_mean == pytest.approx(100.0)
    assert med.std_dev is not None and med.std_dev > 0


def test_standard_deviation_is_what_makes_the_check_honest() -> None:
    """A tight sample and a scattered one can share a mean. Only the deviation
    and the interval tell them apart, the reason for measuring at all."""
    tight = measure([LevelUp(f"p{i}", 3, 4, 28.0) for i in range(6)])
    assert tight.std_dev == pytest.approx(0.0)
    assert tight.confidence_interval == (28.0, 28.0)

    scattered = measure([
        LevelUp("a", 3, 4, 22.0), LevelUp("b", 3, 4, 34.0),
        LevelUp("c", 3, 4, 25.0), LevelUp("d", 3, 4, 31.0),
        LevelUp("e", 3, 4, 24.0), LevelUp("f", 3, 4, 32.0),
    ])
    assert scattered.observed_mean == pytest.approx(28.0)
    assert scattered.std_dev > 4
    low, high = scattered.confidence_interval
    assert low < 28.0 < high
    assert high - low > 5              # same mean, and not yet to be trusted


def test_interval_narrows_as_observations_accumulate() -> None:
    few = measure([LevelUp(f"p{i}", 3, 4, 26.0 + (i % 3)) for i in range(6)])
    many = measure([LevelUp(f"p{i}", 3, 4, 26.0 + (i % 3)) for i in range(60)])
    assert many.std_dev == pytest.approx(few.std_dev, rel=0.20)

    def width(c: Measurement) -> float:
        return c.confidence_interval[1] - c.confidence_interval[0]

    assert width(many) < width(few) / 2


def test_the_check_says_whether_the_configured_value_agrees() -> None:
    """Es para lo que sirve medir: ver si el número en uso cae dentro de lo
    observado. Si no cae, se dice; no se cambia."""
    cuadra = measure([LevelUp(f"p{i}", 3, 4, 99.0 + (i % 3)) for i in range(8)])
    assert cuadra.agrees is True

    no_cuadra = measure([LevelUp(f"p{i}", 3, 4, 26.0 + (i % 3)) for i in range(8)])
    assert no_cuadra.agrees is False
    assert no_cuadra.points_per_level == 100       # y aun así no se mueve

    assert measure([]).agrees is None


def test_measurement_breaks_down_by_starting_level() -> None:
    """If the cost per level turns out to depend on the level, it shows up here
    instead of being averaged away."""
    med = measure([
        LevelUp("a", 3, 4, 25.0), LevelUp("b", 3, 4, 25.0),
        LevelUp("c", 8, 9, 31.0), LevelUp("d", 8, 9, 31.0),
        LevelUp("e", 5, 6, 28.0), LevelUp("f", 6, 7, 28.0),
    ])
    assert med.by_level[3] == pytest.approx(25.0)
    assert med.by_level[8] == pytest.approx(31.0)
    assert 5 not in med.by_level      # a single sample is not reported


# ── Detecting level-ups from synchronised history ───────────────────────────

def test_level_ups_are_detected_from_consecutive_snapshots() -> None:
    found = detect_level_ups([
        ("Raúl", 4, 20.0), ("Raúl", 4, 26.0), ("Raúl", 5, 1.0),
        ("Hugo", 2, 10.0), ("Hugo", 2, 27.0), ("Hugo", 3, 0.5),
    ])
    assert len(found) == 2
    raul = next(f for f in found if f.player == "Raúl")
    assert (raul.from_level, raul.to_level) == (4, 5)
    # The cost is what he held just before crossing, not after the reset.
    assert raul.points_accumulated == pytest.approx(26.0)


def test_no_level_up_means_no_observation() -> None:
    assert detect_level_ups([("A", 3, 10.0), ("A", 3, 15.0), ("A", 3, 20.0)]) == []


def test_first_sighting_of_a_player_is_never_a_level_up() -> None:
    assert detect_level_ups([("A", 9, 5.0)]) == []


def test_detection_feeds_the_check_not_the_threshold() -> None:
    """Cada sync que pilla un cruce añade una observación con la que comparar.
    El umbral sigue siendo el de la tabla."""
    snapshots = []
    for i in range(6):
        snapshots += [(f"p{i}", 3, 26.0 + i * 0.2), (f"p{i}", 4, 0.0)]
    med = measure(detect_level_ups(snapshots))
    assert med.observations == 6
    assert 26.0 <= (med.observed_mean or 0) <= 27.0
    assert med.points_per_level == 100


# ── Progress towards the next level ─────────────────────────────────────────

def test_progress_always_measures_against_the_configured_threshold() -> None:
    matches = {"league": 14, "friendly_international": 3}
    hecho = progress(matches)
    assert hecho.points == pytest.approx(51.1)
    assert hecho.points_per_level == 100
    assert hecho.remaining_points == pytest.approx(48.9)


def test_progress_is_capped_and_flags_players_about_to_level() -> None:
    nearly = progress({"league": 26})
    assert nearly.percent >= 90 and nearly.is_close

    over = progress({"league": 40})
    assert over.percent == 100
    assert over.remaining_points == 0.0
    assert not progress({"league": 2}).is_close


def test_breakdown_shows_where_the_points_came_from() -> None:
    b = progress({"league": 14, "friendly_international": 3, "tournament": 5}).breakdown
    assert b == {"league": 49.0, "friendly_international": 2.1}


def test_unscored_national_matches_are_reported_separately() -> None:
    """Selección nacional competitiva (10/11) no tiene un match_points propio
    a propósito (ver experience.yaml), progress() solo la refleja si se le
    pasa el conteo explícitamente; por defecto es 0."""
    default = progress({"league": 1})
    assert default.unscored_national_matches == 0

    seen = progress({"league": 1}, unscored_national_matches=2)
    assert seen.unscored_national_matches == 2
    assert seen.points == default.points  # no puntúan, solo se cuentan


# ── Time to the next level ──────────────────────────────────────────────────

def test_matches_and_weeks_to_next_level() -> None:
    matches = {"league": 14, "friendly_international": 3}
    assert matches_to_next_level(matches, "league") == pytest.approx(14.0)
    assert matches_to_next_level(matches, "cup") == pytest.approx(7.0)
    assert weeks_to_next_level(matches, league_matches_per_week=1.0) == pytest.approx(14.0)


def test_a_match_type_worth_nothing_never_gets_there() -> None:
    assert matches_to_next_level({"league": 1}, "tournament") == float("inf")
    assert weeks_to_next_level({"league": 1}, league_matches_per_week=0) == float("inf")


# ── Captain ─────────────────────────────────────────────────────────────────

def test_captain_recommendation_prefers_leadership_and_experience() -> None:
    squad = [
        {"name": "Veterano", "skills": {"leadership": 7, "experience": 12}},
        {"name": "Promesa", "skills": {"leadership": 2, "experience": 1}},
    ]
    assert recommend_captain(squad)["player"] == "Veterano"
    assert recommend_captain([]) is None


# ── What the engine says about itself ───────────────────────────────────────

def test_model_info_separates_what_is_verified_from_what_is_assumed() -> None:
    info = model_info()
    assert info["verified"] == ["league", "friendly_international"]
    assert set(info["fromSpec"]) == {
        "cup", "cup_secondary", "qualification", "friendly",
        "masters", "national_team_friendly", "youth_league", "youth_friendly",
    }
    assert info["pointsPerLevel"] == 100
    assert info["observedMean"] is None
    assert info["agreesWithConfigured"] is None


def test_model_info_reports_the_measurement_once_there_is_one() -> None:
    med = measure([LevelUp(f"p{i}", 3, 4, 26.0 + (i % 3)) for i in range(8)])
    info = model_info(med)
    assert info["observations"] == 8
    assert info["standardDeviation"] > 0
    assert info["confidenceInterval"] is not None
    assert info["observedMean"] == pytest.approx(26.875)
    # Lo que la aplicación usa no se ha movido.
    assert info["pointsPerLevel"] == 100
    assert info["agreesWithConfigured"] is False
