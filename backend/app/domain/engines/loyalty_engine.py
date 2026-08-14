"""Motor de Fidelidad basado únicamente en la antigüedad en el club.

La curva se ajusta exactamente a los niveles conocidos de la plantilla:

    F(d) = min(20, 1 + floor(19 * sqrt(d / 336)))

``d`` son días calendario desde la compra. 336 días equivalen a tres
temporadas de Hattrick (3 × 16 semanas × 7 días). No se usan pops,
promedios observados ni calibración por jugador.
"""
from math import ceil, floor, sqrt
from typing import Any


LOYALTY_MAX_LEVEL = 20
LOYALTY_FULL_DAYS = 336
LOYALTY_STEPS = LOYALTY_MAX_LEVEL - 1


def loyalty_level(days_since_purchase: int | float | None) -> int | None:
    """Nivel entero de Fidelidad para la antigüedad indicada."""
    if days_since_purchase is None:
        return None
    days = max(float(days_since_purchase), 0.0)
    return min(
        LOYALTY_MAX_LEVEL,
        1 + floor(LOYALTY_STEPS * sqrt(days / LOYALTY_FULL_DAYS)),
    )


def loyalty_decimal(days_since_purchase: int | float | None) -> float | None:
    """Valor continuo de la misma curva, útil para mostrar el progreso.

    No interpola entre observaciones: es la expresión anterior antes de
    aplicar ``floor``. El nivel mostrado sigue siendo su parte entera.
    """
    if days_since_purchase is None:
        return None
    days = max(float(days_since_purchase), 0.0)
    return round(
        min(
            float(LOYALTY_MAX_LEVEL),
            1.0 + LOYALTY_STEPS * sqrt(days / LOYALTY_FULL_DAYS),
        ),
        2,
    )


def days_for_level(level: int) -> int:
    """Primer día calendario en el que la fórmula alcanza ``level``."""
    normalized = min(LOYALTY_MAX_LEVEL, max(1, int(level)))
    return ceil(
        LOYALTY_FULL_DAYS * ((normalized - 1) / LOYALTY_STEPS) ** 2
    )


def model_info() -> dict[str, Any]:
    return {
        "formula": "min(20, 1 + floor(19 × √(días desde compra / 336)))",
        "maxLevel": LOYALTY_MAX_LEVEL,
        "fullDays": LOYALTY_FULL_DAYS,
        "seasons": 3,
        "thresholds": [
            {"level": level, "day": days_for_level(level)}
            for level in range(1, LOYALTY_MAX_LEVEL + 1)
        ],
        "reference": {
            "implementation": "Curva de Fidelidad por antigüedad en el club",
            "status": "structural",
            "source_files": [],
            "recovered": (
                "La fórmula reproduce sin errores los niveles conocidos de la "
                "plantilla usando únicamente días calendario desde la compra."
            ),
            "pending": (
                "No requiere calibración por pops ni promedios de transiciones."
            ),
        },
    }
