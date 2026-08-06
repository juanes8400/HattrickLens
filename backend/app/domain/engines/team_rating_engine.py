"""Calificación de equipo por sector — fórmula EXACTA de contribución
posicional del Manual no Escrito (wiki.hattrick.org), la misma familia de
datos que usan herramientas como Hattrick Organizer.

Es un motor DISTINTO de `position_engine.py`. Ese responde "¿en qué posición
rinde mejor este jugador?" con un modelo ajustado por calibración (R² 0.951,
error medio 0.331 contra 41 observaciones reales) — sigue siendo el que
decide el once en `lineup_optimizer.py`, porque está benchmarkeado contra
datos reales y este motor nuevo todavía no. Este responde una pregunta
distinta: "dado un once ya armado, ¿cuánto aporta cada sector según la
fórmula exacta de la comunidad?" — un panel informativo adicional, no un
reemplazo del optimizador.

DOS SIMPLIFICACIONES DELIBERADAS, declaradas para no fingir más precisión de
la que hay:

1. **Sin lado (L/R).** La tabla original de la comunidad separa Defensa/
   Ataque Lateral por izquierda y derecha, con contribuciones distintas según
   el lado — pero la taxonomía de posiciones de este motor (`positions.yaml`,
   compartida con `lineup_optimizer`) no distingue lado. Se agrupan ambos en
   un único "lateral_def"/"lateral_att" pooled. Para el Delantero hacia
   Lateral, que sí reporta cifras separadas para su lado y el opuesto, se
   suman ambas.

2. **Habilidades crudas, sin modificadores de partido.** No se aplica forma,
   condición, experiencia, clima ni Espíritu de Equipo — esos ya tienen sus
   propios paneles explorables (Ranking de formaciones, Impacto del clima,
   Espíritu de Equipo × Actitud). Mezclarlos aquí impediría aislar qué hace
   la fórmula de contribución en sí.
"""
from dataclasses import dataclass
from typing import Any

SECTORS = ("central_def", "lateral_def", "midfield", "central_att", "lateral_att")

SECTOR_LABELS = {
    "central_def": "Defensa central",
    "lateral_def": "Defensa lateral",
    "midfield": "Mediocampo",
    "central_att": "Ataque central",
    "lateral_att": "Ataque lateral",
}

