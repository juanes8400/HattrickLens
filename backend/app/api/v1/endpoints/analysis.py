"""Endpoints de los motores de análisis. HL-034, HL-036, HL-101, HL-121, HL-130."""
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.cup import cup as get_cup_data
from app.application.queries.academy import AcademyQueryService
from app.application.queries.arena import ArenaQueryService
from app.application.queries.league import LeagueQueryService
from app.application.queries.player_history import HISTORY_SKILL_COLS, PlayerHistoryQueryService
from app.application.queries.post_match_training import PostMatchTrainingService
from app.application.queries.squad import SKILL_COLS, SquadQueryService
from app.application.queries.training_context import TrainingContextService
from app.application.queries.training_squad import TrainingSquadQueryService
from app.application.queries.weekly import season_week_for_datetime, season_week_label
from app.domain.engines import insights as ins
from app.domain.engines.career_stage_engine import classify_career_stage
from app.domain.engines.economy_engine import structural_balance, total_sponsor_income
from app.domain.engines.experience_engine import (
    calibrate,
)
from app.domain.engines.experience_engine import model_info as experience_model_info
from app.domain.engines.lineup_optimizer import (
    FORMATIONS,
    TEAM_SPIRIT_ATTITUDE_MULTIPLIER,
    best_formation,
    best_lineup,
    weather_impact,
)
from app.domain.engines.loyalty_engine import loyalty_decimal as calculate_loyalty_decimal
from app.domain.engines.loyalty_engine import model_info as loyalty_model_info
from app.domain.engines.position_engine import rate_all
from app.domain.engines.pricing_engine import (
    SALARY_FIELD_SKILLS,
    estimate_salary,
)
from app.domain.engines.team_rating_engine import (
    SECTOR_LABELS,
    SECTORS,
    compute_sector_ratings,
)
from app.domain.engines.training_engine import (
    TrainingSetup,
    default_setup as default_training_setup,
    model_info as training_model_info,
    training_mode,
    weeks_to_next_level,
)
from app.domain.value_objects.ht_constants import match_role_name, training_target
from app.domain.value_objects.stamina_reference import (
    age_after_weeks,
    stamina_forecast_level,
)
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session

router = APIRouter()


async def roster(session: AsyncSession, team_id: int) -> tuple[list[dict[str, Any]], m.Team]:
    team = await session.get(m.Team, team_id)
    if team is None:
        raise HTTPException(404, f"team {team_id} not found")
    rows = await SquadQueryService(session)._latest(team_id)
    players = [
        {
            "ht_player_id": ident.ht_player_id,
            "first_name": ident.first_name,
            "last_name": ident.last_name,
            "name": f"{ident.first_name} {ident.last_name}",
            "age_years": snap.age_years,
            "age_days": snap.age_days,
            "tsi": snap.tsi,
            "form": snap.form,
            "stamina": snap.stamina,
            "experience": snap.experience,
            "salary": snap.salary,
            # HL-15x: specialty/leadership ya vienen reales de players.xml —
            # antes se ponían a 0 a mano porque no se persistían todavía.
            "specialty": snap.specialty,
            "leadership": snap.leadership,
            # 2026-08-09: bug real corregido de paso — sin esto,
            # _loyalty_bonus() en position_engine.py siempre daba 0 (ningún
            # llamador pasaba "loyalty"), pese a que positions.yaml ya
            # declara la fidelidad como ajuste del Manual.
            "loyalty": snap.loyalty,
            "injury_level": snap.injury_level,
            "is_transfer_listed": snap.is_transfer_listed,
            "skills": {c: getattr(snap, c) or 0 for c in SKILL_COLS},
        }
        for snap, ident in rows
    ]
    return players, team


