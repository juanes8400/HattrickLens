"""Experience Engine — Spec: docs/spec/EXPERIENCE_ENGINE.md

Tracks how close each player is to the next experience level, and which matches
got them there. Experience cannot be trained, only accumulated, which is why a
veteran is hard to replace even when his skills are worse.

POINTS PER LEVEL — PROFILED, THEN MEASURED
-------------------------------------------
Hattrick Control exposes the threshold and match weights as an editable
profile. Lens starts from the compatible profile, then records observed
level-ups and reports the mean and standard deviation of complete intervals.

The configured value is the prior: it is used while there is no evidence, and
it is replaced by the observed mean once enough level-ups have been recorded.
The standard deviation is the honest part — it says how much the estimate can
be trusted, and it will reveal whether the true figure is 28, 27, or whether it
varies with the player's current level.

The point values per match type are verified: league and international friendly
reconstruct Hattrick Control's "Suma" column for 19 players with zero error.

2026-08-05: rescaled to Hattrick's real point values (docs/reference/
tabla_experiencia.html) — the proportions between match types are the same
ones already verified against Hattrick Control, only expressed in the game's
own units (points_per_level=100) instead of the old internal profile
(points_per_level=28). See experience.yaml for the full cross-check note.
"""
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from statistics import mean, stdev
from typing import Any, cast

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "experience.yaml"


@lru_cache(maxsize=1)
def _config() -> dict[str, Any]:
    with CONFIG_PATH.open(encoding="utf-8") as fh:
        return cast(dict[str, Any], yaml.safe_load(fh))


def reload_config() -> None:
    _config.cache_clear()


@dataclass(frozen=True)
class MatchCount:
    """Matches played since the last experience increase."""

    league: int = 0
    cup: int = 0
    cup_secondary: int = 0
    qualification: int = 0
    friendly: int = 0
    friendly_international: int = 0
    tournament: int = 0
    masters: int = 0
    national_team_friendly: int = 0
    youth_league: int = 0
    youth_friendly: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "league": self.league, "cup": self.cup,
            "cup_secondary": self.cup_secondary,
            "qualification": self.qualification,
            "friendly": self.friendly,
            "friendly_international": self.friendly_international,
            "tournament": self.tournament,
            "masters": self.masters,
            "national_team_friendly": self.national_team_friendly,
            "youth_league": self.youth_league,
            "youth_friendly": self.youth_friendly,
        }


@dataclass(frozen=True)
class LevelUp:
    """One observed experience increase, used to calibrate the engine."""

    player: str
    from_level: int
    to_level: int
    points_accumulated: float


@dataclass
class Calibration:
    """What the observed level-ups say about the points needed per level."""

    points_per_level: float
    std_dev: float | None
    observations: int
    source: str          # "configured" | "observed" | "blended"
    configured_value: float
    observed_mean: float | None = None
    by_level: dict[int, float] = field(default_factory=dict)

    @property
    def is_measured(self) -> bool:
        return self.source != "configured"

    @property
    def confidence_interval(self) -> tuple[float, float] | None:
        """Roughly 95% interval for the mean, if there is enough evidence."""
        if self.std_dev is None or self.observations < 2:
            return None
        margin = 1.96 * self.std_dev / (self.observations ** 0.5)
        return round(self.points_per_level - margin, 2), round(self.points_per_level + margin, 2)


@dataclass
class ExperienceProgress:
    points: float
    percent: int
    remaining_points: float
    points_per_level: float
    calibration_source: str
    breakdown: dict[str, float] = field(default_factory=dict)
    # Partidos de selección nacional COMPETITIVOS vistos (MatchType 10/11):
    # CHPP no distingue Mundial/Copa continental/Copa de Naciones ni sus
    # rondas con ese código, así que no se les asigna puntaje (inventar un
    # valor sería peor que omitirlo) — se cuentan aquí para que quede
    # constancia de que el jugador SÍ jugó con la selección, aunque esos
    # puntos no entren en `points`/`percent`.
    unscored_national_matches: int = 0

    @property
    def is_close(self) -> bool:
        return self.percent >= 90


def points(matches: MatchCount | Mapping[str, float]) -> float:
    """Weighted experience points for a set of matches.

    `matches` values are match-equivalents, not necessarily whole matches:
    2026-08-05, pedido explícitamente, un partido pesa proporcional a los
    minutos jugados sobre 90 (jugar 70 de 90 = 0.777 partidos de esa
    categoría) — quien arma el conteo (`player_history.py`) ya entrega el
    valor ponderado; este motor solo multiplica por el punto de la categoría,
    sin distinguir si el origen fue un conteo entero o una fracción."""
    cfg = _config()["match_points"]
    data = matches.as_dict() if isinstance(matches, MatchCount) else matches
    return float(round(sum(cfg.get(kind, 0.0) * n for kind, n in data.items()), 4))


