"""Liga y predicciones. HL-080, HL-083, HL-090, HL-091, HL-094."""

import time
from dataclasses import asdict
from typing import Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_team_owner
from app.api.rate_limit import limite
from app.api.v1.endpoints.analysis import roster
from app.api.v1.endpoints.arena import _camel
from app.application.commands.sync_team import FILE_VERSIONS, MATCHLINEUP_ROLE_VERSION
from app.application.queries.league import LEAGUE_MATCH_TYPE, LeagueQueryService
from app.domain.engines.lineup_optimizer import best_formation
from app.domain.engines.position_engine import best_position
from app.domain.engines.rival_scouting import tsi_kde_comparison
from app.domain.engines.season_simulator import model_info
from app.domain.engines.team_of_the_week import (
    FORMATIONS,
    MAX_CENTRAL_DEFENDERS,
    MAX_INNER_MIDFIELDERS,
    SLOT_LABELS,
    LineupPlayer,
    best_team,
    line_splits,
    resolve_split,
)
from app.domain.value_objects.ht_constants import match_role_name
from app.infrastructure.chpp.client import CHPPAuthError, CHPPClient, CHPPUnavailableError
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.infrastructure.security.tokens import decrypt_token

router = APIRouter()

# 2026-08-05, pedido explícitamente: abrir la Comparativa de liga (o mover
# cualquiera de sus 3 toggles) pedía las plantillas de los 7-8 rivales de la
# serie a CHPP, en secuencia, cada vez — aunque ninguno de los toggles
# (log_tsi, top11) necesite un dato nuevo de Hattrick: son
# post-proceso puro sobre el mismo TSI ya descargado. Cache en memoria (sin
# Redis en desarrollo — mismo patrón que `_pending` en auth_chpp.py) de la
# plantilla propia + rivales, keyed por la jornada realmente sincronizada
# (cambia sola cuando hay clasificación nueva). TTL corto: es "no repitas
# la llamada mientras el usuario juega con los controles", no un caché de
# verdad — datos más viejos que esto se sienten desactualizados.
_ROSTER_CACHE_TTL_SECONDS = 300
_roster_cache: dict[tuple[int, int, int, int], tuple[float, list[Any]]] = {}

# "Última posición en partido oficial" del jugador de mayor TSI de cada
# equipo — pedido explícitamente 2026-08-08. Es una llamada CHPP nueva
# (playerdetails.xml) por equipo, no cubierta por `_roster_cache` (que solo
# trae TSI vía players.xml) — TTL más largo porque LastMatch de un jugador
# cambia como mucho una vez por semana, no cada vez que se abre la página.
_LAST_POSITION_CACHE_TTL_SECONDS = 1800
_last_position_cache: dict[int, tuple[float, str | None]] = {}

# Alineaciones reales (matchlineup.xml) por partido — pedido explícitamente
# 2026-08-08 para "Mejor alineación". Un partido ya finalizado es un hecho
# público permanente (nunca cambia), así que el TTL es largo: no hace falta
# volver a pedirlo salvo que el proceso se reinicie.
_LINEUP_CACHE_TTL_SECONDS = 3600
# MATCHLINEUP_ROLE_VERSION vive en sync_team.py (compartida con el
# refresco de "Última semana" en Posiciones) — ver su comentario ahí para
# por qué es una versión distinta a MATCHLINEUP_POSITION_CODE_VERSION de
# rivals.py, para el mismo fichero.
_lineup_cache: dict[tuple[int, int], tuple[float, list[dict[str, Any]]]] = {}


