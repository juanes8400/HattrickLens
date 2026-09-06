"""Predecir victoria, empate o derrota a partir de la historia de los equipos.

QUÉ COMPARA
-----------
Siete zonas, cruzadas como en el campo --mi banda izquierda ataca la derecha
del rival--, más el balón parado en los dos sentidos. Todo como PROPORCIÓN
`A/(A+B)`, nunca como resta: los ratings van de 1 a 93 y una diferencia de 10
no significa lo mismo arriba que abajo, mientras que la proporción siempre
dice «qué parte del enfrentamiento es mía».

DOS PROBLEMAS, NO UNO
---------------------
Aquí se resuelven dos cosas distintas y conviene no confundirlas:

1. CÓMO FUNCIONA EL MOTOR de Hattrick: dados unos ratings, ¿qué resultado
   sale? Es una función fija, la misma para todos los equipos del mundo.
2. QUÉ RATINGS TENDRÁ un equipo el domingo que viene. Eso sí depende del
   equipo, y no se sabe: se estima de su forma reciente.

El primero se aprende con los ratings DEL PROPIO partido. No hace falta
historia del equipo para medir una función: cada partido es una observación
completa --entraron estos ratings, salió este resultado-- y vale por sí sola,
venga de quien venga. Por eso la muestra son partidos ajenos bajados una vez,
y por eso mil partidos de mil equipos distintos enseñan más que mil de uno.

El segundo se resuelve con la MEDIANA de los partidos oficiales recientes del
equipo. Mediana y no media porque protege gratis del partido con tres
lesionados; en la cuenta real apenas se diferencian (75,1 contra 75,5), y lo
que sí quitó ruido --de 11,5 a 9,5 de desviación-- fue descartar lo no
oficial, así que eso se hace primero.

QUE SE ENTRENE CON DATOS PRECISOS Y SE TRABAJE CON ESTIMADOS es una asimetría
real, y no se tapa: parte del error de una predicción no es del motor sino de
haber adivinado mal los ratings. Pero mezclarlos sería peor. Aprender la
función con medianas la deformaría --el rating de un partido concreto es lo
que de verdad entró en el motor, la mediana no entró en ninguno-- y ya no
habría forma de saber cuánto falla cada mitad. Separados, el ajuste de esta
parte se mide con sus propios partidos y la otra queda a la vista.

QUÉ NO ENTRA
------------
La actitud: Hattrick sólo la manda para tu propio equipo, nunca para el rival.

LO QUE DA, MEDIDO
-----------------
Con 1.031 partidos de liga de 186 equipos distintos, bajados el 2026-09-05.
Se entrena con los primeros 773 y se mide con los 258 siguientes, que el
modelo no vio:

    aciertos                        74,4 %   (acertar siempre lo más común: 48,1 %)
    AUC victoria / derrota          0,900 / 0,923
    pseudo-R² de McFadden           0,42
    sólo victoria contra derrota    87,2 % de aciertos, AUC 0,948

El medio campo manda con diferencia: por cada 10 puntos porcentuales que un
equipo se lleva del medio campo, la derrota se vuelve 5,5 veces menos probable
frente a la victoria. Después van el ataque central y el balón parado
ofensivo. Los nueve coeficientes tienen el signo que deben: todo lo que
favorece al local lo aleja de la derrota.

EL EMPATE NO SE PREDICE, SE MIDE. De 39 empates reales, el modelo señaló 1
como resultado más probable. No es un fallo que se pueda arreglar afinando:
el empate casi nunca es la opción más probable de las tres --su AUC, 0,741,
dice que sí distingue cuándo es más probable de lo normal--. Por eso lo que
se enseña son las tres probabilidades y no un pronóstico.

Este motor, escrito a mano, empata con la regresión de referencia de
statsmodels: mismos aciertos y mismo AUC hasta el tercer decimal. Y con esta
cantidad de partidos la regularización mueve el log-loss menos de 0,01; se
mantiene porque el problema que resolvía era el de pocos datos, y ahí sigue.

ESTÁ CALIBRADO, Y ESO SE COMPROBÓ APARTE. Acertar y estar calibrado son cosas
distintas: un modelo puede acertar el 74 % y aun así decir «80 %» donde la
verdad es 60 %. Como aquí lo que se enseña son porcentajes, la calibración es
justo lo que hace que el número sirva para algo.

No se compara con cero, porque cero no se alcanza: con 258 partidos, hasta un
modelo perfecto se desvía --la moneda cargada al 70 % no sale cara exactamente
7 de cada 10 veces--. Así que se simulan dos mil mundos en los que el modelo
acierta exacto y se mira si el error real cabe entre lo que sale ahí:

    error de calibración   victoria 0,063   empate 0,042   derrota 0,042
    lo esperable (p95)              0,070            0,051            0,068

Cabe en los tres. Se probó además la corrección estándar --escalar por una
temperatura ajustada en un bloque aparte-- y EMPEORA: el log-loss sube de
0,625 a 0,628. Así que no se aplica; el modelo ya sale calibrado de fábrica.

Lo único que se le ve es que espera menos empates de los que ocurren (29
frente a 39 en el bloque de medida). Está dentro del ruido de la muestra, pero
si con más partidos se confirma, ahí es donde habría que meter mano.

El análisis se rehace con `scripts/analizar_prediccion.py`. Necesita
`statsmodels` y `scikit-learn`, que están en el grupo `dev` y NO en las
dependencias que se despliegan: la imagen de producción no ajusta modelos,
sólo aplica coeficientes ya calculados.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

#: Liga, promoción y copa. Un torneo o un amistoso se juegan con suplentes.
TIPOS_OFICIALES = (1, 2, 3)

#: Las nueve comparaciones, en el orden en que viajan en el vector. Cada una
#: es (nombre, mi campo, su campo) — y los cruces son los del terreno de
#: juego: mi ataque izquierdo contra su defensa DERECHA.
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

#: Cuánto pesa cada modelo. Decisión del usuario el 2026-09-05.
PESO_ZONAS = 0.90
PESO_POISSON = 0.10

#: Mínimo de partidos previos para que una mediana signifique algo. Con menos,
#: no se PREDICE: se dice que no se puede. No afecta al entrenamiento, que no
#: mira historia ninguna.
MINIMO_HISTORIA = 3

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


class PartidoConRatings(Protocol):
    """Lo que el motor necesita de un partido ya jugado."""

    ht_match_id: int
    match_type: int
    home_team_id: int
    away_team_id: int
    home_goals: int
    away_goals: int


def proporcion(a: float, b: float) -> float:
    """`A/(A+B)`, acotada en [0, 1].

    Con los dos a cero no hay información y devuelve 0,5: decir 0 o 1 sería
    afirmar que gana uno de los dos sin dato que lo sostenga.
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


