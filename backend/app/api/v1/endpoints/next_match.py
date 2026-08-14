"""Análisis de decisión para el próximo partido del equipo conectado."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.v1.endpoints.analysis import roster
from app.api.v1.endpoints.arena import _camel
from app.api.v1.endpoints.rivals import _submitted_players, fetch_rival_matches_and_lineups
from app.domain.engines.lineup_optimizer import best_formation
from app.domain.engines.next_match_analysis import direct_condition_summary, probable_starters
from app.domain.value_objects.ht_constants import (
    FRIENDLY_MATCH_TYPES,
    NON_OFFICIAL_MATCH_TYPES,
    match_behaviour_name,
    match_role_name,
    match_type_name,
)
from app.infrastructure.chpp.client import CHPPAuthError, CHPPClient, CHPPUnavailableError
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.infrastructure.security.tokens import decrypt_token


router = APIRouter()


async def _next_match(session: AsyncSession, ht_team_id: int) -> m.Match | None:
    # Mantener un margen pequeño evita esconder un partido que aún no ha sido
    # actualizado por CHPP justo después de la hora programada.
    statement = (
        select(m.Match)
        .where(
            (m.Match.home_team_ht_id == ht_team_id) | (m.Match.away_team_ht_id == ht_team_id),
            ~m.Match.status.ilike("finished"),
            m.Match.match_type.not_in(NON_OFFICIAL_MATCH_TYPES | FRIENDLY_MATCH_TYPES),
            m.Match.played_at >= datetime.now(UTC) - timedelta(hours=4),
        )
        .order_by(m.Match.played_at.asc())
        .limit(1)
    )
    return await session.scalar(statement)


@router.get("/teams/{team_id}/next-match/analysis", summary="Análisis del próximo partido")
async def next_match_analysis(
    team_id: int,
    session: AsyncSession = Depends(get_session),
    user: m.User = Depends(get_current_user),
) -> dict[str, Any]:
    """Une la próxima cita sincronizada con lecturas vivas del rival.

    Los datos ajenos viven únicamente durante esta petición. La aplicación no
    guarda una serie temporal de otro equipo: usa su estado actual público y
    los reportes públicos de sus cinco partidos oficiales terminados.
    """
    own_players, team = await roster(session, team_id)
    if team.owner_user_id != user.id:
        raise HTTPException(403, "este equipo no está conectado a tu sesión")

    upcoming = await _next_match(session, team.ht_team_id)
    if upcoming is None:
        return {
            "match": None,
            "message": "No hay un próximo partido sincronizado. Ejecuta Sync para actualizar el calendario.",
        }

    is_home = upcoming.home_team_ht_id == team.ht_team_id
    rival_ht_team_id = upcoming.away_team_ht_id if is_home else upcoming.home_team_ht_id
    rival_name = upcoming.away_team_name if is_home else upcoming.home_team_name
    token_row = await session.scalar(select(m.CHPPToken).where(m.CHPPToken.user_id == user.id))
    if token_row is None or token_row.status != "active":
        raise HTTPException(409, "reconecta con Hattrick: no hay un token activo")

    client = CHPPClient(
        decrypt_token(token_row.oauth_token_enc), decrypt_token(token_row.oauth_secret_enc)
    )
    try:
        # Comparte el mismo pipeline en vivo (players.xml + matches.xml +
        # matchlineup.xml) y el mismo filtro de tipo de partido que la ficha
        # completa de rival — antes esta vista tenía su propia copia, más
        # vieja, que todavía dejaba pasar partidos de Selección nacional
        # como "oficiales". Solo competitivos, sin amistosos (mismo alcance
        # que tenía antes esta vista).
        rival_data = await fetch_rival_matches_and_lineups(
            client, rival_ht_team_id, include_competitive=True, include_friendlies=False,
        )
    except CHPPAuthError as exc:
        raise HTTPException(401, "Hattrick revocó el acceso: reconecta tu cuenta") from exc
    except CHPPUnavailableError as exc:
        raise HTTPException(503, f"Hattrick no responde: {exc}") from exc
    finally:
        await client.aclose()

    rival_players = rival_data.players_raw
    rival_matches = rival_data.matches
    rivals = probable_starters(rival_players, rival_data.appearances)
    submitted_players = _submitted_players(upcoming, own_players)
    submitted_orders: dict[str, Any] | None = None
    if submitted_players and upcoming.submitted_lineup_json:
        by_id = {int(player["ht_player_id"]): player for player in submitted_players}
        try:
            submitted_rows = json.loads(upcoming.submitted_lineup_json)
        except (TypeError, ValueError):
            submitted_rows = []
        submitted_lineup = []
        for row in submitted_rows:
            if not isinstance(row, dict):
                continue
            player = by_id.get(int(row.get("ht_player_id", 0)))
            if player is None:
                continue
            role_id = int(row.get("role_id", 0))
            behaviour = int(row.get("behaviour", 0))
            submitted_lineup.append({
                "ht_player_id": player["ht_player_id"],
                "name": player["name"],
                "position": match_role_name(role_id),
                "role_id": role_id,
                "behaviour": behaviour,
                "behaviour_label": match_behaviour_name(behaviour),
                "stamina": player["stamina"],
                "form": player["form"],
                "experience": player["experience"],
            })
        submitted_orders = {
            "match_id": upcoming.ht_match_id,
            "captured_at": upcoming.submitted_orders_captured_at,
            "ratings_captured_at": upcoming.submitted_ratings_captured_at,
            "tactic_type": upcoming.submitted_tactic_type,
            "tactic_skill": upcoming.submitted_tactic_skill,
            "ratings": {
                "midfield": upcoming.submitted_rating_midfield,
                "right_def": upcoming.submitted_rating_right_def,
                "central_def": upcoming.submitted_rating_central_def,
                "left_def": upcoming.submitted_rating_left_def,
                "right_att": upcoming.submitted_rating_right_att,
                "central_att": upcoming.submitted_rating_central_att,
                "left_att": upcoming.submitted_rating_left_att,
            },
            "lineup": submitted_lineup,
        }
    try:
        own_lineup, own_ranking = best_formation(own_players)
        own_xi = [
            {
                "ht_player_id": assignment.player["ht_player_id"],
                "name": assignment.player["name"],
                "position": assignment.label,
                "stamina": assignment.player["stamina"],
                "form": assignment.player["form"],
                "experience": assignment.player["experience"],
                "rating": assignment.rating,
            }
            for assignment in own_lineup.assignments
        ]
        own_formation: dict[str, Any] | None = {
            "formation": own_lineup.formation,
            "total_rating": own_lineup.total_rating,
            "ranking": own_ranking,
            "lineup": own_xi,
        }
    except ValueError:
        own_formation = None
        own_xi = own_players[:11]

    condition_reference = submitted_players or own_xi
    own_condition_players = [
        {
            "line": (
                "Tu alineación enviada" if submitted_players else "Tu once recomendado"
            ),
            "stamina": int(player["stamina"]),
            "form": int(player["form"]),
            "experience": int(player["experience"]),
        }
        for player in condition_reference
    ]
    rival_condition = direct_condition_summary(rivals)
    own_condition = direct_condition_summary(own_condition_players)
    freshness = datetime.now(UTC).isoformat()

    return _camel({
        "match": {
            "ht_match_id": upcoming.ht_match_id,
            "date": upcoming.played_at,
            "match_type": upcoming.match_type,
            "match_type_label": match_type_name(upcoming.match_type),
            "is_home": is_home,
            "home": upcoming.home_team_name,
            "away": upcoming.away_team_name,
            "rival_ht_team_id": rival_ht_team_id,
            "rival_name": rival_name,
        },
        "rival": {
            "ht_team_id": rival_ht_team_id,
            "name": rival_name,
            "probable_lineup": rivals,
            "condition": rival_condition,
            "matches_analysed": len(rival_matches),
            "selection_method": (
                "Once probable: titulares más recurrentes en sus últimos partidos oficiales; "
                "los atributos que CHPP expone son lecturas actuales de players.xml."
            ),
        },
        "own": {
            "formation": own_formation,
            "submitted_orders": submitted_orders,
            "condition_source": (
                "submitted_orders" if submitted_players else "recommended_lineup"
            ),
            "condition": own_condition,
        },
        "data_freshness": freshness,
        "notes": [
            "Forma, resistencia y experiencia del rival se leen en vivo desde players.xml 2.8. Si CHPP omite alguno, se declara ausente: nunca se convierte en cero.",
            (
                "Tu condición usa la alineación realmente enviada; sus ratings son la predicción oficial CHPP al minuto 0."
                if submitted_players else
                "Aún no hay una alineación enviada disponible: tu condición usa temporalmente el once recomendado por Hattrick Lens."
            ),
            "El once rival es una proyección y puede cambiar hasta que el partido se juegue. Se basa solo en reportes públicos de sus últimos cinco partidos oficiales terminados.",
            "Los datos del rival no se almacenan como historial; se descartan al terminar esta consulta.",
        ],
    })
