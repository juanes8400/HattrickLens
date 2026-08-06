"""Valoración de jugadores y retorno del entrenamiento — HL-101, HL-036, HL-107.

Hattrick Control registra el precio al que compraste y al que vendiste, pero
nunca te dice cuánto vale un jugador *hoy* ni cuándo conviene venderlo. Este
motor cierra ese hueco.

MODELO DE PRECIO
----------------
Precio = f(skill dominante, edad, TSI, forma, especialidad). En Hattrick el
valor de mercado crece de forma fuertemente convexa con la skill principal y
decae con la edad a partir de cierto punto. Se modela como:

    precio = base × valor_skill(dominante) × factor_edad(edad) × (1 + primas)

Los coeficientes son ⚠️ SUPUESTOS: no hemos observado suficientes ventas.
El motor está construido para recalibrarse contra `transfersteam` en cuanto
haya muestras propias — ese es su diseño, no un parche.

VENTANA ÓPTIMA DE VENTA
-----------------------
Un jugador gana valor entrenando y lo pierde envejeciendo. El máximo está donde
la ganancia por entrenamiento deja de compensar la caída por edad. Se calcula
proyectando ambas curvas semana a semana.
"""
from dataclasses import dataclass
from typing import Any

# Valor relativo de cada nivel de skill (convexo). Índice = nivel.
# ⚠️ SUPUESTO: forma tomada del consenso de la comunidad, magnitudes sin verificar.
SKILL_VALUE = [
    0, 1, 2, 4, 7, 12, 20, 33, 54, 88, 143, 232, 376, 609, 986, 1596,
    2583, 4180, 6764, 10945, 17710,
]

# Multiplicador por edad. El valor cae a partir de los 27-28.
AGE_FACTOR = {
    17: 1.45, 18: 1.42, 19: 1.38, 20: 1.34, 21: 1.30, 22: 1.24, 23: 1.16,
    24: 1.08, 25: 1.00, 26: 0.92, 27: 0.82, 28: 0.70, 29: 0.58, 30: 0.46,
    31: 0.35, 32: 0.26, 33: 0.19, 34: 0.13, 35: 0.09,
}
BASE_PRICE = 850.0          # moneda local por unidad de valor de skill
FORM_PREMIUM = 0.02         # por nivel de forma sobre 4
SPECIALTY_PREMIUM = 0.08    # tener especialidad
CALIBRATION = "assumed"


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
    return max(
        AGE_FACTOR[_LAST_TABLE_YEAR] * _DECAY_RATIO ** (years - _LAST_TABLE_YEAR), _FLOOR
    )


def age_factor(years: int, days: int = 0) -> float:
    """Multiplicador de valor por edad — HL-15x: público porque
    career_stage_engine también lo usa (edad óptima vs. declive), no solo
    `value_player` aquí abajo."""
    lo = _year_factor(years)
    hi = _year_factor(years + 1)
    return lo + (hi - lo) * (days / 112.0)


@dataclass
class Valuation:
    expected_price: int
    low: int
    high: int
    dominant_skill: str
    dominant_level: int
    age_factor: float
    confidence: str = CALIBRATION
    comparables: int = 0


def value_player(
    skills: dict[str, int],
    age_years: int,
    age_days: int = 0,
    form: int = 5,
    specialty: int = 0,
    currency_rate: float = 1.0,
) -> Valuation:
    """Precio esperado con banda. HL-101."""
    dominant = max(skills, key=lambda s: skills.get(s, 0)) if skills else "playmaking"
    level = min(max(skills.get(dominant, 0), 0), len(SKILL_VALUE) - 1)

    base = BASE_PRICE * SKILL_VALUE[level]
    af = age_factor(age_years, age_days)
    premium = 1.0 + FORM_PREMIUM * max(form - 4, 0) + (SPECIALTY_PREMIUM if specialty else 0.0)

    price = base * af * premium / max(currency_rate, 1.0)
    # Banda ancha por diseño: los coeficientes no están verificados
    return Valuation(
        expected_price=int(round(price)),
        low=int(round(price * 0.65)),
        high=int(round(price * 1.45)),
        dominant_skill=dominant,
        dominant_level=level,
        age_factor=round(af, 3),
    )


@dataclass
class SellWindow:
    best_week: int
    best_age_years: int
    best_age_days: int
    peak_price: int
    price_now: int
    gain_if_waiting: int
    verdict: str


