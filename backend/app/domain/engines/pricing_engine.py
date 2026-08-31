"""Sueldo semanal estimado y factor de edad — HL-141.

2026-08-11, pedido explícito del usuario: se retiró por completo el modelo
de valor de mercado (`value_player`, banda de precio, ventana óptima de
venta, ROI de entrenamiento en dinero, índice de arrepentimiento) — sus
coeficientes eran un supuesto propio sin ninguna venta real observada que
lo respalde, y no debe quedar ningún cálculo derivado de él en la
plataforma. Lo único que sobrevive de este archivo es lo que SÍ tiene una
base verificable:

- `age_factor`: curva de edad reutilizada por `career_stage_engine` para
  clasificar el momento de la carrera de un jugador (no un precio).
- `estimate_salary`: fórmula EXACTA documentada por la comunidad (Manual
  no Escrito), contrastable contra el sueldo real que ya reporta CHPP.
"""

from dataclasses import dataclass

# Multiplicador por edad. El valor cae a partir de los 27-28.
AGE_FACTOR = {
    17: 1.45,
    18: 1.42,
    19: 1.38,
    20: 1.34,
    21: 1.30,
    22: 1.24,
    23: 1.16,
    24: 1.08,
    25: 1.00,
    26: 0.92,
    27: 0.82,
    28: 0.70,
    29: 0.58,
    30: 0.46,
    31: 0.35,
    32: 0.26,
    33: 0.19,
    34: 0.13,
    35: 0.09,
}

_LAST_TABLE_YEAR = max(AGE_FACTOR)
_FIRST_TABLE_YEAR = min(AGE_FACTOR)
# Ritmo de caída del último tramo de la tabla (34->35), extendido más allá de
# ella en vez de un valor fijo de repuesto: un fallback constante recalculado
# cada año producía un diente de sierra (el valor subía en cada cumpleaños).
_DECAY_RATIO = AGE_FACTOR[_LAST_TABLE_YEAR] / AGE_FACTOR[_LAST_TABLE_YEAR - 1]
_FLOOR = 0.03


def _year_factor(years: int) -> float:
    if years in AGE_FACTOR:
        return AGE_FACTOR[years]
    if years < _FIRST_TABLE_YEAR:
        return AGE_FACTOR[_FIRST_TABLE_YEAR]
    return max(AGE_FACTOR[_LAST_TABLE_YEAR] * _DECAY_RATIO ** (years - _LAST_TABLE_YEAR), _FLOOR)


def age_factor(years: int, days: int = 0) -> float:
    """Multiplicador por edad — usado por `career_stage_engine` para
    clasificar edad óptima vs. declive."""
    lo = _year_factor(years)
    hi = _year_factor(years + 1)
    return lo + (hi - lo) * (days / 112.0)


#  SUELDO SEMANAL — HL-141. Fórmula EXACTA documentada por la comunidad
# (Manual no Escrito, wiki.hattrick.org, coeficientes de bigpapy) — no
# publicada oficialmente por CHPP, pero derivada matemáticamente de sueldos
# reales observados, no una opinión. Solo cubre jugadores de campo: la
# fórmula de Arquero no está documentada en la fuente consultada.
SALARY_COEFFICIENTS: dict[str, tuple[float, float, float]] = {
    # habilidad: (A, B, C)
    "defending": (0.0007145560, 6.4607813171, 0.7921),
    "playmaking": (0.0009418058, 6.4407950328, 0.7832),
    "passing": (0.0004476257, 6.5136791026, 0.7707),
    "winger": (0.0004437607, 6.4641257225, 0.7789),
    "scoring": (0.0009136982, 6.4090063683, 0.7984),
}
SALARY_FIELD_SKILLS = tuple(SALARY_COEFFICIENTS)
SET_PIECES_SALARY_BONUS_PER_LEVEL = 0.0025
SALARY_BASE = 250.0


def _salary_component(skill: str, level: int) -> float:
    a, b, c = SALARY_COEFFICIENTS[skill]
    componente: float = a * float(max(level - 1, 0)) ** b
    if componente > 20000:
        componente = (componente - 20000) * c + 20000
    return componente


@dataclass
class SalaryEstimate:
    weekly_salary: int
    main_skill: str
    components: dict[str, int]
    confidence: str = (
        "de comunidad (Manual no Escrito), no oficial de Hattrick, contrastada contra sueldos "
        "reales de esta plantilla, con un margen de ~10-50%"
    )


def estimate_salary(skills: dict[str, int], set_pieces: int = 0) -> SalaryEstimate:
    """Sueldo semanal proyectado de un jugador de campo, a partir de sus 5
    habilidades principales. Útil para proyectar el sueldo ANTES de entrenar
    o fichar — para un jugador que ya es tuyo, el sueldo real ya lo reporta
    CHPP directamente y esta estimación no debería reemplazarlo."""
    components = {
        skill: _salary_component(skill, skills.get(skill, 0)) for skill in SALARY_FIELD_SKILLS
    }
    main_skill = max(components, key=lambda s: components[s])
    secondary_sum = sum(v for k, v in components.items() if k != main_skill) / 2
    salary = (components[main_skill] + secondary_sum) * (
        1 + set_pieces * SET_PIECES_SALARY_BONUS_PER_LEVEL
    ) + SALARY_BASE
    return SalaryEstimate(
        weekly_salary=int(round(salary)),
        main_skill=main_skill,
        components={k: int(round(v)) for k, v in components.items()},
    )
