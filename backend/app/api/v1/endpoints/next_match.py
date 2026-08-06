"""Análisis de decisión para el próximo partido del equipo conectado."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.v1.endpoints.analysis import roster
from app.api.v1.endpoints.arena import _camel
from app.api.v1.endpoints.rivals import fetch_rival_matches_and_lineups
from app.domain.engines.lineup_optimizer import best_formation
from app.domain.engines.next_match_analysis import direct_condition_summary, probable_starters
from app.domain.value_objects.ht_constants import (
    FRIENDLY_MATCH_TYPES,
    NON_OFFICIAL_MATCH_TYPES,
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

    own_condition_players = [
        {
            "line": "Tu once recomendado",
            "stamina": int(player["stamina"]),
            "form": int(player["form"]),
            "experience": int(player["experience"]),
        }
        for player in own_xi
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
            "condition": own_condition,
        },
        "data_freshness": freshness,
        "notes": [
            "Forma, resistencia y experiencia del rival se leen en vivo desde players.xml 2.8. Si CHPP omite alguno, se declara ausente: nunca se convierte en cero.",
            "El once rival es una proyección y puede cambiar hasta que el partido se juegue. Se basa solo en reportes públicos de sus últimos cinco partidos oficiales terminados.",
            "Los datos del rival no se almacenan como historial; se descartan al terminar esta consulta.",
        ],
    })
