"""Qué valores se movieron desde la última vez que entraste.

2026-11-07, pedido del usuario: «Cambios: advertir qué movimientos de valor de
los jugadores ocurrieron al conectar, con umbrales (±5 % del valor)».

EL DATO YA ESTABA. `market_estimates` guarda una lectura por cambio --no por
fecha-- desde que existe la gráfica del precio comparable, así que el valor de
cualquier jugador en cualquier momento pasado se puede leer sin pedir nada a
Hattrick. Lo que faltaba era decirlo al entrar, que es cuando importa: un
jugador que vale un 30 % más que la semana pasada es una decisión, y hasta hoy
había que ir a buscarlo a su ficha.

TRES COSAS DISTINTAS, Y SE CUENTAN APARTE. La tentación es hacer una resta y
sacar un porcentaje, pero hay tres casos que no son el mismo y mezclarlos
inventaría movimientos que no ocurrieron:

· **Un movimiento de verdad.** Mismo jugador, mismos criterios de búsqueda,
  número antes y número ahora, y la diferencia pasa del umbral. Ésta es la
  única que lleva porcentaje.

· **Un estreno.** Antes no había número --no había ventas cerradas bastantes
  para dar uno-- y ahora sí. Es noticia, y de las buenas, pero no tiene
  porcentaje: no se puede dividir por lo que no había. Se cuenta aparte.

· **Un cambio de con quién se compara.** El jugador cumplió años, o le subió
  una habilidad, y desde ese día Hattrick lo compara con OTRA gente. Cambió la
  pregunta, no la respuesta, así que esto NO es un movimiento del mercado y va
  en su propio grupo con su nota: el proyecto ya decidió el 2026-10-26 que
  entonces la gráfica del precio vuelve a empezar, porque unir los dos tramos
  dibuja una subida que no ocurrió.

  LLEVA PORCENTAJE IGUAL, por decisión del usuario del 2026-11-07. Se lo
  discutí --un 18 % ahí no dice que el mercado se moviera-- y lo reafirmó con
  razón: el número que él ve en Valor de Plantilla sí cambió un 18 %, y el
  total de su plantilla con él. Callar la cifra no la hacía desaparecer, sólo
  obligaba a calcularla a mano. Lo que queda separado es el SIGNIFICADO, que
  es lo que de verdad había que no mezclar.

Y UNA CUARTA QUE NO SE AVISA: el que tenía número y lo perdió. Pasa cuando sus
comparables caducan sin que entren otros, y no es que el jugador valga menos
--es que dejamos de saberlo--. Se cuenta para poder decir cuántos, sin
dramatizarlo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

#: Cuánto tiene que moverse un valor para que se avise, en por ciento.
#:
#: CINCO, y lo puso el usuario el 2026-11-07: «con umbrales (±5 % del valor)».
#: Es simétrico a propósito --sube y baja cuentan igual-- porque una caída del
#: 8 % en lo que vale un jugador es exactamente la misma noticia que una
#: subida, y sólo avisar de lo bueno sería un informe que miente por omisión.
#:
#: Por qué hace falta un umbral y no se avisa de todo: una lectura se anota en
#: cuanto el número cambia aunque sea en un euro, así que sin umbral cada
#: sincronización traería la plantilla entera y el aviso no diría nada.
MOVIMIENTO_QUE_SE_AVISA = 5.0


@dataclass(frozen=True, slots=True)
class Lectura:
    """Lo que decía el valor de un jugador en un momento dado.

    `valor` es la MEDIA ponderada y no la mediana, porque es la que la pantalla
    de Valor de Plantilla enseña como el valor de un jugador y la que suma en
    el total. Avisar sobre una cifra distinta de la que se lee sería dar dos
    valores del mismo jugador.

    `criterios` es la ventana con la que de verdad se le buscó comparables ese
    día. Es lo que distingue un movimiento del mercado de un cambio de
    pregunta, y por eso viaja.
    """

    ht_player_id: int
    nombre: str
    #: `None` cuando ese día no había número: no es cero, es que no se sabía.
    valor: int | None
    criterios: str
    #: Con cuántas ventas cerradas se hizo. Un movimiento apoyado en dos
    #: ventas y otro apoyado en diez no merecen la misma confianza.
    n: int
    cuando: datetime


@dataclass(frozen=True, slots=True)
class Movimiento:
    """Un valor que se movió lo bastante para contarlo.

    `clase` dice cuál de los tres casos es, y la pantalla los agrupa por ella:

    · `"movimiento"` --mismo jugador, misma gente, con porcentaje--
    · `"estreno"`    --antes no había número, así que sin porcentaje--
    · `"otra gente"` --cambiaron los criterios: con porcentaje, pero no es un
                       movimiento del mercado--
    · `"perdido"`    --había número y ya no, así que sin porcentaje--
    """

    ht_player_id: int
    nombre: str
    clase: str
    antes: int | None
    ahora: int | None
    diferencia: int | None
    #: `None` SÓLO cuando no hay nada por lo que dividir: un estreno no tenía
    #: número antes, y un perdido no lo tiene ahora. Un 0 % ahí se leería como
    #: «no se movió», que es justo lo contrario.
    #:
    #: El cambio de criterios SÍ lo lleva, desde el 2026-11-07: los dos valores
    #: existen, así que el porcentaje existe. Lo que no existe es la lectura
    #: «el mercado lo movió», y eso lo dice el grupo, no la ausencia del
    #: número.
    porcentaje: float | None
    n_antes: int
    n_ahora: int
    desde: datetime
    hasta: datetime


def movimiento_de(
    antes: Lectura | None,
    ahora: Lectura,
    umbral: float = MOVIMIENTO_QUE_SE_AVISA,
) -> Movimiento | None:
    """Clasifica el paso de una lectura a otra, o `None` si no hay nada que
    contar.

    `antes` puede faltar --un jugador que llegó entre las dos lecturas-- y eso
    NO es un estreno del valor: es un jugador nuevo, y de eso ya avisa Cambios
    por su cuenta. Devolver un estreno aquí lo anunciaría dos veces.

    EL ORDEN DE LAS PREGUNTAS IMPORTA. Los criterios se miran ANTES del
    porcentaje: si cambiaron, la resta no significa nada, por grande que sea.
    """
    if antes is None:
        return None

    def _como(
        clase: str,
        *,
        valor_antes: int | None,
        valor_ahora: int | None,
        diferencia: int | None = None,
        porcentaje: float | None = None,
    ) -> Movimiento:
        """Un movimiento con lo que es igual en los cuatro casos ya puesto.

        Se escribe como funcion y no como un diccionario que se desempaqueta
        porque desempaquetar pierde los tipos: `**comun` deja a mypy con un
        `dict[str, object]` y las seis columnas comunes dejan de comprobarse.
        """
        return Movimiento(
            ht_player_id=ahora.ht_player_id,
            nombre=ahora.nombre,
            clase=clase,
            antes=valor_antes,
            ahora=valor_ahora,
            diferencia=diferencia,
            porcentaje=porcentaje,
            n_antes=antes.n,
            n_ahora=ahora.n,
            desde=antes.cuando,
            hasta=ahora.cuando,
        )

    # Lo perdió. No vale menos: dejamos de saber lo que vale.
    if ahora.valor is None:
        if antes.valor is None:
            return None
        return _como("perdido", valor_antes=antes.valor, valor_ahora=None)

    # Lo estrenó.
    if antes.valor is None or antes.valor <= 0:
        return _como("estreno", valor_antes=antes.valor, valor_ahora=ahora.valor)

    # Cambió con quién se le compara. La resta NO es un movimiento del mercado
    # --cambió la pregunta, no la respuesta-- y por eso sigue en su propio
    # grupo, con su nota al lado.
    #
    # PERO LLEVA PORCENTAJE (2026-11-07, pedido del usuario: «quiero que se
    # notifique el cambio en % de valoración así haya habido cambio de edad y
    # lo otro»). Lo había pedido sin él y se lo discutí: un 18 % ahí no dice
    # que el mercado se moviera. Lo reafirmó, y tiene su razón: el número que
    # ve en Valor de Plantilla SÍ cambió un 18 %, y la suma de su plantilla con
    # él. Callar la cifra no hacía que la cifra no existiera; sólo obligaba a
    # calcularla a mano.
    #
    # El umbral se le aplica igual. Sin él, un cumpleaños que mueve la cifra un
    # 1 % saldría en el informe de cada jugador que cumpla años, y el grupo se
    # llenaría de ruido justo por ser el que menos acción pide.
    if antes.criterios != ahora.criterios:
        diferencia = ahora.valor - antes.valor
        if not diferencia:
            return None
        porcentaje = diferencia / antes.valor * 100
        if abs(porcentaje) < umbral:
            return None
        return _como(
            "otra gente",
            valor_antes=antes.valor,
            valor_ahora=ahora.valor,
            diferencia=diferencia,
            porcentaje=porcentaje,
        )

    diferencia = ahora.valor - antes.valor
    porcentaje = diferencia / antes.valor * 100
    if abs(porcentaje) < umbral:
        return None
    return _como(
        "movimiento",
        valor_antes=antes.valor,
        valor_ahora=ahora.valor,
        diferencia=diferencia,
        porcentaje=porcentaje,
    )


def ordenados(movimientos: list[Movimiento]) -> list[Movimiento]:
    """De lo que más mueve una decisión a lo que menos.

    Primero los movimientos de verdad, por tamaño del porcentaje y sin mirar el
    signo: una caída del 20 % pide tanta atención como una subida del 20 %.
    Luego los estrenos por su cifra, luego los cambios de criterios, y al final
    los perdidos, que son los que menos se puede hacer con ellos.
    """
    orden = {"movimiento": 0, "estreno": 1, "otra gente": 2, "perdido": 3}
    return sorted(
        movimientos,
        key=lambda mv: (
            orden.get(mv.clase, 9),
            -abs(mv.porcentaje or 0),
            -(mv.ahora or mv.antes or 0),
            mv.nombre,
        ),
    )
