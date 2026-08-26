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

from app.domain.value_objects.formatting import thousands

# Un juvenil puede permanecer en la academia hasta los 19 años
MAX_YOUTH_AGE = 19
YOUTH_SKILLS = ("keeper", "defending", "playmaking", "winger", "passing", "scoring", "set_pieces")


class Category(StrEnum):
    """Clasificación que en HC es manual y aquí se calcula."""

    UNRATED = "sin ojear"  # el ojeador no ha revelado ni un techo
    PLUMBER = "fontanero"  # no vale para nada
    SELLABLE = "vendible"  # se vende sin pena
    ACCEPTABLE = "aceptable"  # puede servir de suplente
    PROSPECT = "promesa"  # merece plaza de entrenamiento
    STAR = "crack"  # proyecto de titular


@dataclass
class YouthSkill:
    current: int
    maximum: int | None  # None = todavía sin revelar
    is_max_reached: bool = False

    @property
    def headroom(self) -> int:
        """Cuánto le queda por crecer. Si no se conoce el techo, se estima."""
        if self.maximum is None:
            return max(0, 8 - self.current)  # supuesto conservador
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


def _potential(skills: dict[str, YouthSkill]) -> tuple[float, str, int | None, int]:
    """Puntuación de potencial y mejor habilidad.

    Devuelve `(total, mejor_habilidad, techo_revelado, techo_asumido)`.

    2026-08-15, corregido al ver datos reales por primera vez: `best_skill` se
    elegía entre TODAS las habilidades usando el techo asumido de `headroom`
    (8 cuando no hay revelación). Con un juvenil recién llegado eso significa
    que las siete empatan en 8, gana la primera del diccionario, y la pantalla
    mostraba "keeper (techo 8)" como si el ojeador lo hubiera dicho. Es el
    mismo error que este módulo promete no cometer, en espejo: presentar una
    suposición como evidencia.

    Ahora `mejor_habilidad`/`techo_revelado` sólo salen de habilidades con
    techo REVELADO — vacío y `None` mientras no haya ninguna. El techo asumido
    se devuelve aparte para que la categoría siga siendo provisional en vez de
    desplomarse a "fontanero" por ignorancia.
    """
    best_key, best_revealed = "", -1
    best_assumed = 0
    total = 0.0
    for key, s in skills.items():
        assumed = s.maximum if s.maximum is not None else s.current + s.headroom
        # El techo es lo que importa; lo alcanzado indica cuánto falta entrenar
        total += assumed * 1.0 + s.current * 0.3
        best_assumed = max(best_assumed, assumed)
        if s.maximum is not None and s.maximum > best_revealed:
            best_key, best_revealed = key, s.maximum
    return (
        round(total, 2),
        best_key,
        best_revealed if best_revealed >= 0 else None,
        best_assumed,
    )


#: Los cortes de categoria, en la escala JUVENIL. 2026-08-23, dictados por el
#: usuario: son los mismos que ya mandan en el resto del modulo --excelente 8,
#: bueno 7, aceptable 6-- para que una sola escala valga en toda la academia.
#:
#: Antes estaban en 12 / 9 / 7 / 5, que es escala de primer equipo. Un techo
#: juvenil no llega a 12, asi que "crack" y "promesa" eran inalcanzables y los
#: dieciocho canteranos salian "aceptable": la etiqueta no distinguia a nadie.
CORTE_CRACK = 8
CORTE_PROMESA = 7
CORTE_ACEPTABLE = 6
CORTE_VENDIBLE = 5

#: Cuantos techos hacen falta para que un veredicto deje de ser provisional.
#: Vivia en la capa de consultas, pero es una regla del dominio: el motor la
#: necesita para no recomendar un despido sobre una sola lectura.
MIN_REVEALED_FOR_A_VERDICT = 3


def _categorise(best_max: int | None) -> Category:
    """La categoria sale del techo REVELADO, nunca del asumido.

    Con el techo supuesto --8 mientras el ojeador calla-- todo canterano sin
    ojear daria "crack", que es afirmar justo lo que no se sabe. Sin ninguna
    revelacion no hay veredicto, y eso tiene nombre propio.
    """
    if best_max is None:
        return Category.UNRATED
    if best_max >= CORTE_CRACK:
        return Category.STAR
    if best_max >= CORTE_PROMESA:
        return Category.PROSPECT
    if best_max >= CORTE_ACEPTABLE:
        return Category.ACCEPTABLE
    if best_max >= CORTE_VENDIBLE:
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
    potential, best_key, best_max, _asumido = _potential(skills)
    # Sin revelaciones un juvenil no es un fontanero, pero tampoco un crack:
    # es un desconocido. El techo asumido sigue alimentando `potential_score`
    # --sirve para ordenar-- pero no fabrica una etiqueta.
    category = _categorise(best_max)
    left = days_until_deadline(age_years, age_days)
    revealed = sum(1 for s in skills.values() if s.maximum is not None)

    if left <= 21:
        advice = f"URGENTE: quedan {left} días para promocionarlo o lo pierdes"
    elif revealed == 0:
        advice = "el ojeador aún no ha revelado nada suyo: no hay con qué juzgarlo"
    elif revealed < MIN_REVEALED_FOR_A_VERDICT:
        # Despedir no se deshace. Con una sola lectura no se recomienda: lo
        # unico que se sabe de el puede ser justo su peor habilidad, y el
        # consejo saldria de esa casualidad.
        advice = "sigue entrenándolo: aún no conoces su techo real"
    elif category in (Category.PLUMBER, Category.SELLABLE):
        advice = "no merece plaza de entrenamiento: despídelo y libera hueco"
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
    invested: int,
    weeks_invested: int,
    sales_income: int,
    average_sale_price: int = 0,
    weekly_investment: int = 0,
) -> AcademyROI:
    """¿Ha valido la pena la cantera? HL-114.

    Caso real que motivó esta función: 11.240.000 invertidos desde la temporada
    47 y la tabla de ingresos vacía. HC muestra ambos números sin cruzarlos.

    2026-08-16, corregido a petición del usuario: `invested` llega ya sumado,
    semana a semana. Antes esta función multiplicaba el coste semanal ACTUAL
    por el número de semanas, lo que sólo es correcto si nunca cambiaste la
    inversión juvenil — y en cuanto la subes o la bajas, reescribe el pasado
    con el precio de hoy. `weekly_investment` se conserva sólo para mostrar
    "X por semana" en la ficha; ya no interviene en ningún cálculo.
    """
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
        verdict = f"rentable: has recuperado la inversión y ganado {thousands(net)}"
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
