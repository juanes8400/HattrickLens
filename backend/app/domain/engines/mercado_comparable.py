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

DE QUÉ ESTÁ HECHO. De **ventas cerradas, y de nada más**. Una puja abierta se
guarda, se vigila y se enseña marcada como lo que es, pero NO promedia: se
queda para sacarle el precio cuando cierre (2026-10-09, ver
`cuenta_para_el_numero`). Eso no es un tecnicismo: el 2026-10-05 Valerio
Cataldi tenía 65.000.000 de puja y cerró en 77.720.000, un 16 % por encima, y
el mismo día tres pujas de 3.000, 1.000 y 1.000 US$ arrastraban la media de un
jugador de 876.000 a 436.144.

A QUIÉN SE PARECE. A las TRES habilidades más altas de las seis de campo. La
resistencia y el balón parado no cuentan, igual que no cuentan en el propio
buscador de Hattrick. Y tienen que ser las mismas tres, en el mismo orden: a
quien le gana el desempate otra habilidad al mismo nivel es otro jugador, y el
usuario lo decidió mirando un caso concreto que costó la única puja de aquella
medición.

CUÁNTO SE PARECE: DOS PESOS Y NADA MÁS (2026-10-27, decisión del usuario).
**100** es el clavado, «coincidencia exacta Edad + top 3 habilidades»: es el
mismo jugador. **90** es el sello, «aparece en el comparador de Hattrick pero
no es exactamente el mismo jugador»: el propio juego lo enseñaría al comparar
al nuestro, comprobado contra su regla. Lo que no es ninguna de las dos cosas
no es comparable y no entra.

Antes de eso había una escalera nuestra de cuatro peldaños más --95, 90, 80 y
75-- que puntuaba lo que hubo que mover, y una ventana para la terciaria. Se
fue entera: «solo hay esos dos escalones, el resto ya no los quiero». La
medición de lo que cuesta está escrita junto a los pesos.

EL SELLO SE MIDIÓ, no se supuso (2026-10-10). Salió de sondear el Comparador
del propio juego --unas 460 consultas a su panel «Editar búsqueda», repartidas
en cinco días-- y de ahí sale la regla que aplica `criterios_hattrick`, con un
98 % de acierto fuera de muestra. Un dato de aquel sondeo explica por qué la
escalera nuestra nunca fue buena: el peldaño que abría la primera habilidad no
acertaba NI UNO de 5.801 pares, porque Hattrick no mueve nunca la primera.
La medición está en `docs/reference/CRITERIOS_DEL_COMPARADOR.md`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from app.domain.engines.criterios_hattrick import criterios_de

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

#: CUÁNTOS DATOS SE QUIEREN POR JUGADOR: TREINTA (2026-11-08, decisión del
#: usuario, el día que rehízo el algoritmo entero). Antes eran ocho.
#:
#: NO ES UNA PUERTA NI UN RECORTE: es un tope y un objetivo. Por debajo de 30
#: sólo se suma --«si nos faltan, entonces agregar», y si llegan comparables
#: entran todos--. Al llegar a 30 empieza el relevo, que es lo único que saca a
#: alguien de la lista. «Ya no quiero cortes, si muchos jugadores pueden entrar
#: como comparables, entran.»
#:
#: Y YA NO MIDE LA CONFIANZA. Hasta hoy el mismo ocho hacía dos trabajos:
#: decidía a quién se recortaba y rotulaba «este número sale de 3 ventas, no de
#: 8». El segundo se fue con él --«sólo se dice n», decisión suya del mismo
#: día-- porque un objetivo de recogida no es un umbral de fiabilidad, y
#: presentarlo como tal haría leer un precio de 29 ventas como flojo.
#:
#: AQUÍ VIVÍA TAMBIÉN `SIN_PUJA_QUE_SE_ENSENAN`, el tope de anuncios a cero que
#: se pintaban en la tabla. Se fue el mismo día con su motivo: la tabla es sólo
#: de ventas con precio --«si no promedia, no es fila»-- así que ya no hay
#: ninguna fila muerta que limitar.
OBJETIVO_DE_DATOS = 30

#: Cuánto vive un dato antes de quedar marcado como viejo. No se borra al
#: cumplirlo: queda a la espera de que algo mejor lo sustituya, y si no
#: aparece nada se queda, porque un dato viejo informa más que ninguno.
#:
#: VEINTICUATRO SEMANAS (2026-11-07, decisión del usuario; antes eran siete).
#: Es la regla que él fija, y además cuadra con lo único que se midió del juego:
#: el comparable más viejo que Hattrick usa para Moisés Llauge es del 15 de
#: abril, unas VEINTICINCO semanas, y lo sigue metiendo en su promedio. Con
#: siete semanas estábamos marcando por viejo lo que el propio juego
#: considera vigente.
#:
#: Y CUESTA POCO, porque caducar no borra: una venta vieja sólo deja paso
#: cuando aparece algo mejor. Lo que cambia de verdad es `viejo`, la marca
#: naranja de la tabla, que dejará de salir en ventas de dos meses que el juego
#: seguiría usando.
VIDA = timedelta(weeks=24)

#: NO HAY LIMITE DURO. Del 2026-10-09 al 2026-10-10 lo hubo: se borraba a las
#: doce semanas, sobre la base de que Hattrick hace lo mismo. Se le sondeo la
#: pantalla y resulto que no: el comparable mas viejo que el juego usa para
#: Moises Llauge es del 15 de abril, unas VEINTICINCO semanas, y lo sigue
#: metiendo en su promedio. Cuando no tiene nada mas fresco prefiere una venta
#: de hace seis meses a dejar al jugador sin cifra, y tiene razon: una cifra
#: vieja informa, y ninguna cifra no informa nada.
#:
#: Asi que vuelve a mandar `VIDA` sola: cumplirla no borra, deja paso.

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

