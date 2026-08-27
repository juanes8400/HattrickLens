"""Inferencia de la habilidad entrenada de cada jugador vendido.

Regla suministrada expresamente por el usuario el 2026-08-26:

1. Para cada venta se compara el primer snapshot histórico del jugador con el
   último snapshot anterior o igual a la venta.
2. Si una de las siete habilidades tiene un aumento positivo máximo único,
   esa es la asignación directa.
3. Si no hubo aumentos o el máximo empata, gana primero la habilidad con más
   NIVELES acumulados entre los vendidos de la misma temporada.
4. Si empatan en niveles, gana la que subió en más JUGADORES de la temporada.
5. Si persiste el empate, se usa el entrenamiento actual y después la
   prioridad fija pedida por el usuario.
6. Sin ninguna evidencia en la temporada queda ``Sin evidencia suficiente``:
   el entrenamiento actual no puede reconstruir qué se entrenaba años atrás.

Este motor no calibra parámetros ni usa regresiones. Solo aplica una regla
determinista sobre diferencias observadas.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Literal

TRAINABLE_SKILLS = (
    "keeper",
    "defending",
    "playmaking",
    "winger",
    "passing",
    "scoring",
    "set_pieces",
)

# Prioridad exacta pedida por el usuario para el último desempate de temporada.
SKILL_TIEBREAK_PRIORITY = (
    "defending",
    "keeper",
    "playmaking",
    "scoring",
    "winger",
    "passing",
    "set_pieces",
)

AssignmentMethod = Literal[
    "direct_maximum",
    "season_levels",
    "season_players",
    "season_current_training",
    "season_skill_priority",
    "insufficient_evidence",
]


@dataclass(frozen=True)
class SoldPlayerEvidence:
    stint_id: int
    player_id: int
    sale_season: int | None
    is_real_sale: bool
    increases: dict[str, int]


@dataclass(frozen=True)
class TrainingAssignment:
    skill: str | None
    levels: int | None
    method: AssignmentMethod


def _direct_skill(evidence: SoldPlayerEvidence) -> str | None:
    if not evidence.is_real_sale:
        return None
    if not evidence.increases:
        return None
    maximum = max(evidence.increases.values(), default=0)
    if maximum <= 0:
        return None
    winners = [skill for skill, increase in evidence.increases.items() if increase == maximum]
    return winners[0] if len(winners) == 1 else None


def derive_training_assignments(
    evidence_rows: list[SoldPlayerEvidence],
    current_training_skill: str | None = None,
) -> dict[int, TrainingAssignment]:
    """Devuelve una asignación por stint cerrado.

    Cada jugador cuenta una sola vez por temporada. Si tuvo varias ventas en
    ella, se conserva por habilidad el mayor aumento observado hasta esas
    ventas; sumar las etapas duplicaría el mismo tramo histórico.
    """

    direct_by_stint = {row.stint_id: _direct_skill(row) for row in evidence_rows}

    increases_by_season_player: dict[tuple[int, int], dict[str, int]] = defaultdict(dict)
    for row in evidence_rows:
        if row.sale_season is None or not row.is_real_sale:
            continue
        player_increases = increases_by_season_player[(row.sale_season, row.player_id)]
        for skill in TRAINABLE_SKILLS:
            player_increases[skill] = max(
                player_increases.get(skill, 0),
                max(row.increases.get(skill, 0), 0),
            )

    levels_by_season: dict[int, Counter[str]] = defaultdict(Counter)
    players_by_season: dict[int, Counter[str]] = defaultdict(Counter)
    for (season, _player_id), increases in increases_by_season_player.items():
        for skill in TRAINABLE_SKILLS:
            increase = increases.get(skill, 0)
            levels_by_season[season][skill] += increase
            if increase > 0:
                players_by_season[season][skill] += 1

    assignments: dict[int, TrainingAssignment] = {}
    for row in evidence_rows:
        direct = direct_by_stint[row.stint_id]
        if direct is not None:
            assignments[row.stint_id] = TrainingAssignment(
                skill=direct,
                levels=row.increases.get(direct, 0),
                method="direct_maximum",
            )
            continue

        if not row.is_real_sale:
            assignments[row.stint_id] = TrainingAssignment(
                skill=None,
                levels=None,
                method="insufficient_evidence",
            )
            continue

        level_scores = (
            levels_by_season.get(row.sale_season, Counter())
            if row.sale_season is not None
            else Counter()
        )
        maximum_levels = max(
            (level_scores.get(skill, 0) for skill in TRAINABLE_SKILLS),
            default=0,
        )
        level_candidates = [
            skill for skill in TRAINABLE_SKILLS if level_scores.get(skill, 0) == maximum_levels
        ]
        if maximum_levels > 0 and len(level_candidates) == 1:
            winner = level_candidates[0]
            assignments[row.stint_id] = TrainingAssignment(
                skill=winner,
                levels=row.increases.get(winner, 0),
                method="season_levels",
            )
            continue

        if maximum_levels == 0:
            assignments[row.stint_id] = TrainingAssignment(
                skill=None,
                levels=None,
                method="insufficient_evidence",
            )
            continue

        player_scores = (
            players_by_season.get(row.sale_season, Counter())
            if row.sale_season is not None
            else Counter()
        )
        maximum_players = max(
            (player_scores.get(skill, 0) for skill in level_candidates),
            default=0,
        )
        player_candidates = [
            skill for skill in level_candidates if player_scores.get(skill, 0) == maximum_players
        ]
        if maximum_levels > 0 and len(player_candidates) == 1:
            winner = player_candidates[0]
            assignments[row.stint_id] = TrainingAssignment(
                skill=winner,
                levels=row.increases.get(winner, 0),
                method="season_players",
            )
            continue

        candidates = player_candidates
        if current_training_skill in candidates:
            winner = current_training_skill
            assignments[row.stint_id] = TrainingAssignment(
                skill=winner,
                levels=row.increases.get(winner, 0),
                method="season_current_training",
            )
            continue

        priority_winner = next(skill for skill in SKILL_TIEBREAK_PRIORITY if skill in candidates)
        assignments[row.stint_id] = TrainingAssignment(
            skill=priority_winner,
            levels=row.increases.get(priority_winner, 0),
            method="season_skill_priority",
        )

    return assignments
