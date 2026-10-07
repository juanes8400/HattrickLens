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

#: Cuántos grupos de rotación. Cada semana le toca a uno.
GRUPOS = 5

#: Lo que se le resta a la actualización económica para fijar el disparador.
ANTICIPO = timedelta(hours=24)

#: Nadie juega en el primer equipo con menos de 17 años.
EDAD_MINIMA = 17

#: Cuántos datos tiene que aportar la gente sin puja para que valga la pena
#: anotarla. Con uno solo no se gastan resoluciones.
MINIMO_PARA_BAJAR_A_SIN_PUJA = 2

#: Lo que se espera tras el cierre de una subasta antes de preguntar por el
#: precio. Hattrick tarda un poco en registrar el traspaso, y preguntar
#: demasiado pronto gasta una llamada para no encontrar nada.
MARGEN_TRAS_EL_PLAZO = timedelta(hours=2)

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
    #: Si entra en el número. Falso sólo para un provisional al que se le
    #: agotaron los intentos de resolución: su precio es una puja que ya no
    #: va a corregirse, así que se sigue enseñando pero no se promedia.
    #: Con los reintentos de ahora esto no debería saltar nunca; está para
    #: que, si salta, no se quede un número bajo contando en silencio.
    cuenta: bool = True


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
) -> tuple[list[tuple[Candidato, int]], list[tuple[Candidato, int]]]:
    """Separa lo que devuelve una búsqueda en dos montones, con su peso.

    El primero es el de los que tienen puja, cuya venta está garantizada. El
    segundo es el de los que no, que sólo se anotan si hacen falta para
    reunir lo bastante (ver `MINIMO_PARA_BAJAR_A_SIN_PUJA`).

    Quedan fuera, y cada exclusión tiene su motivo: tus propios jugadores en
    venta, porque su precio es justo el que queremos estimar y no un dato
    ajeno; y quien no se parece lo bastante. Los lesionados y los sancionados
    SÍ entran, por decisión del usuario del 2026-10-06. Las ligas extranjeras
    también.
    """
    conocidos = set(ya_vistos)
    con_puja: list[tuple[Candidato, int]] = []
    sin_puja: list[tuple[Candidato, int]] = []
    for fila in filas:
        candidato = candidato_de(fila)
        if candidato is None:
            continue
        if candidato.ht_player_id == objetivo.ht_player_id:
            continue
        if candidato.vendedor and candidato.vendedor == mi_equipo:
            continue
        if candidato.ht_player_id in conocidos:
            continue
        peso = peso_de(candidato, objetivo)
        if peso is None:
            continue
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
                viejo=reemplazable(venta, ahora),
                cuenta=cuenta_para_el_numero(venta),
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
    # La selección se hace SÓLO entre las que cuentan, para que una
    # abandonada no le quite el sitio a una buena ni engañe al recorrido
    # haciéndole creer que ya tiene bastantes. Las que no cuentan se
    # añaden al final: siguen enseñándose, marcadas.
    cuentan = [c for c in medidos if c.cuenta]
    sobran = [c for c in medidos if not c.cuenta]
    if len(cuentan) > OBJETIVO:
        corte = cuentan[OBJETIVO - 1].peso
        cuentan = [c for c in cuentan if c.peso >= corte]
    return (*cuentan, *sobran)


def cuenta_para_el_numero(venta: Guardado) -> bool:
    """Si esta venta puede entrar en la media.

    Una venta cerrada siempre cuenta. Un provisional cuenta mientras le
    queden intentos de resolución: su puja es un suelo que todavía va a
    corregirse. Cuando se le agotan, su precio se queda congelado en una
    puja que sabemos corta y ya no se promedia.
    """
    return venta.firme or venta.intentos <= REINTENTOS_DE_RESOLUCION


def estimar(comparables: Sequence[Comparable]) -> Estimacion:
    """La media y la mediana, las dos ponderadas por parecido.

    Con menos de `OBJETIVO` no hay número, pero sí lista: la pantalla tiene
    que poder enseñar lo que hay y decir que todavía no basta.
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
            provisionales=sum(1 for c in elegidos if not c.venta.firme),
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
        provisionales=sum(1 for c in elegidos if not c.venta.firme),
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


def precio_cerrado(
    traspasos: Iterable[tuple[datetime, int]],
    plazo: datetime,
    *,
    tolerancia: timedelta = timedelta(minutes=5),
) -> int | None:
    """Lo que se pagó en la subasta que estábamos siguiendo.

    El historial de un jugador trae TODOS sus traspasos, así que hay que
    quedarse con el que cierra en el plazo que anotamos. No vale coger el más
    reciente sin más: si el jugador cambió de club otra vez entre medias, ése
    sería otro traspaso y otro precio.

    Devuelve `None` cuando ninguno encaja, que con una puja encima no debería
    pasar. Cuando pasa no se inventa nada: se reintenta y, si sigue sin
    aparecer, la venta se queda con su puja.
    """
    objetivo = _aware(plazo)
    for cierre, precio in traspasos:
        if abs(_aware(cierre) - objetivo) <= tolerancia:
            return precio
    return None


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
    """Si este jugador es de los que tocan esta semana.

    El grupo sale del propio identificador, así que no hay nada que guardar ni
    que recolocar al fichar o vender. El 0 rota a 1, 2, 3 y 4 cada semana.
    """
    return ht_player_id % GRUPOS == semana_de(frontera, ancla) % GRUPOS


def hay_que_buscar(comparables: Sequence[Comparable]) -> bool:
    """Si en su turno hay algo que hacer.

    No lo hay cuando ya tiene sus seis y ninguno está ahí de prestado: gastar
    llamadas en reemplazar lo que no caducó sería tirar cuota de la
    aplicación entera.

    Se miran sólo las que cuentan. Una abandonada no es un dato, es un hueco
    con nombre, y dejar que ocupe plaza impediría salir a buscar lo que
    de verdad falta.
    """
    utiles = [c for c in comparables if c.cuenta]
    if len(utiles) < OBJETIVO:
        return True
    return any(c.viejo for c in utiles)


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
