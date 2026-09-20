import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_squad_service,
    require_team_owner,
)
from app.api.rate_limit import limite
from app.api.v1.endpoints.precalentar import lanzar_precalentado
from app.application.commands.sync_team import (
    FILE_VERSIONS,
    MENSAJE_BASE_CORTADA,
    SyncBackfillBatchCommand,
    SyncMatchDetailsCommand,
    SyncPlayerDetailsCommand,
    SyncPreviousClubBonusCommand,
    SyncTeamCommand,
    SyncTeamHandler,
    SyncTransfersHistoryCommand,
    SyncTransfersPlayerCommand,
    mensaje_de_error,
)
from app.application.dto.dashboard import DashboardResponse
from app.application.dto.squad import PositionRatingDTO, SquadResponse
from app.application.queries.changes_history import (
    ALLOWED_WINDOW_WEEKS,
    DEFAULT_WINDOW_WEEKS,
    build_changes_history,
)
from app.application.queries.club import ClubQueryService
from app.application.queries.dashboard import DashboardQueryService
from app.application.queries.squad import SquadQueryService
from app.application.queries.sync_comparison import build_sync_comparison
from app.application.queries.transparencia import como_json as catalogo_de_calculos
from app.domain.engines.position_engine import model_info
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

#: Las sincronizaciones con stream que siguen corriendo. Sin la referencia el
#: recolector podría llevarse una a medias si quien miraba cerró la pestaña.
_en_curso: set[asyncio.Task[None]] = set()

# Cuantos jugadores atiende cada pulsacion. 40 llamadas a Hattrick es un
# lote que cabe de sobra en el tiempo de una peticion, incluso en un plan
# gratuito, y deja ver el avance sin que la espera canse.
# Un jugador por peticion. El censo de partidos tarda ~20 segundos por
# jugador, asi que un lote grande deja la barra quieta minutos enteros: con
# uno, avanza cada vez que termina alguien y "Parar" responde al instante.
BACKFILL_BATCH_SIZE = 1
MAX_BACKFILL_BATCH = 100


