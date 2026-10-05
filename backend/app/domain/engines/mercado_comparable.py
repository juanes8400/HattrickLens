"""Qué pagaría hoy el mercado por un jugador tuyo, mirando a los que se le parecen.

Diseñado con el usuario, y rediseñado por él el 2026-10-05 después de probarlo
contra el mercado de verdad. La regla es suya de principio a fin, y eso importa
por `AGENTS.md`: aquí no se ajusta ningún parámetro contra la plantilla propia.
Lo que hay es una media ponderada de datos ajenos con unos pesos que él fijó.

LA IDEA. Dos jugadores son comparables si coinciden en edad y en sus dos
habilidades más altas, y si no coinciden del todo, en lo poco que se apartan.
Pero se apartan DE UNA EN UNA: cada escalón es el jugador con UNA sola cosa
movida y las otras dos clavadas.

    escalón  primaria  secundaria   edad   peso
      0          =          =         =    100%
      1          =         -1         =     95%
      2         -1          =         =     90%
      3          =          =        +1     85%
      4          =          =        -1     80%
      5          =         -2         =     75%    (y vuelta a empezar, un
      6         -2          =         =     70%     nivel más hondo cada
      7          =          =        +2     65%     vuelta, hasta el suelo)
      ...

Lo que se gana, y es la razón de haberlo rediseñado: con ventanas que se
ensanchan, un comparable del 45% podía diferir en edad, en primaria y en
secundaria a la vez, y «45%» no decía en cuál. Aquí cada comparable difiere en
EXACTAMENTE UNA COSA y en una cantidad conocida, así que el peso significa algo
que se puede decir en voz alta.

LO QUE CUESTA, y conviene tenerlo presente al leer un precio:

· **Hay huecos.** Un jugador con la secundaria un nivel más baja Y un año más
  no aparece en ningún escalón, ni en la primera vuelta ni en la última: el
  escalón de la secundaria le pide la edad exacta y el de la edad le pide la
  secundaria exacta. Es el precio de la pureza, y es deliberado.
· **Las habilidades sólo se mueven hacia abajo.** La edad va en los dos
  sentidos desde la primera vuelta, pero la primaria y la secundaria sólo
  bajan, así que los comparables son algo más flojos que el jugador y el
  precio sale, por construcción, por el lado prudente.

LA TERCIARIA NO ESTÁ. El diseño anterior comparaba tres habilidades; éste
compara dos. Se sigue calculando la tercera de cada jugador porque se enseña,
para que se vea a quién se está comparando, pero no entra en el parecido.

LAS 24 HORAS, y por qué existen. Pedido por el usuario el 2026-10-05, y es la
regla que salva el número. Una puja sólo cuenta si a la subasta le quedan menos
de veinticuatro horas. Probando contra el mercado real aparecieron pujas de
50.000 al lado de pujas de 18.000.000 para jugadores casi idénticos, y la
diferencia no era el jugador: eran subastas sin precio mínimo recién abiertas,
donde la puja va por donde va la escalada y no por lo que vale nadie. Promediar
eso con una subasta a punto de cerrar no da un precio, da un revoltijo. Cuanto
más cerca del cierre, más se parece la puja a lo que de verdad se va a pagar.

LO QUE LA PANTALLA ESTÁ OBLIGADA A DECIR. La puja más alta es una puja EN
CURSO, no una venta cerrada: aunque queden horas, el precio todavía puede
subir. El número que sale de aquí es «lo que se está pujando hoy por los que se
le parecen». En el fichero del mercado no hay ni una venta cerrada.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, tzinfo
from typing import Any

from app.domain.value_objects.ht_time import HATTRICK_TZ, ht_to_utc

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

#: Lo que baja el peso de un escalón al siguiente.
ESCALON_DE_PESO = 5

#: Nadie juega en el primer equipo con menos de 17 años.
EDAD_MINIMA = 17

#: Cuánto le puede faltar a una subasta para que su puja cuente.
HORAS_PARA_QUE_CUENTE = 24


@dataclass(frozen=True, slots=True)
class Rasgo:
    """Una habilidad con su nivel."""

    habilidad: str
    nivel: int


@dataclass(frozen=True, slots=True)
class Desvio:
    """Cuánto se aparta un comparable del jugador, y lo que vale apartarse así.

    Los tres números son desplazamientos EXACTOS respecto al jugador, no
    radios de una ventana: `secundaria=-1` significa «uno por debajo», ni cero
    ni dos.
    """

    primaria: int
    secundaria: int
    edad: int
    peso: int


def _escalera() -> tuple[Desvio, ...]:
    """La escalera que dictó el usuario, construida con su propia regla.

    Primero el exacto, y luego vueltas de cuatro: la secundaria un nivel más
    abajo, la primaria un nivel más abajo, un año más, un año menos. Cada
    vuelta repite esas cuatro un nivel más hondo, y cada escalón vale cinco
    puntos menos que el anterior hasta el suelo.

    Con el suelo en 30 la escalera termina a mitad de la cuarta vuelta:
    entran la secundaria -4 y la primaria -4, y los años ya no. Completar esa
    vuelta llevaría el suelo al 20%.
    """
    escalones = [Desvio(primaria=0, secundaria=0, edad=0, peso=100)]
    peso = 100
    profundidad = 0
    while True:
        profundidad += 1
        vuelta = (
            (0, -profundidad, 0),
            (-profundidad, 0, 0),
            (0, 0, profundidad),
            (0, 0, -profundidad),
        )
        for primaria, secundaria, edad in vuelta:
            peso -= ESCALON_DE_PESO
            if peso < SUELO_DE_PESO:
                return tuple(escalones)
            escalones.append(Desvio(primaria=primaria, secundaria=secundaria, edad=edad, peso=peso))


ESCALERA: tuple[Desvio, ...] = _escalera()

#: El peso de cada desvío, para encontrarlo sin recorrer la escalera. Como
#: cada escalón clava los tres ejes, un jugador encaja como mucho en uno.
_PESO_DE: dict[tuple[int, int, int], int] = {
    (d.primaria, d.secundaria, d.edad): d.peso for d in ESCALERA
}


@dataclass(frozen=True, slots=True)
class Objetivo:
    """El jugador tuyo al que se le busca precio."""

    ht_player_id: int
    edad: int
    primaria: Rasgo
    secundaria: Rasgo


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
    #: No entra en el parecido; se enseña, para que se vea a quién se compara.
    terciaria: Rasgo


@dataclass(frozen=True, slots=True)
class Comparable:
    """Un candidato aceptado, con el peso que se ganó."""

    candidato: Candidato
    peso: int


@dataclass(frozen=True, slots=True)
class Franja:
    """El nivel que se le pide a una habilidad.

    Viaja con mínimo y máximo porque así lo pide la búsqueda del juego, pero
    en este diseño los dos valen lo mismo: se piden niveles exactos.
    """

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

    Las dos primeras deciden el parecido; la tercera se devuelve porque se
    enseña. Es `None` cuando no hay con qué comparar, es decir cuando las seis
    están a cero: eso no es un jugador flojo, es un hueco en los datos.

    La resistencia y el balón parado no se miran, y el empate lo rompe
    `ORDEN_DE_DESEMPATE`, así que el mismo jugador da siempre la misma terna.
    """
    rasgos = [Rasgo(nombre, max(0, int(skills.get(nombre, 0)))) for nombre in ORDEN_DE_DESEMPATE]
    ordenados = sorted(rasgos, key=lambda rasgo: (-rasgo.nivel, _RANGO[rasgo.habilidad]))
    if ordenados[0].nivel <= 0:
        return None
    return ordenados[0], ordenados[1], ordenados[2]


