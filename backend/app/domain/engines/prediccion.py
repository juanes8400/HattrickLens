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

UN SOLO MODELO, DESDE EL 2026-09-20
-----------------------------------
El motor es la regresión de Poisson sobre los goles: estima cuántos marca
cada lado, despliega esa estimación en una rejilla de marcadores y suma la
rejilla en tres montones. Decisión del usuario, tomada sobre el barrido
entero (ver `PESO_GOLES`).

Hubo una segunda mitad, una regresión ordinal que aprendía de quién ganó sin
pasar por los goles, y pesaba un 20 %. Sigue en este fichero, apagada: el
peso a cero salta su cuenta entera y volver a encenderla es cambiar un número.
Lo que no se hace es enseñarla, porque ya no interviene en nada de lo que se
ve.

LO QUE DA, MEDIDO
-----------------
Sobre los 5.232 partidos de liga de 979 equipos de cinco países, con los
coeficientes que lleva pegados este fichero:

    aciertos     71,3 %   (acertar siempre lo más común: 50,7 %)
    log-loss     0,659
    AUC          0,877 victoria
    empates      promete 806, ocurren 733

Y las dos advertencias que van con esas cifras, porque sin ellas engañan:

1. Los coeficientes salieron de estos mismos partidos, así que es preguntarle
   al modelo por un examen que ya vio: los números de verdad, contra partidos
   nuevos, serán algo peores. Medirlo bien exige rehacer el ajuste no lineal
   en cada corte; ver la cabecera de `scripts/evaluar_motor.py`.

2. EL EMPATE NO ESTÁ CALIBRADO. Promete un 10 % más de empates de los que
   ocurren, y su error de calibración se sale de la banda que explicaría el
   azar. Con la mitad ordinal puesta sí cabía dentro. Es el precio conocido
   de esta decisión, no una sorpresa, y por eso está escrito aquí y no
   escondido: donde la pantalla dice «28 % de empate», ocurre algo menos.

El acierto y el log-loss, en cambio, no se movieron: entre el 80 % y el 100 %
la diferencia era de seis centésimas de por ciento, ruido. Lo que la ordinal
sujetaba era la cifra del empate, no la puntería.

DOS PROBLEMAS, NO UNO
---------------------
1. CÓMO FUNCIONA EL MOTOR de Hattrick: dados unos ratings, ¿qué resultado
   sale? Función fija, la misma para todos los equipos del mundo.
2. QUÉ RATINGS TENDRÁ un equipo el domingo. Eso sí depende del equipo.

El primero se aprende con los ratings DEL PROPIO partido. No hace falta
historia de nadie para medir una función: cada partido es una observación
completa y vale por sí sola, venga de quien venga. Por eso la muestra son
partidos ajenos bajados una vez.

El segundo se resuelve con el PROMEDIO de los partidos oficiales recientes.
Fue la mediana hasta el 2026-09-13, cuando se retiró por enredar a los
usuarios; en la cuenta real apenas se diferenciaban (75,1 contra 75,5) y lo
que sí quitó ruido --de 11,5 a 9,5 de desviación-- fue descartar lo no oficial.

LOS DOS LADOS ENTRAN IGUAL
--------------------------
También el equipo propio, aunque para el propio exista algo mejor: Hattrick
calcula los siete ratings EXACTOS de la alineación ya guardada. No se usa.

`A/(A+B)` deja de ser simétrica si un lado entra afilado y el otro suavizado
por el promedio. Medido en 180 partidos la diferencia es ruido, pero el
síntoma aparece: dar el dato exacto a un lado bajó el AUC de 0,905 a 0,894
--añadir información buena empeoró la discriminación--. Y hay dos razones
mejores que la medida: los ratings exactos describen la alineación que hay
guardada AHORA, que puede ser un borrador y puede cambiar antes del pitido,
mientras que el promedio describe al equipo; y es un solo camino de código.

LA VENTAJA DE CAMPO NO SE SUMA APARTE
-------------------------------------
Ya viene dentro de los ratings: medido en los 1.031 partidos, el medio campo
del local es un 19 % más alto que el del visitante --14,2 contra 12,0-- y en
defensa y ataque la diferencia es del 2 % o menos. Sumarle encima un bono de
local sería contarla dos veces.

Y DESDE EL 2026-09-20 NO SE SUMA NADA EN ABSOLUTO. Con ratings idénticos en
los dos lados el modelo da ahora 40,97 % de victoria contra 40,97 % de
derrota: exactamente simétrico. La Poisson calcula la lambda de cada lado con
SUS duelos ofensivos, así que con ratings iguales las dos coinciden al último
decimal.

Hasta ese día quedaba un residuo de 5,7 puntos a favor del local (42,1 contra
36,4), y no venía de ningún bono: salía de la mitad ordinal, de que la suma de
sus coeficientes (38,26) no coincidiera con la de sus umbrales (37,95). Al
apagar la ordinal se fue con ella.

Es una consecuencia de la decisión, no un descuido. Lo que queda es la ventaja
de campo que ya traen los ratings, que es la grande y la medida; lo que se ha
perdido es esa corrección de encima. Se comprobó en su día que meter un
término explícito de «juega en casa» en la Poisson no compensa: sale +0,0149
con p = 0,33 y el AIC empeora.

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

from app.domain.engines.rival_scouting import PitchZoneMethod, resumir_ratings
from app.domain.value_objects.ht_constants import (
    FRIENDLY_MATCH_TYPES,
    MATCH_TYPE_CUP,
    MATCH_TYPE_LEAGUE,
    MATCH_TYPE_MASTERS,
    MATCH_TYPE_QUALIFICATION,
)

#: EL RESUMEN SE SACA DE UNA SOLA COMPETICIÓN, y esto se arregló el 2026-09-08
#: porque estaba de las dos maneras a la vez: `promedios()` mezclaba liga y
#: copa mientras la pantalla de Liga usaba sólo liga. Dos reglas para el mismo
#: número, y ninguna elegida a propósito.
#:
#: Se separan porque un equipo NO juega igual en las dos. Medido sobre el
#: equipo del usuario, temporada 83:
#:
#:     mediocampo en sus 6 partidos de liga:   6, 10,  9, 11,  9, 19
#:     mediocampo en sus 6 partidos de copa:   8, 13, 27, 13, 21, 21
#:
#: Son dos equipos distintos. Un promedio que los mezcle no describe ninguno
#: de los dos: en copa lo subestima y en liga lo infla. Medido en sus once
#: partidos de la temporada, el error de goles de la copa casi dobla al de la
#: liga (1,97 contra 1,17) y no es azar, es esto.
#:
#: QUÉ VA CON QUÉ, decidido por el usuario el 2026-09-08:
#:
#:   · La PROMOCIÓN va con la liga. Es el mismo torneo, su desenlace: se juega
#:     contra rivales del mismo nivel y con el equipo de siempre.
#:   · El HATTRICK MASTERS va con la liga. Es eliminatoria, pero no se afronta
#:     como una copa: se sale a ganar con el once titular, que es lo que el
#:     resumen intenta describir. Lo que agrupa aquí NO es el formato del
#:     torneo, es CON QUÉ EQUIPO se juega.
#:   · La COPA va sola, por lo mismo al revés.
TIPOS_DE_LIGA = (
    MATCH_TYPE_LEAGUE,
    MATCH_TYPE_QUALIFICATION,
    MATCH_TYPE_MASTERS,
)
TIPOS_DE_COPA = (MATCH_TYPE_CUP,)

