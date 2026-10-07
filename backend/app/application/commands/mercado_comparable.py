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

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.engines.mercado_comparable import (
    GRUPOS,
    REINTENTOS_DE_RESOLUCION,
    Guardado,
    Rasgo,
    frontera_semanal,
    le_toca,
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


def toca_el_paso(equipo: m.Team, economy_date: datetime | None, ahora: datetime) -> bool:
    """Si esta sincronización es la primera posterior al disparador."""
    frontera = frontera_semanal(economy_date, ahora)
    if frontera is None:
        return False
    if equipo.market_run_at is None:
        return True
    sello = equipo.market_run_at
    if sello.tzinfo is None:
        sello = sello.replace(tzinfo=UTC)
    return sello < frontera


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


async def pendientes_de_resolver(
    session: AsyncSession, team_id: int, ahora: datetime
) -> list[m.MarketSale]:
    """Las ventas cuya subasta ya cerró y siguen con la puja de precio."""
    filas = (
        await session.execute(
            select(m.MarketSale).where(
                m.MarketSale.team_id == team_id,
                m.MarketSale.is_final.is_(False),
                m.MarketSale.resolve_attempts <= REINTENTOS_DE_RESOLUCION,
            )
        )
    ).scalars()
    return [f for f in filas if se_puede_resolver(f.deadline, ahora)]


def aplicar_resolucion(fila: m.MarketSale, historial: Mapping[str, Any]) -> Resolucion:
    """Cambia la puja por el precio real, si el historial lo trae.

    Cuando no lo trae se anota el intento. Con una puja encima la venta está
    garantizada, así que no encontrarla casi siempre es que Hattrick aún no la
    había registrado, y se arregla esperando a la siguiente sincronización. Si
    tampoco entonces, se deja con su puja y se deja de preguntar: insistir
    sería gastar llamadas en balde.
    """
    traspasos = [
        (cierre, int(t.get("price", 0) or 0))
        for t in historial.get("transfers", [])
        if (cierre := ht_to_utc(str(t.get("deadline", "") or ""))) is not None
    ]
    precio = precio_cerrado(traspasos, fila.deadline) if fila.deadline is not None else None
    if precio is not None:
        fila.price = precio
        fila.is_final = True
        return Resolucion(ht_player_id=fila.ht_player_id, precio=precio, abandonada=False)
    fila.resolve_attempts += 1
    return Resolucion(
        ht_player_id=fila.ht_player_id,
        precio=None,
        abandonada=fila.resolve_attempts > REINTENTOS_DE_RESOLUCION,
    )
