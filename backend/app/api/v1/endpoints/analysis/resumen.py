"""El resumen del equipo.

Sale de partir `analysis.py`, que tenia 2309 lineas y se abria
entera para tocar cualquiera de sus rutas. El `__init__.py` del paquete
monta `router` con todos estos, asi que las URL no cambian.
"""

from typing import Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query
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
    mirar: Literal["estrellas", "gangas", "caros", "economicos"] | None = Query(
        None,
        description="Un grupo de Rentabilidad deportiva en vez de la plantilla entera.",
    ),
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

    # El grupo de «Mirar a» va en la clave: Rentabilidad deportiva sólo
    # cambia al sincronizar, así que también se guarda una vez por sync.
    respuesta = await por_sync(
        session,
        team_id,
        "habilidades",
        (mirar,),
        lambda: _team_overview_sin_cache(session, team_id, mirar),
    )
    if respuesta is None:
        raise HTTPException(404, f"team {team_id} sin plantilla sincronizada")
    return cast(dict[str, Any], respuesta)


async def _team_overview_sin_cache(
    session: AsyncSession, team_id: int, mirar: str | None = None
) -> dict[str, Any] | None:
    data = await TeamOverviewQueryService(session).get(team_id, mirar)
    if data is None:
        return None
    return {
        "teamName": data.team_name,
        "playerCount": data.player_count,
        "currency": data.currency,
        "mirar": {
            "selected": data.mirar.selected,
            "options": [
                {"key": o.key, "label": o.label, "count": o.count} for o in data.mirar.options
            ],
            "members": data.mirar.members,
        },
        "groups": [
            {
                "key": g.key,
                "label": g.label,
                "chart": g.chart,
                "note": g.note,
                "weeks": g.weeks,
                "counts": g.counts,
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
                                "reference": sr.reference,
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
