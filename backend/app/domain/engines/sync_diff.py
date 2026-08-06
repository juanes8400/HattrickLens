"""Diff de sync: que cambio desde la ultima vez.

Esto es una de las cosas que Hattrick Control hace bien: despues de cargar
datos, no te obliga a comparar de memoria. Este modulo recibe el estado viejo
y el nuevo, justo durante el sync, y devuelve frases legibles para la UI.
"""
from dataclasses import dataclass
from typing import Any

from app.domain.value_objects.ht_constants import CONFIDENCE, SKILL_LABELS, TEAM_SPIRIT

ECONOMY_FIELDS: dict[str, str] = {
    "cash": "Caja",
    "sponsors_popularity": "Popularidad con patrocinadores",
    "supporters_popularity": "Popularidad con la aficion",
    "fan_club_size": "Pena de aficionados",
    "income_sum": "Ingresos totales",
    "costs_sum": "Gastos totales",
}
ECONOMY_MONEY_FIELDS = {"cash", "income_sum", "costs_sum"}

PLAYER_LEVEL_FIELDS: dict[str, str] = {
    "form": "Forma",
    "stamina": "Resistencia",
    "experience": "Experiencia",
}


def diff_player_skills(
    old: dict[str, Any] | None, new: dict[str, Any], player_name: str
) -> list[str]:
    """Detecta cambios relevantes de jugador.

    `old is None` significa primera vez que vemos al jugador: se anuncia como
    alta de plantilla, no como una lista enorme de "subidas" desde cero.
    """
    if old is None:
        return [f"{player_name} se unio a la plantilla"]

    changes: list[str] = []
    old_skills = old.get("skills", {}) or {}
    new_skills = new.get("skills", {}) or {}
    for skill, label in SKILL_LABELS.items():
        o, n = old_skills.get(skill), new_skills.get(skill)
        if o is not None and n is not None and o != n:
            verb = "subio" if n > o else "bajo"
            changes.append(f"{player_name}: {label} {verb} de {o} a {n}")

    if old.get("tsi") != new.get("tsi"):
        changes.append(f"{player_name}: TSI {old.get('tsi', 0):,} -> {new.get('tsi', 0):,}")

    if old.get("salary") != new.get("salary"):
        changes.append(
            f"{player_name}: Salario {old.get('salary', 0):,} -> {new.get('salary', 0):,}"
        )

    for field, label in PLAYER_LEVEL_FIELDS.items():
        if old.get(field) != new.get(field):
            changes.append(f"{player_name}: {label} {old.get(field, 0)} -> {new.get(field, 0)}")

    old_injury, new_injury = old.get("injury_level", -1), new.get("injury_level", -1)
    if old_injury != new_injury:
        if new_injury == -1:
            changes.append(f"{player_name}: se recupero de la lesion")
        elif old_injury == -1:
            changes.append(f"{player_name}: se lesiono")
        else:
            changes.append(f"{player_name}: lesion de nivel {old_injury} a {new_injury}")

    if old.get("is_transfer_listed") != new.get("is_transfer_listed"):
        listed = new.get("is_transfer_listed")
        changes.append(f"{player_name}: {'puesto en' if listed else 'retirado del'} mercado")

    return changes


def diff_economy(
    old: dict[str, Any] | None, new: dict[str, Any], currency: str = "", rate: float = 1.0
) -> list[str]:
    """`rate`: CHPP devuelve los montos de economy.xml en la moneda base del
    juego (SEK), no en la local del equipo — corrección 2026-08-05, bug real
    encontrado en vivo: este mensaje mostraba el número crudo en SEK con la
    etiqueta de la moneda LOCAL (p. ej. "10,000 US$" cuando el cambio real,
    dividido por la tasa de Colombia = 10, era 1,000 US$). Mismo criterio
    de conversión que `conv()` en player_balance.py."""
    if old is None:
        return []
    changes = []
    for field, label in ECONOMY_FIELDS.items():
        o, n = old.get(field), new.get(field)
        if o is None or n is None or o == n:
            continue
        if field in ECONOMY_MONEY_FIELDS:
            o_conv, n_conv = round(o / rate), round(n / rate)
            if o_conv == n_conv:
                continue  # el cambio crudo en SEK no llega a mover la moneda local
            changes.append(f"{label}: {o_conv:,} -> {n_conv:,} {currency}".strip())
        else:
            changes.append(f"{label}: {o} -> {n}")
    return changes


def diff_training(old: dict[str, Any] | None, new: dict[str, Any]) -> list[str]:
    if old is None:
        return []
    changes = []
    if old.get("training_type") != new.get("training_type"):
        changes.append(
            f"Entrenamiento cambiado: tipo {old.get('training_type')} -> "
            f"{new.get('training_type')}"
        )
    if old.get("training_level") != new.get("training_level"):
        changes.append(
            f"Nivel de entrenamiento: {old.get('training_level')} -> "
            f"{new.get('training_level')}"
        )
    old_trainer, new_trainer = old.get("trainer_name", ""), new.get("trainer_name", "")
    if old_trainer != new_trainer and new_trainer:
        changes.append(f"Nuevo entrenador: {new_trainer}")
    if old.get("morale") != new.get("morale"):
        before, after = old.get("morale", -1), new.get("morale", -1)
        changes.append(
            f"Espíritu del equipo: {TEAM_SPIRIT.get(before, before)} -> "
            f"{TEAM_SPIRIT.get(after, after)}"
        )
    if old.get("self_confidence") != new.get("self_confidence"):
        before = old.get("self_confidence", -1)
        after = new.get("self_confidence", -1)
        changes.append(
            f"Confianza: {CONFIDENCE.get(before, before)} -> {CONFIDENCE.get(after, after)}"
        )
    return changes


def diff_standing(old_position: int | None, new_position: int, team_name: str) -> str | None:
    if old_position is None or old_position == new_position:
        return None
    verb = "subio" if new_position < old_position else "bajo"
    return f"{team_name} {verb} de la posicion {old_position} a la {new_position}"


@dataclass(frozen=True)
class MatchState:
    status: str
    home_goals: int
    away_goals: int


def diff_match(
    before: MatchState | None, after: MatchState, is_home: bool, opponent: str
) -> str | None:
    """Anuncia solo resultados nuevos; no repite partidos ya conocidos."""
    if before is None or after.status != "FINISHED":
        return None
    if before.status == "FINISHED" and (
        before.home_goals == after.home_goals and before.away_goals == after.away_goals
    ):
        return None

    own_goals = after.home_goals if is_home else after.away_goals
    rival_goals = after.away_goals if is_home else after.home_goals
    if own_goals > rival_goals:
        verdict = "Ganaste"
    elif own_goals < rival_goals:
        verdict = "Perdiste"
    else:
        verdict = "Empataste"
    return f"{verdict} {own_goals}-{rival_goals} vs {opponent}"
