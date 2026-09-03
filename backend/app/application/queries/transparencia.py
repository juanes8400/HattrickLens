"""El catálogo de cálculos: qué hace cada número y con qué constantes.

La pantalla que sale de aquí existe para que el usuario pueda decidir si se
fía. Eso impone una regla que gobierna todo el módulo:

    LAS CONSTANTES SE LEEN DE LOS MOTORES, NUNCA SE COPIAN AQUÍ.

Un catálogo que repite «β = 3» de memoria queda desfasado el día que alguien
toque el motor, y entonces la única pantalla que promete transparencia es la
que miente. Por eso cada valor de abajo entra por `import`, y si un motor
renombra una constante esto revienta al arrancar — que es exactamente lo que
tiene que pasar.

La fórmula sí es texto: es la parte que un humano escribe para que otro humano
la entienda. Lo que no puede ser texto es el número que la acompaña.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.engines import htms
from app.domain.engines.economy_engine import HOME_MATCHES_PER_SEASON, SEASON_WEEKS
from app.domain.engines.metodo_ocho import ESCALERA, UMBRAL_DE_DESCARTE
from app.domain.engines.season_simulator import HOME_ADVANTAGE, SHRINKAGE_K
from app.domain.engines.training_engine import DAYS_PER_HT_YEAR, parametros
from app.domain.engines.youth_skill_score import (
    DEFAULT_WEIGHT_BASE,
    EXPONENTS,
    SQUAD_NORMALISER,
    weights_for,
)
from app.domain.engines.youth_training_plan import (
    CASTIGO_POR_REPETIR,
    SECUNDARIO_DUPLICADO,
    SECUNDARIO_NORMAL,
)
from app.domain.value_objects.ht_constants import skill_name
from app.domain.value_objects.stamina_reference import (
    STAMINA_FORECAST_TABLE,
    STAMINA_MAX_LEVEL,
    STAMINA_MAX_TABLE_AGE,
    STAMINA_MIN_LEVEL,
    STAMINA_MIN_TABLE_AGE,
    STAMINA_TRAINING_PCT_BUCKETS,
    STAMINA_TRAINING_PCT_MAX,
    STAMINA_TRAINING_PCT_MIN,
)


@dataclass
class Constante:
    """Un número de la fórmula, con su valor REAL y qué significa."""

    symbol: str
    value: str
    what: str


@dataclass
class Fuente:
    """De dónde sale un dato que entra en la fórmula.

    Es la mitad que faltaba: una fórmula sin sus fuentes dice cómo se hace la
    cuenta pero no de dónde salen los sumandos, y esa es justo la pregunta que
    trae quien abre esta pantalla. Distingue tres orígenes que NO valen lo
    mismo: lo que Hattrick te enseña, lo que se ha observado en tu propio
    histórico, y lo que aporta una tabla de la comunidad.
    """

    what: str
    origin: str


@dataclass
class Tabla:
    """Una tabla de números que la fórmula consulta en vez de calcular.

    Hay parámetros que no caben en una lista de constantes: el coeficiente de
    cada entrenamiento, el reloj de edad, el nivel esperado de resistencia por
    edad. Enseñar sólo los extremos --«la tabla va de 17 a 36»-- contesta a
    medias: quien abre esta pantalla quiere ver la fila que le toca a SU
    jugador. Así que se enseña entera.
    """

    title: str
    columns: list[str]
    rows: list[list[str]]
    note: str = ""


@dataclass
class Calculo:
    id: str
    name: str
    #: La pregunta que contesta. Va antes que la fórmula a propósito: quien
    #: abre esto quiere saber qué mira, no qué se multiplica.
    answers: str
    formula: str
    sources: list[Fuente] = field(default_factory=list)
    constants: list[Constante] = field(default_factory=list)
    tables: list[Tabla] = field(default_factory=list)
    #: La cuenta hecha con números de verdad, línea a línea. Una fórmula se
    #: entiende, pero no se comprueba: el paso a paso es lo que deja al
    #: usuario repetirla en un papel y ver si le sale lo mismo.
    steps: list[str] = field(default_factory=list)
    limits: list[str] = field(default_factory=list)
    note: str = ""
    #: Nombre del panel VIVO que la pantalla debe pintar debajo, si lo hay.
    #: Así los cuatro paneles de Motor --con sus valores leídos de tu club y
    #: su contraste contra subidas reales-- se conservan enteros dentro de su
    #: cálculo, en vez de quedar en una página aparte.
    live: str | None = None


@dataclass
class Seccion:
    id: str
    name: str
    calcs: list[Calculo]


def _fmt(v: float) -> str:
    """Sin decimales cuando no hacen falta: «16», no «16.0»."""
    return str(int(v)) if float(v).is_integer() else f"{v:.4g}"


def _escalera_de_juveniles() -> str:
    """La escalera de pesos, dibujada con los exponentes REALES del motor."""
    pesos = weights_for()
    return "\n".join(
        f"    {str(bucket):<20} β^{exp:<3} = {_fmt(pesos[bucket])}"
        for bucket, exp in EXPONENTS.items()
    )


#: Cómo se llama en pantalla cada modo de la fórmula técnica. Los nombres son
#: los que ya usa el resto de la aplicación (Portería, Jugadas, Lateral...);
#: aquí sólo se traduce la clave del motor, nunca su número.
NOMBRE_DEL_MODO: dict[str, str] = {
    "goalkeeping": "Portería",
    "defending": "Defensa",
    "defensive_positions": "Defensa (porteros, defensas y centrocampistas)",
    "playmaking": "Jugadas",
    "playmaking_partial": "Jugadas · puestos de aporte parcial",
    "winger": "Lateral",
    "winger_partial": "Lateral · puestos de aporte parcial",
    "wing_attacks": "Lateral (extremos y delanteros)",
    "scoring": "Anotación",
    "shooting": "Anotación, dentro de «Anotación y balón parado»",
    "short_passes": "Pases",
    "through_passes": "Pases (defensas y centrocampistas)",
    "set_pieces": "Balón parado",
    "set_pieces_bonus": "Balón parado, dentro de «Anotación y balón parado»",
}


#: Semanas de una temporada, deducidas del año de Hattrick en vez de escritas.
SEMANAS_POR_TEMPORADA = DAYS_PER_HT_YEAR // 7


def _exacto(v: float) -> str:
    """El número ENTERO de decimales que tiene, sin recortar.

    `_fmt` redondea a cuatro cifras y eso vale para un resultado, no para un
    coeficiente: enseñar «6,09» donde la fórmula usa 6,0896 es justo el tipo
    de media verdad que esta pantalla existe para no contar.
    """
    return str(int(v)) if float(v).is_integer() else repr(float(v))


def _param(clave: str) -> str:
    """Un parámetro suelto de la fórmula, leído del motor."""
    return _exacto(float(parametros()[clave]))


def _param_bruto(clave: str) -> Any:
    return parametros()[clave]


def _curva(clave: str) -> str:
    """Un parámetro de la curva de esfuerzo F(s)."""
    return _exacto(float(parametros()["skill_curve"][clave]))


#: Los tres grados de puesto, con el nombre que ya usa la pantalla.
NOMBRE_DEL_PUESTO: dict[str, str] = {
    "full": "entero",
    "partial": "a medias",
    "none": "fuera",
}


#: A quién se le debe la fórmula. El usuario lo pidió expreso y es de
#: justicia: HT Lens no inventó nada de esto, sólo lo reimplementó para no
#: depender de una llamada a una web ajena. El documento consultado no nombra
#: a una persona concreta, así que aquí no se nombra ninguna.
NOTA_DE_CREDITO = (
    "La fórmula no es nuestra: la formuló la comunidad de Hattrick y se "
    "publicó en el foro del juego (hilo 17024376, mensajes 56 y 57). La "
    "calculadora de Fantamondi (fantamondi.it/HTMS) y Foxtrick la "
    "implementan en abierto, y de ahí sale esta reimplementación, hecha para "
    "dar exactamente el mismo número sin depender de ellos. La documentación "
    "consultada no nombra a un autor individual."
)


#: Las siete habilidades en el orden EXACTO de las columnas de la tabla de
#: puntos. El orden no es decorativo: es el que indexa la tabla del motor.
HABILIDADES_HTMS: tuple[tuple[str, str], ...] = (
    ("POR", "Portería"),
    ("DEF", "Defensa"),
    ("JUG", "Jugadas"),
    ("LAT", "Lateral"),
    ("PAS", "Pases"),
    ("ANOT", "Anotación"),
    ("BP", "Balón parado"),
)

#: El jugador con el que se enseña la cuenta. Sale del documento de referencia
#: para que quien lo tenga delante compare línea a línea. Los números que
#: acompañan a cada paso NO están escritos: los calcula el motor.
EJEMPLO_HTMS: tuple[int, ...] = (1, 16, 12, 10, 13, 5, 7)
EJEMPLO_EDAD = (17, 50)


def _tabla_de_puntos_htms() -> Tabla:
    """Los veinticuatro niveles por las siete habilidades, entera."""
    return Tabla(
        title="Puntos por habilidad y nivel",
        columns=["Nivel", *(corto for corto, _ in HABILIDADES_HTMS)],
        rows=[[str(nivel), *(str(v) for v in fila)] for nivel, fila in sorted(htms.TABLA.items())],
        note=(
            "La tabla crece mucho más deprisa que el nivel: de 16 a 17 en "
            "Defensa hay 150 puntos, y de 3 a 4 hay veintiséis. Por eso dos "
            "jugadores con la misma «suma de estrellas» pueden valer cosas "
            "muy distintas. Los últimos niveles se repiten porque cada "
            "habilidad tiene su propio techo."
        ),
    )


def _tabla_de_ritmo_htms() -> Tabla:
    """Lo que rinde una semana de entrenamiento a cada edad."""
    return Tabla(
        title="Puntos que genera una semana de entrenamiento",
        columns=["Edad", "Puntos por semana"],
        rows=[
            [str(edad), f"{puntos:.2f}"] for edad, puntos in sorted(htms.PUNTOS_POR_SEMANA.items())
        ],
        note=(
            f"Fuera de este rango se usa el extremo más cercano: "
            f"{min(htms.PUNTOS_POR_SEMANA)} por abajo y "
            f"{max(htms.PUNTOS_POR_SEMANA)} por arriba."
        ),
    )


def _el_jugador_del_ejemplo() -> str:
    """Presenta al jugador con el que se hace la cuenta.

    Sin esta línea el paso a paso empieza con un número que sale de la nada, y
    quien lo lee no sabe si es SU jugador o uno inventado.
    """
    niveles = ", ".join(
        f"{largo} {nivel}" for (_, largo), nivel in zip(HABILIDADES_HTMS, EJEMPLO_HTMS, strict=True)
    )
    anos, dias = EJEMPLO_EDAD
    return f"Ejemplo, con un jugador de {anos} años y {dias} días: {niveles}."


def _pasos_de_htms() -> list[str]:
    """La suma de los siete aportes, hecha con un jugador de verdad."""
    pasos = [_el_jugador_del_ejemplo()]
    pasos += [
        f"{largo} en {nivel} → {htms.TABLA[nivel][i]} puntos"
        for i, ((_, largo), nivel) in enumerate(zip(HABILIDADES_HTMS, EJEMPLO_HTMS, strict=True))
    ]
    total = htms.ability(*EJEMPLO_HTMS)
    sumandos = " + ".join(str(htms.TABLA[n][i]) for i, n in enumerate(EJEMPLO_HTMS))
    pasos.append(f"Se suman los siete: {sumandos} = {total}")
    return pasos


def _pasos_de_htms28() -> list[str]:
    """La proyección hasta los 28, paso a paso y con los números del motor."""
    anos, dias = EJEMPLO_EDAD
    base = htms.ability(*EJEMPLO_HTMS)
    quedan = htms.DIAS_POR_ANO - dias
    semanas = quedan / htms.DIAS_POR_SEMANA
    ritmo = htms.PUNTOS_POR_SEMANA[anos]
    del_ano = semanas * ritmo
    enteros = sum(16 * htms.PUNTOS_POR_SEMANA[k] for k in range(anos + 1, htms.EDAD_OBJETIVO))
    total = htms.potential(base, anos, dias)
    return [
        _el_jugador_del_ejemplo(),
        f"Se parte de su HTMS de hoy, el del cálculo de al lado: {base}",
        (
            f"Del año en curso le quedan {htms.DIAS_POR_ANO} − {dias} = "
            f"{quedan} días, que son {quedan} ÷ {htms.DIAS_POR_SEMANA} = "
            f"{semanas:.4f} semanas"
        ),
        (
            f"A los {anos} años cada semana da {ritmo:.2f} puntos: "
            f"{semanas:.4f} × {ritmo:.2f} = {del_ano:.3f}"
        ),
        (
            f"Se añaden las temporadas enteras de {anos + 1} a "
            f"{htms.EDAD_OBJETIVO - 1}, a 16 semanas cada una: {enteros:.3f}"
        ),
        (f"Se suma todo y se redondea: {base} + {del_ano:.3f} + {enteros:.3f} = {total}"),
    ]


def _tabla_de_entrenamientos() -> Tabla:
    """El coeficiente de cada entrenamiento, los catorce."""
    coef = parametros()["training_coefficients"]
    filas = sorted(coef.items(), key=lambda kv: -float(kv[1]))
    return Tabla(
        title="Coeficiente de cada entrenamiento (K_entrenamiento)",
        columns=["Entrenamiento", "K"],
        rows=[[NOMBRE_DEL_MODO.get(modo, modo), _exacto(float(v))] for modo, v in filas],
        note=(
            "Cuanto más alto, más rápido sube esa habilidad con el mismo club "
            "detrás. Balón parado es el más alto porque su habilidad tiene "
            "menos peso en el campo, no porque entrene mejor."
        ),
    )


def _tabla_de_entrenadores() -> Tabla:
    """Qué multiplica cada nivel de entrenador."""
    cfg = parametros()
    escala = cfg["trainer_skill_to_formula_level"]
    coef = cfg["coach_coefficients"]
    return Tabla(
        title="Coeficiente del entrenador (K_entrenador)",
        columns=["Nivel del entrenador", "Escala de la fórmula", "K"],
        rows=[
            [str(visible), str(interno), _exacto(float(coef[interno]))]
            for visible, interno in sorted(escala.items())
        ],
        note=(
            "El nivel 5 no lleva bono aparte: su efecto ya está dentro del "
            "coeficiente. El liderazgo del entrenador no entra en la fórmula."
        ),
    )


def _tabla_del_reloj_de_edad() -> Tabla:
    """El reloj entero, año por año, y lo que frena cada edad."""
    cfg = parametros()
    inicio = int(cfg["age_clock"]["start_age"])
    reloj = [float(v) for v in cfg["age_clock"]["values"]]
    velocidad = [float(v) for v in cfg["age_speed_coefficients"]]
    return Tabla(
        title="Reloj de edad",
        columns=["Edad", "Reloj acumulado", "Velocidad relativa"],
        rows=[
            [str(inicio + i), f"{reloj[i]:.3f}", f"{velocidad[i]:.3f}"] for i in range(len(reloj))
        ],
        note=(
            "Entre dos cumpleaños el reloj se interpola en línea recta. El "
            f"último tramo publicado es el de {inicio + len(reloj) - 1} años: "
            "por encima se prolonga, y esa prolongación es una extensión "
            "nuestra, no un dato."
        ),
    )


def _tramos_de_resistencia() -> list[str]:
    """«5–10 %», «11–15 %»... calculados desde los propios límites."""
    cortes = list(STAMINA_TRAINING_PCT_BUCKETS)
    techos = [c - 1 for c in cortes[1:]] + [int(STAMINA_TRAINING_PCT_MAX)]
    return [f"{a}–{b} %" for a, b in zip(cortes, techos, strict=True)]


def _tabla_de_condicion() -> Tabla:
    """La tabla de resistencia entera: veinte edades por cinco tramos."""
    return Tabla(
        title="Nivel de resistencia al que tiende cada edad",
        columns=["Edad", *_tramos_de_resistencia()],
        rows=[
            [str(edad), *(skill_name(n).capitalize() for n in fila)]
            for edad, fila in sorted(STAMINA_FORECAST_TABLE.items())
        ],
        note=(
            "El % de la cabecera es el REAL: la intensidad del club "
            "multiplicada por la parte que dedicas a resistencia. Un club al "
            "40 % con la mitad en resistencia pone un 20 %, no un 50 %."
        ),
    )


def catalogo() -> list[Seccion]:
    """Todo lo que la herramienta calcula, sección por sección."""
    return [
        Seccion(
            id="entrenamiento",
            name="Entrenamiento",
            calcs=[
                Calculo(
                    id="semanas-al-pop",
                    sources=[
                        Fuente(
                            "Intensidad y parte dedicada a resistencia",
                            "Tu pantalla de Entrenamiento",
                        ),
                        Fuente("Nivel del entrenador y de los ayudantes", "Tu cuerpo técnico"),
                        Fuente("Nivel actual de la habilidad", "La ficha de cada jugador"),
                        Fuente(
                            "Minutos jugados en una posición que entrena", "Los partidos ya jugados"
                        ),
                        Fuente(
                            "Coeficientes K y la tabla de esfuerzo F",
                            "Tabla pública de la comunidad",
                        ),
                        Fuente("Subidas confirmadas para contrastar", "Tu propio histórico"),
                    ],
                    name="Semanas hasta el próximo nivel",
                    answers="Cuánto falta para que un jugador suba una habilidad.",
                    formula=(
                        "K = K_entrenamiento · K_entrenador · K_asistentes\n"
                        "    · intensidad · (1 − %resistencia) · exposición\n"
                        "\n"
                        f"K_asistentes = {_param('assistant_base_coefficient')}"
                        f" + {_param('assistant_bonus_per_level')} · (suma de niveles)\n"
                        "\n"
                        f"F(s) = (s^{_curva('low_power')} − 1)"
                        f" ÷ ({_curva('low_scale')} · {_curva('low_power')})"
                        f"          si s < {_curva('split_level')}\n"
                        f"F(s) = {_curva('high_offset')}"
                        f" + (s − {_curva('high_shift')})^{_curva('high_power')}"
                        f" ÷ ({_curva('high_scale')} · {_curva('high_power')})"
                        f"   si s ≥ {_curva('split_level')}\n"
                        "\n"
                        f"semanas = {SEMANAS_POR_TEMPORADA} · ( reloj⁻¹( reloj(edad)\n"
                        "                          + [F(n+1) − F(n)] / K ) − edad )"
                    ),
                    constants=[
                        Constante(
                            "semanas por año",
                            str(SEMANAS_POR_TEMPORADA),
                            f"Un año de Hattrick son {DAYS_PER_HT_YEAR} días.",
                        ),
                        Constante(
                            "s de corte",
                            _curva("split_level"),
                            "Nivel donde la curva de esfuerzo cambia de tramo.",
                        ),
                        Constante(
                            "exponente bajo",
                            _curva("low_power"),
                            "Potencia del tramo por debajo del corte.",
                        ),
                        Constante(
                            "divisor bajo", _curva("low_scale"), "Escala de ese mismo tramo."
                        ),
                        Constante(
                            "arranque alto",
                            _curva("high_offset"),
                            "Trabajo ya acumulado al llegar al corte.",
                        ),
                        Constante(
                            "desplazamiento alto",
                            _curva("high_shift"),
                            "Lo que se resta al nivel en el tramo alto.",
                        ),
                        Constante(
                            "exponente alto",
                            _curva("high_power"),
                            "Potencia del tramo por encima del corte.",
                        ),
                        Constante(
                            "divisor alto", _curva("high_scale"), "Escala de ese mismo tramo."
                        ),
                        Constante(
                            "ayudantes: base",
                            _param("assistant_base_coefficient"),
                            "Lo que multiplica sin ningún ayudante.",
                        ),
                        Constante(
                            "ayudantes: por nivel",
                            _param("assistant_bonus_per_level"),
                            "Lo que suma cada nivel de ayudante.",
                        ),
                        Constante(
                            "ayudantes: tope",
                            _param("assistant_level_sum_cap"),
                            (
                                f"{_param('max_assistants')} ayudantes por nivel "
                                f"{_param('max_assistant_level')}. Es la SUMA de "
                                "sus niveles, no cuántos son."
                            ),
                        ),
                        Constante(
                            "minutos de partido completo",
                            _param("full_training_minutes"),
                            "Menos minutos, menos exposición, en proporción.",
                        ),
                        Constante(
                            "exposición por puesto",
                            " · ".join(
                                f"{NOMBRE_DEL_PUESTO.get(k, k)} {_exacto(float(x))}"
                                for k, x in _param_bruto("position_training_share").items()
                            ),
                            "Lo que cuenta jugar en un puesto que entrena o no.",
                        ),
                        Constante(
                            "%resistencia por defecto",
                            f"{_param('default_stamina_share')} %",
                            "Lo que se supone si no se conoce tu reparto.",
                        ),
                    ],
                    tables=[
                        _tabla_de_entrenamientos(),
                        _tabla_de_entrenadores(),
                        _tabla_del_reloj_de_edad(),
                    ],
                    limits=[
                        "El subnivel exacto no se publica: si no se conoce, se usa 0,0.",
                        "La tabla pública de edad termina en 34; por encima se prolonga "
                        "su último tramo.",
                        "La resistencia usa un motor separado de la fórmula técnica.",
                    ],
                    note=(
                        "Los coeficientes son la estimación comunitaria pública de "
                        "HT-Tools: no son constantes oficiales de Hattrick ni se "
                        "ajustan con tus datos."
                    ),
                    live="trainingFormula",
                ),
                Calculo(
                    id="individual",
                    sources=[
                        Fuente(
                            "Nivel y techo revelados de cada canterano",
                            "Lo que han visto tus ojeadores",
                        ),
                        Fuente(
                            "Habilidad que toca en cada partido", "Se sortea: se estima por puesto"
                        ),
                        Fuente(
                            "Los factores ⅔ y ½",
                            "Observación de la comunidad, contrastada en el foro",
                        ),
                    ],
                    name="Reparto del entrenamiento Individual",
                    answers=(
                        "Cuánto entrenamiento recibe cada habilidad cuando se elige Individual."
                    ),
                    formula=(
                        "secundaria distinta:  100 % + "
                        f"{SECUNDARIO_NORMAL:.1%}\n"
                        "secundaria repetida:  100 % + "
                        f"{SECUNDARIO_NORMAL:.1%} · {CASTIGO_POR_REPETIR:.0%}"
                        f" = {SECUNDARIO_DUPLICADO:.1%}\n"
                        "\n"
                        f"total cuando se repite = {1 + SECUNDARIO_DUPLICADO:.1%}"
                    ),
                    constants=[
                        Constante(
                            "secundario",
                            f"{SECUNDARIO_NORMAL:.4f}",
                            "Fracción que recibe la habilidad secundaria.",
                        ),
                        Constante(
                            "castigo",
                            f"{CASTIGO_POR_REPETIR:.2f}",
                            "Multiplicador si la secundaria repite la principal.",
                        ),
                    ],
                    limits=[
                        "Cómo se reparte ese total entre las dos habilidades sigue sin cerrarse.",
                        "La habilidad que toca cada partido se sortea por puesto: no "
                        "hay mapa fijo ni un único ritmo.",
                    ],
                ),
                Calculo(
                    id="experiencia",
                    sources=[
                        Fuente(
                            "Partidos jugados y de qué tipo era cada uno",
                            "Tu histórico de partidos",
                        ),
                        Fuente("Puntos que da cada tipo de partido", "Tabla de la comunidad"),
                        Fuente(
                            "Subidas de experiencia ya observadas",
                            "Tu propio histórico: son las que calibran",
                        ),
                    ],
                    name="Puntos de experiencia por nivel",
                    answers="Cuántos partidos hacen falta para subir de experiencia.",
                    formula="nivel(p) = mayor n tal que  puntos_acumulados(n) ≤ p",
                    limits=[
                        "Calibrado contra observaciones; Hattrick no publica la tabla.",
                    ],
                    live="experienceModel",
                ),
                Calculo(
                    id="condicion",
                    sources=[
                        Fuente("Edad del jugador", "Su ficha"),
                        Fuente(
                            "Parte del entrenamiento dedicada a resistencia",
                            "Tu pantalla de Entrenamiento",
                        ),
                        Fuente(
                            "Nivel esperado para cada edad",
                            "Tabla de la comunidad, de 17 a 36 años",
                        ),
                    ],
                    name="Condición",
                    answers=("En qué nivel de resistencia se va a estabilizar un jugador."),
                    formula=(
                        "nivel_esperado = tabla[ edad ][ tramo(%resistencia) ]\n"
                        "\n"
                        f"edad recortada al rango de la tabla: "
                        f"{STAMINA_MIN_TABLE_AGE}–{STAMINA_MAX_TABLE_AGE}"
                    ),
                    constants=[
                        Constante(
                            "edad mínima de la tabla",
                            str(STAMINA_MIN_TABLE_AGE),
                            "Por debajo se lee la fila más joven.",
                        ),
                        Constante(
                            "edad máxima de la tabla",
                            str(STAMINA_MAX_TABLE_AGE),
                            "Por encima se prolonga la última fila.",
                        ),
                        Constante(
                            "% real mínimo",
                            f"{_fmt(STAMINA_TRAINING_PCT_MIN)} %",
                            "Por debajo se lee la primera columna.",
                        ),
                        Constante(
                            "% real máximo",
                            f"{_fmt(STAMINA_TRAINING_PCT_MAX)} %",
                            "Por encima se lee la última columna.",
                        ),
                        Constante(
                            "tramos del %",
                            " · ".join(_tramos_de_resistencia()),
                            "Las cinco columnas de la tabla.",
                        ),
                        Constante(
                            "nivel más bajo de la tabla",
                            f"{STAMINA_MIN_LEVEL} · {skill_name(STAMINA_MIN_LEVEL)}",
                            "Ninguna casilla baja de aquí.",
                        ),
                        Constante(
                            "nivel más alto de la tabla",
                            f"{STAMINA_MAX_LEVEL} · {skill_name(STAMINA_MAX_LEVEL)}",
                            "Ninguna casilla sube de aquí.",
                        ),
                    ],
                    tables=[_tabla_de_condicion()],
                    limits=[
                        "Es el nivel de EQUILIBRIO al que tiende, no una predicción "
                        "semana a semana.",
                        "Fuera del rango de la tabla la edad se recorta: un jugador de "
                        "40 lee la fila de 36.",
                        "La resistencia va por un motor propio, separado de la fórmula "
                        "técnica de entrenamiento.",
                    ],
                ),
                Calculo(
                    id="fidelidad",
                    sources=[
                        Fuente("Cuándo llegó al club", "Tu libro de transferencias"),
                        Fuente("Umbral de cada nivel", "Tabla de la comunidad"),
                    ],
                    name="Fidelidad",
                    answers="Cuánta fidelidad tiene un jugador y cuánto aporta.",
                    formula="fidelidad = f(semanas en el club)",
                    limits=[
                        "Modelo comunitario; Hattrick sólo publica el nivel entero.",
                    ],
                    live="loyaltyModel",
                ),
            ],
        ),
        Seccion(
            id="posiciones",
            name="Posiciones y alineación",
            calcs=[
                Calculo(
                    id="aporte",
                    sources=[
                        Fuente("Habilidades de cada jugador", "Su ficha"),
                        Fuente(
                            "Coeficiente de cada puesto y orden individual", "El Manual no Escrito"
                        ),
                    ],
                    name="Aporte por posición",
                    answers="Cuánto rinde un jugador en cada puesto y orden individual.",
                    formula=(
                        "aporte(jugador, puesto, orden)\n"
                        "  =  Σ  coeficiente(puesto, orden, habilidad) · nivel(habilidad)\n"
                        "    habilidades"
                    ),
                    limits=[
                        "La matriz de coeficientes es comunitaria (Manual no Escrito), no oficial.",
                    ],
                    live="positionModel",
                ),
                Calculo(
                    id="once-optimo",
                    sources=[
                        Fuente(
                            "Habilidades, forma, condición, experiencia y fidelidad",
                            "La última lectura guardada de cada jugador",
                        ),
                        Fuente(
                            "Coeficientes por posición y orden individual",
                            "Manual no Escrito, declarados en positions.yaml",
                        ),
                        Fuente(
                            "Formaciones, casillas y órdenes legales",
                            "Las reglas de alineación que aplica el motor",
                        ),
                        Fuente("Quién está lesionado", "Tu plantilla"),
                    ],
                    name="Once óptimo",
                    answers=(
                        "Qué formación, jugador por casilla y orden individual legal "
                        "maximizan juntos el aporte posicional total."
                    ),
                    formula=(
                        "A(j, s, b) = aporte del jugador j en la casilla s\n"
                        "             con la orden individual b\n"
                        "\n"
                        "max          Σ  A(jugador_s, casilla_s, orden_s)\n"
                        "formación,   s\n"
                        "jugadores,\n"
                        "órdenes\n"
                        "\n"
                        "sujeto a:  una formación legal\n"
                        "           cada jugador en ≤ 1 casilla\n"
                        "           cada casilla con exactamente 1 jugador\n"
                        "           orden_s ∈ órdenes legales de esa casilla\n"
                        "           si el usuario fija orden_k: orden_k = la elegida\n"
                        "\n"
                        "Objetivo = aporte posicional total, no ratings de partido"
                    ),
                    steps=[
                        (
                            "Para cada formación candidata se construyen sus once casillas "
                            "legales y se aplica la penalización posicional que corresponda."
                        ),
                        (
                            "Para cada pareja jugador–casilla se prueban las órdenes "
                            "individuales legales y se conserva la de mayor aporte."
                        ),
                        (
                            "Si fijaste una orden, esa casilla sólo admite la orden elegida; "
                            "los jugadores, casillas y órdenes restantes se vuelven a optimizar."
                        ),
                        (
                            "El algoritmo húngaro asigna jugadores distintos a las once "
                            "casillas para maximizar la suma de esos aportes."
                        ),
                        (
                            "Si no fijaste la formación, se repite el proceso para todas y "
                            "se elige la de mayor aporte posicional total."
                        ),
                    ],
                    limits=[
                        "El objetivo es la suma del índice de aporte posicional basado en "
                        "los coeficientes del Manual no Escrito de positions.yaml.",
                        "No maximiza los ratings predichos de un partido ni estima el "
                        "resultado contra un rival.",
                        "La calificación por sector se calcula después sobre el once elegido: "
                        "es un desglose diagnóstico y no interviene en la optimización.",
                        "Una orden fijada restringe sólo su casilla; no congela al jugador ni "
                        "el resto de la formación.",
                        "Los jugadores con una lesión de una semana o más quedan fuera; un "
                        "jugador magullado sigue disponible.",
                    ],
                    note=(
                        "El campo «calificación total» se conserva por compatibilidad, pero "
                        "representa esta suma de aportes normalizados. No es una predicción "
                        "de los ratings oficiales del partido."
                    ),
                ),
            ],
        ),
        Seccion(
            id="economia",
            name="Economía",
            calcs=[
                Calculo(
                    id="estructural",
                    sources=[
                        Fuente(
                            "Ingresos y gastos, partida por partida",
                            "Tus dos últimas semanas cerradas",
                        ),
                        Fuente("Espectadores", "Esas mismas semanas cerradas"),
                    ],
                    name="Balance sin transferencias",
                    answers=("Si la operación del club se sostiene sola, sin vender a nadie."),
                    formula=(
                        "estructural = patrocinios + taquilla_semana\n"
                        "            − salarios − staff − estadio\n"
                        "            − (juveniles + financieros)\n"
                        "\n"
                        f"taquilla_semana = espectadores · {_fmt(SEASON_WEEKS)}"
                        f" ÷ {_fmt(HOME_MATCHES_PER_SEASON)}"
                    ),
                    constants=[
                        Constante(
                            "semanas por temporada",
                            _fmt(SEASON_WEEKS),
                            "Sobre cuántas semanas se reparte la taquilla.",
                        ),
                        Constante(
                            "partidos en casa",
                            _fmt(HOME_MATCHES_PER_SEASON),
                            "Cuántas veces al año entra taquilla de verdad.",
                        ),
                    ],
                    limits=[
                        "Cada término es la media de las DOS semanas ya cerradas. La "
                        "semana en curso no entra: reporta taquilla 0 hasta que se "
                        "juega el partido en casa.",
                    ],
                    note=(
                        "Una sola implementación alimenta el Panel, Economía y la "
                        "alerta de déficit: las tres dicen el mismo número."
                    ),
                ),
            ],
        ),
        Seccion(
            id="liga",
            name="Liga",
            calcs=[
                Calculo(
                    id="simulacion",
                    sources=[
                        Fuente(
                            "Goles a favor y en contra de cada equipo",
                            "Las jornadas ya jugadas de tu serie",
                        ),
                        Fuente("Partidos que quedan y contra quién", "El calendario de tu liga"),
                        Fuente(
                            "Plazas de ascenso y descenso", "La configuración real de tu división"
                        ),
                    ],
                    name="Simulación de temporada",
                    answers="Probabilidad de terminar en cada puesto.",
                    formula=(
                        "λ_local   = ataque_i · defensa_j · media_liga · ventaja_local\n"
                        "λ_visita  = ataque_j · defensa_i · media_liga\n"
                        "\n"
                        "fuerza_i  = (goles_i + K · media) ÷ (partidos_i + K)\n"
                        "\n"
                        "P(puesto) ≈ Monte Carlo sobre las jornadas que faltan"
                    ),
                    constants=[
                        Constante(
                            "K",
                            _fmt(SHRINKAGE_K),
                            "Encogimiento hacia la media: cuánto desconfiar de pocos partidos.",
                        ),
                        Constante(
                            "ventaja_local",
                            _fmt(HOME_ADVANTAGE),
                            "Multiplicador de goles esperados jugando en casa.",
                        ),
                    ],
                    limits=[
                        "Usa forma agregada: no conoce lesiones, alineaciones ni tácticas.",
                        "«Terminar 1º» no es ascender: eso depende del ranking nacional "
                        "de campeones, que Hattrick no publica.",
                    ],
                ),
            ],
        ),
        Seccion(
            id="juveniles",
            name="Juveniles",
            calcs=[
                Calculo(
                    id="puntaje",
                    sources=[
                        Fuente("Nivel y techo de cada habilidad", "Lo revelado por tus ojeadores"),
                        Fuente("Qué entrena el primer equipo", "Tu pantalla de Entrenamiento"),
                    ],
                    name="Puntaje de selección de entrenamiento",
                    answers="Qué habilidad conviene entrenar en la academia.",
                    formula=(
                        "puntaje(h) =  Σ  peso(cubo) · cuántos(cubo, h)"
                        f"  ÷ {_fmt(SQUAD_NORMALISER)}\n"
                        "             cubos\n"
                        "\n"
                        f"escalera con β = {_fmt(DEFAULT_WEIGHT_BASE)}:\n"
                        f"{_escalera_de_juveniles()}\n"
                        "    al_tope              siempre = 0"
                    ),
                    constants=[
                        Constante(
                            "β",
                            _fmt(DEFAULT_WEIGHT_BASE),
                            "Base de la escalera: cuánto más vale cada peldaño que el siguiente.",
                        ),
                        Constante(
                            "normalizador",
                            _fmt(SQUAD_NORMALISER),
                            "Tamaño MÁXIMO de una academia, no el actual: así el "
                            "puntaje no sube sólo por tener pocos canteranos.",
                        ),
                        Constante(
                            "umbral de descarte",
                            f"{UMBRAL_DE_DESCARTE:.0%}",
                            "Desde cuánta niebla deja de convenir una habilidad concreta.",
                        ),
                    ],
                    limits=[
                        "Quien ya tocó techo pesa CERO y no está en la escalera: no es "
                        "un peldaño más bajo, es que no cuenta.",
                        "Revelar sólo puede SUBIR el mejor techo. Un veredicto bueno es "
                        "firme ya; uno condenatorio necesita las siete reveladas.",
                        "Los peldaños, de más a menos: " + ", ".join(ESCALERA) + ".",
                    ],
                ),
            ],
        ),
        Seccion(
            id="partidos",
            name="Partidos",
            calcs=[
                Calculo(
                    id="hatstats",
                    sources=[
                        Fuente("Los siete ratings del partido", "El detalle de ese partido"),
                    ],
                    name="HatStats",
                    answers="Un número que resume la fuerza mostrada en un partido.",
                    formula=(
                        "HatStats = 3 · mediocampo\n"
                        "         + (def. derecha + def. central + def. izquierda)\n"
                        "         + (atq. derecha + atq. central + atq. izquierda)"
                    ),
                    limits=[
                        "Índice de la comunidad, no de Hattrick. El mediocampo pesa "
                        "triple porque decide la posesión, no porque valga triple gol.",
                    ],
                ),
            ],
        ),
        Seccion(
            id="htms",
            name="HTMS",
            calcs=[
                Calculo(
                    id="htms-ability",
                    name="HTMS",
                    answers="Cuánto vale hoy un jugador, sumando lo que aporta cada habilidad.",
                    sources=[
                        Fuente("Las siete habilidades del jugador", "Su ficha"),
                        Fuente("Los puntos que da cada nivel", "Tabla de la comunidad"),
                    ],
                    formula=(
                        "HTMS = f(POR) + f(DEF) + f(JUG) + f(LAT)\n"
                        "       + f(PAS) + f(ANOT) + f(BP)\n"
                        "\n"
                        "f(habilidad) = tabla[ nivel ][ columna de esa habilidad ]"
                    ),
                    constants=[
                        Constante(
                            "nivel más alto de la tabla",
                            str(htms.NIVEL_MAXIMO),
                            "Por encima se lee esa misma fila.",
                        ),
                        Constante(
                            "habilidad desconocida",
                            "0",
                            "No se estima: lo que no se sabe no suma.",
                        ),
                    ],
                    tables=[_tabla_de_puntos_htms()],
                    steps=_pasos_de_htms(),
                    limits=[
                        "No es una suma de niveles: la tabla no es lineal.",
                        "Mide lo que el jugador YA tiene, no lo que puede llegar a tener.",
                        "Ignora edad, forma, experiencia, fidelidad y resistencia.",
                    ],
                    note=NOTA_DE_CREDITO,
                ),
                Calculo(
                    id="htms28",
                    name="HTMS28",
                    answers=("Cuántos puntos tendría si lo entrenaras sin parar hasta los 28."),
                    sources=[
                        Fuente("El HTMS de hoy", "El cálculo de al lado"),
                        Fuente("Edad exacta, en años y días", "Su ficha"),
                        Fuente("Lo que rinde una semana a cada edad", "Tabla de la comunidad"),
                    ],
                    formula=(
                        f"antes de los {htms.EDAD_OBJETIVO}:\n"
                        f"  HTMS28 = A + (({htms.DIAS_POR_ANO} − d) ÷ "
                        f"{htms.DIAS_POR_SEMANA}) · W(y)\n"
                        f"           + 16 · Σ W(k),  k = y+1 … "
                        f"{htms.EDAD_OBJETIVO - 1}\n"
                        "\n"
                        f"desde los {htms.EDAD_OBJETIVO}:\n"
                        f"  HTMS28 = A − (d ÷ {htms.DIAS_POR_SEMANA}) · W(y)\n"
                        f"           − 16 · Σ W(k),  k = {htms.EDAD_OBJETIVO} … y−1\n"
                        "\n"
                        "A = HTMS de hoy · y = años · d = días · W = puntos por semana"
                    ),
                    constants=[
                        Constante(
                            "edad de referencia",
                            str(htms.EDAD_OBJETIVO),
                            "Todos los jugadores se comparan a esa edad.",
                        ),
                        Constante(
                            "días de un año",
                            str(htms.DIAS_POR_ANO),
                            f"Son {htms.DIAS_POR_ANO // htms.DIAS_POR_SEMANA} semanas.",
                        ),
                        Constante(
                            "días de una semana",
                            str(htms.DIAS_POR_SEMANA),
                            "Convierte los días que quedan en semanas.",
                        ),
                        Constante(
                            "d",
                            f"0–{htms.DIAS_POR_ANO - 1}",
                            "Los días sueltos de la edad; fuera de rango se recortan.",
                        ),
                    ],
                    tables=[_tabla_de_ritmo_htms()],
                    steps=_pasos_de_htms28(),
                    limits=[
                        (
                            "No decide qué habilidad se entrena: convierte tiempo en "
                            "puntos, sin más."
                        ),
                        (
                            "Supone entrenamiento continuo, entrenador bueno, "
                            "ayudantes en torno a 8,23 y un 10 % de resistencia. "
                            "Si tu club no es así, el número tampoco lo es."
                        ),
                        (
                            f"Un chico de {min(htms.PUNTOS_POR_SEMANA)} sale altísimo "
                            "porque le quedan once temporadas por delante, no porque "
                            "sea mejor."
                        ),
                        (
                            f"Pasados los {htms.EDAD_OBJETIVO} deja de ser un "
                            "potencial: es «cuánto valía a los "
                            f"{htms.EDAD_OBJETIVO}»."
                        ),
                        (
                            "A los 42 el ritmo sube en vez de bajar. Es una anomalía "
                            "de la implementación de referencia y se conserva a "
                            "propósito, para dar el mismo número que ella."
                        ),
                    ],
                    note=NOTA_DE_CREDITO,
                ),
            ],
        ),
        Seccion(
            id="transferencias",
            name="Transferencias",
            calcs=[
                Calculo(
                    id="roi",
                    sources=[
                        Fuente("Precio de compra y de venta", "Tu libro de transferencias"),
                        Fuente(
                            "Salario semanal", "Las lecturas guardadas mientras estuvo en plantilla"
                        ),
                        Fuente("Porcentaje del agente", "El mismo libro de transferencias"),
                    ],
                    name="ROI de una transferencia",
                    answers="Cuánto se ganó o se perdió con un jugador.",
                    formula=(
                        "venta_neta = precio · (1 − %agente)\n"
                        "coste      = compra + salario + listados\n"
                        "\n"
                        "ROI = (venta_neta − coste + reventa) ÷ coste · 100"
                    ),
                    limits=[
                        "Sin salario guardado el coste queda incompleto: se marca, no se estima.",
                        "«Reventa» es la comisión que llega si su nuevo club lo vuelve a vender.",
                    ],
                ),
            ],
        ),
    ]


def como_json() -> list[dict[str, Any]]:
    return [
        {
            "id": s.id,
            "name": s.name,
            "calcs": [
                {
                    "id": c.id,
                    "name": c.name,
                    "answers": c.answers,
                    "formula": c.formula,
                    "sources": [{"what": f.what, "origin": f.origin} for f in c.sources],
                    "constants": [
                        {"symbol": k.symbol, "value": k.value, "what": k.what} for k in c.constants
                    ],
                    "tables": [
                        {"title": t.title, "columns": t.columns, "rows": t.rows, "note": t.note}
                        for t in c.tables
                    ],
                    "steps": c.steps,
                    "limits": c.limits,
                    "note": c.note,
                    "live": c.live,
                }
                for c in s.calcs
            ],
        }
        for s in catalogo()
    ]
