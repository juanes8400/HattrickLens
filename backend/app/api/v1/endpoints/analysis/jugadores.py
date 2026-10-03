"""Ficha de jugador.

Sale de partir `analysis.py`, que tenia 2309 lineas y se abria
entera para tocar cualquiera de sus rutas. El `__init__.py` del paquete
monta `router` con todos estos, asi que las URL no cambian.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_team_owner
from app.api.v1.endpoints.analysis.plantilla import roster
from app.application.queries.player_history import HISTORY_SKILL_COLS, PlayerHistoryQueryService
from app.application.queries.squad import SKILL_COLS, SquadQueryService
from app.application.queries.training_context import TrainingContextService
from app.application.queries.training_squad import TrainingSquadQueryService
from app.application.queries.weekly import season_week_for_datetime, season_week_label
from app.domain.engines import htms as htms_motor
from app.domain.engines.career_stage_engine import classify_career_stage
from app.domain.engines.loyalty_engine import loyalty_decimal as calculate_loyalty_decimal
from app.domain.engines.position_engine import rate_all
from app.domain.engines.pricing_engine import (
    SALARY_FIELD_SKILLS,
    estimate_salary,
)
from app.domain.engines.training_engine import (
    default_setup as default_training_setup,
)
from app.domain.engines.training_engine import (
    weeks_to_next_level,
)
from app.domain.value_objects.ht_constants import (
    match_role_name,
    training_target,
)
from app.domain.value_objects.stamina_reference import (
    age_after_weeks,
    stamina_forecast_level,
)
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session

router = APIRouter()


@router.get(
    "/teams/{team_id}/players/{ht_player_id}",
    summary="Ficha del jugador, hub de todos los enlaces por nombre",
    dependencies=[Depends(require_team_owner)],
)
async def player_detail(
    team_id: int,
    ht_player_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Identidad, habilidades, las 19 posiciones + roles especiales, valoración,
    ventana de venta y previsión de entrenamiento de un jugador, todo lo que
    ya calculan los motores de plantilla, filtrado a uno solo."""
    players, team = await roster(session, team_id)
    p = next((x for x in players if x["ht_player_id"] == ht_player_id), None)
    if p is None:
        # 2026-08-05: no está en la plantilla ACTUAL (`roster()` solo trae
        # `left_team_at IS NULL`), puede ser un ex-jugador (venta real o
        # despido) que sigue en nuestra base (append-only, nunca se borra),
        # no un ID que nunca pasó por este equipo. Se devuelve una ficha
        # reducida en vez de 404, pedido explícitamente 2026-08-05: solo
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
            "purchasedAt": (ex_player.purchased_at.isoformat() if ex_player.purchased_at else None),
            "leftTeamAt": (ex_player.left_team_at.isoformat() if ex_player.left_team_at else None),
            "soldAt": ex_player.sold_at.isoformat() if ex_player.sold_at else None,
            # Partidos que jugó de verdad con nosotros. None mientras el censo
            # no haya pasado por él: es una alineación por partido, así que la
            # pantalla dice "sin contar" en vez de inventar un cero.
            "gamesWithUs": ex_player.games_played_for_us,
            # Si ya no puede darnos nada más, y por qué.
            "resaleClosed": ex_player.resale_closed,
            "resaleClosedReason": ex_player.resale_closed_reason,
        }
    rate_ = team.currency_rate or 1.0
    htms_ahora = htms_motor.de_habilidades(
        p["age_years"],
        p["age_days"],
        **{c: p["skills"].get(c) for c in SKILL_COLS},
    )

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
            trained_skill,
            p["skills"].get(trained_skill, 0),
            p["age_years"],
            p["age_days"],
            setup=setup,
        )
        if trained_skill
        else None
    )
    weeks_to_next_pop = training_speed.weeks_to_next_level if training_speed else None
    # HL-15x #97: ritmo semanal REAL de la fórmula (1/semanas), no es el
    # acumulado real por partidos jugados (esa tabla posición→entrenamiento
    # todavía no está verificada, ver Nota en el panel), pero sí es un
    # porcentaje derivado de la fórmula comunitaria, no un valor observado.
    weekly_training_progress_pct = (
        round(training_speed.weekly_progress * 100, 1) if training_speed else None
    )
    # HL-141: fórmula de comunidad, distinta de un modelo de precio de
    # mercado. Sirve para contrastar contra el sueldo real que ya
    # reporta CHPP (arriba) y para proyectar el sueldo tras la próxima subida
    # de la habilidad entrenada. Solo cubre jugadores de campo, para un
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

    # HL-15x: gráficas ampliadas de la ficha, todo real, sin proyecciones.
    history_svc = PlayerHistoryQueryService(session)
    snapshot_history = await history_svc.snapshot_history(ht_player_id)
    match_rating_history = await history_svc.match_rating_history(ht_player_id)
    distributions = await history_svc.squad_distributions(team_id, ht_player_id, rate_)
    percentile = await history_svc.dominant_skill_percentile(team_id, ht_player_id)
    top_skill_distributions = await history_svc.top_skill_distributions(team_id, ht_player_id)
    experience_progress = await history_svc.experience_progress(ht_player_id)

    # "TT-ss" por punto, mismo filtro por `ht_league_id` que economy.py
    # (bug real corregido 2026-08-09: "la fila de WorldContext más reciente"
    # daba cualquier país al azar en cuanto había más de uno).
    world = (
        await session.scalar(
            select(m.WorldContext).where(m.WorldContext.ht_league_id == team.ht_league_id)
        )
        if team.ht_league_id is not None
        else None
    )

    def _season_week(captured_at: str) -> str | None:
        when = datetime.fromisoformat(captured_at)
        return season_week_for_datetime(world, when)

    squad = await SquadQueryService(session).get(team_id)
    squad_player = (
        next((sp for sp in squad.players if sp.ht_player_id == ht_player_id), None)
        if squad is not None
        else None
    )

    # HL-15x, pedido explícito 2026-08-10: "cuándo entró al equipo" para el
    # punto más antiguo del radar, la compra real es más honesta que "la
    # primera vez que sincronizamos", que puede ser meses después de que el
    # jugador ya estaba en el club. `purchased_at_manual` (HL-161) es el
    # respaldo para jugadores que llegaron antes de que existiera el
    # tracking de compras; si tampoco hay eso, el radar sigue cayendo de
    # vuelta al primer snapshot real (sin inventar una fecha).
    player_row = await session.scalar(
        select(m.Player).where(m.Player.team_id == team_id, m.Player.ht_player_id == ht_player_id)
    )
    joined_at = (
        (player_row.purchased_at or player_row.purchased_at_manual)
        if player_row is not None
        else None
    )
    joined_season_week = _season_week(joined_at.isoformat()) if joined_at is not None else None
    # "Precio de compra" se declara "real, de transfersteam.xml", a
    # diferencia de arriba, aquí NUNCA se usa el respaldo manual, para no
    # ponerle un "TT-ss" real a una fecha que en realidad es una estimación.
    purchased_at_season_week = (
        _season_week(player_row.purchased_at.isoformat())
        if player_row is not None and player_row.purchased_at is not None
        else None
    )

    # HL-15x, pedido explícito 2026-08-10: ¿jugó esta semana?, señal simple
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
        purchase_date = (joined_at if joined_at.tzinfo else joined_at.replace(tzinfo=UTC)).date()
        days_since_purchase = max((datetime.now(UTC).date() - purchase_date).days, 0)
        loyalty_decimal = calculate_loyalty_decimal(days_since_purchase)

    # HL-15x, pedido explícito 2026-08-10: proyección de Resistencia (líneas
    # punteadas en "Evolución de habilidades") según la tabla de Federación
    # Ocerin, asume que el % de entrenamiento de resistencia actual se
    # mantiene constante hacia adelante; `None` solo si no hay WorldContext
    # propio (sin él no hay forma de etiquetar las "TT-ss" futuras). Las
    # edades fuera de la tabla ya no cortan la proyección: desde 2026-08-15
    # `stamina_forecast_level` recorta la edad al extremo más cercano.
    stamina_forecast: dict[str, Any] | None = None
    if world is not None:
        current_stamina_pct = setup.effective_stamina_intensity
        forecast_season_weeks: list[str | None] = []
        forecast_levels: list[int] = []
        for weeks_ahead in range(1, 9):
            proj_years, proj_days = age_after_weeks(p["age_years"], p["age_days"], weeks_ahead)
            level = stamina_forecast_level(proj_years, current_stamina_pct)
            forecast_season_weeks.append(season_week_label(world, weeks_offset=weeks_ahead))
            forecast_levels.append(level)
        # Nivel esperado HOY con el % real actual, la barrita de Resistencia
        # lo compara contra el nivel real (`p["stamina"]`) para decidir si el
        # rojo se agrega (sube) o se come parte del azul (baja).
        current_expected_level = stamina_forecast_level(p["age_years"], current_stamina_pct)
        if forecast_levels:
            stamina_forecast = {
                "seasonWeeks": forecast_season_weeks,
                "levels": forecast_levels,
                "trainingPct": round(current_stamina_pct, 1),
                "currentExpectedLevel": current_expected_level,
            }

    # HL-15x #87: preclasificación de "en qué momento de su vida está", motor
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
        age_years=p["age_years"],
        age_days=p["age_days"],
        skills_rising=skills_rising,
        skills_falling=skills_falling,
        skills_stable=skills_stable,
        has_sufficient_history=has_sufficient_history,
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
        "tsi": p["tsi"],
        "form": p["form"],
        "stamina": p["stamina"],
        "experience": p["experience"],
        "salary": int(round(p["salary"] / rate_)),
        "injuryLevel": p["injury_level"],
        # Datos de ficha: son observaciones directas de players.xml y
        # playerdetails.xml. Se exponen separados de cualquier cálculo Lens
        # para que la vista Detalles pueda conservar el lenguaje de HC.
        "countryId": squad_player.country_id if squad_player is not None else 0,
        "countryCode": squad_player.country_code if squad_player is not None else None,
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
            {
                "position": r.position,
                "label": r.label,
                "rating": r.rating,
                "isSpecialRole": r.is_special_role,
            }
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
        # con la selección nacional?", Caps/CapsU20 de playerdetails.xml,
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
        "nativeLeagueName": (squad_player.native_league_name if squad_player is not None else None),
        # HTMS del momento: el mismo numero que ve la comunidad en Foxtrick,
        # calculado aqui (docs/reference/htms_formulas_hattrick.html).
        "htms": htms_ahora.ability,
        "htms28": htms_ahora.potential,
        "purchasePrice": squad_player.purchase_price if squad_player is not None else None,
        "purchasedAt": squad_player.purchased_at if squad_player is not None else None,
        "careerStage": {
            "stage": career_stage.stage,
            "label": career_stage.label,
            "rationale": career_stage.rationale,
            "confidence": career_stage.confidence,
            "signals": career_stage.signals,
            # HL-15x #93: confirmación manual del usuario, si la hay, la app
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
                "league": squad_player.league_goals,
                "cup": squad_player.cup_goals,
                "friendlies": squad_player.friendlies_goals,
                "career": squad_player.career_goals,
                "hattricks": squad_player.career_hattricks,
                "assists": squad_player.career_assists,
            }
            if squad_player is not None
            else None
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
            if squad_player is not None
            else None
        ),
        # HL-15x #5: timeline real de las 9 variables (7 skills + experiencia
        # + fidelidad) + TSI + salario, tal cual está en player_snapshots
        # hoy puede tener pocos puntos (cuenta nueva), se devuelve así.
        "history": {
            "dates": [pt.captured_at for pt in snapshot_history],
            "seasonWeeks": [_season_week(pt.captured_at) for pt in snapshot_history],
            "tsi": [pt.tsi for pt in snapshot_history],
            "salary": [int(round(pt.salary / rate_)) for pt in snapshot_history],
            "skills": {
                col: [pt.skills[col] for pt in snapshot_history] for col in HISTORY_SKILL_COLS
            },
            "htms": [pt.htms for pt in snapshot_history],
            "htms28": [pt.htms28 for pt in snapshot_history],
        },
        # HL-15x #21: histórico real de rating por partido (tabla aparte,
        # append-only), puede estar vacío si playerdetails no se ha
        # sincronizado nunca para este jugador.
        "matchRatingHistory": [
            {
                "matchId": pt.ht_match_id,
                "date": pt.captured_at,
                "seasonWeek": _season_week(pt.captured_at),
                "rating": pt.rating,
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
                    "grid": dist.grid,
                    "density": dist.density,
                    "values": dist.values,
                    "ownValue": dist.own_value,
                }
                for key, dist in distributions.items()
            }
            if distributions is not None
            else None
        ),
        # HL-15x #23: percentil en su skill dominante dentro de la plantilla
        # sigue calculándose (lo usa el motor de preclasificación), pero ya
        # no se muestra como panel propio: HL-15x #99 lo reemplaza por los
        # histogramas de abajo.
        "percentile": percentile,
        # HL-15x #11: % real hacia la próxima subida de experiencia, Manual
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
            if experience_progress is not None
            else None
        ),
        # HL-15x #99: histogramas KDE de las 3 habilidades más altas del
        # jugador (sin Balón Parado), cada una con su plantilla real.
        "topSkillDistributions": (
            {
                key: {
                    "grid": dist.grid,
                    "density": dist.density,
                    "values": dist.values,
                    "ownValue": dist.own_value,
                }
                for key, dist in top_skill_distributions.items()
            }
            if top_skill_distributions is not None
            else None
        ),
        # HL-15x #22: TSI vs. edad de toda la plantilla activa, para
        # dispersión, ya calculado arriba (`players`, de `roster()`), sin
        # query nueva.
        "squadAgeTsi": [
            {
                "htPlayerId": x["ht_player_id"],
                "name": x["name"],
                "age": round(x["age_years"] + x["age_days"] / 112, 2),
                "tsi": x["tsi"],
            }
            for x in players
        ],
    }


@router.get(
    "/teams/{team_id}/players/{ht_player_id}/training/levels",
    summary="Subidas confirmadas y previsión de niveles futuros de un jugador",
    dependencies=[Depends(require_team_owner)],
)
async def player_training_levels(
    team_id: int,
    ht_player_id: int,
    skill: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """«Mejoras» (subidas confirmadas por trainingevents) y «Previsión
    subidas» (cascada de niveles futuros con la fórmula) para un jugador
    la vista individual de Hattrick Control."""
    history = await TrainingSquadQueryService(session).player_levels(
        team_id, ht_player_id, skill=skill
    )
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
