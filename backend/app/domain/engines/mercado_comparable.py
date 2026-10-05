"""Qué pagaría hoy el mercado por un jugador tuyo, mirando a los que se le parecen.

Diseñado con el usuario el 2026-10-04. La regla es suya de principio a fin, y
eso importa por `AGENTS.md`: aquí no se ajusta ningún parámetro contra la
plantilla propia. Lo que hay es una media ponderada de datos ajenos con unos
pesos que él fijó, que es estadística descriptiva aplicada a una regla general
suministrada expresamente, no una regresión.

LA IDEA. Dos jugadores son comparables si tienen la misma edad y las mismas
tres habilidades más altas, en el mismo orden y al mismo nivel. Se buscan así,
exactos, y sólo cuentan los que ya tienen una puja encima. Si no se reúnen
seis, se van abriendo ventanas en un orden fijo, y cada apertura se paga con
peso: el que apareció exacto vale 100%, el que hizo falta ensanchar la
terciaria dos niveles vale 85%, y así hasta un suelo de 30%, donde la búsqueda
se rinde antes que inventar un precio con gente que no se le parece.

LAS SIETE DECISIONES QUE HAY DETRÁS, todas del usuario y todas con consecuencia:

1. **La media es ponderada**, suma de peso por puja dividida por la suma de
   pesos. Si no, los pesos no harían nada. Cuando todos entran al 100%
   coincide con la media simple.
2. **El desempate de habilidades lo fijó él**: creación, portería, defensa,
   anotación, lateral, pases. Hace falta porque dos habilidades al mismo nivel
   darían ternas distintas en dos semanas, y el mismo jugador dejaría de ser
   comparable consigo mismo.
3. **La resistencia NO entra**, ni el balón parado. Son seis habilidades, no
   ocho. Dos jugadores con la misma resistencia y distinto remate no se
   parecen en precio, y la resistencia sale terciaria con muchísima facilidad.
4. **Acumula y no repite.** Cada jugador cuenta una vez, con el peso de la
   ventana más estrecha que lo admite, y eso se calcula aquí sobre sus datos:
   no depende de en qué búsqueda apareció, así que el orden de llegada no
   cambia el resultado.
5. **La terna tiene que coincidir en los NOMBRES, no sólo en los niveles.**
   Una búsqueda por «creación 11, pases 9, defensa 8» devuelve también a un
   delantero que tenga esos tres valores y anotación 14; su terna es otra y es
   otro jugador. Por eso se recalcula la terna del candidato y se compara
   hueco por hueco.
6. **Suelo de 30%.** Si al llegar ahí no hay seis, no hay precio: la pantalla
   dice que esta semana no hay mercado comparable y enseña los que encontró.
7. **Se corre una vez por semana**, en la primera visita posterior al viernes
   a las 20:00, ver `toca_buscar`.

LO QUE LA PANTALLA ESTÁ OBLIGADA A DECIR. La puja más alta es una puja EN
CURSO, no una venta cerrada: el plazo sigue abierto y el precio todavía sube.
El número que sale de aquí es «lo que se está pujando hoy por los que se le
parecen», y llamarlo «lo que vale» sería mentir en una palabra. En el fichero
del mercado no hay ni una venta cerrada.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, tzinfo
from typing import Any

from app.domain.value_objects.ht_time import HATTRICK_TZ

# El orden de desempate, dictado por el usuario el 2026-10-04. También es la
# lista entera de habilidades que entran: seis, sin resistencia ni balón
# parado. No se reordena ni se amplía sin que él lo diga, porque cambiarlo
# cambia a qué jugador se parece cada jugador.
ORDEN_DE_DESEMPATE: tuple[str, ...] = (
    "playmaking",
    "keeper",
    "defending",
    "scoring",
    "winger",
    "passing",
)

_RANGO = {habilidad: puesto for puesto, habilidad in enumerate(ORDEN_DE_DESEMPATE)}

#: Cuántos comparables hacen falta para dar un precio.
MINIMO_DE_COMPARABLES = 6

#: Por debajo de este peso la búsqueda se rinde.
SUELO_DE_PESO = 30

#: Nadie juega en el primer equipo con menos de 17 años: ensanchar la edad
#: hacia abajo no puede pasar de aquí.
EDAD_MINIMA = 17


@dataclass(frozen=True, slots=True)
class Rasgo:
    """Una habilidad con su nivel."""

    habilidad: str
    nivel: int


@dataclass(frozen=True, slots=True)
class Escalon:
    """Cuánto se abre cada ventana, y lo que cuesta abrirla.

    Los cuatro primeros números son el radio de la ventana en cada rasgo: 0 es
    exacto, 1 es «uno arriba o uno abajo».
    """

    edad: int
    primaria: int
    secundaria: int
    terciaria: int
    peso: int


# La escalera, tal y como la dictó el usuario. La primera vuelta es suya
# literal (terciaria, terciaria, secundaria, edad, primaria) y las dos
# siguientes repiten esa misma secuencia de aperturas encima de lo ya abierto,
# que es lo que él llamó «volvemos a comenzar», bajando de cinco en cinco
# hasta el suelo de 30.
#
# Dos invariantes que vigila `test_mercado_comparable.py`, porque si se rompen
# el motor miente sin fallar: ninguna ventana se ESTRECHA al bajar de escalón
# (si no, un jugador podría cobrar un peso peor del que le toca), y los pesos
# bajan siempre (si no, `peso_de` devolvería el primero que encaja y no el
# mejor).
ESCALERA: tuple[Escalon, ...] = (
    Escalon(edad=0, primaria=0, secundaria=0, terciaria=0, peso=100),
    Escalon(edad=0, primaria=0, secundaria=0, terciaria=1, peso=90),
    Escalon(edad=0, primaria=0, secundaria=0, terciaria=2, peso=85),
    Escalon(edad=0, primaria=0, secundaria=1, terciaria=2, peso=80),
    Escalon(edad=1, primaria=0, secundaria=1, terciaria=2, peso=75),
    Escalon(edad=1, primaria=1, secundaria=1, terciaria=2, peso=70),
    # Segunda vuelta.
    Escalon(edad=1, primaria=1, secundaria=1, terciaria=3, peso=65),
    Escalon(edad=1, primaria=1, secundaria=1, terciaria=4, peso=60),
    Escalon(edad=1, primaria=1, secundaria=2, terciaria=4, peso=55),
    Escalon(edad=2, primaria=1, secundaria=2, terciaria=4, peso=50),
    Escalon(edad=2, primaria=2, secundaria=2, terciaria=4, peso=45),
    # Tercera vuelta, que termina en el suelo.
    Escalon(edad=2, primaria=2, secundaria=2, terciaria=5, peso=40),
    Escalon(edad=2, primaria=2, secundaria=2, terciaria=6, peso=35),
    Escalon(edad=2, primaria=2, secundaria=3, terciaria=6, peso=30),
)


# La escalera del MODO DUO, sin terciaria. Es la misma idea con una vuelta de
# cuatro aperturas en vez de cinco: los dos escalones que abrian la terciaria
# pasan a la secundaria, que ahora es el rasgo menos importante que queda.
# Mismo suelo de 30 y mismos catorce escalones.
ESCALERA_DUO: tuple[Escalon, ...] = (
    Escalon(edad=0, primaria=0, secundaria=0, terciaria=0, peso=100),
    Escalon(edad=0, primaria=0, secundaria=1, terciaria=0, peso=90),
    Escalon(edad=0, primaria=0, secundaria=2, terciaria=0, peso=85),
    Escalon(edad=1, primaria=0, secundaria=2, terciaria=0, peso=80),
    Escalon(edad=1, primaria=1, secundaria=2, terciaria=0, peso=75),
    # Segunda vuelta.
    Escalon(edad=1, primaria=1, secundaria=3, terciaria=0, peso=70),
    Escalon(edad=1, primaria=1, secundaria=4, terciaria=0, peso=65),
    Escalon(edad=2, primaria=1, secundaria=4, terciaria=0, peso=60),
    Escalon(edad=2, primaria=2, secundaria=4, terciaria=0, peso=55),
    # Tercera vuelta.
    Escalon(edad=2, primaria=2, secundaria=5, terciaria=0, peso=50),
    Escalon(edad=2, primaria=2, secundaria=6, terciaria=0, peso=45),
    Escalon(edad=3, primaria=2, secundaria=6, terciaria=0, peso=40),
    Escalon(edad=3, primaria=3, secundaria=6, terciaria=0, peso=35),
    Escalon(edad=3, primaria=3, secundaria=7, terciaria=0, peso=30),
)


@dataclass(frozen=True, slots=True)
class Objetivo:
    """El jugador tuyo al que se le busca precio.

    `terciaria` a `None` es el MODO DUO: se compara sólo por las dos primeras
    habilidades. Afloja mucho lo que cuenta como parecido, y hay mercados
    donde es la diferencia entre un precio y un «no hay nadie».
    """

    ht_player_id: int
    edad: int
    primaria: Rasgo
    secundaria: Rasgo
    terciaria: Rasgo | None


@dataclass(frozen=True, slots=True)
class Candidato:
    """Un jugador del mercado que podría servir de comparable."""

    ht_player_id: int
    nombre: str
    edad: int
    puja: int
    precio_pedido: int
    tiene_puja: bool
    lesion: int
    plazo: str
    tsi: int
    especialidad: int
    vendedor: str
    liga_del_vendedor: int
    primaria: Rasgo
    secundaria: Rasgo
    terciaria: Rasgo


@dataclass(frozen=True, slots=True)
class Comparable:
    """Un candidato aceptado, con el peso que se ganó."""

    candidato: Candidato
    peso: int


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
    terciaria: Franja | None


@dataclass(frozen=True, slots=True)
class Estimacion:
    """El resultado, que puede ser «no hay precio» sin ser un error."""

    precio: int | None
    suficiente: bool
    n: int
    peso_minimo: int
    comparables: tuple[Comparable, ...]


def terna(skills: Mapping[str, int]) -> tuple[Rasgo, Rasgo, Rasgo] | None:
    """Las tres habilidades más altas de las seis que cuentan, ya ordenadas.

    Devuelve `None` cuando no hay con qué comparar, es decir cuando las seis
    están a cero: eso no es un jugador flojo, es un hueco en los datos.

    La resistencia y el balón parado no se miran, y el empate lo rompe
    `ORDEN_DE_DESEMPATE`, así que el mismo jugador da siempre la misma terna.
    """
    rasgos = [Rasgo(nombre, max(0, int(skills.get(nombre, 0)))) for nombre in ORDEN_DE_DESEMPATE]
    ordenados = sorted(rasgos, key=lambda rasgo: (-rasgo.nivel, _RANGO[rasgo.habilidad]))
    if ordenados[0].nivel <= 0:
        return None
    return ordenados[0], ordenados[1], ordenados[2]


def escalera_de(objetivo: Objetivo) -> tuple[Escalon, ...]:
    """La escalera que le toca a este objetivo segun su modo."""
    return ESCALERA if objetivo.terciaria is not None else ESCALERA_DUO


def objetivo_de(
    ht_player_id: int,
    edad: int,
    skills: Mapping[str, int],
    *,
    con_terciaria: bool = True,
) -> Objetivo | None:
    """El objetivo a partir de un jugador propio.

    `None` cuando no se le puede sacar una terna o no se sabe su edad: sin eso
    no hay con qué buscar, y buscar «lo que sea» devolvería un precio que no
    es de nadie.
    """
    tres = terna(skills)
    if tres is None or edad <= 0:
        return None
    primaria, secundaria, terciaria = tres
    return Objetivo(
        ht_player_id=ht_player_id,
        edad=edad,
        primaria=primaria,
        secundaria=secundaria,
        terciaria=terciaria if con_terciaria else None,
    )


def ventana_de(objetivo: Objetivo, escalon: Escalon) -> Ventana:
    """La búsqueda que le corresponde a un escalón."""
    return Ventana(
        peso=escalon.peso,
        edad_minima=max(EDAD_MINIMA, objetivo.edad - escalon.edad),
        edad_maxima=objetivo.edad + escalon.edad,
        primaria=_franja(objetivo.primaria, escalon.primaria),
        secundaria=_franja(objetivo.secundaria, escalon.secundaria),
        terciaria=(
            _franja(objetivo.terciaria, escalon.terciaria)
            if objetivo.terciaria is not None
            else None
        ),
    )


def plan_de_busqueda(objetivo: Objetivo) -> tuple[Ventana, ...]:
    """Las búsquedas a recorrer, de la más estrecha a la más ancha.

    Quien las recorra para en cuanto `estimar` diga que ya hay suficientes, y
    no antes de terminar un escalón: si el sexto y el séptimo se parecen
    igual, dejar fuera al séptimo por orden de llegada sería arbitrario.
    """
    return tuple(ventana_de(objetivo, escalon) for escalon in escalera_de(objetivo))


def peso_de(candidato: Candidato, objetivo: Objetivo) -> int | None:
    """Lo que vale este candidato, o `None` si no se le parece lo bastante.

    Es el peso de la ventana más ESTRECHA que lo admite, calculado sobre sus
    propios datos. Da igual en qué búsqueda apareció, así que una búsqueda
    ancha que devuelva de más no infla a nadie ni lo degrada.
    """
    if (
        candidato.primaria.habilidad != objetivo.primaria.habilidad
        or candidato.secundaria.habilidad != objetivo.secundaria.habilidad
    ):
        return None
    tercera = objetivo.terciaria
    if tercera is not None and candidato.terciaria.habilidad != tercera.habilidad:
        return None
    for escalon in escalera_de(objetivo):
        if (
            abs(candidato.edad - objetivo.edad) <= escalon.edad
            and abs(candidato.primaria.nivel - objetivo.primaria.nivel) <= escalon.primaria
            and abs(candidato.secundaria.nivel - objetivo.secundaria.nivel) <= escalon.secundaria
            and (
                tercera is None
                or abs(candidato.terciaria.nivel - tercera.nivel) <= escalon.terciaria
            )
        ):
            return escalon.peso
    return None


def candidato_de(fila: Mapping[str, Any]) -> Candidato | None:
    """Un candidato a partir de una fila del parser del mercado.

    Devuelve `None` cuando la fila no sirve para comparar: sin jugador, o sin
    ninguna de las seis habilidades. Que la lesión falte NO lo descarta: el
    fichero no trae ese campo mientras hay un partido en juego, y su ausencia
    significa sano, nunca magullado.
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
        # Se respeta la bandera del parser cuando viene, porque es ella la que
        # distingue «nadie pujó» de «ofrecieron cero».
        tiene_puja=bool(fila["has_bids"]) if "has_bids" in fila else puja > 0,
        lesion=int(fila["injury_level"]) if fila.get("injury_level") is not None else -1,
        plazo=str(fila.get("deadline", "") or ""),
        tsi=int(fila.get("tsi", 0) or 0),
        especialidad=int(fila.get("specialty", 0) or 0),
        vendedor=str(fila.get("seller_team_name", "") or ""),
        liga_del_vendedor=int(fila.get("seller_league_id", 0) or 0),
        primaria=primaria,
        secundaria=secundaria,
        terciaria=terciaria,
    )


