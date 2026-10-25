"""Cuántas plazas de entrenamiento aprovecha cada formación.

2026-10-25, reporte de un usuario:

    «I would also like to have "Best Training" which would exclude a formation
    that doesn't use all training spots. I'm getting the suggested Best
    Formation of 4-4-2 for my team training Scoring. I consider training to be
    critical in this phase, so will not play 442 no matter the ratings
    difference.»

Y tiene razón en lo de «no matter the ratings difference»: entrenando Anotación
sólo entrenan los delanteros, así que un 4-4-2 deja una de las tres plazas sin
usar y esa semana no vuelve. Ninguna diferencia de valoración compensa un
tercio del entrenamiento tirado.

UNA MEDIA RACIÓN TAMBIÉN ES UNA PLAZA (decisión del usuario, 2026-10-25). Era
la única duda del encargo: entrenando Jugadas, `{inner_midfield: 100,
winger: 50}`, ¿cuenta un extremo que entrena a la mitad? Sí.

Y esa respuesta simplifica el cálculo más de lo que parece, porque los puestos
de Hattrick se reparten por LÍNEAS y los entrenamientos suelen tocar la línea
entera:

  Jugadas   mediocentros + extremos  = toda la línea del medio
  Defensa   centrales + laterales    = toda la línea de atrás
  Anotación delanteros               = toda la línea de arriba

En esos tres, las plazas no dependen de cómo repartas la línea entre dentro y
banda: suman lo mismo. Donde SÍ manda el reparto es en Lateral
--`{winger: 100, wingback: 50}`-- porque coge los extremos de una línea y los
laterales de otra, así que un 4-4-2 con dos laterales y dos extremos aprovecha
cuatro y uno con tres centrales aprovecha tres.

DE DÓNDE SALE LA TABLA. De `youth_training_plan`, que ya la tenía: la dictó el
usuario el 2026-08-23 y sus dos casos de media ración están comprobados contra
la wiki de Hattrick. No se copia aquí --una segunda copia es la forma segura de
que un día discrepen-- se importa.
"""

from __future__ import annotations

from app.domain.engines.youth_training_plan import ENTRENAMIENTOS
from app.domain.value_objects.formations import (
    LINE_COUNTS,
    resolve_split,
    slots_for,
)


def puestos_que_entrena(entrenamiento: str) -> frozenset[str]:
    """Los puestos a los que llega un entrenamiento, a la ración que sea.

    Un entrenamiento desconocido no llega a ninguno, y eso hace que todas las
    formaciones empaten a cero plazas: la pantalla deja de filtrar en vez de
    quedarse sin formaciones, que es lo que se quiere si algún día llega un
    código que este módulo no conoce.
    """
    ficha = ENTRENAMIENTOS.get(entrenamiento)
    if ficha is None:
        return frozenset()
    return frozenset(puesto for puesto, racion in ficha.ritmos.items() if racion > 0)


def plazas(
    entrenamiento: str,
    formacion: str,
    central_defenders: int | None = None,
    inner_midfielders: int | None = None,
) -> int:
    """Cuántas casillas del once reciben este entrenamiento.

    Se cuentan CASILLAS, no jugadores distintos: tres delanteros son tres
    plazas de Anotación aunque sea el mismo tipo de puesto.
    """
    if formacion not in LINE_COUNTS:
        return 0
    tocados = puestos_que_entrena(entrenamiento)
    if not tocados:
        return 0
    casillas = slots_for(formacion, central_defenders, inner_midfielders)
    return sum(1 for casilla in casillas if casilla in tocados)


def plazas_por_formacion(entrenamiento: str) -> dict[str, int]:
    """Las diez formaciones con sus plazas, CON SU REPARTO POR DEFECTO.

    El reparto por defecto y no el mejor posible, por la misma razón que
    `best_formation` compara con él: si cada formación se midiera con el
    reparto que más le conviene, el ranking compararía onces distintos de los
    que después se enseñan.

    Para Lateral eso significa que la cifra es la del reparto base; cambiando
    el reparto a mano se puede ganar una plaza más. Es una limitación conocida
    y dicha, no un descuido.
    """
    return {nombre: plazas(entrenamiento, nombre) for nombre in LINE_COUNTS}