#: CUÁNTAS VECES SE COMPRUEBA SI UNA VENTA SE CERRÓ: DOS (2026-11-08,
#: decisión del usuario: «vamos a revisar solamente 2 veces en el tiempo en el
#: que se supone que ya se vendieron»).
#:
#: SON DOS SINCRONIZACIONES REALES, NO DOS DÍAS DE RELOJ, y toda la diferencia
#: está ahí. Aquí vivía `VENTANA_DE_RESOLUCION = 3 días`, un plazo contado
#: desde el cierre que se cumplía solo, estuviera la aplicación abierta o no.
#:
#: LO QUE ESO COSTÓ, medido el 2026-11-08 sobre la copia local: de 22 ventas
#: con puja sin resolver, 20 habían pasado el plazo, y DIECIOCHO de esas 20
#: tenían cero intentos. No es que fallaran: es que nunca se les preguntó. El
#: plazo se les cumplió mientras nadie miraba, y quedaron en el peor estado
#: posible --sin precio, sin borrarse y ocupando sitio--.
#:
#: Contando comprobaciones, esas dieciocho conservan sus dos intactas. Una
#: llamada que no llegó --CHPP caído-- no gasta comprobación: lo que se cuenta
#: es lo que sabemos de la venta, y una llamada que no salió no sabe nada.
COMPROBACIONES = 2


class Perfilado(Protocol):
    """Cualquiera a quien se le pueda medir el parecido.

    Lo cumplen el jugador del mercado recién leído y la venta ya guardada en
    el fondo, que es justo lo que permite recalcular el peso de una venta
    vieja contra un jugador nuevo.
    """

    @property
    def edad(self) -> int: ...

    #: LOS DIAS DE SU EDAD, para el tope de los 17. `-1` significa «no los
    #: tenemos»: las ventas guardadas antes de la columna vienen asi, y el
    #: tope no se les aplica --que es lo mismo que hacíamos con todas--.
    @property
    def dias(self) -> int: ...

    @property
    def primaria(self) -> Rasgo: ...

    @property
    def secundaria(self) -> Rasgo: ...

    @property
    def terciaria(self) -> Rasgo: ...

    @property
    def habilidades(self) -> Mapping[str, int]: ...


@dataclass(frozen=True, slots=True)
class Rasgo:
    """Una habilidad con su nivel."""

    habilidad: str
    nivel: int


#: EL CLAVADO VALE 100: «100 = coincidencia exacta Edad + top 3 habilidades»,
#: palabras del usuario, dichas el 2026-10-26 y repetidas igual el 2026-10-27.
#: Es el mismo jugador, y no hay nada mejor que pueda existir: por eso no
#: caduca.
PESO_DEL_CLAVADO = 100

#: EL SELLO VALE 90 (2026-10-27, decisión del usuario): «90 = aparece en el
#: comparador de Hattrick pero no es exactamente el mismo jugador». Un
#: comparable se lleva el sello cuando el propio juego lo enseñaría al comparar
#: a nuestro jugador, comprobado contra su regla --ver `criterios_hattrick`--.
#:
#: VALÍA 100 HASTA HOY, y el cambio es suyo. El 2026-10-26 se le preguntó
#: expresamente si prefería bajar el sello a 95 y dijo que no, los dos a 100;
#: el 2026-10-27 lo movió él a 90, que no era ninguna de las dos opciones de
#: entonces. Queda escrito porque cambia todos los precios de la aplicación:
#: una venta avalada pesa ahora menos que una clavada, y la media ponderada se
#: mueve con ella.
PESO_DE_HATTRICK = 90

# AQUÍ VIVÍA `PESO_QUE_NO_CADUCA = 100`, y lo derogó el usuario el 2026-11-08:
# «todo lo que entra sí debe caducar (24 semanas), pero nunca nos debemos
# quedar con 0 jugadores». Desde el 2026-10-07 el clavado era inmune, con su
# argumento --«es el mejor dato que puede existir y no hay nada más fresco que
# pueda mejorarlo»--, y lo que lo hace innecesario es el relevo: sin lista
# llena no sale nadie, así que el miedo que el escudo protegía ya no existe.

# SÓLO HAY DOS PESOS, y aquí ya no hay escalera. Se fue entera el 2026-10-27
# --«solo hay esos dos escalones, el resto ya no los quiero»-- con sus cuatro
# peldaños (95, 90, 80 y 75) y la ventana de la terciaria que los acompañaba.
# Lo que no está clavado ni avalado no es comparable: no pesa poco, no entra.
#
# Ya no disparaba búsquedas --eso se había ido el 2026-10-26, ver
# `plan_de_busqueda`--, así que lo único que se pierde es puntuar lo que entra
# por criterios sin estar clavado. LO QUE CUESTA, medido antes de hacerlo y
# aceptado: contra el fondo del 2026-10-27, 27 pares puntuados pasan a 0 y los
# jugadores con precio de 8 a ninguno. No es la regla, es el fondo: ninguna de
# sus 33 ventas guarda las siete habilidades --todas se vieron antes del
# 2026-10-10, que es cuando se añadió la columna-- y sin las siete no se puede
# preguntar por el sello. Se llena solo: `transfersearch` sí las trae.