def recolectar(
    objetivo: Objetivo,
    filas: Iterable[Mapping[str, Any]],
    acumulado: Mapping[int, Comparable] | None = None,
) -> dict[int, Comparable]:
    """Añade a lo ya reunido los comparables que haya en estas filas.

    Quedan fuera, y cada exclusión tiene su motivo:

    · el propio jugador, si resulta que está en el mercado, porque compararlo
      consigo mismo devolvería su propia puja como precio de mercado;
    · el que no tiene puja, porque su precio pedido es una opinión del
      vendedor y no un dato del mercado;
    · el lesionado de verdad, lesión mayor que 0, porque su precio está tocado
      por la lesión y no por lo que vale. El magullado (0) y el sano (-1) sí
      entran;
    · el que no se le parece lo bastante, hasta el suelo de peso.

    El que ya estaba se queda con el mejor peso de los dos, así que el orden
    en que lleguen las búsquedas no cambia el resultado.
    """
    reunidos: dict[int, Comparable] = dict(acumulado) if acumulado else {}
    for fila in filas:
        candidato = candidato_de(fila)
        if candidato is None:
            continue
        if candidato.ht_player_id == objetivo.ht_player_id:
            continue
        if not candidato.tiene_puja or candidato.puja <= 0:
            continue
        if candidato.lesion > 0:
            continue
        peso = peso_de(candidato, objetivo)
        if peso is None:
            continue
        previo = reunidos.get(candidato.ht_player_id)
        if previo is not None and previo.peso >= peso:
            continue
        reunidos[candidato.ht_player_id] = Comparable(candidato=candidato, peso=peso)
    return reunidos


