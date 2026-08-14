"""Tabla de referencia de Resistencia (condición) — Federación Ocerin.

Hattrick no publica la fórmula real de subida/bajada de condición; esta es
una tabla comunitaria (aportada por el usuario, screenshot 2026-08-10) que
cruza edad × % de entrenamiento de resistencia REAL contra el nivel
esperado. A diferencia de Fidelidad (que solo sube), Resistencia puede
subir O BAJAR: si el % real de entrenamiento de resistencia no alcanza
para la edad del jugador, el nivel esperado desciende.

`% de entrenamiento de resistencia real` = intensidad total del club × %
de esa intensidad dedicado a resistencia (`stamina_share`), NO el
`stamina_share` crudo — un club entrenando al 40% con 50% dedicado a
resistencia solo está poniendo un 20% real de esfuerzo en resistencia
(ver `TrainingSetup.effective_stamina_intensity`).

Los niveles de la tabla original venían en palabras (Pobre, Débil,
Insuficiente, Aceptable, Bueno, Excelente, Formidable) — se guardan aquí
como el índice numérico equivalente de `SKILL_LEVELS` (ht_constants.py),
que ya nombra esos mismos niveles 0-20 (Resistencia solo usa el tramo 3-9
de ese rango completo, el mismo límite real de Hattrick para esta
habilidad).

La tabla solo cubre edades 17-36: fuera de ese rango no hay evidencia, así
que `stamina_forecast_level` devuelve `None` en vez de extrapolar. El
porcentaje de entrenamiento SÍ se recorta al rango cubierto (5%-30%) — un
club con menos o más esfuerzo real cae al extremo conocido más cercano en
vez de quedarse sin previsión.
"""
from __future__ import annotations

# Límite inferior de cada bucket de "% de entrenamiento de resistencia
# real" — el límite superior es el inferior del siguiente bucket (o 30
# para el último). Mismo orden que las columnas de la tabla original.
STAMINA_TRAINING_PCT_BUCKETS: tuple[int, ...] = (5, 11, 16, 21, 26)

# edad -> nivel esperado por bucket, mismo orden que
# STAMINA_TRAINING_PCT_BUCKETS. Niveles en índice de SKILL_LEVELS
# (3=pobre .. 9=formidable, el rango real de Resistencia en Hattrick).
STAMINA_FORECAST_TABLE: dict[int, tuple[int, int, int, int, int]] = {
    17: (5, 6, 6, 6, 6),
    18: (5, 6, 7, 7, 7),
    19: (6, 7, 7, 8, 8),
    20: (6, 7, 8, 9, 9),
    21: (6, 7, 8, 9, 9),
    22: (6, 8, 8, 9, 9),
    23: (6, 8, 8, 9, 9),
    24: (6, 7, 8, 9, 9),
    25: (6, 7, 8, 8, 9),
    26: (6, 7, 8, 8, 9),
    27: (5, 7, 7, 8, 8),
    28: (5, 7, 8, 8, 8),
    29: (5, 6, 7, 8, 8),
    30: (5, 6, 6, 8, 8),
    31: (4, 6, 6, 8, 8),
    32: (4, 6, 6, 7, 8),
    33: (4, 5, 6, 7, 8),
    34: (3, 5, 5, 6, 7),
    35: (3, 5, 5, 6, 7),
    36: (3, 4, 4, 5, 6),
}


def stamina_forecast_level(age_years: int, training_pct: float) -> int | None:
    """Nivel esperado de Resistencia para esta edad y este % real de
    entrenamiento de resistencia — `None` si la edad está fuera de la
    tabla (17-36), en vez de extrapolar sin evidencia."""
    row = STAMINA_FORECAST_TABLE.get(age_years)
    if row is None:
        return None
    clamped_pct = max(5.0, min(30.0, training_pct))
    bucket_idx = 0
    for i, lower_bound in enumerate(STAMINA_TRAINING_PCT_BUCKETS):
        if clamped_pct >= lower_bound:
            bucket_idx = i
    return row[bucket_idx]


def age_after_weeks(age_years: int, age_days: int, weeks: int) -> tuple[int, int]:
    """Edad proyectada `weeks` semanas adelante, en la misma convención de
    112 días/año que ya usa toda la app para la edad fraccionaria
    (`age_years + age_days / 112`, ver pricing_engine.age_factor)."""
    total_days = age_years * 112 + age_days + weeks * 7
    return total_days // 112, total_days % 112
