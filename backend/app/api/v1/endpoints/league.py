"""Liga y predicciones. HL-080, HL-083, HL-090, HL-091, HL-094."""
from dataclasses import asdict
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.v1.endpoints.analysis import roster
from app.api.v1.endpoints.arena import _camel
from app.application.commands.sync_team import FILE_VERSIONS
from app.application.queries.league import LeagueQueryService
from app.domain.engines.lineup_optimizer import best_formation
from app.domain.engines.position_engine import best_position
from app.domain.engines.rival_scouting import tsi_kde_comparison
from app.domain.engines.season_simulator import model_info
from app.infrastructure.chpp.client import CHPPAuthError, CHPPClient, CHPPUnavailableError
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.infrastructure.security.tokens import decrypt_token

router = APIRouter()


@router.get("/teams/{team_id}/league", summary="Clasificación, calendario y simulación")
async def league(
    team_id: int,
    runs: int = Query(10000, ge=1000, le=50000, description="Simulaciones de Monte Carlo"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """En qué puesto se acaba, como distribución y no como número.

    Dieciséis jornadas son pocas para que el mejor equipo gane siempre, así que
    la respuesta útil es una distribución de posiciones finales. Las fuerzas de
    ataque y defensa se encogen hacia la media de la liga con un peso que
    depende de las jornadas jugadas: el modelo empieza humilde y se vuelve
    específico según llegan los datos, en vez de fabricar certezas en la
    jornada 3.
    """
    data = await LeagueQueryService(session).get(team_id, runs=runs)
    if data is None:
        raise HTTPException(404, f"no standings for team {team_id}")
    return cast(dict[str, Any], _camel(asdict(data)))


@router.get("/league/model", summary="Qué modela la simulación y qué no")
async def league_model() -> dict[str, Any]:
    return model_info()


@router.get(
    "/teams/{team_id}/league/comparison", summary="Comparativa de TSI contra toda la serie"
)
async def league_comparison(
    team_id: int,
    log_tsi: bool = False,
    exclude_keeper: bool = True,
    top11: bool = False,
    session: AsyncSession = Depends(get_session),
    user: m.User = Depends(get_current_user),
) -> dict[str, Any]:
    """No solo el próximo rival: dónde queda tu plantilla frente a TODA la
    serie. Mismo límite que la ficha de un rival — TSI real vía `players.xml`
    de cada equipo, nombres y skills exactas ocultos por CHPP para quien no
    es tuyo — pero agregado a las 7-8 escuadras de la liga en vez de una.
    Nada de esto se persiste: se pide en vivo cada vez."""
    team = await session.get(m.Team, team_id)
    if team is None:
        raise HTTPException(404, f"team {team_id} not found")
    if team.owner_user_id != user.id:
        raise HTTPException(403, "este equipo no está conectado a tu sesión")

    own_standing = await session.scalar(
        select(m.Standing)
        .where(m.Standing.team_ht_id == team.ht_team_id)
        .order_by(m.Standing.captured_at.desc(), m.Standing.match_round.desc())
        .limit(1)
    )
    if own_standing is None:
        raise HTTPException(409, "sincroniza la clasificación de tu liga primero")

    series_teams = (
        await session.execute(
            select(m.Standing).where(
                m.Standing.series_ht_id == own_standing.series_ht_id,
                m.Standing.season == own_standing.season,
                m.Standing.match_round == own_standing.match_round,
            )
        )
    ).scalars().all()
    rivals = [s for s in series_teams if s.team_ht_id != team.ht_team_id]

    token_row = await session.scalar(select(m.CHPPToken).where(m.CHPPToken.user_id == user.id))
    if token_row is None or token_row.status != "active":
        raise HTTPException(409, "reconecta con Hattrick: no hay un token activo")

    own_players, _ = await roster(session, team_id)

    client = CHPPClient(
        decrypt_token(token_row.oauth_token_enc), decrypt_token(token_row.oauth_secret_enc)
    )
    league_rosters: list[tuple[str, int, list[dict[str, Any]]]] = []
    try:
        for st in rivals:
            payload = await client.fetch(
                "players", version=FILE_VERSIONS["players"], teamID=st.team_ht_id
            )
            league_rosters.append((st.team_name, st.team_ht_id, payload["players"]))
    except CHPPAuthError as exc:
        raise HTTPException(401, "Hattrick revocó el acceso: reconecta tu cuenta") from exc
    except CHPPUnavailableError as exc:
        raise HTTPException(503, f"Hattrick no responde: {exc}") from exc
    finally:
        await client.aclose()

    own_for_metrics = own_players
    if top11:
        try:
            best_xi_ids = {
                a.player["ht_player_id"] for a in best_formation(own_players)[0].assignments
            }
            own_for_metrics = [p for p in own_players if p["ht_player_id"] in best_xi_ids]
        except ValueError:
            pass  # plantilla insuficiente para armar un once: se compara la plantilla completa

    def top_n(players: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(players, key=lambda p: -p["tsi"])[:11] if top11 else players

    def summarize(
        name: str, ht_id: int, players: list[dict[str, Any]], is_own: bool
    ) -> dict[str, Any]:
        ps = top_n(players)
        total = sum(p["tsi"] for p in ps)
        return {
            "teamHtId": ht_id, "teamName": name, "totalTsi": total,
            "avgTsi": round(total / len(ps), 1) if ps else 0.0,
            "playerCount": len(ps), "isOwn": is_own,
        }

    summaries = [summarize(team.name, team.ht_team_id, own_for_metrics, True)]
    summaries += [
        summarize(name, ht_id, players, False) for name, ht_id, players in league_rosters
    ]
    summaries.sort(key=lambda s: -s["totalTsi"])
    for i, s in enumerate(summaries):
        s["rank"] = i + 1
    own_rank = next(s["rank"] for s in summaries if s["isOwn"])

    # Para el propio equipo sabemos si es portero (skills reales); para el
    # resto de la liga no hay forma de saberlo sin adivinar, así que el
    # toggle solo actúa sobre lo que sí se puede verificar.
    own_for_tsi = [
        {
            "tsi": p["tsi"],
            "position_code": 1 if best_position(p).position == "keeper" else 2,
        }
        for p in own_for_metrics
    ]
    league_for_tsi = [
        {"tsi": p["tsi"], "position_code": None}
        for _, _, players in league_rosters
        for p in top_n(players)
    ]
    histogram = tsi_kde_comparison(
        own_for_tsi, league_for_tsi, log_transform=log_tsi, exclude_keeper=exclude_keeper
    )

    return cast(dict[str, Any], _camel({
        "series_name": team.series_name or "",
        "teams_in_series": len(summaries),
        "own_rank": own_rank,
        "ranking": summaries,
        "tsi_histogram": {
            "grid": histogram.grid,
            "own_density": histogram.own_density,
            "rival_density": histogram.rival_density,
            "own_values": histogram.own_values,
            "rival_values": histogram.rival_values,
            "log_transform": histogram.log_transform,
            "excluded_keeper": histogram.excluded_keeper,
            "top11": top11,
        },
        "caveats": [
            "El TSI de cada rival es real (dato público de Hattrick); sus habilidades exactas "
            "y su alineación real están ocultas por CHPP para cualquier equipo que no sea "
            "el tuyo — «excluir arquero» solo se aplica con certeza a tu plantilla.",
            "Nada de esto se sincroniza ni se guarda: se pide en vivo cada vez que se abre "
            "esta comparativa.",
        ],
    }))