#: LOS AMISTOSOS, como TERCERA muestra elegible. Pedido explícitamente el
#: 2026-09-08 para la ficha de rival: hay quien quiere ver qué dice el modelo
#: con los amistosos del rival, que a veces son lo único reciente que tiene.
#:
#: NO ES UNA MUESTRA EQUIVALENTE A LAS OTRAS DOS, y quien la pida tiene que
#: saberlo: un amistoso se juega con suplentes y sin nada en juego. Los
#: coeficientes del motor salieron de 5.232 partidos de LIGA, así que aplicarlos
#: a ratings de amistoso es extrapolar. Sirve para explorar, no para decidir, y
#: la pantalla lo dice cuando esta muestra está elegida.
#:
#: SÓLO SE OFRECE CONTRA UN RIVAL DE AMISTOSO, acotado por el usuario el
#: 2026-09-08. Contra el rival de liga del domingo la muestra buena son sus
#: partidos de liga: mirar sus amistosos describiría al equipo de suplentes
#: que NO va a jugar ese partido. Y cuando lo que viene ES un amistoso, esta
#: muestra pasa a ser la automática, por la misma regla que manda en las
#: otras dos: el resumen sale de la competición del partido que se juega.
TIPOS_DE_AMISTOSOS = tuple(sorted(FRIENDLY_MATCH_TYPES))

TIPOS_POR_COMPETICION: dict[str, tuple[int, ...]] = {
    "liga": TIPOS_DE_LIGA,
    "copa": TIPOS_DE_COPA,
    "amistosos": TIPOS_DE_AMISTOSOS,
}

#: Los oficiales son la unión de liga y copa --los amistosos NO son oficiales--
#: y se DERIVA en vez de escribirse aparte: escrita a mano era otra lista más
#: que podía discrepar de éstas, que es exactamente el fallo que se vino a
#: arreglar.
TIPOS_OFICIALES = TIPOS_DE_LIGA + TIPOS_DE_COPA

#: Pero para APRENDER el resultado, sólo liga. La copa juega con otras reglas y
#: se comprobó lo que eso hace: de 861 partidos de copa recogidos, CERO
#: empates --hay prórroga, alguien tiene que pasar-- y el local marcaba 1,18
#: por 5,42 del visitante, porque el sorteo cruza divisiones distintas y el
#: que recibe suele ser el débil.
#:
#: Entrenar con eso enseña dos mentiras a la vez: que el empate casi no existe
#: y que jugar en casa perjudica. Con la copa dentro, las tres clases salían
#: descalibradas; fuera, las tres pasan.
TIPOS_DE_ENTRENAMIENTO = (1,)

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

#: LOS NUEVE DUELOS SE SUMAN, y no es por no haber probado otra cosa.
#:
#: La objeción es buena: en Hattrick el mediocampo no es un sector más, decide
#: la POSESIÓN, y la posesión no debería sumarse a tus ataques sino
#: multiplicarlos --dominar el medio valdría un porcentaje más de las ocasiones
#: que tus ataques generan, no un número fijo de puntos--. Es decir:
#:
#:     hoy:         eta = b_medio*medio + suma(b_zona * zona)
#:     multiplica:  eta = b_medio*medio + m(medio) * suma(b_zona * zona)
#:
#: Se probaron 42 estructuras el 2026-09-07 --seis formas de medir un duelo por
#: siete multiplicadores de posesión, todos con los mismos once parámetros y
#: los mismos cortes de origen móvil-- en `scripts/rejilla_de_estructuras.py`.
#: NINGUNA le gana a sumar. Las tres primeras:
#:
#:     A/(A+B) sin multiplicador   0,6445   <- ésta
#:     A/(A+B) x raiz(2p)          0,6449   (empate técnico, gana 2 de 5 cortes)
#:     A/(A+B) x 2p                0,6463
#:     A/(A+B) x p/(1-p)           0,7039   (la 40ª de 42)
#:
#: Y lo que dicen las 42 juntas es más interesante que el ganador: cuanto más
#: AGRESIVO el multiplicador, peor predice, en las seis familias a la vez
#: --ninguno < raiz(2p) < 2p < e^(2p-1) < raiz(p/(1-p)) < (2p)^2 < p/(1-p)--.
#: O sea que el efecto multiplicativo, si existe, es tan flojo que la mejor
#: aproximación es no tenerlo. Tiene sentido: el mediocampo ya entra por su
#: propio coeficiente, que es con diferencia el más grande de los nueve
#: (11,80 contra 2,2-3,8 de los demás), y eso ya recoge casi todo lo que la
#: posesión explica.
#:
#: Los nueve duelos, en el orden en que viajan en el vector. Cada uno es
#: (nombre, mi campo, su campo), y los cruces son los del terreno de juego.
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
#:
#: Se nombra el ENFRENTAMIENTO entero, no sólo mi lado. Antes ponía «Mi ataque
#: central» a secas y eso se lee mal: parece que el coeficiente habla de mi
#: ataque, cuando habla del duelo. Con la etiqueta corta, alguien podía leer
#: «subir mi ataque central multiplica por 1,76 mis opciones», y no es eso
#: lo que las multiplica es llevarse diez puntos porcentuales más DEL DUELO,
#: que se consigue subiendo yo o bajando él.
#:
#: Y las bandas van espejadas, que tampoco es obvio: mi extremo izquierdo
#: corre por el mismo carril físico por el que defiende su lateral DERECHO.
#: Sin decirlo, nadie lo adivina mirando una tabla de coeficientes.
ETIQUETAS = {
    "medio": "Mi medio campo contra el suyo",
    "ata_izq": "Mi ataque izquierdo contra su defensa derecha",
    "ata_cen": "Mi ataque central contra su defensa central",
    "ata_der": "Mi ataque derecho contra su defensa izquierda",
    "def_izq": "Mi defensa izquierda contra su ataque derecho",
    "def_cen": "Mi defensa central contra su ataque central",
    "def_der": "Mi defensa derecha contra su ataque izquierdo",
    "bp_def": "Mi Balón Parado defensivo contra su ofensivo",
    "bp_ata": "Mi Balón Parado ofensivo contra su defensivo",
}

