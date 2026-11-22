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
from app.application.queries.autopsia_del_partido import autopsia_del_partido
from app.application.queries.parte_del_partido import build_parte_del_partido
from app.application.queries.proximo_partido_oficial import proximo_partido_oficial
from app.domain.value_objects.ht_constants import MATCH_TYPE_LEAGUE
from app.infrastructure.db import models as m
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


@router.get(
    "/{team_id}/match-autopsy",
    summary="La autopsia del ultimo partido: el partido y la prediccion, abiertos",
    dependencies=[Depends(require_team_owner)],
)
async def match_autopsy(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any] | None:
    """Debajo del parte, en Partidos → Último partido (2026-11-22). Lo que
    dijimos, lo que habría dicho el motor con lo real, y por qué.

    Una vez por sync, como el parte: el partido ya está jugado."""
    from app.api.cache_por_sync import por_sync

    return await por_sync(
        session,
        team_id,
        "autopsia-del-partido",
        (),
        lambda: autopsia_del_partido(session, team_id),
    )


@router.get(
    "/{team_id}/next-official-match",
    summary="El proximo partido oficial: liga, copa, promocion o Masters",
    dependencies=[Depends(require_team_owner)],
)
async def next_official_match(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any] | None:
    """El que encabeza el Dashboard (2026-11-18). `null` sin partidos oficiales
    pendientes. El partido no se guarda por sync: depende de la hora, y pasado
    el partido el siguiente tiene que salir aunque no se haya sincronizado.

    LA PREDICCIÓN, SIEMPRE (regla del usuario del 2026-11-14: «todos los
    partidos oficiales deben tener predicción»). La de liga la pinta el
    Dashboard con el modelo de la serie; la de copa, promoción y Masters sale
    de la ficha de ese rival, la MISMA que enseñan Copa y Rivales, que además
    la guarda para compararla después del partido. Cuesta llamadas a
    Hattrick, así que se guarda cinco minutos por sync, como la de Copa."""
    p = await proximo_partido_oficial(session, team_id)
    if p is None:
        return None
    prediccion = None
    if p.match_type != MATCH_TYPE_LEAGUE:
        from app.api.cache_por_sync import por_sync
        from app.api.v1.endpoints.cup import _prediccion_de_rivales

        equipo = await session.get(m.Team, team_id)
        if equipo is not None:
            dicho = await por_sync(
                session,
                team_id,
                "prediccion-del-proximo-oficial",
                (p.ht_match_id,),
                lambda: _prediccion_de_rivales(session, equipo, p.rival_ht_id),
                ttl=300,
            )
            if dicho:
                prediccion = {
                    "ownProbability": dicho["own_probability"],
                    "rivalProbability": dicho["rival_probability"],
                    "mostLikelyScore": dicho["most_likely_score"],
                }
    return {
        "htMatchId": p.ht_match_id,
        "matchType": p.match_type,
        "tournament": p.tournament,
        "date": p.played_at.isoformat(),
        "home": p.home,
        "away": p.away,
        "isHome": p.is_home,
        "rivalHtId": p.rival_ht_id,
        "ordersGiven": p.orders_given,
        "round": p.round,
        "prediction": prediccion,
    }
