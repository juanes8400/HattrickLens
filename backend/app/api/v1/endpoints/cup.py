"""Centro de decisión de Copa.

Los hechos (estado, ronda, calendario, asistencia e historial) se mantienen
separados de las proyecciones (probabilidad, taquilla futura y escenarios).
La clasificación usa las dos dimensiones oficiales: CupLeagueLevel distingue
Nacional/Divisional y CupLevel distingue Principal/Desafío/Consuelo.
"""
import json
from statistics import median
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_team_owner
from app.api.v1.endpoints.arena import _camel
from app.application.queries.weekly import season_for_datetime
from app.domain.engines.arena_engine import ArenaCapacity, Attendance, analyse_match
from app.domain.engines.match_analysis import hatstats
from app.domain.value_objects.ht_constants import MATCH_TYPE_LEAGUE
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session

router = APIRouter()

CUP_MATCH_TYPE = 3
CHALLENGE_NAMES = {1: "Esmeralda", 2: "Rubí", 3: "Zafiro"}

# Importes canónicos en SEK. El manual los presenta convertidos a la moneda
# del usuario; Team.currency_rate hace la misma conversión que Economía.
# rounds_from_title: 1=Final, 2=Semifinal, 3=Cuartos, etc.
CUP_PRIZES_SEK: dict[str, list[tuple[str, int, int]]] = {
    "national_main": [
        ("Ronda de 512", 1_200_000, 9), ("Ronda de 256", 1_400_000, 8),
        ("Ronda de 128", 1_600_000, 7), ("Ronda de 64", 1_800_000, 6),
        ("Ronda de 32", 2_000_000, 5), ("Octavos", 2_500_000, 4),
        ("Cuartos", 5_000_000, 3), ("Semifinal", 7_500_000, 2),
        ("Subcampeón", 10_000_000, 1), ("Campeón", 15_000_000, 0),
    ],
    "national_challenge": [
        ("Octavos", 250_000, 4), ("Cuartos", 500_000, 3),
        ("Semifinal", 1_000_000, 2), ("Subcampeón", 1_500_000, 1),
        ("Campeón", 3_000_000, 0),
    ],
    "divisional_main": [
        ("Octavos", 250_000, 4), ("Cuartos", 500_000, 3),
        ("Semifinal", 1_000_000, 2), ("Subcampeón", 1_500_000, 1),
        ("Campeón", 3_000_000, 0),
    ],
    "divisional_challenge": [
        ("Cuartos", 250_000, 3), ("Semifinal", 500_000, 2),
        ("Subcampeón", 1_000_000, 1), ("Campeón", 1_500_000, 0),
    ],
}


def _classification(
    cup_league_level: int | None,
    cup_level: int | None,
    cup_level_index: int | None,
) -> dict[str, str | None]:
    if cup_level is None:
        return {"scope": None, "scope_label": "Sin clasificar", "tier": None,
                "tier_label": "Sin clasificar", "prize_key": None}
    scope = "national" if (cup_league_level or 0) == 0 else "divisional"
    scope_label = (
        "Nacional" if scope == "national"
        else f"Divisional · nivel {cup_league_level}"
    )
    if cup_level == 1:
        tier, tier_label = "main", "Principal"
    elif cup_level == 2:
        tier = "challenge"
        tier_label = f"Desafío {CHALLENGE_NAMES.get(cup_level_index or 0, '')}".strip()
    elif cup_level == 3:
        tier, tier_label = "consolation", "Consuelo"
    else:
        tier, tier_label = "other", f"Nivel {cup_level}"
    prize_key = f"{scope}_{tier}" if tier in {"main", "challenge"} else None
    return {
        "scope": scope, "scope_label": scope_label,
        "tier": tier, "tier_label": tier_label, "prize_key": prize_key,
    }


def _stage_label(rounds_left: int | None) -> str | None:
    if rounds_left is None or rounds_left < 0:
        return None
    labels = {0: "Campeón", 1: "Final", 2: "Semifinal", 3: "Cuartos", 4: "Octavos"}
    return labels.get(rounds_left, f"Ronda de {2 ** rounds_left}")


