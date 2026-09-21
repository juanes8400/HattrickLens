"""Partidos. HL-071, HL-072, HL-073, HL-075, HL-076."""

import json
from dataclasses import asdict
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_team_owner
from app.api.v1.endpoints.arena import _camel
from app.application.queries.matches import MatchesQueryService
from app.infrastructure.db.session import get_session

router = APIRouter()


@router.get(
    "/teams/{team_id}/matches",
    summary="Partidos, ratings y conversión",
    dependencies=[Depends(require_team_owner)],
)
async def matches(
    team_id: int,
    include_friendlies: bool = Query(False, description="Incluir Amistosos en el historial"),
    season: int | None = Query(
        None, description="Filtrar por temporada. Ausente = todas las temporadas"
    ),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Separa generación de definición, que son problemas distintos.

    «Generamos nueve ocasiones y metimos una» y «llegamos tres veces y metimos
    dos» son el mismo 1-2 y piden decisiones opuestas. Las tasas vienen con su
    tamaño de muestra y marcadas como fiables o no, porque con pocas ocasiones
    la diferencia entre un 20% y un 40% es azar.

    Escaleras, Duelos, Torneos y Preparación se excluyen siempre, no son
    partidos oficiales y no hay override para ellos en ningún punto de la
    herramienta.
    """
    from app.api.cache_por_sync import por_sync

    async def calcular() -> bytes | None:
        datos = await MatchesQueryService(session).overview(
            team_id, include_friendlies=include_friendlies, season=season
        )
        if datos is None:
            return None
        return json.dumps(_camel(asdict(datos)), ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )

    # Una vez por sync (2026-09-14): los partidos sólo cambian al sincronizar.
    #
    # LO GUARDADO SON LOS BYTES, no el diccionario (2026-09-20). Es el cuerpo
    # más gordo de la aplicación --setecientos y pico partidos con su historial
    # de ratings-- y lo que costaba caro no era la consulta, que son 162 ms una
    # vez, sino el camino de vuelta, que se repetía ENTERO en cada visita:
    # `asdict` copia en profundidad las mil quinientas fichas, `_camel` las
    # recorre otra vez para renombrar cada clave, y el serializador de la web
    # las vuelve a recorrer para convertirlas. Tres paseos por el mismo árbol
    # para llegar al mismo texto de siempre. Devolviendo una respuesta ya
    # escrita, la visita repetida no paga ninguno de los tres.
    cuerpo = await por_sync(
        session,
        team_id,
        "partidos",
        (include_friendlies, season),
        calcular,
    )
    if cuerpo is None:
        raise HTTPException(404, f"no played matches for team {team_id}")
    return Response(content=cuerpo, media_type="application/json")


@router.get(
    "/teams/{team_id}/matches/{ht_match_id}",
    summary="Análisis de un partido (HL-071)",
    dependencies=[Depends(require_team_owner)],
)
async def match_detail(
    team_id: int, ht_match_id: int, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    """Sector a sector frente al rival, con veredicto y puntos fuertes/débiles."""
    data = await MatchesQueryService(session).detail(team_id, ht_match_id)
    if data is None:
        raise HTTPException(404, f"no ratings for match {ht_match_id}")
    return cast(dict[str, Any], _camel(asdict(data)))
