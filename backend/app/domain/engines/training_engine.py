"""Training Engine — HTC-compatible profile: docs/spec/TRAINING_ENGINE.md

Estimates how fast each player develops, when the next skill increase lands,
and what that increase is worth.

PROFILE FORMULA
---------------
The profile follows the inputs and per-training setup recovered from Hattrick
Control 3.50.02.1619. Its numeric coefficients remain explicit configuration
until the original Defaults.dat / helper routine is fully reconstructed:

    weeks = base_weeks[skill]
          ÷ (1 + assistant_level_sum × 3.5%)
          × (1 + 6% × (age − 17))
          × (1 + 10% × max(7 − coach_level, 0) − 5% if excellent)
          × (1 − 1% × (intensity − 100))
          ÷ (1 − stamina_share)

THE ASSISTANT TERM IS A PROFILE INPUT
-------------------------------------
Hattrick Control exposes an editable assistant decrement. Lens receives the
sum of assistant levels from CHPP, applies the active compatibility profile,
and keeps its cap and coefficient visible in configuration. Assistants add
speed, so their factor divides waiting time.

The earlier validation used this multiplier in the wrong direction. Its error
figures are retired rather than carried over. CHPP training events will provide
the new validation evidence as the app collects complete pop intervals.

An exponential age model fits marginally better (R² 0.999) but lacks the
per-skill structure; it stays available through `use_alternative_age_model`.

`base_weeks` is an explicit per-skill compatibility profile. Hattrick Control
provides a separate editable control for every training type.
"""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "training.yaml"


@lru_cache(maxsize=1)
def _config() -> dict[str, Any]:
    with CONFIG_PATH.open(encoding="utf-8") as fh:
        return cast(dict[str, Any], yaml.safe_load(fh))


def reload_config() -> None:
    _config.cache_clear()


@dataclass(frozen=True)
class TrainingSetup:
    """The club's current training configuration.

    `assistant_level_sum` is the sum of every assistant coach's level, not the
    number of assistants. Its permitted range comes from the active profile.
    """

    skill: str
    intensity: int = 100                  # percent, as Hattrick reports it
    stamina_share: float = 0              # percent diverted to stamina
    coach_level: int = 8                  # 7 = bueno, 8 = excelente
    coach_is_excellent: bool = True
    assistant_level_sum: int | float = 0  # SUM OF LEVELS of at most 2 assistants

    def __post_init__(self) -> None:
        validate_assistant_level_sum(self.assistant_level_sum)

    @property
    def effective_intensity(self) -> float:
        return max(self.intensity / 100 * (1 - self.stamina_share / 100), 0.0)

    @property
    def effective_stamina_intensity(self) -> float:
        """% real de la intensidad total dedicado a resistencia — el
        complemento de `effective_intensity` (que resta esta porción de la
        habilidad primaria). Unidad: puntos porcentuales (0-100), igual que
        las columnas de la tabla de referencia de Resistencia
        (stamina_reference.py)."""
        return max(self.intensity * self.stamina_share / 100, 0.0)


@dataclass(frozen=True)
class TrainingSpeed:
    skill: str
    base_weeks: float
    assistant_factor: float
    age_factor: float
    coach_factor: float
    intensity_factor: float
    stamina_factor: float
    weeks_to_next_level: float

    @property
    def weekly_progress(self) -> float:
        return 1.0 / self.weeks_to_next_level if self.weeks_to_next_level else 0.0


def assistant_factor(level_sum: int | float) -> float:
    """Training-speed multiplier configured by the active HTC profile.

    The caller divides weeks by this multiplier, so more assistant levels
    always reduce waiting.
    """
    cfg = _config()
    capped = max(0.0, min(float(level_sum), float(cfg["assistant_level_sum_cap"])))
    return float(1.0 + capped * cfg["assistant_bonus_per_level"])


def validate_assistant_level_sum(level_sum: int | float) -> None:
    """Raise if a caller passes something outside the active profile.

    A head-count slipped in where a level sum belongs is silent and expensive:
    it shifts every forecast without ever looking wrong. This makes it loud.
    """
    cfg = _config()
    ceiling = cfg["assistant_level_sum_cap"]
    if not 0 <= level_sum <= ceiling:
        raise ValueError(
            f"assistant_level_sum={level_sum} exceeds the active HTC-compatible "
            f"profile cap of {ceiling} ({cfg['max_assistants']} assistants × "
            f"level {cfg['max_assistant_level']}). Note this is a SUM OF LEVELS, "
            "not a head-count."
        )


