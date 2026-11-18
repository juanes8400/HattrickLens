"""Quién cambió de clase desde la sincronización anterior (2026-11-18).

Pedido del usuario para Cambios: «Horhoi: Suplencia → Titular». Las clases
se calculan al vuelo, así que para tener un «antes» se guardan: una LECTURA
por sincronización, identificada por la sincronización de la que salen las
fotos de la plantilla (la última `player_snapshots.sync_id` del equipo).

La lectura se escribe la primera vez que se piden los cambios después de
esa sincronización, no dentro de la propia sincronización: así un fallo aquí
nunca puede tumbar un sync. Lo que se compara es esa lectura con la
anterior que haya guardada.

Sólo las tres clasificaciones de la app. Lo que el usuario mueve a mano en
sus clasificaciones propias no es una noticia: ya lo sabe.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.clases_de_jugador import ClasesDeJugadorQueryService
from app.infrastructure.db import models as m

#: Las clasificaciones que se comparan, en el orden de la pantalla.
CLASIFICACIONES = ("titularidad", "rentabilidad", "etapa")


@dataclass(frozen=True)
class CambioDeClase:
    ht_player_id: int
    name: str
    #: «titularidad», «rentabilidad» o «etapa».
    clasificacion: str
    antes: str
    ahora: str


@dataclass(frozen=True)
class CambiosDeClase:
    #: La sincronización de las fotos de hoy; None sin plantilla.
    sync_id: int | None
    #: La lectura con la que se compara; None si todavía no hay otra.
    previous_sync_id: int | None
    changes: tuple[CambioDeClase, ...]


async def _ultima_sincronizacion(session: AsyncSession, team_id: int) -> int | None:
    return await session.scalar(
        select(func.max(m.PlayerSnapshot.sync_id))
        .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
        .where(m.Player.team_id == team_id)
    )


def comparar(
    antes: dict[int, dict[str, str]],
    ahora: dict[int, dict[str, str]],
    nombres: dict[int, str],
) -> tuple[CambioDeClase, ...]:
    """Los cambios entre dos lecturas. Quien sólo está en una --llegó o se
    fue-- no cambió de clase: eso ya lo cuenta Cambios por su lado. Un valor
    vacío (sin experiencia leída, sin medianas) tampoco es un cambio."""
    cambios = []
    for pid, actual in ahora.items():
        previo = antes.get(pid)
        if previo is None:
            continue
        for c in CLASIFICACIONES:
            a, b = previo.get(c, ""), actual.get(c, "")
            if a and b and a != b:
                cambios.append(
                    CambioDeClase(
                        ht_player_id=pid,
                        name=nombres.get(pid, str(pid)),
                        clasificacion=c,
                        antes=a,
                        ahora=b,
                    )
                )
    return tuple(cambios)


async def cambios_de_clase(session: AsyncSession, team_id: int) -> CambiosDeClase:
    sync_id = await _ultima_sincronizacion(session, team_id)
    if sync_id is None:
        return CambiosDeClase(sync_id=None, previous_sync_id=None, changes=())

    clases = await ClasesDeJugadorQueryService(session).get(team_id)
    nombres = {j.ht_player_id: j.name for j in clases.players}

    guardadas = (
        (
            await session.execute(
                select(m.PlayerClassReading).where(
                    m.PlayerClassReading.team_id == team_id,
                    m.PlayerClassReading.sync_id == sync_id,
                )
            )
        )
        .scalars()
        .all()
    )
    if guardadas:
        # La lectura de esta sincronización ya existe: manda ella, no lo que
        # salga hoy (una etapa confirmada a mano después no es un cambio
        # del jugador).
        ahora = {
            r.ht_player_id: {
                "titularidad": r.titularidad,
                "rentabilidad": r.rentabilidad,
                "etapa": r.etapa,
            }
            for r in guardadas
        }
    else:
        ahora = {
            j.ht_player_id: {
                "titularidad": j.titularidad,
                "rentabilidad": j.rentabilidad,
                "etapa": j.etapa.stage,
            }
            for j in clases.players
        }
        creada = datetime.now(UTC)
        for pid, v in ahora.items():
            session.add(
                m.PlayerClassReading(
                    team_id=team_id,
                    sync_id=sync_id,
                    ht_player_id=pid,
                    titularidad=v["titularidad"],
                    rentabilidad=v["rentabilidad"],
                    etapa=v["etapa"],
                    created_at=creada,
                )
            )
        try:
            await session.commit()
        except IntegrityError:
            # Otra petición la escribió a la vez: la suya vale igual.
            await session.rollback()

    previa = await session.scalar(
        select(func.max(m.PlayerClassReading.sync_id)).where(
            m.PlayerClassReading.team_id == team_id,
            m.PlayerClassReading.sync_id < sync_id,
        )
    )
    if previa is None:
        return CambiosDeClase(sync_id=sync_id, previous_sync_id=None, changes=())
    antes = {
        r.ht_player_id: {
            "titularidad": r.titularidad,
            "rentabilidad": r.rentabilidad,
            "etapa": r.etapa,
        }
        for r in (
            await session.execute(
                select(m.PlayerClassReading).where(
                    m.PlayerClassReading.team_id == team_id,
                    m.PlayerClassReading.sync_id == previa,
                )
            )
        )
        .scalars()
        .all()
    }
    return CambiosDeClase(
        sync_id=sync_id, previous_sync_id=previa, changes=comparar(antes, ahora, nombres)
    )