def medianas(
    partidos: Sequence[Any], equipo: int, *, hasta: int | None = None
) -> dict[str, float] | None:
    """La mediana de cada rating del equipo en sus partidos oficiales previos.

    `hasta` es el `ht_match_id` del partido que se está evaluando: sólo se
    miran los ANTERIORES. Sin ese corte, el modelo vería el resultado que
    intenta predecir --fuga temporal-- y daría una precisión imposible.

    Se ordena por identificador y no por fecha porque los identificadores de
    Hattrick son crecientes en el tiempo y `played_at` puede faltar.
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


def ratings_de(partido: Any, lado: str) -> dict[str, float]:
    """Los nueve ratings de un lado (`home` o `away`) de un partido jugado."""
    return {c: float(getattr(partido, f"{lado}_{c}")) for c in CAMPOS}


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


@dataclass
class ModeloDeZonas:
    """Regresión logística multinomial sobre las nueve proporciones.

    Escrita a mano --como `salary_model`-- para no traer una dependencia de
    aprendizaje automático entera por un modelo de tres clases y nueve
    variables.

    `regularizacion` no es un adorno: sin ella, unos pocos partidos separables
    hacen que los coeficientes crezcan sin límite. Comprobado con cinco
    partidos reales: la pérdida bajaba a 0,002 mientras el mayor coeficiente
    llegaba a 17 y seguía subiendo, y el medio campo salía con signo negativo.
    """

    #: (3 clases × 10) — nueve variables más el término independiente.
    pesos: np.ndarray
    observaciones: int

    CLASES = ("victoria", "empate", "derrota")

    def probabilidades(self, x: np.ndarray) -> Probabilidades:
        z = self.pesos @ np.append(1.0, x)
        z -= z.max()  # estabilidad numérica: exp(1000) desborda
        e = np.exp(z)
        p = e / e.sum()
        return Probabilidades(float(p[0]), float(p[1]), float(p[2]))


def ajustar_zonas(
    diseno: np.ndarray, y: np.ndarray, *, regularizacion: float = 1.0, vueltas: int = 4000
) -> ModeloDeZonas:
    """Multinomial por descenso de gradiente. `y` en 0=victoria, 1=empate, 2=derrota."""
    n, k = diseno.shape
    con_intercepto = np.hstack([np.ones((n, 1)), diseno])
    pesos = np.zeros((3, k + 1))
    indicadora = np.zeros((n, 3))
    indicadora[np.arange(n), y] = 1.0
    for _ in range(vueltas):
        z = con_intercepto @ pesos.T
        z -= z.max(axis=1, keepdims=True)
        p = np.exp(z)
        p /= p.sum(axis=1, keepdims=True)
        grad = (indicadora - p).T @ con_intercepto / n
        # El término independiente NO se regulariza: penalizarlo empujaría las
        # tres clases hacia la misma frecuencia y borraría que la victoria
        # local es más común que la derrota.
        pen = regularizacion * pesos / n
        pen[:, 0] = 0.0
        pesos += 0.5 * (grad - pen)
    return ModeloDeZonas(pesos=pesos, observaciones=n)


@dataclass
class ModeloPoisson:
    """Goles a favor y en contra, con la Poisson de siempre.

    Vale igual en Liga que en Copa: lo que cambia entre competiciones es el
    rival, no cómo se reparten los goles.
    """

    #: Goles que marca de media un local y un visitante en la muestra.
    media_local: float
    media_visitante: float
    #: Fuerza ofensiva y defensiva por equipo, relativa a esas medias.
    ataque: dict[int, float]
    defensa: dict[int, float]
    #: Hasta cuántos goles se suman al repartir. Más allá, la probabilidad es
    #: despreciable y sólo añade tiempo.
    tope: int = 8

    def probabilidades(self, local: int, visitante: int) -> Probabilidades:
        lam_l = self.media_local * self.ataque.get(local, 1.0) * self.defensa.get(visitante, 1.0)
        lam_v = (
            self.media_visitante * self.ataque.get(visitante, 1.0) * self.defensa.get(local, 1.0)
        )
        pl = [math.exp(-lam_l) * lam_l**i / math.factorial(i) for i in range(self.tope + 1)]
        pv = [math.exp(-lam_v) * lam_v**i / math.factorial(i) for i in range(self.tope + 1)]
        v = e = d = 0.0
        for i, a in enumerate(pl):
            for j, b in enumerate(pv):
                if i > j:
                    v += a * b
                elif i == j:
                    e += a * b
                else:
                    d += a * b
        # Se renormaliza porque el tope deja fuera una cola minúscula; sin
        # esto las tres no sumarían exactamente 1 y `Probabilidades` lo veta.
        t = v + e + d
        return Probabilidades(v / t, e / t, d / t)


def ajustar_poisson(partidos: Sequence[Any]) -> ModeloPoisson:
    """Fuerza ofensiva y defensiva de cada equipo, relativa a la media."""
    oficiales = [p for p in partidos if p.match_type in TIPOS_OFICIALES]
    if not oficiales:
        raise ValueError("sin partidos oficiales no hay Poisson que ajustar")
    ml = float(np.mean([p.home_goals for p in oficiales])) or 0.01
    mv = float(np.mean([p.away_goals for p in oficiales])) or 0.01

    marcados: dict[int, list[float]] = {}
    recibidos: dict[int, list[float]] = {}
    for p in oficiales:
        marcados.setdefault(p.home_team_id, []).append(p.home_goals / ml)
        recibidos.setdefault(p.home_team_id, []).append(p.away_goals / mv)
        marcados.setdefault(p.away_team_id, []).append(p.away_goals / mv)
        recibidos.setdefault(p.away_team_id, []).append(p.home_goals / ml)
    return ModeloPoisson(
        media_local=ml,
        media_visitante=mv,
        ataque={t: float(np.mean(v)) for t, v in marcados.items()},
        defensa={t: float(np.mean(v)) for t, v in recibidos.items()},
    )


def mezclar(zonas: Probabilidades, poisson: Probabilidades) -> Probabilidades:
    """90 % zonas, 10 % Poisson. Decisión del usuario, no un peso ajustado.

    Se puede medir si otra mezcla acierta más en cuanto haya datos suficientes;
    mientras tanto es una opinión declarada, y por eso vive en una constante
    con nombre en vez de escondida en una fórmula.
    """
    return Probabilidades(
        PESO_ZONAS * zonas.victoria + PESO_POISSON * poisson.victoria,
        PESO_ZONAS * zonas.empate + PESO_POISSON * poisson.empate,
        PESO_ZONAS * zonas.derrota + PESO_POISSON * poisson.derrota,
    )


def resultado(partido: Any) -> int:
    """0 victoria local, 1 empate, 2 derrota local."""
    if partido.home_goals > partido.away_goals:
        return 0
    return 1 if partido.home_goals == partido.away_goals else 2


def tabla_de_entrenamiento(
    partidos: Sequence[Any],
) -> tuple[np.ndarray, np.ndarray, list[int]]:
    """`X`, `y` y los identificadores de los partidos que entraron.

    Una fila por partido, desde el LOCAL, con los ratings de ESE partido.
    Meter también la del visitante duplicaría sin añadir nada: cada proporción
    suya es `1 − la del local`, y el modelo creería tener el doble de
    observaciones de las que tiene.

    No se pide historia ni se corta por fecha. Lo que se está midiendo es el
    motor de Hattrick, y para medir una función cada partido se basta a sí
    mismo. Antes esta función exigía tres partidos previos de cada equipo y
    usaba medianas; con eso, de 22 partidos recogidos sobrevivían 10.
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
