"""El resumen del equipo.

Sale de partir `analysis.py`, que tenia 2309 lineas y se abria
entera para tocar cualquiera de sus rutas. El `__init__.py` del paquete
monta `router` con todos estos, asi que las URL no cambian.
"""

from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_team_owner
from app.application.queries.team_overview import TeamOverviewQueryService
from app.infrastructure.db.session import get_session

router = APIRouter()


@router.get(
    "/teams/{team_id}/overview",
    summary="Habilidades: la plantilla entera promediada por grupos",
    dependencies=[Depends(require_team_owner)],
)
async def team_overview(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Promedios de plantilla agrupados para leer al equipo de un vistazo.

    Cada grupo declara con qué forma se puede dibujar: `radar` solo cuando
    todas sus métricas comparten escala, `bars` cuando cada una necesita su
    propio techo (ver `team_overview.py`).
    """
    # Una vez por sync (2026-09-20). Es el promedio de la plantilla entera por
    # grupos, con sus series semanales: 168 ms de cuentas que sólo cambian
    # cuando llegan datos nuevos, y se pagaban en cada visita a Habilidades.
    from app.api.cache_por_sync import por_sync

    respuesta = await por_sync(
        session, team_id, "habilidades", (), lambda: _team_overview_sin_cache(session, team_id)
    )
    if respuesta is None:
        raise HTTPException(404, f"team {team_id} sin plantilla sincronizada")
    return cast(dict[str, Any], respuesta)


async def _team_overview_sin_cache(session: AsyncSession, team_id: int) -> dict[str, Any] | None:
    data = await TeamOverviewQueryService(session).get(team_id)
    if data is None:
        return None
    return {
        "teamName": data.team_name,
        "playerCount": data.player_count,
        "currency": data.currency,
        "groups": [
            {
                "key": g.key,
                "label": g.label,
                "chart": g.chart,
                "note": g.note,
                "weeks": g.weeks,
                "charts": [
                    {
                        "key": ch.key,
                        "title": ch.title,
                        "scaleMin": ch.scale_min,
                        "scaleMax": ch.scale_max,
                        "band": ch.band,
                        "series": [
                            {
                                "key": sr.key,
                                "label": sr.label,
                                "values": sr.values,
                                "display": sr.display,
                            }
                            for sr in ch.series
                        ],
                    }
                    for ch in g.charts
                ],
                "pitch": [
                    {
                        "key": sl.key,
                        "label": sl.label,
                        "count": sl.count,
                        "bestRating": sl.best_rating,
                        "topPlayer": sl.top_player,
                        "bestVariantLabel": sl.best_variant_label,
                        "averageRating": sl.average_rating,
                    }
                    for sl in g.pitch
                ],
                "specialRoles": [
                    {
                        "key": sr.key,
                        "label": sr.label,
                        "topPlayer": sr.top_player,
                        "rating": sr.rating,
                    }
                    for sr in g.special_roles
                ],
                "metrics": [
                    {
                        "key": mtr.key,
                        "label": mtr.label,
                        "value": mtr.value,
                        "scaleMax": mtr.scale_max,
                        "display": mtr.display,
                        "valueLabel": mtr.value_label,
                    }
                    for mtr in g.metrics
                ],
            }
            for g in data.groups
        ],
    }
