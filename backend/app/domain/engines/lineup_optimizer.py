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

# Órdenes individuales de cada puesto. La clave es la posición "Normal" y la
# lista, todas las variantes que Hattrick permite dar ahí — la primera es
# siempre la Normal. El motor de posiciones ya sabe puntuar las diecinueve;
# aquí solo se declara cuáles caben en cada casilla de la formación.
#
# 2026-08-21, pedido por los usuarios: antes el once se resolvía SOLO con las
# variantes Normal, de modo que la herramienta proponía un lateral cuando lo
# que le convenía al equipo era un lateral ofensivo. Ahora la orden se elige
# dentro de la misma asignación: para cada pareja jugador-casilla se toma su
# mejor variante, y el algoritmo húngaro reparte con ese valor. Es exacto,
# porque el máximo por celda no cambia la estructura del problema.
ORDER_VARIANTS: dict[str, tuple[str, ...]] = {
    "keeper": ("keeper",),
    "central_defender": (
        "central_defender",
        "central_defender_towards_wing",
        "central_defender_offensive",
    ),
    "wingback": (
        "wingback",
        "wingback_towards_middle",
        "wingback_offensive",
        "wingback_defensive",
    ),
    "inner_midfield": (
        "inner_midfield",
        "inner_midfield_towards_wing",
        "inner_midfield_offensive",
        "inner_midfield_defensive",
    ),
    "winger": (
        "winger",
        "winger_towards_middle",
        "winger_offensive",
        "winger_defensive",
    ),
    "forward": (
        "forward",
        "forward_defensive",
        "forward_towards_wing",
    ),
}

# Lo que hay que sumar por línea para la penalización por saturación: una
# variante ofensiva sigue ocupando el centro de la defensa.
#: La orden que se pierde en el centro de un carril de tres.
HACIA_EL_LATERAL = "_towards_wing"


def variantes_de_casilla(slots: list[str], indice: int) -> tuple[str, ...]:
    """Las ordenes que caben en ESTA casilla, no en ese puesto en general.

    Los carriles centrales tienen lado. Con tres en linea hay uno izquierdo,
    uno central y uno derecho; el lado no cambia lo que aporta el jugador,
    pero decide que ordenes tiene: los de los lados pueden salir «hacia el
    lateral» --cada uno hacia el suyo-- y el del medio no, porque no tiene
    lado al que salir.

    Vale igual para los tres carriles: defensas centrales, medios centros y
    delanteros. Con dos en linea los dos son de lado y no se quita nada.

    Antes esto no se miraba y el optimizador podia proponer un central del
    medio yendo hacia el lateral: una alineacion que Hattrick no deja montar.
    """
    slot = slots[indice]
    todas = ORDER_VARIANTS.get(slot, (slot,))
    inicio = indice
    while inicio > 0 and slots[inicio - 1] == slot:
        inicio -= 1
    fin = indice
    while fin + 1 < len(slots) and slots[fin + 1] == slot:
        fin += 1
    if fin - inicio + 1 != 3 or indice != inicio + 1:
        return todas
    return tuple(v for v in todas if not v.endswith(HACIA_EL_LATERAL))


