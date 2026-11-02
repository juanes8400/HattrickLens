"""Experience Engine, Spec: docs/spec/EXPERIENCE_ENGINE.md

Tracks how close each player is to the next experience level, and which matches
got them there. Experience cannot be trained, only accumulated, which is why a
veteran is hard to replace even when his skills are worse.

POINTS PER LEVEL: 100, FIXED, AND NEVER FITTED HERE
--------------------------------------------------
The threshold is 100 points per level and the match weights are Hattrick's own
table (docs/reference/tabla_experiencia.html). They are configuration, not
something this engine estimates.

Until 2026-11-02 there was a `calibrate()` that replaced the threshold with the
mean of the owner's observed level-ups as soon as five had been recorded. That
is fitting a formula's parameter to private account data, which the owner
forbade on 2026-08-14, and it was also pointless once the owner confirmed the
100 in-game. Removed.

What is kept is the opposite direction: `measure()` reports what those same
level-ups came out to, as a CHECK against the configured value. Describing and
verifying is allowed and useful; feeding it back is not. Nothing in the app
reads the measured number as the threshold.

The point values per match type are verified: league and international friendly
reconstruct Hattrick Control's "Suma" column for 19 players with zero error.

2026-08-05: rescaled to Hattrick's real point values (docs/reference/
tabla_experiencia.html), the proportions between match types are the same
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
    national_team_competitive: int = 0
    national_team_competitive_cup: int = 0
    youth_league: int = 0
    youth_friendly: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "league": self.league,
            "cup": self.cup,
            "cup_secondary": self.cup_secondary,
            "qualification": self.qualification,
            "friendly": self.friendly,
            "friendly_international": self.friendly_international,
            "tournament": self.tournament,
            "masters": self.masters,
            "national_team_friendly": self.national_team_friendly,
            "national_team_competitive": self.national_team_competitive,
            "national_team_competitive_cup": self.national_team_competitive_cup,
            "youth_league": self.youth_league,
            "youth_friendly": self.youth_friendly,
        }


@dataclass(frozen=True)
class LevelUp:
    """One observed experience increase, used to check the configured threshold."""

    player: str
    from_level: int
    to_level: int
    points_accumulated: float


@dataclass
class Measurement:
    """What the observed level-ups came out to, NEXT TO the configured value.

    `points_per_level` is always the configured one, the number the app uses.
    `observed_mean` is what this account's own level-ups averaged, and it is
    there to be compared with it, never to replace it.
    """

    points_per_level: float
    std_dev: float | None
    observations: int
    observed_mean: float | None = None
    by_level: dict[int, float] = field(default_factory=dict)

    @property
    def agrees(self) -> bool | None:
        """Whether the configured value falls inside the observed interval."""
        interval = self.confidence_interval
        if interval is None:
            return None
        return interval[0] <= self.points_per_level <= interval[1]

    @property
    def confidence_interval(self) -> tuple[float, float] | None:
        """Roughly 95% interval for the OBSERVED mean, if there is evidence."""
        if self.std_dev is None or self.observed_mean is None or self.observations < 2:
            return None
        margin = 1.96 * self.std_dev / (self.observations**0.5)
        return round(self.observed_mean - margin, 2), round(self.observed_mean + margin, 2)


@dataclass
class ExperienceProgress:
    points: float
    percent: int
    remaining_points: float
    points_per_level: float
    breakdown: dict[str, float] = field(default_factory=dict)
    # Conteo de partidos reales, separado del desglose de puntos. Un partido
    # de 45 minutos cuenta como un partido aquí, aunque aporte medio peso al
    # cálculo de experiencia.
    match_counts: dict[str, int] = field(default_factory=dict)
    # Partidos de selección nacional COMPETITIVOS vistos (MatchType 10/11):
    # CHPP no distingue Mundial/Copa continental/Copa de Naciones ni sus
    # rondas con ese código, así que no se les asigna puntaje (inventar un
    # valor sería peor que omitirlo), se cuentan aquí para que quede
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
    categoría), quien arma el conteo (`player_history.py`) ya entrega el
    valor ponderado; este motor solo multiplica por el punto de la categoría,
    sin distinguir si el origen fue un conteo entero o una fracción."""
    cfg = _config()["match_points"]
    data = matches.as_dict() if isinstance(matches, MatchCount) else matches
    return float(round(sum(cfg.get(kind, 0.0) * n for kind, n in data.items()), 4))


def measure(observations: list[LevelUp] | None = None) -> Measurement:
    """What the observed level-ups came out to, as a check on the configured 100.

    This NEVER changes the threshold the app uses. With no observations there
    is simply nothing to compare, and the configured value travels alone.
    """
    cfg = _config()
    configured = float(cfg["points_per_level"])
    obs = observations or []

    if not obs:
        return Measurement(points_per_level=configured, std_dev=None, observations=0)

    values = [o.points_accumulated for o in obs]
    deviation = round(stdev(values), 3) if len(values) > 1 else 0.0

    by_level: dict[int, float] = {}
    for level in {o.from_level for o in obs}:
        same = [o.points_accumulated for o in obs if o.from_level == level]
        if len(same) >= 2:
            by_level[level] = round(mean(same), 2)

    return Measurement(
        points_per_level=configured,
        std_dev=deviation,
        observations=len(obs),
        observed_mean=round(mean(values), 3),
        by_level=by_level,
    )


def progress(
    matches: MatchCount | Mapping[str, float],
    unscored_national_matches: int = 0,
    match_counts: Mapping[str, int] | None = None,
) -> ExperienceProgress:
    cfg = _config()
    per_level = float(cfg["points_per_level"])
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
        breakdown=breakdown,
        match_counts=dict(match_counts or {}),
        unscored_national_matches=unscored_national_matches,
    )


def matches_to_next_level(
    matches: MatchCount | dict[str, int],
    match_type: str = "league",
) -> float:
    """How many more matches of a given type are needed."""
    cfg = _config()
    value = cfg["match_points"].get(match_type, 0.0)
    if value <= 0:
        return float("inf")
    return float(round(progress(matches).remaining_points / value, 1))


def weeks_to_next_level(
    matches: MatchCount | dict[str, int],
    league_matches_per_week: float = 1.0,
) -> float:
    if league_matches_per_week <= 0:
        return float("inf")
    return round(matches_to_next_level(matches, "league") / league_matches_per_week, 1)


def detect_level_ups(
    snapshots: list[tuple[str, int, float]],
) -> list[LevelUp]:
    """Turn a chronological series of (player, experience, points) readings into
    observed level-ups.

    Every synchronisation that catches a player crossing a level adds one
    observation. They are a CHECK on the configured 100 (see `measure`), not a
    source for it.
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


def model_info(measurement: Measurement | None = None) -> dict[str, Any]:
    cfg = _config()
    med = measurement or measure()
    return {
        # El que usa la aplicación, siempre el configurado. Lo observado viaja
        # al lado para poder compararlo, nunca en su lugar.
        "pointsPerLevel": med.points_per_level,
        "observedMean": med.observed_mean,
        "standardDeviation": med.std_dev,
        "observations": med.observations,
        "confidenceInterval": med.confidence_interval,
        "agreesWithConfigured": med.agrees,
        "byLevel": med.by_level,
        "matchPoints": cfg["match_points"],
        "verified": ["league", "friendly_international"],
        "fromSpec": [
            "cup",
            "cup_secondary",
            "qualification",
            "friendly",
            "masters",
            "national_team_friendly",
            "youth_league",
            "youth_friendly",
        ],
        "reference": cfg["reference"],
    }