def estimar(acumulado: Mapping[int, Comparable]) -> Estimacion:
    """El precio simulado, o la constancia de que no se pudo.

    Con menos de `MINIMO_DE_COMPARABLES` no se devuelve precio, pero sí la
    lista: la pantalla tiene que poder decir «no hay mercado comparable esta
    semana» y enseñar los que sí encontró.
    """
    comparables = tuple(
        sorted(acumulado.values(), key=lambda c: (-c.peso, c.candidato.ht_player_id))
    )
    suficiente = len(comparables) >= MINIMO_DE_COMPARABLES
    denominador = sum(c.peso for c in comparables)
    precio = None
    if suficiente and denominador > 0:
        numerador = sum(c.peso * c.candidato.puja for c in comparables)
        # Redondeo al par, el mismo que usa la simulación de venta del front,
        # para que las dos cifras no discrepen en una unidad.
        precio = round(numerador / denominador)
    return Estimacion(
        precio=precio,
        suficiente=suficiente,
        n=len(comparables),
        peso_minimo=min((c.peso for c in comparables), default=0),
        comparables=comparables,
    )


# --------------------------------------------------------------------------
# Cuándo se corre
# --------------------------------------------------------------------------

#: Viernes, con lunes = 0, que es como cuenta `datetime.weekday()`.
DIA_DE_LA_BUSQUEDA = 4
HORA_DE_LA_BUSQUEDA = 20