def objetivo_de(ht_player_id: int, edad: int, skills: Mapping[str, int]) -> Objetivo | None:
    """El objetivo a partir de un jugador propio.

    `None` cuando no se le pueden sacar sus dos habilidades o no se sabe su
    edad: sin eso no hay con qué buscar, y buscar «lo que sea» devolvería un
    precio que no es de nadie.
    """
    tres = terna(skills)
    if tres is None or edad <= 0:
        return None
    primaria, secundaria, _ = tres
    return Objetivo(
        ht_player_id=ht_player_id,
        edad=edad,
        primaria=primaria,
        secundaria=secundaria,
    )


def ventana_de(objetivo: Objetivo, desvio: Desvio) -> Ventana | None:
    """La búsqueda de un escalón, o `None` si ese escalón no existe.

    Un escalón deja de existir cuando lo que pediría se sale del mundo: un
    jugador de 17 años no tiene escalón de «un año menos», y una habilidad de
    nivel 2 no tiene uno de «cuatro niveles por debajo». No se recorta al
    valor válido más cercano, porque entonces se buscaría un desvío distinto
    del que se dijo y se gastaría una llamada en repetir un escalón ya hecho.
    """
    edad = objetivo.edad + desvio.edad
    primaria = objetivo.primaria.nivel + desvio.primaria
    secundaria = objetivo.secundaria.nivel + desvio.secundaria
    if edad < EDAD_MINIMA or primaria < 0 or secundaria < 0:
        return None
    return Ventana(
        peso=desvio.peso,
        edad_minima=edad,
        edad_maxima=edad,
        primaria=Franja(objetivo.primaria.habilidad, primaria, primaria),
        secundaria=Franja(objetivo.secundaria.habilidad, secundaria, secundaria),
    )