@router.get(
    "/teams/{team_id}/players/{ht_player_id}",
    summary="Ficha del jugador — hub de todos los enlaces por nombre",
)
async def player_detail(
    team_id: int,
    ht_player_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Identidad, habilidades, las 19 posiciones + roles especiales, valoración,
    ventana de venta y previsión de entrenamiento de un jugador — todo lo que
    ya calculan los motores de plantilla, filtrado a uno solo."""
    players, team = await roster(session, team_id)
    p = next((x for x in players if x["ht_player_id"] == ht_player_id), None)
    if p is None:
        # 2026-08-05: no está en la plantilla ACTUAL (`roster()` solo trae
        # `left_team_at IS NULL`) — puede ser un ex-jugador (venta real o
        # despido) que sigue en nuestra base (append-only, nunca se borra),
        # no un ID que nunca pasó por este equipo. Se devuelve una ficha
        # reducida en vez de 404 — pedido explícitamente 2026-08-05: solo
        # identidad + fechas, el saldo/ROI completo lo trae ya calculado
        # `/teams/{team_id}/player-balance` (mismo criterio de despido a
        # $0), no se duplica ese cálculo aquí.
        ex_player = await session.scalar(
            select(m.Player).where(
                m.Player.team_id == team_id, m.Player.ht_player_id == ht_player_id
            )
        )
        if ex_player is None:
            raise HTTPException(404, f"player {ht_player_id} not found in team {team_id}")
        return {
            "isExPlayer": True,
            "htPlayerId": ex_player.ht_player_id,
            "name": f"{ex_player.first_name} {ex_player.last_name}".strip(),
            "purchasedAt": (
                ex_player.purchased_at.isoformat() if ex_player.purchased_at else None
            ),
            "leftTeamAt": (
                ex_player.left_team_at.isoformat() if ex_player.left_team_at else None
            ),
            "soldAt": ex_player.sold_at.isoformat() if ex_player.sold_at else None,
        }
    rate_ = team.currency_rate or 1.0

    # Roles especiales (capitán y balón parado) son recomendaciones aparte:
    # no deben desplazar la mejor posición de cancha en la ficha.
    field_ranked = rate_all(p)
    ranked = field_ranked + [r for r in rate_all(p, include_special=True) if r.is_special_role]

    tr = await session.scalar(
        select(m.TrainingSnapshot)
        .where(m.TrainingSnapshot.team_id == team_id)
        .order_by(m.TrainingSnapshot.captured_at.desc())
        .limit(1)
    )
    ctx = await TrainingContextService(session).get(team_id)
    trained_skill: str | None
    if ctx is not None:
        setup = ctx.setup
        trained_skill = ctx.trained_skill
    else:
        trained_skill = training_target(tr.training_type) if tr else None
        setup = default_training_setup(
            trained_skill or "playmaking",
            training_type=tr.training_type if tr else None,
            intensity=tr.training_level if tr else 100,
            stamina_share=tr.stamina_part if tr else None,
        )
    training_speed = (
        weeks_to_next_level(
            trained_skill, p["skills"].get(trained_skill, 0),
            p["age_years"], p["age_days"], setup=setup,
        )
        if trained_skill else None
    )
    weeks_to_next_pop = training_speed.weeks_to_next_level if training_speed else None
    # HL-15x #97: ritmo semanal REAL de la fórmula (1/semanas) — no es el
    # acumulado real por partidos jugados (esa tabla posición→entrenamiento
    # todavía no está verificada, ver Nota en el panel), pero sí es un
    # porcentaje derivado de la fórmula comunitaria, no un valor observado.
    weekly_training_progress_pct = (
        round(training_speed.weekly_progress * 100, 1) if training_speed else None
    )
    # HL-141: fórmula de comunidad, distinta de un modelo de precio de
    # mercado. Sirve para contrastar contra el sueldo real que ya
    # reporta CHPP (arriba) y para proyectar el sueldo tras la próxima subida
    # de la habilidad entrenada. Solo cubre jugadores de campo — para un
    # arquero (Portero es su mejor posición) el manual no publica la fórmula
    # y devolver algo aquí sería inventar un número, así que se omite.
    salary_now = None
    salary_after_pop = None
    if field_ranked[0].position != "keeper":
        salary_now = estimate_salary(p["skills"], p["skills"].get("set_pieces", 0))
        if trained_skill in SALARY_FIELD_SKILLS and weeks_to_next_pop is not None:
            projected = dict(p["skills"])
            projected[trained_skill] = projected.get(trained_skill, 0) + 1
            salary_after_pop = estimate_salary(
                projected, p["skills"].get("set_pieces", 0)
            ).weekly_salary

    # HL-15x: gráficas ampliadas de la ficha — todo real, sin proyecciones.
    history_svc = PlayerHistoryQueryService(session)
    snapshot_history = await history_svc.snapshot_history(ht_player_id)
    match_rating_history = await history_svc.match_rating_history(ht_player_id)
    distributions = await history_svc.squad_distributions(team_id, ht_player_id, rate_)
    percentile = await history_svc.dominant_skill_percentile(team_id, ht_player_id)
    top_skill_distributions = await history_svc.top_skill_distributions(team_id, ht_player_id)
    experience_progress = await history_svc.experience_progress(ht_player_id)

    # "TT-ss" por punto — mismo filtro por `ht_league_id` que economy.py
    # (bug real corregido 2026-08-09: "la fila de WorldContext más reciente"
    # daba cualquier país al azar en cuanto había más de uno).
    world = (
        await session.scalar(
            select(m.WorldContext).where(m.WorldContext.ht_league_id == team.ht_league_id)
        )
        if team.ht_league_id is not None else None
    )

    def _season_week(captured_at: str) -> str | None:
        when = datetime.fromisoformat(captured_at)
        return season_week_for_datetime(world, when)

    squad = await SquadQueryService(session).get(team_id)
    squad_player = (
        next((sp for sp in squad.players if sp.ht_player_id == ht_player_id), None)
        if squad is not None else None
    )

    # HL-15x, pedido explícito 2026-08-10: "cuándo entró al equipo" para el
    # punto más antiguo del radar — la compra real es más honesta que "la
    # primera vez que sincronizamos", que puede ser meses después de que el
    # jugador ya estaba en el club. `purchased_at_manual` (HL-161) es el
    # respaldo para jugadores que llegaron antes de que existiera el
    # tracking de compras; si tampoco hay eso, el radar sigue cayendo de
    # vuelta al primer snapshot real (sin inventar una fecha).
    player_row = await session.scalar(
        select(m.Player).where(
            m.Player.team_id == team_id, m.Player.ht_player_id == ht_player_id
        )
    )
    joined_at = (
        (player_row.purchased_at or player_row.purchased_at_manual)
        if player_row is not None else None
    )
    joined_season_week = _season_week(joined_at.isoformat()) if joined_at is not None else None
    # "Precio de compra" se declara "real, de transfersteam.xml" — a
    # diferencia de arriba, aquí NUNCA se usa el respaldo manual, para no
    # ponerle un "TT-ss" real a una fecha que en realidad es una estimación.
    purchased_at_season_week = (
        _season_week(player_row.purchased_at.isoformat())
        if player_row is not None and player_row.purchased_at is not None
        else None
    )

    # HL-15x, pedido explícito 2026-08-10: ¿jugó esta semana? — señal simple
    # para la barrita de la habilidad entrenada (el rojo del ritmo semanal
    # solo se muestra si jugó) y para Forma (no hay fórmula propia, solo se
    # marca que algo pudo haber cambiado).
    current_week_label = season_week_label(world, weeks_offset=0)
    played_this_week = bool(
        match_rating_history
        and current_week_label is not None
        and _season_week(match_rating_history[-1].captured_at) == current_week_label
    )

    # Fidelidad usa exclusivamente los días calendario transcurridos desde la
    # compra. La parte decimal es la misma curva antes de aplicar floor; no se
    # calibra con pops ni con el historial de snapshots.
    loyalty_decimal: float | None = None
    if joined_at is not None:
        purchase_date = (
            joined_at if joined_at.tzinfo else joined_at.replace(tzinfo=UTC)
        ).date()
        days_since_purchase = max((datetime.now(UTC).date() - purchase_date).days, 0)
        loyalty_decimal = calculate_loyalty_decimal(days_since_purchase)

    # HL-15x, pedido explícito 2026-08-10: proyección de Resistencia (líneas
    # punteadas en "Evolución de habilidades") según la tabla de Federación
    # Ocerin — asume que el % de entrenamiento de resistencia actual se
    # mantiene constante hacia adelante; `None` si no hay WorldContext propio
    # (no hay forma de etiquetar "TT-ss" futuras) o la edad ya no está
    # cubierta por la tabla (17-36).
    stamina_forecast: dict[str, Any] | None = None
    if world is not None:
        current_stamina_pct = setup.effective_stamina_intensity
        forecast_season_weeks: list[str | None] = []
        forecast_levels: list[int] = []
        for weeks_ahead in range(1, 9):
            proj_years, proj_days = age_after_weeks(
                p["age_years"], p["age_days"], weeks_ahead
            )
            level = stamina_forecast_level(proj_years, current_stamina_pct)
            if level is None:
                continue
            forecast_season_weeks.append(season_week_label(world, weeks_offset=weeks_ahead))
            forecast_levels.append(level)
        # Nivel esperado HOY con el % real actual — la barrita de Resistencia
        # lo compara contra el nivel real (`p["stamina"]`) para decidir si el
        # rojo se agrega (sube) o se come parte del azul (baja).
        current_expected_level = stamina_forecast_level(
            p["age_years"], current_stamina_pct
        )
        if forecast_levels or current_expected_level is not None:
            stamina_forecast = {
                "seasonWeeks": forecast_season_weeks,
                "levels": forecast_levels,
                "trainingPct": round(current_stamina_pct, 1),
                "currentExpectedLevel": current_expected_level,
            }

    # HL-15x #87: preclasificación de "en qué momento de su vida está" — motor
    # puro, aquí solo se ensamblan las señales reales que necesita.
    has_sufficient_history = len(snapshot_history) >= 2
    skills_rising = skills_falling = skills_stable = 0
    if has_sufficient_history:
        oldest_skills, latest_skills = snapshot_history[0].skills, snapshot_history[-1].skills
        for col in SKILL_COLS:
            o, n = oldest_skills.get(col, 0), latest_skills.get(col, 0)
            if n > o:
                skills_rising += 1
            elif n < o:
                skills_falling += 1
            else:
                skills_stable += 1
    career_stage = classify_career_stage(
        age_years=p["age_years"], age_days=p["age_days"],
        skills_rising=skills_rising, skills_falling=skills_falling,
        skills_stable=skills_stable, has_sufficient_history=has_sufficient_history,
        squad_percentile=percentile["percentile"] if percentile else None,
        leadership=p["leadership"],
        loyalty=squad_player.loyalty if squad_player is not None else 0,
    )

    return {
        "isExPlayer": False,
        "htPlayerId": p["ht_player_id"],
        "name": p["name"],
        "team": {"htTeamId": team.ht_team_id, "name": team.name},
        "age": f"{p['age_years']}.{p['age_days']}",
        "tsi": p["tsi"], "form": p["form"], "stamina": p["stamina"],
        "experience": p["experience"], "salary": int(round(p["salary"] / rate_)),
        "injuryLevel": p["injury_level"],
        # Datos de ficha: son observaciones directas de players.xml y
        # playerdetails.xml. Se exponen separados de cualquier cálculo Lens
        # para que la vista Detalles pueda conservar el lenguaje de HC.
        "countryId": squad_player.country_id if squad_player is not None else 0,
        "specialty": squad_player.specialty if squad_player is not None else "",
        "leadership": p["leadership"],
        "isTransferListed": p["is_transfer_listed"],
        "lastMatch": (
            {
                "position": squad_player.last_match_position,
                "rating": squad_player.last_match_rating,
                "minutes": squad_player.last_match_played_minutes,
            }
            if squad_player is not None and squad_player.last_match_position is not None
            else None
        ),
        "playerTrainer": (
            {
                "level": squad_player.player_trainer_skill_level,
                "type": squad_player.player_trainer_type,
            }
            if squad_player is not None and squad_player.player_trainer_skill_level > 0
            else None
        ),
        "skills": p["skills"],
        "positions": [
            {"position": r.position, "label": r.label, "rating": r.rating,
             "isSpecialRole": r.is_special_role}
            for r in ranked
        ],
        "training": {
            "trainedSkill": trained_skill,
            "weeksToPop": round(weeks_to_next_pop, 1) if weeks_to_next_pop is not None else None,
            "weeklyProgressPct": weekly_training_progress_pct,
        },
        "salaryEstimate": (
            {
                "weeklySalary": salary_now.weekly_salary,
                "mainSkill": salary_now.main_skill,
                "afterNextPop": salary_after_pop,
                "confidence": salary_now.confidence,
            }
            if salary_now is not None
            else None
        ),
        "loyalty": squad_player.loyalty if squad_player is not None else None,
        "loyaltyDecimal": loyalty_decimal,
        "staminaForecast": stamina_forecast,
        "joinedSeasonWeek": joined_season_week,
        "purchasedAtSeasonWeek": purchased_at_season_week,
        "playedThisWeek": played_this_week,
        # HL-15x, pedido explícitamente 2026-08-05: "¿este jugador ha jugado
        # con la selección nacional?" — Caps/CapsU20 de playerdetails.xml,
        # totales de carrera. None = todavía no se ha pedido playerdetails
        # para este jugador (distinto de "0 caps reales").
        "nationalTeam": (
            {
                "caps": squad_player.career_caps,
                "capsU20": squad_player.career_caps_u20,
            }
            if squad_player is not None and squad_player.career_caps is not None
            else None
        ),
        "nativeLeagueName": (
            squad_player.native_league_name if squad_player is not None else None
        ),
        "purchasePrice": squad_player.purchase_price if squad_player is not None else None,
        "purchasedAt": squad_player.purchased_at if squad_player is not None else None,
        "careerStage": {
            "stage": career_stage.stage, "label": career_stage.label,
            "rationale": career_stage.rationale, "confidence": career_stage.confidence,
            "signals": career_stage.signals,
            # HL-15x #93: confirmación manual del usuario, si la hay — la app
            # solo sugiere `stage`/`label` de arriba, nunca los sobreescribe.
            "confirmedStage": (
                squad_player.confirmed_career_stage if squad_player is not None else None
            ),
            "confirmedAt": (
                squad_player.confirmed_career_stage_at if squad_player is not None else None
            ),
        },
        "goals": (
            {
                "league": squad_player.league_goals, "cup": squad_player.cup_goals,
                "friendlies": squad_player.friendlies_goals,
                "career": squad_player.career_goals,
                "hattricks": squad_player.career_hattricks,
                "assists": squad_player.career_assists,
            }
            if squad_player is not None else None
        ),
        "character": (
            {
                "agreeability": squad_player.agreeability,
                "agreeabilityLabel": squad_player.agreeability_label,
                "aggressiveness": squad_player.aggressiveness,
                "aggressivenessLabel": squad_player.aggressiveness_label,
                "honesty": squad_player.honesty,
                "honestyLabel": squad_player.honesty_label,
            }
            if squad_player is not None else None
        ),
        # HL-15x #5: timeline real de las 9 variables (7 skills + experiencia
        # + fidelidad) + TSI + salario, tal cual está en player_snapshots —
        # hoy puede tener pocos puntos (cuenta nueva), se devuelve así.
        "history": {
            "dates": [pt.captured_at for pt in snapshot_history],
            "seasonWeeks": [_season_week(pt.captured_at) for pt in snapshot_history],
            "tsi": [pt.tsi for pt in snapshot_history],
            "salary": [int(round(pt.salary / rate_)) for pt in snapshot_history],
            "skills": {
                col: [pt.skills[col] for pt in snapshot_history]
                for col in HISTORY_SKILL_COLS
            },
        },
        # HL-15x #21: histórico real de rating por partido (tabla aparte,
        # append-only) — puede estar vacío si playerdetails no se ha
        # sincronizado nunca para este jugador.
        "matchRatingHistory": [
            {
                "matchId": pt.ht_match_id, "date": pt.captured_at,
                "seasonWeek": _season_week(pt.captured_at), "rating": pt.rating,
                "position": match_role_name(pt.position_code),
                "minutes": pt.played_minutes,
            }
            for pt in match_rating_history
        ],
        # HL-15x #8: KDE de TSI/Salario/$-por-TSI sobre la plantilla activa,
        # con el valor de este jugador para resaltar. None si el jugador ya
        # no está en el club (no tiene sentido "su lugar en la plantilla").
        "squadDistributions": (
            {
                key: {
                    "grid": dist.grid, "density": dist.density,
                    "values": dist.values, "ownValue": dist.own_value,
                }
                for key, dist in distributions.items()
            }
            if distributions is not None else None
        ),
        # HL-15x #23: percentil en su skill dominante dentro de la plantilla —
        # sigue calculándose (lo usa el motor de preclasificación), pero ya
        # no se muestra como panel propio: HL-15x #99 lo reemplaza por los
        # histogramas de abajo.
        "percentile": percentile,
        # HL-15x #11: % real hacia la próxima subida de experiencia — Manual
        # No Escrito, contado desde partidos reales jugados desde que se
        # observó este nivel (ver docstring de experience_progress).
        "experienceProgress": (
            {
                "points": experience_progress.points,
                "percent": experience_progress.percent,
                "remainingPoints": experience_progress.remaining_points,
                "pointsPerLevel": experience_progress.points_per_level,
                "calibrationSource": experience_progress.calibration_source,
                "breakdown": experience_progress.breakdown,
                "unscoredNationalMatches": experience_progress.unscored_national_matches,
            }
            if experience_progress is not None else None
        ),
        # HL-15x #99: histogramas KDE de las 3 habilidades más altas del
        # jugador (sin Balón Parado), cada una con su plantilla real.
        "topSkillDistributions": (
            {
                key: {
                    "grid": dist.grid, "density": dist.density,
                    "values": dist.values, "ownValue": dist.own_value,
                }
                for key, dist in top_skill_distributions.items()
            }
            if top_skill_distributions is not None else None
        ),
        # HL-15x #22: TSI vs. edad de toda la plantilla activa, para
        # dispersión — ya calculado arriba (`players`, de `roster()`), sin
        # query nueva.
        "squadAgeTsi": [
            {
                "htPlayerId": x["ht_player_id"], "name": x["name"],
                "age": round(x["age_years"] + x["age_days"] / 112, 2),
                "tsi": x["tsi"],
            }
            for x in players
        ],
    }


@router.get("/teams/{team_id}/lineup", summary="Mejor once posible (HL-121)")
async def lineup(
    team_id: int,
    formation: str | None = Query(None, description="Si se omite, prueba las 8"),
    weather: str | None = Query(None, pattern="^(rain|cloudy|partly|sun)$"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    players, _ = await roster(session, team_id)
    if formation and formation not in FORMATIONS:
        raise HTTPException(400, f"formación desconocida: {formation}")
    try:
        if formation:
            lu = best_lineup(players, formation, weather=weather)
            ranking = {formation: lu.total_rating}
        else:
            lu, ranking = best_formation(players, weather=weather)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    # HL-143: segunda opinión sobre el MISMO once que ya eligió el optimizador
    # húngaro (arriba), con la fórmula exacta de contribución de la
    # comunidad — habilidades crudas, sin forma/condición/clima. No decide
    # nada por sí sola, solo informa.
    sector = compute_sector_ratings(
        [(a.player, a.position, a.label) for a in lu.assignments]
    )

    return {
        "formation": lu.formation,
        "totalRating": lu.total_rating,
        "manualShare": round(lu.manual_share, 2),
        "weather": lu.weather,
        "formationRanking": ranking,
        "lineup": [
            {
                "slot": a.slot, "position": a.position, "label": a.label,
                "player": a.player["name"], "htPlayerId": a.player["ht_player_id"],
                "rating": a.rating, "confidence": a.confidence,
            }
            for a in lu.assignments
        ],
        "bench": [
            {"player": b["name"], "htPlayerId": b["ht_player_id"], "tsi": b["tsi"]}
            for b in lu.bench
        ],
        "sectorRatings": {
            "ratings": [
                {
                    "sector": s, "label": SECTOR_LABELS[s], "value": sector.ratings[s],
                    "topContributors": [
                        {"player": c.player_name, "position": c.position_label, "amount": c.amount}
                        for c in sector.top_contributors[s]
                    ],
                }
                for s in SECTORS
            ],
            "note": (
                "Fórmula exacta de contribución posicional (Manual no Escrito), sobre "
                "habilidades crudas — sin forma, condición ni clima, que ya tienen sus "
                "propios paneles. No reemplaza el ranking de arriba, que sí está "
                "contrastado contra datos reales: es una segunda mirada, complementaria."
            ),
        },
    }


@router.get("/teams/{team_id}/lineup/weather", summary="Impacto del clima (HL-123)")
async def lineup_weather(
    team_id: int,
    formation: str = "4-4-2",
    session: AsyncSession = Depends(get_session),
) -> dict[str, float]:
    players, _ = await roster(session, team_id)
    return weather_impact(players, formation)


@router.get(
    "/teams/{team_id}/lineup/team-spirit",
    summary="Multiplicador de mediocampo por Espíritu de Equipo × Actitud (HL-142)",
)
async def team_spirit_multiplier(
    team_id: int, session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Tabla de referencia, no ligada al Espíritu real de este equipo: los
    nombres del Manual no Escrito no coinciden con los niveles que usa CHPP,
    así que no hay forma honesta de marcar "esta es tu fila" — se explora."""
    team = await session.get(m.Team, team_id)
    if team is None:
        raise HTTPException(404, f"team {team_id} not found")
    return {
        "rows": [
            {"spirit": name, "pic": pic, "normal": normal, "mots": mots}
            for name, pic, normal, mots in TEAM_SPIRIT_ATTITUDE_MULTIPLIER
        ],
        "note": (
            "Fuente: Manual no Escrito de la comunidad — los nombres de esta tabla no "
            "coinciden con los niveles de Espíritu que reporta CHPP, así que no se puede "
            "marcar cuál es tu fila actual: es una tabla explorable, no una lectura de tu "
            "equipo."
        ),
    }


@router.get("/teams/{team_id}/training/forecast", summary="Previsión de subidas (HL-034)")
async def training_forecast(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    players, team = await roster(session, team_id)
    tr = await session.scalar(
        select(m.TrainingSnapshot)
        .where(m.TrainingSnapshot.team_id == team_id)
        .order_by(m.TrainingSnapshot.captured_at.desc())
        .limit(1)
    )
    # El contexto se construye con los valores LEÍDOS del CHPP (ayudantes,
    # intensidad, condición, entrenador). Si aún no se han sincronizado club /
    # stafflist, cae a los valores de training + defaults, sin romper.
    ctx = await TrainingContextService(session).get(team_id)
    skill: str | None
    if ctx is not None:
        setup = ctx.setup
        skill = ctx.trained_skill
    else:
        skill = training_target(tr.training_type) if tr else None
        setup = default_training_setup(
            skill or "playmaking",
            training_type=tr.training_type if tr else None,
            intensity=tr.training_level if tr else 100,
            stamina_share=tr.stamina_part if tr else None,
        )

    trainer_ht_id = tr.trainer_ht_id if tr else None
    out = []
    for p in players:
        if not skill or p["ht_player_id"] == trainer_ht_id:
            # El propio entrenador no es una decisión de entrenamiento de
            # nadie (HL-038): sale por training.xml, no por una heurística.
            continue
        speed = weeks_to_next_level(
            skill, p["skills"].get(skill, 0), p["age_years"], p["age_days"], setup=setup
        )
        out.append({
            "player": p["name"], "htPlayerId": p["ht_player_id"],
            "age": f"{p['age_years']}.{p['age_days']}",
            "currentLevel": p["skills"].get(skill, 0),
            "weeksToPop": round(speed.weeks_to_next_level, 1),
        })
    out.sort(key=lambda x: x["weeksToPop"])
    return {
        "trainingType": tr.training_type if tr else None,
        "trainedSkill": skill,
        "exposure": round(setup.effective_intensity, 3),
        "players": out,
    }


@router.get("/teams/{team_id}/insights", summary="Alertas accionables (HL-130)")
async def team_insights(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """Catálogo de reglas de negocio, evaluadas contra los datos reales ya
    sincronizados de este equipo — entrenamiento, plantilla, mercado,
    economía, liga, copa, estadio, academia y cuerpo técnico.

    Es un motor de reglas, no un modelo de IA: cada función de
    `domain.engines.insights` es una condición explícita y auditable sobre
    datos reales (algunas, jugador a jugador). Solo se muestran las que
    disparan de verdad con el estado actual — el catálogo completo es mucho
    más grande que la lista de abajo, que es la intersección con tu equipo
    hoy.
    """
    players, team = await roster(session, team_id)
    rate_ = team.currency_rate or 1.0
    currency = team.currency_name or ""

    econ_rows = list((
        await session.execute(
            select(m.EconomySnapshot)
            .where(m.EconomySnapshot.team_id == team_id)
            .order_by(m.EconomySnapshot.captured_at.desc())
            .limit(2)
        )
    ).scalars())
    econ = econ_rows[0] if econ_rows else None
    econ_prev = econ_rows[1] if len(econ_rows) > 1 else None

    tr = await session.scalar(
        select(m.TrainingSnapshot)
        .where(m.TrainingSnapshot.team_id == team_id)
        .order_by(m.TrainingSnapshot.captured_at.desc()).limit(1)
    )
    staff = await session.scalar(
        select(m.StaffSnapshot)
        .where(m.StaffSnapshot.team_id == team_id)
        .order_by(m.StaffSnapshot.captured_at.desc()).limit(1)
    )
    last_sync = await session.scalar(
        select(m.Sync)
        .where(m.Sync.team_id == team_id, m.Sync.status.in_(("completed", "partial")))
        .order_by(m.Sync.started_at.desc()).limit(1)
    )

    groups: list[list[ins.Insight]] = [
        ins.injuries(players), ins.ageing_squad(players),
        ins.low_form(players), ins.high_form(players), ins.transfer_listed(players),
    ]

    # ── Entrenamiento ───────────────────────────────────────────────────
    ctx = await TrainingContextService(session).get(team_id)
    trained_skill: str | None = None
    setup: TrainingSetup | None = None
    if tr:
        trained_skill = ctx.trained_skill if ctx else training_target(tr.training_type)
        if trained_skill:
            # El propio entrenador (identificado por TrainerID en training.xml,
            # no por heurísticas como TSI) no es una decisión de entrenamiento
            # de nadie: se excluye de las alertas de entrenamiento.
            # `tr` ya está confirmado no-None por el `if tr:` de arriba — el
            # supuesto debe leer su intensidad/condición reales, no caer en
            # 100/0 en silencio (bug real corregido 2026-08-14: antes las
            # ignoraba aunque ya las tenía).
            setup = ctx.setup if ctx else default_training_setup(
                trained_skill, training_type=tr.training_type,
                intensity=tr.training_level, stamina_share=tr.stamina_part,
            )
            trainees = [
                {"name": p["name"], "age_years": p["age_years"],
                 "weeks_to_pop": weeks_to_next_level(
                     trained_skill, p["skills"].get(trained_skill, 0),
                     p["age_years"], p["age_days"], setup=setup).weeks_to_next_level}
                for p in players
                if p["ht_player_id"] != tr.trainer_ht_id
            ]
            groups += [ins.inefficient_training(trainees), ins.upcoming_pops(trainees)]

    # ── Plantilla: posición natural, sueldo de mercado ──
    for p in players:
        p["best_position"] = rate_all(p)[0].position
    groups.append(ins.thin_keeper_depth(players))

    salary_rows: list[dict[str, Any]] = []
    wage_players: list[dict[str, Any]] = []
    total_salary_local = 0
    for p in players:
        salary_local = int(round(p["salary"] / rate_))
        total_salary_local += salary_local
        wage_players.append({
            "ht_player_id": p["ht_player_id"], "name": p["name"], "salary_local": salary_local,
        })

        # La fórmula de sueldo (Manual no Escrito) solo cubre jugadores de
        # campo — igual que en /players/{id}, un arquero se omite en vez de
        # inventarle una estimación.
        if p["best_position"] != "keeper":
            est = estimate_salary(p["skills"], p["skills"].get("set_pieces", 0))
            salary_rows.append({
                "ht_player_id": p["ht_player_id"], "name": p["name"], "currency": currency,
                "real_salary": salary_local, "estimated_salary": est.weekly_salary,
            })

    groups += [
        ins.salary_market_mismatch(salary_rows),
        ins.wage_concentration(wage_players, total_salary_local, currency),
    ]

    # ── Alineación óptima: titulares lesionados, aportadores por sector ──
    try:
        lu, _ = best_formation(players)
    except ValueError:
        lu = None
    if lu is not None:
        starters = [
            {"ht_player_id": a.player["ht_player_id"], "name": a.player["name"],
             "label": a.label, "injury_level": a.player.get("injury_level", -1)}
            for a in lu.assignments
        ]
        groups.append(ins.starter_injured(starters))

        sector = compute_sector_ratings([(a.player, a.position, a.label) for a in lu.assignments])
        standouts = []
        for s in SECTORS:
            top = sector.top_contributors.get(s) or []
            if top:
                c = top[0]
                standouts.append({
                    "sector": s, "label": SECTOR_LABELS[s],
                    "player": c.player_name, "positionLabel": c.position_label, "amount": c.amount,
                })
        groups.append(ins.sector_standouts(standouts))

    # ── Economía ────────────────────────────────────────────────────────
    if econ:
        sponsors_total = total_sponsor_income(econ.income_sponsors, econ.income_sponsor_bonuses)
        structural = int(structural_balance(
            sponsors_total, econ.income_spectators,
            econ.costs_players, econ.costs_staff, econ.costs_arena,
        ) / rate_)
        groups.append(ins.structural_deficit(structural, int(econ.cash / rate_), currency))

        income_items = [
            ("Espectadores", int((econ.income_spectators or 0) / rate_)),
            ("Patrocinadores", int(sponsors_total / rate_)),
            ("Financieros", int((econ.income_financial or 0) / rate_)),
            ("Temporales", int((econ.income_temporary or 0) / rate_)),
        ]
        groups.append(ins.income_concentration(income_items, currency))
        groups.append(ins.cash_vs_expected_mismatch(
            int(econ.cash / rate_), int(econ.expected_cash / rate_), currency))

        if econ_prev:
            groups.append(ins.sponsor_popularity_trend(
                econ_prev.sponsors_popularity, econ.sponsors_popularity))
            groups.append(ins.fan_club_trend(econ_prev.fan_club_size, econ.fan_club_size))

    # ── Liga ────────────────────────────────────────────────────────────
    # runs reducido frente al endpoint dedicado (10000): aquí solo hacen
    # falta umbrales gruesos (25-40%), no la precisión completa.
    league = await LeagueQueryService(session).get(team_id, runs=2000)
    if league and league.own_outlook:
        own = league.own_outlook
        own_dict = {
            "name": own.name, "expected_position": own.expected_position,
            "expected_points": own.expected_points,
            "relegation_probability": own.relegation_probability,
            "relegation_playoff_probability": own.relegation_playoff_probability,
            "promotion_probability": own.promotion_probability,
            "title_probability": own.title_probability,
            "attack_strength": own.attack_strength, "defence_strength": own.defence_strength,
        }
        groups += [
            ins.relegation_danger(own_dict), ins.relegation_playoff_risk(own_dict),
            ins.promotion_chance(own_dict), ins.title_race(own_dict),
            ins.weak_attack(own_dict), ins.weak_defence(own_dict),
        ]
        if league.next_match:
            groups.append(ins.next_match_forecast(league.next_match))

    # ── Copa ────────────────────────────────────────────────────────────
    cup_data = await get_cup_data(team_id, session)
    groups.append(ins.cup_streak_notable(cup_data.get("currentStreak")))

    # ── Estadio ─────────────────────────────────────────────────────────
    arena = await ArenaQueryService(session).get(team_id)
    if arena:
        groups.append(ins.sold_out_sectors(
            arena.censored_sectors, arena.revenue_left_on_table, arena.currency))
        options = [
            {"label": o.label, "netPerSeason": o.net_per_season,
             "paybackSeasons": o.payback_seasons}
            for o in arena.expansion_options
        ]
        groups.append(ins.arena_expansion_opportunity(options, arena.currency))

    # ── Academia ────────────────────────────────────────────────────────
    academy = await AcademyQueryService(session).get(team_id)
    if academy:
        groups.append(ins.academy_roi(academy.invested, academy.earned, academy.currency))
        youth_dicts = [
            {"ht_youth_player_id": y.ht_youth_player_id, "name": y.name,
             "days_until_deadline": y.days_until_deadline, "category": y.category,
             "best_skill": y.best_skill, "best_skill_max": y.best_skill_max,
             "verdict_is_provisional": y.verdict_is_provisional,
             "promote_advice": y.promote_advice}
            for y in academy.players
        ]
        groups.append(ins.youth_deadline(youth_dicts))
        groups.append(ins.youth_star_prospect(youth_dicts))

    # ── Cuerpo técnico ──────────────────────────────────────────────────
    if staff:
        staff_dict = {
            "medic_levels": staff.medic_levels,
            "sport_psychologist_levels": staff.sport_psychologist_levels,
            "assistant_trainer_levels": staff.assistant_trainer_levels,
        }
        groups += [
            ins.missing_medic_or_psych(staff_dict),
            ins.assistant_trainers_below_reference(staff_dict),
        ]

    # ── Sincronización ──────────────────────────────────────────────────
    if last_sync:
        synced_at = last_sync.finished_at or last_sync.started_at
        ref = synced_at if synced_at.tzinfo else synced_at.replace(tzinfo=UTC)
        hours = (datetime.now(UTC) - ref).total_seconds() / 3600
        groups.append(ins.stale_data(hours))

    return [
        {"key": i.key, "severity": i.severity.value, "title": i.title,
         "detail": i.detail, "action": i.action, "module": i.module,
         "evidence": i.evidence}
        for i in ins.collect(*groups)
    ]


@router.get(
    "/teams/{team_id}/experience/calibration",
    summary="Puntos por nivel medidos, no declarados (HL-041)",
)
async def experience_calibration(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """How many experience points a level actually costs, measured from history.

    The specification says 28. Rather than assert that, the engine watches every
    fully observed interval between two experience level-ups, totals the real
    matches played in that interval, and reports their mean together with the
    standard deviation — the part that says whether the mean can be trusted.

    Until enough crossings have accumulated the configured 28 stands and the
    response says so plainly, along with how many more are needed. Nothing here
    pretends to a precision it does not have.
    """
    await roster(session, team_id)          # 404s on an unknown team

    history = PlayerHistoryQueryService(session)
    level_ups, crossings_seen = await history.experience_level_up_observations(team_id)

    cal = calibrate(level_ups)
    info = experience_model_info(cal)
    minimum = 5
    info["observationsNeeded"] = max(minimum - cal.observations, 0)
    info["crossingsSeen"] = crossings_seen
    info["discardedCrossings"] = crossings_seen - len(level_ups)
    info["distinctReadings"] = int(
        await session.scalar(
            select(func.count(m.PlayerSnapshot.id))
            .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
            .where(m.Player.team_id == team_id)
        )
        or 0
    )
    info["levelUps"] = [
        {
            "player": lu.player,
            "fromLevel": lu.from_level,
            "toLevel": lu.to_level,
            "pointsAccumulated": lu.points_accumulated,
        }
        for lu in level_ups
    ]

    # Subidas confirmadas por Hattrick (trainingevents). Importante: validan la
    # fórmula de ENTRENAMIENTO (habilidades entrenadas), no los puntos por nivel
    # de EXPERIENCIA, que dependen de partidos jugados. Se declaran aquí para
    # que no se confundan las dos mecánicas.
    confirmed = await session.scalar(
        select(func.count(m.SkillUp.id)).where(m.SkillUp.team_id == team_id)
    )
    info["confirmedSkillUps"] = int(confirmed or 0)
    info["confirmedSkillUpsNote"] = (
        "Las subidas confirmadas de trainingevents validan la fórmula de "
        "entrenamiento (ver /training/formula), no estos puntos de experiencia: "
        "son mecánicas distintas. La experiencia se calibra con partidos."
    )
    return info


@router.get(
    "/teams/{team_id}/loyalty/model",
    summary="Fórmula de Fidelidad según los días transcurridos desde la compra",
)
async def loyalty_model(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Expone la única regla usada por la ficha y sus umbrales enteros."""
    await roster(session, team_id)  # 404s on an unknown team
    return loyalty_model_info()


@router.get(
    "/teams/{team_id}/training/formula",
    summary="La fórmula de entrenamiento con la procedencia de cada valor (HL-030)",
)
async def training_formula(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Cierra la fórmula: muestra, término a término, si el valor se lee del
    CHPP o sigue siendo un supuesto, y valida contra las subidas confirmadas.

    Es la pantalla que responde «¿de dónde sale este número?» sin que quede
    ningún valor puesto a mano escondido.
    """
    team = await session.get(m.Team, team_id)
    if team is None:
        raise HTTPException(404, f"team {team_id} not found")
    ctx = await TrainingContextService(session).get(team_id)
    if ctx is None:
        raise HTTPException(404, f"team {team_id} not found")

    s = ctx.setup
    model = training_model_info()
    return {
        "trainedSkill": ctx.trained_skill,
        "allRead": ctx.all_read,
        "formula": model["formula"],
        "reference": model["reference"],
        "limitations": model["limitations"],
        "inputs": {
            key: {
                "value": p.value,
                "source": p.source,
                "isRead": p.is_read,
                "note": p.note,
            }
            for key, p in ctx.provenance.items()
        },
        "setup": {
            "skill": s.skill,
            "trainingType": s.training_type,
            "trainingMode": training_mode(s.skill, s.training_type),
            "intensity": s.intensity,
            "staminaShare": s.stamina_share,
            "coachLevel": s.coach_level,
            "coachIsExcellent": s.coach_is_excellent,
            "assistantLevelSum": s.assistant_level_sum,
        },
        "validation": {
            "observations": ctx.validation.observations,
            "meanErrorWeeks": ctx.validation.mean_error_weeks,
            "maxErrorWeeks": ctx.validation.max_error_weeks,
            "samples": ctx.validation.samples,
            "caveats": ctx.validation.caveats,
        },
        "notes": ctx.notes,
    }


@router.get(
    "/teams/{team_id}/training/squad",
    summary="Vista de plantilla por entrenamiento — la pestaña que HC deja vacía",
)
async def training_squad(
    team_id: int,
    skill: str | None = Query(default=None),
    include_this_week: bool = Query(default=True),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Cada jugador activo, para la habilidad elegida: nivel actual, semanas
    transcurridas desde la última subida confirmada por Hattrick o detectada
    entre snapshots reales, % de avance, configuración vigente e histórico
    semanal."""
    view = await TrainingSquadQueryService(session).squad_view(
        team_id, skill=skill, include_this_week=include_this_week,
    )
    if view is None:
        raise HTTPException(404, f"team {team_id} not found")
    s = view.setup
    return {
        "skill": view.skill,
        "skillLabel": view.skill_label,
        "availableSkills": [{"skill": s_, "label": lbl} for s_, lbl in view.available_skills],
        "includeThisWeek": view.include_this_week,
        "setup": {
            "skill": s.skill,
            "trainingType": s.training_type,
            "trainingMode": training_mode(s.skill, s.training_type),
            "intensity": s.intensity,
            "staminaShare": s.stamina_share,
            "coachLevel": s.coach_level,
            "coachIsExcellent": s.coach_is_excellent,
            "assistantLevelSum": s.assistant_level_sum,
        },
        "players": [
            {
                "htPlayerId": r.ht_player_id,
                "name": r.name,
                "nativeCountry": r.native_country,
                "age": f"{r.age_years}.{r.age_days}",
                "level": r.level,
                "levelName": r.level_name,
                "weeksElapsed": r.weeks_elapsed,
                "weeksTotal": r.weeks_total,
                "progressPct": r.progress_pct,
                "hasReference": r.has_reference,
            }
            for r in view.rows
        ],
        "weeklyLog": [
            {
                "seasonWeek": entry.season_week,
                "date": entry.date,
                "trainingType": entry.training_type,
                "intensity": entry.intensity,
                "staminaShare": entry.stamina_share,
                "trainerName": entry.trainer_name,
            }
            for entry in view.weekly_log
        ],
        "notes": view.notes,
    }


@router.get(
    "/teams/{team_id}/training/development",
    summary="Progreso de Experiencia y Fidelidad de la plantilla",
)
async def training_development(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Dos vistas de desarrollo no entrenable, calculadas por sus motores.

    Experiencia se reconstruye con partidos/minutos reales. Fidelidad se
    calcula desde la fecha de llegada. Ninguna de las dos ajusta una regresión
    con los datos privados de la cuenta.
    """
    view = await TrainingSquadQueryService(session).development_view(team_id)
    if view is None:
        raise HTTPException(404, f"team {team_id} not found")
    return {
        "experience": [
            {
                "htPlayerId": row.ht_player_id,
                "name": row.name,
                "nativeCountry": row.native_country,
                "age": f"{row.age_years}.{row.age_days}",
                "level": row.level,
                "levelName": row.level_name,
                "decimalLevel": row.decimal_level,
                "points": row.points,
                "pointsPerLevel": row.points_per_level,
                "remainingPoints": row.remaining_points,
                "progressPct": row.progress_pct,
                "breakdown": row.breakdown,
                "unscoredNationalMatches": row.unscored_national_matches,
            }
            for row in view.experience
        ],
        "loyalty": [
            {
                "htPlayerId": row.ht_player_id,
                "name": row.name,
                "nativeCountry": row.native_country,
                "age": f"{row.age_years}.{row.age_days}",
                "reportedLevel": row.reported_level,
                "calculatedLevel": row.calculated_level,
                "levelName": row.level_name,
                "decimalLevel": row.decimal_level,
                "progressPct": row.progress_pct,
                "daysInClub": row.days_in_club,
                "nextLevel": row.next_level,
                "daysToNextLevel": row.days_to_next_level,
                "dateSource": row.date_source,
            }
            for row in view.loyalty
        ],
        "notes": view.notes,
    }


@router.get(
    "/teams/{team_id}/players/{ht_player_id}/training/levels",
    summary="Subidas confirmadas y previsión de niveles futuros de un jugador",
)
async def player_training_levels(
    team_id: int,
    ht_player_id: int,
    skill: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """«Mejoras» (subidas confirmadas por trainingevents) y «Previsión
    subidas» (cascada de niveles futuros con la fórmula) para un jugador —
    la vista individual de Hattrick Control."""
    history = await TrainingSquadQueryService(session).player_levels(team_id, ht_player_id, skill=skill)
    if history is None:
        raise HTTPException(404, f"team {team_id} or player {ht_player_id} not found")
    return {
        "htPlayerId": history.ht_player_id,
        "name": history.name,
        "skill": history.skill,
        "skillLabel": history.skill_label,
        "currentLevel": history.current_level,
        "currentLevelName": history.current_level_name,
        "confirmed": [
            {
                "seasonWeek": c.season_week,
                "fromLevel": c.from_level,
                "fromLevelName": c.from_level_name,
                "toLevel": c.to_level,
                "toLevelName": c.to_level_name,
                "weeksBetween": c.weeks_between,
            }
            for c in history.confirmed
        ],
        "forecast": [
            {
                "level": f.level,
                "levelName": f.level_name,
                "weeksForThisLevel": f.weeks_for_this_level,
                "weeksFromNow": f.weeks_from_now,
                "seasonWeek": f.season_week,
                "age": f"{f.age_years}.{f.age_days}",
            }
            for f in history.forecast
        ],
        "notes": history.notes,
    }


@router.get(
    "/teams/{team_id}/training/post-match",
    summary="Entrenamiento decidido a posteriori",
)
async def post_match_training(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Compara entrenamientos posibles usando los minutos/posiciones que ya se
    jugaron antes del update de entrenamiento.

    La idea es escoger *despues* de ver la exposicion real de la semana: si los
    jovenes terminaron jugando de delanteros, scoring puede superar al plan
    original; si jugaron interiores, jugadas/pases pueden ganar. El endpoint no
    cambia el entrenamiento en Hattrick: recomienda y deja evidencia.
    """
    result = await PostMatchTrainingService(session).get(team_id)
    if result is None:
        raise HTTPException(404, f"team {team_id} not found")
    return result