def frontera_semanal(ahora: datetime, zona: tzinfo = HATTRICK_TZ) -> datetime:
    """El último viernes a las 20:00 anterior a `ahora`, en UTC.

    El reloj de referencia es el de Hattrick por defecto, que es el que usa
    todo lo demás en la aplicación. El usuario pidió la hora local del país
    del equipo, pero CHPP no publica la zona horaria de cada liga (lo que trae
    el fichero del mundo es un nombre de zona del juego y un formato de hora,
    no un desfase), así que la zona entra por parámetro y se cambiará el día
    que tengamos de dónde sacarla.

    El desfase no se calcula a mano: a las 20:00 de un viernes de enero y a
    las 20:00 de uno de julio les corresponden dos instantes UTC distintos, y
    de eso se encarga la base de zonas horarias.
    """
    local = (ahora if ahora.tzinfo is not None else ahora.replace(tzinfo=UTC)).astimezone(zona)
    atras = (local.weekday() - DIA_DE_LA_BUSQUEDA) % 7
    frontera = (local - timedelta(days=atras)).replace(
        hour=HORA_DE_LA_BUSQUEDA, minute=0, second=0, microsecond=0
    )
    if frontera > local:
        # Es viernes pero todavía no son las ocho: la frontera es la de hace
        # una semana.
        frontera -= timedelta(days=7)
    return frontera.astimezone(UTC)


def toca_buscar(ultima: datetime | None, ahora: datetime, zona: tzinfo = HATTRICK_TZ) -> bool:
    """Si esta visita es la primera de la semana de mercado.

    No hace falta programador de tareas: se guarda cuándo se buscó por última
    vez y se compara contra la frontera. Una fecha futura (reloj descuadrado)
    no dispara nada.
    """
    if ultima is None:
        return True
    marcada = ultima if ultima.tzinfo is not None else ultima.replace(tzinfo=UTC)
    return marcada.astimezone(UTC) < frontera_semanal(ahora, zona)


def _franja(rasgo: Rasgo, radio: int) -> Franja:
    return Franja(
        habilidad=rasgo.habilidad,
        minimo=max(0, rasgo.nivel - radio),
        maximo=rasgo.nivel + radio,
    )


def _nombre(fila: Mapping[str, Any]) -> str:
    partes = [str(fila.get("first_name", "") or ""), str(fila.get("last_name", "") or "")]
    return " ".join(parte for parte in partes if parte)