def _prize_goal(
    prize_key: str | None,
    rounds_left: int | None,
    rate: float,
    league_system_id: int,
    is_consolation: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    femme_factor = 0.75 if league_system_id == 2 else 1.0

    def conv(amount_sek: int) -> int:
        return int(round(amount_sek * femme_factor / (rate or 1.0)))

    source = CUP_PRIZES_SEK.get(prize_key or "", [])
    table = []
    for stage, amount_sek, from_title in source:
        if rounds_left is None:
            status = "future"
            wins_needed = None
        elif from_title > rounds_left:
            status = "passed"
            wins_needed = 0
        elif from_title == rounds_left:
            status = "current"
            wins_needed = 0
        else:
            status = "future"
            wins_needed = rounds_left - from_title
        table.append({
            "stage": stage, "amount": conv(amount_sek),
            "rounds_from_title": from_title, "status": status,
            "wins_needed": wins_needed, "trophy_only": False,
        })

    if is_consolation:
        table = [{
            "stage": "Campeón", "amount": 0, "rounds_from_title": 0,
            "status": "current" if rounds_left == 0 else "future",
            "wins_needed": rounds_left, "trophy_only": True,
        }]

    current = next((row for row in table if row["status"] == "current"), None)
    future = [row for row in table if row["status"] == "future"]
    next_milestone = max(future, key=lambda row: row["rounds_from_title"], default=None)
    champion = next((row for row in table if row["rounds_from_title"] == 0), None)
    goal = {
        "stage": _stage_label(rounds_left),
        "rounds_left": rounds_left,
        "wins_to_title": rounds_left,
        "secured_amount": current["amount"] if current else 0,
        "next_milestone": next_milestone,
        "title_amount": champion["amount"] if champion else 0,
        "trophy_only": is_consolation,
    }
    return table, goal


def _loss_destination(
    classification: dict[str, str | None],
    cup_league_level: int,
    cup_level_index: int,
    match_round: int | None,
    cups: list[m.WorldCup],
) -> tuple[bool | None, str | None, str]:
    tier = classification["tier"]
    destination_level: int | None = None
    destination_index = 1
    if tier == "main" and match_round in {1, 2, 3, 4, 5, 6}:
        destination_level = 2
        destination_index = 1 if match_round in {1, 6} else 2 if match_round in {2, 5} else 3
    elif tier == "challenge" and match_round == 1 and cup_level_index in {1, 2}:
        destination_level = 3
    elif match_round is None:
        return None, None, "La ruta tras una derrota se conocerá cuando CHPP entregue la ronda oficial."

    if destination_level is None:
        return False, None, "La derrota cerraría la participación de Copa esta temporada."

    row = next((
        cup for cup in cups
        if cup.cup_league_level == cup_league_level
        and cup.cup_level == destination_level
        and cup.cup_level_index == destination_index
    ), None)
    fallback = (
        f"Copa Desafío {CHALLENGE_NAMES[destination_index]}"
        if destination_level == 2 else "Copa de Consuelo"
    )
    name = row.cup_name if row else fallback
    return True, name, f"La derrota trasladaría al equipo a {name}; la temporada de Copa continuaría."


async def _readiness(
    session: AsyncSession,
    team_id: int,
    team_ht_id: int,
    cup_matches: list[m.Match],
    cup_matches_played_this_season: int,
) -> dict[str, Any]:
    latest = (
        select(
            m.PlayerSnapshot.player_id.label("pid"),
            func.max(m.PlayerSnapshot.captured_at).label("mx"),
        )
        .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
        .where(m.Player.team_id == team_id, m.Player.left_team_at.is_(None))
        .group_by(m.PlayerSnapshot.player_id)
        .subquery()
    )
    rows = (
        await session.execute(
            select(m.PlayerSnapshot, m.Player)
            .join(
                latest,
                (m.PlayerSnapshot.player_id == latest.c.pid)
                & (m.PlayerSnapshot.captured_at == latest.c.mx),
            )
            .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
        )
    ).all()
    roster = [(snap, player) for snap, player in rows]
    by_ht_player_id = {player.ht_player_id: (snap, player) for snap, player in roster}

    def lineup_xi(lineup_json: str | None) -> list[tuple[m.PlayerSnapshot, m.Player]] | None:
        if not lineup_json:
            return None
        try:
            submitted = json.loads(lineup_json)
            ids = [
                int(row["ht_player_id"])
                for row in submitted
                if isinstance(row, dict) and row.get("ht_player_id")
            ]
        except (TypeError, ValueError, KeyError):
            return None
        xi = [by_ht_player_id[pid] for pid in ids if pid in by_ht_player_id]
        return xi if len(xi) >= 9 else None

    def opponent_of(mt: m.Match) -> str:
        return mt.away_team_name if mt.home_team_ht_id == team_ht_id else mt.home_team_name

    def penalty_order(
        xi: list[tuple[m.PlayerSnapshot, m.Player]]
    ) -> list[dict[str, Any]]:
        """Los tiradores de ese once, del primero al último.

        2026-08-19, pedido explícito: el orden depende del once que estés
        mirando. Antes salía de TODA la plantilla, así que podía proponer de
        tirador a alguien que ni siquiera está en el campo cuando llegan los
        penaltis.
        """
        filas = []
        for snap, player in xi:
            # Índice transparente para ordenar, no una probabilidad de marcar.
            indice = (
                (snap.set_pieces or 0) * 0.45
                + (snap.scoring or 0) * 0.30
                + snap.experience * 0.20
                + (1.0 if snap.specialty == 1 else 0.0)
            )
            filas.append({
                "ht_player_id": player.ht_player_id,
                "name": f"{player.first_name} {player.last_name}",
                "set_pieces": snap.set_pieces or 0,
                "scoring": snap.scoring or 0,
                "experience": snap.experience,
                "technical": snap.specialty == 1,
                "readiness_index": round(indice, 2),
            })
        filas.sort(key=lambda fila: (-fila["readiness_index"], fila["name"]))
        return filas

    def stamina_summary(xi: list[tuple[m.PlayerSnapshot, m.Player]]) -> dict[str, Any]:
        average_stamina = round(sum(snap.stamina for snap, _ in xi) / len(xi), 1) if xi else None
        # Resistencia (Stamina skill) va de 0 a 9, no de 0 a 20 — esa era la
        # escala equivocada que también arrastraba el "/20" mostrado en el
        # frontend (bug real reportado 2026-08-13).
        stamina_bands = [
            {"label": "Frágil para 120'", "min": 0, "max": 5,
             "count": sum(1 for snap, _ in xi if snap.stamina <= 5)},
            {"label": "Intermedia", "min": 6, "max": 7,
             "count": sum(1 for snap, _ in xi if 6 <= snap.stamina <= 7)},
            {"label": "Preparada", "min": 8, "max": 9,
             "count": sum(1 for snap, _ in xi if snap.stamina >= 8)},
        ]
        return {
            "average_stamina": average_stamina, "stamina_bands": stamina_bands,
            "starters_count": len(xi),
            # Los once que patearían si el partido llega a penaltis con ESTE
            # once en el campo.
            "penalty_candidates": penalty_order(xi),
        }

    top_tsi_xi = sorted(roster, key=lambda row: row[0].tsi, reverse=True)[:11]
    variants: list[dict[str, Any]] = [{
        "mode": "top_tsi", "label": "11 jugadores activos con mayor TSI",
        "source_match_id": None, "source_opponent": None, "source_date": None,
        **stamina_summary(top_tsi_xi),
    }]

    # "Última formación en Copa" solo se ofrece si ya se jugó más de un
    # partido de Copa esta temporada — pedido explícito 2026-08-13: con un
    # solo partido no hay nada distinto que mostrar frente al historial.
    if cup_matches_played_this_season > 1:
        for mt in sorted(
            (x for x in cup_matches if x.status.upper() == "FINISHED"),
            key=lambda x: x.played_at, reverse=True,
        ):
            xi = lineup_xi(mt.submitted_lineup_json)
            if xi:
                variants.append({
                    "mode": "last_cup", "label": "Última formación en Copa",
                    "source_match_id": mt.ht_match_id, "source_opponent": opponent_of(mt),
                    "source_date": mt.played_at.date().isoformat(),
                    **stamina_summary(xi),
                })
                break

    league_candidates = (await session.execute(
        select(m.Match).where(
            ((m.Match.home_team_ht_id == team_ht_id) | (m.Match.away_team_ht_id == team_ht_id)),
            m.Match.match_type == MATCH_TYPE_LEAGUE,
            m.Match.status == "FINISHED",
            m.Match.submitted_lineup_json.is_not(None),
        ).order_by(m.Match.played_at.desc()).limit(5)
    )).scalars().all()
    for mt in league_candidates:
        xi = lineup_xi(mt.submitted_lineup_json)
        if xi:
            variants.append({
                "mode": "last_league", "label": "Última formación en Liga",
                "source_match_id": mt.ht_match_id, "source_opponent": opponent_of(mt),
                "source_date": mt.played_at.date().isoformat(),
                **stamina_summary(xi),
            })
            break

    default_mode = "last_cup" if any(v["mode"] == "last_cup" for v in variants) else "top_tsi"

    best_keeper = max(roster, key=lambda row: row[0].keeper or 0, default=None)
    return {
        "reference_variants": variants,
        "default_mode": default_mode,
        # El orden del once por defecto. Cada variante trae el suyo, y la
        # pantalla usa el de la que esté seleccionada.
        "penalty_candidates": next(
            (v["penalty_candidates"] for v in variants if v["mode"] == default_mode),
            [],
        ),
        "goalkeeper": (
            {
                "ht_player_id": best_keeper[1].ht_player_id,
                "name": f"{best_keeper[1].first_name} {best_keeper[1].last_name}",
                "keeper": best_keeper[0].keeper or 0,
            }
            if best_keeper else None
        ),
        "penalty_method": (
            "Orden orientativo: 45% balón parado, 30% anotación, 20% experiencia "
            "y bonificación técnica. Es un índice comparativo, no una probabilidad."
        ),
    }


async def _cup_economy(
    session: AsyncSession,
    team: m.Team,
    next_match: m.Match | None,
    rounds_left: int | None,
) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(m.StadiumHistory, m.Match)
            .join(m.Match, m.Match.ht_match_id == m.StadiumHistory.ht_match_id)
            .where(m.StadiumHistory.team_id == team.id, m.Match.match_type == CUP_MATCH_TYPE)
            .order_by(m.StadiumHistory.played_at)
        )
    ).all()
    gross_values: list[int] = []
    for stadium, _match in rows:
        real = [
            stadium.capacity_terraces, stadium.capacity_basic,
            stadium.capacity_roof, stadium.capacity_vip,
        ]
        sold = [
            stadium.sold_terraces, stadium.sold_basic,
            stadium.sold_roof, stadium.sold_vip,
        ]
        if all(value is not None and value > 0 for value in real):
            cap_values = [int(value) for value in real if value is not None]
        else:
            cap_values = [max(value, 1) for value in sold]
        report = analyse_match(ArenaCapacity(*cap_values), Attendance(*sold))
        gross_values.append(int(round(report.revenue)))

    observed_gross = sum(gross_values)
    estimated_share = int(round(observed_gross * 2 / 3))
    neutral = rounds_left is not None and 0 < rounds_left <= 6
    next_projection = None
    share_percent = None
    basis = "No hay taquillas propias de Copa suficientes para proyectar el siguiente partido."
    if next_match is not None and gross_values and (next_match.home_team_ht_id == team.ht_team_id or neutral):
        share_percent = 50 if neutral else 67
        next_projection = int(round(median(gross_values) * share_percent / 100))
        basis = (
            f"Mediana de {len(gross_values)} taquilla(s) propia(s) de Copa × "
            f"{share_percent}% de participación."
        )
    elif next_match is not None and next_match.home_team_ht_id != team.ht_team_id:
        basis = "Partido visitante: falta la demanda del estadio rival para una proyección responsable."

    return {
        "currency": team.currency_name or "",
        "observed_home_matches": len(gross_values),
        "observed_gross_gate": observed_gross,
        "estimated_historical_share": estimated_share,
        "next_gate_projection": next_projection,
        "next_share_percent": share_percent,
        "projection_basis": basis,
        "quality_note": (
            "La asistencia es real; la taquilla se deriva de entradas por sector "
            "con los cuatro precios confirmados por el usuario."
        ),
    }