def calibrate(observations: list[LevelUp] | None = None) -> Calibration:
    """Estimate points per level from observed level-ups.

    Below `min_observations` the configured value stands: a mean over one or
    two samples is not evidence, and pretending otherwise would be worse than
    using the prior.
    """
    cfg = _config()
    configured = float(cfg["points_per_level"])
    minimum = int(cfg.get("min_observations_to_calibrate", 5))
    obs = observations or []

    if len(obs) < minimum:
        return Calibration(
            points_per_level=configured,
            std_dev=None,
            observations=len(obs),
            source="configured",
            configured_value=configured,
        )

    values = [o.points_accumulated for o in obs]
    observed_mean = round(mean(values), 3)
    deviation = round(stdev(values), 3) if len(values) > 1 else 0.0

    by_level: dict[int, float] = {}
    for level in {o.from_level for o in obs}:
        same = [o.points_accumulated for o in obs if o.from_level == level]
        if len(same) >= 2:
            by_level[level] = round(mean(same), 2)

    return Calibration(
        points_per_level=observed_mean,
        std_dev=deviation,
        observations=len(obs),
        source="observed",
        configured_value=configured,
        observed_mean=observed_mean,
        by_level=by_level,
    )


def progress(
    matches: MatchCount | Mapping[str, float],
    calibration: Calibration | None = None,
    unscored_national_matches: int = 0,
) -> ExperienceProgress:
    cfg = _config()
    cal = calibration or calibrate()
    per_level = cal.points_per_level
    data = matches.as_dict() if isinstance(matches, MatchCount) else matches
    total = points(data)
    pct = int(min(total / per_level * 100, 100)) if per_level else 0
    breakdown = {
        kind: round(cfg["match_points"].get(kind, 0.0) * n, 3)
        for kind, n in data.items()
        if n and cfg["match_points"].get(kind, 0.0)
    }
    return ExperienceProgress(
        points=total,
        percent=pct,
        remaining_points=round(max(per_level - total, 0.0), 2),
        points_per_level=per_level,
        calibration_source=cal.source,
        breakdown=breakdown,
        unscored_national_matches=unscored_national_matches,
    )


def matches_to_next_level(
    matches: MatchCount | dict[str, int],
    match_type: str = "league",
    calibration: Calibration | None = None,
) -> float:
    """How many more matches of a given type are needed."""
    cfg = _config()
    value = cfg["match_points"].get(match_type, 0.0)
    if value <= 0:
        return float("inf")
    return float(round(progress(matches, calibration).remaining_points / value, 1))


def weeks_to_next_level(
    matches: MatchCount | dict[str, int],
    league_matches_per_week: float = 1.0,
    calibration: Calibration | None = None,
) -> float:
    if league_matches_per_week <= 0:
        return float("inf")
    return round(
        matches_to_next_level(matches, "league", calibration) / league_matches_per_week, 1
    )


def detect_level_ups(
    snapshots: list[tuple[str, int, float]],
) -> list[LevelUp]:
    """Turn a chronological series of (player, experience, points) readings into
    observed level-ups.

    This is what makes the calibration self-improving: every synchronisation
    that catches a player crossing a level adds one observation.
    """
    out: list[LevelUp] = []
    previous: dict[str, tuple[int, float]] = {}
    for player, level, accumulated in snapshots:
        before = previous.get(player)
        if before and level > before[0]:
            out.append(
                LevelUp(
                    player=player,
                    from_level=before[0],
                    to_level=level,
                    # Points held just before the increase are what the level cost
                    points_accumulated=before[1],
                )
            )
        previous[player] = (level, accumulated)
    return out


def recommend_captain(players: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Captain suitability leans on leadership and experience. The position
    engine owns the weights; this is the convenience entry point."""
    from app.domain.engines.position_engine import best_for_role

    result = best_for_role(players, "captain")
    if result is None:
        return None
    player, rating = result
    return {"player": player.get("name", ""), "rating": rating.rating, "role": rating.label}


def model_info(calibration: Calibration | None = None) -> dict[str, Any]:
    cfg = _config()
    cal = calibration or calibrate()
    return {
        "pointsPerLevel": cal.points_per_level,
        "configuredPointsPerLevel": cal.configured_value,
        "observedMean": cal.observed_mean,
        "standardDeviation": cal.std_dev,
        "observations": cal.observations,
        "source": cal.source,
        "confidenceInterval": cal.confidence_interval,
        "byLevel": cal.by_level,
        "matchPoints": cfg["match_points"],
        "verified": ["league", "friendly_international"],
        "fromSpec": [
            "cup", "cup_secondary", "qualification", "friendly",
            "masters", "national_team_friendly", "youth_league", "youth_friendly",
        ],
        "reference": cfg["reference"],
    }
