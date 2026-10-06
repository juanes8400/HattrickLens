"""El paso semanal del mercado, de principio a fin.

Esto es lo que se llama desde una sincronización. Hace dos cosas, y la primera
corre SIEMPRE mientras la segunda sólo cuando toca:

1. **Resolver.** A las ventas que entraron con una puja y cuya subasta ya cerró
   se les pregunta cuánto se pagó de verdad. Corre en todas las
   sincronizaciones, le toque el turno a quien le toque: una subasta anotada
   hoy cierra en días, y esperar cinco semanas al siguiente turno de su jugador
   dejaría el número provisional todo ese tiempo.

2. **Buscar.** Si esta sincronización es la primera posterior al disparador
   (la actualización económica de la liga menos 24 horas), se recorre la
   escalera para los jugadores cuyo identificador cae en el turno de la
   semana, una quinta parte de la plantilla.

EL GASTO. Buscar cuesta cinco peticiones por jugador como mucho, y resolver una
por venta pendiente. Con una quinta parte de una plantilla de veinticinco son
unas veinticinco peticiones de búsqueda por semana, menos de una
sincronización. Un jugador que ya tiene sus seis comparables vivos no gasta ni
una.
"""

from __future__ import annotations

from collections.abc import Awaitable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.commands.mercado_comparable import (
    Resolucion,
    aplicar_resolucion,
    del_turno,
    fondo_del_equipo,
    guardar,
    pendientes_de_resolver,
    toca_el_paso,
)
from app.application.queries.mercado_comparable import correr_el_turno
from app.domain.engines.mercado_comparable import objetivo_de
from app.infrastructure.db import models as m

#: Las habilidades que hay que leer del jugador propio. Las ocho, aunque sólo
#: seis cuenten: `terna` se encarga de descartar resistencia y balón parado, y
#: pedirlas todas evita que este módulo tenga que saber cuáles son.
HABILIDADES = (
    "keeper",
    "defending",
    "playmaking",
    "winger",
    "passing",
    "scoring",
    "set_pieces",
    "stamina",
)


class Historiales(Protocol):
    """Quien sabe traer el historial de traspasos de un jugador.

    Entra como puerto y no como cliente concreto: la capa de aplicacion no
    tiene por que saber que al otro lado hay CHPP, y asi el paso se puede
    probar sin red.
    """

    def __call__(self, ht_player_id: int) -> Awaitable[Mapping[str, Any]]: ...


@dataclass(frozen=True, slots=True)
class PasoSemanal:
    """Lo que hizo el paso, para poder contarlo en el registro."""

    resueltas: tuple[Resolucion, ...]
    jugadores_del_turno: tuple[int, ...]
    ventas_nuevas: int
    busquedas: int
    #: Falso cuando no tocaba y sólo se resolvió lo pendiente.
    se_busco: bool


async def correr_el_paso_semanal(
    session: AsyncSession,
    equipo: m.Team,
    *,
    buscar: Any,
    historial_de: Historiales,
    ahora: datetime,
) -> PasoSemanal:
    """Resuelve lo pendiente y, si toca, busca para los jugadores del turno."""
    resueltas = await _resolver(session, equipo, historial_de, ahora)

    economica = await _fecha_economica(session, equipo)
    if not toca_el_paso(equipo, economica, ahora):
        return PasoSemanal(
            resueltas=resueltas,
            jugadores_del_turno=(),
            ventas_nuevas=0,
            busquedas=0,
            se_busco=False,
        )

    plantilla = await _plantilla(session, equipo.id)
    turno = del_turno([p.ht_player_id for p in plantilla], economica, ahora)
    nuevas = 0
    busquedas = 0
    for jugador in plantilla:
        if jugador.ht_player_id not in turno:
            continue
        objetivo = objetivo_de(
            jugador.ht_player_id,
            jugador.edad,
            jugador.habilidades,
            especialidad=jugador.especialidad,
        )
        if objetivo is None:
            continue
        fondo = await fondo_del_equipo(session, equipo.id)
        resultado = await correr_el_turno(
            objetivo,
            buscar,
            fondo=fondo,
            mi_equipo=equipo.ht_team_id,
            ahora=ahora,
        )
        busquedas += resultado.busquedas
        plazos = {p.ht_player_id: p.plazo for p in resultado.por_resolver}
        nuevas += await guardar(session, equipo.id, resultado.nuevas, plazos)
        await session.flush()

    equipo.market_run_at = ahora
    return PasoSemanal(
        resueltas=resueltas,
        jugadores_del_turno=tuple(turno),
        ventas_nuevas=nuevas,
        busquedas=busquedas,
        se_busco=True,
    )


async def _resolver(
    session: AsyncSession, equipo: m.Team, historial_de: Historiales, ahora: datetime
) -> tuple[Resolucion, ...]:
    """Le pregunta al historial de cada pendiente cuánto se pagó.

    Un fallo al resolver NO tumba el paso: la venta se queda con su puja y se
    reintenta a la siguiente. Perder un precio real es una lástima; perder la
    búsqueda entera por ello sería peor.
    """
    hechas: list[Resolucion] = []
    for fila in await pendientes_de_resolver(session, equipo.id, ahora):
        try:
            historial = await historial_de(fila.ht_player_id)
        except Exception:  # noqa: BLE001
            fila.resolve_attempts += 1
            continue
        hechas.append(aplicar_resolucion(fila, historial))
    if hechas:
        await session.flush()
    return tuple(hechas)


@dataclass(frozen=True, slots=True)
class _Jugador:
    ht_player_id: int
    edad: int
    especialidad: int
    habilidades: dict[str, int]


async def _plantilla(session: AsyncSession, team_id: int) -> list[_Jugador]:
    """La plantilla de hoy, con la foto más reciente de cada jugador."""
    jugadores = (
        await session.execute(select(m.Player).where(m.Player.team_id == team_id))
    ).scalars()
    salida: list[_Jugador] = []
    for jugador in jugadores:
        foto = (
            await session.execute(
                select(m.PlayerSnapshot)
                .where(m.PlayerSnapshot.player_id == jugador.id)
                .order_by(m.PlayerSnapshot.captured_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if foto is None:
            continue
        salida.append(
            _Jugador(
                ht_player_id=jugador.ht_player_id,
                edad=foto.age_years or 0,
                especialidad=foto.specialty or 0,
                habilidades={h: getattr(foto, h, 0) or 0 for h in HABILIDADES},
            )
        )
    return salida


async def _fecha_economica(session: AsyncSession, equipo: m.Team) -> datetime | None:
    """La actualización económica de SU liga. Hattrick la publica por país, y
    de ahí sale el disparador sin inventar zonas horarias."""
    if equipo.ht_league_id is None:
        return None
    contexto = (
        await session.execute(
            select(m.WorldContext).where(m.WorldContext.ht_league_id == equipo.ht_league_id)
        )
    ).scalar_one_or_none()
    return contexto.economy_date if contexto is not None else None