@dataclass(frozen=True, slots=True)
class Objetivo:
    """El jugador tuyo al que se le busca precio."""

    ht_player_id: int
    edad: int
    primaria: Rasgo
    secundaria: Rasgo
    terciaria: Rasgo
    especialidad: int = 0
    #: Las siete habilidades enteras. Hacen falta para preguntarle a la regla
    #: de Hattrick, que mira la cuarta y pone tope a las demás; la terna sola
    #: no basta. Vacío significa «no las tenemos», no «están a cero».
    habilidades: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Candidato:
    """Un jugador del mercado que podría servir de comparable."""

    ht_player_id: int
    nombre: str
    edad: int
    #: Los dias de su edad. Hacen falta para el tope de los 17.
    dias: int
    puja: int
    precio_pedido: int
    tiene_puja: bool
    plazo: str
    tsi: int
    #: Su FORMA, de 1 a 8. No entra en el parecido --el usuario comparo por
    #: habilidades-- pero se guarda y se enseña: es columna del Comparador de
    #: Transferencias del propio juego. `-1` es «no la sabemos».
    forma: int
    especialidad: int
    lesion: int
    vendedor: int
    liga_del_vendedor: int
    #: El pais de nacimiento, para poder enseñar su bandera.
    pais: int
    primaria: Rasgo
    secundaria: Rasgo
    terciaria: Rasgo
    #: Igual que en `Objetivo`: las siete, para poder aplicar la regla del juego.
    habilidades: Mapping[str, int] = field(default_factory=dict)


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
    #: Los dias de la edad del vendido. `-1` en las ventas guardadas antes de
    #: la columna, y entonces el tope de los 17 no se les aplica.
    dias: int = -1
    #: Las siete habilidades del vendido, si las tenemos. Las ventas anteriores
    #: a la columna las traen vacias y por eso no pueden llegar al 100 %.
    habilidades: Mapping[str, int] = field(default_factory=dict)
    #: Lo que valia para Hattrick al encontrarlo. No entra en el parecido
    #: --el usuario comparo por habilidades, no por TSI-- pero se enseña,
    #: porque es la medida que todo el mundo tiene en la cabeza.
    tsi: int = 0
    #: Su pais de nacimiento, para la bandera.
    pais: int = 0
    #: Su FORMA al encontrarlo, de 1 a 8. `-1` en las ventas guardadas antes
    #: de que hubiera columna.
    forma: int = -1
    #: Lo que PEDIA el vendedor cuando se abrio la fila. Cero es «no lo
    #: sabemos»: ni las ventas viejas ni una fila abierta antes del 2026-11-07.
    precio_pedido: int = 0
    #: CUANDO CIERRA SU SUBASTA, que para una venta ya resuelta es cuando se
    #: vendio. Viaja aqui desde el 2026-11-07, y antes no: se decia que «deja
    #: de importar en cuanto la venta se resuelve». Importa, por dos cosas.
    #:
    #: La columna «Fecha» que pidio el usuario es esta, y hasta hoy la pantalla
    #: la sacaba de un diccionario `{jugador: plazo}`. Desde la 0105 un mismo
    #: jugador puede tener DOS subastas --el 490357848 sale dos veces en su
    #: propio Comparador, a 215.220 y a 125.000-- asi que esa clave se quedaba
    #: con el plazo de una de las dos y lo pegaba a las dos filas. Con el plazo
    #: dentro de la venta, cada fila lleva el suyo.
    plazo: datetime | None = None
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
    #: Si el propio Hattrick ensenaria esta venta al comparar a este jugador,
    #: comprobado contra su regla --ver `criterios_hattrick`--. Es un SELLO, no
    #: un peso: no entra en la media ni cambia el orden. Sirve para poder decir
    #: «esto lo avalaria el juego» y para medir cuanto se separa nuestra
    #: escalera de la suya antes de decidir si la sustituimos.
    #:
    #: Falso tambien cuando no tenemos las siete habilidades de la venta, que
    #: es el caso de todo lo guardado antes del 2026-10-10.
    avalado_por_hattrick: bool = False
    # AQUÍ VIVÍA `ocupa`, y se fue con el recorte el 2026-11-08. Decía si una
    # venta ocupaba plaza del fondo sin contar para la media, y existía para
    # dos cosas que ya no existen: el corte por peso y la puerta de la
    # búsqueda. Sin nada que recortar, no hay plazas que ocupar.


@dataclass(frozen=True, slots=True)
class Estimacion:
    """El resultado. Puede ser «todavía no» sin ser un error."""

    media: int | None
    mediana: int | None
    n: int
    peso_minimo: int
    provisionales: int
    comparables: tuple[Comparable, ...]

    # AQUÍ VIVÍA `suficiente`, «el número se apoya en ocho ventas o más», y se
    # fue el 2026-11-08 con el ocho entero. La pantalla ya no compara `n` con
    # ningún objetivo: dice «este número sale de N ventas» y para. Decisión del
    # usuario, y es coherente: un objetivo de recogida --ahora 30-- no es un
    # umbral de fiabilidad, y usarlo de umbral haría leer como flojo un precio
    # apoyado en veintinueve ventas reales.


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
        habilidades=dict(skills),
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


#: Cuántos filtros de habilidad admite `transfersearch`. Son cuatro, pero el
#: cuarto se deja libre a propósito: ver `infrastructure/chpp/mercado`.
FILTROS_DE_HABILIDAD = 3