def optimal_sell_window(
    skills: dict[str, int],
    age_years: int,
    age_days: int,
    weeks_to_next_pop: float | None,
    trained_skill: str | None,
    horizon_weeks: int = 78,
    form: int = 5,
    specialty: int = 0,
    currency_rate: float = 1.0,
) -> SellWindow:
    """Cuándo vender para maximizar el precio. HL-101.

    Proyecta semana a semana: la edad resta valor, cada subida de la skill
    entrenada lo suma. El máximo de esa curva es la ventana de venta.
    """
    now = value_player(skills, age_years, age_days, form, specialty, currency_rate)
    best = (0, now.expected_price, age_years, age_days)

    proj = dict(skills)
    total_days = age_years * 112 + age_days
    next_pop = weeks_to_next_pop

    for week in range(1, horizon_weeks + 1):
        total_days += 7
        y, d = divmod(total_days, 112)
        if trained_skill and next_pop is not None and week >= next_pop:
            proj[trained_skill] = proj.get(trained_skill, 0) + 1
            next_pop += weeks_to_next_pop or 0
        price = value_player(proj, y, d, form, specialty, currency_rate).expected_price
        if price > best[1]:
            best = (week, price, y, d)

    gain = best[1] - now.expected_price
    # HL-101: proyección, no certeza — el precio real depende de mercado y
    # forma en ese momento, que este modelo no puede conocer hoy.
    if best[0] == 0:
        verdict = "vende ahora: el modelo no proyecta que su valor vaya a subir"
    elif gain < now.expected_price * 0.05:
        verdict = "da igual cuándo: la diferencia proyectada es marginal"
    else:
        pct = gain / max(now.expected_price, 1)
        verdict = f"esperar {best[0]} semanas podría subir su valor ~{pct:.0%} (estimado)"

    return SellWindow(best[0], best[2], best[3], best[1], now.expected_price, gain, verdict)


@dataclass
class TrainingROI:
    skill: str
    from_level: int
    to_level: int
    value_gain: int
    weeks: float
    value_per_week: int


def training_roi(
    skills: dict[str, int],
    trained_skill: str,
    age_years: int,
    age_days: int,
    weeks_per_level: float,
    levels: int = 3,
    currency_rate: float = 1.0,
) -> list[TrainingROI]:
    """Cuánto vale cada nivel que entrenas. HL-036.

    Hattrick Control mide esto a posteriori sobre ventas ya hechas; nosotros lo
    proyectamos antes de decidir.
    """
    out: list[TrainingROI] = []
    proj = dict(skills)
    total_days = age_years * 112 + age_days
    for _ in range(levels):
        before = value_player(proj, *divmod(total_days, 112),
                              currency_rate=currency_rate).expected_price
        proj[trained_skill] = proj.get(trained_skill, 0) + 1
        total_days += int(weeks_per_level * 7)
        after = value_player(proj, *divmod(total_days, 112),
                             currency_rate=currency_rate).expected_price
        out.append(
            TrainingROI(
                skill=trained_skill,
                from_level=proj[trained_skill] - 1,
                to_level=proj[trained_skill],
                value_gain=after - before,
                weeks=round(weeks_per_level, 1),
                value_per_week=int((after - before) / max(weeks_per_level, 1)),
            )
        )
    return out


#  SUELDO SEMANAL — HL-141. A diferencia de `value_player` de arriba (precio
# de mercado, coeficientes ⚠️ SUPUESTOS sin verificar), esta es una fórmula
# EXACTA documentada por la comunidad (Manual no Escrito, wiki.hattrick.org,
# coeficientes de bigpapy) — no publicada oficialmente por CHPP, pero
# derivada matemáticamente de sueldos reales observados, no una opinión.
# Solo cubre jugadores de campo: la fórmula de Arquero no está documentada
# en la fuente consultada.
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
        "de comunidad (Manual no Escrito), no oficial de CHPP — contrastada contra sueldos "
        "reales de esta plantilla, con un margen de ~10-50%"
    )


def estimate_salary(skills: dict[str, int], set_pieces: int = 0) -> SalaryEstimate:
    """Sueldo semanal proyectado de un jugador de campo, a partir de sus 5
    habilidades principales. Útil para proyectar el sueldo ANTES de entrenar
    o fichar — para un jugador que ya es tuyo, el sueldo real ya lo reporta
    CHPP directamente y esta estimación no debería reemplazarlo."""
    components = {
        skill: _salary_component(skill, skills.get(skill, 0))
        for skill in SALARY_FIELD_SKILLS
    }
    main_skill = max(components, key=lambda s: components[s])
    secondary_sum = sum(v for k, v in components.items() if k != main_skill) / 2
    salary = (
        (components[main_skill] + secondary_sum)
        * (1 + set_pieces * SET_PIECES_SALARY_BONUS_PER_LEVEL)
        + SALARY_BASE
    )
    return SalaryEstimate(
        weekly_salary=int(round(salary)),
        main_skill=main_skill,
        components={k: int(round(v)) for k, v in components.items()},
    )


@dataclass
class RegretIndex:
    player: str
    sold_for: int
    worth_today: int
    delta: int
    verdict: str


def regret_index(sales: list[dict[str, Any]], currency_rate: float = 1.0) -> list[RegretIndex]:
    """Qué fue de los que vendiste. HL-107.

    Hattrick Control lista a los ex jugadores como curiosidad. Convertirlo en un
    contraste entre lo que cobraste y lo que valen hoy cierra el bucle de
    aprendizaje sobre tus propias decisiones de venta.
    """
    out: list[RegretIndex] = []
    for s in sales:
        today = value_player(
            s["skills"], s["age_years"], s.get("age_days", 0),
            s.get("form", 5), s.get("specialty", 0), currency_rate,
        ).expected_price
        delta = today - s["sold_for"]
        if delta > s["sold_for"] * 0.25:
            verdict = "vendiste barato"
        elif delta < -s["sold_for"] * 0.25:
            verdict = "buena venta: hoy vale menos"
        else:
            verdict = "precio justo"
        out.append(RegretIndex(s["name"], s["sold_for"], today, delta, verdict))
    return sorted(out, key=lambda r: -r.delta)