@router.get("/teams/{team_id}/cup", summary="Copa: estado, meta y decisiones",
    dependencies=[Depends(require_team_owner)],
)
async def cup(team_id: int, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    team = await session.get(m.Team, team_id)
    if team is None:
        raise HTTPException(404, f"team {team_id} not found")

    world = None
    cups: list[m.WorldCup] = []
    if team.ht_league_id is not None:
        world = await session.scalar(
            select(m.WorldContext).where(m.WorldContext.ht_league_id == team.ht_league_id)
        )
        cups = list((await session.execute(
            select(m.WorldCup).where(m.WorldCup.ht_league_id == team.ht_league_id)
        )).scalars())
    cup_by_id = {row.ht_cup_id: row for row in cups if row.ht_cup_id}
    current_season = world.season if world is not None else None

    def match_season(mt: m.Match) -> int | None:
        if world is None:
            return None
        return season_for_datetime(world, mt.played_at)

    def cup_row_of(mt: m.Match) -> m.WorldCup | None:
        candidates = [
            row for row in cups
            if row.cup_level == mt.cup_level and row.cup_level_index == mt.cup_level_index
        ]
        if team.current_cup_id:
            active = cup_by_id.get(team.current_cup_id)
            if active in candidates:
                return active
        expected_league_level = team.league_level if team.league_level > 6 else 0
        return next(
            (row for row in candidates if row.cup_league_level == expected_league_level),
            candidates[0] if candidates else None,
        )

    matches = list((await session.execute(
        select(m.Match).where(
            ((m.Match.home_team_ht_id == team.ht_team_id)
             | (m.Match.away_team_ht_id == team.ht_team_id)),
            m.Match.match_type == CUP_MATCH_TYPE,
        ).order_by(m.Match.played_at)
    )).scalars())
    played = [mt for mt in matches if mt.status.upper() == "FINISHED"]
    upcoming = [mt for mt in matches if mt.status.upper() != "FINISHED"]
    next_match = min(upcoming, key=lambda mt: mt.played_at, default=None)
    latest_match = next_match or max(played, key=lambda mt: mt.played_at, default=None)

    active_world_cup = cup_by_id.get(team.current_cup_id or 0)
    fallback_world_cup = cup_row_of(latest_match) if latest_match else None
    current_world_cup = active_world_cup or fallback_world_cup
    still_in_cup = team.still_in_cup if team.still_in_cup is not None else bool(upcoming)
    status_source = "teamdetails" if team.still_in_cup is not None else "calendario"

    cup_league_level = (
        team.current_cup_league_level if team.still_in_cup and team.current_cup_league_level is not None
        else current_world_cup.cup_league_level if current_world_cup else None
    )
    cup_level = (
        team.current_cup_level if team.still_in_cup and team.current_cup_level is not None
        else current_world_cup.cup_level if current_world_cup else latest_match.cup_level if latest_match else None
    )
    cup_level_index = (
        team.current_cup_level_index if team.still_in_cup and team.current_cup_level_index is not None
        else current_world_cup.cup_level_index if current_world_cup
        else latest_match.cup_level_index if latest_match else None
    )
    current_name = (
        team.current_cup_name if team.still_in_cup and team.current_cup_name
        else current_world_cup.cup_name if current_world_cup else None
    )
    official_round = (
        team.current_cup_match_round if team.still_in_cup and team.current_cup_match_round is not None
        else current_world_cup.match_round if still_in_cup and current_world_cup and current_world_cup.match_round >= 0
        else None
    )
    # Rows created before migration 0035 carry the database defaults
    # MatchRound=-1/MatchRoundsLeft=0. Zero is meaningful only when CHPP also
    # supplied a valid round; by itself it must never be read as "champion".
    rounds_left = (
        team.current_cup_match_rounds_left
        if (
            team.still_in_cup
            and team.current_cup_match_round is not None
            and team.current_cup_match_rounds_left is not None
        )
        else current_world_cup.match_rounds_left
        if (
            still_in_cup
            and current_world_cup
            and current_world_cup.match_round >= 0
        )
        else None
    )
    classification = _classification(cup_league_level, cup_level, cup_level_index)
    prize_table, goal = _prize_goal(
        cast(str | None, classification["prize_key"]), rounds_left,
        team.currency_rate or 1.0, world.league_system_id if world else 1,
        classification["tier"] == "consolation",
    )

    # Historial: solo la temporada actual (pedido explícito 2026-08-13), sin
    # aviso — el usuario ya sabe que es así.
    matches_this_season = (
        [mt for mt in matches if match_season(mt) == current_season]
        if current_season is not None else matches
    )
    played_this_season = [mt for mt in matches_this_season if mt.status.upper() == "FINISHED"]

    ratings_by_match = {
        row.ht_match_id: row for row in (await session.execute(
            select(m.MatchRating).where(
                m.MatchRating.ht_match_id.in_([mt.ht_match_id for mt in played_this_season] or [-1]),
                m.MatchRating.team_ht_id == team.ht_team_id,
            )
        )).scalars()
    }

    def side(mt: m.Match) -> tuple[bool, str, int]:
        is_home = mt.home_team_ht_id == team.ht_team_id
        return (
            is_home,
            mt.away_team_name if is_home else mt.home_team_name,
            mt.away_team_ht_id if is_home else mt.home_team_ht_id,
        )

    # La ronda de cada partido NO es una estimación: cada vez que el equipo
    # entra a una llave concreta (cup_level, cup_level_index) esa llave
    # arranca en ronda 1 y avanza de uno en uno mientras se gana — verificado
    # en vivo 2026-08-13 contando los partidos de "Copa Cocuy Rubí" (2
    # jugados + el próximo) contra `current_cup_match_round`=3, que CHPP
    # confirma como oficial. Contar posición dentro de la llave DA el número
    # real. Se agrupa solo dentro de la temporada actual porque el índice de
    # llave (p. ej. Desafío Rubí) se reutiliza cada temporada.
    round_by_match_id: dict[int, int] = {}
    by_cup_key: dict[tuple[int, int], list[m.Match]] = {}
    for mt in matches_this_season:
        if mt.cup_level >= 0 and mt.cup_level_index >= 0:
            by_cup_key.setdefault((mt.cup_level, mt.cup_level_index), []).append(mt)
    for group in by_cup_key.values():
        for index, mt in enumerate(sorted(group, key=lambda item: item.played_at), start=1):
            round_by_match_id[mt.ht_match_id] = index

    won = drawn = lost = goals_for = goals_against = 0
    history = []
    for mt in played_this_season:
        is_home, opponent, opponent_ht_id = side(mt)
        own_goals = mt.home_goals if is_home else mt.away_goals
        opp_goals = mt.away_goals if is_home else mt.home_goals
        goals_for += own_goals
        goals_against += opp_goals
        if own_goals > opp_goals:
            won += 1
            result = "V"
        elif own_goals == opp_goals:
            drawn += 1
            result = "E"
        else:
            lost += 1
            result = "D"
        rating = ratings_by_match.get(mt.ht_match_id)
        hs = hatstats({
            "midfield": rating.midfield, "right_def": rating.right_def,
            "central_def": rating.central_def, "left_def": rating.left_def,
            "right_att": rating.right_att, "central_att": rating.central_att,
            "left_att": rating.left_att,
        }) if rating else None
        row = cup_row_of(mt)
        history.append({
            "ht_match_id": mt.ht_match_id, "date": mt.played_at.date().isoformat(),
            "opponent": opponent, "opponent_ht_team_id": opponent_ht_id,
            "is_home": is_home, "goals_for": own_goals, "goals_against": opp_goals,
            "result": result, "hatstats": hs,
            "round": round_by_match_id.get(mt.ht_match_id),
            "cup_name": row.cup_name if row else None,
        })

    streak_count = 0
    streak_result: str | None = None
    for row in reversed(history):
        if streak_result is None:
            streak_result = cast(str, row["result"])
            streak_count = 1
        elif row["result"] == streak_result:
            streak_count += 1
        else:
            break
    current_streak = {"count": streak_count, "result": streak_result} if streak_result else None

    ladder: list[dict[str, Any]] = []
    current_key: tuple[int, int] | None = None
    current_group: list[m.Match] = []
    for mt in matches:
        key = (mt.cup_level, mt.cup_level_index)
        if mt.cup_level < 0:
            continue
        if key != current_key:
            if current_group:
                row = cup_row_of(current_group[0])
                ladder.append({
                    "cup_level": current_key[0] if current_key else -1,
                    "cup_level_index": current_key[1] if current_key else -1,
                    "cup_name": row.cup_name if row else None,
                    "from_date": current_group[0].played_at.date().isoformat(),
                    "to_date": current_group[-1].played_at.date().isoformat(),
                    "matches": len(current_group),
                })
            current_key, current_group = key, [mt]
        else:
            current_group.append(mt)
    if current_group:
        row = cup_row_of(current_group[0])
        ladder.append({
            "cup_level": current_key[0] if current_key else -1,
            "cup_level_index": current_key[1] if current_key else -1,
            "cup_name": row.cup_name if row else None,
            "from_date": current_group[0].played_at.date().isoformat(),
            "to_date": current_group[-1].played_at.date().isoformat(),
            "matches": len(current_group),
        })

    is_neutral = rounds_left is not None and 0 < rounds_left <= 6
    next_matches = []
    for mt in sorted(upcoming, key=lambda item: item.played_at):
        row = cup_row_of(mt)
        next_matches.append({
            "ht_match_id": mt.ht_match_id, "date": mt.played_at.date().isoformat(),
            "opponent": side(mt)[1], "opponent_ht_team_id": side(mt)[2],
            "is_home": side(mt)[0], "is_neutral": is_neutral,
            "venue_label": "Sede neutral" if is_neutral else "Local" if side(mt)[0] else "Visitante",
            "round_estimate": round_by_match_id.get(mt.ht_match_id),
            "official_round": official_round,
            "cup_name": row.cup_name if row else None,
        })

    scenarios = None
    if still_in_cup and cup_level is not None:
        if rounds_left == 1:
            win_text = f"Victoria: campeón de {current_name or 'esta Copa'}."
        elif rounds_left is None:
            win_text = "Victoria: avanza; la siguiente instancia se confirmará con la ronda oficial."
        else:
            win_text = f"Victoria: avanza a {_stage_label(rounds_left - 1) or 'la siguiente ronda'}."
        continues, destination, loss_text = _loss_destination(
            classification, cup_league_level or 0, cup_level_index or 1,
            official_round, cups,
        )
        scenarios = {
            "win": {
                "continues": True, "destination": current_name,
                "description": win_text,
                "next_stage": (
                    _stage_label(rounds_left - 1)
                    if rounds_left is not None and rounds_left > 0
                    else None
                ),
                "prize_amount": goal["next_milestone"]["amount"] if goal["next_milestone"] else goal["title_amount"],
            },
            "loss": {
                "continues": continues, "destination": destination,
                "description": loss_text, "next_stage": None,
                "prize_amount": goal["secured_amount"],
            },
        }

    readiness = await _readiness(
        session, team_id, team.ht_team_id, matches, len(played_this_season),
    )
    economy = await _cup_economy(session, team, next_match, rounds_left)
    experience_multiplier = 2.0 if classification["tier"] == "main" else 0.5
    impact = {
        "experience_multiplier_vs_league": experience_multiplier,
        "experience_points_per_90": 3.5 * experience_multiplier,
        "affects_club_mood": classification["tier"] == "main",
        "injury_effect": "Riesgo completo de partido competitivo",
    }

    notes = []
    if not matches:
        notes.append("Todavía no hay partidos de Copa sincronizados.")
    if team.still_in_cup is None:
        notes.append("Sincroniza para leer si sigues en Copa: por ahora se deduce del calendario.")
    if official_round is None and still_in_cup:
        notes.append("Sincroniza para leer la ronda oficial.")

    return cast(dict[str, Any], _camel({
        "team_name": team.name,
        "currency": team.currency_name or "",
        "matches_played": len(played), "record": f"{won}-{drawn}-{lost}",
        "goals_for": goals_for, "goals_against": goals_against,
        "current_cup_name": current_name, "current_streak": current_streak,
        "status": {
            "still_in_cup": still_in_cup, "source": status_source,
            "cup_id": team.current_cup_id if team.still_in_cup else current_world_cup.ht_cup_id if current_world_cup else None,
            "cup_name": current_name,
            "scope": classification["scope"], "scope_label": classification["scope_label"],
            "tier": classification["tier"], "tier_label": classification["tier_label"],
            "official_round": official_round, "rounds_left": rounds_left,
            "stage_label": _stage_label(rounds_left),
            "next_cup_match_date": world.cup_match_date.isoformat() if world and world.cup_match_date else None,
        },
        "goal": goal, "scenarios": scenarios, "impact": impact,
        "economy": economy, "readiness": readiness,
        "ladder": ladder, "history": history, "next_matches": next_matches,
        "prize_table": prize_table, "notes": notes,
    }))