def ventana_de_hattrick(objetivo: Objetivo) -> Ventana | None:
    """Lo que le pediría Hattrick al mercado para este jugador.

    Traduce sus criterios a una `Ventana` nuestra: su ventana de edad tal cual
    y las TRES PRIMERAS habilidades de su lista, que son las que identifican al
    jugador. `transfersearch` acepta exactamente tres filtros de habilidad, así
    que la cuarta --cuando existe-- y los topes de las de abajo no caben en la
    petición: se aplican al volver, en `peso_de`, que es donde se decide si la
    venta se gana el 100 %.

    `None` cuando no tenemos las siete habilidades del jugador, que es lo único
    con lo que se puede preguntar su regla.
    """
    if not objetivo.habilidades:
        return None
    criterios = criterios_de(objetivo.edad, dict(objetivo.habilidades))
    tres = criterios.habilidades[:FILTROS_DE_HABILIDAD]
    if len(tres) < FILTROS_DE_HABILIDAD:
        return None
    primera, segunda, tercera = tres
    return Ventana(
        peso=PESO_DE_HATTRICK,
        edad_minima=max(EDAD_MINIMA, criterios.edad_minima),
        edad_maxima=criterios.edad_maxima,
        primaria=Franja(primera.habilidad, primera.minimo, primera.maximo),
        secundaria=Franja(segunda.habilidad, segunda.minimo, segunda.maximo),
        terciaria=Franja(tercera.habilidad, tercera.minimo, tercera.maximo),
    )


def clave_de_criterios(objetivo: Objetivo) -> str:
    """Con qué se le está comparando, en una cadena que se pueda comparar.

    2026-10-26, decisión del usuario sobre qué pasa cuando los criterios de un
    jugador se mueven: «en ese caso, la gráfica de precios volverá a empezar».

    POR QUÉ SE MUEVEN. Los criterios son del jugador y Hattrick los recalcula
    con él: al cumplir años cambia su ventana de edad, y al subir una habilidad
    cambia cuál lo identifica y con qué banda. Desde ese momento el barrido
    está preguntando por OTRA gente, así que los números de antes y los de
    después no son la misma medida y unirlos con una línea sería mentir.

    LA CLAVE ES LA BÚSQUEDA, no la terna. Se construye de la ventana que de
    verdad sale por el cable --edad y las tres franjas-- porque es exactamente
    lo que determina a quién se compara. Una cuarta habilidad que suba y le
    cambie el tope a Hattrick mueve la ventana sin mover la terna, y tiene que
    contar; mirar sólo la terna se lo perdería.

    Vacío cuando no hay búsqueda posible --sin las siete habilidades-- y eso
    también es una clave válida: significa «no se le está comparando con
    nadie», y es distinto de cualquier ventana.
    """
    ventana = ventana_de_hattrick(objetivo)
    if ventana is None:
        return ""
    partes = [f"{ventana.edad_minima}-{ventana.edad_maxima}"]
    for franja in (ventana.primaria, ventana.secundaria, ventana.terciaria):
        partes.append(f"{franja.habilidad}:{franja.minimo}-{franja.maximo}")
    return "|".join(partes)


def plan_de_busqueda(objetivo: Objetivo) -> tuple[Ventana, ...]:
    """La búsqueda de un jugador: UNA, la de los criterios de Hattrick.

    Le pedimos al mercado exactamente lo mismo que pediría el juego, para que
    lo que entre sea «lo que él enseñaría» y no una aproximación nuestra.

    SE FUE LA ESCALERA ANCHA (2026-10-26, decisión del usuario: «no hay
    búsqueda ampliada... se acaba: sólo criterios»). Eran cuatro ventanas más
    --95, 90, 80 y 75-- que se abrían una tras otra hasta reunir ocho
    comparables, y recorrerlas costaba hasta cinco peticiones por jugador.

    Lo que se gana es el barrido diario. Con una sola ventana, mirar a los
    veinticinco jugadores cuesta unas veinticinco peticiones al día; con la
    escalera entera habrían sido más de cien, contra una cuota que es de la
    aplicación y no de cada manager. El usuario eligió ver el mercado TODOS LOS
    DÍAS con menos anchura, en vez de una quinta parte de la plantilla por
    semana con más.

    Y DESDE EL 2026-10-27 LA ESCALERA YA NO EXISTE NI PARA PUNTUAR. Aquel día
    dejó de disparar búsquedas y conservó los pesos; ahora se fue del todo, así
    que lo que entra por esta única ventana vale 90 si lo avala la regla y 100
    si además está clavado. Nada más entra.

    Devuelve vacío cuando no se puede preguntar la regla, que pasa sin las
    siete habilidades del jugador. Antes la escalera hacía de red en ese caso;
    ahora no hay red, y es lo correcto: buscar sin saber a quién se parece
    gastaría cuota para traer gente que después no se puede puntuar.
    """
    ventana = ventana_de_hattrick(objetivo)
    return (ventana,) if ventana is not None else ()