def coach_factor(level: int, is_excellent: bool = False) -> float:
    """1 + 10% × max(7 − level, 0) − 5% if the coach is excellent.

    The penalty applies *below* the reference level: a weaker coach costs weeks,
    a stronger one simply stops costing them. Because the term is zero for any
    coach at level 7 or above, the excellent bonus cannot double-count.
    """
    cfg = _config()
    factor = 1.0 + cfg["coach_penalty_per_level"] * max(
        cfg["coach_reference_level"] - level, 0
    )
    if is_excellent and cfg.get("apply_excellent_coach_bonus", True):
        factor -= cfg["excellent_coach_bonus"]
    return float(max(factor, 0.05))


def age_factor(age_years: int, age_days: int = 0, alternative: bool = False) -> float:
    cfg = _config()
    age = age_years + age_days / 112.0
    if alternative:
        alt = cfg["alternative_age_model"]
        return float((1.0 + alt["age_factor_per_year"]) ** (age - cfg["reference_age"]))
    return float(1.0 + cfg["age_increase_per_year"] * (age - cfg["reference_age"]))


def default_setup(
    skill: str,
    *,
    intensity: int = 100,
    stamina_share: float | None = None,
) -> TrainingSetup:
    """The `TrainingSetup` to fall back to when club/stafflist haven't synced
    yet — coach and assistant assumptions read from `training.yaml` instead of
    duplicated as magic numbers at each call site (HL-2xx, 2026-08-14: found
    four independent copies of `coach_level=8, coach_is_excellent=True,
    assistant_level_sum=10`, one of which silently used `stamina_share=0`
    instead of the yaml's own `default_stamina_share`)."""
    cfg = _config()
    return TrainingSetup(
        skill=skill,
        intensity=intensity,
        stamina_share=(
            stamina_share if stamina_share is not None
            else float(cfg.get("default_stamina_share", 0))
        ),
        coach_level=8,
        coach_is_excellent=True,
        assistant_level_sum=int(cfg.get("default_assistant_level_sum", 10)),
    )


def training_exposure(minutes: int, position_share: str = "full") -> float:
    """How much of the week's training a player actually received."""
    cfg = _config()
    minutes_factor = min(minutes / cfg["full_training_minutes"], 1.0)
    return float(minutes_factor * cfg["position_training_share"].get(position_share, 0.0))


def weeks_to_next_level(
    skill: str,
    current_level: int,
    age_years: int,
    age_days: int = 0,
    setup: TrainingSetup | None = None,
    exposure: float = 1.0,
    use_alternative_age_model: bool = False,
) -> TrainingSpeed:
    """Weeks until this player gains one level in `skill`."""
    cfg = _config()
    setup = setup or TrainingSetup(skill=skill)

    base = float(cfg["base_weeks"].get(skill, cfg["base_weeks"]["playmaking"]))
    assist = assistant_factor(setup.assistant_level_sum)
    age_f = age_factor(age_years, age_days, use_alternative_age_model)
    coach_f = coach_factor(setup.coach_level, setup.coach_is_excellent)
    intensity_f = 1.0 - cfg["intensity_factor_per_point"] * (setup.intensity - 100)
    stamina_f = (
        1.0 - setup.stamina_share / 100 if cfg.get("apply_stamina_share", True) else 1.0
    )

    # Assistants add speed, not time. A higher level must shorten the wait.
    # Conditioning diverts capacity: a larger share must make the primary skill
    # wait longer, never shorter.
    weeks = base / assist * age_f * coach_f * intensity_f / max(stamina_f, 1e-6)

    if use_alternative_age_model:
        weeks *= max(current_level, 1) ** cfg["alternative_age_model"]["level_exponent"]

    # Minutes played and position training share dilute the week further.
    weeks = weeks / max(exposure, 1e-6)

    return TrainingSpeed(
        skill=skill,
        base_weeks=base,
        assistant_factor=round(assist, 4),
        age_factor=round(age_f, 4),
        coach_factor=round(coach_f, 4),
        intensity_factor=round(intensity_f, 4),
        stamina_factor=round(stamina_f, 4),
        weeks_to_next_level=round(max(weeks, 0.1), 2),
    )


@dataclass(frozen=True)
class LevelMilestone:
    """One future level in a cascading forecast — the tab Hattrick Control
    calls "Previsión subidas" (per player, not per squad)."""

    level: int
    weeks_for_this_level: float
    weeks_from_now: float          # cumulative from today
    age_years: int
    age_days: int


DAYS_PER_HT_YEAR = 112  # 16-week season × 7 days; a player ages 1 year/season