# Contribución relativa exacta por posición — Manual no Escrito. Claves de
# habilidad iguales a `position_engine.SKILL_KEYS`.
POSITION_SECTOR_CONTRIBUTION: dict[str, dict[str, dict[str, float]]] = {
    "keeper": {
        "central_def": {"keeper": 0.87, "defending": 0.35},
        "lateral_def": {"keeper": 0.61, "defending": 0.25},
    },
    "central_defender": {
        "central_def": {"defending": 1.00},
        "lateral_def": {"defending": 0.52},
        "midfield": {"playmaking": 0.25},
    },
    "central_defender_towards_wing": {
        "central_def": {"defending": 0.67},
        "lateral_def": {"defending": 0.81},
        "midfield": {"playmaking": 0.15},
        "lateral_att": {"winger": 0.26},
    },
    "central_defender_offensive": {
        "central_def": {"defending": 0.73},
        "lateral_def": {"defending": 0.40},
        "midfield": {"playmaking": 0.40},
    },
    "wingback": {
        "central_def": {"defending": 0.38},
        "lateral_def": {"defending": 0.92},
        "midfield": {"playmaking": 0.15},
        "lateral_att": {"winger": 0.59},
    },
    "wingback_defensive": {
        "central_def": {"defending": 0.43},
        "lateral_def": {"defending": 1.00},
        "midfield": {"playmaking": 0.10},
        "lateral_att": {"winger": 0.45},
    },
    "wingback_towards_middle": {
        "central_def": {"defending": 0.70},
        "lateral_def": {"defending": 0.75},
        "midfield": {"playmaking": 0.20},
        "lateral_att": {"winger": 0.35},
    },
    "wingback_offensive": {
        "central_def": {"defending": 0.35},
        "lateral_def": {"defending": 0.74},
        "midfield": {"playmaking": 0.20},
        "lateral_att": {"winger": 0.69},
    },
    "inner_midfield": {
        "midfield": {"playmaking": 1.00},
        "central_def": {"defending": 0.40},
        "lateral_def": {"defending": 0.19},
        "central_att": {"scoring": 0.22, "passing": 0.33},
        "lateral_att": {"passing": 0.26},
    },
    "inner_midfield_offensive": {
        "midfield": {"playmaking": 0.95},
        "central_def": {"defending": 0.16},
        "lateral_def": {"defending": 0.09},
        "central_att": {"scoring": 0.31, "passing": 0.49},
        "lateral_att": {"passing": 0.36},
    },
    "inner_midfield_defensive": {
        "midfield": {"playmaking": 0.95},
        "central_def": {"defending": 0.58},
        "lateral_def": {"defending": 0.27},
        "central_att": {"scoring": 0.13, "passing": 0.18},
        "lateral_att": {"passing": 0.14},
    },
    "inner_midfield_towards_wing": {
        "midfield": {"playmaking": 0.90},
        "central_def": {"defending": 0.33},
        "lateral_def": {"defending": 0.24},
        "central_att": {"passing": 0.23},
        "lateral_att": {"winger": 0.59, "passing": 0.31},
    },
    "winger": {
        "midfield": {"playmaking": 0.45},
        "central_def": {"defending": 0.20},
        "lateral_def": {"defending": 0.35},
        "central_att": {"passing": 0.11},
        "lateral_att": {"winger": 0.86, "passing": 0.26},
    },
    "winger_offensive": {
        "midfield": {"playmaking": 0.30},
        "central_def": {"defending": 0.13},
        "lateral_def": {"defending": 0.22},
        "central_att": {"passing": 0.13},
        "lateral_att": {"winger": 1.00, "passing": 0.29},
    },
    "winger_towards_middle": {
        "midfield": {"playmaking": 0.55},
        "central_def": {"defending": 0.25},
        "lateral_def": {"defending": 0.29},
        "central_att": {"passing": 0.16},
        "lateral_att": {"winger": 0.74, "passing": 0.15},
    },
    "winger_defensive": {
        "midfield": {"playmaking": 0.30},
        "central_def": {"defending": 0.25},
        "lateral_def": {"defending": 0.61},
        "central_att": {"passing": 0.05},
        "lateral_att": {"winger": 0.69, "passing": 0.21},
    },
    "forward": {
        "midfield": {"playmaking": 0.25},
        "central_att": {"scoring": 1.00, "passing": 0.33},
        "lateral_att": {"winger": 0.24, "passing": 0.14, "scoring": 0.27},
    },
    "forward_defensive": {
        "midfield": {"playmaking": 0.35},
        "central_att": {"scoring": 0.56, "passing": 0.53},
        "lateral_att": {"winger": 0.13, "passing": 0.31, "scoring": 0.13},
    },
    "forward_towards_wing": {
        "midfield": {"playmaking": 0.15},
        "central_att": {"scoring": 0.66, "passing": 0.23},
        # Pooled: propio (51% Anot, 21% Pas, 64% Lat) + opuesto (19%, 6%, 21%).
        "lateral_att": {"scoring": 0.70, "passing": 0.27, "winger": 0.85},
    },
}

# Misma tabla que `lineup_optimizer.OVERCROWDING_PENALTY` — una sola fuente
# (el manual), dos motores que la necesitan.
OVERCROWDING_PENALTY: dict[str, dict[int, float]] = {
    "central_defender": {2: 0.964, 3: 0.90},
    "inner_midfield": {2: 0.935, 3: 0.825},
    "forward": {2: 0.945, 3: 0.865},
}


@dataclass
class SectorContribution:
    player_name: str
    position_label: str
    amount: float


@dataclass
class SectorRatings:
    ratings: dict[str, float]
    top_contributors: dict[str, list[SectorContribution]]


def compute_sector_ratings(
    assignments: list[tuple[dict[str, Any], str, str]],
) -> SectorRatings:
    """`assignments`: lista de (jugador, position_key, label). El jugador
    necesita `skills` (crudas, sin ajustar) y `name`. Posiciones sin entrada
    en `POSITION_SECTOR_CONTRIBUTION` (roles especiales) se ignoran."""
    counts: dict[str, int] = {}
    for _, pos, _ in assignments:
        counts[pos] = counts.get(pos, 0) + 1

    ratings = dict.fromkeys(SECTORS, 0.0)
    contributions: dict[str, list[SectorContribution]] = {s: [] for s in SECTORS}

    for player, pos, label in assignments:
        table = POSITION_SECTOR_CONTRIBUTION.get(pos)
        if table is None:
            continue
        overcrowd = OVERCROWDING_PENALTY.get(pos, {}).get(counts[pos], 1.0)
        skills = player.get("skills", {})
        for sector, weights in table.items():
            amount = sum(skills.get(skill, 0) * pct for skill, pct in weights.items())
            amount *= overcrowd
            if amount <= 0:
                continue
            ratings[sector] += amount
            contributions[sector].append(
                SectorContribution(player.get("name", "?"), label, round(amount, 2))
            )

    for sector in contributions:
        contributions[sector].sort(key=lambda c: -c.amount)

    return SectorRatings(
        ratings={s: round(v, 2) for s, v in ratings.items()},
        top_contributors={s: v[:3] for s, v in contributions.items()},
    )
