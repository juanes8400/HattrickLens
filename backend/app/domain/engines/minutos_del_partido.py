"""Quién estuvo en qué puesto y cuántos minutos, reconstruido del partido.

QUÉ PROBLEMA RESUELVE. Hattrick no publica los minutos por puesto en ningún
campo. `playerdetails.xml` da, en `<LastMatch>`, UN `PositionCode` --el puesto
en el que el jugador acabó-- y el TOTAL de `PlayedMinutes`. Con eso, un jugador
que hizo 87 minutos de lateral y 3 de extremo llega como «extremo, 90 minutos»,
y el entrenamiento se le calcula entero sobre el puesto equivocado.

Lo reportó un usuario el 2026-10-08 con su jugador 513909842: con
entrenamiento de Lateral, el extremo recibe el 100 % y el lateral el 50 %, así
que sus 87′ + 3′ valen el 51,7 % de la semana y la aplicación le enseñaba el
100 %. El error va en los dos sentidos: al que empieza de extremo y lo pasan a
lateral en el minuto 87 se le quita el entrenamiento que sí se ganó.

DE DÓNDE SALE LO QUE HACE FALTA. De `matchlineup.xml` 2.1, que la aplicación ya
descarga para enseñar el once que de verdad salió:

  · `<StartingLineup>`  el once inicial, cada uno con su `RoleID`.
  · `<Substitutions>`   cada orden, con `MatchMinute`, quién sale, quién entra
                        y `NewPositionId`.

POR QUÉ NO SE MIRA `OrderType`. Hattrick tiene tres clases de orden --sustituir,
reubicar a un jugador y intercambiar a dos-- y cada una trae su código. Aquí se
decide por el ESTADO del partido en ese minuto, no por el código: si el jugador
al que la orden manda a un puesto ya estaba jugando, nadie entra y lo que hay
es un movimiento; si no estaba, es una sustitución. Sale lo mismo, no hay que
interpretar ningún número, y el día que Hattrick añada una clase de orden nueva
esto la reparte igual en vez de ignorarla.

QUÉ NO SABE. Cuándo se fue el que no salió por una orden --el expulsado, el
lesionado sin cambio--. Para eso está `minutos_totales`: el total que Hattrick
sí publica por jugador, con el que se cierra su último tramo. Sin ese dato se
cierra al final del partido, que es lo que pasaba antes con todo.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Lo que dura un partido, salvo que el total de alguien diga otra cosa.
MINUTOS_DEL_PARTIDO = 90


@dataclass(frozen=True, slots=True)
class Titular:
    """Un jugador del once inicial, con el puesto en el que salió."""

    ht_player_id: int
    position_code: int


@dataclass(frozen=True, slots=True)
class Orden:
    """Una orden ejecutada: sustitución, reubicación o intercambio.

    `sale` y `entra` son los dos jugadores que nombra la orden, tal como los
    manda Hattrick (`SubjectPlayerID` y `ObjectPlayerID`). Qué significan
    depende de quién estuviera en el campo, y eso lo decide `tramos_del_partido`.
    """

    minuto: int
    sale: int
    entra: int
    nuevo_puesto: int


@dataclass(frozen=True, slots=True)
class Tramo:
    """Un jugador, un puesto y los minutos que estuvo ahí.

    `desde` es el minuto DEL PARTIDO en que empezó el tramo. Viaja porque el
    entrenamiento se corta a los 90 minutos aunque el partido siga: sin saber
    cuándo ocurrió cada tramo no hay forma de decir cuáles caen dentro.
    """

    ht_player_id: int
    position_code: int
    minutos: int
    desde: int = 0


def tramos_del_partido(
    titulares: list[Titular],
    ordenes: list[Orden],
    minutos_totales: dict[int, int] | None = None,
    duracion: int | None = None,
) -> list[Tramo]:
    """Los tramos de todos los que jugaron, del minuto 0 al final.

    `minutos_totales` son los minutos que Hattrick publica por jugador. Hacen
    dos cosas, y las dos se comprobaron contra el partido 771779994 del
    2026-10-07:

    · Cierran el tramo de quien se fue sin que lo sustituyeran. Ahí, el extremo
      461351045 figura en el once y no sale en ninguna orden, pero Hattrick le
      cuenta 87 minutos: se lesionó o lo expulsaron. Sin su total se le darían
      los noventa.
    · Dicen cuánto duró el partido. Ese duró 91 minutos, no 90, y el suplente
      que entró en el 89 jugó 2 según Hattrick. Con el 90 cableado salía 1.

    `duracion` en `None` la deduce de ahí, que es lo normal. Pasarla a mano es
    para las pruebas y para un partido del que no se sepa ningún total.
    """
    totales = minutos_totales or {}
    if duracion is None:
        duracion = max(MINUTOS_DEL_PARTIDO, max(totales.values(), default=0))
    # En el campo AHORA: jugador → (puesto, minuto en que llegó a ese puesto).
    campo: dict[int, tuple[int, int]] = {t.ht_player_id: (t.position_code, 0) for t in titulares}
    tramos: list[Tramo] = []
    # Lo que cada uno lleva jugado. Hace falta porque `minutos_totales` cuenta
    # MINUTOS JUGADOS y el campo guarda MINUTOS DE PARTIDO, que no son lo mismo
    # en cuanto alguien entra desde el banquillo: el que sale en el 70 y juega
    # 20 se va en el minuto 90, no en el 20.
    jugados: dict[int, int] = {}

    def cerrar(jugador: int, minuto: int) -> None:
        """Guarda lo que llevaba este jugador en su puesto actual."""
        if jugador not in campo:
            return
        puesto, desde = campo.pop(jugador)
        if minuto > desde:
            tramos.append(Tramo(jugador, puesto, minuto - desde, desde))
            jugados[jugador] = jugados.get(jugador, 0) + (minuto - desde)

    for orden in sorted(ordenes, key=lambda o: o.minuto):
        minuto = max(0, min(orden.minuto, duracion))
        # QUIÉN SE MUEVE. `entra` es a quien la orden manda a `nuevo_puesto`.
        # Si ya estaba jugando, no entra nadie: se mueve. Si no estaba, entra
        # y el otro deja su sitio.
        movimiento = orden.entra in campo
        if movimiento:
            # UNA ORDEN QUE NO MUEVE NADA no parte el tramo en dos. En el
            # partido de seleccion 41943634 (fixture real) hay dos ordenes que
            # mandan a un jugador al puesto que YA ocupaba, y sin esto salia
            # «Mediocentro izquierdo 60′ + Mediocentro izquierdo 30′»: el mismo
            # total, pero ilegible en pantalla.
            mismo_sitio = campo[orden.entra][0] == orden.nuevo_puesto
            sin_pareja = not orden.sale or orden.sale == orden.entra
            if mismo_sitio and sin_pareja:
                continue
            # El intercambio nombra a dos que están dentro: el segundo se queda
            # con el puesto que el primero acaba de dejar. La reubicación
            # nombra a uno solo --Hattrick repite su id, o manda 0-- y entonces
            # no hay nadie a quien darle nada.
            puesto_liberado = campo[orden.entra][0]
            cerrar(orden.entra, minuto)
            campo[orden.entra] = (orden.nuevo_puesto, minuto)
            if orden.sale and orden.sale != orden.entra and orden.sale in campo:
                cerrar(orden.sale, minuto)
                campo[orden.sale] = (puesto_liberado, minuto)
        else:
            cerrar(orden.sale, minuto)
            if orden.entra:
                campo[orden.entra] = (orden.nuevo_puesto, minuto)

    for jugador in list(campo):
        # El expulsado y el lesionado sin cambio no aparecen en ninguna orden;
        # su total es lo único que dice cuándo se fueron.
        _, desde = campo[jugador]
        total = totales.get(jugador)
        if total is None:
            final = duracion
        else:
            le_queda = max(0, total - jugados.get(jugador, 0))
            final = min(duracion, desde + le_queda)
        cerrar(jugador, final)

    return tramos


def mejores_minutos(
    pesados: list[tuple[int, float]], tope: int = MINUTOS_DEL_PARTIDO
) -> list[tuple[int, float]]:
    """Los `tope` minutos que MEJOR entrenan, de los que el jugador jugó.

    REGLA DEL USUARIO, 2026-10-09. El entrenamiento se corta en 90 minutos
    aunque el partido tenga prórroga, pero no son los primeros noventa: son los
    noventa que más entrenan. Se coge toda la tanda del peso más alto, luego la
    siguiente, y así hasta llenar el cupo.

    Su ejemplo, con entrenamiento de Lateral --el extremo recibe el 100 %, el
    lateral el 50 %-- y un jugador con 45 minutos de lateral y 75 de extremo,
    120 en total:

        75 minutos al 100 %  (todo el extremo, que es lo que más vale)
        15 minutos al  50 %  (lo que cabe en los 90 menos los 75 ya cogidos)
        ---------------------------------------------------------------
        82,5 minutos equivalentes = 91,7 % de la semana

    Coger los primeros noventa del reloj habría dado 45 al 50 % más 45 al
    100 %, un 75 %: casi diecisiete puntos menos por un orden que el jugador no
    eligió.

    `pesados` son pares `(minutos, peso)`, y el peso sale de la tabla de
    puestos de quien llama: aquí no se sabe --ni hace falta saber-- qué se está
    entrenando. Se devuelven los trozos elegidos, no un número, para que la
    pantalla pueda enseñar el reparto tal como lo explicó el usuario.
    """
    elegidos: list[tuple[int, float]] = []
    restante = tope
    for minutos, peso in sorted(pesados, key=lambda par: par[1], reverse=True):
        if restante <= 0:
            break
        usados = min(max(minutos, 0), restante)
        if usados > 0 and peso > 0:
            elegidos.append((usados, peso))
        restante -= usados
    return elegidos