def forecast_level_chain(
    skill: str,
    current_level: int,
    age_years: int,
    age_days: int,
    setup: TrainingSetup,
    exposure: float = 1.0,
    max_levels: int = 15,
) -> list[LevelMilestone]:
    """Every future level from `current_level + 1` onward, each predicted
    with the age the player will actually HAVE when they get there — age
    compounds through the chain, so later levels cost more weeks than a
    naive per-level look would suggest (matches Hattrick Control's own
    table, where weeks-per-level climbs step over step as the player ages
    into it).

    Stops at level 20 ("divino", the top of `SKILL_LEVELS`) even if
    `max_levels` would reach further — beyond that a level name is a
    guess, and cascading a forecast through a guess compounds the guess.
    """
    out: list[LevelMilestone] = []
    cumulative_weeks = 0.0
    level = current_level
    total_days = age_years * DAYS_PER_HT_YEAR + age_days
    steps = min(max_levels, max(0, 20 - current_level))
    for _ in range(steps):
        ay, ad = divmod(total_days, DAYS_PER_HT_YEAR)
        speed = weeks_to_next_level(skill, level, int(ay), int(ad), setup, exposure)
        cumulative_weeks += speed.weeks_to_next_level
        total_days += speed.weeks_to_next_level * 7
        level += 1
        new_ay, new_ad = divmod(total_days, DAYS_PER_HT_YEAR)
        out.append(LevelMilestone(
            level=level,
            weeks_for_this_level=speed.weeks_to_next_level,
            weeks_from_now=round(cumulative_weeks, 1),
            age_years=int(new_ay),
            age_days=int(round(new_ad)),
        ))
    return out


@dataclass
class PopForecast:
    player: str
    skill: str
    current_level: int
    weeks_remaining: float
    progress: float          # 0–1 towards the next level
    confidence: str


def forecast_pops(
    players: list[dict[str, Any]],
    setup: TrainingSetup,
    weeks_already_trained: dict[int, float] | None = None,
) -> list[PopForecast]:
    """Upcoming skill increases, soonest first — the tab Hattrick Control
    ships empty."""
    trained = weeks_already_trained or {}
    out: list[PopForecast] = []
    for p in players:
        level = int(p.get("skills", {}).get(setup.skill, 0))
        speed = weeks_to_next_level(
            setup.skill, level, p.get("age_years", 17), p.get("age_days", 0), setup
        )
        done = trained.get(p.get("ht_player_id", 0), 0.0)
        remaining = max(speed.weeks_to_next_level - done, 0.0)
        progress = min(done / speed.weeks_to_next_level, 1.0) if speed.weeks_to_next_level else 0.0
        out.append(
            PopForecast(
                player=p.get("name", ""),
                skill=setup.skill,
                current_level=level,
                weeks_remaining=round(remaining, 1),
                progress=round(progress, 3),
                # Without observed history the sub-level is unknown, so this is
                # a schedule rather than a measurement. Say so.
                confidence="estimated" if done else "no_history",
            )
        )
    return sorted(out, key=lambda f: f.weeks_remaining)


def compare_training_types(
    players: list[dict[str, Any]],
    setup: TrainingSetup,
    candidate_skills: list[str] | None = None,
) -> dict[str, float]:
    """Average weeks per level under each training type — which skill develops
    this squad fastest."""
    cfg = _config()
    skills = candidate_skills or list(cfg["base_weeks"])
    out: dict[str, float] = {}
    for skill in skills:
        candidate = TrainingSetup(
            skill=skill, intensity=setup.intensity, stamina_share=setup.stamina_share,
            coach_level=setup.coach_level, coach_is_excellent=setup.coach_is_excellent,
            assistant_level_sum=setup.assistant_level_sum,
        )
        weeks = [
            weeks_to_next_level(
                skill, int(p.get("skills", {}).get(skill, 0)),
                p.get("age_years", 17), p.get("age_days", 0), candidate,
            ).weeks_to_next_level
            for p in players
        ]
        out[skill] = round(sum(weeks) / len(weeks), 2) if weeks else 0.0
    return dict(sorted(out.items(), key=lambda kv: kv[1]))


def model_info() -> dict[str, Any]:
    cfg = _config()
    return {
        "baseWeeks": cfg["base_weeks"],
        "ageIncreasePerYear": cfg["age_increase_per_year"],
        "assistantBonusPerLevel": cfg["assistant_bonus_per_level"],
        "maxAssistants": cfg["max_assistants"],
        "maxAssistantLevel": cfg["max_assistant_level"],
        "assistantLevelSumCap": cfg["assistant_level_sum_cap"],
        "coachReferenceLevel": cfg["coach_reference_level"],
        "formula": (
            "base ÷ (1 + Σlevels_of_at_most_2_assistants×3.5%) × (1 + 6%×(age−17)) "
            "× (1 + 10%×max(7−coach,0) − 5% if excellent) "
            "× (1 − 1%×(intensity−100)) ÷ (1 − stamina_share)"
        ),
        "reference": cfg["reference"],
        "benchmark": None,
        "alternativeModel": cfg["alternative_age_model"],
    }