def lo_ensenaria_hattrick(candidato: Perfilado, objetivo: Objetivo) -> bool:
    """Si el propio Hattrick enseñaría esta venta al comparar a este jugador.

    Le pregunta a `criterios_hattrick` qué criterios usaría el juego para
    nuestro jugador y comprueba al candidato contra todos: la ventana de edad y
    cada habilidad, incluidos los topes de las que no lo identifican.

    DEVUELVE FALSO SI NO TENEMOS LAS SIETE HABILIDADES de alguno de los dos. La
    regla mira la cuarta y pone tope a las demás, así que con la terna sola no
    se puede responder, y responder a medias sería peor que no responder: daría
    por bueno a un jugador que Hattrick descartaría por una cuarta alta.

    Las ventas que se guardaron antes de que existiera la columna de
    habilidades caen por aquí, y se quedan con el peso que les dé la escalera
    nuestra. No se borran ni se inventan: envejecen y se reemplazan solas.
    """
    if not candidato.habilidades or not objetivo.habilidades:
        return False
    criterios = criterios_de(objetivo.edad, dict(objetivo.habilidades))
    if not criterios.edad_minima <= candidato.edad <= criterios.edad_maxima:
        return False
    # EL TOPE DE DIAS DE LOS 17, que es la ultima parte de la regla que faltaba
    # por aplicar. A los 17 anos Hattrick anade «Dias <= 24», y es una CONSTANTE:
    # el mismo perfil pedido desde dos fichas con dias distintos --29a 2d y
    # 28a 20d-- da el mismo 24, asi que no sale de la edad del jugador (FASE L).
    #
    # SI NO SABEMOS LOS DIAS DEL CANDIDATO, el tope no se aplica. Las ventas
    # guardadas antes de la columna traen `dias = -1` y se quedan como estaban:
    # mejor eso que inventarles una fecha. No se pueden rellenar, porque haria
    # falta saber los dias que tenia el vendido EL DIA DE LA VENTA y CHPP no lo
    # publica, igual que con las habilidades (migracion 0102).
    dias = getattr(candidato, "dias", -1)
    if criterios.tope_de_dias is not None and dias >= 0 and dias > criterios.tope_de_dias:
        return False
    return all(
        criterio.admite(max(0, candidato.habilidades.get(criterio.habilidad, 0)))
        for criterio in criterios.habilidades
    )


def esta_clavado(candidato: Perfilado, objetivo: Objetivo) -> bool:
    """Misma edad y las tres habilidades en el mismo nivel.

    No comprueba que la terna sea la misma: eso ya lo mira quien llama, y
    repetirlo aquí invitaría a usar esta función suelta creyendo que lo hace.

    LA EDAD EN AÑOS Y NO EN DÍAS, por la misma razón que la busca en años la
    propia búsqueda: `transfersearch` filtra por años cumplidos, así que pedir
    los días estrecharía por un criterio que el mercado no sabe aplicar y
    dejaría el clavado en algo casi inalcanzable.
    """
    return (
        candidato.edad == objetivo.edad
        and candidato.primaria.nivel == objetivo.primaria.nivel
        and candidato.secundaria.nivel == objetivo.secundaria.nivel
        and candidato.terciaria.nivel == objetivo.terciaria.nivel
    )


def peso_de(candidato: Perfilado, objetivo: Objetivo) -> int | None:
    """Lo que vale este candidato, o `None` si no se le parece lo bastante.

    SÓLO HAY DOS PESOS, y en este orden:

      · 100, CLAVADO: misma edad y las tres habilidades más altas, las mismas y
        en el mismo nivel. «100 = coincidencia exacta Edad + top 3
        habilidades», palabras del usuario.
      · 90, EL SELLO: el propio Hattrick lo enseñaría al comparar a nuestro
        jugador, comprobado contra su regla. «90 = aparece en el comparador de
        Hattrick pero no es exactamente el mismo jugador», también suyas.

    Lo que no es ninguna de las dos cosas devuelve `None`: no es que pese poco,
    es que no es comparable. Ahí se fue la escalera nuestra entera el
    2026-10-27 --«solo hay esos dos escalones, el resto ya no los quiero»--,
    con el 95, el 90, el 80, el 75 y la ventana de la terciaria.

    EL CLAVADO SE MIRA PRIMERO, y es deliberado: casi todo clavado está además
    avalado, y preguntando al sello antes se quedaría en 90 justo el comparable
    que mejor existe. Mientras el sello valió 100 el orden daba igual; desde
    que vale 90, no.

    EL SELLO SE SALTA NUESTRO DESEMPATE DE TERNA, y eso no se toca
    (2026-10-18). Pedimos que las tres habilidades más altas sean LAS MISMAS y
    en el mismo orden --quien tiene los niveles pedidos en otras habilidades es
    otro jugador, y lo que se paga por él no dice nada del nuestro--, pero esa
    comprobación es NUESTRA, y una vez corrió antes que el sello: una venta que
    Hattrick SÍ enseñaría se caía por nuestro desempate sin que nadie le
    preguntara al sello.

    Se vio con un defensa de 21 anos, Defensa 12 y Lateral 7 (jugador
    491919135). Hattrick no usa su Anotacion de criterio --va quinta en
    importancia y le pone techo en 10-- asi que su busqueda admite Anotacion de
    0 a 10. De esos once perfiles, SIETE --los de Anotacion 0 a 6-- tienen otra
    terna que la suya, porque sin Anotacion alta el Lateral se les sube al
    segundo puesto. Los once los ensenaria Hattrick; nosotros nos quedabamos
    cuatro. Y la busqueda si los pedia: `ventana_de_hattrick` va por los
    criterios, no por la terna, asi que se gastaba cuota en traerlos para
    tirarlos al llegar.

    La terna es nuestro modo de decir «es el mismo jugador» cuando no tenemos
    regla; cuando la hay, manda la regla.
    """
    misma_terna = (
        candidato.primaria.habilidad == objetivo.primaria.habilidad
        and candidato.secundaria.habilidad == objetivo.secundaria.habilidad
        and candidato.terciaria.habilidad == objetivo.terciaria.habilidad
    )
    if misma_terna and esta_clavado(candidato, objetivo):
        return PESO_DEL_CLAVADO
    if lo_ensenaria_hattrick(candidato, objetivo):
        return PESO_DE_HATTRICK
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
        # `parse_transfersearch` ya los devuelve; antes se tiraban.
        dias=int(fila.get("age_days", -1) if fila.get("age_days") is not None else -1),
        puja=puja,
        precio_pedido=int(fila.get("asking_price", 0) or 0),
        # La bandera del parser manda cuando viene: es la que distingue
        # «nadie pujó» de «ofrecieron cero».
        tiene_puja=bool(fila["has_bids"]) if "has_bids" in fila else puja > 0,
        plazo=str(fila.get("deadline", "") or ""),
        tsi=int(fila.get("tsi", 0) or 0),
        # `parse_transfersearch` ya la devolvia; se tiraba aqui.
        forma=int(fila["form"]) if fila.get("form") is not None else -1,
        especialidad=int(fila.get("specialty", 0) or 0),
        lesion=int(fila["injury_level"]) if fila.get("injury_level") is not None else -1,
        vendedor=int(fila.get("seller_team_id", 0) or 0),
        liga_del_vendedor=int(fila.get("seller_league_id", 0) or 0),
        pais=int(fila.get("native_country_id", 0) or 0),
        habilidades=dict(habilidades),
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