@router.get(
    "/{team_id}/club",
    summary="Estado, evolución y cuerpo técnico del club",
    dependencies=[Depends(require_team_owner)],
)
async def club(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Equivalente moderno de Club, Gráfico y Empleados de Hattrick Control.

    Expone sólo observaciones CHPP y conserva las tres series separadas para
    no convertir una lectura puntual en una tendencia ficticia.
    """
    data = await ClubQueryService(session).get(team_id)
    if data is None:
        raise HTTPException(404, f"team {team_id} not found")
    return data


@router.post(
    "/{team_id}/sync",
    status_code=200,
    dependencies=[
        Depends(require_team_owner),
        Depends(limite("sync", 6)),
    ],
)
async def trigger_sync(
    team_id: int,
    session: AsyncSession = Depends(get_session),
    user: m.User = Depends(get_current_user),
) -> dict[str, Any]:
    """Sync iniciado por el usuario (requisito CHPP: nunca por timer).

    Corre en el propio request en vez de encolarse a Celery: sin Redis/worker
    en desarrollo, encolar sería simular un job que nunca se ejecuta. Un solo
    fichero tarda segundos, así que es una espera razonable; migrar a Celery
    cuando haya cola real es cambiar quién llama a `SyncTeamHandler`, no su
    lógica."""
    team = await session.get(m.Team, team_id)
    if team is None:
        raise HTTPException(404, f"team {team_id} not found")
    if team.owner_user_id != user.id:
        raise HTTPException(403, "este equipo no está conectado a tu sesión")

    token_row = await session.scalar(select(m.CHPPToken).where(m.CHPPToken.user_id == user.id))
    if token_row is None or token_row.status != "active":
        raise HTTPException(409, "reconecta con Hattrick: no hay un token activo")

    client = CHPPClient(
        decrypt_token(token_row.oauth_token_enc), decrypt_token(token_row.oauth_secret_enc)
    )
    try:
        handler = SyncTeamHandler(SqlAlchemyUnitOfWork(SessionLocal), client)
        result = await handler.execute(
            SyncTeamCommand(user_id=user.id, team_id=team_id, ht_team_id=team.ht_team_id)
        )
        await _revisar_comisiones(handler, user.id, team_id, result)
        lanzar_precalentado(team_id)
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

    return _result_payload(result)


#: Cuántos ex-jugadores se revisan en busca de comisiones al final de cada
#: sincronización, y cada cuánto vuelve a tocarle a uno ya revisado.
LOTE_DE_COMISIONES_POR_SYNC = 10
DIAS_ENTRE_REVISIONES = 7


async def _revisar_comisiones(
    handler: Any,
    user_id: int,
    team_id: int,
    result: Any,
    on_progress: Any = None,
) -> None:
    """Un lote pequeño del barrido de comisiones, sin que nadie lo pulse.

    2026-09-13, pedido del usuario: quitar el botón «Sincronizar
    transferencias» sin perder las comisiones de reventa. Cada sincronización
    revisa unos pocos ex-jugadores --los vendidos más recientes primero, que
    son los que más probablemente se revenden-- y deja fuera a quien ya se
    revisó en la última semana, así que la cola rota sola de una vez a otra.

    NUNCA TUMBA LA SINCRONIZACIÓN. Lo que ya se descargó está guardado; si
    Hattrick falla aquí, se anota y la sincronización se da por buena.
    """
    from datetime import UTC, datetime, timedelta

    from app.application.commands.sync_team import SyncBackfillBatchCommand

    if on_progress is not None:
        await on_progress(
            f"Revisando comisiones de reventa de hasta {LOTE_DE_COMISIONES_POR_SYNC} ex-jugadores"
        )
    try:
        lote = await handler.execute_backfill_batch(
            SyncBackfillBatchCommand(
                user_id=user_id,
                team_id=team_id,
                limite=LOTE_DE_COMISIONES_POR_SYNC,
                revisar_desde=datetime.now(UTC).replace(tzinfo=None)
                - timedelta(days=DIAS_ENTRE_REVISIONES),
                reutilizar_fila=False,
            ),
            on_progress=on_progress,
        )
    except Exception as exc:  # noqa: BLE001, un lote caído no tumba la sincronización
        result.errors.append(f"comisiones: {exc}")
        return
    # Lo que encontró va al informe de ESTA sincronización: es dinero, y
    # quien acaba de sincronizar tiene que verlo sin ir a buscarlo.
    result.changes.extend(lote.changes)


def _result_payload(result: Any) -> dict[str, Any]:
    return {
        "syncId": result.sync_id,
        "status": result.status,
        "snapshotsWritten": result.snapshots_written,
        "unchanged": result.unchanged,
        "errors": result.errors,
        "changes": [{"category": c["category"], "summary": c["summary"]} for c in result.changes],
    }


@router.post(
    "/{team_id}/sync/stream",
    status_code=200,
    dependencies=[
        Depends(require_team_owner),
        Depends(limite("sync", 6)),
    ],
)
async def trigger_sync_stream(
    team_id: int,
    session: AsyncSession = Depends(get_session),
    user: m.User = Depends(get_current_user),
) -> StreamingResponse:
    """Como `trigger_sync`, pero transmite en vivo qué se está descargando
    pedido explícitamente 2026-08-05, mismo espíritu que la ventana
    "Conexión" de Hattrick Control: un sync ya no es una caja negra de
    15-20s, sino una línea por fichero/jugador/partido a medida que ocurre.

    NDJSON, no SSE: una línea JSON por evento (`{"type":"progress",...}` o
    el `{"type":"done"|"error",...}` final), el frontend lee el body como
    stream con `fetch`, sin depender de que el navegador entienda
    `text/event-stream` para un POST (EventSource solo hace GET)."""
    team = await session.get(m.Team, team_id)
    if team is None:
        raise HTTPException(404, f"team {team_id} not found")
    if team.owner_user_id != user.id:
        raise HTTPException(403, "este equipo no está conectado a tu sesión")

    token_row = await session.scalar(select(m.CHPPToken).where(m.CHPPToken.user_id == user.id))
    if token_row is None or token_row.status != "active":
        raise HTTPException(409, "reconecta con Hattrick: no hay un token activo")

    # Capturados como valores simples ANTES de entrar al generador: la
    # dependencia `session` se cierra en cuanto esta función retorna (el
    # generador se consume DESPUÉS, como cuerpo de la respuesta), así que
    # cualquier objeto ORM (`team`, `token_row`) quedaría desvinculado si se
    # usara dentro de `generate()`.
    oauth_token = decrypt_token(token_row.oauth_token_enc)
    oauth_secret = decrypt_token(token_row.oauth_secret_enc)
    token_row_id = token_row.id
    user_id = user.id
    ht_team_id = team.ht_team_id

    async def generate() -> AsyncIterator[bytes]:
        client = CHPPClient(oauth_token, oauth_secret)
        queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

        async def on_progress(message: str) -> None:
            await queue.put(("progress", message))

        async def run() -> None:
            try:
                handler = SyncTeamHandler(SqlAlchemyUnitOfWork(SessionLocal), client)
                result = await handler.execute(
                    SyncTeamCommand(user_id=user_id, team_id=team_id, ht_team_id=ht_team_id),
                    on_progress=on_progress,
                )
                await _revisar_comisiones(handler, user_id, team_id, result, on_progress)
                lanzar_precalentado(team_id)
                await queue.put(("done", result))
            except CHPPAuthError:
                async with SessionLocal() as s2:
                    row = await s2.get(m.CHPPToken, token_row_id)
                    if row is not None:
                        row.status = "revoked"
                        await s2.commit()
                await queue.put(("error", "Hattrick revocó el acceso: reconecta tu cuenta"))
            except CHPPUnavailableError as exc:
                await queue.put(("error", f"Hattrick no responde: {exc}"))
            except Exception as exc:  # noqa: BLE001, el stream reporta, no revienta el proceso
                await queue.put(("error", mensaje_de_error(exc)))
            finally:
                # El cliente se cierra cuando TERMINA la sincronización, no cuando
                # se corta el stream (2026-09-15, visto en producción). Si quien
                # miraba cerraba la pestaña, el cierre del stream cerraba también
                # el cliente con la tarea todavía viva, y la revisión de
                # comisiones fallaba con «the client has been closed».
                await client.aclose()

        task = asyncio.create_task(run())
        _en_curso.add(task)
        task.add_done_callback(_en_curso.discard)
        while True:
            kind, payload = await queue.get()
            if kind == "progress":
                yield (json.dumps({"type": "progress", "message": payload}) + "\n").encode()
            elif kind == "done":
                yield (
                    json.dumps({"type": "done", "result": _result_payload(payload)}) + "\n"
                ).encode()
                break
            else:  # "error"
                yield (json.dumps({"type": "error", "message": payload}) + "\n").encode()
                break
        await task

    # `identity` es la forma de decir «a éste no lo comprimas». Desde el
    # 2026-09-20 las respuestas salen comprimidas, y un flujo comprimido se
    # queda esperando a llenar el búfer: la barra de progreso no se movería
    # hasta el final, que es justo cuando ya no sirve. Starlette respeta una
    # cabecera de codificación que ya venga puesta, así que basta con ésta.
    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"Content-Encoding": "identity"},
    )


@router.post(
    "/{team_id}/matches/details/sync",
    status_code=200,
    dependencies=[
        Depends(require_team_owner),
        Depends(limite("sync", 6)),
    ],
)
async def trigger_match_details_sync(
    team_id: int,
    session: AsyncSession = Depends(get_session),
    user: m.User = Depends(get_current_user),
) -> dict[str, Any]:
    """Rellena los ratings por sector de los partidos ya jugados que aún no
    los tienen (HL-071/072). `matches` solo trae calendario y resultado;
    `matchdetails` se pide por partido, así que sin este endpoint la tabla de
    Partidos se queda en 0 para todo lo que no se sincronizó a mano."""
    team = await session.get(m.Team, team_id)
    if team is None:
        raise HTTPException(404, f"team {team_id} not found")
    if team.owner_user_id != user.id:
        raise HTTPException(403, "este equipo no está conectado a tu sesión")

    token_row = await session.scalar(select(m.CHPPToken).where(m.CHPPToken.user_id == user.id))
    if token_row is None or token_row.status != "active":
        raise HTTPException(409, "reconecta con Hattrick: no hay un token activo")

    ratings_missing = ~m.Match.ht_match_id.in_(select(m.MatchRating.ht_match_id))
    stadium_missing_on_home = (
        m.Match.home_team_ht_id == team.ht_team_id
    ) & ~m.Match.ht_match_id.in_(select(m.StadiumHistory.ht_match_id))
    pending = (
        (
            await session.execute(
                select(m.Match.ht_match_id).where(
                    (m.Match.home_team_ht_id == team.ht_team_id)
                    | (m.Match.away_team_ht_id == team.ht_team_id),
                    m.Match.status.ilike("finished"),
                    or_(ratings_missing, stadium_missing_on_home),
                )
            )
        )
        .scalars()
        .all()
    )

    client = CHPPClient(
        decrypt_token(token_row.oauth_token_enc), decrypt_token(token_row.oauth_secret_enc)
    )
    snapshots_written = 0
    unchanged = 0
    errors: list[str] = []
    try:
        handler = SyncTeamHandler(SqlAlchemyUnitOfWork(SessionLocal), client)
        arena_capacity: dict[str, int] | None = None
        try:
            arena = await client.fetch(
                "arenadetails", version=FILE_VERSIONS["arenadetails"], teamID=team.ht_team_id
            )
            arena_capacity = arena.get("current_capacity")
        except (CHPPAuthError, CHPPUnavailableError):
            raise
        except Exception as exc:  # no invalida ratings si falla sólo el aforo
            errors.append(f"arenadetails: {exc}")
        for ht_match_id in pending:
            r = await handler.execute_match_details(
                SyncMatchDetailsCommand(
                    user_id=user.id,
                    team_id=team_id,
                    ht_match_id=ht_match_id,
                    arena_capacity=arena_capacity,
                )
            )
            snapshots_written += r.snapshots_written
            unchanged += r.unchanged
            errors.extend(r.errors)
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
    finally:
        await client.aclose()

    return {
        "matchesProcessed": len(pending),
        "snapshotsWritten": snapshots_written,
        "unchanged": unchanged,
        "errors": errors,
    }


@router.post(
    "/{team_id}/players/details/sync",
    status_code=200,
    dependencies=[
        Depends(require_team_owner),
        Depends(limite("sync", 6)),
    ],
)
async def trigger_player_details_sync(
    team_id: int,
    session: AsyncSession = Depends(get_session),
    user: m.User = Depends(get_current_user),
) -> dict[str, Any]:
    """Club de origen y última posición/rating jugado de cada jugador
    (HL-15x fase B). `playerdetails` se pide por jugador, no por equipo, a
    diferencia del resto del sync, son tantas llamadas a CHPP como
    jugadores tenga la plantilla, así que es una acción aparte que el
    usuario dispara a mano, nunca parte del sync normal. El precio de
    compra (fase C) no está aquí: sale de `transfersteam.xml`, en el sync
    normal, y de `transfersplayer.xml` (por jugador, corrección 2026-08-03:
    funciona con este token, un comentario anterior tenía mal el nombre
    del fichero) para jugadores anteriores a esta app."""
    team = await session.get(m.Team, team_id)
    if team is None:
        raise HTTPException(404, f"team {team_id} not found")
    if team.owner_user_id != user.id:
        raise HTTPException(403, "este equipo no está conectado a tu sesión")

    token_row = await session.scalar(select(m.CHPPToken).where(m.CHPPToken.user_id == user.id))
    if token_row is None or token_row.status != "active":
        raise HTTPException(409, "reconecta con Hattrick: no hay un token activo")

    ht_player_ids = (
        (
            await session.execute(
                select(m.Player.ht_player_id).where(
                    m.Player.team_id == team_id, m.Player.left_team_at.is_(None)
                )
            )
        )
        .scalars()
        .all()
    )

    client = CHPPClient(
        decrypt_token(token_row.oauth_token_enc), decrypt_token(token_row.oauth_secret_enc)
    )
    snapshots_written = 0
    errors: list[str] = []
    try:
        handler = SyncTeamHandler(SqlAlchemyUnitOfWork(SessionLocal), client)
        for ht_player_id in ht_player_ids:
            r = await handler.execute_player_details(
                SyncPlayerDetailsCommand(
                    user_id=user.id, team_id=team_id, ht_player_id=ht_player_id
                )
            )
            snapshots_written += r.snapshots_written
            errors.extend(r.errors)
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
    finally:
        await client.aclose()

    return {
        "playersProcessed": len(ht_player_ids),
        "snapshotsWritten": snapshots_written,
        "errors": errors,
    }


@router.post(
    "/{team_id}/players/purchase-price/sync",
    status_code=200,
    dependencies=[
        Depends(require_team_owner),
        Depends(limite("sync", 6)),
    ],
)
async def trigger_purchase_price_sync(
    team_id: int,
    session: AsyncSession = Depends(get_session),
    user: m.User = Depends(get_current_user),
) -> dict[str, Any]:
    """HL-161: rellena `purchase_price` para jugadores que `transfersteam.xml`
    (sync normal) no pudo resolver, llegaron antes de sincronizar con esta
    app, o su compra quedó fuera de la única página que CHPP entrega por
    defecto. Una llamada a `transfersplayer.xml` por jugador SIN precio
    conocido (ni real ni manual); incluye jugadores que ya se fueron del
    club, porque son justo los que tienen una historia de saldo que cerrar."""
    team = await session.get(m.Team, team_id)
    if team is None:
        raise HTTPException(404, f"team {team_id} not found")
    if team.owner_user_id != user.id:
        raise HTTPException(403, "este equipo no está conectado a tu sesión")

    token_row = await session.scalar(select(m.CHPPToken).where(m.CHPPToken.user_id == user.id))
    if token_row is None or token_row.status != "active":
        raise HTTPException(409, "reconecta con Hattrick: no hay un token activo")

    ht_player_ids = (
        (
            await session.execute(
                select(m.Player.ht_player_id).where(
                    m.Player.team_id == team_id,
                    m.Player.purchase_price.is_(None),
                    m.Player.purchase_price_manual.is_(None),
                    # 2026-08-05, pedido explícitamente: "backfill de un
                    # jugador máximo una vez", transfersplayer.xml ya trae
                    # TODA la historia; si ya se intentó y no aparecimos como
                    # compradores, no va a cambiar en un intento futuro.
                    ~m.Player.tsi_at_purchase_attempted,
                )
            )
        )
        .scalars()
        .all()
    )

    client = CHPPClient(
        decrypt_token(token_row.oauth_token_enc), decrypt_token(token_row.oauth_secret_enc)
    )
    snapshots_written = 0
    errors: list[str] = []
    try:
        handler = SyncTeamHandler(SqlAlchemyUnitOfWork(SessionLocal), client)
        for ht_player_id in ht_player_ids:
            r = await handler.execute_transfers_player(
                SyncTransfersPlayerCommand(
                    user_id=user.id, team_id=team_id, ht_player_id=ht_player_id
                )
            )
            snapshots_written += r.snapshots_written
            errors.extend(r.errors)
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
    finally:
        await client.aclose()

    return {
        "playersProcessed": len(ht_player_ids),
        "snapshotsWritten": snapshots_written,
        "errors": errors,
    }


@router.post(
    "/{team_id}/players/previous-club-bonus/sync",
    status_code=200,
    dependencies=[
        Depends(require_team_owner),
        Depends(limite("sync", 6)),
    ],
)
async def trigger_previous_club_bonus_backfill(
    team_id: int,
    session: AsyncSession = Depends(get_session),
    user: m.User = Depends(get_current_user),
) -> dict[str, Any]:
    """HL-161, 2026-08-14, pedido explícitamente ("backfill masivo de
    todos los ex-jugadores"): recorre TODOS los jugadores alguna vez
    vendidos por este club (no solo los recién revisados, a diferencia
    del monitoreo automático acotado dentro del sync normal) buscando, uno
    por uno, si el club al que se los vendimos ya los revendió, y si es
    así, calcula y guarda la comisión exacta de club anterior. Reemplaza
    por completo el reparto heurístico que antes vivía en
    `resale_bonus.py`. Costoso (una llamada a transfersplayer.xml por
    jugador, más matchesarchive+matchlineup la primera vez que encuentra
    una reventa real), por eso es un botón explícito, no parte del sync
    normal."""
    team = await session.get(m.Team, team_id)
    if team is None:
        raise HTTPException(404, f"team {team_id} not found")
    if team.owner_user_id != user.id:
        raise HTTPException(403, "este equipo no está conectado a tu sesión")

    token_row = await session.scalar(select(m.CHPPToken).where(m.CHPPToken.user_id == user.id))
    if token_row is None or token_row.status != "active":
        raise HTTPException(409, "reconecta con Hattrick: no hay un token activo")

    ht_player_ids = (
        (
            await session.execute(
                select(m.Player.ht_player_id).where(
                    m.Player.team_id == team_id,
                    m.Player.sold_at.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )

    client = CHPPClient(
        decrypt_token(token_row.oauth_token_enc), decrypt_token(token_row.oauth_secret_enc)
    )
    bonuses_found = 0
    errors: list[str] = []
    try:
        handler = SyncTeamHandler(SqlAlchemyUnitOfWork(SessionLocal), client)
        for ht_player_id in ht_player_ids:
            r = await handler.execute_previous_club_bonus(
                SyncPreviousClubBonusCommand(
                    user_id=user.id, team_id=team_id, ht_player_id=ht_player_id
                )
            )
            bonuses_found += r.snapshots_written
            errors.extend(r.errors)
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
    finally:
        await client.aclose()

    return {
        "playersProcessed": len(ht_player_ids),
        "bonusesFound": bonuses_found,
        "errors": errors,
    }


@router.post(
    "/{team_id}/transfers/sync",
    status_code=200,
    dependencies=[
        Depends(require_team_owner),
        Depends(limite("sync", 6)),
    ],
)
async def trigger_transfers_history_sync(
    team_id: int,
    session: AsyncSession = Depends(get_session),
    user: m.User = Depends(get_current_user),
) -> dict[str, Any]:
    """HL-161, 2026-08-04: botón "Actualizar transferencias", pagina
    transfersteam.xml completo (no solo la página más reciente del sync
    normal), trayendo TODA la historia de compraventas del equipo (casi
    1000 transferencias reales para una cuenta activa desde 2015), creando
    identidades mínimas para jugadores que esta app nunca vio en
    players.xml. La primera vez recorre todas las páginas; las siguientes
    paran en cuanto reconocen una transferencia ya vista, ver
    `execute_transfers_history`."""
    team = await session.get(m.Team, team_id)
    if team is None:
        raise HTTPException(404, f"team {team_id} not found")
    if team.owner_user_id != user.id:
        raise HTTPException(403, "este equipo no está conectado a tu sesión")

    token_row = await session.scalar(select(m.CHPPToken).where(m.CHPPToken.user_id == user.id))
    if token_row is None or token_row.status != "active":
        raise HTTPException(409, "reconecta con Hattrick: no hay un token activo")

    client = CHPPClient(
        decrypt_token(token_row.oauth_token_enc), decrypt_token(token_row.oauth_secret_enc)
    )
    try:
        handler = SyncTeamHandler(SqlAlchemyUnitOfWork(SessionLocal), client)
        result = await handler.execute_transfers_history(
            SyncTransfersHistoryCommand(
                user_id=user.id, team_id=team_id, ht_team_id=team.ht_team_id
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
    finally:
        await client.aclose()

    return {
        "status": result.status,
        "pagesFetched": result.pages_fetched,
        "transfersSeen": result.transfers_seen,
        "transfersNew": result.transfers_new,
        "snapshotsWritten": result.snapshots_written,
        "errors": result.errors,
    }


class SetManualPurchasePriceBody(BaseModel):
    price: int
    purchased_at: str | None = None


@router.put(
    "/{team_id}/players/{ht_player_id}/purchase-price",
    status_code=200,
    dependencies=[Depends(require_team_owner)],
)
async def set_manual_purchase_price(
    team_id: int,
    ht_player_id: int,
    body: SetManualPurchasePriceBody,
    session: AsyncSession = Depends(get_session),
    user: m.User = Depends(get_current_user),
) -> dict[str, Any]:
    """HL-161: precio de compra escrito a mano, solo para cuando ni
    `transfersteam.xml` ni `transfersplayer.xml` traen una compra real
    (jugador anterior a cualquier historial que CHPP guarde). Nunca
    sobrescribe un precio real ya conocido, bórralo primero si de verdad
    quieres reemplazarlo."""
    team = await session.get(m.Team, team_id)
    if team is None:
        raise HTTPException(404, f"team {team_id} not found")
    if team.owner_user_id != user.id:
        raise HTTPException(403, "este equipo no está conectado a tu sesión")

    player = await session.scalar(
        select(m.Player).where(m.Player.ht_player_id == ht_player_id, m.Player.team_id == team_id)
    )
    if player is None:
        raise HTTPException(404, f"player {ht_player_id} not found on team {team_id}")
    if player.purchase_price is not None:
        raise HTTPException(
            409,
            "ya hay un precio de compra real (transfersteam/transfersplayer), "
            "no se puede sobrescribir con uno manual",
        )

    player.purchase_price_manual = body.price
    if body.purchased_at:
        player.purchased_at_manual = datetime.fromisoformat(body.purchased_at).replace(tzinfo=UTC)
    await session.commit()
    return {"htPlayerId": ht_player_id, "purchasePriceManual": body.price}


CONFIRMABLE_CAREER_STAGES = {"promesa", "pico", "veterano", "rotacion", "declive"}


class ConfirmCareerStageBody(BaseModel):
    # None = borrar la confirmación y volver a mostrar la sugerencia de la app.
    stage: str | None = None


@router.post(
    "/{team_id}/players/{ht_player_id}/career-stage",
    summary="Confirmar (o borrar, el momento de carrera sugerido por la app, HL-15x #93",
    dependencies=[Depends(require_team_owner)],
)
async def confirm_career_stage(
    team_id: int,
    ht_player_id: int,
    body: ConfirmCareerStageBody,
    session: AsyncSession = Depends(get_session),
    user: m.User = Depends(get_current_user),
) -> dict[str, Any]:
    """La app SUGIERE el momento de carrera (career_stage_engine, con sus
    señales reales); el usuario CONFIRMA aquí, nunca se sobreescribe solo
    en un sync posterior."""
    team = await session.get(m.Team, team_id)
    if team is None:
        raise HTTPException(404, f"team {team_id} not found")
    if team.owner_user_id != user.id:
        raise HTTPException(403, "este equipo no está conectado a tu sesión")
    if body.stage is not None and body.stage not in CONFIRMABLE_CAREER_STAGES:
        raise HTTPException(
            400, f"etapa desconocida: {body.stage}, válidas: {sorted(CONFIRMABLE_CAREER_STAGES)}"
        )

    player = await session.scalar(
        select(m.Player).where(m.Player.ht_player_id == ht_player_id, m.Player.team_id == team_id)
    )
    if player is None:
        raise HTTPException(404, f"player {ht_player_id} not found in team {team_id}")

    player.confirmed_career_stage = body.stage
    player.confirmed_career_stage_at = datetime.now(UTC) if body.stage is not None else None
    await session.commit()

    return {
        "htPlayerId": ht_player_id,
        "confirmedStage": player.confirmed_career_stage,
        "confirmedAt": (
            player.confirmed_career_stage_at.isoformat()
            if player.confirmed_career_stage_at is not None
            else None
        ),
    }


@router.get(
    "/{team_id}/sync/changes",
    summary="Qué cambió en el último sync (HL-140)",
    dependencies=[Depends(require_team_owner)],
)
async def last_sync_changes(
    team_id: int,
    sync_id: int | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Al estilo Hattrick Control: qué cambió desde la vez anterior, no solo
    el estado actual. Vive aparte de `POST /sync` para poder volver a verlo
    tras recargar la página sin tener que sincronizar otra vez.

    `sync_id` (2026-08-15, pedido explícito) permite navegar el archivo: la
    respuesta trae en `availableReports` las fechas que SÍ tuvieron cambios,
    y pedir una de ellas devuelve esa comparación en vez de la más reciente.
    Un id inválido o sin cambios cae a la última, no es un error del usuario
    pedir una fecha que ya no existe."""
    return await build_sync_comparison(session, team_id, sync_id)


@router.get(
    "/{team_id}/changes/history",
    summary="Histórico real de cambios de jugadores",
    dependencies=[Depends(require_team_owner)],
)
async def changes_history(
    team_id: int,
    player_id: int | None = Query(None, description="Jugador a mostrar en la gráfica"),
    weeks: int = Query(
        DEFAULT_WINDOW_WEEKS,
        description=(
            "Semanas hacia atrás con las que comparar (1, 2, 4, 8 o 16). "
            "0 = «siempre»: contra el primer cierre guardado de cada jugador."
        ),
    ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Archivo de Cambios: habilidades, forma, experiencia y serie de jugador.

    Cada fila es la diferencia NETA contra el cierre semanal de hace `weeks`
    semanas, salida de valores CHPP guardados; los syncs repetidos sin
    variaciones no producen filas ficticias.
    """
    if weeks not in ALLOWED_WINDOW_WEEKS:
        raise HTTPException(
            status_code=422,
            detail=f"weeks debe ser uno de {', '.join(map(str, ALLOWED_WINDOW_WEEKS))}",
        )
    from app.api.cache_por_sync import por_sync

    # Una vez por sync (2026-09-14): las fotos sólo cambian al sincronizar.
    return await por_sync(
        session,
        team_id,
        "historial-de-cambios",
        (player_id, weeks),
        lambda: build_changes_history(session, team_id, player_id, weeks=weeks),
    )


async def dashboard_guardado(session: AsyncSession, team_id: int) -> DashboardResponse | None:
    """El Dashboard, calculado una vez por sync (2026-09-14).

    Medido en producción: 5 segundos en cada visita aunque nada hubiera
    cambiado. Tope de 15 minutos porque «datos desactualizados» mira el reloj.
    Lo usan el endpoint y el precalentado del final del sync.
    """
    from app.api.cache_por_sync import TTL_CON_RELOJ, por_sync

    data: DashboardResponse | None = await por_sync(
        session,
        team_id,
        "dashboard",
        (),
        lambda: DashboardQueryService(session).get(team_id),
        ttl=TTL_CON_RELOJ,
    )
    return data


@router.get(
    "/{team_id}/dashboard",
    response_model=DashboardResponse,
    response_model_by_alias=True,
    dependencies=[Depends(require_team_owner)],
)
async def dashboard(
    team_id: int,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> DashboardResponse:
    data = await dashboard_guardado(session, team_id)
    if data is None:
        raise HTTPException(404, f"team {team_id} not found")
    # Cache barato: el payload solo cambia cuando cambia el sync (docs/04)
    if data.sync_id is not None:
        response.headers["ETag"] = f'W/"dash-{team_id}-{data.sync_id}"'
        response.headers["Cache-Control"] = "private, max-age=30"
    return data


@router.get(
    "/{team_id}/squad",
    response_model=SquadResponse,
    response_model_by_alias=True,
    summary="Plantilla con rating de posición (HL-021, HL-022)",
    dependencies=[Depends(require_team_owner)],
)
async def squad(
    team_id: int,
    position: str | None = Query(
        None,
        description="Si se indica, la plantilla se ordena por el rendimiento en esa posición",
    ),
    comparison_sync_id: int | None = Query(
        None,
        description="Snapshot histórico contra el cual comparar la plantilla actual",
    ),
    svc: SquadQueryService = Depends(get_squad_service),
) -> SquadResponse:
    try:
        data = await svc.get(team_id, position, comparison_sync_id)
    except KeyError as exc:
        raise HTTPException(400, str(exc)) from exc
    if data is None:
        raise HTTPException(404, f"team {team_id} not found")
    return data


@router.get(
    "/players/{ht_player_id}/positions",
    response_model=list[PositionRatingDTO],
    response_model_by_alias=True,
    summary="Las 19 variantes de posición de un jugador (HL-020)",
)
async def player_positions(
    ht_player_id: int,
    svc: SquadQueryService = Depends(get_squad_service),
) -> list[PositionRatingDTO]:
    data = await svc.player_positions(ht_player_id)
    if data is None:
        raise HTTPException(404, f"player {ht_player_id} not found")
    return data


@router.get("/calculos", summary="Catálogo de cálculos con su formulación y sus constantes")
async def calculos() -> list[dict[str, Any]]:
    """Qué calcula la herramienta, con qué fórmula y con qué constantes.

    No lleva `team_id`: describe los MOTORES, que son los mismos para todos.
    Los valores del club de cada uno llegan por los endpoints que ya existen
    --la fórmula de entrenamiento, la matriz de posiciones-- y la pantalla los
    engancha bajo su cálculo.
    """
    return catalogo_de_calculos()


@router.get("/positions/model", summary="Modelo de posiciones basado en el Manual no Escrito")
async def positions_model() -> dict[str, Any]:
    """Procedencia, matriz y factores del motor de posiciones."""
    return model_info()


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
