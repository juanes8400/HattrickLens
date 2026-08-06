"""Academia juvenil — HL-110 a HL-115.

Hattrick Control obliga a teclear a mano las skills de cada juvenil y a
clasificarlos al ojo (fontanero, vendible, aceptable, promesa, crack). Hoy
`youthplayerlist` entrega skill actual y máxima de los entrenados, así que todo
ese trabajo manual sobra.

Lo que HC no hace y aquí sí:

* **Potencial estimado** combinando skills reveladas, techos conocidos y la
  información parcial de los informes del ojeador.
* **Fecha límite de promoción** como alerta, no como pestaña escondida.
* **Rentabilidad de la academia**: HC muestra la inversión acumulada y los
  ingresos por categoría en dos tablas que nunca cruza.
"""
from dataclasses import dataclass
from enum import StrEnum

# Un juvenil puede permanecer en la academia hasta los 19 años
MAX_YOUTH_AGE = 19
YOUTH_SKILLS = ("keeper", "defending", "playmaking", "winger", "passing", "scoring", "set_pieces")


class Category(StrEnum):
    """Clasificación que en HC es manual y aquí se calcula."""

    PLUMBER = "fontanero"      # no vale para nada
    SELLABLE = "vendible"      # se vende sin pena
    ACCEPTABLE = "aceptable"   # puede servir de suplente
    PROSPECT = "promesa"       # merece plaza de entrenamiento
    STAR = "crack"             # proyecto de titular


@dataclass
class YouthSkill:
    current: int
    maximum: int | None      # None = todavía sin revelar
    is_max_reached: bool = False

    @property
    def headroom(self) -> int:
        """Cuánto le queda por crecer. Si no se conoce el techo, se estima."""
        if self.maximum is None:
            return max(0, 8 - self.current)     # supuesto conservador
        return max(0, self.maximum - self.current)


@dataclass
class YouthEvaluation:
    name: str
    age_years: int
    age_days: int
    potential_score: float
    category: Category
    best_skill: str
    best_skill_max: int | None
    days_until_deadline: int
    promote_advice: str
    revealed_skills: int


def _potential(skills: dict[str, YouthSkill]) -> tuple[float, str, int | None]:
    """Puntuación de potencial: pesa el techo conocido más que lo ya alcanzado."""
    best_key, best_val = "", -1.0
    total = 0.0
    for key, s in skills.items():
        techo = s.maximum if s.maximum is not None else s.current + s.headroom
        # El techo es lo que importa; lo alcanzado indica cuánto falta entrenar
        valor = techo * 1.0 + s.current * 0.3
        total += valor
        if techo > best_val:
            best_key, best_val = key, float(techo)
    return round(total, 2), best_key, (int(best_val) if best_val >= 0 else None)


def _categorise(potential: float, best_max: int | None) -> Category:
    techo = best_max or 0
    if techo >= 12 and potential >= 30:
        return Category.STAR
    if techo >= 9 and potential >= 22:
        return Category.PROSPECT
    if techo >= 7:
        return Category.ACCEPTABLE
    if techo >= 5:
        return Category.SELLABLE
    return Category.PLUMBER


def days_until_deadline(age_years: int, age_days: int) -> int:
    """Días que quedan para promocionar antes de perder al juvenil. HL-112."""
    total = age_years * 112 + age_days
    limit = MAX_YOUTH_AGE * 112
    return max(limit - total, 0)


def evaluate(
    name: str,
    age_years: int,
    age_days: int,
    skills: dict[str, YouthSkill],
) -> YouthEvaluation:
    """Evaluación completa de un juvenil. HL-111."""
    potential, best_key, best_max = _potential(skills)
    category = _categorise(potential, best_max)
    left = days_until_deadline(age_years, age_days)
    revealed = sum(1 for s in skills.values() if s.maximum is not None)

    if left <= 21:
        advice = f"URGENTE: quedan {left} días para promocionarlo o lo pierdes"
    elif category in (Category.PLUMBER, Category.SELLABLE):
        advice = "no merece plaza de entrenamiento: despídelo y libera hueco"
    elif revealed < 3:
        advice = "sigue entrenándolo: aún no conoces su techo real"
    elif age_years >= 17:
        advice = "listo para promocionar: ya aprovechará mejor el entrenamiento senior"
    else:
        advice = "mantenlo en la academia y sigue revelando skills"

    return YouthEvaluation(
        name=name,
        age_years=age_years,
        age_days=age_days,
        potential_score=potential,
        category=category,
        best_skill=best_key,
        best_skill_max=best_max,
        days_until_deadline=left,
        promote_advice=advice,
        revealed_skills=revealed,
    )


def rank(evaluations: list[YouthEvaluation]) -> list[YouthEvaluation]:
    """Ranking interno de la academia. HL-111."""
    return sorted(evaluations, key=lambda e: -e.potential_score)


@dataclass
class AcademyROI:
    invested: int
    earned: int
    net: int
    seasons: int
    weekly_cost: int
    break_even_sales: int
    verdict: str


def academy_roi(
    weekly_investment: int,
    weeks_invested: int,
    sales_income: int,
    average_sale_price: int = 0,
) -> AcademyROI:
    """¿Ha valido la pena la cantera? HL-114.

    Caso real que motivó esta función: 11.240.000 invertidos desde la temporada
    47 y la tabla de ingresos vacía. HC muestra ambos números sin cruzarlos.
    """
    invested = weekly_investment * weeks_invested
    net = sales_income - invested
    seasons = weeks_invested // 16
    faltan = (
        max(0, -net) // average_sale_price + (1 if -net % max(average_sale_price, 1) else 0)
        if average_sale_price > 0 and net < 0
        else 0
    )

    if invested == 0:
        verdict = "academia cerrada: sin inversión ni retorno"
    elif net > 0:
        verdict = f"rentable: has recuperado la inversión y ganado {net:,}"
    elif average_sale_price > 0:
        verdict = f"en pérdidas: harían falta {faltan} venta(s) más para equilibrar"
    else:
        verdict = "en pérdidas: aún no has vendido ningún canterano"

    return AcademyROI(invested, sales_income, net, seasons, weekly_investment, faltan, verdict)


def training_exposure(
    minutes_main_position: int,
    minutes_secondary_position: int,
    is_official_match: bool,
    is_primary_training: bool = True,
) -> float:
    """Aprovechamiento de la plaza de entrenamiento juvenil. HL-115.

    Pesos leídos directamente del panel "Valoración del entrenamiento" de
    Hattrick Control (ver docs/16): principal 1,0 / secundario 0,8;
    posición principal 1,0 / secundaria 0,5; oficial 1,0 / amistoso 0,5.
    """
    w_training = 1.0 if is_primary_training else 0.8
    w_match = 1.0 if is_official_match else 0.5
    minutes = min(minutes_main_position, 90) * 1.0 + min(minutes_secondary_position, 90) * 0.5
    return round(min(minutes / 90.0, 1.0) * w_training * w_match, 4)
