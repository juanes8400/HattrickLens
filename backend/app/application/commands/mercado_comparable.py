"""El paso semanal del mercado: buscar, guardar y resolver.

Aquí se junta todo lo demás con la base de datos. Tres piezas, y la tercera es
la que de verdad hace que esto funcione:

1. **¿Toca?** El disparador es la actualización económica de la liga menos 24
   horas, que Hattrick publica por país. Se corre en la primera sincronización
   posterior a ese instante, y sólo para los jugadores cuyo identificador
   caiga en el turno de la semana.
2. **Buscar.** Por cada jugador del turno se recorre la escalera, y lo que se
   encuentra se guarda en el fondo DEL EQUIPO, con el perfil del vendido, para
   que sirva también a sus compañeros.
3. **Resolver.** Lo guardado entra con la puja de precio. Cuando la subasta
   cierra se le pregunta al historial del jugador cuánto se pagó de verdad, y
   ese precio sustituye a la puja. Esto no es cosmético: el 2026-10-05 Valerio
   Cataldi tenía 65.000.000 de puja y cerró en 77.720.000, un 16% más. La puja
   se queda corta, y siempre por el mismo lado.

La resolución corre en TODAS las sincronizaciones, le toque el turno a quien le
toque: una subasta anotada hoy cierra en días, y esperar cinco semanas al
siguiente turno de su jugador dejaría el número provisional todo ese tiempo.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.engines.mercado_comparable import (
    GRUPOS,
    REINTENTOS_DE_RESOLUCION,
    Estimacion,
    Guardado,
    Rasgo,
    Traspaso,
    frontera_semanal,
    le_toca,
    le_toca_el_exacto,
    precio_cerrado,
    se_puede_resolver,
    semana_de,
)
from app.domain.value_objects.ht_time import ht_to_utc
from app.infrastructure.db import models as m

#: Desde dónde se cuentan las semanas para rotar los turnos. Cualquier fecha
#: fija sirve: lo único que importa es que no cambie, porque cambiarla
#: reordenaría a quién le toca cuándo.
ANCLA = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class Resolucion:
    """Lo que pasó al preguntar por una venta pendiente."""

    ht_player_id: int
    precio: int | None
    #: Si se agotaron los reintentos y se deja con su puja.
    abandonada: bool
    #: El traspaso de Hattrick con el que se resolvió, cuando se resolvió.
    ht_transfer_id: int = 0


def toca_el_paso(equipo: m.Team, ahora: datetime) -> bool:
    """Si esta sincronización es la primera DEL DÍA.

    Era «la primera posterior al disparador semanal» hasta el 2026-10-09.
    Cambió porque los dos ritmos que decidió el usuario ya no son el mismo: el
    escalón exacto de cada jugador toca cada SEIS DÍAS y los anchos cada cinco
    semanas, así que el paso tiene que mirarse a diario para que el reloj de
    los seis días pueda caer en cualquier día. Quién busca y qué busca lo
    deciden `del_turno_exacto` y `del_turno`, no esta puerta.

    Una vez al día y no en cada sincronización: dos sincronizaciones seguidas
    no pueden gastar dos veces las mismas búsquedas. `market_run_at` sigue
    siendo el sello, ahora comparado por día y no contra la frontera semanal,
    así que no hay nada nuevo que guardar.

    LA FECHA ECONOMICA YA NO ENTRA AQUI. Era el disparador --la actualización
    de la liga menos 24 horas-- y se quedó sin papel al pasar la puerta a
    diaria; la frontera semanal sigue viva, pero sólo donde hace falta: en
    `del_turno`, que reparte los turnos anchos. Llevarla también aquí era un
    parámetro que no decidía nada.
    """
    if equipo.market_run_at is None:
        return True
    sello = equipo.market_run_at
    if sello.tzinfo is None:
        sello = sello.replace(tzinfo=UTC)
    return sello.astimezone(UTC).date() < ahora.astimezone(UTC).date()


def del_turno(
    ht_player_ids: Sequence[int], economy_date: datetime | None, ahora: datetime
) -> list[int]:
    """Los jugadores a los que les toca esta semana.

    El grupo sale del propio identificador, así que no hay nada que guardar ni
    que recolocar al fichar o vender, y el 0 rota a 1, 2, 3 y 4 cada semana.
    """
    frontera = frontera_semanal(economy_date, ahora)
    if frontera is None:
        return []
    return [p for p in ht_player_ids if le_toca(p, frontera, ANCLA)]


def del_turno_exacto(ht_player_ids: Sequence[int], ahora: datetime) -> list[int]:
    """Los jugadores a los que les toca HOY su escalón exacto.

    Uno de cada seis días por jugador, sacado del identificador: nada que
    guardar. Con veinticinco jugadores salen unos cuatro al día.
    """
    return [p for p in ht_player_ids if le_toca_el_exacto(p, ahora, ANCLA)]


def numero_de_turno(economy_date: datetime | None, ahora: datetime) -> int | None:
    """Qué grupo de los cinco corre esta semana. Para poder enseñarlo."""
    frontera = frontera_semanal(economy_date, ahora)
    if frontera is None:
        return None
    return semana_de(frontera, ANCLA) % GRUPOS


# --------------------------------------------------------------------------
# El fondo, de la base a memoria y vuelta
# --------------------------------------------------------------------------


def a_guardado(fila: m.MarketSale) -> Guardado:
    """Una fila de la base como la ve el motor."""
    return Guardado(
        ht_player_id=fila.ht_player_id,
        nombre=fila.name,
        precio=fila.price,
        firme=fila.is_final,
        puja=fila.bid_price,
        visto_el=fila.seen_at,
        edad=fila.age_years,
        primaria=Rasgo(fila.primary_skill, fila.primary_level),
        secundaria=Rasgo(fila.secondary_skill, fila.secondary_level),
        terciaria=Rasgo(fila.tertiary_skill, fila.tertiary_level),
        especialidad=fila.specialty,
        tsi=fila.tsi,
        pais=fila.country_id,
        intentos=fila.resolve_attempts,
        ht_transfer_id=fila.ht_transfer_id,
    )


async def fondo_del_equipo(session: AsyncSession, team_id: int) -> list[Guardado]:
    filas = (
        await session.execute(select(m.MarketSale).where(m.MarketSale.team_id == team_id))
    ).scalars()
    return [a_guardado(f) for f in filas]


async def guardar(
    session: AsyncSession,
    team_id: int,
    ventas: Sequence[Guardado],
    plazos: dict[int, str],
) -> int:
    """Mete en el fondo lo que trajo un turno.

    Si el mismo jugador vuelve a aparecer en otra subasta, su fila se
    actualiza con la nueva puja y el nuevo plazo y vuelve a quedar pendiente:
    es otra venta, y la de antes ya cumplió su función.
    """
    nuevas = 0
    for venta in ventas:
        fila = (
            await session.execute(
                select(m.MarketSale).where(
                    m.MarketSale.team_id == team_id,
                    m.MarketSale.ht_player_id == venta.ht_player_id,
                )
            )
        ).scalar_one_or_none()
        plazo = ht_to_utc(plazos.get(venta.ht_player_id, ""))
        if fila is None:
            fila = m.MarketSale(team_id=team_id, ht_player_id=venta.ht_player_id)
            session.add(fila)
            nuevas += 1
        fila.name = venta.nombre
        fila.price = venta.precio
        fila.is_final = venta.firme
        fila.bid_price = venta.puja
        fila.deadline = plazo
        fila.seen_at = venta.visto_el
        fila.resolve_attempts = 0
        fila.age_years = venta.edad
        fila.primary_skill = venta.primaria.habilidad
        fila.primary_level = venta.primaria.nivel
        fila.secondary_skill = venta.secundaria.habilidad
        fila.secondary_level = venta.secundaria.nivel
        fila.tertiary_skill = venta.terciaria.habilidad
        fila.tertiary_level = venta.terciaria.nivel
        fila.specialty = venta.especialidad
        fila.tsi = venta.tsi
        fila.country_id = venta.pais
    return nuevas


# --------------------------------------------------------------------------
# De la puja al precio de verdad
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# La serie: como ha ido cambiando el numero
# --------------------------------------------------------------------------


def _retrato(estimacion: Estimacion) -> str:
    """Los precios que formaron esta lectura, en JSON.

    Van los que OCUPAN PLAZA, no solo los que cuentan (2026-10-09). Desde que
    el numero sale unicamente de ventas cerradas, guardar solo lo que cuenta
    dejaba la nube VACIA en cuanto un jugador no tenia ninguna cerrada --el
    caso de 23 de los 26 jugadores del club ese dia-- y la grafica del tiempo
    se quedaba sin nada que dibujar en esas lecturas.

    Cada uno con su estado: la grafica enseña las cerradas, y si una lectura
    no tiene ninguna enseña sus pujas, que es mejor que una columna vacia.

    Y con su PESO, el «se parece» (2026-10-09, pedido del usuario): la
    grafica pinta mas pequeño y mas suave lo que se parece menos, para que no
    pese lo mismo en el ojo un gemelo que un primo lejano. Las lecturas
    anteriores a hoy no lo llevan y se dibujan al 100 %, que es lo que se
    suponia hasta ahora.
    """
    return json.dumps(
        [
            {"precio": c.venta.precio, "firme": c.venta.firme, "peso": c.peso}
            for c in estimacion.comparables
            if c.ocupa
        ],
        separators=(",", ":"),
    )


async def anotar_si_cambio(
    session: AsyncSession,
    team_id: int,
    ht_player_id: int,
    estimacion: Estimacion,
    ahora: datetime,
) -> bool:
    """Guarda una lectura, y solo si dice algo distinto de la anterior.

    UN PUNTO POR CAMBIO Y NO POR FECHA. Si se anotara en cada sincronizacion
    la serie seria una linea plana con cientos de puntos iguales, y el
    tiempo entre dos puntos dejaria de significar nada. Anotando solo los
    cambios, los tramos planos de la grafica cuentan que no paso nada, que
    es informacion.

    Devuelve si se anoto.
    """
    ultima = (
        await session.execute(
            select(m.MarketEstimate)
            .where(
                m.MarketEstimate.team_id == team_id,
                m.MarketEstimate.ht_player_id == ht_player_id,
            )
            .order_by(m.MarketEstimate.captured_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    retrato = _retrato(estimacion)
    if (
        ultima is not None
        and ultima.mean_price == estimacion.media
        and ultima.median_price == estimacion.mediana
        and ultima.n == estimacion.n
        and ultima.prices_json == retrato
    ):
        return False

    session.add(
        m.MarketEstimate(
            team_id=team_id,
            ht_player_id=ht_player_id,
            captured_at=ahora,
            mean_price=estimacion.media,
            median_price=estimacion.mediana,
            n=estimacion.n,
            min_weight=estimacion.peso_minimo,
            provisional=estimacion.provisionales,
            prices_json=retrato,
        )
    )
    return True


async def pendientes_de_resolver(
    session: AsyncSession, team_id: int, ahora: datetime
) -> list[m.MarketSale]:
    """Las ventas cuya subasta ya cerró, siguen con la puja, y hoy no se han
    preguntado todavía.

    DOS CONDICIONES, las dos del usuario (2026-10-09):

    · **Posterior a la hora de cierre.** La pone `se_puede_resolver`, y es más
      vieja que esta función: nunca se ha preguntado por una subasta abierta.
    · **Un intento al día por venta.** Esta es nueva, y hace falta desde que no
      hay margen tras el plazo. La resolución corre en cada sincronización, y
      la aplicación permite seis por hora: sin el freno, las cinco
      oportunidades de una venta se gastaban en la primera hora tras el cierre
      y se abandonaba antes de que Hattrick publicara el traspaso.

    El día se compara en UTC, que es el huso en el que viven todos los sellos.
    """
    filas = (
        await session.execute(
            select(m.MarketSale).where(
                m.MarketSale.team_id == team_id,
                m.MarketSale.is_final.is_(False),
                m.MarketSale.resolve_attempts <= REINTENTOS_DE_RESOLUCION,
            )
        )
    ).scalars()
    hoy = ahora.astimezone(UTC).date()
    return [f for f in filas if se_puede_resolver(f.deadline, ahora) and _preguntado_el(f) != hoy]


def _preguntado_el(fila: m.MarketSale) -> date | None:
    """El día en que se preguntó por última vez, o `None` si nunca."""
    sello = fila.resolve_asked_at
    if sello is None:
        return None
    if sello.tzinfo is None:
        sello = sello.replace(tzinfo=UTC)
    return sello.astimezone(UTC).date()


def aplicar_resolucion(
    fila: m.MarketSale, historial: Mapping[str, Any], ahora: datetime | None = None
) -> Resolucion:
    """Cambia la puja por el precio real, si el historial lo trae.

    Cuando no lo trae se anota el intento. Con una puja encima la venta está
    garantizada, así que no encontrarla casi siempre es que Hattrick aún no la
    había registrado, y se arregla esperando a la siguiente sincronización. Si
    tampoco entonces, se deja con su puja y se deja de preguntar: insistir
    sería gastar llamadas en balde.

    `ahora` sella la pregunta para que no se repita hoy. Se sella SIEMPRE que
    se llegó a preguntar, se encontrara o no: lo que el sello mide es que la
    llamada se gastó. Una llamada que ni salió --CHPP caído-- no llega aquí.
    """
    if ahora is not None:
        fila.resolve_asked_at = ahora
    traspasos = [
        Traspaso(
            ht_transfer_id=int(t.get("ht_transfer_id", 0) or 0),
            cierre=cierre,
            precio=int(t.get("price", 0) or 0),
        )
        for t in historial.get("transfers", [])
        if (cierre := ht_to_utc(str(t.get("deadline", "") or ""))) is not None
    ]
    cerrado = precio_cerrado(traspasos, fila.deadline) if fila.deadline is not None else None
    if cerrado is not None:
        fila.price = cerrado.precio
        fila.is_final = True
        # Desde aquí la venta tiene identidad propia de Hattrick, y no una
        # marca de tiempo con tolerancia de cinco minutos.
        fila.ht_transfer_id = cerrado.ht_transfer_id
        return Resolucion(
            ht_player_id=fila.ht_player_id,
            precio=cerrado.precio,
            abandonada=False,
            ht_transfer_id=cerrado.ht_transfer_id,
        )
    fila.resolve_attempts += 1
    return Resolucion(
        ht_player_id=fila.ht_player_id,
        precio=None,
        abandonada=fila.resolve_attempts > REINTENTOS_DE_RESOLUCION,
    )