#: Partidos previos mínimos para que un resumen signifique algo. Uno.
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

    SE PROBARON LAS CUATRO FORMAS el 2026-09-07, con los mismos 5.232 partidos
    y los mismos cortes de origen móvil (`scripts/comparar_parametrizacion.py`).
    Las cuatro ordenan los duelos IGUAL --son transformaciones monótonas unas
    de otras-- y lo que cambia es cómo entran a una suma en línea recta.
    Log-loss del motor entero, fuera de muestra:

        A/(A+B)       0,6419   <- ésta, y gana los 5 cortes de 5
        log(A/(A+B))  0,6471
        log(A/B)      0,6476
        A/B           0,6822   y deja un duelo sin significar nada (p = 0,25)

    La ventaja sobre las dos del medio es pequeña --menos que la dispersión
    entre cortes-- pero es del mismo signo en los cinco, que por azar sale una
    vez de cada 32. No se vuelve a probar sin datos nuevos.

    Y NO, EL 0,5 NO METE SESGO, que es la duda razonable que aparece al ver
    que dos medios campos iguales suman 0,5 x 11,80 a la recta. En un modelo
    ordinal sólo cuenta la diferencia `umbral − recta`, así que esa constante
    la absorben los umbrales al ajustar: ver `scripts/sesgo_del_neutro.py`,
    que reajusta con `x − 0,5` y obtiene las mismas probabilidades con los
    umbrales movidos exactamente 0,5 x Σβ.
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


def promedios(
    partidos: Sequence[Any],
    equipo: int,
    *,
    competicion: str,
    hasta: int | None = None,
) -> dict[str, float] | None:
    """El promedio de cada rating del equipo en sus partidos previos DE ESA
    COMPETICIÓN.

    `competicion` es "liga" o "copa" y NO tiene valor por defecto a
    propósito: el defecto anterior mezclaba las dos y nadie lo había elegido.
    Quien pida un promedio tiene que decir para qué pantalla es.

    `hasta` es el `ht_match_id` del partido que se evalúa: sólo se miran los
    ANTERIORES. Sirve para comprobar el modelo contra partidos ya jugados sin
    que vea el que intenta predecir; para predecir el domingo no hace falta,
    porque todavía no existe.

    Se ordena por identificador y no por fecha porque los identificadores de
    Hattrick crecen con el tiempo y la fecha puede faltar.
    """
    tipos = TIPOS_POR_COMPETICION[competicion]
    suyos = [
        p
        for p in partidos
        if p.match_type in tipos
        and _lado(p, equipo) is not None
        and (hasta is None or p.ht_match_id < hasta)
    ]
    if len(suyos) < MINIMO_HISTORIA:
        return None
    suyos.sort(key=lambda p: p.ht_match_id)

    out: dict[str, float] = {}
    for campo in CAMPOS:
        vals = [float(getattr(p, f"{_lado(p, equipo)}_{campo}")) for p in suyos]
        out[campo] = round(float(np.mean(vals)), 1)
    out["_partidos"] = float(len(suyos))
    return out


#: LA SEDE, que un resumen diluye (2026-09-13). La ventaja de campo no se suma
#: aparte porque ya viene dentro de los ratings --ver la cabecera--: el medio
#: campo de un equipo en casa sale más alto que fuera. Eso vale para los
#: ratings de UN partido. Un resumen de varios mezcla partidos de casa y de
#: fuera, y entonces el local entra rebajado y el visitante inflado.
#:
#: Medido con origen móvil sobre los 5.232 partidos de liga, prediciendo con el
#: promedio de los partidos anteriores: el motor prometía un 41,5 % de
#: victorias locales donde ocurrían un 50,1 %. Corrigiendo el medio campo con
#: esta razón promete un 49,7 %, y el log-loss baja de 0,7233 a 0,6924, con
#: p < 1e-9 en la comparación partido a partido. Corregir las nueve zonas daba
#: lo mismo --en las otras ocho la razón es prácticamente 1-- y promediar sólo
#: los partidos de la misma sede era peor, porque deja muy pocos partidos.
#:
#: Es la media del medio campo en casa entre la media fuera. Salió entre 1,177
#: y 1,180 en los cinco cortes.
RAZON_MEDIO_CASA_FUERA = 1.178

#: Los partidos con una sede segura y donde se midió la corrección. En copa las
#: últimas rondas se juegan en campo neutral, y un amistoso no se midió.
TIPOS_CON_SEDE = (MATCH_TYPE_LEAGUE, MATCH_TYPE_QUALIFICATION)


def corregir_sede(
    resumen: dict[str, float],
    lecturas: Sequence[dict[str, Any]],
    en_casa: bool | None,
    metodo: str = PitchZoneMethod.AVERAGE,
) -> dict[str, float]:
    """El medio campo de un resumen, llevado a la sede del partido que viene.

    Si una fracción `f` de los partidos resumidos se jugó en casa, el resumen
    vale base·(f·h + (1−f)·a), con h = √razón y a = 1/√razón. En casa se lleva
    a base·h y fuera a base·a. Usa la mezcla REAL de cada equipo y no un 50 %
    supuesto: quien ha jugado cuatro de cinco en casa ya viene casi corregido.

    Con el ÚLTIMO partido la fracción es 1 o 0, según dónde se jugó ese.

    No toca nada cuando `en_casa` es None --un partido hipotético, o en campo
    neutral-- ni cuando alguna lectura no dice dónde se jugó: la alineación
    enviada no es un partido jugado, y adivinar su sede sería inventar.
    """
    if en_casa is None or not lecturas or "midfield" not in resumen:
        return resumen
    crudas = [r.get("en_casa") for r in lecturas]
    if any(s is None for s in crudas):
        return resumen
    sedes = [1.0 if s else 0.0 for s in crudas]
    fraccion = sedes[-1] if metodo == PitchZoneMethod.LAST else sum(sedes) / len(sedes)
    casa = float(np.sqrt(RAZON_MEDIO_CASA_FUERA))
    fuera = 1.0 / casa
    mezcla = fraccion * casa + (1.0 - fraccion) * fuera
    return {**resumen, "midfield": resumen["midfield"] * (casa if en_casa else fuera) / mezcla}


