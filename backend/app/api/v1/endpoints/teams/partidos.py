"""Partidos.

Sale de partir `teams.py`, que tenia 1179 lineas y se abria
entera para tocar cualquiera de sus rutas. El `__init__.py` del paquete
monta `router` con todos estos, asi que las URL no cambian.
"""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    require_team_owner,
)
from app.application.queries.parte_del_partido import build_parte_del_partido
from app.infrastructure.db.session import get_session

router = APIRouter()


@router.get(
    "/{team_id}/last-match-report",
    summary="El ultimo partido jugado, contra lo que habiamos dicho de el",
    dependencies=[Depends(require_team_owner)],
)
async def last_match_report(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any] | None:
    """Encabeza Cambios: el resultado al lado de la terna que dabamos ANTES.

    `null` mientras el equipo no tenga ningun partido jugado, y `prediction`
    a `null` cuando de ese partido no guardamos nada, que es el caso de todo
    partido anterior al 2026-09-26. La pantalla pinta los dos estados.

    Una vez por sync: ni el resultado de un partido jugado ni lo que dijimos
    antes de jugarlo vuelven a cambiar.
    """
    from app.api.cache_por_sync import por_sync

    return await por_sync(
        session,
        team_id,
        "parte-del-partido",
        (),
        lambda: build_parte_del_partido(session, team_id),
    )
