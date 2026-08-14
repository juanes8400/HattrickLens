"""Motor de posiciones — matriz del Manual no Escrito.

El Manual no Escrito publica, para cada puesto y orden individual, qué
porcentaje de cada habilidad alimenta la defensa central/lateral, mediocampo y
ataque central/lateral. Esta es la fuente única de las matrices de este motor:
no intenta reproducir estrellas ni se ajusta a observaciones de otra
aplicación.

Para ordenar jugadores en un mismo puesto, ``rating`` es su aporte de sector
normalizado por sus coeficientes. Es un **índice de aporte**, no el rating
oficial de un partido. El
desglose por sector queda declarado en ``positions.yaml`` para que el
optimizador de alineaciones pueda usarlo sin inventar pesos nuevos.

Las habilidades efectivas siguen las fórmulas del Manual para forma, condición,
experiencia y fidelidad. Los roles de capitán y lanzador de faltas se calculan
aparte porque no son posiciones de campo.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from math import log
from pathlib import Path
from typing import Any, cast

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "positions.yaml"
SOURCE_URL = "https://wiki.hattrick.org/wiki/Manual_no_Escrito"

# SPECIALTIES[1] en ht_constants.py ("Tecnico") — usado solo por
# penalty_taker (ver positions.yaml). No se importa ht_constants aquí para
# no acoplar este motor a esa tabla completa por un solo código.
TECHNICAL_SPECIALTY_CODE = 1


@lru_cache(maxsize=1)
def _config() -> dict[str, Any]:
    with CONFIG_PATH.open(encoding="utf-8") as fh:
        return cast(dict[str, Any], yaml.safe_load(fh))


def reload_config() -> None:
    """Drop the cache so an edited YAML takes effect without a restart."""
    _config.cache_clear()


@dataclass(frozen=True)
class PositionRating:
    position: str
    label: str
    rating: float
    is_special_role: bool = False


def _skill(player: dict[str, Any], key: str) -> float:
    return float(player.get("skills", {}).get(key, 0))


def _form_factor(player: dict[str, Any]) -> float:
    """Manual no Escrito: ``((forma - .5) / 7) ^ .45``."""
    base = (float(player.get("form", 0)) - 0.5) / 7
    return max(base, 0.0) ** 0.45


def _stamina_factor(player: dict[str, Any]) -> float:
    """Manual no Escrito: ``((condición + 6.5) / 14) ^ .6``."""
    base = (float(player.get("stamina", 0)) + 6.5) / 14
    return max(base, 0.0) ** 0.6


def _experience_bonus(player: dict[str, Any]) -> float:
    """Experience adds ``ln(XP) * 4 / 3`` to each effective skill."""
    experience = float(player.get("experience", 0))
    return log(experience) * 4 / 3 if experience > 0 else 0.0


def _loyalty_bonus(player: dict[str, Any]) -> float:
    """The Manual's loyalty scale runs linearly from 0 to +1 at divine.

    CHPP exposes it as the 0–19 skill-level scale; bounding it keeps imported
    historical records and malformed data from overstating the effect.
    """
    return min(max(float(player.get("loyalty", 0)), 0.0), 19.0) / 19.0


def _effective_skill(player: dict[str, Any], key: str) -> float:
    return _skill(player, key) + _experience_bonus(player) + _loyalty_bonus(player)


def _spec_for(position: str) -> tuple[dict[str, Any], bool]:
    cfg = _config()
    if position in cfg["positions"]:
        return cfg["positions"][position], False
    if position in cfg.get("special_roles", {}):
        return cfg["special_roles"][position], True
    raise KeyError(f"unknown position: {position}")


def _pitch_contribution(player: dict[str, Any], spec: dict[str, Any]) -> float:
    """Sum the Manual's sector contributions for one role.

    A sector can contain several contributing skills (for example, a normal
    inner midfielder's central attack contains passing and scoring). We sum
    every declared ``coefficient × effective skill`` exactly once. Dividing by
    the sum of declared coefficients makes positions comparable without
    changing any Manual coefficient: a role with more sector columns cannot
    become a player's “best position” solely for that reason. Form and stamina
    are then applied to the player's field impact.
    """
    terms = [
        (coefficient, _effective_skill(player, skill))
        for sector in spec["contributions"].values()
        for skill, coefficient in sector.items()
    ]
    coefficient_total = sum(coefficient for coefficient, _ in terms) or 1.0
    raw = sum(coefficient * skill for coefficient, skill in terms)
    return raw / coefficient_total * _form_factor(player) * _stamina_factor(player)


def _special_role_score(player: dict[str, Any], position: str) -> float:
    experience = float(player.get("experience", 0))
    if position == "captain":
        # Manual: choosing with 3 × leadership + 2 × experience generally
        # produces team experience equal to or above the automatic captain.
        return 3 * float(player.get("leadership", 0)) + 2 * experience
    if position == "set_piece_taker":
        # Direct set pieces consider set pieces and experience. The Manual
        # gives no relative coefficient, so the transparent selection index is
        # their unweighted sum rather than a fitted ratio.
        return _skill(player, "set_pieces") + experience
    if position == "penalty_taker":
        # A DISTINCT role from set_piece_taker (2026-08-09) — covers penalty
        # kicks, including shootouts ("penales de tanda"). Weighted formula
        # and the Technical-specialty bonus given directly by the user
        # 2026-08-09 (see positions.yaml note: not independently verified by
        # this engine against the wiki, unlike the rest of the matrix).
        cfg = _config()["special_roles"]["penalty_taker"]["coefficients"]
        base = (
            experience * cfg["experience"]
            + _skill(player, "set_pieces") * cfg["set_pieces"]
            + _skill(player, "scoring") * cfg["scoring"]
        )
        is_technical = int(player.get("specialty", 0)) == TECHNICAL_SPECIALTY_CODE
        return base * (1 + cfg["technical_specialty_bonus"]) if is_technical else base
    raise KeyError(f"unknown special role: {position}")


def rate(player: dict[str, Any], position: str) -> PositionRating:
    """Return a Manual-based contribution index for one role.

    ``rating`` deliberately remains the field name for API compatibility. Its
    meaning is now a sector-contribution index; it is neither a star rating nor
    an imitation of Hattrick Control.
    """
    spec, special = _spec_for(position)
    value = _special_role_score(player, position) if special else _pitch_contribution(player, spec)
    return PositionRating(position, spec["label"], round(max(value, 0.0), 2), special)


def rate_all(player: dict[str, Any], include_special: bool = False) -> list[PositionRating]:
    """Every pitch position, ordered by normalised Manual contribution."""
    cfg = _config()
    keys = list(cfg["positions"])
    if include_special:
        keys += list(cfg.get("special_roles", {}))
    return sorted((rate(player, k) for k in keys), key=lambda r: -r.rating)


def best_position(player: dict[str, Any]) -> PositionRating:
    """Role with the player's largest normalised Manual contribution."""
    return rate_all(player)[0]


def rank_for_position(
    players: list[dict[str, Any]], position: str
) -> list[tuple[dict[str, Any], PositionRating]]:
    """Order a squad by the Manual contribution generated in a given role."""
    rated = [(p, rate(p, position)) for p in players]
    return sorted(rated, key=lambda t: -t[1].rating)


def best_for_role(
    players: list[dict[str, Any]], role: str
) -> tuple[dict[str, Any], PositionRating] | None:
    """Manual-based captain and direct-free-kick recommendations."""
    if not players:
        return None
    return max(((p, rate(p, role)) for p in players), key=lambda t: t[1].rating)


def positions() -> dict[str, str]:
    return {k: v["label"] for k, v in _config()["positions"].items()}


def special_roles() -> dict[str, str]:
    return {k: v["label"] for k, v in _config().get("special_roles", {}).items()}


def model_info() -> dict[str, Any]:
    """Provenance and formulas displayed in the transparency screen."""
    cfg = _config()
    source = cfg["source"]
    return {
        "positions": len(cfg["positions"]),
        "specialRoles": len(cfg.get("special_roles", {})),
        "source": source["name"],
        "sourceUrl": source["url"],
        "sourceType": source["type"],
        "matrix": source["matrix"],
        "adjustments": cfg["adjustments"],
        "scoreLabel": "aporte medio ponderado a sectores",
        "configPath": str(CONFIG_PATH.name),
        "reference": cfg["reference"],
    }
