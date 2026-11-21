"""Que cambio en la ultima sincronizacion, y el historial.

Sale de partir `teams.py`, que tenia 1179 lineas y se abria
entera para tocar cualquiera de sus rutas. El `__init__.py` del paquete
monta `router` con todos estos, asi que las URL no cambian.
"""

from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cache_por_sync import por_sync
from app.api.deps import (
    require_team_owner,
)
from app.application.queries.changes_history import (
    ALLOWED_WINDOW_WEEKS,
    DEFAULT_WINDOW_WEEKS,
    build_changes_history,
)
from app.application.queries.sync_comparison import build_sync_comparison
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session

router = APIRouter()

#: La clave del informe de Cambios en la caché por sync.
CLAVE_DE_CAMBIOS = "cambios-de-la-sincronizacion"


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
    pedir una fecha que ya no existe.

    GUARDADO HASTA QUE HAYA ALGO NUEVO (2026-11-21, pedido del usuario: que
    las páginas carguen más rápido). Eran 131 consultas en cada visita. La
    clave lleva el último cambio guardado del equipo, así que lo que se
    apunte después del sync --las comisiones que se revisan al terminar--
    lo invalida solo; y editar precios o etapas a mano lo olvida
    (`CLAVE_DE_CAMBIOS`), porque cambia los cruces del precio de equilibrio."""
    ultimo_cambio = await session.scalar(
        select(func.max(m.SyncChange.id)).where(m.SyncChange.team_id == team_id)
    )

    async def calcular() -> dict[str, Any]:
        return await build_sync_comparison(session, team_id, sync_id)

    return cast(
        dict[str, Any],
        await por_sync(session, team_id, CLAVE_DE_CAMBIOS, (sync_id, ultimo_cambio), calcular),
    )


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

    # Una vez por sync (2026-09-14): las fotos sólo cambian al sincronizar.
    return await por_sync(
        session,
        team_id,
        "historial-de-cambios",
        (player_id, weeks),
        lambda: build_changes_history(session, team_id, player_id, weeks=weeks),
    )