def fecha_de_la_venta(venta: Guardado) -> datetime:
    """Cuándo se pagó este precio.

    EL PLAZO Y NO `visto_el` (2026-11-08). El plazo es la hora de cierre que
    publica Hattrick, o sea el instante en que ese dinero cambió de manos; el
    `visto_el` es cuándo pasamos nosotros por delante del anuncio. Lo que
    envejece es el precio pagado, así que la caducidad y el orden se cuentan
    desde el plazo. Sin plazo --fila vieja o incompleta-- queda `visto_el`,
    que es lo único que hay.
    """
    return _aware(venta.plazo) if venta.plazo is not None else _aware(venta.visto_el)


def caduco(venta: Guardado, ahora: datetime) -> bool:
    """Si ya pasó sus 24 semanas.

    CUMPLIRLO NO SACA A NADIE. Es una marca, no una expulsión: «mientras no
    haya una persona, un jugador que haya entrado dentro de la
    caracterización, esa persona puede seguir así tenga más de 24 semanas»
    --usuario, 2026-11-08--. Lo único que saca a alguien de la lista es el
    relevo de `comparables_de`, y ése sólo actúa con la lista llena.

    Antes se llamaba `reemplazable` y contaba desde `visto_el`. El nombre
    mentía por partida doble: no autorizaba ningún reemplazo, y medía la edad
    del anuncio en vez de la del precio.
    """
    return _aware(ahora) - fecha_de_la_venta(venta) >= VIDA


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

    Se devuelven los `OBJETIVO_DE_DATOS` mejores de entre las ventas CERRADAS,
    y detrás las que siguen en stand-by, que no son filas de la tabla pero hay
    que contarlas para la pastilla.
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
                # TODO CADUCA DESDE EL 2026-11-08, regla del usuario. Hasta
                # ese día el clavado era inmune --«el 100% no caduca nunca»,
                # 2026-10-07-- y la marca sólo salía en los avalados.
                #
                # Y SIGUE SIENDO SÓLO UNA MARCA: no saca a nadie. Lo que saca
                # es el relevo, y el relevo necesita la lista llena.
                viejo=caduco(venta, ahora),
                avalado_por_hattrick=lo_ensenaria_hattrick(venta, objetivo),
                cuenta=cuenta_para_el_numero(venta),
            )
        )
    medidos.sort(
        key=lambda c: (
            -c.peso,
            -fecha_de_la_venta(c.venta).timestamp(),
            -c.venta.precio,
            0 if c.venta.especialidad == objetivo.especialidad else 1,
        )
    )
    # EL RELEVO, y es todo lo que queda de la selección (2026-11-08).
    #
    # Su regla, en sus palabras: «Nuestro objetivo sí debe ser obtener hasta 30
    # datos. Si nos faltan, entonces agregar. Si ya tenemos 30 y llega el 31,
    # podemos reemplazar por uno que sea 90, si el nuevo es de 100, o
    # reemplazar el viejo por uno de los nuevos.»
    #
    # ESO ES EXACTAMENTE QUEDARSE CON LOS 30 PRIMEROS DE ESTE ORDEN, y conviene
    # que esté escrito por qué, porque la regla suya es incremental y ésta no.
    # Un recién llegado entra, bajo su regla, sólo si puede desplazar a alguien
    # PEOR: de menos peso, o del mismo peso y más viejo. Y desplaza justo a ese
    # peor. Aplicado una y otra vez, lo que queda es el top 30 por (peso, luego
    # frescura) --que es este orden-- sin necesidad de recordar en qué momento
    # llegó cada uno. Se le preguntó el caso límite el 2026-11-08: con 30
    # clavados frescos y un avalado nuevo llamando a la puerta, el avalado NO
    # entra, porque no hay nadie peor que él. Que es lo que hace el corte a 30.
    #
    # AQUÍ VIVÍA EL CORTE POR PESO, y es lo que él vino a quitar: cuando ocho
    # comparables pesaban 100, expulsaba a TODOS los de 90 aunque fueran ventas
    # reales que Hattrick enseñaría. Medido sobre un caso de doce: la media
    # pasaba de 150.000 a 141.923 al dejarlos entrar.
    #
    # Y LA LISTA ES SÓLO DE VENTAS CON PRECIO (su regla del 2026-11-07, «si no
    # promedia, no es fila»). Las de stand-by van detrás, fuera del tope: no se
    # pintan, pero `estimar` las cuenta para decir cuántas están esperando su
    # precio.
    cerradas = [c for c in medidos if c.venta.firme][:OBJETIVO_DE_DATOS]
    en_stand_by = [c for c in medidos if not c.venta.firme]
    return (*cerradas, *en_stand_by)


