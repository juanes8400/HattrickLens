"""El catálogo de cálculos: qué hace cada número y con qué constantes.

La pantalla que sale de aquí existe para que el usuario pueda decidir si se
fía. Eso impone una regla que gobierna todo el módulo:

    LAS CONSTANTES SE LEEN DE LOS MOTORES, NUNCA SE COPIAN AQUÍ.

Un catálogo que repite «β = 3» de memoria queda desfasado el día que alguien
toque el motor, y entonces la única pantalla que promete transparencia es la
que miente. Por eso cada valor de abajo entra por `import`, y si un motor
renombra una constante esto revienta al arrancar, que es exactamente lo que
tiene que pasar.

La fórmula sí es texto: es la parte que un humano escribe para que otro humano
la entienda. Lo que no puede ser texto es el número que la acompaña.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from app.domain.engines import htms
from app.domain.engines.economy_engine import HOME_MATCHES_PER_SEASON, SEASON_WEEKS
from app.domain.engines.metodo_ocho import ESCALERA, UMBRAL_DE_DESCARTE
from app.domain.engines.prediccion import (
    BETA,
    COMPARACIONES,
    ETIQUETAS,
    FACTOR_POR_TACTICA,
    MAXIMO_GOLES_ESPERADOS,
    MINIMO_HISTORIA,
    OBSERVACIONES,
    PESO_GOLES,
    PESO_ORDINAL,
    POISSON_BP_BALON_PARADO,
    POISSON_BP_INTERCEPTO,
    POISSON_BP_MEDIO,
    POISSON_ETA_MEDIA,
    POISSON_JUEGO_CARRIL,
    POISSON_JUEGO_CUADRATICO,
    POISSON_JUEGO_ETA_MAXIMA,
    POISSON_JUEGO_INTERCEPTO,
    POISSON_JUEGO_MEDIO,
    RAZON_MEDIO_CASA_FUERA,
    TOPE_DE_GOLES,
    UMBRALES,
)
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
from app.domain.value_objects.ht_constants import TACTIC_TYPES, skill_name
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
    #: El CUERPO, en párrafos. La ficha nació para explicar un número: fórmula,
    #: constantes, límites. Eso basta para «¿de dónde sale el ROI?» y se queda
    #: corto para un motor entero, que hay que CONTAR --por qué esta forma y no
    #: otra, qué se probó y se descartó, cómo se comprobó que funciona--.
    #:
    #: 2026-09-08, pedido explícito: que el pronóstico de partido se explique
    #: «paso a paso, como si alguien que no conoce se quisiera empapar», con la
    #: calidad de un artículo. Sin prosa larga eso no cabía en ninguna parte:
    #: `note` es una coletilla de once píxeles y `steps` es una cuenta, no una
    #: explicación.
    #:
    #: Vacío en los cálculos que no lo necesitan, que son casi todos.
    body: list[str] = field(default_factory=list)
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


#: ── El pronóstico de partido, dibujado del motor ──────────────────────────
#:
#: Las tres tablas del capítulo «Pronóstico de partido» se GENERAN de las
#: constantes de `prediccion`, no se transcriben. Es la misma regla del módulo
#: llevada al caso peor: son veintitantos números con cuatro decimales, y ese
#: es exactamente el tipo de tabla que nadie vuelve a revisar cuando el motor
#: se reajusta.


def _miles(n: int) -> str:
    """5232 → «5.232». El separador de millar que se lee aquí es el punto."""
    return f"{n:,}".replace(",", ".")


def _coma(v: float) -> str:
    """El número redondeado y con coma decimal, para meterlo dentro de prosa."""
    return _fmt(v).replace(".", ",")


def _con_signo(v: float) -> str:
    """«− 0.14452», para encadenar un término dentro de una fórmula.

    El coeficiente cuadrático es negativo y pegarlo tal cual dejaba «exp( η
    -0.14452 × ...)», que se lee como un guion y no como una resta. El signo
    se DERIVA del valor: si algún día el reajuste lo devuelve positivo, la
    fórmula publicada cambia sola de operador en vez de mentir.
    """
    return f"{'−' if v < 0 else '+'} {_exacto(abs(v))}"


def _por_diez_puntos(coeficiente: float) -> str:
    """Cuánto multiplica llevarse diez puntos porcentuales más de un duelo.

    Un coeficiente ordinal vive en la escala de la recta latente, que no
    significa nada para quien lee. Lo que sí significa algo es la razón de
    momios: `e^(β × 0,10)`. Se calcula, no se teclea, para que siga al motor.
    """
    return f"×{math.exp(coeficiente * 0.10):.2f}"


def _tabla_de_duelos() -> Tabla:
    """Los nueve duelos con su peso, de mayor a menor."""
    filas = sorted(
        (
            (ETIQUETAS[clave], float(beta))
            for (clave, _, _), beta in zip(COMPARACIONES, BETA, strict=True)
        ),
        key=lambda fila: -fila[1],
    )
    return Tabla(
        title="Los nueve duelos, ordenados por lo que pesan",
        columns=["Duelo", "Coeficiente", "Si te llevas 10 puntos más del duelo"],
        rows=[[nombre, _exacto(beta), _por_diez_puntos(beta)] for nombre, beta in filas],
        note=(
            "Cada fila es un ENFRENTAMIENTO, no un rating tuyo. El coeficiente no "
            "dice «subir mi ataque central multiplica por 1,45 mis opciones»: dice "
            "que llevarte diez puntos porcentuales más de ESE DUELO las multiplica "
            "por eso, y eso se consigue subiendo tú o bajando él. El medio campo "
            "manda con diferencia sobre los otros ocho, que quedan agrupados entre "
            "2,2 y 3,9. Las bandas van cruzadas porque el campo es así."
        ),
    )


def _tabla_de_poisson() -> Tabla:
    """Los siete coeficientes de goles, con su lectura en castellano."""
    return Tabla(
        title="Los siete coeficientes de los goles",
        columns=["Componente", "Término", "Coeficiente", "Cómo se lee"],
        rows=[
            [
                "Juego abierto",
                "constante",
                _exacto(POISSON_JUEGO_INTERCEPTO),
                "el nivel del que se parte antes de mirar ningún duelo",
            ],
            [
                "Juego abierto",
                "log p(medio campo)",
                _exacto(POISSON_JUEGO_MEDIO),
                "elasticidad: un 1 % más de medio campo son 2,5 % más de goles",
            ],
            [
                "Juego abierto",
                "exponente de cada carril",
                _exacto(POISSON_JUEGO_CARRIL),
                "cuánto compensa un carril fuerte a uno tapado; los tres lo comparten",
            ],
            [
                "Juego abierto",
                "(η − centro)²",
                _exacto(POISSON_JUEGO_CUADRATICO),
                "la descompresión: estira los extremos que el modelo aplastaba",
            ],
            [
                "Juego abierto",
                "centro de la curvatura",
                _exacto(POISSON_ETA_MEDIA),
                "el η medio de la muestra; sin él el cuadrático dice otra cosa",
            ],
            [
                "Balón parado",
                "constante",
                _exacto(POISSON_BP_INTERCEPTO),
                "el nivel de partida de la amenaza a balón parado",
            ],
            [
                "Balón parado",
                "log p(medio campo)",
                _exacto(POISSON_BP_MEDIO),
                "tres veces menos que en el juego abierto, y a propósito",
            ],
            [
                "Balón parado",
                "log p(balón parado ofensivo)",
                _exacto(POISSON_BP_BALON_PARADO),
                "OJO: comparte el 62 % de su varianza con los ataques",
            ],
        ],
        note=(
            "Los duelos entran en LOGARITMO y el enlace de la regresión también es "
            "logarítmico. Eso convierte la suma en producto y cada coeficiente en "
            "una ELASTICIDAD: el porcentaje que crecen los goles cuando ese duelo "
            "crece un uno por ciento. No se impuso esa forma, salió sola al probar "
            "seis maneras de medir un duelo. El término cuadrático y el sumando de "
            "balón parado la desvían un poco de un producto puro, pero la lectura "
            "sigue valiendo cerca del centro."
        ),
    )


def _tabla_de_tacticas() -> Tabla:
    """Cuánto corrige cada táctica, y con cuántos partidos se midió."""
    medido = {
        0: ("8.200", "dentro del ruido"),
        1: ("287", "recorta ocasiones a los dos equipos"),
        2: ("547", "menos posesión, pero ocasiones más limpias"),
        3: ("423", "dentro del ruido"),
        4: ("593", "algo más de gol del que predicen los ratings"),
        7: ("344", "el que más goles añade sobre lo previsto"),
        8: ("70", "muy pocos partidos: se corrige casi nada"),
    }
    return Tabla(
        title="El factor de cada táctica",
        columns=["Táctica", "Factor", "Lados medidos", "Qué significa"],
        rows=[
            [
                TACTIC_TYPES.get(codigo, str(codigo)),
                _exacto(factor),
                medido.get(codigo, ("-", ""))[0],
                medido.get(codigo, ("-", ""))[1],
            ]
            for codigo, factor in sorted(FACTOR_POR_TACTICA.items(), key=lambda kv: kv[1])
        ],
        note=(
            "Un factor menor que 1 dice que con esa táctica se marca MENOS de lo "
            "que los ratings hacían esperar, y mayor que 1, más. Cuatro se "
            "separan de 1 de forma clara --Presionar, Contraataques, Jugar "
            "creativamente y Atacar por las bandas--; los otros tres están tan "
            "cerca de 1 que da igual aplicarlos que no."
        ),
    )


def _tabla_de_resumenes() -> Tabla:
    """Cómo se saca cada uno de los cuatro resúmenes, y dónde falla."""
    return Tabla(
        title="Los cuatro resúmenes, con la cuenta delante",
        columns=["Resumen", "Cómo se saca, exactamente", "Su punto débil"],
        rows=[
            [
                "Promedio",
                "se suman los valores de esa zona en todos los partidos y se "
                "divide entre cuántos son",
                "un solo partido raro lo arrastra, y con cuatro o cinco partidos eso se nota mucho",
            ],
            [
                "Máximo",
                "el valor más alto de esa zona entre todos los partidos, cada zona por su cuenta",
                "las nueve zonas pueden venir de partidos distintos: describe "
                "un equipo que nunca salió a la cancha",
            ],
            [
                "Máximo por carril",
                "el máximo de cada zona y, dentro de cada trío paralelo --los "
                "tres carriles de defensa y los tres de ataque--, el más alto "
                "se le pone a los tres; el balón parado se queda con el suyo",
                "por construcción los tres carriles salen iguales y altos, así "
                "que borra el lado fuerte, que es información",
            ],
            [
                "Último partido",
                "los valores del día más reciente, tal cual, sin mezclar nada",
                "es un solo partido: recoge antes que nadie un fichaje, y "
                "también toda la suerte de esa tarde",
            ],
        ],
        note=(
            "El resumen se aplica a cada rating POR SEPARADO, no al partido "
            "entero: el medio campo se resume con los medios campos, y así las "
            "nueve zonas. Y un partido al que le falte alguna se descarta entero "
            "antes de resumir, para que las nueve salgan siempre de los mismos "
            "partidos: media lectura no es una lectura con un cero."
        ),
    )


def _tabla_del_barrido() -> Tabla:
    """El barrido de la mezcla, con la fila elegida marcada."""
    pesos = ("0,00", "0,40", "0,60", "0,70", "0,80", "0,90", "1,00")
    perdida = ("0,6445", "0,6350", "0,6333", "0,6329", "0,6328", "0,6329", "0,6334")
    empate = ("calibrado",) * 5 + ("SE SALE", "SE SALE")
    elegido = f"{PESO_GOLES:.2f}".replace(".", ",")
    return Tabla(
        title="Por qué 80 % y no otro número",
        columns=["Peso de los goles", "Error (log-loss)", "Calibración del empate", ""],
        rows=[
            [p, e, c, "← el que se usa" if p == elegido else ""]
            for p, e, c in zip(pesos, perdida, empate, strict=True)
        ],
        note=(
            "Menos es mejor. La curva es planísima entre 0,60 y 0,90 --cuatro "
            "diezmilésimas separan los cuatro-- así que el mínimo por sí solo no "
            "decide nada. Lo que decide es la última columna: a partir de 0,90 la "
            "probabilidad de EMPATE se sale de su banda de calibración, porque la "
            "rejilla de marcadores conserva un resto de exceso de resultados bajos "
            "y el modelo ordinal es lo que lo sujeta. 0,80 es a la vez el mínimo y "
            "el último punto que todavía calibra: por eso se eligió ése."
        ),
    )


def catalogo() -> list[Seccion]:
    """Todo lo que la herramienta calcula, sección por sección."""
    return [
        # Antes de las fórmulas, QUÉ hace cada módulo. Quien abre esta pantalla
        # está decidiendo si se fía, y para eso hacen falta las dos cosas: qué
        # mira la herramienta y cómo lo calcula. La misma lista, en inglés y para
        # presentarla fuera, vive en `docs/25-funcionalidades.md`; si cambia una,
        # cambia la otra.
        Seccion(
            id="modulos",
            name="Qué hace cada módulo",
            calcs=[
                Calculo(
                    id="panel",
                    name="Panel",
                    answers="La foto del club para decidir en un minuto",
                    formula="",
                    note="Caja actual, balance de las últimas semanas cerradas, cuánto "
                    "pesa la nómina sobre lo que entra, fuerza de la plantilla, "
                    "eficiencia del entrenamiento, las alertas abiertas, tu fuerza "
                    "relativa a la serie y el once recomendado.",
                ),
                Calculo(
                    id="club",
                    name="Club y cuerpo técnico",
                    answers="Quién trabaja para ti y cómo está el ambiente",
                    formula="",
                    note="Espíritu de equipo, confianza, socios, inversión en la "
                    "cantera, entrenador y especialistas. Guarda además la serie "
                    "semanal del humor del club, los socios y los niveles del "
                    "cuerpo técnico, y explica qué aporta cada empleado.",
                ),
                Calculo(
                    id="jugadores",
                    name="Jugadores",
                    answers="Todo lo que se sabe de cada uno, presente y pasado",
                    formula="",
                    note="Tabla completa de la plantilla, ordenable y exportable, y "
                    "ficha por jugador: habilidades, forma, resistencia, "
                    "experiencia, fidelidad, TSI, sueldo, HTMS y HTMS28, "
                    "nacionalidad, especialidad, carácter, lesiones, datos de "
                    "compra, estado en el mercado, calificación por puesto e "
                    "historial semanal. Los ex-jugadores tienen su propia ficha "
                    "económica: tiempo en el club, sueldos acumulados, coste de "
                    "listados, lo que dejó la venta y ROI.",
                ),
                Calculo(
                    id="posiciones",
                    name="Posiciones y alineación",
                    answers="Dónde rinde cada jugador y qué once poner",
                    formula="",
                    note="Evalúa a cada jugador en 19 variantes de puesto y orden "
                    "individual, más capitán, lanzador de balón parado y de "
                    "penaltis. Recomienda el mejor once para cualquier formación "
                    "legal, admite repartos entre el centro y las bandas, calcula "
                    "lo que aporta cada sector y compara la propuesta con la "
                    "alineación que ya mandaste a Hattrick.",
                ),
                Calculo(
                    id="entrenamiento-que-hace",
                    name="Entrenamiento",
                    answers="Cuánto falta para la siguiente subida, y si entrenas lo que conviene",
                    formula="",
                    note="Enseña el entrenamiento actual, la intensidad, la parte "
                    "dedicada a resistencia, el entrenador, los ayudantes y la "
                    "velocidad efectiva. Estima lo que falta para el siguiente "
                    "nivel con la edad, el cuerpo técnico, la intensidad y los "
                    "minutos REALES jugados en posiciones que entrenan. Sigue las "
                    "subidas confirmadas, la experiencia, la fidelidad y la "
                    "resistencia, prevé niveles futuros, y después de los partidos "
                    "de la semana compara todos los entrenamientos posibles para "
                    "enseñar cuál habría aprovechado mejor esos mismos minutos.",
                ),
                Calculo(
                    id="juveniles-que-hace",
                    name="Juveniles",
                    answers="Qué tienes en la cantera y a quién no puedes dejar pasar",
                    formula="",
                    note="Trabaja con las habilidades actuales reveladas, los techos "
                    "revelados, la edad, el plazo para ascender y los rangos de "
                    "HTMS28. Clasifica a los juveniles, avisa de los ascensos que "
                    "se te acaban, recomienda entrenamiento principal y secundario, "
                    "propone la siguiente alineación juvenil y sigue a los "
                    "ojeadores, sus regiones, el coste de la academia, las ventas y "
                    "los antiguos canteranos.",
                ),
                Calculo(
                    id="transferencias-que-hace",
                    name="Transferencias",
                    answers="Qué dejó de verdad cada jugador que pasó por el club",
                    formula="",
                    note="Libro histórico de comprados, canteranos, vendidos y "
                    "despedidos, con coste de compra, sueldos acumulados, coste de "
                    "los listados, comisión del agente, producto neto de la venta, "
                    "comisiones de reventa, beneficio y ROI. Con desglose por "
                    "temporada, semana de compra, semana de venta, edad, "
                    "entrenamiento, habilidad más alta y hora de cierre de la "
                    "subasta.\n\nDe quien se fue antes de que la aplicación "
                    "existiera, Hattrick no publica el sueldo hacia atrás. Esos "
                    "sueldos se ESTIMAN a partir del TSI y la edad contra las "
                    "lecturas de tu propio club, y toda cifra estimada va marcada: "
                    "cada fila dice si es medida, calculada o desconocida, y los "
                    "totales se pueden ver con todo, sin las desconocidas, o sólo "
                    "con lo medido.",
                ),
                Calculo(
                    id="partidos-que-hace",
                    name="Partidos",
                    answers="Qué pasó en cada partido y por qué",
                    formula="",
                    note="Historial por temporada y competición, registro en casa y "
                    "fuera, goles, Hatstats, generación de ocasiones, mejores "
                    "calificaciones por sector y tasa de conversión. Cada partido "
                    "se abre con la comparación sector a sector, el radar de "
                    "calificaciones, el análisis de ocasiones y la explicación del "
                    "resultado.",
                ),
                Calculo(
                    id="liga-que-hace",
                    name="Liga",
                    answers="Cómo va la temporada y cómo puede acabar",
                    formula="",
                    note="Clasificación oficial en total, en casa y fuera, el calendario "
                    "completo y la evolución real de puestos y puntos. Proyección "
                    "de temporada, marcada como tal, con puntos esperados, "
                    "probabilidad de cada puesto final, de título y de acabar entre "
                    "los cuatro primeros, los límites matemáticos mejor y peor, y "
                    "un pronóstico para cada equipo. Compara además TSI, forma y "
                    "resistencia de toda la serie, y arma el mejor once por "
                    "calificaciones reales de una jornada o de la temporada entera.",
                ),
                Calculo(
                    id="copa-que-hace",
                    name="Copa",
                    answers="Qué te juegas en el siguiente cruce",
                    formula="",
                    note="Tu copa actual, la ronda oficial, el próximo rival, cuántas "
                    "victorias faltan para el título y los premios que todavía "
                    "puedes alcanzar. Explica qué pasa si ganas y qué pasa si "
                    "pierdes, incluido el movimiento entre niveles de copa donde "
                    "aplica. Con análisis del rival, una estimación de probabilidad "
                    "(marcada como estimación), los ingresos de copa observados, un "
                    "escenario aparte de taquilla futura, preparación de "
                    "resistencia para 120 minutos y un orden indicativo de "
                    "lanzadores de penalti.",
                ),
                Calculo(
                    id="rivales-que-hace",
                    name="Rivales",
                    answers="Cómo llega el equipo que tienes enfrente",
                    formula="",
                    note="Analiza a los rivales de liga y copa con la información "
                    "pública que Hattrick publica de sus partidos recientes. Estima "
                    "su once probable, compara TSI, forma, resistencia y "
                    "experiencia, y detecta fichajes recientes, actividad del "
                    "mánager, formaciones y tácticas habituales, rotación del lado "
                    "de ataque y jugadores visibles. Propone marcajes y una "
                    "comparación del campo por siete zonas. De tu equipo puede usar "
                    "las calificaciones oficiales previstas de las órdenes que ya "
                    "mandaste; del rival, sólo partidos ya jugados.",
                ),
                Calculo(
                    id="economia-que-hace",
                    name="Economía",
                    answers="A dónde va tu dinero y cuánto te queda",
                    formula="",
                    note="Sigue las categorías oficiales de ingresos y gastos de "
                    "Hattrick sin renombrarlas ni fundirlas. Enseña las finanzas de "
                    "la semana en curso, el histórico de ingresos, gastos, "
                    "resultado y caja, los balances acumulados y un diagrama de "
                    "flujo para varias ventanas de tiempo. Los valores futuros van "
                    "APARTE y marcados como escenarios, nunca como resultados. "
                    "Admite proyección estructural, rangos de incertidumbre y, "
                    "cuando hay suficiente historia, comparación con un modelo de "
                    "series de tiempo. Y dice cuántas semanas aguanta la caja "
                    "actual, con y sin contar la compraventa.",
                ),
                Calculo(
                    id="estadio-que-hace",
                    name="Estadio",
                    answers="Si te sobran asientos o te faltan",
                    formula="",
                    note="Analiza el aforo real, la asistencia, la ocupación, los "
                    "ingresos y la demanda por sector. Distingue la demanda que se "
                    "puede medir de la que queda oculta cuando un sector se agota, "
                    "e identifica los partidos en los que el aforo pudo estar "
                    "limitando la entrada.",
                ),
            ],
        ),
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
                    name="Resistencia",
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
                            "Habilidades, forma, resistencia, experiencia y fidelidad",
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
                        "Encuentra el mayor aporte posicional posible en dos modos. En "
                        "«Mejor formación», compara las diez formaciones con su reparto "
                        "predeterminado. Al elegir una, por ejemplo, 3-5-2, mantiene esa "
                        "estructura y optimiza dentro de ella los jugadores y las órdenes "
                        "que no fijaste."
                    ),
                    formula=(
                        "A(j, s, b) = aporte del jugador j en la casilla s\n"
                        "             con la orden individual b\n"
                        "\n"
                        "MODO «MEJOR FORMACIÓN»\n"
                        "Q(f) = max                  Σ A(jugador_s, casilla_s, orden_s)\n"
                        "       jugadores, órdenes  s\n"
                        "f* = argmax Q(f), entre las 10 formaciones con su reparto base\n"
                        "\n"
                        "MODO «FORMACIÓN ELEGIDA»\n"
                        "dadas f y su distribución central/bandas:\n"
                        "max                            Σ A(jugador_s, casilla_s, orden_s)\n"
                        "jugadores, órdenes no fijadas  s\n"
                        "\n"
                        "sujeto a:  cada jugador en ≤ 1 casilla\n"
                        "           cada casilla con exactamente 1 jugador\n"
                        "           orden_s ∈ órdenes legales de esa casilla\n"
                        "           si el usuario fija orden_k: orden_k = la elegida\n"
                        "\n"
                        "Objetivo = aporte posicional total, no ratings de partido"
                    ),
                    steps=[
                        (
                            "Al abrir la pantalla, prueba las diez formaciones con el reparto "
                            "central/bandas predeterminado de cada una."
                        ),
                        (
                            "Para cada pareja jugador–casilla se prueban las órdenes "
                            "individuales legales y se conserva la de mayor aporte."
                        ),
                        (
                            "El algoritmo húngaro asigna once jugadores distintos y se muestra "
                            "la formación cuya suma de aportes es mayor."
                        ),
                        (
                            "Si eliges 3-5-2, deja de comparar formaciones: conserva el 3-5-2 y "
                            "recalcula el mejor once para la distribución central/bandas elegida."
                        ),
                        (
                            "Una orden manual queda fijada a la casilla, no al jugador visible. "
                            "El jugador puede cambiar mientras se reasignan todos los jugadores "
                            "y se recalculan las órdenes no fijadas."
                        ),
                    ],
                    limits=[
                        "El objetivo es la suma del índice de aporte posicional basado en "
                        "los coeficientes del Manual no Escrito de positions.yaml.",
                        "No maximiza los ratings predichos de un partido ni estima el "
                        "resultado contra un rival.",
                        "La calificación por sector se calcula después sobre el once elegido: "
                        "es un desglose diagnóstico y no interviene en la optimización.",
                        "«Mejor formación» compara el reparto predeterminado de cada formación; "
                        "los repartos alternativos se evalúan al elegir una formación y su "
                        "distribución central/bandas.",
                        "Si fijas una orden mientras sigues en «Mejor formación», se restringe "
                        "la formación ganadora mostrada, pero no se vuelve a comparar el ranking "
                        "de las diez formaciones. Para estudiar un 3-5-2 con tus órdenes, elige "
                        "primero 3-5-2.",
                        "Una orden fijada restringe sólo su casilla: no congela al jugador. Al "
                        "cambiar de formación o de distribución se limpian las órdenes, porque "
                        "las casillas ya no representan lo mismo.",
                        "Los jugadores con una lesión de una semana o más quedan fuera; un "
                        "jugador magullado sigue disponible.",
                    ],
                    note=(
                        "Flujo para una 3-5-2 personalizada: selecciona 3-5-2, define el reparto "
                        "central/bandas y después fija las órdenes. «Calificación total» es la "
                        "suma de aportes normalizados; no es una predicción de ratings oficiales."
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
        # ── EL PRONÓSTICO DE PARTIDO ──────────────────────────────────────
        #
        # Ocho fichas que son un artículo, no ocho cálculos sueltos. Encargo
        # explícito del 2026-09-08: «que explique paso a paso todo el proceso,
        # como si alguien que no conoce se quisiera empapar del tema».
        #
        # Va en su PROPIA sección y no dentro de Liga, aunque naciera allí:
        # desde el 2026-09-08 el mismo motor firma también el pronóstico de
        # Copa y el de la ficha de rival. Colgarlo de Liga diría que es un
        # cálculo de Liga, y entonces quien llegue desde Copa no lo encuentra.
        Seccion(
            id="pronostico",
            name="Pronóstico de partido",
            calcs=[
                Calculo(
                    id="pronostico-resumen",
                    name="1 · En una página",
                    answers=(
                        "Qué es el pronóstico, qué necesita para funcionar y qué "
                        "devuelve. El resto del capítulo lo desarrolla paso a paso."
                    ),
                    body=[
                        "Cuando la aplicación dice «34 % de victoria, 28 % de empate, "
                        "38 % de derrota» no está opinando ni comparando presupuestos: "
                        "está aplicando dos regresiones ajustadas sobre "
                        f"{_miles(OBSERVACIONES)} partidos de liga reales de 979 equipos "
                        "repartidos por cinco países. Este capítulo cuenta, sin "
                        "saltarse nada, cómo se llega de los ratings de un partido a "
                        "esos tres números.",
                        "La idea de fondo cabe en una frase: un partido de Hattrick es "
                        "un conjunto de duelos localizados. Tu ataque por la izquierda "
                        "no se enfrenta a «el rival», se enfrenta a su defensa por la "
                        "derecha, que es quien cubre ese carril del campo. Si se mide "
                        "qué parte de cada duelo te llevas y se sabe cuánto pesa cada "
                        "uno, se puede estimar cuántos goles marcará cada equipo; y de "
                        "una estimación de goles sale, por aritmética, la probabilidad "
                        "de cada marcador y por tanto de cada resultado.",
                        "El motor da dos respuestas a la misma pregunta y luego las "
                        "promedia. La primera mira los GOLES: una regresión de Poisson "
                        "estima cuántos marca cada lado y despliega esa estimación en "
                        "una rejilla de marcadores. La segunda mira el RESULTADO: una "
                        "regresión ordinal aprende directamente de quién ganó, sin "
                        "pasar por los goles. Se equivocan en sitios distintos, así "
                        f"que juntas --{PESO_GOLES:.0%} goles, {PESO_ORDINAL:.0%} "
                        "resultado-- aciertan más que cualquiera de las dos por "
                        "separado.",
                        "Lo que sigue son siete pasos. De dónde sale la muestra (paso "
                        "2), cómo se mide un duelo (paso 3), cómo se convierten los "
                        "duelos en goles (paso 4), qué corrige la táctica que los "
                        "ratings no ven (paso 5), cómo se pasa de goles a marcadores y "
                        "de marcadores a probabilidades (paso 6), por qué hay una "
                        "segunda opinión y cuánto pesa (paso 7), y cómo se comprobó que "
                        "todo esto funciona de verdad (paso 8). El paso 9 dice qué NO "
                        "puede hacer, que es la parte que conviene leer dos veces.",
                    ],
                    formula=(
                        "duelo         p = A / (A + B)      A tuyo, B suyo, mismo carril\n"
                        "\n"
                        "goles         λ = [ juego_abierto(p) + balón_parado(p) ]\n"
                        "                  × factor de la táctica\n"
                        "marcadores    P(i, j) = Poisson(i; λ_tuya) × Poisson(j; λ_suya)\n"
                        "\n"
                        "resultado     P(victoria) = suma de las casillas con i > j\n"
                        "              P(empate)   = suma de la diagonal\n"
                        "              P(derrota)  = suma de las casillas con i < j\n"
                        "\n"
                        f"mezcla        final = {PESO_GOLES:.2f} × goles "
                        f"+ {PESO_ORDINAL:.2f} × ordinal"
                    ),
                    sources=[
                        Fuente(
                            "Los nueve ratings por zona de los dos equipos",
                            "Sus partidos ya jugados, con el resumen que elijas "
                            "(promedio por defecto)",
                        ),
                        Fuente(
                            "Cuánto pesa cada zona",
                            f"Dos regresiones sobre {_miles(OBSERVACIONES)} partidos de "
                            "liga de 979 equipos de cinco países",
                        ),
                    ],
                    constants=[
                        Constante(
                            "partidos del ajuste",
                            _miles(OBSERVACIONES),
                            "Sobre cuántos partidos reales se estimaron los coeficientes.",
                        ),
                        Constante(
                            "peso de los goles",
                            f"{PESO_GOLES:.2f}",
                            "Cuánto manda la regresión de Poisson en la mezcla final.",
                        ),
                        Constante(
                            "peso del resultado",
                            f"{PESO_ORDINAL:.2f}",
                            "Cuánto corrige la regresión ordinal.",
                        ),
                        Constante(
                            "partidos previos mínimos",
                            str(MINIMO_HISTORIA),
                            "Con menos que esto por lado no se pronostica nada.",
                        ),
                    ],
                    steps=[
                        "Se recogen los partidos ya jugados de los dos equipos, de UNA "
                        "sola competición, y se resume cada rating con el resumen "
                        "elegido --el promedio, si no se toca nada--.",
                        "Los nueve ratings de cada lado se cruzan contra los del rival "
                        "en el carril que les toca: nueve duelos, cada uno un número "
                        "entre 0 y 1.",
                        "Cinco de esos duelos --medio campo, los tres ataques y el "
                        "balón parado ofensivo-- entran en la regresión de Poisson y "
                        "salen los goles esperados de ese lado. Se repite al revés "
                        "para el rival.",
                        "Con los dos números de goles se construye la rejilla de "
                        "marcadores y se suman sus casillas en tres montones: gano, "
                        "empato, pierdo.",
                        "Los nueve duelos, todos, entran además en la regresión "
                        "ordinal, que da su propia terna sin mirar los goles.",
                        f"Las dos ternas se promedian {PESO_GOLES:.0%} / "
                        f"{PESO_ORDINAL:.0%} y eso es lo que se pinta en la barra.",
                    ],
                    limits=[
                        "Todo el capítulo describe un motor ESTADÍSTICO ajustado sobre "
                        "partidos pasados. No simula el partido y no conoce la "
                        "alineación que se pondrá el domingo, ni la tuya ni la del "
                        "rival: mide a cada equipo por los partidos que ya jugó.",
                        "De la táctica sí sabe algo, y es el paso 5: la tuya se lee de "
                        "las órdenes si ya las mandaste, y la del rival se pondera por "
                        "las que ha usado. Lo que no entra es la actitud --Hattrick "
                        "sólo la publica de tu propio equipo-- ni las lesiones, las "
                        "sanciones o las tarjetas.",
                        "Los dos avisos que conviene no saltarse están en el paso 8: "
                        "el coeficiente del balón parado no se puede leer literalmente, "
                        "y el empate sale algo más alto de lo que ocurre.",
                    ],
                    note=(
                        "Los coeficientes de todo el capítulo se leen del motor cada vez "
                        "que se abre esta pantalla. Si alguien reajusta el modelo y no "
                        "toca esta página, la página cambia igual: es la única promesa "
                        "que hace Transparencia."
                    ),
                ),
                Calculo(
                    id="pronostico-muestra",
                    name="2 · De dónde salen los números",
                    answers=(
                        "Qué partidos se miran para describir a un equipo, cuál de los "
                        "cuatro resúmenes se les aplica, y por qué no se mezclan liga y "
                        "copa."
                    ),
                    body=[
                        "Hattrick no publica los ratings de un partido que todavía no "
                        "se ha jugado. Nadie los conoce: dependen de la alineación que "
                        "se envíe, de la forma del día y de las órdenes. Así que el "
                        "primer problema no es predecir, es DESCRIBIR: hay que resumir "
                        "en nueve números cómo suele salir cada equipo.",
                        "EL RESUMEN LO ELIGES TÚ, y son cuatro. Cada uno responde una "
                        "pregunta distinta sobre los mismos partidos: el PROMEDIO dice "
                        "cómo suele salir; el MÁXIMO, de lo que es capaz "
                        "en cada zona; el MÁXIMO POR CARRIL, de lo que es capaz por "
                        "cualquiera de los tres carriles de una mitad --si rompió por "
                        "la izquierda puede volver a romper por la derecha cuando el "
                        "rival mueva a sus hombres--; y el ÚLTIMO PARTIDO, con lo que "
                        "salió el último día, sin resumir nada.",
                        "Abre en el PROMEDIO: usa todos los partidos que entran y es el "
                        "más fácil de repetir con una calculadora. Tiene un precio "
                        "conocido --un partido raro, el día que se rotó medio equipo o "
                        "el 7-0 al colista, tira del número--, y por eso los otros tres "
                        "están al lado: si sospechas de un partido, el máximo o el "
                        "último contestan otra pregunta sobre los mismos datos. Y "
                        "medido, es el que menos se equivoca de los cuatro.",
                        "LA SEDE SE CORRIGE, porque un resumen la diluye. La ventaja de "
                        "campo no se suma aparte: ya viene dentro de los ratings, y el "
                        "medio campo de un equipo en casa sale un 17,8 % más alto que "
                        "fuera. El promedio mezcla partidos de casa y de fuera, así que "
                        "sin corregir el local entraba rebajado y el visitante inflado. "
                        "Por eso el medio campo del resumen se lleva a la sede del "
                        "partido que viene, con la mezcla real de cada equipo: quien ya "
                        "jugó casi todo en casa apenas se toca. Sólo el medio campo, "
                        "porque en las otras ocho zonas la diferencia entre casa y fuera "
                        "es de un 2 % o menos. En campo neutral, o en un partido "
                        "hipotético sin sede, no se corrige nada; en la ficha de rival, "
                        "sólo con un cruce de liga o de promoción.",
                        "El mando vive donde se ve su efecto. En la ficha de rival, "
                        "junto al mapa de la cancha, con un selector para tu lado y "
                        "otro para el suyo: lo que quieres saber de ti no tiene por "
                        "qué ser lo mismo que quieres saber de él. En Liga es UNO solo, "
                        "en la pestaña de Proyección, y vale para los ocho equipos "
                        "--ahí no hay dos lados, hay ocho--: mueve los puntos "
                        "esperados, la distribución de puestos y los límites. En Copa "
                        "vuelven a ser dos, como en la ficha.",
                        "EL PRÓXIMO PARTIDO DEL RESUMEN DE LIGA NO USA RESUMEN. Es el "
                        "único sitio de esa pantalla que pronostica UN partido, y un "
                        "partido se juega con un once, no con el promedio de cinco. Así "
                        "que cada lado va con una alineación concreta: la tuya ENVIADA "
                        "si ya mandaste órdenes, y si no la de tu ÚLTIMO partido; la "
                        "del rival, siempre la de su último partido, porque sus "
                        "órdenes son privadas hasta que se juega y su último once es "
                        "lo más reciente que se sabe de él. La táctica va con cada "
                        "alineación: la de esas mismas órdenes o la de ese mismo "
                        "partido. El precio es la fragilidad --un solo partido trae "
                        "toda la suerte de esa tarde-- y la pantalla lo dice.",
                        "TU LADO TIENE UNA OPCIÓN MÁS: la ALINEACIÓN ENVIADA. Cuando "
                        "ya mandaste órdenes, Hattrick calcula él mismo los ratings de "
                        "minuto 0 de esa alineación, y eso no resume nada pasado: es "
                        "el partido que viene. De un rival nunca existe, porque sus "
                        "órdenes son privadas hasta que se juega. Y no viene completa: "
                        "Hattrick prevé siete sectores y no prevé los dos de acciones "
                        "indirectas a balón parado, así que esos dos se toman de tu "
                        "resumen de lo ya jugado y la pantalla lo avisa. En el "
                        "selector de Liga no se ofrece: de siete de los ocho equipos no "
                        "se pueden ver las órdenes, y un método que sólo funcionara "
                        "para uno no describiría esa pantalla. Por eso tus órdenes "
                        "entran sólo donde hay un único partido tuyo: el próximo del "
                        "Resumen.",
                        "EL RESUMEN SALE DE UNA SOLA COMPETICIÓN, y esto importa más de "
                        "lo que parece. Un equipo no juega igual en liga que en copa: "
                        "medido sobre el equipo del autor en la temporada 83, su medio "
                        "campo en los seis partidos de liga fue 6, 10, 9, 11, 9 y 19, y "
                        "en los seis de copa fue 8, 13, 27, 13, 21 y 21. Son dos "
                        "equipos distintos. Un promedio que los mezcle no describe a "
                        "ninguno de los dos: infla al de liga y subestima al de copa. "
                        "Mezclados, el error de goles de la copa casi doblaba al de la "
                        "liga --1,97 contra 1,17-- y no era azar, era esto.",
                        "El reparto lo decide CON QUÉ EQUIPO se juega, no el formato "
                        "del torneo. La promoción va con la liga: es el desenlace del "
                        "mismo torneo, contra rivales del mismo nivel. El Hattrick "
                        "Masters también va con la liga, aunque sea eliminatoria, "
                        "porque se sale a ganarlo con el once titular, que es justo lo "
                        "que el resumen intenta describir. La copa va sola, por lo "
                        "mismo al revés.",
                        "Los AMISTOSOS son una tercera muestra, y en la ficha de un "
                        "rival se piden con un selector aparte, en la esquina: "
                        "oficiales O amistosos, uno u otro, nunca los dos ni ninguno. "
                        "Nunca los dos porque una muestra que los mezcle no describe a "
                        "nadie --son dos equipos distintos, por lo mismo que liga y "
                        "copa-- y nunca ninguno porque entonces no quedaría nada que "
                        "resumir. Abre en oficiales. Ese selector manda sobre toda la "
                        "ficha --el mapa de la cancha, el pronóstico, el once probable, "
                        "la táctica y la rotación de lado-- para que ninguna parte de "
                        "la pantalla pueda contar algo distinto del mismo equipo.",
                        "Con amistosos marcados la advertencia sigue en pie: un "
                        "amistoso se juega con suplentes y sin nada en juego, y los "
                        "coeficientes salieron de partidos de liga, así que aplicarlos "
                        "ahí es extrapolar.",
                        f"Basta con {MINIMO_HISTORIA} partido previo por lado. Estuvo en "
                        "tres y se bajó tras medirlo: con un solo partido previo el "
                        "error es 0,661 contra 0,674 con tres, o sea que exigir tres no "
                        "era mejor, y encima se negaba a pronosticar en las jornadas 2 "
                        "y 3, que es cuando más se quiere saber.",
                    ],
                    formula=(
                        "para cada uno de los nueve ratings:\n"
                        "    valor = RESUMEN(ese rating en los partidos que entran)\n"
                        "\n"
                        "RESUMEN, a elegir:\n"
                        "    Promedio           → la media                (por defecto)\n"
                        "    Máximo             → el mejor registro de esa zona\n"
                        "    Máximo por carril  → el mejor de los tres carriles de esa\n"
                        "                         mitad, aplicado a los tres\n"
                        "    Último partido     → el del último día, sin resumir\n"
                        "\n"
                        "y después, la sede del partido que viene (sólo el medio campo):\n"
                        "    en casa   medio × h / (f·h + (1−f)·a)\n"
                        "    fuera     medio × a / (f·h + (1−f)·a)\n"
                        f"    h = √{_coma(RAZON_MEDIO_CASA_FUERA)}   a = 1 / h   "
                        "f = parte de sus partidos jugada en casa\n"
                        "\n"
                        "sólo para TU lado, y sólo con órdenes ya enviadas:\n"
                        "    Alineación enviada → los siete sectores que Hattrick prevé;\n"
                        "                         los dos de balón parado, de tu resumen\n"
                        "\n"
                        "qué partidos entran, según la pantalla:\n"
                        "    Liga            → liga, promoción y Hattrick Masters\n"
                        "    Copa            → sólo copa\n"
                        "    Ficha de rival  → oficiales O amistosos, según el\n"
                        "                      selector de la esquina"
                    ),
                    sources=[
                        Fuente(
                            "Los nueve ratings de cada partido jugado",
                            "El detalle de ese partido, tal como lo publica Hattrick",
                        ),
                        Fuente(
                            "Qué partidos cuentan como liga, copa o amistoso",
                            "El tipo de partido que Hattrick asigna a cada uno",
                        ),
                        Fuente(
                            "Los partidos del rival",
                            "Su historial público, pedido al abrir la ficha",
                        ),
                    ],
                    tables=[_tabla_de_resumenes()],
                    constants=[
                        Constante(
                            "resúmenes disponibles",
                            "4",
                            "Promedio, máximo, máximo por carril y último partido. Tu "
                            "lado suma la alineación enviada.",
                        ),
                        Constante(
                            "resumen por defecto",
                            "promedio",
                            "El que abre en Liga, Copa y la ficha de rival.",
                        ),
                        Constante(
                            "partidos previos mínimos",
                            str(MINIMO_HISTORIA),
                            "Con menos que esto por lado, la pantalla no pronostica.",
                        ),
                    ],
                    steps=[
                        "Se decide QUÉ partidos entran. En Liga, los de liga de esta "
                        "temporada; en Copa, los de copa; en la ficha de un rival, los "
                        "oficiales o los amistosos, según el selector de la esquina.",
                        "Se leen sus nueve ratings: medio campo, tres defensas, tres "
                        "ataques y los dos de balón parado. Una lectura a la que le "
                        "falte alguno se descarta entera: media lectura no es una "
                        "lectura con un cero.",
                        "Se aplica el RESUMEN elegido a cada rating por separado. Con "
                        "el promedio, que es el que abre: medio campo 6, 9, 9, 10, 11, "
                        "19 → 64 / 6 = 10,7. Ese mismo medio campo, con el máximo, "
                        "sale 19.",
                        "Se repite con el rival y con SU selector: su medio campo sale, "
                        "digamos, 14,5. Los dos lados no tienen por qué llevar el "
                        "mismo resumen, salvo en Liga, donde el selector es uno solo "
                        "para los ocho equipos.",
                        "Si tu lado va con «Alineación enviada», los siete sectores "
                        "que Hattrick prevé sustituyen a los resumidos; los dos de "
                        "balón parado se quedan con tu resumen, porque Hattrick no los "
                        "prevé.",
                        "Esos dos vectores de nueve números son toda la entrada del "
                        "modelo. Nada más entra.",
                    ],
                    limits=[
                        "Un equipo que acaba de fichar o de vender medio plantel tarda "
                        "unas jornadas en reflejarse en su resumen. El modelo describe "
                        "lo que fue, no lo que acaba de pasar en el mercado.",
                        "Al principio de temporada el resumen se calcula con muy pocos "
                        "partidos y es frágil: con uno o dos es casi ese partido, y "
                        "los cuatro se parecen entre sí porque no hay variedad que "
                        "resumir.",
                        "Las cifras de error del paso 8 predicen cada partido con sus "
                        "propios ratings. Con el promedio de los partidos anteriores, "
                        "que es lo que usa la pantalla, el error medido es mayor "
                        "--log-loss 0,6924 contra 0,6177 en los mismos partidos, ya "
                        "con la sede corregida--. La corrección usa una razón media: "
                        "un equipo cuyo medio campo cambie mucho entre casa y fuera "
                        "queda peor descrito que uno regular.",
                        "Los ratings del rival se piden en el momento. Si Hattrick no "
                        "responde, la pantalla cae al modelo simple por TSI y lo dice.",
                        "La muestra de amistosos no es equivalente a las otras dos: "
                        "durante su ajuste el modelo no vio ni un solo amistoso.",
                    ],
                ),
                Calculo(
                    id="pronostico-duelo",
                    name="3 · El duelo, la unidad de medida",
                    answers=(
                        "Por qué los ratings se comparan cruzados y en proporción, y "
                        "cuánto pesa cada uno de los nueve duelos."
                    ),
                    body=[
                        "Un rating suelto no dice nada. Un ataque de 12 es excelente "
                        "contra una defensa de 6 y es poca cosa contra una de 20. Lo "
                        "que predice goles no es tu número, es la RELACIÓN entre tu "
                        "número y el suyo. Por eso la unidad de medida del motor no es "
                        "un rating: es un duelo.",
                        "Los duelos van CRUZADOS, como en el campo. Tu ataque por la "
                        "izquierda corre por el mismo carril físico que defiende el "
                        "lateral derecho del rival, así que ése es su oponente natural "
                        "y no su defensa izquierda. Mirando una tabla de coeficientes "
                        "esto no se adivina, y sin decirlo la mitad de las filas "
                        "parecen mal emparejadas.",
                        "Cada duelo se mide como p = A / (A + B), donde A es tu rating "
                        "y B el suyo. Es la fracción del duelo que te llevas: 0,5 es "
                        "igualdad exacta, 0,7 es dominio claro, 0,3 es estar dominado. "
                        "Se eligió una proporción y no una diferencia porque la "
                        "diferencia no escala: cinco puntos de ventaja no valen lo "
                        "mismo partiendo de 10 que partiendo de 60. La proporción sí "
                        "conserva su significado a cualquier nivel.",
                        "También se probó a MULTIPLICAR en vez de sumar. La objeción es "
                        "buena: en Hattrick el medio campo no es un sector más, decide "
                        "la posesión, y la posesión debería multiplicar tus ataques en "
                        "vez de sumarse a ellos. Se probaron 42 estructuras --seis "
                        "maneras de medir un duelo por siete multiplicadores de "
                        "posesión, todas con los mismos parámetros y los mismos cortes-- "
                        "y ninguna le gana a sumar.",
                        "Lo que dicen esas 42 juntas es más informativo que el ganador: "
                        "cuanto más agresivo el multiplicador, peor predice, y eso pasa "
                        "en las seis familias a la vez. El efecto multiplicativo, si "
                        "existe, es tan flojo que la mejor aproximación es no tenerlo. "
                        "Tiene sentido: el medio campo ya entra por su propio "
                        "coeficiente, que es con diferencia el mayor de los nueve, y "
                        "eso ya recoge casi todo lo que la posesión explica.",
                    ],
                    formula=(
                        "p = A / (A + B)        A = tu rating,  B = el suyo\n"
                        "\n"
                        "los nueve cruces:\n"
                        "    tu medio campo        ↔  su medio campo\n"
                        "    tu ataque izquierdo   ↔  su defensa DERECHA\n"
                        "    tu ataque central     ↔  su defensa central\n"
                        "    tu ataque derecho     ↔  su defensa IZQUIERDA\n"
                        "    tu defensa izquierda  ↔  su ataque DERECHO\n"
                        "    tu defensa central    ↔  su ataque central\n"
                        "    tu defensa derecha    ↔  su ataque IZQUIERDO\n"
                        "    tu balón parado ata.  ↔  su balón parado def.\n"
                        "    tu balón parado def.  ↔  su balón parado ata."
                    ),
                    sources=[
                        Fuente(
                            "Los nueve ratings de cada lado",
                            "El resumen del paso anterior",
                        ),
                        Fuente(
                            "Qué carril enfrenta a cuál",
                            "La geometría del campo: las bandas se cruzan",
                        ),
                        Fuente(
                            "El peso de cada duelo",
                            f"Una regresión ordinal sobre {_miles(OBSERVACIONES)} partidos",
                        ),
                    ],
                    constants=[
                        Constante("p", "de 0 a 1", "Qué parte del duelo te llevas."),
                        Constante("p = 0,5", "igualdad", "Los dos ratings son iguales."),
                    ],
                    tables=[_tabla_de_duelos()],
                    steps=[
                        "Tu medio campo (promedio) es 9,5; el suyo, 14,5.",
                        "p(medio) = 9,5 / (9,5 + 14,5) = 0,3958. Te llevas el 40 % de ese duelo.",
                        "Tu ataque izquierdo es 12,0 y su defensa DERECHA es 13,0: "
                        "p = 12 / 25 = 0,4800.",
                        "Tu ataque central 10,0 contra su defensa central 11,0: p = 0,4762.",
                        "Tu ataque derecho 11,0 contra su defensa IZQUIERDA 12,0: p = 0,4783.",
                        "Tu balón parado ofensivo 8,0 contra su defensivo 7,0: "
                        "p = 0,5333. Es el único duelo que ganas.",
                        "Y así los nueve. Ese vector de nueve proporciones es lo que "
                        "entra en los dos modelos.",
                    ],
                    limits=[
                        "La proporción trata un 12 contra 6 igual que un 40 contra 20. "
                        "Es deliberado --así escala-- pero significa que el modelo no "
                        "distingue el nivel absoluto de un partido.",
                        "Un rating de 0 se trata como «no se sabe», no como «malísimo»: "
                        "se le pone un suelo antes de operar, porque elevado a una "
                        "potencia hundiría los goles del equipo entero. En los partidos "
                        "medidos el mínimo real de cualquier rating va de 1 a 5, así "
                        "que ese suelo no toca ningún dato de verdad.",
                        "Los nueve duelos se suman, no se multiplican. Está medido "
                        "contra 42 alternativas, pero sigue siendo una simplificación "
                        "de cómo funciona la posesión.",
                    ],
                ),
                Calculo(
                    id="pronostico-goles",
                    name="4 · De los duelos a los goles",
                    answers=(
                        "La ecuación central: cómo cinco duelos se convierten en el "
                        "número de goles que se espera de un equipo."
                    ),
                    body=[
                        "Aquí está el corazón del motor. Se llama regresión de Poisson "
                        "y es el instrumento estándar para modelar CONTEOS: cosas que "
                        "sólo pueden ser 0, 1, 2, 3... como los goles de un partido. En "
                        "vez de predecir el número exacto, estima λ (lambda), el "
                        "promedio de goles que cabe esperar de ese equipo en ese "
                        "partido. Con λ ya se puede calcular la probabilidad de marcar "
                        "exactamente 0, exactamente 1, exactamente 2.",
                        "Se ajusta una fila por LADO, no por partido: cada partido "
                        "aporta dos observaciones, la del local y la del visitante, "
                        "cada una con sus propios duelos y sus propios goles. Entran "
                        "cinco duelos: el medio campo --que da el balón-- los tres "
                        "carriles de ataque y el balón parado ofensivo. Los duelos "
                        "DEFENSIVOS no entran, y no por olvido: ya están dentro, porque "
                        "cada duelo de ataque se mide contra la defensa del rival en "
                        "ese carril. Meterlos otra vez sería contarlos dos veces.",
                        "EL MEDIO CAMPO MULTIPLICA. Una regresión de Poisson usa "
                        "enlace logarítmico, o sea que modela log(λ) como una suma; si "
                        "el duelo entra en logaritmo, por fuera queda multiplicando, y "
                        "su coeficiente es una elasticidad: el porcentaje que crecen los "
                        "goles cuando ese duelo crece un uno por ciento. Así entra el "
                        "medio campo, que es quien da el balón.",
                        "LOS TRES CARRILES DE ATAQUE, EN CAMBIO, SE PROMEDIAN "
                        "(2026-09-12). Hasta esa fecha se multiplicaban entre sí, y eso "
                        "decía que un carril tapado hunde el ataque entero por fuertes "
                        "que sean los otros dos. Hattrick no juega así: reparte las "
                        "ocasiones POR carril, y si uno está cerrado se ataca por otro. "
                        "Ahora los tres entran como una media ponderada --30 % por cada "
                        "banda, 40 % por el centro, que es como se reparten los "
                        "ataques-- con cada carril elevado a un exponente común. Ese "
                        "exponente es la pregunta de fondo: cerca de cero harían falta "
                        "los tres a la vez, que es exactamente la forma vieja como caso "
                        "límite; cuanto más alto, más manda el carril mejor. Sale 3,39.",
                        "NO SE ELIGIÓ, SE MIDIÓ. Sobre los mismos 5.232 partidos de "
                        "liga, con validación cruzada de diez pliegues y comparando "
                        "partido a partido, la forma nueva gana a la vieja en las dos "
                        "cosas que se pueden medir: el resultado (p = 0,014) y los goles "
                        "(p < 0,001). Se probó además dejar al centro su propio "
                        "exponente, distinto del de las bandas, y no mejora "
                        "(p = 0,097): los tres comparten uno, que es lo que manda un "
                        "campo simétrico.",
                        "EL BALÓN PARADO VA APARTE, en su propio sumando, y ésta fue la "
                        "última corrección del modelo. Cuando todo era un solo producto, "
                        "el medio campo multiplicaba también la amenaza a balón parado: "
                        "un equipo que perdía el mediocampo veía hundida hasta su "
                        "peligro en los córners. Eso no se sostiene --una falta o un "
                        "córner no dependen de la posesión como una jugada elaborada-- "
                        "y los datos lo confirmaron. Ahora son dos sumandos, y como la "
                        "suma de dos Poisson sigue siendo Poisson, el modelo de conteo "
                        "no cambia. Lo que cambia es que el balón parado tiene su "
                        f"propia dependencia del medio campo: {_coma(POISSON_BP_MEDIO)} "
                        f"contra {_coma(POISSON_JUEGO_MEDIO)}, tres veces menos. No es "
                        "cero --se probó, y sale peor: los córners salen de atacar, y "
                        "para atacar hace falta el balón--, lo que no se sostenía era "
                        "que dependieran TANTO. De media el reparto queda en 72 % juego "
                        "abierto y 28 % balón parado.",
                        "LA DESCOMPRESIÓN es el término elevado al cuadrado, y merece "
                        "su párrafo. Un producto de potencias limpio apretaba las "
                        "lambdas hacia el centro: donde prometía 0,76 goles se marcaban "
                        "0,68, y donde prometía 3,30 se marcaban 3,55. Eso llenaba la "
                        "rejilla de marcadores bajos --sobraban 233 partidos en el "
                        "bloque de cero y un gol-- y de ahí salían 115 empates de más. "
                        "No era un problema de escala, porque la regresión ya tenía la "
                        "mejor recta posible y una pendiente libre habría salido 1 por "
                        "construcción: era de CURVATURA, y se corrige con el cuadrado "
                        "del propio predictor. Tampoco era el efecto que uno probaría "
                        "primero para un exceso de empates --la dependencia entre los "
                        "goles de los dos equipos-- porque ésa se midió y sale "
                        "prácticamente nula, y además conserva los totales: sólo "
                        "reparte masa DENTRO del bloque de marcadores bajos, nunca la "
                        "saca de él, que era justo lo que hacía falta.",
                        "EL TOPE es un seguro, no un ajuste. El coeficiente cuadrático "
                        "es negativo, así que la parábola tiene vértice: pasado ese "
                        "punto la fórmula daría la vuelta y un equipo más fuerte "
                        f"marcaría MENOS. El vértice cae en {_coma(POISSON_JUEGO_ETA_MAXIMA)} "
                        "y el máximo observado en la muestra es 3,465, así que hay poco "
                        "margen: en cuanto aparezca un equipo algo más fuerte que los "
                        "del ajuste, el tope entra. Recortando ahí, el juego abierto se "
                        "queda plano en su máximo en vez de bajar. No es un valor "
                        "escrito a mano: se deriva del propio coeficiente cuadrático, "
                        "para que se mueva con él si algún día se reajusta.",
                        "NO HAY TÉRMINO DE VENTAJA LOCAL, y se volvió a comprobar con "
                        "esta forma: sale +0,0149 con p = 0,33, o sea indistinguible de "
                        "cero, y el criterio de información empeora al añadirlo. Tiene "
                        "explicación: la ventaja de campo ya vive DENTRO de los "
                        "ratings, porque el medio campo del local es de media un 19 % "
                        "más alto. Sumarla otra vez sería contarla dos veces.",
                    ],
                    formula=(
                        "p(x)  = duelo x, medido como A/(A+B)\n"
                        "\n"
                        f"η     = {_exacto(POISSON_JUEGO_INTERCEPTO)}\n"
                        f"        + {_exacto(POISSON_JUEGO_MEDIO)} × log p(medio)\n"
                        f"        + log [ 0,3 × p(ata.izq)^{_exacto(POISSON_JUEGO_CARRIL)}\n"
                        f"                + 0,4 × p(ata.cen)^{_exacto(POISSON_JUEGO_CARRIL)}\n"
                        f"                + 0,3 × p(ata.der)^{_exacto(POISSON_JUEGO_CARRIL)} ]\n"
                        "\n"
                        f"η     ← min(η, {_fmt(POISSON_JUEGO_ETA_MAXIMA)})"
                        "        ← el tope del vértice\n"
                        "\n"
                        "juego abierto = exp( η "
                        f"{_con_signo(POISSON_JUEGO_CUADRATICO)} × (η − "
                        f"{_exacto(POISSON_ETA_MEDIA)})² )\n"
                        "\n"
                        f"balón parado  = exp( {_exacto(POISSON_BP_INTERCEPTO)}\n"
                        f"                     + {_exacto(POISSON_BP_MEDIO)} × log p(medio)\n"
                        f"                     + {_exacto(POISSON_BP_BALON_PARADO)}"
                        " × log p(bal.parado ata.) )\n"
                        "\n"
                        "λ     = ( juego abierto + balón parado ) × f(táctica)\n"
                        "\n"
                        "        f(táctica) corrige lo que el rating no ve;\n"
                        "        vale 1 si no se sabe qué se va a jugar.\n"
                        "        Se explica en el paso siguiente.\n"
                        "\n"
                        f"        (tope de seguridad: {_coma(MAXIMO_GOLES_ESPERADOS)})"
                    ),
                    sources=[
                        Fuente(
                            "Los cinco duelos ofensivos",
                            "El paso anterior: medio campo, tres ataques y balón parado",
                        ),
                        Fuente(
                            "Los siete coeficientes",
                            f"Una regresión de Poisson sobre {_miles(2 * OBSERVACIONES)} "
                            f"lados de {_miles(OBSERVACIONES)} partidos de liga",
                        ),
                    ],
                    constants=[
                        Constante(
                            "tope de goles",
                            _coma(MAXIMO_GOLES_ESPERADOS),
                            "Seguro contra un rating absurdo: la exponencial no tiene freno.",
                        ),
                        Constante(
                            "vértice del juego abierto",
                            _fmt(POISSON_JUEGO_ETA_MAXIMA),
                            "Donde la parábola daría la vuelta. Se deriva, no se teclea.",
                        ),
                    ],
                    tables=[_tabla_de_poisson()],
                    steps=[
                        "Tus cinco duelos: medio 0,3958 · ataques 0,4800, 0,4762 y "
                        "0,4783 · balón parado 0,5333.",
                        "log p(medio) = log 0,3958 = −0,9268.",
                        "La media de los carriles: 0,3 × 0,4800^3,38551 + 0,4 × "
                        "0,4762^3,38551 + 0,3 × 0,4783^3,38551 = 0,0822, y su logaritmo "
                        "−2,4992.",
                        "η = 4,75262 + 2,51368 × (−0,9268) + (−2,4992) = −0,0763. Está "
                        "muy por debajo del vértice, así que el tope no actúa.",
                        "Juego abierto = exp(−0,0763 − 0,14746 × (−0,0763 − 0,35161)²) = "
                        "0,902 goles.",
                        "Balón parado = exp(2,38119 + 0,84696 × (−0,9268) + 3,18660 × "
                        "log 0,5333) = 0,666 goles.",
                        "λ tuya = 0,902 + 0,666 = 1,567 goles esperados.",
                    ],
                    limits=[
                        "El coeficiente del balón parado NO se puede leer literalmente. "
                        "Ese duelo comparte el 62 % de su varianza con los de ataque, "
                        "así que buena parte de lo que mide es «este equipo es bueno», "
                        "no «los córners valen esto». Al quitarlo, el medio campo y los "
                        "ataques suben a absorberlo, que es la firma de una variable "
                        "colineal. Sigue en el modelo porque quitarlo empeora mucho la "
                        "predicción, pero su número no es una lección de táctica.",
                        "El vértice queda a 0,28 del máximo observado en el ajuste. Con "
                        "un equipo bastante más fuerte que cualquiera de la muestra, el "
                        "tope entra y el juego abierto se queda plano: el modelo deja "
                        "de distinguir entre «muy fuerte» y «aún más fuerte».",
                        "El término cuadrático es una corrección empírica de curvatura. "
                        "Arregla un sesgo medido, pero no sale de ninguna teoría de "
                        "cómo se marcan goles.",
                        "No hay ventaja local. Está comprobado que aquí no hace falta "
                        "--ya vive dentro de los ratings-- pero si Hattrick cambiara "
                        "cómo la reparte, esto habría que volver a medirlo.",
                    ],
                    note=(
                        "Medido fuera de muestra sobre los 5.232 partidos de liga, con "
                        "validación cruzada de diez pliegues: esta forma predice mejor "
                        "que la anterior tanto el resultado como los goles, y la mejora "
                        "sobrevive a compararla partido a partido en vez de por "
                        "promedios."
                    ),
                ),
                Calculo(
                    id="pronostico-tactica",
                    name="5 · La táctica, que el rating no ve",
                    answers=(
                        "Por qué un equipo que presiona marca menos de lo que promete "
                        "su mediocampo, y cómo se corrige sin saber qué va a jugar."
                    ),
                    body=[
                        "Hasta aquí el modelo mira nueve números por equipo y nada más. "
                        "Esos nueve resumen CON QUÉ se juega, no CÓMO. Y el cómo deja "
                        "huella: midiendo los goles que el modelo prometía contra los "
                        "que se marcaron, separados por la táctica que cada lado usó, "
                        "aparecen desvíos que no son ruido.",
                        "EL MÁS GRANDE ES PRESIONAR. En los 287 lados que presionaron, "
                        "el modelo prometía 2,00 goles y se marcaron 1,45: medio gol de "
                        "más, sistemáticamente. Tiene sentido futbolístico --presionar "
                        "recorta ocasiones a los dos equipos-- y es justo lo que un "
                        "rating no puede contar, porque el rating describe la fuerza, "
                        "no el ritmo al que se juega. En la otra dirección van "
                        "Contraataques, Jugar creativamente y Atacar por las bandas: "
                        "los tres marcan algo más de lo previsto.",
                        "LA CORRECCIÓN ES UN FACTOR, no un término más de la regresión. "
                        "Cada táctica multiplica la lambda de quien la juega. Se eligió "
                        "así por tres razones: no toca la forma de la Poisson --un "
                        "múltiplo de una Poisson sigue siendo una Poisson--, su máxima "
                        "verosimilitud tiene forma cerrada, y se puede apagar poniendo "
                        "el factor en 1 sin que nada más cambie.",
                        "EL ESTIMADOR es la suma de goles observados dividida por la "
                        "suma de lambdas de esa táctica. No es una heurística: es "
                        "exactamente el máximo de la verosimilitud de un factor "
                        "multiplicativo en un modelo de Poisson. Con ese valor, cada "
                        "grupo queda insesgado por construcción, y como los grupos "
                        "cubren todos los partidos, el modelo entero sigue insesgado.",
                        "EL PROBLEMA DE VERDAD NO ES ESTIMARLO, ES SABER QUÉ TÁCTICA SE "
                        "VA A JUGAR. Los factores se miden con partidos ya jugados, "
                        "donde la táctica es historia conocida; pero para PREDECIR hay "
                        "que adivinarla. Y aquí hay dos situaciones muy distintas.",
                        "TU LADO NO SE ADIVINA. Si ya mandaste la alineación, tu táctica "
                        "viene con ella y se aplica el factor exacto. La mitad del "
                        "problema desaparece sin coste.",
                        "LA DEL RIVAL SE PONDERA, NO SE APUESTA. Lo natural sería "
                        "tomar su táctica más frecuente, pero eso castiga dos veces "
                        "cuando se falla: no corriges la que jugó y corriges de más una "
                        "que no jugó. En su lugar se toma el REPARTO de sus tácticas "
                        "recientes y se promedian los factores pesados por su "
                        "frecuencia, que es la esperanza del factor cuando la táctica "
                        "es incierta. Medido, eso recupera la mitad del sesgo en vez de "
                        "un tercio.",
                        "CUÁNTO SE RECUPERA, medido fuera de muestra con validación "
                        "cruzada de diez pliegues sobre los partidos de liga: apostando "
                        "por la táctica más frecuente se corrige el 35 % del sesgo; "
                        "ponderando por el reparto, el 50 %; y sabiendo la propia y "
                        "ponderando la del rival, el 80 %. El 100 % sería saber las dos "
                        "de antemano, que no se puede.",
                        "POR QUÉ NO SE LLEGA AL 100 %. La táctica habitual acierta la "
                        "real el 92 % de las veces, pero ese número engaña: acierta "
                        "casi siempre en Normal --que es el 78 % de los casos y donde no "
                        "había nada que corregir-- y falla justo en las especiales, que "
                        "son las que tienen sesgo. Presionar sólo se adivina el 62 % de "
                        "las veces, y Contraataques el 67 %.",
                        "QUÉ PASA CUANDO NO HAY INFORMACIÓN. Sin partidos previos del "
                        "rival, el factor es 1 y el modelo se comporta exactamente como "
                        "antes de que esto existiera. Una táctica que Hattrick añadiera "
                        "mañana tampoco rompería nada: sin factor medido, factor 1.",
                    ],
                    formula=(
                        "factor de una táctica t, del ajuste:\n"
                        "    d(t) = Σ goles observados con t  /  Σ λ predichas con t\n"
                        "\n"
                        "al predecir, el factor de un lado:\n"
                        "    si se sabe su táctica     f = d(táctica)\n"
                        "    si no                     f = Σ  π(t) × d(t)\n"
                        "                                  t\n"
                        "    donde π(t) es cuántas veces usó t en lo visto\n"
                        "    y sin ningún dato         f = 1\n"
                        "\n"
                        "y entra multiplicando:\n"
                        "    λ = ( juego abierto + balón parado ) × f"
                    ),
                    sources=[
                        Fuente(
                            "Qué táctica usó cada equipo en cada partido",
                            "El detalle del partido, que la publica para los dos lados",
                        ),
                        Fuente(
                            "El reparto de tácticas del rival",
                            "Sus partidos vistos, los mismos que alimentan el resumen",
                        ),
                        Fuente(
                            "Tu táctica del próximo partido",
                            "Las órdenes que ya mandaste, si las mandaste",
                        ),
                    ],
                    constants=[
                        Constante(
                            "sesgo de Presionar, antes",
                            "+0,56 goles",
                            "Lo que el modelo prometía de más en cada lado que presionaba.",
                        ),
                        Constante(
                            "sesgo de Presionar, después",
                            "+0,11 goles",
                            "Lo que queda con la táctica propia sabida y la del rival ponderada.",
                        ),
                        Constante(
                            "sesgo recuperado",
                            "80 %",
                            "Fuera de muestra. Sería 100 % sabiendo las dos tácticas.",
                        ),
                        Constante(
                            "lados que corrige",
                            "22 %",
                            "Los que jugaron una táctica distinta de Normal.",
                        ),
                    ],
                    tables=[_tabla_de_tacticas()],
                    steps=[
                        "Se mira qué táctica jugó cada lado en cada partido del ajuste.",
                        "Por cada táctica se suman los goles marcados y las lambdas que "
                        "el modelo había predicho, y se dividen: ése es su factor.",
                        "Al predecir, tu factor sale de tu táctica si mandaste órdenes, "
                        "y si no, del reparto de las tuyas recientes.",
                        "El del rival sale siempre del reparto de las suyas: se "
                        "promedian los factores pesados por cuántas veces usó cada una.",
                        "Cada lambda se multiplica por el factor de SU lado antes de "
                        "construir la rejilla de marcadores.",
                    ],
                    limits=[
                        "La táctica del rival se estima, no se sabe. Se acierta el 92 % "
                        "de las veces en conjunto, pero sólo el 62 % cuando presiona, "
                        "que es justo el caso que más corrección necesitaba.",
                        "Los factores salen de partidos de LIGA. En copa se aplican "
                        "igual, y eso es una extrapolación: no hay muestra suficiente "
                        "para medirlos allí por separado.",
                        "Tiros lejanos se midió con 70 lados, así que su factor es poco "
                        "más que ruido. Está tan cerca de 1 que aplicarlo apenas mueve "
                        "nada, y por eso se deja.",
                        "La corrección endereza los GOLES esperados. En las tres "
                        "probabilidades del resultado la mejora existe pero es pequeña, "
                        "y no llega a ser concluyente en la prueba pareada.",
                        "El factor es el mismo para un equipo que presiona bien y uno "
                        "que presiona mal. Mide el efecto MEDIO de la táctica, no cómo "
                        "la ejecuta cada club.",
                    ],
                    note=(
                        "Esta corrección se añadió el 2026-09-12. Antes el motor "
                        "ignoraba la táctica por completo, y eso está medido: el sesgo "
                        "que arrastraba en Presionar era de medio gol por partido."
                    ),
                ),
                Calculo(
                    id="pronostico-rejilla",
                    name="6 · Del gol al marcador, y del marcador al resultado",
                    answers=(
                        "Cómo dos números de goles esperados se convierten en las tres "
                        "probabilidades de la barra."
                    ),
                    body=[
                        "Con las dos lambdas ya no hace falta más estadística: lo que "
                        "queda es aritmética. La distribución de Poisson dice qué "
                        "probabilidad tiene un equipo con promedio λ de marcar "
                        "exactamente k goles. Aplicándola a las dos lambdas se tienen "
                        "dos listas de probabilidades: la tuya de marcar 0, 1, 2... y "
                        "la suya.",
                        "Se supone que los dos marcadores son INDEPENDIENTES, así que "
                        "la probabilidad de un resultado concreto es el producto de sus "
                        "dos casillas: la de un 2-1 es «tú marcas 2» por «él marca 1». "
                        "Multiplicando las dos listas se obtiene una rejilla completa "
                        f"de marcadores, hasta {TOPE_DE_GOLES} goles por lado, más allá "
                        "de lo cual la probabilidad es despreciable.",
                        "La independencia es un supuesto, y en fútbol real se sabe que "
                        "no es del todo cierto: los partidos donde marca uno tienden a "
                        "ser partidos donde marca el otro. Se midió esa dependencia en "
                        "la muestra y sale prácticamente nula, así que aquí el supuesto "
                        "no cuesta nada. La corrección clásica para eso quedó descartada "
                        "por la misma razón: además de innecesaria, conserva los "
                        "totales, y el problema que había --exceso de marcadores bajos-- "
                        "exigía sacar masa del bloque, no repartirla dentro.",
                        "Sumando las casillas de la rejilla en tres montones salen las "
                        "tres probabilidades: por debajo de la diagonal ganas, en la "
                        "diagonal empatas, por encima pierdes. El «resultado más "
                        "probable» que enseña la pantalla es simplemente la casilla "
                        "individual más alta, y conviene no confundirlo con el "
                        "resultado esperado: casi nunca pasa del 12 % de probabilidad.",
                        "EN COPA NO HAY EMPATE. Hay prórroga y penaltis, y alguien "
                        "pasa. Así que en las pantallas de copa la probabilidad de "
                        "empate se reparte entre los dos equipos en proporción a lo que "
                        "ya tienen, y la barra se pinta con dos tramos en vez de tres. "
                        "No es una suposición: de 861 partidos de copa recogidos, cero "
                        "empates.",
                    ],
                    formula=(
                        "P(k goles | λ) = λ^k × e^(−λ) / k!         ← Poisson\n"
                        "\n"
                        "rejilla:  P(i, j) = P(i | λ_tuya) × P(j | λ_suya)\n"
                        f"          para i y j de 0 a {TOPE_DE_GOLES}\n"
                        "\n"
                        "P(victoria) = Σ P(i, j) con i > j\n"
                        "P(empate)   = Σ P(i, i)\n"
                        "P(derrota)  = Σ P(i, j) con i < j\n"
                        "\n"
                        "en copa:    P(victoria) ← P(victoria) + P(empate) × parte proporcional\n"
                        "            P(empate)   ← no se pinta"
                    ),
                    sources=[
                        Fuente(
                            "Los goles esperados de cada lado",
                            "El paso anterior, aplicado dos veces",
                        ),
                        Fuente(
                            "Que en copa no hay empate",
                            "Las reglas del torneo, confirmadas en 861 partidos de copa",
                        ),
                    ],
                    constants=[
                        Constante(
                            "goles por lado en la rejilla",
                            str(TOPE_DE_GOLES),
                            "Hasta dónde se reparte la probabilidad. Más allá es despreciable.",
                        ),
                    ],
                    steps=[
                        "λ tuya = 1,633 y λ suya = 2,641, del paso anterior.",
                        "Tu probabilidad de marcar 0 goles es e^(−1,633) = 0,195; de "
                        "marcar 1, 0,318; de marcar 2, 0,260.",
                        "La suya de marcar 0 es 0,071; de marcar 1, 0,188; de marcar 2, 0,248.",
                        "La casilla del 1-2 vale 0,318 × 0,248 = 0,079, y resulta ser "
                        "la más alta de toda la rejilla: ése es el «resultado más "
                        "probable», con menos del 8 % de probabilidad.",
                        "Sumando los tres montones: victoria 22,7 %, empate 18,0 %, "
                        "derrota 59,3 %.",
                        "Si el partido fuera de copa, ese 18,0 % de empate se repartiría "
                        "entre los dos y quedaría 27,7 % contra 72,3 %.",
                    ],
                    limits=[
                        "Se supone que los goles de los dos equipos son independientes. "
                        "Está medido y aquí se sostiene, pero es un supuesto.",
                        "El «resultado más probable» es la casilla más alta, no una "
                        "predicción: rara vez pasa del 12 % de probabilidad. Se enseña "
                        "porque orienta, no porque vaya a ocurrir.",
                        "El reparto del empate en copa es proporcional, que es lo "
                        "razonable sin más información. No modela la prórroga ni los "
                        "penaltis, donde influyen cosas --resistencia, cambios-- que el "
                        "motor no mira.",
                    ],
                ),
                Calculo(
                    id="pronostico-mezcla",
                    name="7 · La segunda opinión, y cuánto pesa",
                    answers=(
                        "Por qué hay un segundo modelo mirando los mismos duelos, y por "
                        "qué la mezcla es 80/20 y no otra cosa."
                    ),
                    body=[
                        "El modelo de goles no es el único que mira estos duelos. Hay "
                        "un segundo, una regresión logística ORDINAL, que aprende de "
                        "otra cosa: no de cuántos goles se marcaron, sino de quién "
                        "ganó. Recibe los NUEVE duelos --incluidos los tres defensivos, "
                        "que el de goles no usa-- los combina en un solo número, y "
                        "parte la recta en tres tramos con dos umbrales: por debajo del "
                        "primero, derrota; entre los dos, empate; por encima del "
                        "segundo, victoria.",
                        "«Ordinal» significa que respeta el orden natural del "
                        "resultado: derrota < empate < victoria. No son tres categorías "
                        "sueltas, son tres tramos de una misma escala, y el modelo lo "
                        "sabe. Por eso hay dos umbrales y no dos modelos separados, y "
                        "por eso los coeficientes de la tabla del paso 3 son los de esa "
                        "escala.",
                        "Los dos modelos miran los mismos partidos y se equivocan en "
                        "sitios distintos. El de goles discrimina un poco mejor y es el "
                        "único que sabe de marcadores; el ordinal calibra mejor el "
                        "empate y es el único que mira los duelos DEFENSIVOS de forma "
                        "directa. Promediarlos es la forma más barata que existe de "
                        "quedarse con lo mejor de cada uno, y funciona: juntos aciertan "
                        "más que cualquiera de los dos por separado.",
                        "El peso se eligió barriendo todos los valores y mirando dos "
                        "cosas a la vez, no una. La primera es el error de predicción. "
                        "La segunda, y es la que manda, es la CALIBRACIÓN del empate: "
                        "que cuando el motor dice 25 % de empate, empaten cerca del "
                        "25 % de las veces. La curva de error es planísima entre 0,60 y "
                        "0,90 --cuatro diezmilésimas separan cuatro puntos-- así que el "
                        "mínimo por sí solo no decidía nada; lo que decide es que a "
                        "partir de 0,90 el empate se sale de su banda. 0,80 es a la vez "
                        "el mínimo y el último punto que todavía calibra.",
                        "Conviene decir de dónde viene ese 80. Estuvo en 75/25 y luego "
                        "en 60/40, con el modelo de goles anterior. Subió hasta aquí "
                        "porque el modelo de goles mejoró mucho al partirlo en dos "
                        "componentes y descomprimirlo: pasó de 0,6559 a 0,6334 de "
                        "error, mientras el ordinal se queda en 0,6445. El peso siguió "
                        "a la mejora, no al revés.",
                    ],
                    formula=(
                        "z = Σ βᵢ × pᵢ                    los NUEVE duelos\n"
                        "\n"
                        f"P(derrota)  = σ({_exacto(UMBRALES[0])} − z)\n"
                        f"P(empate)   = σ({_exacto(UMBRALES[1])} − z) − P(derrota)\n"
                        f"P(victoria) = 1 − σ({_exacto(UMBRALES[1])} − z)\n"
                        "\n"
                        "σ(t) = 1 / (1 + e^(−t))          la función logística\n"
                        "\n"
                        f"final = {PESO_GOLES:.2f} × (lo del paso 5) "
                        f"+ {PESO_ORDINAL:.2f} × (lo de aquí)"
                    ),
                    sources=[
                        Fuente(
                            "Los nueve duelos",
                            "El paso 3, esta vez los nueve y no sólo los ofensivos",
                        ),
                        Fuente(
                            "Los nueve coeficientes y los dos umbrales",
                            f"Una regresión ordinal sobre {_miles(OBSERVACIONES)} partidos de liga",
                        ),
                        Fuente(
                            "El peso de la mezcla",
                            "Un barrido completo, con la calibración del empate como corte",
                        ),
                    ],
                    constants=[
                        Constante(
                            "umbral derrota / empate",
                            _exacto(UMBRALES[0]),
                            "Por debajo de este punto de la escala, derrota.",
                        ),
                        Constante(
                            "umbral empate / victoria",
                            _exacto(UMBRALES[1]),
                            "Por encima de este punto, victoria.",
                        ),
                        Constante(
                            "peso de los goles",
                            f"{PESO_GOLES:.2f}",
                            "Cuánto manda la Poisson del paso 5.",
                        ),
                        Constante(
                            "peso del ordinal",
                            f"{PESO_ORDINAL:.2f}",
                            "Cuánto corrige la regresión de resultado.",
                        ),
                    ],
                    tables=[_tabla_del_barrido()],
                    steps=[
                        "Con los nueve duelos del ejemplo, z = 17,9526.",
                        "Ese número cae entre los dos umbrales (17,86 y 18,88): el "
                        "ordinal ve un partido de la zona del empate.",
                        "Sus tres probabilidades: victoria 28,4 %, empate 23,8 %, derrota 47,8 %.",
                        "Las del modelo de goles eran 22,7 %, 18,0 % y 59,3 %.",
                        "Victoria final = 0,80 × 22,7 % + 0,20 × 28,4 % = 23,9 %.",
                        "Empate final = 0,80 × 18,0 % + 0,20 × 23,8 % = 19,1 %. "
                        "Derrota, 57,0 %. Eso es lo que se pinta.",
                    ],
                    limits=[
                        "El peso es una decisión, no un parámetro ajustado. Está "
                        "medido, pero elegir 0,80 en vez de 0,70 fue una elección "
                        "declarada.",
                        "Los dos modelos comparten muestra y comparten variables, así "
                        "que sus errores no son independientes: mezclarlos ayuda menos "
                        "de lo que ayudaría combinar dos modelos de verdad distintos.",
                        "El ordinal no sabe nada de goles. En la mezcla sólo corrige "
                        "las tres probabilidades; los goles esperados y el marcador más "
                        "probable que enseña la pantalla salen enteros del paso 5.",
                    ],
                ),
                Calculo(
                    id="pronostico-validacion",
                    name="8 · Cómo se comprobó que funciona",
                    answers=(
                        "Qué se midió, contra qué se comparó y qué salió. Sin esto, "
                        "todo lo anterior son sólo fórmulas."
                    ),
                    body=[
                        "Un modelo que se prueba con los mismos partidos con los que se "
                        "ajustó siempre parece bueno. Así que aquí no se hizo eso: se "
                        "usó ORIGEN MÓVIL, que es la forma honesta de evaluar algo que "
                        "predice el futuro. Se ordenan los partidos por fecha, se corta "
                        "en un punto, se ajusta el modelo SÓLO con lo anterior al corte "
                        "y se predice el tramo siguiente, que el modelo no ha visto "
                        "nunca. Luego se mueve el corte y se repite. Cinco cortes, "
                        "reajustando en cada uno.",
                        "La medida principal es el log-loss, que castiga la confianza "
                        "equivocada: acertar diciendo «60 %» puntúa menos que acertar "
                        "diciendo «90 %», y fallar diciendo «90 %» se paga carísimo. Es "
                        "la métrica correcta cuando lo que se publica son "
                        "probabilidades y no un pronóstico. Menos es mejor.",
                        "El resultado: 0,6328 contra un suelo de 1,0986, que es lo que "
                        "sacaría alguien que dijera siempre «un tercio, un tercio, un "
                        "tercio». Traducido: acierta el 73 % de los partidos contra el "
                        "50 % de acertar siempre lo más común. Y esa ganancia se repitió "
                        "con cuatro esquemas de corte distintos, así que no es un "
                        "artefacto de dónde se puso la raya.",
                        "Pero acertar no basta: hay que estar CALIBRADO. Cuando la "
                        "pantalla dice 70 %, tiene que ocurrir cerca del 70 % de las "
                        "veces, o el número engaña aunque el ranking sea bueno. Se "
                        "comprobó simulando: se generaron dos mil mundos donde el "
                        "modelo es cierto por construcción, se midió cuánto se desvía "
                        "la calibración en esos mundos por puro azar, y se exigió que "
                        "la desviación real cayera dentro de esa banda. Las tres "
                        "clases --victoria, empate y derrota-- pasan.",
                        "LA COPA SE VALIDÓ APARTE ANTES DE CABLEARLA, porque nada "
                        "garantizaba que un modelo ajustado con partidos de liga "
                        "sirviera allí. Sobre los cruces de copa recogidos: log-loss "
                        "0,2106 contra un suelo de 0,5499, área bajo la curva 0,9596 y "
                        "88,4 % de acierto en quién pasa, calibrado y sin necesidad de "
                        "corregir por ventaja de campo. Contra los tres rivales reales "
                        "de copa de esta temporada acertó la dirección en los tres. Es "
                        "mejor que en liga por una razón que no es mérito del modelo: "
                        "en copa el sorteo cruza divisiones distintas, así que muchos "
                        "cruces son desiguales y son fáciles.",
                        "Los goles también se midieron por su cuenta: 0,921 de error "
                        "medio absoluto contra un suelo de 1,573. Y la pendiente de "
                        "calibración de las lambdas, que es lo que la descompresión "
                        "venía a arreglar, quedó en 0,994 sobre un ideal de 1,000.",
                        "LO QUE VE LA PANTALLA ES OTRA COSA, y se midió aparte. Las "
                        "cifras de arriba predicen cada partido con SUS PROPIOS "
                        "ratings: miden cuánto sabe el motor convertir ratings en "
                        "resultados. Pero el partido que viene todavía no tiene "
                        "ratings, así que la pantalla usa el PROMEDIO de los partidos "
                        "anteriores de cada equipo. Con el mismo origen móvil, sobre "
                        "2.773 partidos donde los dos equipos tenían historia: log-loss "
                        "0,6924 y 71,3 % de acierto, contra 0,6177 y 73,6 % con los "
                        "ratings del propio partido y 0,9787 de no saber nada. Esa "
                        "distancia es el precio de no conocer la alineación.",
                        "Entre los resúmenes, el promedio es el que menos se equivoca: "
                        "con la sede corregida, 0,7007 el máximo, 0,7092 el máximo por "
                        "carril y 0,7010 el último partido. El valor central que se "
                        "retiró tampoco lo mejoraba: sin corregir la sede daba 0,7309 "
                        "contra 0,7233 del promedio, que le gana partido a partido con "
                        "p = 0,0003.",
                        "HABÍA UN SESGO CONTRA EL LOCAL, y se corrigió el 2026-09-13. "
                        "Con el promedio sin más, el motor prometía un 41,5 % de "
                        "victorias locales donde ocurrían un 50,1 %, y un 43,5 % de "
                        "derrotas locales donde ocurrían un 37,2 %: el promedio mezcla "
                        "partidos de casa y de fuera, y la ventaja de campo va dentro de "
                        "los ratings. Corrigiendo la sede --paso 2-- promete un 49,7 % "
                        "y un 35,4 %, y el log-loss baja de 0,7233 a 0,6924, con "
                        "p < 0,000001 en la comparación partido a partido. La "
                        "calibración mejora pero no queda perfecta: el empate se sigue "
                        "prometiendo algo de más, 14,8 % contra 12,7 %.",
                    ],
                    formula=(
                        "origen móvil, 5 cortes, reajustando en cada uno:\n"
                        "    ajusta con  [inicio ............ corte]\n"
                        "    evalúa en             (corte ..... corte + tramo]\n"
                        "\n"
                        "log-loss = − promedio de log P(lo que de verdad pasó)\n"
                        "\n"
                        "calibración: |lo prometido − lo ocurrido|, comparado contra\n"
                        "             el percentil 95 de 2.000 mundos simulados"
                    ),
                    sources=[
                        Fuente(
                            "Los partidos de la evaluación",
                            "Los mismos de liga del ajuste, pero SIEMPRE posteriores al corte",
                        ),
                        Fuente(
                            "Los cruces de copa de la validación",
                            "Partidos de copa reales, con su ganador conocido",
                        ),
                        Fuente(
                            "La banda de calibración",
                            "2.000 mundos simulados donde el modelo es cierto por construcción",
                        ),
                    ],
                    constants=[
                        Constante("cortes de origen móvil", "5", "Cuántas veces se reajustó."),
                        Constante(
                            "log-loss del motor",
                            "0,6328",
                            "Menos es mejor. El suelo de no saber nada es 1,0986.",
                        ),
                        Constante(
                            "acierto",
                            "73 %",
                            "Contra el 50 % de acertar siempre el resultado más común.",
                        ),
                        Constante(
                            "error de goles",
                            "0,921",
                            "Goles de diferencia de media. El suelo es 1,573.",
                        ),
                        Constante(
                            "log-loss en copa",
                            "0,2106",
                            "Sobre pasar o no pasar. El suelo allí es 0,5499.",
                        ),
                        Constante(
                            "con promedio",
                            "0,6924",
                            "Log-loss de lo que ve la pantalla: el partido predicho con "
                            "el promedio de los anteriores y la sede corregida.",
                        ),
                        Constante(
                            "acierto real",
                            "71,3 %",
                            "Con el promedio y la sede. Con los ratings del partido, 73,6 %.",
                        ),
                    ],
                    steps=[
                        "Se ordenan los partidos por fecha y se corta al 40 % de la serie.",
                        "Se ajusta el modelo con el 40 % anterior y se predice el tramo "
                        "siguiente, que no ha visto.",
                        "Se apunta el error de cada predicción contra lo que de verdad pasó.",
                        "Se mueve el corte al 52 %, al 64 %, al 76 % y al 88 %, "
                        "reajustando cada vez.",
                        "Se promedian los cinco tramos: log-loss 0,6328.",
                        "Se repite el ejercicio con otros tres esquemas de corte. Gana "
                        "en los cuatro.",
                        "Aparte, se comprueba la calibración de las tres clases contra "
                        "la banda simulada. Las tres pasan.",
                    ],
                    limits=[
                        "Todo se midió sobre partidos de LIGA de cinco países. Nada "
                        "garantiza que los coeficientes valgan igual en una división "
                        "muy distinta de las de la muestra.",
                        "La validación de copa se hizo sobre cruces de copa reales, "
                        "pero con un modelo ajustado en liga. Que funcione bien no "
                        "significa que la copa se comporte como la liga: significa que "
                        "los duelos siguen ordenando bien a los equipos.",
                        "Un log-loss de 0,6328 es bueno para este problema, no es "
                        "adivinación. Un tercio largo de los partidos sale distinto de "
                        "lo que el modelo consideraba más probable, y eso es normal en "
                        "un deporte con estos marcadores.",
                        "Lo que ve la pantalla se equivoca más que la cifra principal "
                        "--0,6924 contra 0,6177 en los mismos partidos-- porque predice "
                        "sin los ratings del partido. La sede se corrige con una razón "
                        "media, así que un equipo cuyo medio campo cambie mucho entre "
                        "casa y fuera sigue quedando peor descrito.",
                    ],
                ),
                Calculo(
                    id="pronostico-limites",
                    name="9 · Hasta dónde vale",
                    answers=(
                        "Lo que el modelo NO puede hacer, y las dos cosas que conviene "
                        "no leer de más."
                    ),
                    body=[
                        "Esta ficha es la letra pequeña, y es la mitad del valor del "
                        "capítulo. Un motor que sólo publica sus aciertos no es "
                        "transparente, es publicidad.",
                        "EL PRIMER AVISO es sobre el coeficiente del balón parado. Es "
                        "el más grande de los tres de la ecuación de goles, y la "
                        "tentación de leerlo como «los córners deciden los partidos» es "
                        "inmediata. No se sostiene: ese duelo comparte el 62 % de su "
                        "varianza con los de ataque, o sea que los equipos buenos a "
                        "balón parado son en general los equipos buenos. Al quitarlo "
                        "del modelo, el medio campo y los ataques suben a absorber lo "
                        "que medía, que es la firma inconfundible de una variable "
                        "colineal. Se queda porque quitarlo empeora mucho la "
                        "predicción, no porque su número sea una lección de táctica.",
                        "EL SEGUNDO AVISO es sobre el empate. El motor promete de media "
                        "un 14,5 % de empates y en la muestra ocurren un 13,0 %. Está "
                        "dentro de la banda de calibración, pero es un sesgo real y "
                        "conocido: queda un resto del exceso de marcadores bajos que la "
                        "descompresión no llegó a eliminar del todo. Si la barra dice "
                        "que el empate es la opción más gorda, conviene descontarle "
                        "algo mentalmente. Es además la razón por la que la mezcla no "
                        "sube del 80 %: el modelo ordinal es lo que sujeta esa clase.",
                        "Y luego está lo que el motor sencillamente no mira. No conoce "
                        "la alineación del domingo, ni la del rival. No sabe de "
                        "lesiones, sanciones, actitud ni órdenes individuales. No sabe "
                        "si llueve. No sabe si el rival está guardando piernas para la "
                        "copa. Resume cómo SUELE salir un equipo, y eso es lo que "
                        "puede prometer.",
                        "DE LA TÁCTICA SÍ SABE ALGO, desde el 2026-09-12, y conviene "
                        "saber cuánto: corrige los goles por la táctica de cada lado, "
                        "pero la del rival la ESTIMA de lo que viene jugando. Acierta "
                        "el 92 % de las veces en conjunto y sólo el 62 % cuando el "
                        "rival presiona. Si sabes por otra vía que va a cambiar de "
                        "táctica, el modelo no se ha enterado.",
                        "Tampoco enseña el partido más probable: enseña tres "
                        "probabilidades. Que aparezca «0-0» como marcador más probable "
                        "no significa que se espere un 0-0, significa que ninguna otra "
                        "casilla concreta le gana, y casi siempre con menos del 12 %. "
                        "Es una orientación, no un pronóstico.",
                    ],
                    formula=(
                        "lo que el modelo ve:      9 promedios tuyos + 9 del rival\n"
                        "lo que estima:            la táctica de cada lado\n"
                        "                          (la tuya exacta si mandaste órdenes)\n"
                        "lo que el modelo NO ve:   alineación, órdenes individuales,\n"
                        "                          lesiones, sanciones, actitud,\n"
                        "                          forma del día, clima, motivación"
                    ),
                    sources=[
                        Fuente(
                            "El sesgo del empate",
                            "Medido en la propia evaluación: 14,5 % prometido, 13,0 % ocurrido",
                        ),
                        Fuente(
                            "La colinealidad del balón parado",
                            "Medida contra los duelos de ataque en la muestra del ajuste",
                        ),
                    ],
                    constants=[
                        Constante(
                            "empate prometido",
                            "14,5 %",
                            "Lo que el motor dice de media.",
                        ),
                        Constante(
                            "empate ocurrido",
                            "13,0 %",
                            "Lo que pasa de verdad. Calibrado, pero con sesgo conocido.",
                        ),
                        Constante(
                            # Corto a propósito: la primera columna de las
                            # constantes va en `nowrap`, y un símbolo largo
                            # ensancha la tabla hasta sacar la página de la
                            # pantalla en un teléfono. Lo que es se dice al lado.
                            "varianza compartida",
                            "62 %",
                            "La del balón parado con los duelos de ataque: por eso "
                            "su coeficiente no se lee literal.",
                        ),
                    ],
                    steps=[
                        "Si la barra da empate como opción más gorda, réstale algo: el "
                        "motor lo sobreestima en punto y medio.",
                        "Si el coeficiente del balón parado te tienta a fichar un "
                        "especialista, no lo hagas por este número: mide en buena parte "
                        "otra cosa.",
                        "Si el rival acaba de reforzarse, el modelo todavía no lo sabe: "
                        "su promedio es de los partidos anteriores.",
                        "Si vas a rotar, el modelo tampoco lo sabe: describe tu equipo "
                        "típico, no el que vas a alinear. Tu TÁCTICA sí la sabe, si ya "
                        "mandaste las órdenes.",
                        "Y si el marcador más probable te parece raro, mira su "
                        "probabilidad: rara vez llega al 12 %.",
                    ],
                    limits=[
                        "El coeficiente del balón parado no se puede leer literalmente: "
                        "comparte el 62 % de su varianza con los duelos de ataque.",
                        "El motor promete alrededor de un 14,5 % de empates donde "
                        "ocurren un 13,0 %. Calibrado, pero sesgado hacia arriba.",
                        "No conoce alineaciones, órdenes individuales, lesiones, "
                        "sanciones ni actitud. La táctica la estima, y falla cuatro "
                        "de cada diez veces cuando el rival presiona.",
                        "Se ajustó con partidos de liga. En copa está validado aparte; "
                        "con muestra de amistosos es una extrapolación declarada.",
                        "Describe el equipo típico de las últimas jornadas, no el del "
                        "próximo domingo.",
                    ],
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
                            "Los nueve ratings por zona de los ocho equipos",
                            "Sus partidos ya jugados, con el resumen que elijas",
                        ),
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
                        "QUIÉN GANA cada partido que falta\n"
                        "    la terna del motor de zonas, la misma del capítulo\n"
                        "    «Pronóstico de partido»\n"
                        "\n"
                        "    y sólo si a un cruce le faltan ratings de algún lado:\n"
                        "        λ_local   = ataque_i · defensa_j · media_liga · ventaja_local\n"
                        "        λ_visita  = ataque_j · defensa_i · media_liga\n"
                        "\n"
                        "EL MARCADOR, siempre por los goles de la temporada\n"
                        "    fuerza_i  = (goles_i + K · media) ÷ (partidos_i + K)\n"
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
                        "Son DOS motores con dos trabajos, y conviene no confundirlos: "
                        "quién gana cada partido pendiente lo decide el motor de zonas "
                        "--que sí mira los ratings del último partido de cada equipo y "
                        "las tácticas que suele usar--, y el marcador con el que gana "
                        "sale de los goles agregados de la temporada.",
                        "El modelo de goles agregados es el respaldo, y ése sí ignora "
                        "alineaciones y tácticas: entra cuando a un cruce le faltan "
                        "ratings de alguno de los dos lados.",
                        "Ninguno de los dos conoce lesiones, sanciones ni las "
                        "alineaciones que se pondrán el domingo.",
                        "El puesto sale de simular miles de veces, no de una fórmula "
                        "cerrada: dos consultas seguidas del mismo estado dan números "
                        "casi iguales, no idénticos.",
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
                    "body": c.body,
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