@router.get(
    "/teams/{team_id}/league",
    summary="Clasificación, calendario y simulación",
    dependencies=[Depends(require_team_owner)],
)
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
    "/teams/{team_id}/league/comparison",
    summary="Comparativa de TSI contra toda la serie",
    dependencies=[
        Depends(require_team_owner),
        Depends(limite("rivales", 30)),
    ],
)
async def league_comparison(
    team_id: int,
    log_tsi: bool = False,
    top11: bool = False,
    session: AsyncSession = Depends(get_session),
    user: m.User = Depends(get_current_user),
) -> dict[str, Any]:
    """No solo el próximo rival: dónde queda tu plantilla frente a TODA la
    serie. Mismo límite que la ficha de un rival — TSI real vía `players.xml`
    de cada equipo, nombres y skills exactas ocultos por CHPP para quien no
    es tuyo — pero agregado a las 7-8 escuadras de la liga en vez de una.
    Nada de esto se guarda en la base de datos: se pide a CHPP la primera
    vez y se cachea en memoria un rato corto (`_ROSTER_CACHE_TTL_SECONDS`)
    para que mover los controles (Log/TSI, excluir portero, top11) no
    vuelva a consultar a los 7-8 clubes — esos tres son post-proceso puro
    sobre el mismo TSI ya descargado."""
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
        (
            await session.execute(
                select(m.Standing).where(
                    m.Standing.series_ht_id == own_standing.series_ht_id,
                    m.Standing.season == own_standing.season,
                    m.Standing.match_round == own_standing.match_round,
                )
            )
        )
        .scalars()
        .all()
    )
    rivals = [s for s in series_teams if s.team_ht_id != team.ht_team_id]

    token_row = await session.scalar(select(m.CHPPToken).where(m.CHPPToken.user_id == user.id))
    if token_row is None or token_row.status != "active":
        raise HTTPException(409, "reconecta con Hattrick: no hay un token activo")

    # own_players es una consulta local (DB, sin CHPP) — barata, se pide
    # fresca siempre. Lo caro son las plantillas rivales: eso sí se cachea.
    own_players, _ = await roster(session, team_id)

    cache_key = (
        team_id,
        own_standing.series_ht_id,
        own_standing.season,
        own_standing.match_round,
    )
    cached = _roster_cache.get(cache_key)
    now = time.monotonic()
    if cached is not None and now - cached[0] < _ROSTER_CACHE_TTL_SECONDS:
        league_rosters: list[tuple[str, int, list[dict[str, Any]]]] = cached[1]
    else:
        client = CHPPClient(
            decrypt_token(token_row.oauth_token_enc), decrypt_token(token_row.oauth_secret_enc)
        )
        league_rosters = []
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
        _roster_cache[cache_key] = (now, league_rosters)

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
        # Jugador de mayor TSI, forma y resistencia medias — pedido
        # explícitamente 2026-08-08. Forma/resistencia solo promedian
        # jugadores donde CHPP de verdad las mostró (`*_is_read`): para un
        # rival, un dato ausente no es un 0 real, es "no se sabe".
        top_player = max(ps, key=lambda p: p["tsi"]) if ps else None
        readable_form = [p["form"] for p in ps if p.get("form_is_read")]
        readable_stamina = [p["stamina"] for p in ps if p.get("stamina_is_read")]
        return {
            "teamHtId": ht_id,
            "teamName": name,
            "totalTsi": total,
            "avgTsi": round(total / len(ps), 1) if ps else 0.0,
            "playerCount": len(ps),
            "isOwn": is_own,
            "topPlayerId": top_player["ht_player_id"] if top_player else None,
            "topPlayerName": (
                f"{top_player['first_name']} {top_player['last_name']}".strip()
                if top_player
                else None
            ),
            "topPlayerTsi": top_player["tsi"] if top_player else None,
            "avgForm": round(sum(readable_form) / len(readable_form), 1) if readable_form else None,
            "avgStamina": (
                round(sum(readable_stamina) / len(readable_stamina), 1)
                if readable_stamina
                else None
            ),
        }

    summaries = [summarize(team.name, team.ht_team_id, own_for_metrics, True)]
    summaries += [summarize(name, ht_id, players, False) for name, ht_id, players in league_rosters]
    summaries.sort(key=lambda s: -s["totalTsi"])
    for i, s in enumerate(summaries):
        s["rank"] = i + 1
    own_rank = next(s["rank"] for s in summaries if s["isOwn"])

    # "Última posición en partido oficial" del jugador de mayor TSI de cada
    # equipo — una llamada playerdetails.xml aparte, solo para ese jugador
    # (no toda la plantilla). Cliente propio: el de arriba puede no existir
    # si `league_rosters` vino del caché.
    position_client = CHPPClient(
        decrypt_token(token_row.oauth_token_enc), decrypt_token(token_row.oauth_secret_enc)
    )
    try:
        for s in summaries:
            pid = s.pop("topPlayerId")
            if pid is None:
                s["topPlayerLastPosition"] = None
                continue
            cached_pos = _last_position_cache.get(pid)
            now2 = time.monotonic()
            if cached_pos is not None and now2 - cached_pos[0] < _LAST_POSITION_CACHE_TTL_SECONDS:
                s["topPlayerLastPosition"] = cached_pos[1]
                continue
            try:
                # includeMatchInfo=true es obligatorio para que CHPP rellene
                # `LastMatch` — verificado en vivo 2026-08-09: la misma
                # versión (3.2) sin este parámetro nunca lo trae, con
                # cualquier jugador. Sin esto, "Última posición" salía
                # siempre vacía para todos los rivales.
                payload = await position_client.fetch(
                    "playerdetails",
                    version=FILE_VERSIONS["playerdetails"],
                    playerID=pid,
                    includeMatchInfo="true",
                )
                last_match = payload.get("last_match")
                pos_name = match_role_name(last_match["position_code"]) if last_match else None
            except (CHPPAuthError, CHPPUnavailableError):
                pos_name = None
            _last_position_cache[pid] = (now2, pos_name)
            s["topPlayerLastPosition"] = pos_name
    finally:
        await position_client.aclose()

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
    histogram = tsi_kde_comparison(own_for_tsi, league_for_tsi, log_transform=log_tsi)

    return cast(
        dict[str, Any],
        _camel(
            {
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
                    "top11": top11,
                },
                "caveats": [
                    "El TSI de cada rival es real (dato público de Hattrick); sus habilidades exactas "  # noqa: E501
                    "y su alineación real están ocultas por CHPP para cualquier equipo que no sea "
                    "el tuyo, «excluir nuestro arquero» solo se aplica con certeza a tu "
                    "plantilla, nunca a los rivales.",
                    "Nada de esto se sincroniza ni se guarda: se pide en vivo cada vez que se abre "
                    "esta comparativa.",
                ],
            }
        ),
    )


