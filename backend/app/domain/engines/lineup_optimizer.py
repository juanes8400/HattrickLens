"""Optimizador de alineación — HL-120, HL-121, HL-122, HL-123.

Hattrick Control tiene una pantalla "Mejor equipo" que busca alineaciones por
formación. Nosotros resolvemos el problema bien: **asignación óptima**.

Elegir el mejor jugador para cada puesto uno a uno (lo intuitivo) no da el mejor
equipo. Si tu mejor central es también tu mejor lateral, ponerlo de central
puede costarte más en el lateral de lo que ganas en el centro. Es el problema
clásico de asignación y se resuelve exacto con el algoritmo húngaro, que aquí se
implementa sin dependencias externas.

Coste: O(n³) con n = 24 jugadores. Milisegundos.
"""
from dataclasses import dataclass, field
from typing import Any

from app.domain.engines.position_engine import positions as _positions
from app.domain.engines.position_engine import rate
from app.domain.value_objects.formations import (
    LINE_COUNTS,
    resolve_split,
    slots_for,
)

# Formaciones de Hattrick: (portero, defensas, medios, extremos, delanteros)
# El catálogo vive en `value_objects/formations.py`: lo comparten este motor y
# el del once ideal de la liga, para que "5-3-2" signifique lo mismo en las dos
# pantallas. Aquí se conserva el nombre `FORMATIONS` con el reparto por defecto
# de cada una, que es lo que usa el ranking de formaciones.
FORMATIONS: dict[str, list[str]] = {
    nombre: slots_for(nombre) for nombre in LINE_COUNTS
}

# Penalización por saturación posicional — Manual no Escrito (wiki.hattrick.org).
# Jugar 2 o 3 en la misma posición central resta rendimiento a TODOS los que
# la ocupan. Solo aplica a las posiciones "Normal" (DC, MC, DN): las variantes
# ofensiva/defensiva/hacia-lateral no están en las FORMATIONS de este motor,
# así que cualquier slot con esa clave ya es la variante Normal.
OVERCROWDING_PENALTY: dict[str, dict[int, float]] = {
    "central_defender": {2: 0.964, 3: 0.90},
    "inner_midfield": {2: 0.935, 3: 0.825},
    "forward": {2: 0.945, 3: 0.865},
}


def _overcrowd_multipliers(slots: list[str]) -> dict[str, float]:
    counts: dict[str, int] = {}
    for s in slots:
        counts[s] = counts.get(s, 0) + 1
    return {
        pos: OVERCROWDING_PENALTY[pos].get(counts[pos], 1.0)
        for pos in counts
        if pos in OVERCROWDING_PENALTY
    }


@dataclass
class Assignment:
    slot: int
    position: str
    label: str
    player: dict[str, Any]
    rating: float
    confidence: str


@dataclass
class Lineup:
    formation: str
    assignments: list[Assignment]
    total_rating: float
    bench: list[dict[str, Any]] = field(default_factory=list)

    @property
    def manual_share(self) -> float:
        """Kept for API compatibility. Every assignment uses a declared
        Manual no Escrito matrix, so this is always 1.0."""
        return 1.0 if self.assignments else 0.0


def _hungarian(cost: list[list[float]]) -> list[int]:
    """Asignación de coste mínimo. Devuelve, para cada fila, la columna asignada.

    Implementación clásica O(n³) con potenciales (método húngaro / JV simple).
    La matriz debe ser cuadrada.
    """
    n = len(cost)
    inf_ = float("inf")
    u = [0.0] * (n + 1)
    v = [0.0] * (n + 1)
    p = [0] * (n + 1)
    way = [0] * (n + 1)

    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [inf_] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], inf_, 0
            for j in range(1, n + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j], way[j] = cur, j0
                    if minv[j] < delta:
                        delta, j1 = minv[j], j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break

    result = [-1] * n
    for j in range(1, n + 1):
        if p[j] > 0:
            result[p[j] - 1] = j - 1
    return result


def _player_rating(
    player: dict[str, Any],
    position: str,
    overcrowd: dict[str, float] | None = None,
) -> float:
    value = rate(player, position).rating
    if overcrowd:
        value *= overcrowd.get(position, 1.0)
    return value


