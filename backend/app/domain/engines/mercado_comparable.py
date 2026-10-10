"""Qué ha costado en el mercado la gente que se parece a un jugador tuyo.

Diseñado con el usuario a lo largo del 2026-10-05 y cerrado el 2026-10-06,
pregunta a pregunta. La regla es suya de principio a fin, y eso importa por
`AGENTS.md`: aquí no se ajusta ningún parámetro contra la plantilla propia. Lo
que hay es estadística descriptiva sobre ventas ajenas con unos pesos que él
fijó.

QUÉ AFIRMA EL NÚMERO, que es lo primero que decidió: **lo que ha costado gente
como él**, no lo que te darían por él. Al ser una descripción y no una
predicción, no se corrige por forma, experiencia, especialidad ni bonos de
club de origen. Nada de eso entra.

DE QUÉ ESTÁ HECHO. De **ventas cerradas**. Una subasta con puja sirve de precio
provisional mientras tanto, porque con puja la venta está garantizada, pero
sólo hasta que se pueda preguntar cuánto se pagó de verdad. Eso no es un
tecnicismo: el 2026-10-05 Valerio Cataldi tenía 65.000.000 de puja y cerró en
77.720.000, un 16% por encima. El provisional no sólo es incierto, se queda
corto.

A QUIÉN SE PARECE. A las TRES habilidades más altas de las seis de campo. La
resistencia y el balón parado no cuentan, igual que no cuentan en el propio
buscador de Hattrick. Y tienen que ser las mismas tres, en el mismo orden: a
quien le gana el desempate otra habilidad al mismo nivel es otro jugador, y el
usuario lo decidió mirando un caso concreto que costó la única puja de aquella
medición.

LA ESCALERA. Cinco escalones que se van abriendo, y se para en cuanto reúne
seis. La terciaria lleva siempre la misma ventana, un nivel por arriba y dos
por abajo.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

# El orden de desempate, dictado por el usuario el 2026-10-04, y también la
# lista entera de habilidades que cuentan: seis, sin resistencia ni balón
# parado. Cambiarlo cambia a qué jugador se parece cada jugador.
ORDEN_DE_DESEMPATE: tuple[str, ...] = (
    "playmaking",
    "keeper",
    "defending",
    "scoring",
    "winger",
    "passing",
)

_RANGO = {habilidad: puesto for puesto, habilidad in enumerate(ORDEN_DE_DESEMPATE)}

#: Cuántos comparables hacen falta para cerrar la búsqueda y dar un número.
OBJETIVO = 6

#: La ventana de la terciaria, igual en todos los escalones: un nivel por
#: encima y dos por debajo.
TERCIARIA_ARRIBA = 1
TERCIARIA_ABAJO = 2

#: Cuánto vive un dato antes de volverse reemplazable. No se borra al
#: cumplirlo: queda a la espera de que algo mejor lo sustituya, y si no
#: aparece nada se queda, porque un dato viejo informa más que ninguno.
VIDA = timedelta(weeks=7)

#: Cuántos grupos de rotación de los escalones ANCHOS (<100 %). Cada semana le
#: toca a uno, así que a cada jugador le toca cada cinco semanas.
GRUPOS = 5

#: Cada cuántos días se vuelve a buscar el escalón EXACTO de un jugador
#: (2026-10-09, decisión del usuario). El exacto es el mejor dato que puede
#: existir para él --misma edad y las tres habilidades clavadas-- y no caduca,
#: así que refrescarlo seguido es lo que hace que el fondo no envejezca.
#:
#: SEIS Y NO SIETE a propósito: con siete, a cada jugador le tocaría siempre el
#: mismo día de la semana y vería siempre el mismo trozo del mercado. Con seis,
#: su turno se adelanta un día cada semana y acaba pasando por todos.
#:
#: El grupo sale del propio identificador, igual que el de los anchos: no hay
#: reloj que guardar por jugador, ni que recolocar al fichar o vender.
DIAS_DEL_EXACTO = 6

#: Lo que se le resta a la actualización económica para fijar el disparador.
ANTICIPO = timedelta(hours=24)

#: Nadie juega en el primer equipo con menos de 17 años.
EDAD_MINIMA = 17

#: Lo que se espera tras el cierre de una subasta antes de preguntar por el
#: precio: NADA. Se pregunta en cuanto el plazo que tenemos anotado ha pasado.
#:
#: Fueron dos horas, y el 2026-10-09 tres dias --«cuando se sabe que debio
#: terminar»-- hasta que se vio lo que costaban: desde que la media solo cuenta
#: ventas cerradas, una venta no entra en ningun numero hasta que se resuelve,
#: asi que cada hora de margen es una hora que el precio del jugador no se
#: mueve. El usuario lo zanjo el mismo dia: «busca en cuanto tengas anotado que
#: la subasta termina».
#:
#: El plazo es un dato de Hattrick, no una estimacion: viene en el anuncio. Si
#: al preguntar el traspaso todavia no esta registrado, para eso estan los
#: reintentos --medido el 2026-10-07 con Guido Bernacki: el traspaso aparecio
#: con el plazo desviado trece segundos--.
MARGEN_TRAS_EL_PLAZO = timedelta(0)

#: Cuántas veces se reintenta una resolución que no encontró la venta.
#:
#: Eran dos intentos hasta el 2026-10-07, con el argumento de que insistir
#: sería gastar llamadas en balde. El argumento estaba del revés: con puja
#: la venta está GARANTIZADA, así que no encontrarla no significa que no
#: exista, significa que todavía no la hemos visto. Insistir no gasta en
#: balde, espera a que Hattrick la registre.
#:
#: Comprobado ese día con Guido Bernacki: entró con 4.990.000 de puja y
#: plazo 11:01:13Z, cerró, y el traspaso apareció con plazo 11:01:00Z
#: --trece segundos-- y precio 5.090.000.
REINTENTOS_DE_RESOLUCION = 5


class Perfilado(Protocol):
    """Cualquiera a quien se le pueda medir el parecido.

    Lo cumplen el jugador del mercado recién leído y la venta ya guardada en
    el fondo, que es justo lo que permite recalcular el peso de una venta
    vieja contra un jugador nuevo.
    """

    @property
    def edad(self) -> int: ...

    @property
    def primaria(self) -> Rasgo: ...

    @property
    def secundaria(self) -> Rasgo: ...

    @property
    def terciaria(self) -> Rasgo: ...


@dataclass(frozen=True, slots=True)
class Rasgo:
    """Una habilidad con su nivel."""

    habilidad: str
    nivel: int


@dataclass(frozen=True, slots=True)
class Escalon:
    """Cuánto se abre la búsqueda, y lo que vale lo que entre por ahí.

    `edad_desde` y `edad_hasta` son desplazamientos sobre la edad del jugador,
    no un radio: los dos últimos escalones piden un año concreto, no un
    intervalo. `primaria` y `secundaria` sí son radios.
    """

    edad_desde: int
    edad_hasta: int
    primaria: int
    secundaria: int
    peso: int


# La escalera que cerró el usuario el 2026-10-06. Los tres primeros escalones
# se contienen unos a otros; los dos últimos son rodajas de edad aparte, y por
# eso van al final aunque abran lo mismo que el tercero.
ESCALERA: tuple[Escalon, ...] = (
    Escalon(edad_desde=0, edad_hasta=0, primaria=0, secundaria=0, peso=100),
    Escalon(edad_desde=0, edad_hasta=0, primaria=0, secundaria=1, peso=90),
    Escalon(edad_desde=0, edad_hasta=0, primaria=1, secundaria=1, peso=85),
    Escalon(edad_desde=1, edad_hasta=1, primaria=1, secundaria=1, peso=80),
    Escalon(edad_desde=-1, edad_hasta=-1, primaria=1, secundaria=1, peso=75),
)


@dataclass(frozen=True, slots=True)
class Objetivo:
    """El jugador tuyo al que se le busca precio."""

    ht_player_id: int
    edad: int
    primaria: Rasgo
    secundaria: Rasgo
    terciaria: Rasgo
    especialidad: int = 0


@dataclass(frozen=True, slots=True)
class Candidato:
    """Un jugador del mercado que podría servir de comparable."""

    ht_player_id: int
    nombre: str
    edad: int
    puja: int
    precio_pedido: int
    tiene_puja: bool
    plazo: str
    tsi: int
    especialidad: int
    lesion: int
    vendedor: int
    liga_del_vendedor: int
    #: El pais de nacimiento, para poder enseñar su bandera.
    pais: int
    primaria: Rasgo
    secundaria: Rasgo
    terciaria: Rasgo


@dataclass(frozen=True, slots=True)
class Franja:
    """El tramo de nivel que se le pide a una habilidad."""

    habilidad: str
    minimo: int
    maximo: int


@dataclass(frozen=True, slots=True)
class Ventana:
    """Una búsqueda concreta: qué pedirle al mercado en este escalón."""

    peso: int
    edad_minima: int
    edad_maxima: int
    primaria: Franja
    secundaria: Franja
    terciaria: Franja


@dataclass(frozen=True, slots=True)
class Guardado:
    """Una venta del mercado, en el fondo del equipo.

    Lleva SU PROPIO perfil (edad y las tres habilidades que cuentan) y no el
    peso. El peso es relativo al jugador que pregunta, así que guardarlo haría
    que esta venta sólo sirviera para aquel para quien se buscó; guardando el
    perfil se recalcula contra cualquiera, que es lo que el usuario pidió al
    decidir que el fondo se comparte en la plantilla.

    `precio` es la puja mientras `firme` sea falso, y el precio de venta real
    en cuanto se resuelve. `visto_el` es cuándo se encontró, que es lo que
    gobierna la caducidad.
    """

    ht_player_id: int
    nombre: str
    precio: int
    firme: bool
    #: La puja que vimos al encontrarla, que NO se pisa al resolver: es lo
    #: que permite enseñar el salto de la puja al precio de verdad.
    puja: int
    visto_el: datetime
    edad: int
    primaria: Rasgo
    secundaria: Rasgo
    terciaria: Rasgo
    especialidad: int = 0
    #: Lo que valia para Hattrick al encontrarlo. No entra en el parecido
    #: --el usuario comparo por habilidades, no por TSI-- pero se enseña,
    #: porque es la medida que todo el mundo tiene en la cabeza.
    tsi: int = 0
    #: Su pais de nacimiento, para la bandera.
    pais: int = 0
    #: El identificador del traspaso en Hattrick, en cuanto se resuelve.
    #: Cero mientras siga siendo una puja.
    ht_transfer_id: int = 0
    #: Cuántas veces se preguntó por su precio sin encontrarlo. Sólo cuenta
    #: el «pregunté y no estaba», no el «no pude preguntar».
    intentos: int = 0


@dataclass(frozen=True, slots=True)
class Comparable:
    """Una venta del fondo, ya medida contra un jugador concreto."""

    venta: Guardado
    peso: int
    #: Si ya cumplió su vida y sólo está ahí porque no hay nada más fresco.
    viejo: bool
    #: Si entra en el número. Desde el 2026-10-09, sólo las ventas ya
    #: cerradas: una puja no es un precio, y se vio cuánto no lo es --Edu
    #: Fuenllana pujaba 6.000 US$ y se vendió en 1.241.000--.
    cuenta: bool = True
    #: Si ocupa una de las seis plazas del fondo. NO es lo mismo que contar:
    #: una subasta abierta con puja ocupa --se está vigilando y va a
    #: convertirse en venta-- pero no promedia hasta que cierre. Si fueran lo
    #: mismo, el fondo no se llenaría nunca buscando, porque una búsqueda
    #: encuentra anuncios y no ventas cerradas.
    ocupa: bool = True


@dataclass(frozen=True, slots=True)
class Estimacion:
    """El resultado. Puede ser «todavía no» sin ser un error."""

    media: int | None
    mediana: int | None
    n: int
    peso_minimo: int
    provisionales: int
    comparables: tuple[Comparable, ...]

    @property
    def suficiente(self) -> bool:
        return self.media is not None


def terna(skills: Mapping[str, int]) -> tuple[Rasgo, Rasgo, Rasgo] | None:
    """Las tres habilidades más altas de las seis que cuentan, ya ordenadas.

    Devuelve `None` cuando las seis están a cero: eso no es un jugador flojo,
    es un hueco en los datos. El empate lo rompe `ORDEN_DE_DESEMPATE`, así que
    el mismo jugador da siempre la misma terna.
    """
    rasgos = [Rasgo(nombre, max(0, int(skills.get(nombre, 0)))) for nombre in ORDEN_DE_DESEMPATE]
    ordenados = sorted(rasgos, key=lambda rasgo: (-rasgo.nivel, _RANGO[rasgo.habilidad]))
    if ordenados[0].nivel <= 0:
        return None
    return ordenados[0], ordenados[1], ordenados[2]


def objetivo_de(
    ht_player_id: int,
    edad: int,
    skills: Mapping[str, int],
    *,
    especialidad: int = 0,
) -> Objetivo | None:
    """El objetivo a partir de un jugador propio, o `None` si no se le puede
    sacar una terna ni una edad."""
    tres = terna(skills)
    if tres is None or edad <= 0:
        return None
    primaria, secundaria, terciaria = tres
    return Objetivo(
        ht_player_id=ht_player_id,
        edad=edad,
        primaria=primaria,
        secundaria=secundaria,
        terciaria=terciaria,
        especialidad=especialidad,
    )


def perfil_de(objetivo: Objetivo) -> tuple[int, str, int, str, int, str, int]:
    """La huella del jugador, para saber cuándo lo guardado ya no es suyo.

    Si cambia la edad o cualquiera de las tres habilidades, lo acumulado
    describe a otro jugador y se tira.
    """
    return (
        objetivo.edad,
        objetivo.primaria.habilidad,
        objetivo.primaria.nivel,
        objetivo.secundaria.habilidad,
        objetivo.secundaria.nivel,
        objetivo.terciaria.habilidad,
        objetivo.terciaria.nivel,
    )


def ventana_de(objetivo: Objetivo, escalon: Escalon) -> Ventana | None:
    """La búsqueda de un escalón, o `None` si pide algo que no existe.

    Un jugador de 17 años no tiene escalón de «un año menos». No se recorta al
    valor válido más cercano, porque eso buscaría otra cosa de la que se dijo
    y repetiría un escalón ya hecho.
    """
    edad_minima = objetivo.edad + escalon.edad_desde
    edad_maxima = objetivo.edad + escalon.edad_hasta
    if edad_minima < EDAD_MINIMA:
        return None
    return Ventana(
        peso=escalon.peso,
        edad_minima=edad_minima,
        edad_maxima=edad_maxima,
        primaria=_franja(objetivo.primaria, escalon.primaria, escalon.primaria),
        secundaria=_franja(objetivo.secundaria, escalon.secundaria, escalon.secundaria),
        terciaria=_franja(objetivo.terciaria, TERCIARIA_ABAJO, TERCIARIA_ARRIBA),
    )


def plan_de_busqueda(objetivo: Objetivo) -> tuple[Ventana, ...]:
    """Las cinco búsquedas, de la más estrecha a la más ancha.

    Quien las recorra para en cuanto reúne `OBJETIVO`, y no a mitad de un
    escalón: si el sexto y el séptimo se parecen igual, dejar fuera al séptimo
    por orden de llegada sería arbitrario. Por eso se traen todos los que haya.
    """
    ventanas = (ventana_de(objetivo, escalon) for escalon in ESCALERA)
    return tuple(v for v in ventanas if v is not None)


def peso_de(candidato: Perfilado, objetivo: Objetivo) -> int | None:
    """Lo que vale este candidato, o `None` si no se le parece lo bastante.

    Las tres habilidades tienen que ser LAS MISMAS y en el mismo orden. Quien
    tiene los niveles pedidos pero en otras habilidades, o a quien otra
    habilidad le gana el desempate, es otro jugador: lo que se paga por él no
    dice nada de lo que se paga por el nuestro.
    """
    if (
        candidato.primaria.habilidad != objetivo.primaria.habilidad
        or candidato.secundaria.habilidad != objetivo.secundaria.habilidad
        or candidato.terciaria.habilidad != objetivo.terciaria.habilidad
    ):
        return None
    distancia_terciaria = candidato.terciaria.nivel - objetivo.terciaria.nivel
    if not -TERCIARIA_ABAJO <= distancia_terciaria <= TERCIARIA_ARRIBA:
        return None
    for escalon in ESCALERA:
        edad = candidato.edad - objetivo.edad
        if (
            escalon.edad_desde <= edad <= escalon.edad_hasta
            and abs(candidato.primaria.nivel - objetivo.primaria.nivel) <= escalon.primaria
            and abs(candidato.secundaria.nivel - objetivo.secundaria.nivel) <= escalon.secundaria
        ):
            return escalon.peso
    return None


def candidato_de(fila: Mapping[str, Any]) -> Candidato | None:
    """Un candidato a partir de una fila del parser del mercado.

    `None` cuando la fila no sirve: sin jugador, o sin ninguna de las seis
    habilidades.
    """
    jugador = int(fila.get("ht_player_id", 0) or 0)
    if jugador <= 0:
        return None
    habilidades = fila.get("skills") or {}
    if not isinstance(habilidades, Mapping):
        return None
    tres = terna(habilidades)
    if tres is None:
        return None
    primaria, secundaria, terciaria = tres
    puja = max(0, int(fila.get("highest_bid", 0) or 0))
    return Candidato(
        ht_player_id=jugador,
        nombre=_nombre(fila),
        edad=int(fila.get("age_years", 0) or 0),
        puja=puja,
        precio_pedido=int(fila.get("asking_price", 0) or 0),
        # La bandera del parser manda cuando viene: es la que distingue
        # «nadie pujó» de «ofrecieron cero».
        tiene_puja=bool(fila["has_bids"]) if "has_bids" in fila else puja > 0,
        plazo=str(fila.get("deadline", "") or ""),
        tsi=int(fila.get("tsi", 0) or 0),
        especialidad=int(fila.get("specialty", 0) or 0),
        lesion=int(fila["injury_level"]) if fila.get("injury_level") is not None else -1,
        vendedor=int(fila.get("seller_team_id", 0) or 0),
        liga_del_vendedor=int(fila.get("seller_league_id", 0) or 0),
        pais=int(fila.get("native_country_id", 0) or 0),
        primaria=primaria,
        secundaria=secundaria,
        terciaria=terciaria,
    )


def cosecha(
    objetivo: Objetivo,
    filas: Iterable[Mapping[str, Any]],
    *,
    mi_equipo: int,
    ya_vistos: Iterable[int] = (),
    tambien_para: Sequence[Objetivo] = (),
) -> tuple[list[tuple[Candidato, int]], list[tuple[Candidato, int]]]:
    """Separa lo que devuelve una búsqueda en dos montones, con su peso.

    El primero es el de los que tienen puja, cuya venta está garantizada. El
    segundo es el de los que no, y desde el 2026-10-07 NO SE ANOTA: se
    devuelve para poder contarlo y enseñarlo --«de 25 parecidos, 19 sin una
    sola puja» dice mucho del mercado de ese jugador-- pero no entra en el
    fondo. Un precio pedido es lo que una persona decidió pedir.

    Quedan fuera, y cada exclusión tiene su motivo: tus propios jugadores en
    venta, porque su precio es justo el que queremos estimar y no un dato
    ajeno; y quien no se parece lo bastante. Los lesionados y los sancionados
    SÍ entran, por decisión del usuario del 2026-10-06. Las ligas extranjeras
    también.

    `tambien_para` SON EL RESTO DE TU PLANTILLA, y vale lo que le sirva a
    cualquiera de ellos (2026-10-07, pedido por el usuario). La búsqueda la
    dispara uno, pero por delante pasa el mercado entero: medido sobre la de
    İmam Ece, de 51 anuncios con puja 8 le servían a él y 4 más a otros dos
    compañeros. Quedarse sólo con los suyos tiraba esos cuatro, que ya
    estaban pagados.

    El peso que se devuelve es el MEJOR de todos, no el del que preguntó: un
    anuncio puede parecerse poco a quien disparó la búsqueda y mucho a otro.
    Da igual para el fondo --`comparables_de` lo vuelve a medir contra quien
    pregunte-- pero importa para decidir a quién se parece de verdad.
    """
    conocidos = set(ya_vistos)
    interesados = (objetivo, *tambien_para)
    # Ninguno de los tuyos, los pida quien los pida: su precio es justo el
    # que queremos estimar y no un dato ajeno.
    nuestros = {o.ht_player_id for o in interesados}
    con_puja: list[tuple[Candidato, int]] = []
    sin_puja: list[tuple[Candidato, int]] = []
    for fila in filas:
        candidato = candidato_de(fila)
        if candidato is None:
            continue
        if candidato.ht_player_id in nuestros:
            continue
        if candidato.vendedor and candidato.vendedor == mi_equipo:
            continue
        if candidato.ht_player_id in conocidos:
            continue
        pesos = [p for o in interesados if (p := peso_de(candidato, o)) is not None]
        if not pesos:
            continue
        peso = max(pesos)
        conocidos.add(candidato.ht_player_id)
        if candidato.tiene_puja and candidato.puja > 0:
            con_puja.append((candidato, peso))
        else:
            sin_puja.append((candidato, peso))
    return con_puja, sin_puja


def reemplazable(venta: Guardado, ahora: datetime) -> bool:
    """Si ya cumplió su vida y puede dejar paso a algo más fresco.

    Cumplirla no la borra. Una venta de hace dos meses sigue informando más
    que ninguna, así que se queda mientras no haya con qué sustituirla.
    """
    return _aware(ahora) - _aware(venta.visto_el) >= VIDA


def comparables_de(
    fondo: Iterable[Guardado], objetivo: Objetivo, ahora: datetime
) -> tuple[Comparable, ...]:
    """Las ventas del fondo que sirven para este jugador, de mejor a peor.

    El fondo es del EQUIPO, así que aquí se vuelve a medir cada venta contra
    el jugador que pregunta. Una venta encontrada buscando para un delantero
    sirve para otro delantero parecido sin gastar una sola llamada.

    El orden lo dictó el usuario, y manda el peso por encima de todo porque
    dijo que un comparable «nunca será reemplazado por algo de menor peso».
    Dentro del mismo peso va su regla de desempate, puesta del derecho: se
    queda antes el más reciente, luego el más caro, y en el último empate el
    que comparte especialidad con tu jugador.

    Se devuelven los `OBJETIVO` mejores Y todos los que empaten en peso con el
    último, porque cuantos más datos haya mejor se describe el mercado: si un
    escalón trajo diez comparables igual de buenos, cuentan los diez.
    """
    medidos: list[Comparable] = []
    for venta in fondo:
        peso = peso_de(venta, objetivo)
        if peso is None:
            continue
        medidos.append(
            Comparable(
                venta=venta,
                peso=peso,
                # EL 100% NO CADUCA NUNCA (2026-10-07, regla del usuario).
                # Un comparable exacto --misma edad y las tres habilidades
                # clavadas-- es el mejor dato que puede existir para este
                # jugador, y no hay nada «más fresco» que pueda mejorarlo;
                # dejarlo caducar seria tirar lo bueno esperando lo que no
                # va a venir. La caducidad existe para los parecidos, que
                # envejecen porque el mercado de su alrededor cambia.
                #
                # Se decide AQUI y no en `reemplazable` porque el peso es
                # relativo a quien pregunta: la misma venta puede ser un
                # 100% para uno y un 75% para su companero, y entonces
                # caduca para el segundo y no para el primero.
                viejo=peso < 100 and reemplazable(venta, ahora),
                cuenta=cuenta_para_el_numero(venta),
                ocupa=ocupa_plaza(venta),
            )
        )
    medidos.sort(
        key=lambda c: (
            -c.peso,
            -_aware(c.venta.visto_el).timestamp(),
            -c.venta.precio,
            0 if c.venta.especialidad == objetivo.especialidad else 1,
        )
    )
    # La selección se hace SÓLO entre las que OCUPAN PLAZA, para que una
    # abandonada no le quite el sitio a una buena ni engañe al recorrido
    # haciéndole creer que ya tiene bastantes. Las demás se añaden al
    # final: siguen enseñándose, marcadas.
    #
    # Ocupar plaza NO es contar para la media (2026-10-09). Una subasta
    # abierta con puja ocupa --es material del fondo, se vigila, y va a
    # convertirse en una venta-- pero no promedia hasta que cierre. Antes era
    # lo mismo, y al separar las dos cosas hubo que separar los criterios: si
    # la selección mirara sólo lo que cuenta, el fondo no se daría nunca por
    # lleno --una búsqueda encuentra anuncios, nunca ventas cerradas-- y cada
    # turno gastaría los cinco escalones de todos los jugadores para siempre.
    ocupan = [c for c in medidos if c.ocupa]
    sobran = [c for c in medidos if not c.ocupa]
    if len(ocupan) > OBJETIVO:
        corte = ocupan[OBJETIVO - 1].peso
        ocupan = [c for c in ocupan if c.peso >= corte]
    return (*ocupan, *sobran)


def ocupa_plaza(venta: Guardado) -> bool:
    """Si esta venta es material util del fondo, cuente o no para la media.

    Separado de `cuenta_para_el_numero` el 2026-10-09, cuando la media paso a
    ser solo de ventas cerradas. Son dos preguntas distintas:

    · «¿Entra en el numero?»  -> solo si ya se vendio.
    · «¿Ocupa una de las seis plazas, y por tanto evita salir a buscar mas?»
      -> tambien una subasta abierta con puja, porque es material que se esta
      vigilando y que va a convertirse en una venta.

    Si fueran la misma pregunta, el fondo no se daria por lleno NUNCA: una
    busqueda en el mercado encuentra anuncios, no ventas cerradas, asi que
    cada turno gastaria los cinco escalones de cada jugador indefinidamente.

    UN ANUNCIO QUE NADIE HA PUJADO NO OCUPA NADA. Su precio llega a cero,
    porque cero es lo que vale `HighestBid` sin pujas. El 2026-10-07, mirando
    a Kurt Schonhueb, el mercado no tenia ni un comparable con puja y si ocho
    anuncios sin ella; dejarles ocupar plaza habria impedido salir a buscar lo
    que de verdad faltaba.

    Y uno al que se le agotaron los intentos de resolucion tampoco: es un
    hueco con nombre, y su plaza tiene que quedar libre.
    """
    if venta.firme:
        return True
    if venta.precio <= 0:
        return False
    return venta.intentos <= REINTENTOS_DE_RESOLUCION


def cuenta_para_el_numero(venta: Guardado) -> bool:
    """Si esta venta puede entrar en la media. SOLO SI YA SE VENDIO.

    DECISION DEL USUARIO, 2026-10-09, y es un cambio de criterio: hasta hoy
    una subasta abierta contaba con su puja mientras le quedaran intentos de
    resolucion. Ya no cuenta ninguna.

    POR QUE. Una puja no es un precio, y no por poco. Ese mismo dia, en la
    tabla de Imam Ece, Edu Fuenllana figuraba con 6.000 US$ de puja y se
    vendio en 1.241.000: un +20.583 %. En la misma tabla, de seis
    comparables, tres eran pujas de 3.000, 1.000 y 1.000 US$, y esas tres
    arrastraban la media del jugador de 876.000 a 436.144. La mitad de la
    cifra la ponia gente que todavia no habia pagado nada.

    Venia de antes: la grafica del tiempo ya se habia quedado solo con las
    ventas cerradas, y la tarjeta seguia contando pujas. Dos numeros para lo
    mismo, el doble uno del otro, en la misma pantalla.

    LO QUE CUESTA, medido antes de hacerlo y aceptado: con el fondo del
    2026-10-09, 23 de los 26 jugadores del club se quedan sin numero, y solo
    uno llega a los seis comparables. No es un fallo, es la verdad --todavia
    no se ha vendido nadie bastante parecido-- y se corrige solo: habia 16
    ventas con el plazo pasado esperando resolucion, y cada paso del mercado
    convierte varias en cerradas.

    Y EMPUJA EN LA DIRECCION BUENA. Esto gobierna tambien `hay_que_buscar`:
    con menos comparables contando, el turno sale a buscar para casi todos en
    vez de darse por satisfecho, que es justo lo que llena el fondo de ventas
    cerradas.

    Las pujas NO se tiran: siguen en el fondo, se siguen vigilando y se
    siguen enseñando en la tabla marcadas como lo que son. Lo unico que no
    hacen es promediar.
    """
    return venta.firme


def estimar(comparables: Sequence[Comparable]) -> Estimacion:
    """La media y la mediana, las dos ponderadas por parecido.

    Con menos de `OBJETIVO` no hay número, pero sí lista: la pantalla tiene
    que poder enseñar lo que hay y decir que todavía no basta.

    `provisionales` se cuenta sobre TODAS las que se enseñan, no sobre las que
    cuentan (2026-10-09). Desde que sólo cuentan las ventas cerradas, sobre
    las que cuentan valdría siempre cero, y un campo que no puede cambiar no
    informa de nada. Sobre todas dice lo que la pantalla necesita: cuántas de
    las que hay delante son subastas que todavía no han cerrado.
    """
    # `comparables` lleva TODAS, para que la pantalla pueda enseñarlas; el
    # numero se hace solo con las que cuentan.
    todas = tuple(comparables)
    elegidos = tuple(c for c in todas if c.cuenta)
    if len(elegidos) < OBJETIVO:
        return Estimacion(
            media=None,
            mediana=None,
            n=len(elegidos),
            peso_minimo=min((c.peso for c in elegidos), default=0),
            provisionales=sum(1 for c in todas if not c.venta.firme),
            comparables=todas,
        )
    denominador = sum(c.peso for c in elegidos)
    numerador = sum(c.peso * c.venta.precio for c in elegidos)
    return Estimacion(
        # Redondeo al par, el mismo que usa la simulación de venta del front.
        media=round(numerador / denominador),
        mediana=_mediana_ponderada(elegidos),
        n=len(elegidos),
        peso_minimo=min(c.peso for c in elegidos),
        provisionales=sum(1 for c in todas if not c.venta.firme),
        comparables=todas,
    )


def _mediana_ponderada(comparables: Sequence[Comparable]) -> int:
    """El precio que parte el peso por la mitad.

    Se ordenan por precio y se va sumando peso hasta pasar de la mitad del
    total. Cuando la mitad cae justo en la frontera entre dos, se promedian
    los dos, como en la mediana de toda la vida con un número par de datos.
    """
    por_precio = sorted(comparables, key=lambda c: c.venta.precio)
    total = sum(c.peso for c in por_precio)
    mitad = total / 2
    acumulado = 0.0
    for indice, comparable in enumerate(por_precio):
        acumulado += comparable.peso
        if acumulado > mitad:
            return comparable.venta.precio
        if acumulado == mitad:
            siguiente = por_precio[indice + 1] if indice + 1 < len(por_precio) else comparable
            return round((comparable.venta.precio + siguiente.venta.precio) / 2)
    return por_precio[-1].venta.precio


# --------------------------------------------------------------------------
# De la puja al precio de verdad
# --------------------------------------------------------------------------


def se_puede_resolver(plazo: datetime | None, ahora: datetime) -> bool:
    """Si ya ha cerrado la subasta y Hattrick ha tenido tiempo de anotarla.

    Sin plazo no se puede saber, y preguntar a ciegas gastaría una llamada por
    cada intento.
    """
    if plazo is None:
        return False
    return _aware(ahora) >= _aware(plazo) + MARGEN_TRAS_EL_PLAZO


@dataclass(frozen=True, slots=True)
class Traspaso:
    """Un cambio de club del historial de un jugador.

    `ht_transfer_id` es el identificador de Hattrick, y SÓLO existe de este
    lado. El fichero del mercado no lo publica --comprobado el 2026-10-07
    listando las etiquetas de un anuncio: `PlayerId`, `AskingPrice`,
    `Deadline`, `HighestBid`, `BidderTeam`, `SellerTeam` y `Details`, y nada
    más-- y es lógico, porque mientras la subasta vive la transferencia
    todavía no ha ocurrido. Por eso el emparejamiento sigue siendo por plazo:
    es el único dato que está en los dos lados. El id entra en cuanto se
    resuelve, y desde ahí la venta tiene identidad propia.
    """

    ht_transfer_id: int
    cierre: datetime
    precio: int


def precio_cerrado(
    traspasos: Iterable[Traspaso],
    plazo: datetime,
    *,
    tolerancia: timedelta = timedelta(minutes=5),
) -> Traspaso | None:
    """El traspaso que cerró la subasta que estábamos siguiendo.

    El historial de un jugador trae TODOS sus traspasos, así que hay que
    quedarse con el que cierra en el plazo que anotamos. No vale coger el más
    reciente sin más: si el jugador cambió de club otra vez entre medias, ése
    sería otro traspaso y otro precio.

    EL MÁS CERCANO, no el primero que encaje (2026-10-07). Dos traspasos
    seguidos pueden caer los dos dentro de la tolerancia, y quedarse con el
    primero que apareciera dejaba la elección al orden en que Hattrick los
    mandara, o sea al azar. El desfase medido en un caso real fue de trece
    segundos contra una tolerancia de cinco minutos, así que el margen para
    equivocarse existe.

    Devuelve `None` cuando ninguno encaja, que con una puja encima no debería
    pasar. Cuando pasa no se inventa nada: se reintenta y, si sigue sin
    aparecer, la venta se queda con su puja.
    """
    objetivo = _aware(plazo)
    dentro = [t for t in traspasos if abs(_aware(t.cierre) - objetivo) <= tolerancia]
    if not dentro:
        return None
    return min(dentro, key=lambda t: abs(_aware(t.cierre) - objetivo))


# --------------------------------------------------------------------------
# Cuándo le toca a quién
# --------------------------------------------------------------------------


def frontera_semanal(economy_date: datetime | None, ahora: datetime) -> datetime | None:
    """El último disparador que ya pasó.

    El disparador es la actualización económica de TU liga menos 24 horas.
    Hattrick publica esa fecha por país, así que no hay que inventar zonas
    horarias ni mantener una tabla a mano: la da el propio juego.

    `economy_date` es la PRÓXIMA actualización, así que se retrocede de semana
    en semana hasta dar con el disparador anterior a `ahora`. Se avanza
    también, por si el dato guardado se quedó viejo.
    """
    if economy_date is None:
        return None
    frontera = _aware(economy_date) - ANTICIPO
    ahora = _aware(ahora)
    while frontera > ahora:
        frontera -= timedelta(days=7)
    while frontera + timedelta(days=7) <= ahora:
        frontera += timedelta(days=7)
    return frontera


def semana_de(frontera: datetime, ancla: datetime) -> int:
    """El número de semana de mercado, para rotar los turnos."""
    return (_aware(frontera) - _aware(ancla)).days // 7


def le_toca(
    ht_player_id: int,
    frontera: datetime,
    ancla: datetime,
) -> bool:
    """Si a este jugador le tocan los escalones ANCHOS esta semana.

    El grupo sale del propio identificador, así que no hay nada que guardar ni
    que recolocar al fichar o vender. El 0 rota a 1, 2, 3 y 4 cada semana.
    """
    return ht_player_id % GRUPOS == semana_de(frontera, ancla) % GRUPOS


def dia_de(ahora: datetime, ancla: datetime) -> int:
    """El número de día, para rotar el turno del escalón exacto."""
    return (_aware(ahora) - _aware(ancla)).days


def le_toca_el_exacto(ht_player_id: int, ahora: datetime, ancla: datetime) -> bool:
    """Si a este jugador le toca HOY su escalón exacto.

    El mismo truco que los anchos pero contando días en vez de semanas, así que
    tampoco guarda nada: `ID % 6` contra el día. A cada jugador le toca uno de
    cada seis días, y como seis no divide a siete su turno recorre todos los
    días de la semana en vez de quedarse clavado en uno.
    """
    return ht_player_id % DIAS_DEL_EXACTO == dia_de(ahora, ancla) % DIAS_DEL_EXACTO


def hay_que_buscar(comparables: Sequence[Comparable]) -> bool:
    """Si en su turno hay algo que hacer: CUANDO NOS QUEDAMOS SIN DATOS.

    Decisión del usuario, 2026-10-09. Antes esto devolvía `True` también
    cuando alguno de los seis había caducado, y entonces el turno se gastaba
    entero buscando con qué sustituirlo. Ya no: lo que dispara la búsqueda
    ancha es no tener bastantes, y el refresco lo lleva el calendario --el
    exacto cada seis días, los anchos cada cinco semanas--.

    Lo que eso significa, y es el precio de la decisión: un comparable puede
    cumplir sus siete semanas de vida y seguir usándose hasta que a su jugador
    le toquen los anchos otra vez, hasta cinco semanas después. Un dato viejo
    informa más que ninguno, que es la misma razón por la que no se borra al
    caducar.

    Se miran sólo las que OCUPAN PLAZA. Una abandonada no es un dato, es un
    hueco con nombre, y dejar que ocupe plaza impediría salir a buscar lo que
    de verdad falta.
    """
    return sum(1 for c in comparables if c.ocupa) < OBJETIVO


def _franja(rasgo: Rasgo, abajo: int, arriba: int) -> Franja:
    return Franja(
        habilidad=rasgo.habilidad,
        minimo=max(0, rasgo.nivel - abajo),
        maximo=rasgo.nivel + arriba,
    )


def _nombre(fila: Mapping[str, Any]) -> str:
    partes = [str(fila.get("first_name", "") or ""), str(fila.get("last_name", "") or "")]
    return " ".join(parte for parte in partes if parte)


def _aware(momento: datetime) -> datetime:
    return momento if momento.tzinfo is not None else momento.replace(tzinfo=UTC)