def resumen_de_lecturas(
    lecturas: Sequence[dict[str, Any]],
    metodo: str = PitchZoneMethod.AVERAGE,
    en_casa: bool | None = None,
) -> dict[str, float] | None:
    """Lo mismo, pero desde lecturas ya extraídas de un equipo.

    La pantalla de rivales no devuelve partidos sino los ratings de un equipo,
    un diccionario por partido. Ese es el camino real en producción; `promedios`
    sirve para las comprobaciones contra partidos guardados.

    EL MÉTODO SE ELIGE (2026-09-09). La misma pregunta tiene las mismas
    respuestas en todas las pantallas, así que el resumen se delega en
    `resumir_ratings`, que es el único sitio donde vive cada método.

    El defecto es el PROMEDIO desde el 2026-09-13. Antes era la mediana, que se
    retiró por enredar a los usuarios; las comprobaciones del modelo se hicieron
    con ella, y en la cuenta real los dos apenas se diferencian.

    Un rating que falte cuenta como 0, y entonces la proporción lo neutraliza a
    0,5. Aquí NO se descartan lecturas incompletas, al revés que en la ficha de
    rival: las de la serie las arma `lecturas_de_la_serie`, que siempre entrega
    los nueve campos, así que un hueco ya llegó resuelto como cero.

    `en_casa` es la sede del partido que se va a predecir: con ella el
    medio campo se corrige por `corregir_sede`. Sin ella, nada cambia.
    """
    if len(lecturas) < MINIMO_HISTORIA:
        return None
    completas = [{c: float(r.get(c) or 0) for c in CAMPOS} for r in lecturas]
    out = corregir_sede(
        resumir_ratings(completas, CAMPOS, metodo),  # type: ignore[arg-type]
        lecturas,
        en_casa,
        metodo,
    )
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

    @staticmethod
    def normalizada(victoria: float, empate: float, derrota: float) -> Probabilidades:
        """Para ternas que vienen de fuera y no suman exactamente uno.

        El pronóstico de la Poisson llega redondeado a tres decimales y suma
        1,0001 tantas veces como 0,9999. Rechazarlo sería correcto y también
        inútil: lo que hay que impedir es que alguien invente una terna, no que
        un redondeo tumbe la pantalla.
        """
        total = victoria + empate + derrota
        if total <= 0:
            raise ValueError("una terna que suma cero no dice nada")
        return Probabilidades(victoria / total, empate / total, derrota / total)

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


#: El ajuste, hecho una vez con `scripts/analizar_prediccion.py` sobre 5.232
#: partidos de LIGA de 979 equipos, de seis bloques repartidos por el mundo
#: --nombres neerlandeses, alemanes, suizos, españoles, colombianos-- bajados
#: el 2026-09-07. Con los 1.031 de una sola liga que había antes, tres de los
#: nueve duelos no eran significativos y el ataque izquierdo parecía valer la
#: mitad que el derecho; con éstos los nueve pasan de sobra y las dos bandas
#: salen iguales (3,05 contra 3,14), que es lo que manda un campo simétrico.
#:
#: Se copian a mano a propósito. Ajustar aquí exigiría traer una biblioteca de
#: estadística entera --cientos de megas en la imagen que se despliega-- y los
#: 1.031 partidos, que viven sólo en la máquina del autor. Lo que hace este
#: módulo es aritmética: multiplicar nueve números y partir una recta en tres.
#:
#: Para rehacerlos: correr el guion y pegar lo que imprime al final.
BETA = (
    11.79576,  # Mi medio campo contra el suyo
    3.04810,  # Mi ataque izquierdo contra su defensa derecha
    3.70385,  # Mi ataque central contra su defensa central
    3.14262,  # Mi ataque derecho contra su defensa izquierda
    3.02126,  # Mi defensa izquierda contra su ataque derecho
    2.24604,  # Mi defensa central contra su ataque central
    3.00260,  # Mi defensa derecha contra su ataque izquierdo
    3.48632,  # Mi Balón Parado defensivo contra su ofensivo
    3.81489,  # Mi Balón Parado ofensivo contra su defensivo
)
UMBRALES = (17.86481, 18.87730)
OBSERVACIONES = 5232