def plan_de_busqueda(objetivo: Objetivo) -> tuple[Ventana, ...]:
    """Las búsquedas a recorrer, del parecido más estrecho al más flojo.

    Quien las recorra para en cuanto `estimar` diga que ya hay suficientes, y
    no antes de terminar un escalón: si el sexto y el séptimo se parecen
    igual, dejar fuera al séptimo por orden de llegada sería arbitrario.
    """
    ventanas = (ventana_de(objetivo, desvio) for desvio in ESCALERA)
    return tuple(v for v in ventanas if v is not None)


def peso_de(candidato: Candidato, objetivo: Objetivo) -> int | None:
    """Lo que vale este candidato, o `None` si no se le parece lo bastante.

    Se mira en qué se aparta y se busca ese desvío en la escalera. Como cada
    escalón clava los tres ejes, un candidato encaja como mucho en uno, así
    que no hay que elegir entre pesos ni importa en qué búsqueda apareciera.
    """
    if (
        candidato.primaria.habilidad != objetivo.primaria.habilidad
        or candidato.secundaria.habilidad != objetivo.secundaria.habilidad
    ):
        return None
    return _PESO_DE.get(
        (
            candidato.primaria.nivel - objetivo.primaria.nivel,
            candidato.secundaria.nivel - objetivo.secundaria.nivel,
            candidato.edad - objetivo.edad,
        )
    )


def cierra_pronto(candidato: Candidato, ahora: datetime) -> bool:
    """Si a su subasta le queda poco, que es cuando su puja significa algo.

    Un plazo YA VENCIDO cuenta: el fichero avisa de que puede venir unas horas
    pasado, y esa puja es lo más parecido a una venta que hay aquí, la última
    que alguien hizo de verdad.

    Un plazo que no se entiende NO cuenta. Sin saber cuándo cierra no se puede
    saber si la puja significa algo, y en la duda se deja fuera: colar una
    subasta recién abierta hunde la media, y dejar fuera a uno bueno sólo
    cuesta seguir buscando.
    """
    cierre = ht_to_utc(candidato.plazo)
    if cierre is None:
        return False
    return cierre - ahora.astimezone(UTC) < timedelta(hours=HORAS_PARA_QUE_CUENTE)


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
    *,
    ahora: datetime | None = None,
) -> dict[int, Comparable]:
    """Añade a lo ya reunido los comparables que haya en estas filas.

    Quedan fuera, y cada exclusión tiene su motivo:

    · el propio jugador, si resulta que está en el mercado, porque compararlo
      consigo mismo devolvería su propia puja como precio de mercado;
    · el que no tiene puja, porque su precio pedido es una opinión del
      vendedor y no un dato del mercado;
    · aquel a cuya subasta le quedan más de `HORAS_PARA_QUE_CUENTE` horas,
      porque su puja habla de por dónde va la escalada y no de lo que vale;
    · el lesionado de verdad, lesión mayor que 0, porque su precio está tocado
      por la lesión y no por lo que vale. El magullado (0) y el sano (-1) sí
      entran;
    · el que no se aparta de una de las maneras que la escalera admite.

    `ahora` se puede fijar desde fuera; sin él es la hora de verdad.

    El que ya estaba se queda con el mejor peso de los dos, así que el orden
    en que lleguen las búsquedas no cambia el resultado.
    """
    momento = ahora or datetime.now(UTC)
    reunidos: dict[int, Comparable] = dict(acumulado) if acumulado else {}
    for fila in filas:
        candidato = candidato_de(fila)
        if candidato is None:
            continue
        if candidato.ht_player_id == objetivo.ht_player_id:
            continue
        if not candidato.tiene_puja or candidato.puja <= 0:
            continue
        if not cierra_pronto(candidato, momento):
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


def _nombre(fila: Mapping[str, Any]) -> str:
    partes = [str(fila.get("first_name", "") or ""), str(fila.get("last_name", "") or "")]
    return " ".join(parte for parte in partes if parte)