def formaciones_que_lo_aprovechan(entrenamiento: str) -> list[str]:
    """Las que llegan al MÁXIMO de plazas que este entrenamiento puede tener.

    Es la lista que pidió el usuario: «exclude a formation that doesn't use all
    training spots». El máximo se saca de las propias formaciones y no de una
    constante, porque depende del entrenamiento: tres en Anotación, cinco en
    Jugadas, once en Balón parado.

    SI NINGUNA DESTACA, VUELVEN TODAS. Pasa con Balón parado y con el
    individual, que llegan a los once puestos: ahí todas empatan y filtrar no
    quitaría ninguna. Devolver la lista entera es lo correcto --no hay nada que
    excluir-- y además evita que la pantalla se quede sin opciones.
    """
    cuentas = plazas_por_formacion(entrenamiento)
    if not cuentas:
        return sorted(LINE_COUNTS)
    tope = max(cuentas.values())
    if tope <= 0:
        return sorted(LINE_COUNTS)
    return [nombre for nombre, cuantas in cuentas.items() if cuantas == tope]


def desperdicio(
    entrenamiento: str,
    formacion: str,
    central_defenders: int | None = None,
    inner_midfielders: int | None = None,
) -> int:
    """Cuántas plazas deja sin usar esta formación frente a la mejor.

    Es lo que convierte la lista en una explicación: «4-4-2 desperdicia 1» dice
    por qué no sale recomendada, y «desperdicia 0» dice que no hay nada que
    objetarle.
    """
    cuentas = plazas_por_formacion(entrenamiento)
    if not cuentas:
        return 0
    tope = max(cuentas.values())
    return max(0, tope - plazas(entrenamiento, formacion, central_defenders, inner_midfielders))


def reparto_que_mas_aprovecha(entrenamiento: str, formacion: str) -> tuple[int, int] | None:
    """El reparto de esta formación que gana más plazas, si gana alguna.

    Sólo tiene algo que decir en Lateral, que es el único entrenamiento cuyas
    plazas dependen del reparto. Devuelve `None` cuando el reparto por defecto
    ya es el mejor, que es lo normal: así quien lo llame sólo tiene que enseñar
    algo cuando de verdad hay algo que enseñar.
    """
    from app.domain.value_objects.formations import (
        central_defender_options,
        inner_midfielder_options,
    )

    if formacion not in LINE_COUNTS:
        return None
    base = plazas(entrenamiento, formacion)
    mejor: tuple[int, int] | None = None
    mejor_cuenta = base
    for centrales in central_defender_options(formacion):
        for interiores in inner_midfielder_options(formacion):
            cuantas = plazas(entrenamiento, formacion, centrales, interiores)
            if cuantas > mejor_cuenta:
                mejor_cuenta, mejor = cuantas, (centrales, interiores)
    if mejor is None or mejor == resolve_split(formacion):
        return None
    return mejor


#: El código de entrenamiento de CHPP, traducido al de la tabla de puestos.
#:
#: EXPLÍCITO Y NO POR TEXTO, y eso se decidió midiendo: diez de los doce casan
#: por etiqueta, pero `ht_constants` llama al 10 «Pases (defensas y
#: centrocampistas)» y la tabla de puestos lo llama «Pases (defensas y centro
#: del campo completo)». Son el mismo entrenamiento con dos redacciones, ya
#: separadas hoy, así que emparejar por el rótulo se rompería en silencio el
#: día que alguien reescriba un texto de pantalla. `test_plazas_de_entrenamiento`
#: vigila que no falte ninguno.
#:
#: El 0 y el 1 están obsoletos en Hattrick --General y Resistencia-- y no tienen
#: pareja: devuelven `None` y con eso la pantalla no filtra, que es lo correcto
#: para un entrenamiento que ya no existe.
DE_CHPP: dict[int, str] = {
    2: "set_pieces",
    3: "defending",
    4: "scoring",
    5: "winger",
    6: "scoring_set_pieces",
    7: "passing",
    8: "playmaking",
    9: "keeper",
    10: "passing_defenders",
    11: "defending_wide",
    12: "winger_forwards",
}


def entrenamiento_de_chpp(codigo: int | None) -> str | None:
    """Qué entrenamiento es un código de CHPP, o `None` si no se sabe."""
    if codigo is None:
        return None
    return DE_CHPP.get(codigo)