#: Cuánto se aplana la recta latente antes de convertirla en probabilidades.
#: Uno: no se aplana nada.
#:
#: Estuvo en 1,30 y tenía motivo. Con 773 partidos de entrenamiento el modelo
#: se pasaba de confiado: de 76 partidos a los que daba más del 90 % de
#: victoria, prometía 97,7 % y ocurría el 88,2 %. Aplanarlo lo arreglaba.
#:
#: Con 5.232 el problema desapareció solo, que es lo que tenía que pasar: el
#: exceso de confianza era de ajustar con pocos datos, no de la forma del
#: modelo. Buscando la escala en un bloque aparte, el óptimo salió 1,0 y
#: cualquier aplanado empeoraba --a 1,3 el log-loss subía de 0,597 a 0,608 y
#: el error de calibración de 0,033 a 0,044--.
#:
#: Se deja como constante en vez de borrarla: si algún día se reajusta con
#: pocos partidos, aquí es donde hay que mirar.
ESCALA = 1.0


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

    Sólo entra la LIGA: ver `TIPOS_DE_ENTRENAMIENTO` para por qué la copa, que
    sí cuenta para la historia de un equipo, no puede enseñar resultados.
    """
    filas, etiquetas, ids = [], [], []
    for p in partidos:
        if p.match_type not in TIPOS_DE_ENTRENAMIENTO:
            continue
        filas.append(variables(ratings_de(p, "home"), ratings_de(p, "away")))
        etiquetas.append(resultado(p))
        ids.append(p.ht_match_id)
    if not filas:
        return np.empty((0, len(COMPARACIONES))), np.empty(0, dtype=int), []
    return np.array(filas), np.array(etiquetas, dtype=int), ids


def probabilidades_de_partido(
    lecturas_local: Sequence[dict[str, Any]],
    lecturas_visitante: Sequence[dict[str, Any]],
    es_copa: bool = False,
    metodo: str = PitchZoneMethod.AVERAGE,
    factor_local: float = 1.0,
    factor_visitante: float = 1.0,
) -> Probabilidades | None:
    """La terna de un partido, de punta a punta.

    Entra lo que devuelven las pantallas de ratings --una lectura por partido
    visto de cada equipo, del más viejo al más reciente-- y sale victoria,
    empate y derrota vistas DESDE EL LOCAL.

    Es el único camino que la aplicación debería usar: si algún día hay que
    cambiar cómo se resume la historia o cómo se mezcla, se cambia aquí y no
    en cada pantalla.

    YA NO RECIBE UNA POISSON DE FUERA. Antes se mezclaba 90/10 con la del
    simulador de temporada, que estima fuerza a partir de los goles agregados
    de la liga. Ahora la Poisson vive dentro y es mejor para esto: mira los
    ratings del partido concreto en vez de la media de la temporada, y su peso
    actual (80 %) está medido en vez de elegido.

    Devuelve `None` si a alguno de los dos lados no le queda ni un partido que
    mirar. Ahí no se predice: se dice que no se puede.
    """
    mio = resumen_de_lecturas(lecturas_local, metodo, en_casa=True)
    suyo = resumen_de_lecturas(lecturas_visitante, metodo, en_casa=False)
    if mio is None or suyo is None:
        return None
    if es_copa:
        return probabilidades_de_copa(mio, suyo, factor_local, factor_visitante)
    return probabilidades_del_motor(mio, suyo, factor_local, factor_visitante)


def marcador_de_partido(
    lecturas_local: Sequence[dict[str, Any]],
    lecturas_visitante: Sequence[dict[str, Any]],
    metodo: str = PitchZoneMethod.AVERAGE,
    factor_local: float = 1.0,
    factor_visitante: float = 1.0,
) -> tuple[int, int] | None:
    """El resultado concreto más probable. Lo sabe la mitad de goles."""
    mio = resumen_de_lecturas(lecturas_local, metodo, en_casa=True)
    suyo = resumen_de_lecturas(lecturas_visitante, metodo, en_casa=False)
    if mio is None or suyo is None:
        return None
    return marcador_mas_probable(mio, suyo, factor_local, factor_visitante)


def goles_de_partido(
    lecturas_local: Sequence[dict[str, Any]],
    lecturas_visitante: Sequence[dict[str, Any]],
    metodo: str = PitchZoneMethod.AVERAGE,
    factor_local: float = 1.0,
    factor_visitante: float = 1.0,
) -> tuple[float, float] | None:
    """Cuántos goles espera marcar cada uno."""
    mio = resumen_de_lecturas(lecturas_local, metodo, en_casa=True)
    suyo = resumen_de_lecturas(lecturas_visitante, metodo, en_casa=False)
    if mio is None or suyo is None:
        return None
    return (
        goles_esperados(mio, suyo, factor_local),
        goles_esperados(suyo, mio, factor_visitante),
    )


def tabla_de_puntos_esperados(
    partidos: Sequence[tuple[int, int, Probabilidades]],
) -> dict[int, float]:
    """Cuántos puntos suma cada equipo en los partidos que le quedan.

    Cada entrada es (local, visitante, terna vista desde el local). El
    visitante recibe la misma terna del revés, que es lo que hace que la suma
    de los dos lados de un partido nunca pase de 4 --tres si alguien gana, dos
    si empatan-- sin tener que comprobarlo.
    """
    puntos: dict[int, float] = {}
    for local, visitante, p in partidos:
        puntos[local] = puntos.get(local, 0.0) + p.puntos_esperados
        vuelta = Probabilidades(p.derrota, p.empate, p.victoria)
        puntos[visitante] = puntos.get(visitante, 0.0) + vuelta.puntos_esperados
    return puntos


# ── El segundo modelo: una Poisson sobre los GOLES ──────────────────────────
#
# El ordinal contesta «¿quién gana?». Este contesta «¿cuántos goles marca
# cada uno?», y de ahí sale quién gana. Suena a rodeo y no lo es: un partido
# trae más información en su marcador que en su resultado, así que aprender
# de los goles usa datos que el ordinal tira.
#
# Y arregla el punto flaco del ordinal. Allí el empate depende de una franja
# estrecha entre dos umbrales y casi nunca gana; aquí sale solo, de que las
# dos Poisson den el mismo número. Medido con cinco cortes: en el tramo con
# más empates de la muestra el ordinal se fue a 0,826 de log-loss y esta se
# quedó en 0,704.
#
# UNA FILA POR LADO, no por partido. Los goles que marca un equipo dependen de
# SUS duelos ofensivos contra la defensa del otro, así que cada partido da dos
# observaciones y el mismo juego de coeficientes vale para los dos lados. Con
# 1.031 partidos son 2.062 filas para ajustar seis números.

#: Los cinco duelos de los que dependen los goles de un lado: el medio campo
#: --que da el balón-- más los tres carriles de ataque y el Balón Parado
#: ofensivo. Los defensivos NO entran: ya están dentro, porque cada duelo
#: enfrenta mi ataque contra su defensa.
DUELOS_OFENSIVOS: tuple[tuple[str, str, str], ...] = (
    ("medio", "midfield", "midfield"),
    ("ata_izq", "left_att", "right_def"),
    ("ata_cen", "central_att", "central_def"),
    ("ata_der", "right_att", "left_def"),
    ("bp_ata", "sp_att", "sp_def"),
)

#: LOS GOLES SON UN PRODUCTO DE POTENCIAS, no una suma. Reajustado el
#: 2026-09-08 sobre los 5.232 partidos:
#:
#:     eta   = 4,687 + 2,540 x log p(medio)
#:                     + 1,074 x log [p(ataIzq) p(ataCen) p(ataDer)]
#:     goles = exp(eta - 0,1445 x (eta - 0,356)^2)         <- juego abierto
#:           + exp(2,430 + 0,777 x log p(medio)
#:                       + 3,295 x log p(BPata))           <- balon parado
#:
#: con p(A vs B) = A/(A+B). Sin el termino cuadratico y con un solo sumando
#: eso seria un producto de potencias --como se leia hasta el 2026-09-08-- y
#: cada coeficiente seria una ELASTICIDAD: el porcentaje que crecen los goles
#: cuando ese duelo crece un uno por ciento. Con los dos anadidos ya no es
#: exactamente eso, pero la lectura sigue valiendo cerca del centro.
#:
#: DE DÓNDE SALE ESA FORMA. Es la misma Poisson de siempre --enlace
#: logarítmico, `log(goles) = intercepto + suma(coef x duelo)`-- pero con los
#: duelos entrando como `log(A/(A+B))` en vez de `A/(A+B)`. Al ser logaritmo
#: dentro y fuera, la suma se convierte en producto y cada coeficiente pasa a
#: ser una ELASTICIDAD: el porcentaje que crecen los goles cuando ese duelo
#: crece un uno por ciento. La forma multiplicativa no se impuso, salió sola.
#:
#: POR QUÉ ESTA FORMA Y NO OTRA. Se probaron seis maneras de medir un duelo y
#: ésta gana las seis medidas a la vez --error, verosimilitud, sesgo,
#: calibración y log-loss del resultado--. La anterior, `A/(A+B)`, aplastaba
#: los extremos: prometía goles de más donde se marcaba poco y de menos donde
#: se marcaba mucho. La pendiente de calibración pasó de 0,963 a 0,994.
#:
#: LOS TRES ATAQUES COMPARTEN COEFICIENTE, y no es una simplificación gratuita.
#: Sueltos salían 0,650 / 0,609 / 0,581 con errores de 0,05: indistinguibles.
#: Juntos se estima uno solo con el triple de datos y su error baja a 0,013.
#: El AIC mejora (30.600,7 contra 30.604,0) gastando DOS parámetros menos.
#: El Balón Parado no entra en el reparto: es otro tipo de ataque, y quitarlo
#: se rechaza de plano (razón de verosimilitud 275,6 con 1 gl, p = 7e-62).
#:
#: OJO CON LEER EL 1,031 DEL BALÓN PARADO literalmente. Ese duelo comparte el
#: 62 % de su varianza con los de ataque, así que buena parte de lo que mide
#: es «este equipo es bueno», no «los córners valen esto». Al quitarlo, el
#: mediocampo y los ataques suben a absorberlo (1,718 -> 1,972 y 0,614 ->
#: 0,735), que es la firma de una variable colineal.
#:
#: NO LLEVA TÉRMINO DE LOCAL, a propósito, y se volvió a comprobar con esta
#: forma: sale +0,0149 con p = 0,33 y el AIC empeora. La ventaja de campo ya
#: vive dentro de los ratings --el medio campo del local es un 19 % más alto--
#: así que sumarla otra vez sería contarla dos veces.
#:
#: Para rehacerlos: `scripts/poisson_final.py` los imprime con su diagnóstico.
#: ── El juego abierto ──────────────────────────────────────────────────
POISSON_JUEGO_INTERCEPTO = 4.75262
POISSON_JUEGO_MEDIO = 2.51368

#: LOS TRES CARRILES SE PROMEDIAN, NO SE MULTIPLICAN (2026-09-12).
#:
#: Hasta hoy el ataque entraba como `C · log(p_izq · p_cen · p_der)`, o sea la
#: MEDIA GEOMÉTRICA de los tres: un carril tapado hundía el ataque entero por
#: fuertes que fueran los otros dos. Eso describe un ataque en cadena, y
#: Hattrick no juega así, reparte las ocasiones POR carril.
#:
#: Ahora es una media ponderada de potencias:
#:
#:     log( 0,3·p_izq^C + 0,4·p_cen^C + 0,3·p_der^C )
#:
#: Los pesos son con qué frecuencia va el ataque por cada sitio, y el
#: exponente dice cuánto compensa un carril fuerte a uno tapado: hacia 0 haría
#: falta que funcionaran los tres --el caso límite es justo la forma vieja--,
#: y cuanto más alto, más manda el mejor carril. Sale 3,39, o sea que los
#: datos prefieren claramente la versión indulgente.
#:
#: MEDIDO, no elegido: sobre los 5.232 partidos de liga, con validación
#: cruzada de diez pliegues y comparación pareada partido a partido, gana a la
#: forma anterior en las DOS cosas -- resultado (p = 0,014) y goles
#: (p < 0,001). Se probó también dejar libre el exponente del centro: no
#: mejora (razón de verosimilitud p = 0,097), así que los tres comparten uno.
PESOS_DE_CARRIL = (0.3, 0.4, 0.3)
POISSON_JUEGO_CARRIL = 3.38551

#: LA DESCOMPRESIÓN. Un solo producto de potencias apretaba las lambdas hacia
#: el centro: donde prometía 0,76 se marcaban 0,68 y donde prometía 3,30 se
#: marcaban 3,55. Eso llenaba de marcadores bajos la rejilla --sobraban 233
#: partidos en el bloque de 0 y 1 goles-- y de ahí salían los 115 empates de
#: más.
#:
#: NO ERA UN PROBLEMA DE ESCALA: la regresión ya tenía la mejor recta, así que
#: una pendiente libre sobre el predictor lineal habría salido 1 por
#: construcción. Era de CURVATURA, y se corrige con el cuadrado del propio
#: predictor.
#:
#: TAMPOCO ERA DIXON-COLES, que es lo que uno probaría primero para el exceso
#: de empates: su rho sale +0,009 con p = 0,72. Esa corrección conserva los
#: marginales, así que sólo reparte masa DENTRO del bloque de marcadores bajos
#: y nunca la saca de él, que era justo lo que hacía falta.
POISSON_JUEGO_CUADRATICO = -0.14746

#: El centro sobre el que se mide la curvatura: la media del predictor lineal
#: en los 5.232 partidos del ajuste. Va junto a los coeficientes; sin ella el
#: término cuadrático significa otra cosa.
POISSON_ETA_MEDIA = 0.35161

#: ── El Balón Parado, aparte ───────────────────────────────────────────
#:
#: HASTA EL 2026-09-08 LOS GOLES ERAN UN SOLO PRODUCTO, así que
#: `p(medio)^1,72` multiplicaba también al Balón Parado: un equipo que perdía
#: el mediocampo veía hundida hasta su amenaza a balón parado. Eso no se
#: sostiene --un córner o una falta no dependen de la posesión como una jugada
#: elaborada-- y los datos lo confirman.
#:
#: Ahora son DOS SUMANDOS. La suma de dos Poisson sigue siendo Poisson, así
#: que el modelo de conteo no cambia; lo que cambia es que el Balón Parado
#: tiene su PROPIA dependencia del mediocampo:
#:
#:     juego abierto:  el mediocampo pesa 2,540
#:     balón parado:   el mediocampo pesa 0,777   <- TRES VECES MENOS
#:
#: Y no es cero: se probó hacerlo independiente del mediocampo (d = 0) y sale
#: PEOR (AIC 30.527,6 contra 30.500,0 con d libre). Tiene sentido: los córners
#: salen de atacar, y para atacar hace falta el balón. Lo que no se sostenía
#: era que dependieran TANTO como una jugada elaborada.
#:
#: De media reparte 1,45 goles al juego abierto (72 %) y 0,57 al balón parado
#: (28 %) sobre los 2,024 por lado de la muestra.
POISSON_BP_INTERCEPTO = 2.38119
POISSON_BP_MEDIO = 0.84696
POISSON_BP_BALON_PARADO = 3.18660

#: Tope del predictor del juego abierto, y es un seguro de verdad. El término
#: cuadrático es NEGATIVO, así que la parábola tiene vértice: pasado ese punto
#: la fórmula daría la vuelta y un equipo más fuerte marcaría MENOS. SE DERIVA
#: en vez de escribirse, porque el vértice se mueve si se reajusta el
#: cuadrático y una constante a mano se quedaría atrás en silencio.
#:
#: Con estos coeficientes cae en 3,742, y el máximo observado en los 5.232
#: partidos es 3,465: sólo 0,28 de margen. El tope SÍ se toca en cuanto
#: aparezca un equipo algo más fuerte que los de la muestra. Recortando a él,
#: el juego abierto se queda plano en su máximo en vez de bajar.
POISSON_JUEGO_ETA_MAXIMA = POISSON_ETA_MEDIA - 1 / (2 * POISSON_JUEGO_CUADRATICO)

#: Los de las dos versiones anteriores, por si hay que volver. Van juntos o no
#: significan nada.
#:
#:   un producto, duelos en A/(A+B) (hasta 2026-09-07):
#:     INTERCEPTO -3.63063 · BETA (3.01537, 1.38636, 1.31952, 1.34806, 1.85908)
#:   un producto, duelos en log(A/(A+B)) (2026-09-08, medio dia):
#:     INTERCEPTO 4.10278 · MEDIO 1.71820 · ATAQUE 0.61413 · BP 1.03091

#: Los de la forma anterior, `A/(A+B)` con los cinco coeficientes sueltos, por
#: si hay que volver. Van juntos o no significan nada.
#:
#:     POISSON_INTERCEPTO = -3.63063
#:     POISSON_BETA = (3.01537, 1.38636, 1.31952, 1.34806, 1.85908)

#: Suelo de una proporción antes de elevarla. Un cero no es un rating bajo, es
#: «no se sabe», y elevado a 1,718 mataría los goles del equipo entero. Igual
#: que `MAXIMO_GOLES_ESPERADOS`, está para un fallo de lectura: en los 6.094
#: partidos medidos el mínimo real de los nueve campos va de 1 a 5, así que no
#: toca ningún dato de verdad.
SUELO_DE_PROPORCION = 1e-3

#: Hasta cuántos goles se reparte la probabilidad. Más allá es despreciable.
TOPE_DE_GOLES = 12

#: Tope de goles esperados, como seguro y no como ajuste.
#:
#: La Poisson es exponencial y no tiene freno: con los cinco duelos a 0,75, un
#: partido que no existe, predice 26 goles. En los 2.062 lados reales el
#: máximo es 13,6 y ninguno tiene los cinco duelos por encima de 0,70, así que
#: este tope no toca nada de lo medido. Está para el día en que llegue un
#: rating absurdo por un fallo de lectura: mejor un 12-0 imposible que una
#: rejilla degenerada donde toda la probabilidad se va al último casillero.
MAXIMO_GOLES_ESPERADOS = 12.0


#: CUÁNTO CAMBIA LOS GOLES CADA TÁCTICA (2026-09-12).
#:
#: El modelo mira ratings y no sabe qué táctica se jugó, y eso deja un sesgo
#: medible: Presionar prometía medio gol de más, y Contraataques, Creativo y
#: Bandas algo de menos. Presionar recorta ocasiones a los dos equipos, y eso
#: no está en ningún rating.
#:
#: Cada número es `goles observados / goles predichos` de esa táctica sobre
#: los 5.232 partidos de liga, que es la máxima verosimilitud de un factor
#: multiplicativo en una Poisson. Los cuatro que de verdad se separan de 1
#: --su intervalo del 95 % no lo contiene-- son Presionar, Contraataques,
#: Creativo y Bandas; los otros tres se dejan por completud y porque están
#: tan cerca de 1 que no mueven nada.
#:
#: Medido fuera de muestra con validación cruzada de diez pliegues: corrige el
#: 80 % del sesgo cuando se sabe la táctica propia y se pondera la del rival.
FACTOR_POR_TACTICA: dict[int, float] = {
    0: 0.9889,  # Normal
    1: 0.7223,  # Presionar
    2: 1.1023,  # Contraataques
    3: 0.9922,  # Atacar por el centro
    4: 1.0566,  # Atacar por las bandas
    7: 1.1037,  # Jugar creativamente
    8: 0.9691,  # Tiros lejanos
}


def factor_de_tactica(
    reparto: dict[int, float] | None = None,
    exacta: int | None = None,
) -> float:
    """El factor que corrige los goles por la táctica, sabida o probable.

    `exacta` es para cuando NO hay que adivinar: tu propia alineación enviada
    trae su táctica. `reparto` es para el rival, y lleva cuántas veces usó
    cada táctica en los partidos vistos.

    SE PONDERA, NO SE APUESTA. Quedarse con la táctica más frecuente castiga
    dos veces cuando se falla: no corrige la que se jugó y corrige de más una
    que no. Promediar los factores por su frecuencia es la esperanza del
    factor, que es lo que toca cuando la táctica es incierta -- y medido
    recupera la mitad del sesgo en vez de un tercio.

    Sin información devuelve 1, o sea no tocar nada.
    """
    if exacta is not None:
        return FACTOR_POR_TACTICA.get(int(exacta), 1.0)
    if not reparto:
        return 1.0
    total = float(sum(reparto.values()))
    if total <= 0:
        return 1.0
    return sum(
        peso / total * FACTOR_POR_TACTICA.get(int(tactica), 1.0)
        for tactica, peso in reparto.items()
    )


def goles_esperados(mio: dict[str, float], suyo: dict[str, float], factor: float = 1.0) -> float:
    """Cuántos goles marca un equipo con esos ratings contra esos otros.

    El medio campo entra como elasticidad --multiplica-- y los tres carriles
    de ataque como una media ponderada de potencias: se PROMEDIAN, porque un
    carril tapado no anula el ataque, se ataca por otro. Ver
    `POISSON_JUEGO_CARRIL`.

    `factor` es la corrección por la táctica de QUIEN ATACA, que sale de
    `factor_de_tactica`. Vale 1 cuando no se sabe qué táctica va a jugar, que
    es como se comportaba esto hasta el 2026-09-12.
    """
    p = {
        clave: max(proporcion(mio[a], suyo[b]), SUELO_DE_PROPORCION)
        for clave, a, b in DUELOS_OFENSIVOS
    }
    log_medio = float(np.log(p["medio"]))
    # Con qué se ataca: cada carril elevado al exponente y pesado por lo que
    # se ataca por ahí. El logaritmo de esa media es lo que entra en la recta.
    peso_izq, peso_cen, peso_der = PESOS_DE_CARRIL
    carriles = (
        peso_izq * p["ata_izq"] ** POISSON_JUEGO_CARRIL
        + peso_cen * p["ata_cen"] ** POISSON_JUEGO_CARRIL
        + peso_der * p["ata_der"] ** POISSON_JUEGO_CARRIL
    )
    # El juego abierto: la recta y la curvatura encima. En logaritmos porque
    # el término cuadrático sólo existe en esta escala.
    eta = min(
        POISSON_JUEGO_INTERCEPTO
        + POISSON_JUEGO_MEDIO * log_medio
        + float(np.log(max(carriles, SUELO_DE_PROPORCION))),
        POISSON_JUEGO_ETA_MAXIMA,
    )
    juego = float(np.exp(eta + POISSON_JUEGO_CUADRATICO * (eta - POISSON_ETA_MEDIA) ** 2))
    # El balón parado, con su propia dependencia del mediocampo.
    balon_parado = float(
        np.exp(
            POISSON_BP_INTERCEPTO
            + POISSON_BP_MEDIO * log_medio
            + POISSON_BP_BALON_PARADO * float(np.log(p["bp_ata"]))
        )
    )
    return min((juego + balon_parado) * factor, MAXIMO_GOLES_ESPERADOS)


def _reparto_de_goles(media: float) -> np.ndarray:
    """Probabilidad de marcar 0, 1, 2… goles, hasta el tope."""
    k = np.arange(TOPE_DE_GOLES + 1)
    # Por logaritmos y no con factoriales sueltos: `media**12 / 12!` es un
    # número enorme partido por otro enorme, y en coma flotante eso se
    # degrada mucho antes de que la probabilidad deje de importar.
    log = (
        -media
        + k * np.log(max(media, 1e-9))
        - np.array([float(np.sum(np.log(np.arange(1, x + 1)))) if x else 0.0 for x in k])
    )
    p = np.exp(log)
    return np.asarray(p / p.sum(), dtype=float)


def probabilidades_poisson(
    mio: dict[str, float],
    suyo: dict[str, float],
    factor_mio: float = 1.0,
    factor_suyo: float = 1.0,
) -> Probabilidades:
    """Victoria, empate y derrota del local, vía los goles de cada uno.

    Las dos Poisson se tratan como independientes. No lo son del todo --un
    equipo que va perdiendo se abre-- pero medido en la muestra la corrección
    clásica de Dixon-Coles mueve el log-loss menos de 0,002, y no se paga un
    parámetro más por eso.
    """
    rejilla = np.outer(
        _reparto_de_goles(goles_esperados(mio, suyo, factor_mio)),
        _reparto_de_goles(goles_esperados(suyo, mio, factor_suyo)),
    )
    # Debajo de la diagonal el local marca MÁS, o sea que gana. Encima pierde.
    # Escrito así porque al revés no falla: da probabilidades perfectamente
    # válidas y sistemáticamente invertidas, que es mucho peor.
    victoria = float(np.tril(rejilla, -1).sum())
    empate = float(np.trace(rejilla))
    derrota = float(np.triu(rejilla, 1).sum())
    total = victoria + empate + derrota
    return Probabilidades(victoria / total, empate / total, derrota / total)


def marcador_mas_probable(
    mio: dict[str, float],
    suyo: dict[str, float],
    factor_mio: float = 1.0,
    factor_suyo: float = 1.0,
) -> tuple[int, int]:
    """El resultado concreto más probable. Lo da la Poisson, no el ordinal."""
    rejilla = np.outer(
        _reparto_de_goles(goles_esperados(mio, suyo, factor_mio)),
        _reparto_de_goles(goles_esperados(suyo, mio, factor_suyo)),
    )
    local, visitante = np.unravel_index(int(np.argmax(rejilla)), rejilla.shape)
    return int(local), int(visitante)


#: Cuánto pesa cada modelo al unirlos. Desde el 2026-09-20: todo la Poisson.
#:
#: DECISIÓN DEL USUARIO, tomada sobre el barrido entero con las dos mitades
#: tal como corren (`scripts/barrido_de_la_mezcla.py`, 5.232 partidos):
#:
#:     peso goles   0,00   0,20   0,60   0,80   0,90   1,00
#:     log-loss   0,6703 0,6641 0,6591 0,6584 0,6585 0,6588
#:     aciertos    0,711  0,712  0,712  0,713  0,713  0,713
#:     AUC vic     0,873  0,875  0,876  0,877  0,877  0,877
#:     empate         ok     ok     ok     ok     NO     NO
#:
#: LO QUE DICE ESA TABLA, y conviene leerlo entero antes de tocar nada:
#:
#: · En PUNTERÍA la ordinal no aportaba. Del 80 % al 100 % el log-loss sube
#:   0,0004 --seis centésimas de por ciento-- y el acierto y el AUC no se
#:   mueven a tres decimales. Quien esperara que quitarla empeorara las
#:   predicciones, no: no las cambia.
#:
#: · En el EMPATE sí aportaba, y es lo que se ha perdido. A 1,00 el modelo
#:   promete 806 empates y ocurren 733, y el error de calibración se sale de
#:   la banda del azar. La rejilla de marcadores conserva un exceso de
#:   resultados bajos y la ordinal era lo que lo sujetaba.
#:
#: · En pantalla el cambio es pequeño pero no nulo: la mediana de los
#:   partidos se mueve 0,6 puntos porcentuales, el peor caso 10,3, y el
#:   «resultado más probable» cambia en 58 de 5.232 partidos.
#:
#: VOLVER ATRÁS ES CAMBIAR ESTOS DOS NÚMEROS. La ordinal sigue entera unas
#: líneas más arriba y `probabilidades_del_motor` la vuelve a llamar en cuanto
#: el peso deje de ser cero.
PESO_ORDINAL = 0.0
PESO_GOLES = 1.0


def probabilidades_del_motor(
    mio: dict[str, float],
    suyo: dict[str, float],
    factor_mio: float = 1.0,
    factor_suyo: float = 1.0,
) -> Probabilidades:
    """Los dos modelos propios, unidos. Es la predicción de la casa.

    De aquí salen las tres probabilidades y, de ellas, todo lo demás: los
    puntos esperados, el marcador más probable y la simulación de la liga.
    Una sola terna por partido, para que dos partes de la pantalla no puedan
    decir cosas distintas del mismo encuentro.
    """
    goles = probabilidades_poisson(mio, suyo, factor_mio, factor_suyo)
    if PESO_ORDINAL <= 0.0:
        # Con la ordinal a cero se salta su cuenta entera en vez de
        # multiplicarla por cero: son once parámetros y una sigmoide por
        # partido, y esto se llama una vez por cada cruce pendiente de la
        # serie. La rama existe para que poner el peso a cero SIGNIFIQUE
        # apagarla, no ejecutarla en balde.
        return goles
    ordinal = modelo_ajustado().probabilidades(variables(mio, suyo))
    return Probabilidades(
        PESO_ORDINAL * ordinal.victoria + PESO_GOLES * goles.victoria,
        PESO_ORDINAL * ordinal.empate + PESO_GOLES * goles.empate,
        PESO_ORDINAL * ordinal.derrota + PESO_GOLES * goles.derrota,
    )


def probabilidades_de_copa(
    mio: dict[str, float],
    suyo: dict[str, float],
    factor_mio: float = 1.0,
    factor_suyo: float = 1.0,
) -> Probabilidades:
    """Un partido de copa, donde no puede haber empate.

    Hay prórroga y penaltis: alguien tiene que pasar. Se comprobó en los datos
    --861 partidos de copa recogidos, CERO empates-- así que enseñar una
    probabilidad de empate ahí sería enseñar algo imposible.

    Lo que se hace es repartir esa probabilidad entre las otras dos en la
    proporción en que ya estaban, que es lo que dice el propio modelo sobre
    quién es mejor. NO se reentrena nada para copa: los 861 partidos que hay
    tienen al débil de local sistemáticamente --el sorteo cruza divisiones-- y
    aprender de ahí enseñaría que jugar en casa perjudica.
    """
    p = probabilidades_del_motor(mio, suyo, factor_mio, factor_suyo)
    decidido = p.victoria + p.derrota
    if decidido <= 0:
        return Probabilidades(0.5, 0.0, 0.5)
    return Probabilidades(p.victoria / decidido, 0.0, p.derrota / decidido)