# AQUÍ VIVÍA `ocupa_plaza`, y se fue el 2026-11-08 con el recorte.
#
# Respondía a «¿ocupa una de las ocho plazas del fondo, y por tanto evita salir
# a buscar más?», que era distinta de «¿entra en el número?»: una subasta
# abierta con puja ocupaba sin promediar. Las dos cosas que la usaban --el
# corte por peso y la puerta de la búsqueda-- ya no existen, así que no hay
# plazas, y lo único que se pregunta de una venta es si tiene precio.


def nunca_tuvo_puja(venta: Guardado) -> bool:
    """Si en ningun momento vimos una puja sobre este anuncio.

    `HighestBid` vale 0 EXACTAMENTE cuando no hay pujas --lo dice la
    documentacion oficial y por eso el parser manda tambien `has_bids`-- asi
    que un cero aqui no es «ofrecieron cero», es «nadie habia ofrecido nada
    cuando lo miramos».

    ES LA COLUMNA «NO PUJA DETECTADA» que pidio el usuario el 2026-11-07, y el
    caso que importa no es el anuncio muerto: es el que SI SE VENDIO sin que
    nosotros llegaramos a ver una sola puja. Esa fila dice dos cosas a la vez
    --se pago tanto, y la subasta se movio entre dos barridos nuestros-- y es
    justo lo que le paso al 472301981.
    """
    return venta.puja <= 0


def es_una_puja_abierta(venta: Guardado) -> bool:
    """Si es una subasta que no ha cerrado Y alguien ha ofrecido dinero.

    ES LO QUE LA PANTALLA LLAMA «puja abierta», y hacia falta separarlo desde
    el 2026-11-07, el dia que los anuncios SIN NINGUNA PUJA empezaron a
    guardarse. Hasta entonces «no firme» y «puja abierta» eran lo mismo, asi
    que `provisionales` se contaba con un `not venta.firme` y decia la verdad.

    Ya no: el barrido es diario y cada pasada trae decenas de anuncios a cero,
    y todos se guardan. Con el
    criterio viejo, un jugador sin UNA sola puja a su alrededor veria «8 pujas
    abiertas, fuera del numero», que es exactamente lo contrario de lo que
    pasa. Y desde hoy esas filas tampoco se enseñan --decision del usuario:
    «los jugadores que nunca se vendieron, no deben ir en la lista»-- asi que
    la pastilla es lo UNICO que se dice de ellas y no puede mentir.

    Una puja abandonada --con dinero ofrecido y los intentos agotados-- sigue
    contando aqui: su subasta cerro para Hattrick pero no para nosotros, que es
    justo lo que la pastilla avisa.
    """
    return not venta.firme and not nunca_tuvo_puja(venta)