@router.get(
    "/teams/{team_id}/league/team-of-the-week",
    summary="Mejor alineación real de la jornada o de la temporada",
    dependencies=[
        Depends(require_team_owner),
        Depends(limite("rivales", 30)),
    ],
)
async def team_of_the_week(
    team_id: int,
    scope: Literal["week", "season"] = "week",
    # `str` y no un `Literal` con las formaciones escritas a mano: esa lista
    # se quedó atrás al añadir 5-5-0, 5-2-3 y 2-5-3 al catálogo (2026-08-19) y
    # el selector ofrecía formaciones que la API rechazaba con un 422. La
    # validación buena es contra la tabla, que es la única fuente.
    formation: str = "4-4-2",
    # Los dos repartos de Hattrick Control: cuántos de la línea juegan por
    # dentro. El resto va a las bandas. `None` = el reparto propio de la
    # formación.
    central_defenders: int | None = None,
    inner_midfielders: int | None = None,
    match_round_param: int | None = Query(default=None, alias="round"),
    session: AsyncSession = Depends(get_session),
    user: m.User = Depends(get_current_user),
) -> dict[str, Any]:
    """Equipo ideal calculado con el rating REAL de cada titular
    (`matchlineup.xml` — público incluso para un rival: un partido ya
    finalizado es un hecho permanente, no el histórico de una cuenta ajena).
    "week" = una jornada concreta (la que pida `round`, o la última con
    TODOS sus partidos ya jugados si se omite — igual que el selector de
    Jornada de Hattrick Control); "season" = todas las jornadas completas
    sincronizadas hasta hoy, ignora `round`. `formation` solo cambia
    cuántos cupos de defensa/medio/delantero se muestran — no altera qué
    partidos se leen. Nunca se guarda: se recalcula cada vez, con caché en
    memoria por partido (los resultados de un partido terminado no
    cambian)."""
    if formation not in FORMATIONS:
        raise HTTPException(
            422,
            f"formación desconocida: {formation}. Las disponibles son {', '.join(FORMATIONS)}",
        )

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

    teams_in_series = len(
        (
            await session.execute(
                select(m.Standing.team_ht_id).where(
                    m.Standing.series_ht_id == own_standing.series_ht_id,
                    m.Standing.season == own_standing.season,
                    m.Standing.match_round == own_standing.match_round,
                )
            )
        ).all()
    )

    matches = list(
        (
            await session.execute(
                select(m.Match).where(
                    m.Match.match_type == LEAGUE_MATCH_TYPE,
                    m.Match.series_ht_id == own_standing.series_ht_id,
                    m.Match.home_goals >= 0,
                    m.Match.away_goals >= 0,
                )
            )
        ).scalars()
    )

    # Solo cuentan jornadas TERMINADAS (todos sus partidos jugados) — igual
    # que `_history_from_matches`: una jornada a medias no es un rango
    # comparable de "mejor alineación".
    by_round: dict[int, list[m.Match]] = {}
    for mt in matches:
        if mt.match_round is not None:
            by_round.setdefault(mt.match_round, []).append(mt)
    complete_rounds = sorted(
        rnd for rnd, mts in by_round.items() if teams_in_series and len(mts) >= teams_in_series // 2
    )

    if scope == "week":
        target_round = (
            match_round_param
            if match_round_param in complete_rounds
            else (complete_rounds[-1] if complete_rounds else None)
        )
        scoped_matches = by_round.get(target_round, []) if target_round is not None else []
        rounds_covered = 1 if target_round is not None else 0
    else:
        target_round = None
        scoped_matches = [mt for rnd in complete_rounds for mt in by_round[rnd]]
        rounds_covered = len(complete_rounds)

    token_row = await session.scalar(select(m.CHPPToken).where(m.CHPPToken.user_id == user.id))
    if token_row is None or token_row.status != "active":
        raise HTTPException(409, "reconecta con Hattrick: no hay un token activo")

    client = CHPPClient(
        decrypt_token(token_row.oauth_token_enc), decrypt_token(token_row.oauth_secret_enc)
    )
    lineup_players: list[LineupPlayer] = []
    lineups_found = 0
    lineups_expected = len(scoped_matches) * 2
    try:
        for match in scoped_matches:
            for team_ht_id, team_name in (
                (match.home_team_ht_id, match.home_team_name),
                (match.away_team_ht_id, match.away_team_name),
            ):
                cache_key = (match.ht_match_id, team_ht_id)
                cached_lineup = _lineup_cache.get(cache_key)
                now = time.monotonic()
                if cached_lineup is not None and now - cached_lineup[0] < _LINEUP_CACHE_TTL_SECONDS:
                    players_payload = cached_lineup[1]
                else:
                    try:
                        # version=2.1 explícito (ver docstring de
                        # team_of_the_week.py y del parser): sin esto,
                        # RoleID es un índice sin significado y ningún
                        # suplente que entrara a mitad de partido tiene
                        # posición fiable — confirmado en vivo 2026-08-09.
                        payload = await client.fetch(
                            "matchlineup",
                            version=MATCHLINEUP_ROLE_VERSION,
                            matchID=match.ht_match_id,
                            teamID=team_ht_id,
                        )
                        players_payload = payload.get("players", [])
                    except (CHPPAuthError, CHPPUnavailableError):
                        players_payload = []
                    _lineup_cache[cache_key] = (now, players_payload)
                if players_payload:
                    lineups_found += 1
                # matchlineup.xml repite entradas especiales del mismo
                # titular (capitán, balón parado) — siempre DESPUÉS de su
                # fila real en el XML, así que quedarse con la primera
                # aparición por jugador basta (como máximo una fila por
                # partido y jugador).
                seen: set[int] = set()
                for p in players_payload:
                    if p["ht_player_id"] in seen:
                        continue
                    seen.add(p["ht_player_id"])
                    lineup_players.append(
                        LineupPlayer(
                            ht_player_id=p["ht_player_id"],
                            name=p["name"],
                            team_ht_id=team_ht_id,
                            team_name=team_name,
                            role_id=p["role_id"],
                            rating_stars=p["rating_stars"],
                            ht_match_id=match.ht_match_id,
                        )
                    )
    finally:
        await client.aclose()

    centrales, interiores = resolve_split(formation, central_defenders, inner_midfielders)
    slots = best_team(
        lineup_players,
        formation=formation,
        central_defenders=centrales,
        inner_midfielders=interiores,
    )
    total_stars = round(sum(p.rating_stars for group in slots.values() for p in group), 1)

    return cast(
        dict[str, Any],
        _camel(
            {
                "scope": scope,
                "formation": formation,
                "formations": list(FORMATIONS.keys()),
                "central_defenders": centrales,
                "inner_midfielders": interiores,
                # Las opciones legales de cada selector para ESTA formación: una línea
                # de cinco solo admite 3 por dentro, y ahí el radio sale único.
                "central_defender_options": line_splits(
                    FORMATIONS[formation][0], MAX_CENTRAL_DEFENDERS
                ),
                "inner_midfielder_options": line_splits(
                    FORMATIONS[formation][1], MAX_INNER_MIDFIELDERS
                ),
                "match_round": target_round,
                "available_rounds": complete_rounds,
                "rounds_covered": rounds_covered,
                "lineups_found": lineups_found,
                "lineups_expected": lineups_expected,
                "slot_labels": SLOT_LABELS,
                "positions": {key: [asdict(p) for p in players] for key, players in slots.items()},
                "total_stars": total_stars,
                "caveats": [
                    "Rating real de cada titular, público para cualquier partido ya terminado "
                    "(matchlineup.xml), un mismo jugador solo cuenta con su mejor actuación del rango.",  # noqa: E501
                    '"De la temporada" pesa cada jornada terminada por igual, sin importar cuándo se '  # noqa: E501
                    "sincronizó el calendario, puede tardar en reflejar la última jornada si "
                    "leaguefixtures.xml todavía no trae su marcador.",
                ],
            }
        ),
    )