def best_lineup(
    players: list[dict[str, Any]],
    formation: str = "4-4-2",
    exclude: set[int] | None = None,
    central_defenders: int | None = None,
    inner_midfielders: int | None = None,
) -> Lineup:
    """Mejor once posible para una formación. HL-121.

    `exclude` son ht_player_id a dejar fuera (lesionados, sancionados, vendidos).

    `central_defenders`/`inner_midfielders` son el reparto de cada línea: el
    nombre de la formación no dice cuántos juegan por dentro, y con tres
    mediocentros o con uno y dos extremos el once óptimo no es el mismo. Sin
    ellos se usa el reparto por defecto de la formación.
    """
    if formation not in LINE_COUNTS:
        raise KeyError(f"formación desconocida: {formation}")
    slots = slots_for(formation, central_defenders, inner_midfielders)
    exclude = exclude or set()

    # 2026-08-16, corregido a petición del usuario: `InjuryLevel` 0 es
    # MAGULLADO, y un magullado puede jugar — solo a partir de 1 (semanas de
    # baja) el jugador está realmente descartado. Excluirlo dejaba fuera del
    # once a gente perfectamente disponible: el caso que lo destapó fue un
    # delantero de 15,74 que desapareció del mejor once por un magullón.
    available = [
        p for p in players
        if p.get("ht_player_id") not in exclude and p.get("injury_level", -1) < 1
    ]
    if len(available) < len(slots):
        raise ValueError(
            f"hacen falta {len(slots)} jugadores disponibles y solo hay {len(available)}"
        )

    overcrowd = _overcrowd_multipliers(slots)

    n = len(available)
    # Matriz cuadrada n×n: las columnas sobrantes son "banquillo" con coste 0
    big = max(len(slots), n)
    cost = [[0.0] * big for _ in range(big)]
    for i, player in enumerate(available):
        for j, pos in enumerate(slots):
            cost[i][j] = -_player_rating(player, pos, overcrowd)  # minimizar = maximizar

    matching = _hungarian(cost)

    assignments: list[Assignment] = []
    used: set[int] = set()
    for i, j in enumerate(matching):
        if j < len(slots):
            pos = slots[j]
            value = _player_rating(available[i], pos, overcrowd)
            assignments.append(
                Assignment(j, pos, _positions()[pos], available[i], round(value, 2), "config")
            )
            used.add(i)

    assignments.sort(key=lambda a: a.slot)
    bench = [p for i, p in enumerate(available) if i not in used]
    bench.sort(key=lambda p: -p.get("tsi", 0))

    return Lineup(
        formation=formation,
        assignments=assignments,
        total_rating=round(sum(a.rating for a in assignments), 2),
        bench=bench[:7],
    )


def best_formation(
    players: list[dict[str, Any]],
    exclude: set[int] | None = None,
) -> tuple[Lineup, dict[str, float]]:
    """Prueba TODAS las del catálogo y devuelve la mejor, con el ranking.

    Cada una con su reparto por defecto: comparar un 5-3-2 con tres
    mediocentros contra un 4-4-2 con el suyo no compararía lo mismo.
    """
    results: dict[str, Lineup] = {}
    for f in FORMATIONS:
        try:
            results[f] = best_lineup(players, f, exclude)
        except ValueError:
            continue
    if not results:
        raise ValueError("no hay jugadores suficientes para ninguna formación")
    ranking = {f: lu.total_rating for f, lu in
               sorted(results.items(), key=lambda kv: -kv[1].total_rating)}
    best = results[next(iter(ranking))]
    return best, ranking


#  Manual no Escrito (wiki.hattrick.org): multiplicador de mediocampo según
# Espíritu de Equipo × Actitud. IMPORTANTE — los 10 nombres de esta tabla NO
# coinciden con los 11 niveles (0-10) de `TEAM_SPIRIT` en ht_constants.py:
# son dos escalas de nombres distintas, y no hay evidencia para mapear una
# fila de esta tabla a un nivel concreto de CHPP con certeza. Por eso se
# expone como tabla de referencia con SUS PROPIOS nombres (explorable), sin
# intentar adivinar a qué Espíritu real del equipo corresponde cada fila.
TEAM_SPIRIT_ATTITUDE_MULTIPLIER: list[tuple[str, float, float, float]] = [
    # (nombre del manual, PIC, Normal, MOTS)
    ("Muy agresivos", 0.63, 0.72, 0.81),
    ("Furiosos", 0.75, 0.86, 0.97),
    ("Irritados", 0.81, 0.93, 1.05),
    ("Indiferentes", 0.87, 1.00, 1.13),
    ("Calmados", 0.92, 1.07, 1.22),
    ("Satisfechos", 0.98, 1.14, 1.30),
    ("Felices", 1.04, 1.21, 1.38),
    ("Eufóricos", 1.10, 1.28, 1.46),
    ("Caminando en las nubes", 1.16, 1.35, 1.54),
    ("¡Paraíso en la tierra!", 1.22, 1.42, 1.62),
]