def se_puede_descartar(venta: Guardado, ahora: datetime | None = None) -> bool:
    """Si esta venta ya se puede borrar del fondo. A LAS DOS COMPROBACIONES.

    DECISIÓN DEL USUARIO (2026-11-08): «Si fueron vendidos, entonces les
    tomamos el precio. Si no fueron vendidos, simplemente eso se descarta, eso
    no sirve para nada.» Y se le preguntó expresamente a quién se le aplica:
    **a cualquiera, con puja o sin ella.**

    DOS COMPROBACIONES, NO DOS DÍAS. `intentos` sólo sube cuando se preguntó de
    verdad y Hattrick no trajo el traspaso; una llamada que no llegó no cuenta.
    Así que llegar a dos significa que se le preguntó dos veces y no estaba, no
    que hayan pasado dos días mirando a otro lado. Eso es lo que mataba antes:
    18 de 20 filas caducaron con CERO preguntas hechas.

    UNA VENTA FIRME NO SE DESCARTA NUNCA. Esa es la que se vino a buscar.

    LO QUE SE PIERDE Y ÉL ACEPTÓ: una venta con puja está garantizada por las
    reglas del juego --medido el 2026-10-07 con Guido Bernacki, cuyo traspaso
    apareció con el plazo desviado trece segundos-- así que si Hattrick la
    publica tarde, a la tercera ya no habrá nadie preguntando. Se le planteó
    con esa cifra delante y eligió el borrado: una fila sin precio no vale
    nada, y la alternativa era el zombi que ocupaba sitio para siempre.

    `ahora` NO SE USA. Las comprobaciones ya sellan el paso del tiempo --una al
    día, y sólo después del cierre--. Se queda en la firma porque el día que el
    criterio quiera mirar el reloj, quien llama no tiene que cambiar.
    """
    if venta.firme:
        return False
    return venta.intentos >= COMPROBACIONES


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

    Las pujas NO se tiran: siguen en el fondo, se siguen vigilando y se
    siguen enseñando en la tabla marcadas como lo que son. Lo unico que no
    hacen es promediar.
    """
    return venta.firme


def estimar(comparables: Sequence[Comparable]) -> Estimacion:
    """La media y la mediana, las dos ponderadas por parecido.

    CON LO QUE HAYA (2026-10-26, decisión del usuario: «precio con los que
    hayan»). Hasta ese día, por debajo de ocho ventas no se daba número:
    sólo la lista y un «faltan tantas».

    Lo cambió al quitar la búsqueda ampliada, y es la consecuencia directa de
    eso: sin escalera ancha hay jugadores que no van a juntar ocho ventas
    cerradas, y con la regla vieja se quedarían sin precio para siempre. Un
    número apoyado en tres ventas no es tan bueno como uno de ocho, pero es
    muchísimo mejor que ninguno, que es lo que informa cero.

    LO QUE NO SE PIERDE: `n` dice sobre cuántas se hizo, y eso es lo que la
    pantalla enseña --«este número sale de 3 ventas»--. Lo que se quita es la
    decisión de NO RESPONDER, que era nuestra y no suya. Y desde el 2026-11-08
    `n` va solo, sin objetivo al lado: ver `OBJETIVO_DE_DATOS`.

    Sin ni una venta cerrada sigue sin haber número, y eso no es una regla sino
    aritmética: no hay nada que promediar.

    `provisionales` NO se cuenta sobre las que cuentan (2026-10-09): sobre
    ésas valdría siempre cero, y un campo que no puede cambiar no informa de
    nada. Se cuenta sobre las subastas con dinero ofrecido que no han cerrado,
    que es lo que la pantalla dice de ellas; ver `es_una_puja_abierta`, que es
    donde está escrito por qué un `not venta.firme` ya no sirve.
    """
    # `comparables` lleva TODAS, para que la pantalla pueda enseñarlas; el
    # numero se hace solo con las que cuentan.
    todas = tuple(comparables)
    elegidos = tuple(c for c in todas if c.cuenta)
    if not elegidos:
        return Estimacion(
            media=None,
            mediana=None,
            n=0,
            peso_minimo=0,
            provisionales=sum(1 for c in todas if es_una_puja_abierta(c.venta)),
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
        provisionales=sum(1 for c in todas if es_una_puja_abierta(c.venta)),
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
    """Si ya cerró la subasta y por tanto se le puede preguntar su precio.

    UN SOLO BORDE DESDE EL 2026-11-08, y el de abajo: antes del cierre no hay
    nada que preguntar, y preguntar a ciegas gastaría una llamada por cada
    comprobación. Sin margen de espera: «busca en cuanto tengas anotado que la
    subasta termina», y el plazo es dato de Hattrick, no estimación nuestra.

    SE FUE EL BORDE DE ARRIBA, que era `VENTANA_DE_RESOLUCION`: tres días de
    reloj desde el cierre y «lo que fue, fue». El usuario lo cambió por un
    recuento de comprobaciones --ver `COMPROBACIONES`-- porque el plazo de
    reloj se cumplía solo, sin preguntar. Con esto, una venta sigue siendo
    candidata hasta que gaste sus dos comprobaciones, por mucho que tarde en
    abrirse la aplicación: «Cualquier 2 sincronizaciones que hayan sucedido
    después de las 3 de la tarde... solo 2.»

    Sin plazo no se puede saber si cerró, así que no se pregunta. Esa fila no
    tiene salida y la borra `se_puede_descartar` en cuanto gaste sus dos.
    """
    if plazo is None:
        return False
    return _aware(plazo) + MARGEN_TRAS_EL_PLAZO <= _aware(ahora)


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


def le_toca_hoy(sello: datetime | None, ahora: datetime) -> bool:
    """Si a este jugador todavía no se le han buscado comparables HOY.

    «Una vez por día natural y por jugador, independiente de cuántas veces
    sincronices» (2026-10-26, decisión del usuario).

    EL DÍA SE COMPARA EN UTC, igual que el de la resolución: es el huso en el
    que viven todos los sellos de esta base. No es el día de Hattrick ni el del
    usuario, y da igual que no lo sea: lo único que tiene que cumplir es ser
    siempre el mismo, porque de lo que protege es de barrer dos veces seguidas,
    y la aplicación admite seis sincronizaciones por hora.

    Sin sello le toca: nunca se le ha buscado nada.

    LO QUE HABÍA AQUÍ ANTES, y por qué se fue. Un reparto por turnos sacado del
    propio identificador: `% 5` contra la semana para los escalones anchos y
    `% 6` contra el día para el exacto, disparado por la actualización
    económica de la liga menos 24 horas. No guardaba ningún reloj y no había
    nada que recolocar al fichar o vender, que para una rotación es mejor
    diseño y por eso duró.

    Un barrido diario no rota: le toca a todos, todos los días. La pregunta ya
    no es «¿a quién le toca hoy?» sino «¿a éste ya se le miró hoy?», y ésa
    depende de lo que haya pasado, así que hay que guardarla.
    """
    if sello is None:
        return True
    return _aware(sello).astimezone(UTC).date() < _aware(ahora).astimezone(UTC).date()


# AQUÍ VIVÍA `hay_que_buscar`, «¿me faltan comparables?», y se fue el
# 2026-11-08. Había dejado de ser una puerta el 2026-10-26 --desde entonces el
# turno busca siempre-- y sólo quedaba de bandera para el informe. Con el ocho
# derogado no le queda ni umbral con el que comparar: el objetivo son 30, los
# junta el mercado a su ritmo, y eso no es algo que la aplicación decida.


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
