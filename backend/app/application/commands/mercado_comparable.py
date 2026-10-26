"""El paso del mercado: buscar, guardar y resolver.

Aquí se junta todo lo demás con la base de datos. Tres piezas, y la tercera es
la que de verdad hace que esto funcione:

1. **¿Toca?** A cada jugador le toca UNA VEZ POR DÍA NATURAL, independiente de
   cuántas veces se sincronice (2026-10-26). Antes el disparador era la
   actualización económica de la liga menos 24 horas y sólo buscaba para los
   jugadores cuyo identificador cayera en el turno de la semana.
2. **Buscar.** Por cada jugador que toque se hace UNA búsqueda --la de los
   criterios de Hattrick-- y lo que se encuentra se guarda en el fondo DEL
   EQUIPO, con el perfil del vendido, para que sirva también a sus compañeros.
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
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.engines.mercado_comparable import (
    REINTENTOS_DE_RESOLUCION,
    Estimacion,
    Guardado,
    Rasgo,
    Traspaso,
    le_toca_hoy,
    precio_cerrado,
    se_puede_resolver,
)
from app.domain.value_objects.ht_time import ht_to_utc
from app.infrastructure.db import models as m


class _ConSello(Protocol):
    """Lo mínimo para saber si a alguien le toca: su id y su último barrido.

    Entra como protocolo y no como el modelo entero para que la regla se pueda
    probar sin base de datos, que es donde vive el único borde que importa
    --el corte del día-- y no hace falta una tabla para comprobarlo.
    """

    @property
    def ht_player_id(self) -> int: ...

    @property
    def market_swept_at(self) -> datetime | None: ...


@dataclass(frozen=True, slots=True)
class Resolucion:
    """Lo que pasó al preguntar por una venta pendiente."""

    ht_player_id: int
    precio: int | None
    #: Si se agotaron los reintentos y se deja con su puja.
    abandonada: bool
    #: El traspaso de Hattrick con el que se resolvió, cuando se resolvió.
    ht_transfer_id: int = 0


def a_quien_le_toca_hoy(jugadores: Sequence[_ConSello], ahora: datetime) -> list[int]:
    """Los jugadores a los que todavía no se les ha barrido el mercado hoy.

    Una vez por día natural y por jugador (2026-10-26). Normalmente son todos,
    porque es lo que quiere decir «todos los días»; son menos cuando una
    sincronización anterior del mismo día ya pasó por ellos, y son ninguno
    cuando ya se hizo el barrido de hoy entero.

    LO QUE SE FUE CON ESTO. `toca_el_paso` --una puerta por equipo-- y
    `del_turno` / `del_turno_exacto` / `numero_de_turno` --el reparto por
    identificador--. La puerta por equipo tenía sentido mientras todos los del
    turno buscaban a la vez; ahora el sello es por jugador, que es más fino y
    además resiste que un barrido se corte a la mitad: los que ya se miraron se
    quedan mirados, y a los que no les toca en la siguiente sincronización.
    """
    return [j.ht_player_id for j in jugadores if le_toca_hoy(j.market_swept_at, ahora)]


# --------------------------------------------------------------------------
# El fondo, de la base a memoria y vuelta
# --------------------------------------------------------------------------


def _habilidades(crudo: str | None) -> dict[str, int]:
    """Las siete habilidades de una venta, o vacio si la fila no las lleva.

    Vacio NO es «todas a cero»: es «no las sabemos», y por eso esa venta no
    puede llevar el sello de Hattrick. Si el JSON viniera roto se trata igual
    que si no estuviera, que es lo unico que no miente.
    """
    if not crudo:
        return {}
    try:
        leido = json.loads(crudo)
    except ValueError:
        return {}
    if not isinstance(leido, dict):
        return {}
    return {str(k): int(v) for k, v in leido.items() if isinstance(v, int | float)}


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
        dias=fila.age_days,
        primaria=Rasgo(fila.primary_skill, fila.primary_level),
        secundaria=Rasgo(fila.secondary_skill, fila.secondary_level),
        terciaria=Rasgo(fila.tertiary_skill, fila.tertiary_level),
        habilidades=_habilidades(fila.skills_json),
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

    UNA FILA ES UNA SUBASTA: jugador MÁS plazo (2026-10-26, decisión del
    usuario). Volver a ver el mismo anuncio --cosa de todos los días desde que
    el barrido es diario-- actualiza su fila; una venta NUEVA del mismo jugador
    abre otra, porque es otra venta y Hattrick también las cuenta por separado.

    Hasta hoy la clave era sólo el jugador y la segunda venta pisaba a la
    primera. Ver la migración 0105 para lo que eso costaba.

    SIN PLAZO SE CAE AL JUGADOR SOLO. No debería pasar --el plazo viene en el
    anuncio-- pero si llegara vacío, la restricción de la base no protegería:
    en SQL dos nulos son distintos, así que cada barrido abriría otra fila y en
    una semana habría siete copias del mismo anuncio. Agrupar por el jugador es
    peor clave, pero acotada; duplicar sin freno no lo está.
    """
    nuevas = 0
    for venta in ventas:
        plazo = ht_to_utc(plazos.get(venta.ht_player_id, ""))
        condiciones = [
            m.MarketSale.team_id == team_id,
            m.MarketSale.ht_player_id == venta.ht_player_id,
        ]
        if plazo is not None:
            condiciones.append(m.MarketSale.deadline == plazo)
        fila = (
            await session.execute(select(m.MarketSale).where(*condiciones).limit(1))
        ).scalar_one_or_none()
        nueva = fila is None
        if fila is None:
            fila = m.MarketSale(team_id=team_id, ht_player_id=venta.ht_player_id)
            session.add(fila)
            nuevas += 1
        elif fila.is_final:
            # UN PRECIO DE VERDAD NO SE PISA CON UNA PUJA. Antes no hacía falta
            # mirarlo: la fila se buscaba por jugador y una venta resuelta ya
            # no volvía a verse. Ahora las filas duran, y si el mercado nos
            # devolviera la misma subasta ya cerrada --un fichero rancio, un
            # plazo corrido-- el precio de cierre se cambiaría por la puja, que
            # es justo lo que se resolvió para no tener que usar.
            continue
        fila.name = venta.nombre
        fila.price = venta.precio
        fila.is_final = venta.firme
        fila.bid_price = venta.puja
        fila.deadline = plazo
        fila.seen_at = venta.visto_el
        # LOS INTENTOS SOLO SE REINICIAN EN UNA FILA NUEVA. Antes se ponían a
        # cero en cada guardado, que con una búsqueda semanal daba igual: la
        # fila era nueva casi siempre. Con el barrido diario, volver a ver el
        # mismo anuncio borraría la cuenta de intentos todos los días y una
        # venta que Hattrick nunca publica no se abandonaría jamás.
        if nueva:
            fila.resolve_attempts = 0
        fila.age_years = venta.edad
        fila.age_days = venta.dias
        fila.primary_skill = venta.primaria.habilidad
        fila.primary_level = venta.primaria.nivel
        fila.secondary_skill = venta.secundaria.habilidad
        fila.secondary_level = venta.secundaria.nivel
        fila.tertiary_skill = venta.terciaria.habilidad
        fila.tertiary_level = venta.terciaria.nivel
        fila.specialty = venta.especialidad
        fila.tsi = venta.tsi
        fila.country_id = venta.pais
        if venta.habilidades:
            fila.skills_json = json.dumps(dict(venta.habilidades), sort_keys=True)
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
    criterios: str = "",
) -> bool:
    """Guarda una lectura, y solo si dice algo distinto de la anterior.

    UN PUNTO POR CAMBIO Y NO POR FECHA. Si se anotara en cada sincronizacion
    la serie seria una linea plana con cientos de puntos iguales, y el
    tiempo entre dos puntos dejaria de significar nada. Anotando solo los
    cambios, los tramos planos de la grafica cuentan que no paso nada, que
    es informacion.

    Y UN CAMBIO DE CRITERIOS TAMBIEN ES UN CAMBIO (2026-10-26), aunque el
    numero salga identico. Es el punto que ABRE el tramo nuevo: sin el, un
    jugador que cumple años sin que le cambie la cifra no dejaria rastro de
    que desde ese dia se le esta comparando con otra gente, y el tramo viejo
    se estiraria sobre el nuevo.

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
        and ultima.criteria_key == criterios
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
            criteria_key=criterios,
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
