"""Predecir victoria, empate o derrota de un partido que aún no se ha jugado.

QUÉ COMPARA
-----------
Nueve duelos, cada uno enfrentando lo que de verdad se enfrenta en el campo:
tres en mi campo --mi defensa contra su ataque, espejados: mi lateral
izquierdo defiende el mismo carril por el que ataca su extremo DERECHO--,
tres en el suyo, el medio campo contra el medio campo, y el Balón Parado en
los dos sentidos.

Todo como PROPORCIÓN `A/(A+B)`, nunca como resta: los ratings van de 1 a 93 y
una diferencia de 10 no significa lo mismo arriba que abajo, mientras que la
proporción siempre dice «qué parte de este duelo es mía».

POR QUÉ ORDINAL Y NO TRES ETIQUETAS SUELTAS
-------------------------------------------
Victoria, empate y derrota están ORDENADAS. Un modelo multinomial las trata
como tres cosas sin relación y gasta dos juegos completos de coeficientes en
redescubrir por su cuenta que el empate está en medio.

El ordinal lo da por sabido: un solo juego de nueve coeficientes que miden
«cuánto favorece esto al local», y dos umbrales que parten esa recta en tres
tramos. Medido con 1.031 partidos: el mismo ajuste con 11 parámetros que el
multinomial con 20. Los nueve de más no compraban nada.

Lo que cuesta, y hay que decirlo: la franja del empate sale estrecha, así que
este modelo casi nunca dirá que un empate es lo más probable. No es un fallo
de ajuste sino de la forma del modelo. Por eso lo que se enseña son las TRES
probabilidades y de ellas salen los puntos esperados, en vez de un pronóstico
que tiraría dos de las tres a la basura.

La otra consecuencia de tener una sola pendiente es que el modelo se pasa de
confiado en los extremos. Eso sí se corrige, y se corrige con un número: ver
`ESCALA`.

DOS PROBLEMAS, NO UNO
---------------------
1. CÓMO FUNCIONA EL MOTOR de Hattrick: dados unos ratings, ¿qué resultado
   sale? Función fija, la misma para todos los equipos del mundo.
2. QUÉ RATINGS TENDRÁ un equipo el domingo. Eso sí depende del equipo.

El primero se aprende con los ratings DEL PROPIO partido. No hace falta
historia de nadie para medir una función: cada partido es una observación
completa y vale por sí sola, venga de quien venga. Por eso la muestra son
partidos ajenos bajados una vez.

El segundo se resuelve con la MEDIANA de los partidos oficiales recientes.
Mediana y no media porque protege gratis del partido con tres lesionados; en
la cuenta real apenas se diferencian (75,1 contra 75,5) y lo que sí quitó
ruido --de 11,5 a 9,5 de desviación-- fue descartar lo no oficial.

LOS DOS LADOS ENTRAN IGUAL
--------------------------
También el equipo propio, aunque para el propio exista algo mejor: Hattrick
calcula los siete ratings EXACTOS de la alineación ya guardada. No se usa.

`A/(A+B)` deja de ser simétrica si un lado entra afilado y el otro suavizado
por la mediana. Medido en 180 partidos la diferencia es ruido, pero el
síntoma aparece: dar el dato exacto a un lado bajó el AUC de 0,905 a 0,894
--añadir información buena empeoró la discriminación--. Y hay dos razones
mejores que la medida: los ratings exactos describen la alineación que hay
guardada AHORA, que puede ser un borrador y puede cambiar antes del pitido,
mientras que la mediana describe al equipo; y es un solo camino de código.

QUÉ NO ENTRA
------------
La actitud: Hattrick sólo la manda para tu propio equipo, nunca para el rival.

DÓNDE SE AJUSTA
---------------
Aquí no. Los coeficientes salen del ajuste hecho una vez en la máquina del
autor con `scripts/analizar_prediccion.py`; lo que corre en producción sólo
los aplica, que es aritmética. Los 1.031 partidos no viajan al servidor y el
servidor no tiene con qué ajustar nada.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

#: Liga, promoción y copa. Un torneo o un amistoso se juegan con suplentes.
TIPOS_OFICIALES = (1, 2, 3)

#: Los nueve ratings de un lado, en el orden en que se leen de la fila.
CAMPOS = (
    "midfield",
    "left_def",
    "central_def",
    "right_def",
    "left_att",
    "central_att",
    "right_att",
    "sp_def",
    "sp_att",
)

#: Los nueve duelos, en el orden en que viajan en el vector. Cada uno es
#: (nombre, mi campo, su campo) — y los cruces son los del terreno de juego.
COMPARACIONES: tuple[tuple[str, str, str], ...] = (
    ("medio", "midfield", "midfield"),
    ("ata_izq", "left_att", "right_def"),
    ("ata_cen", "central_att", "central_def"),
    ("ata_der", "right_att", "left_def"),
    ("def_izq", "left_def", "right_att"),
    ("def_cen", "central_def", "central_att"),
    ("def_der", "right_def", "left_att"),
    ("bp_def", "sp_def", "sp_att"),
    ("bp_ata", "sp_att", "sp_def"),
)

#: Cómo se llama cada duelo en pantalla. Nunca el nombre del campo.
ETIQUETAS = {
    "medio": "Medio campo",
    "ata_izq": "Mi ataque izquierdo",
    "ata_cen": "Mi ataque central",
    "ata_der": "Mi ataque derecho",
    "def_izq": "Mi defensa izquierda",
    "def_cen": "Mi defensa central",
    "def_der": "Mi defensa derecha",
    "bp_def": "Balón Parado defensivo",
    "bp_ata": "Balón Parado ofensivo",
}

#: Cuánto pesa cada modelo al mezclar. Decisión del usuario, no un peso
#: ajustado: se puede medir cuál acierta más, pero mientras tanto es una
#: opinión declarada y por eso vive en una constante con nombre.
PESO_ZONAS = 0.90
PESO_POISSON = 0.10

#: Partidos previos mínimos para que una mediana signifique algo. Uno.
#:
#: Estaba en tres y se bajó tras medirlo: con los mismos 70 partidos y sólo un
#: partido previo por lado, el log-loss es 0,661 contra un suelo de 1,03 --y
#: contra 0,674 con tres previos, o sea que tres no era mejor--. Exigir tres
#: se negaba a predecir en las jornadas 2 y 3, que es justo cuando más se
#: quiere saber, y no ahorraba nada. Es además lo que hace la pantalla de
#: análisis de rival, que resume con los partidos que haya.
MINIMO_HISTORIA = 1

#: Puntos de la liga. Iguales a los del simulador de temporada; si algún día
#: Hattrick los cambia, se cambian en los dos sitios.
PUNTOS_VICTORIA, PUNTOS_EMPATE = 3, 1


def proporcion(a: float, b: float) -> float:
    """`A/(A+B)`, acotada en [0, 1].

    Con los dos a cero no hay información y devuelve 0,5: decir 0 o 1 sería
    afirmar que gana uno de los dos sin dato que lo sostenga. Pasa de verdad
    cuando faltan los dos ratings de Balón Parado.
    """
    total = a + b
    return a / total if total > 0 else 0.5


def _lado(partido: Any, equipo: int) -> str | None:
    """`home` o `away` según de qué lado jugó ese equipo, o `None`."""
    if partido.home_team_id == equipo:
        return "home"
    if partido.away_team_id == equipo:
        return "away"
    return None


def ratings_de(partido: Any, lado: str) -> dict[str, float]:
    """Los nueve ratings de un lado (`home` o `away`) de un partido jugado."""
    return {c: float(getattr(partido, f"{lado}_{c}")) for c in CAMPOS}


def medianas(
    partidos: Sequence[Any], equipo: int, *, hasta: int | None = None
) -> dict[str, float] | None:
    """La mediana de cada rating del equipo en sus partidos oficiales previos.

    `hasta` es el `ht_match_id` del partido que se evalúa: sólo se miran los
    ANTERIORES. Sirve para comprobar el modelo contra partidos ya jugados sin
    que vea el que intenta predecir; para predecir el domingo no hace falta,
    porque todavía no existe.

    Se ordena por identificador y no por fecha porque los identificadores de
    Hattrick crecen con el tiempo y la fecha puede faltar.
    """
    suyos = [
        p
        for p in partidos
        if p.match_type in TIPOS_OFICIALES
        and _lado(p, equipo) is not None
        and (hasta is None or p.ht_match_id < hasta)
    ]
    if len(suyos) < MINIMO_HISTORIA:
        return None
    suyos.sort(key=lambda p: p.ht_match_id)

    out: dict[str, float] = {}
    for campo in CAMPOS:
        vals = [float(getattr(p, f"{_lado(p, equipo)}_{campo}")) for p in suyos]
        out[campo] = float(np.median(vals))
    out["_partidos"] = float(len(suyos))
    return out


def medianas_de_lecturas(lecturas: Sequence[dict[str, Any]]) -> dict[str, float] | None:
    """Lo mismo, pero desde lecturas ya extraídas de un equipo.

    La pantalla de rivales no devuelve partidos sino los ratings de un equipo,
    un diccionario por partido. Ese es el camino real en producción; `medianas`
    sirve para las comprobaciones contra partidos guardados.

    Un rating que falte cuenta como 0, y entonces la proporción lo neutraliza a
    0,5. Es lo que pasa hoy con el Balón Parado, que aún no se lee de ahí.
    """
    if len(lecturas) < MINIMO_HISTORIA:
        return None
    out = {c: float(np.median([float(r.get(c) or 0) for r in lecturas])) for c in CAMPOS}
    out["_partidos"] = float(len(lecturas))
    return out


def variables(mio: dict[str, float], suyo: dict[str, float]) -> np.ndarray:
    """Las nueve proporciones, en el orden de `COMPARACIONES`."""
    return np.array([proporcion(mio[a], suyo[b]) for _, a, b in COMPARACIONES], dtype=float)


@dataclass(frozen=True)
class Probabilidades:
    victoria: float
    empate: float
    derrota: float

    def __post_init__(self) -> None:
        suma = self.victoria + self.empate + self.derrota
        if abs(suma - 1.0) > 1e-6:
            raise ValueError(f"las tres probabilidades suman {suma}, no 1")

    @property
    def puntos_esperados(self) -> float:
        """Lo que ese partido aporta a la tabla, en promedio.

        No se decide un ganador y se le dan tres puntos: se reparte según lo
        que el modelo cree. Un partido igualadísimo aporta ~1,3 puntos a cada
        uno, que es la verdad, en vez de 3 a uno y 0 al otro, que es una
        moneda al aire disfrazada de pronóstico. Y así el empate cuenta aunque
        nunca llegue a ser el resultado más probable.
        """
        return PUNTOS_VICTORIA * self.victoria + PUNTOS_EMPATE * self.empate


def _sigmoide(z: np.ndarray) -> np.ndarray:
    """Estable en los dos extremos: `exp` de un número grande desborda."""
    salida = np.empty_like(z, dtype=float)
    pos = z >= 0
    salida[pos] = 1.0 / (1.0 + np.exp(-z[pos]))
    e = np.exp(z[~pos])
    salida[~pos] = e / (1.0 + e)
    return salida


@dataclass(frozen=True)
class ModeloOrdinal:
    """Regresión logística ordinal, escrita a mano.

    APLICA, no ajusta. El ajuste se hace una vez en la máquina del autor con
    `statsmodels`, y aquí sólo viven los once números que salieron de ahí. Las
    pruebas comprueban que esta aritmética reproduce lo que devuelve la
    biblioteca de referencia, que es lo único que puede desviarse.

    La recta latente es `η = x·beta`: cuanto más alta, más favorece al local.
    Los dos umbrales la parten en tres tramos.
    """

    #: Nueve, en el orden de `COMPARACIONES`.
    beta: np.ndarray
    #: Dos, siempre `umbrales[0] < umbrales[1]`.
    umbrales: np.ndarray
    observaciones: int = 0

    def probabilidades(self, x: np.ndarray) -> Probabilidades:
        eta = float(np.dot(self.beta, np.asarray(x, dtype=float)))
        acumuladas = _sigmoide(np.asarray(self.umbrales, dtype=float) - eta)
        derrota = float(acumuladas[0])
        empate = float(acumuladas[1] - acumuladas[0])
        victoria = float(1.0 - acumuladas[1])
        # Un redondeo desafortunado puede dejar un −1e−17, y la clase lo veta.
        derrota, empate, victoria = (max(0.0, v) for v in (derrota, empate, victoria))
        total = derrota + empate + victoria
        return Probabilidades(victoria / total, empate / total, derrota / total)


#: El ajuste, hecho una vez con `scripts/analizar_prediccion.py` sobre 1.031
#: partidos de liga de 186 equipos distintos, bajados el 2026-09-05.
#:
#: Se copian a mano a propósito. Ajustar aquí exigiría traer una biblioteca de
#: estadística entera --cientos de megas en la imagen que se despliega-- y los
#: 1.031 partidos, que viven sólo en la máquina del autor. Lo que hace este
#: módulo es aritmética: multiplicar nueve números y partir una recta en tres.
#:
#: Para rehacerlos: correr el guion y pegar lo que imprime al final.
BETA = (
    11.80682,  # Medio campo
    1.13017,  # Mi ataque izquierdo
    4.93370,  # Mi ataque central
    3.77174,  # Mi ataque derecho
    3.33673,  # Mi defensa izquierda
    4.45960,  # Mi defensa central
    1.07689,  # Mi defensa derecha
    3.00209,  # Balón Parado defensivo
    4.74328,  # Balón Parado ofensivo
)
UMBRALES = (18.40622, 19.54291)
OBSERVACIONES = 1031

#: Cuánto se aplana la recta latente antes de convertirla en probabilidades.
#:
#: Sin esto el modelo es DEMASIADO CONFIADO en los extremos, y se comprobó:
#: de 76 partidos a los que daba más del 90 % de victoria, prometía un 97,7 %
#: y ocurría el 88,2 %. Uno de cada ocho «victorias seguras» se perdía. Con la
#: escala: promete 97,4 % y ocurre 93,7 %.
#:
#: Es la consecuencia de que un modelo ordinal tenga una sola pendiente para
#: las tres clases: la recta se alarga y la sigmoide se satura. Dividir la
#: recta y los dos umbrales por un mismo número la vuelve a meter en rango sin
#: cambiar el orden de nada --ningún partido adelanta a otro-- ni los
#: aciertos, que se quedan en 0,740.
#:
#: El 1,30 NO se eligió mirando los partidos con los que se mide: se ajustó en
#: un tercer bloque, aparte del de entrenamiento y del de medida. Elegirlo con
#: el de medida sería decidir el examen después de verlo.
#:
#: NO SE CORRIGE NADA MÁS, y no por falta de ganas. En el bloque de medida el
#: modelo espera 28 empates y ocurren 39, que parece otro defecto que corregir.
#: No lo es: dentro de su propia muestra de entrenamiento clava la cuenta --96,0
#: esperados contra 97 ocurridos, 12,4 % contra 12,5 %-- y lo que pasa es que
#: ese bloque salió cargado de empates, un 15,1 % cuando entre trozos de 258
#: partidos la tasa va del 9,3 % al 16,3 %.
#:
#: Perseguir eso con más parámetros ajustados sobre 206 partidos de validación
#: y 39 empates es la receta para memorizar el ruido de un trozo. Se probó:
#: buscar escala, centro y ancho de la franja --por log-loss y por cuadrar lo
#: esperado con lo ocurrido-- estrechaba la franja en vez de ensancharla, y
#: dejaba el modelo peor. La escala sola, que arregla algo real y medido, se
#: queda; lo demás no.
ESCALA = 1.30


def modelo_ajustado() -> ModeloOrdinal:
    """El modelo listo para usar: coeficientes ajustados y ya aplanados.

    `BETA` y `UMBRALES` se guardan CRUDOS --tal como los devolvió la
    regresión-- porque son los que se enseñan en Transparencia. La escala se
    aplica aquí, para que lo publicado y lo aplicado no se puedan separar sin
    que se note.
    """
    return ModeloOrdinal(
        beta=np.array(BETA, dtype=float) / ESCALA,
        umbrales=np.array(UMBRALES, dtype=float) / ESCALA,
        observaciones=OBSERVACIONES,
    )


def mezclar(zonas: Probabilidades, poisson: Probabilidades | None) -> Probabilidades:
    """90 % zonas, 10 % Poisson, componente a componente.

    Sin Poisson --el partido de copa, cuyo rival no está en la tabla de la
    liga y por tanto no tiene fuerza de ataque ni de defensa que estimar-- se
    devuelven las zonas tal cual, en vez de inventar la mitad que falta.
    """
    if poisson is None:
        return zonas
    return Probabilidades(
        PESO_ZONAS * zonas.victoria + PESO_POISSON * poisson.victoria,
        PESO_ZONAS * zonas.empate + PESO_POISSON * poisson.empate,
        PESO_ZONAS * zonas.derrota + PESO_POISSON * poisson.derrota,
    )


def resultado(partido: Any) -> int:
    """0 derrota local < 1 empate < 2 victoria local. En ese orden, que importa."""
    if partido.home_goals > partido.away_goals:
        return 2
    return 1 if partido.home_goals == partido.away_goals else 0


def tabla_de_entrenamiento(
    partidos: Sequence[Any],
) -> tuple[np.ndarray, np.ndarray, list[int]]:
    """`X`, `y` y los identificadores de los partidos que entraron.

    Una fila por partido, desde el LOCAL, con los ratings de ESE partido.
    Meter también la del visitante duplicaría sin añadir nada: cada proporción
    suya es `1 − la del local`, y el modelo creería tener el doble de
    observaciones de las que tiene.

    No se pide historia ni se corta por fecha: lo que se mide es el motor de
    Hattrick, y para medir una función cada partido se basta a sí mismo.
    """
    filas, etiquetas, ids = [], [], []
    for p in partidos:
        if p.match_type not in TIPOS_OFICIALES:
            continue
        filas.append(variables(ratings_de(p, "home"), ratings_de(p, "away")))
        etiquetas.append(resultado(p))
        ids.append(p.ht_match_id)
    if not filas:
        return np.empty((0, len(COMPARACIONES))), np.empty(0, dtype=int), []
    return np.array(filas), np.array(etiquetas, dtype=int), ids
