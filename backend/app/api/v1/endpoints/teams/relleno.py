"""Rellenar hacia atras lo que una sincronizacion vieja no trajo.

Sale de partir `teams.py`, que tenia 1179 lineas y se abria
entera para tocar cualquiera de sus rutas. El `__init__.py` del paquete
monta `router` con todos estos, asi que las URL no cambian.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    require_team_owner,
)
from app.api.rate_limit import limite
from app.application.commands.sync_team import (
    MENSAJE_BASE_CORTADA,
    SyncBackfillBatchCommand,
    SyncTeamHandler,
)
from app.infrastructure.chpp.client import (
    CHPPAuthError,
    CHPPClient,
    CHPPDeniedError,
    CHPPUnavailableError,
)
from app.infrastructure.db import models as m
from app.infrastructure.db.session import SessionLocal, get_session
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.security.tokens import decrypt_token

router = APIRouter()

# Cuantos jugadores atiende cada pulsacion. 40 llamadas a Hattrick es un
# lote que cabe de sobra en el tiempo de una peticion, incluso en un plan
# gratuito, y deja ver el avance sin que la espera canse.
# Un jugador por peticion. El censo de partidos tarda ~20 segundos por
# jugador, asi que un lote grande deja la barra quieta minutos enteros: con
# uno, avanza cada vez que termina alguien y "Parar" responde al instante.
BACKFILL_BATCH_SIZE = 1

MAX_BACKFILL_BATCH = 100


@router.get(
    "/{team_id}/backfill",
    summary="Cuántas fichas de jugador quedan por descargar",
    dependencies=[Depends(require_team_owner)],
)
async def backfill_pending(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Lo que le falta al pasado, en jugadores.

    Se responde sin llamar a Hattrick: son consultas a la base. Así la
    pantalla puede decir "faltan 515 fichas" ANTES de que nadie pulse nada, y
    no hay que gastar cuota para saber cuánto queda.
    """
    uow = SqlAlchemyUnitOfWork(SessionLocal)
    # El contador no habla con Hattrick, solo con la base: el cliente CHPP no
    # hace falta y por eso no se construye ninguno.
    handler = SyncTeamHandler(uow, None)  # type: ignore[arg-type]
    async with uow:
        pendientes = await handler.pendientes_de_ficha(uow, team_id)
    total: set[int] = set()
    for cola in pendientes.values():
        total |= set(cola)
    return {
        "pending": len(total),
        "batchSize": BACKFILL_BATCH_SIZE,
        "detail": {
            "profile": len(pendientes["ficha"]),
            "purchasePrice": len(pendientes["precio"]),
            "destination": len(pendientes["destino"]),
            # Los dos que el usuario pidió ver de frente: a cuántos hay que
            # construirles el historial completo esta primera vez, y cuántos
            # siguen pudiendo darnos comisión algún día.
            "census": len(pendientes["censo"]),
            "resaleWatch": len(pendientes["reventa"]),
        },
    }


@router.post(
    "/{team_id}/backfill/run",
    status_code=200,
    summary="Descargar un lote de fichas pendientes",
    dependencies=[
        Depends(require_team_owner),
        # Cubo propio y holgado: cada peticion es UN jugador, asi que el
        # tope real de gasto lo pone el numero de ex-jugadores, no este
        # limite. Separado de "sync" para que rellenar el pasado no deje
        # a nadie sin poder sincronizar.
        Depends(limite("relleno", 1500)),
    ],
)
async def backfill_run(
    team_id: int,
    session: AsyncSession = Depends(get_session),
    user: m.User = Depends(get_current_user),
    batch: int = Query(
        BACKFILL_BATCH_SIZE,
        ge=1,
        le=MAX_BACKFILL_BATCH,
        description="Cuántos jugadores atender en este lote",
    ),
    since: datetime | None = Query(
        None,
        description=(
            "Momento en que el usuario pulsó. Acota la vigilancia de reventas "
            "a una sola pasada: quien ya se revisó después de esa marca no "
            "vuelve a la cola hasta la siguiente pulsación."
        ),
    ),
) -> dict[str, Any]:
    """Un lote y para. De cada jugador se descarga TODO lo que le falte antes
    de pasar al siguiente, para que ninguna ficha quede a medias, y se
    devuelve cuántos quedan para que la pantalla lo enseñe."""
    team = await session.get(m.Team, team_id)
    if team is None:
        raise HTTPException(404, f"team {team_id} not found")

    token_row = await session.scalar(select(m.CHPPToken).where(m.CHPPToken.user_id == user.id))
    if token_row is None or token_row.status != "active":
        raise HTTPException(409, "reconecta con Hattrick: no hay un token activo")

    client = CHPPClient(
        decrypt_token(token_row.oauth_token_enc), decrypt_token(token_row.oauth_secret_enc)
    )
    try:
        handler = SyncTeamHandler(SqlAlchemyUnitOfWork(SessionLocal), client)
        result = await handler.execute_backfill_batch(
            SyncBackfillBatchCommand(
                user_id=user.id,
                team_id=team_id,
                limite=batch,
                revisar_desde=since.replace(tzinfo=None) if since else None,
            )
        )
    except CHPPAuthError as exc:
        token_row.status = "revoked"
        await session.commit()
        raise HTTPException(401, "Hattrick revocó el acceso: reconecta tu cuenta") from exc
    except CHPPDeniedError as exc:
        # El token sigue vivo: sólo esta llamada estaba vedada. Ni se
        # marca revocado ni se devuelve 401, que el frontend leería
        # como sesión caducada y echaría al usuario (2026-09-04).
        raise HTTPException(403, f"Hattrick no permite esta operación: {exc}") from exc
    except CHPPUnavailableError as exc:
        raise HTTPException(503, f"Hattrick no responde: {exc}") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(503, MENSAJE_BASE_CORTADA) from exc
    finally:
        await client.aclose()

    return {
        "status": result.status,
        "done": result.players_done,
        "pending": result.players_pending,
        "players": result.players_named,
        # El mapa del barrido: la barra lo pinta como un recorrido por la cola
        # --frente por la izquierda, marcas donde cayo el azar-- en vez de
        # como un porcentaje. Va entero en cada respuesta para que el
        # navegador solo tenga que pintarlo.
        "queue": (
            {
                "total": result.queue_map.total,
                "done": result.queue_map.hechas,
                "front": result.queue_map.frente,
            }
            if result.queue_map is not None
            else None
        ),
        # El resumen del barrido, para enseñarlo al parar.
        "balance": (
            {
                "open": result.queue_balance.abiertos,
                "toCheck": result.queue_balance.por_mirar,
                "closed": result.queue_balance.cerrados,
                "closedTotal": result.queue_balance.total_cerrados,
                "commissions": result.queue_balance.comisiones,
                "histories": result.queue_balance.historiales,
            }
            if result.queue_balance is not None
            else None
        ),
        "errors": result.errors[:5],
    }