BASE_OF_VARIANT: dict[str, str] = {
    variante: base
    for base, variantes in ORDER_VARIANTS.items()
    for variante in variantes
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
    # La posición CON su orden individual: "wingback_offensive", no "wingback".
    position: str
    label: str
    player: dict[str, Any]
    rating: float
    confidence: str
    # La casilla de la formación, sin la orden. Dos asignaciones distintas
    # pueden compartirla (dos centrales, uno normal y otro hacia el lateral).
    base_position: str = ""
    # True cuando la orden la fijó el usuario y el motor no pudo elegirla.
    order_pinned: bool = False


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
        # Por línea: un central ofensivo sigue siendo uno de los centrales que
        # se estorban entre sí.
        value *= overcrowd.get(BASE_OF_VARIANT.get(position, position), 1.0)
    return value


def _best_variant(
    player: dict[str, Any],
    slot: str,
    overcrowd: dict[str, float],
    pinned: str | None,
    permitidas: tuple[str, ...] | None = None,
) -> tuple[str, float]:
    """La mejor orden individual para este jugador en esta casilla.

    Con `pinned` no hay nada que elegir: el usuario ya decidió la orden y el
    motor solo decide QUIÉN la juega. Es la forma de decir "aquí quiero un
    lateral ofensivo, dime cuál de mis jugadores rinde más así".
    """
    variantes = (
        (pinned,) if pinned
        else (permitidas if permitidas is not None else ORDER_VARIANTS.get(slot, (slot,)))
    )
    mejor, valor = variantes[0], _player_rating(player, variantes[0], overcrowd)
    for variante in variantes[1:]:
        actual = _player_rating(player, variante, overcrowd)
        if actual > valor:
            mejor, valor = variante, actual
    return mejor, valor


def best_lineup(
    players: list[dict[str, Any]],
    formation: str = "4-4-2",
    exclude: set[int] | None = None,
    central_defenders: int | None = None,
    inner_midfielders: int | None = None,
    orders: dict[int, str] | None = None,
    optimize_orders: bool = True,
) -> Lineup:
    """Mejor once posible para una formación. HL-121.

    `exclude` son ht_player_id a dejar fuera (lesionados, sancionados, vendidos).

    `central_defenders`/`inner_midfielders` son el reparto de cada línea: el
    nombre de la formación no dice cuántos juegan por dentro, y con tres
    mediocentros o con uno y dos extremos el once óptimo no es el mismo. Sin
    ellos se usa el reparto por defecto de la formación.

    `orders` fija la orden individual de casillas concretas (índice de casilla
    → posición con orden, p. ej. {3: "wingback_offensive"}). Para esas el
    motor ya no elige la orden, solo el jugador. El resto se optimizan solas
    salvo que `optimize_orders` sea False, que devuelve el comportamiento de
    antes: todo el mundo en su variante Normal.
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
    fijadas = dict(orders or {})
    # Una orden fijada tiene que caber en SU casilla. Sin esto, pedir un
    # "lateral ofensivo" en la casilla de un central se aceptaba en silencio y
    # devolvía un once que Hattrick no dejaría montar.
    for indice, variante in fijadas.items():
        if not 0 <= indice < len(slots):
            raise ValueError(f"la casilla {indice} no existe en {formation}")
        permitidas = variantes_de_casilla(slots, indice)
        if variante not in permitidas:
            raise ValueError(
                f"«{variante}» no es una orden de {slots[indice]}; "
                f"las de esa casilla son {', '.join(permitidas)}"
            )

    def _elegir(player: dict[str, Any], j: int) -> tuple[str, float]:
        slot = slots[j]
        pinned = fijadas.get(j)
        if pinned is None and not optimize_orders:
            pinned = slot
        return _best_variant(
            player, slot, overcrowd, pinned, variantes_de_casilla(slots, j)
        )

    n = len(available)
    # Matriz cuadrada n×n: las columnas sobrantes son "banquillo" con coste 0.
    # Cada celda ya lleva la MEJOR orden de ese jugador en esa casilla, así que
    # el húngaro sigue resolviendo una asignación normal y el resultado sigue
    # siendo el óptimo exacto.
    big = max(len(slots), n)
    cost = [[0.0] * big for _ in range(big)]
    elegido: dict[tuple[int, int], tuple[str, float]] = {}
    for i, player in enumerate(available):
        for j in range(len(slots)):
            variante, valor = _elegir(player, j)
            elegido[(i, j)] = (variante, valor)
            cost[i][j] = -valor  # minimizar = maximizar

    matching = _hungarian(cost)

    assignments: list[Assignment] = []
    used: set[int] = set()
    for i, j in enumerate(matching):
        if j < len(slots):
            pos, value = elegido[(i, j)]
            assignments.append(
                Assignment(
                    j, pos, _positions()[pos], available[i], round(value, 2), "config",
                    base_position=slots[j], order_pinned=j in fijadas,
                )
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
