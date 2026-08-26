"""Senior-team technical training estimates.

This is a clean-room Python port of the public HT-Tools community formula.
It is not Hattrick server code and it never fits coefficients from the
manager's private data.  Synced pops are used only to contrast predictions
with observed facts.

The formula works in two clocks:

* a piecewise cost curve describes the work between two skill levels;
* an age clock makes the same amount of work take longer as a player ages.

CHPP does not expose the decimal sublevel of a skill.  Callers may provide one
when it is known; otherwise Lens starts at the integer level (sublevel 0.0) and
labels the result as an estimate.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "training.yaml"
DAYS_PER_HT_YEAR = 112  # 16 weeks x 7 days


@lru_cache(maxsize=1)
def _config() -> dict[str, Any]:
    with CONFIG_PATH.open(encoding="utf-8") as fh:
        return cast(dict[str, Any], yaml.safe_load(fh))


def reload_config() -> None:
    _config.cache_clear()


@dataclass(frozen=True)
class TrainingSetup:
    """The club's training configuration.

    ``coach_level`` uses the formula scale 4..8. CHPP's StaffLevel 1..5 is
    mapped to it by ``training_context.py``. ``assistant_level_sum`` is the
    sum of the levels of at most two assistant coaches, never their count.
    """

    skill: str
    training_type: int | None = None
    intensity: int = 100
    stamina_share: float = 0
    coach_level: int = 8
    coach_is_excellent: bool = True  # retained for API compatibility
    assistant_level_sum: int | float = 0

    def __post_init__(self) -> None:
        validate_assistant_level_sum(self.assistant_level_sum)

    @property
    def effective_intensity(self) -> float:
        return max(self.intensity / 100 * (1 - self.stamina_share / 100), 0.0)

    @property
    def effective_stamina_intensity(self) -> float:
        return max(self.intensity * self.stamina_share / 100, 0.0)


@dataclass(frozen=True)
class TrainingSpeed:
    skill: str
    training_mode: str
    training_coefficient: float
    assistant_factor: float
    age_factor: float
    coach_factor: float
    intensity_factor: float
    stamina_factor: float
    exposure_factor: float
    current_skill: float
    target_skill: float
    skill_work: float
    weeks_to_next_level: float

    @property
    def weekly_progress(self) -> float:
        return 1.0 / self.weeks_to_next_level if self.weeks_to_next_level else 0.0


def validate_assistant_level_sum(level_sum: int | float) -> None:
    cfg = _config()
    ceiling = float(cfg["assistant_level_sum_cap"])
    if not 0 <= float(level_sum) <= ceiling:
        raise ValueError(
            f"assistant_level_sum={level_sum} exceeds the formula cap of "
            f"{ceiling:g} ({cfg['max_assistants']} assistants x level "
            f"{cfg['max_assistant_level']}). It must be a sum of levels, not "
            "an assistant count."
        )


def assistant_factor(level_sum: int | float) -> float:
    """Speed coefficient: 0.66 + 0.032 x combined assistant level."""
    cfg = _config()
    capped = max(0.0, min(float(level_sum), float(cfg["assistant_level_sum_cap"])))
    return float(cfg["assistant_base_coefficient"] + capped * cfg["assistant_bonus_per_level"])


def coach_factor(level: int, is_excellent: bool = False) -> float:
    """Coach speed coefficient on the formula's 4..8 scale.

    ``is_excellent`` is deliberately ignored: level 8 already contains that
    effect, so applying a second bonus would double-count it.
    """
    coefficients = _config()["coach_coefficients"]
    normalized = max(min(int(level), max(coefficients)), min(coefficients))
    return float(coefficients[normalized])


def training_efficiency_pct(
    coach_level: int,
    assistant_level_sum: int | float,
    intensity: int,
    # `float`, no `int`: `TrainingSetup.stamina_share` es un float y siempre
    # lo fue. La firma decia otra cosa.
    stamina_share: int | float,
) -> float:
    """Qué porcentaje del entrenamiento máximo posible está recibiendo el club.

    100% es el techo del juego: entrenador 5/5, dos asistentes de nivel 5 y
    toda la intensidad puesta en la habilidad. Se construye con los MISMOS
    coeficientes que usa la proyección (`coach_factor`, `assistant_factor`,
    `effective_intensity`), así que no es una regla aparte que pueda
    desincronizarse: es el mismo número, dividido por su máximo.

    La cuota de resistencia entra restando porque es lo que hace: el porcentaje
    que va a resistencia no va a la habilidad que se entrena.
    """
    cfg = _config()
    techo = coach_factor(max(cfg["coach_coefficients"])) * assistant_factor(
        cfg["assistant_level_sum_cap"]
    )
    actual = (
        coach_factor(coach_level)
        * assistant_factor(assistant_level_sum)
        * max(intensity / 100 * (1 - stamina_share / 100), 0.0)
    )
    return round(100 * actual / techo, 1) if techo > 0 else 0.0


def training_mode(skill: str, training_type: int | None = None) -> str:
    cfg = _config()
    if training_type is not None:
        mode = cfg["training_type_to_mode"].get(int(training_type))
        if mode:
            return str(mode)
    mode = cfg["default_training_mode_by_skill"].get(skill)
    if not mode:
        raise ValueError(
            f"The HT-Tools technical formula has no mode for skill={skill!r}. "
            "Stamina uses a separate reference engine."
        )
    return str(mode)


def training_coefficient(skill: str, training_type: int | None = None) -> float:
    return float(_config()["training_coefficients"][training_mode(skill, training_type)])


def skill_cost(skill_value: float) -> float:
    """Piecewise public cost function F(s)."""
    cfg = _config()["skill_curve"]
    value = max(float(skill_value), 0.0)
    if value < float(cfg["split_level"]):
        power = float(cfg["low_power"])
        return float((value**power - 1.0) / (float(cfg["low_scale"]) * power))
    power = float(cfg["high_power"])
    return float(
        float(cfg["high_offset"])
        + (value - float(cfg["high_shift"])) ** power / (float(cfg["high_scale"]) * power)
    )


def _age_clock_values() -> tuple[int, list[float]]:
    cfg = _config()["age_clock"]
    return int(cfg["start_age"]), [float(value) for value in cfg["values"]]


def age_clock(age: float) -> float:
    """Map a decimal Hattrick age to the public accumulated age clock.

    The source table ends at 34. Beyond it Lens continues with the last known
    segment instead of inventing a fitted curve; model metadata exposes this
    limitation.
    """
    start, values = _age_clock_values()
    decimal_age = float(age)
    if decimal_age <= start:
        return values[0] + (decimal_age - start) * (values[1] - values[0])

    last_age = start + len(values) - 1
    if decimal_age >= last_age:
        return values[-1] + (decimal_age - last_age) * (values[-1] - values[-2])

    lower_age = int(decimal_age)
    fraction = decimal_age - lower_age
    index = lower_age - start
    return values[index] + fraction * (values[index + 1] - values[index])


def inverse_age_clock(clock_value: float) -> float:
    """Inverse of :func:`age_clock`, including the declared edge extensions."""
    start, values = _age_clock_values()
    clock = float(clock_value)
    if clock <= values[0]:
        return start + (clock - values[0]) / (values[1] - values[0])

    for index in range(len(values) - 1):
        if clock <= values[index + 1]:
            fraction = (clock - values[index]) / (values[index + 1] - values[index])
            return start + index + fraction

    return start + len(values) - 1 + (clock - values[-1]) / (values[-1] - values[-2])


def age_factor(age_years: int, age_days: int = 0) -> float:
    """Display-only relative age speed, interpolated from the public table."""
    coefficients = [float(v) for v in _config()["age_speed_coefficients"]]
    start, _ = _age_clock_values()
    age = age_years + age_days / DAYS_PER_HT_YEAR
    if age <= start:
        return coefficients[0]
    last_age = start + len(coefficients) - 1
    if age >= last_age:
        slope = coefficients[-1] - coefficients[-2]
        return max(coefficients[-1] + (age - last_age) * slope, 0.01)
    lower = int(age)
    fraction = age - lower
    index = lower - start
    return coefficients[index] + fraction * (coefficients[index + 1] - coefficients[index])


def default_setup(
    skill: str,
    *,
    training_type: int | None = None,
    intensity: int = 100,
    stamina_share: float | None = None,
) -> TrainingSetup:
    cfg = _config()
    return TrainingSetup(
        skill=skill,
        training_type=training_type,
        intensity=intensity,
        stamina_share=(
            stamina_share
            if stamina_share is not None
            else float(cfg.get("default_stamina_share", 0))
        ),
        coach_level=8,
        coach_is_excellent=True,
        assistant_level_sum=int(cfg.get("default_assistant_level_sum", 10)),
    )


def training_exposure(minutes: int, position_share: str = "full") -> float:
    """Fraction of a full technical training week received on the field."""
    cfg = _config()
    minutes_factor = min(max(minutes, 0) / cfg["full_training_minutes"], 1.0)
    return float(minutes_factor * cfg["position_training_share"].get(position_share, 0.0))


def weeks_to_next_level(
    skill: str,
    current_level: int,
    age_years: int,
    age_days: int = 0,
    setup: TrainingSetup | None = None,
    exposure: float = 1.0,
    current_sublevel: float = 0.0,
) -> TrainingSpeed:
    """Estimate weeks from ``level + sublevel`` to the next integer level."""
    if not 0 <= current_sublevel < 1:
        raise ValueError("current_sublevel must be in the interval [0, 1).")

    setup = setup or default_setup(skill)
    mode = training_mode(skill, setup.training_type)
    training_f = training_coefficient(skill, setup.training_type)
    coach_f = coach_factor(setup.coach_level, setup.coach_is_excellent)
    assist_f = assistant_factor(setup.assistant_level_sum)
    intensity_f = max(setup.intensity / 100.0, 0.0)
    stamina_f = (
        max(1.0 - setup.stamina_share / 100.0, 0.0)
        if _config().get("apply_stamina_share", True)
        else 1.0
    )
    exposure_f = max(float(exposure), 0.0)

    current_skill = float(current_level) + float(current_sublevel)
    target_skill = float(current_level + 1)
    work = max(skill_cost(target_skill) - skill_cost(current_skill), 0.0)
    total_speed = training_f * coach_f * assist_f * intensity_f * stamina_f * exposure_f

    # A zero factor means no progress. Keep the value finite for JSON clients,
    # but make the practical result unmistakably unreachable.
    if total_speed <= 0:
        weeks = 1_000_000.0
    else:
        age = age_years + age_days / DAYS_PER_HT_YEAR
        pop_clock = age_clock(age) + work / total_speed
        pop_age = inverse_age_clock(pop_clock)
        weeks = max(16.0 * (pop_age - age), 0.1)

    return TrainingSpeed(
        skill=skill,
        training_mode=mode,
        training_coefficient=round(training_f, 4),
        assistant_factor=round(assist_f, 4),
        age_factor=round(age_factor(age_years, age_days), 4),
        coach_factor=round(coach_f, 4),
        intensity_factor=round(intensity_f, 4),
        stamina_factor=round(stamina_f, 4),
        exposure_factor=round(exposure_f, 4),
        current_skill=round(current_skill, 4),
        target_skill=target_skill,
        skill_work=round(work, 6),
        weeks_to_next_level=round(weeks, 2),
    )


@dataclass(frozen=True)
class LevelMilestone:
    level: int
    weeks_for_this_level: float
    weeks_from_now: float
    age_years: int
    age_days: int


def forecast_level_chain(
    skill: str,
    current_level: int,
    age_years: int,
    age_days: int,
    setup: TrainingSetup,
    exposure: float = 1.0,
    max_levels: int = 15,
) -> list[LevelMilestone]:
    out: list[LevelMilestone] = []
    cumulative_weeks = 0.0
    level = current_level
    # `float` desde el principio: mas abajo se le suman semanas, que son
    # decimales. Cada uso lo pasa por `int()`, asi que la edad que sale
    # sigue siendo entera.
    total_days: float = age_years * DAYS_PER_HT_YEAR + age_days
    for _ in range(min(max_levels, max(0, 20 - current_level))):
        ay, ad = divmod(total_days, DAYS_PER_HT_YEAR)
        speed = weeks_to_next_level(skill, level, int(ay), int(ad), setup, exposure)
        cumulative_weeks += speed.weeks_to_next_level
        total_days += speed.weeks_to_next_level * 7
        level += 1
        new_ay, new_ad = divmod(total_days, DAYS_PER_HT_YEAR)
        out.append(
            LevelMilestone(
                level=level,
                weeks_for_this_level=speed.weeks_to_next_level,
                weeks_from_now=round(cumulative_weeks, 1),
                age_years=int(new_ay),
                age_days=int(round(new_ad)),
            )
        )
    return out


@dataclass
class PopForecast:
    player: str
    skill: str
    current_level: int
    weeks_remaining: float
    progress: float
    confidence: str


def forecast_pops(
    players: list[dict[str, Any]],
    setup: TrainingSetup,
    weeks_already_trained: dict[int, float] | None = None,
) -> list[PopForecast]:
    trained = weeks_already_trained or {}
    out: list[PopForecast] = []
    for player in players:
        level = int(player.get("skills", {}).get(setup.skill, 0))
        speed = weeks_to_next_level(
            setup.skill,
            level,
            player.get("age_years", 17),
            player.get("age_days", 0),
            setup,
        )
        done = trained.get(player.get("ht_player_id", 0), 0.0)
        remaining = max(speed.weeks_to_next_level - done, 0.0)
        progress = min(done / speed.weeks_to_next_level, 1.0) if speed.weeks_to_next_level else 0.0
        out.append(
            PopForecast(
                player=player.get("name", ""),
                skill=setup.skill,
                current_level=level,
                weeks_remaining=round(remaining, 1),
                progress=round(progress, 3),
                confidence="estimated_from_pop" if done else "integer_level_only",
            )
        )
    return sorted(out, key=lambda forecast: forecast.weeks_remaining)


def compare_training_types(
    players: list[dict[str, Any]],
    setup: TrainingSetup,
    candidate_skills: list[str] | None = None,
) -> dict[str, float]:
    skills = candidate_skills or list(_config()["default_training_mode_by_skill"])
    out: dict[str, float] = {}
    for skill in skills:
        candidate = TrainingSetup(
            skill=skill,
            training_type=None,
            intensity=setup.intensity,
            stamina_share=setup.stamina_share,
            coach_level=setup.coach_level,
            coach_is_excellent=setup.coach_is_excellent,
            assistant_level_sum=setup.assistant_level_sum,
        )
        weeks = [
            weeks_to_next_level(
                skill,
                int(player.get("skills", {}).get(skill, 0)),
                player.get("age_years", 17),
                player.get("age_days", 0),
                candidate,
            ).weeks_to_next_level
            for player in players
        ]
        out[skill] = round(sum(weeks) / len(weeks), 2) if weeks else 0.0
    return dict(sorted(out.items(), key=lambda item: item[1]))


def model_info() -> dict[str, Any]:
    cfg = _config()
    return {
        "engine": "HT-Tools community formula",
        "trainingCoefficients": cfg["training_coefficients"],
        "trainingTypeToMode": cfg["training_type_to_mode"],
        "assistantBaseCoefficient": cfg["assistant_base_coefficient"],
        "assistantBonusPerLevel": cfg["assistant_bonus_per_level"],
        "maxAssistants": cfg["max_assistants"],
        "maxAssistantLevel": cfg["max_assistant_level"],
        "assistantLevelSumCap": cfg["assistant_level_sum_cap"],
        "coachCoefficients": cfg["coach_coefficients"],
        "formula": (
            "K = K_entrenamiento x K_entrenador x K_asistentes x intensidad "
            "x (1 - resistencia) x exposición; semanas = 16 x "
            "(reloj_edad_inverso(reloj_edad + (F(siguiente)-F(actual))/K) - edad)"
        ),
        "skillCurve": cfg["skill_curve"],
        "reference": cfg["reference"],
        "limitations": [
            "CHPP no publica el subnivel: si no se conoce, se usa 0,0.",
            "La tabla pública de edad termina en 34; por encima se prolonga su último tramo.",
            "Resistencia usa un motor separado de la fórmula técnica.",
        ],
        "benchmark": None,
    }
