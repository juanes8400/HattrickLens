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

from app.domain.engines.youth_training_plan import factor_secundario
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
#: Cuantas habilidades pueden quedar SIN revelar y aun asi permitir condenar a
#: un canterano. Cero, y es logica, no gusto: un techo sin revelar puede ser un
#: 8, y un solo 8 convierte a un «fontanero» en un crack. Mientras quede uno,
#: no hay nada que condenar.
#:
#: 2026-08-30, corregido tras un reporte del usuario. Antes bastaba con TRES
#: habilidades reveladas --de siete-- para recomendar el despido, y eso hacia
#: dos cosas al reves:
#:
#:   * A Felipe Castrillon, con 3 reveladas y CUATRO sin revelar --mas
#:     desconocidas que conocidas-- la aplicacion le decia «despidelo».
#:   * Y como revelar es lo que pasa cuando entrenas a alguien, cuanto MAS
#:     sabias de un chico mas cerca estaba de que te dijeran que lo echaras.
#:     Premiaba la ignorancia.
#:
#: Los dos condenados eran el primero y el tercero mas jovenes de la academia,
#: que son justo los que mas vida de entrenamiento tienen por delante.
MAX_SIN_REVELAR_PARA_CONDENAR = 0


def categoria_de(best_max: int | None) -> Category:
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


#: El nombre privado se conserva: hay codigo y pruebas que lo importan.
_categorise = categoria_de

#: Las categorias que CONDENAN a un canterano. Solo estas necesitan que no
#: quede nada por revelar.
CATEGORIAS_QUE_CONDENAN = (Category.PLUMBER, Category.SELLABLE)


def veredicto_provisional(category: Category, revealed: int, total: int) -> bool:
    """Si el veredicto todavia puede cambiar al revelarse mas habilidades.

    Hay una ASIMETRIA que el codigo no recogia y que lo decide todo: revelar
    una habilidad solo puede SUBIR el mejor techo de un canterano, nunca
    bajarlo. De ahi:

      * Un veredicto BUENO --crack, promesa, aceptable-- ya no cambia: si
        tiene un techo de 8 revelado, es un crack, y ningun descubrimiento
        posterior se lo va a quitar. No es provisional.
      * Uno MALO si lo es mientras quede algo por revelar. Un solo 8 escondido
        convierte a un «fontanero» en un crack, y despedir NO SE DESHACE.

    Sin ninguna revelacion no hay veredicto en absoluto, y eso es provisional
    siempre.
    """
    if revealed == 0:
        return True
    if category in CATEGORIAS_QUE_CONDENAN:
        return (total - revealed) > MAX_SIN_REVELAR_PARA_CONDENAR
    return False


def aporte_de_cada_uno(
    buckets_por_canterano: dict[str, list[str]],
    pesos: dict[str, float],
) -> dict[str, float]:
    """Cuanto aporta cada canterano a los puntajes de las siete habilidades.

    Es la suma del peso de su peldano en CADA habilidad. Un chico que sale
    «desconocido» en las siete aporta siete veces ⅓; uno con un excelente
    aporta 81 solo por esa. Es exactamente lo que el ranking de entrenamiento
    esta sumando, visto por canterano en vez de por habilidad.
    """
    return {
        nombre: sum(pesos.get(b, 0.0) for b in cubos)
        for nombre, cubos in buckets_por_canterano.items()
    }


def quien_sobra(
    aportes: dict[str, float],
    edad_en_dias: dict[str, int],
) -> str | None:
    """El canterano que menos aporta. Empata el MAS VIEJO.

    2026-08-30, regla del usuario, y sustituye a un veredicto por canterano
    que estaba mal planteado: despedir libera UNA plaza, asi que la pregunta
    no es «¿este chico es malo?» --que no se puede contestar mientras le
    queden techos sin revelar-- sino «¿quien es el ultimo de la fila?». Eso si
    tiene respuesta siempre, y solo se le sugiere a uno.

    El desempate por edad es el mismo argumento: entre dos que aportan igual,
    al mas viejo le queda menos tiempo para dejar de ser el ultimo.
    """
    if not aportes:
        return None
    return min(aportes, key=lambda n: (aportes[n], -edad_en_dias.get(n, 0), n))


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
    category = categoria_de(best_max)
    left = days_until_deadline(age_years, age_days)
    revealed = sum(1 for s in skills.values() if s.maximum is not None)

    # Contra las SIETE de `YOUTH_SKILLS`, no contra `len(skills)`: un
    # diccionario al que le falten habilidades no significa que esten
    # reveladas, significa que no las han pasado. Confiar en su tamaño hacia
    # que tres habilidades sueltas parecieran una lectura completa y condenaba
    # al canterano.
    sin_revelar = len(YOUTH_SKILLS) - revealed

    if left <= 21:
        advice = f"URGENTE: quedan {left} días para promocionarlo o lo pierdes"
    elif revealed == 0:
        advice = "el ojeador aún no ha revelado nada suyo: no hay con qué juzgarlo"
    elif sin_revelar > MAX_SIN_REVELAR_PARA_CONDENAR:
        # Despedir NO SE DESHACE, y un techo sin revelar puede ser un 8: uno
        # solo convierte a un «fontanero» en un crack. Mientras quede alguno,
        # lo unico honesto es decir cuantos faltan.
        advice = (
            f"sigue entrenándolo: aún le faltan {sin_revelar} "
            + ("habilidad" if sin_revelar == 1 else "habilidades")
            + " por revelar"
        )
    elif category in (Category.PLUMBER, Category.SELLABLE):
        # Con las siete reveladas ya no hay sorpresa posible, asi que aqui si
        # se puede decir. Pero se dice el HECHO y se deja la decision al
        # usuario: la aplicacion no manda ejecutar algo irreversible.
        advice = f"ya sabes todo de él y su mejor techo es {best_max}: no va a dar más"
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
    training_pair: tuple[str, str] | None = None,
) -> float:
    """Aprovechamiento de la plaza de entrenamiento juvenil. HL-115.

    Pesos de entrenamiento: principal 1,0; secundario distinto 2/3; y
    secundario repetido 1/3 (el 2/3 normal castigado a la mitad). Los otros
    factores son independientes: posición principal 1,0 / secundaria 0,5;
    partido oficial 1,0 / amistoso 0,5.
    """
    if is_primary_training:
        w_training = 1.0
    elif training_pair is None:
        raise ValueError("un entrenamiento secundario necesita los códigos principal y secundario")
    else:
        w_training = factor_secundario(*training_pair)
    w_match = 1.0 if is_official_match else 0.5
    minutes = min(minutes_main_position, 90) * 1.0 + min(minutes_secondary_position, 90) * 0.5
    return round(min(minutes / 90.0, 1.0) * w_training * w_match, 4)
