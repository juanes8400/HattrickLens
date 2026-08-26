"""Comisión de "club anterior" — HL-161, 2026-08-14, pedido explícitamente
con las tablas oficiales de Hattrick (docs/reference/bonificaciones_hattrick.html,
docs/reference/tasas_transferencias_hattrick.html).

Cuando alguien revende a un ex-jugador nuestro, Hattrick nos paga un % de
esa reventa según cuántos partidos REALES jugó con nosotros mientras fue
nuestro — un dato exacto, no una aproximación: reemplaza por completo el
reparto heurístico que antes vivía en `resale_bonus.py` ("ya no necesitamos
aproximarnos porque ya tenemos todo", 2026-08-14).

Dos piezas de este cálculo:
1. `previous_club_bonus_pct(games)`: la tabla oficial "Dinero por club
   anterior", por partidos jugados.
2. `counts_toward_games_played(match_type)`: qué partidos cuentan — pedido
   explícitamente 2026-08-14: liga, copa y amistosos SÍ cuentan; solo
   torneos, duelos, escaleras y preparación quedan fuera (el mismo
   `NON_OFFICIAL_MATCH_TYPES` que ya usa el resto de la app, pero SIN la
   exclusión adicional de amistosos que sí aplica en otras pantallas).

"Jugó de verdad" (no solo banca) se decide en la capa de aplicación, no
aquí: `matchlineup.xml` v2.1 marca a un suplente no utilizado con
`RatingStars=0` exacto — verificado en vivo 2026-08-14 (RoleID 114/119,
"Suplente (portero)"/"Suplente (lateral)", ambos con 0/0) — así que
`did_play(rating_stars)` es la única regla que hace falta.
"""

from app.domain.value_objects.ht_constants import NON_OFFICIAL_MATCH_TYPES

# Tabla oficial de Hattrick ("Dinero por club anterior"): SOLO estos
# escalones existen — se leen como tramos (el valor se mantiene hasta el
# siguiente escalón), no interpolados como la tabla de días del agente: son
# conteos de partidos, no una magnitud continua.
PREVIOUS_CLUB_PCT_BREAKPOINTS: list[tuple[int, float]] = [
    (0, 0.0),
    (1, 0.0025),
    (2, 0.005),
    (3, 0.01),
    (4, 0.015),
    (5, 0.02),
    (7, 0.025),
    (10, 0.03),
    (20, 0.035),
    (40, 0.04),
]


def previous_club_bonus_pct(games_played: int) -> float:
    """% de la reventa que nos toca como club anterior, según cuántos
    partidos REALES jugó el jugador con nosotros. Tramos, no interpolación
    — 8 partidos cae en el tramo "7 a 9" (2,5%), no a medio camino entre
    2,5% y 3%."""
    pct = PREVIOUS_CLUB_PCT_BREAKPOINTS[0][1]
    for threshold, value in PREVIOUS_CLUB_PCT_BREAKPOINTS:
        if games_played >= threshold:
            pct = value
        else:
            break
    return pct


def counts_toward_games_played(match_type: int) -> bool:
    """Liga, copa, promoción y amistosos SÍ cuentan para "club anterior"
    (confirmado explícitamente por el usuario 2026-08-14) — solo torneos,
    duelos, escaleras y preparación quedan fuera."""
    return match_type not in NON_OFFICIAL_MATCH_TYPES


def did_play(rating_stars: float) -> bool:
    """Un suplente no utilizado siempre trae RatingStars=0 exacto en
    matchlineup.xml v2.1 — cualquier valor mayor que 0 es participación
    real, aunque el partido haya sido flojo."""
    return rating_stars > 0
