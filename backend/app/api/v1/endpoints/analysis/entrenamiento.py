"""Entrenamiento: prevision, formula y reparto de minutos.

Sale de partir `analysis.py`, que tenia 2309 lineas y se abria
entera para tocar cualquiera de sus rutas. El `__init__.py` del paquete
monta `router` con todos estos, asi que las URL no cambian.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_team_owner
from app.api.v1.endpoints.analysis.plantilla import roster
from app.application.queries.post_match_training import PostMatchTrainingService
from app.application.queries.training_context import TrainingContextService
from app.application.queries.training_squad import TrainingSquadQueryService
from app.application.queries.ultimo_entrenamiento import (
    UltimoEntrenamientoQueryService,
    como_json,
)
from app.domain.engines.training_engine import (
    default_setup as default_training_setup,
)
from app.domain.engines.training_engine import (
    model_info as training_model_info,
)
from app.domain.engines.training_engine import (
    training_mode,
    weeks_to_next_level,
)
from app.domain.value_objects.ht_constants import (
    training_target,
)
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session

router = APIRouter()


@router.get(
    "/teams/{team_id}/training/forecast",
    summary="Previsión de subidas (HL-034)",
    dependencies=[Depends(require_team_owner)],
)
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
        out.append(
            {
                "player": p["name"],
                "htPlayerId": p["ht_player_id"],
                "age": f"{p['age_years']}.{p['age_days']}",
                "currentLevel": p["skills"].get(skill, 0),
                "weeksToPop": round(speed.weeks_to_next_level, 1),
            }
        )
    out.sort(key=lambda x: x["weeksToPop"])
    return {
        "trainingType": tr.training_type if tr else None,
        "trainedSkill": skill,
        "exposure": round(setup.effective_intensity, 3),
        "players": out,
    }


@router.get(
    "/teams/{team_id}/training/formula",
    summary="La fórmula de entrenamiento con la procedencia de cada valor (HL-030)",
    dependencies=[Depends(require_team_owner)],
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
    summary="Vista de plantilla por entrenamiento, la pestaña que HC deja vacía",
    dependencies=[Depends(require_team_owner)],
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
        team_id,
        skill=skill,
        include_this_week=include_this_week,
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
                "countryCode": r.country_code,
                "age": f"{r.age_years}.{r.age_days}",
                "level": r.level,
                "levelName": r.level_name,
                "weeksElapsed": r.weeks_elapsed,
                "weeksTotal": r.weeks_total,
                "progressPct": r.progress_pct,
                "hasReference": r.has_reference,
                "hasHistoricalReference": r.has_historical_reference,
                "lastImprovement": r.last_improvement,
                "currentWeekMinutes": r.current_week_minutes,
                "currentWeekExposure": r.current_week_exposure,
                "withoutFieldSkills": r.without_field_skills,
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
    dependencies=[Depends(require_team_owner)],
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
                "countryCode": row.country_code,
                "age": f"{row.age_years}.{row.age_days}",
                "level": row.level,
                "levelName": row.level_name,
                "decimalLevel": row.decimal_level,
                "points": row.points,
                "pointsPerLevel": row.points_per_level,
                "remainingPoints": row.remaining_points,
                "progressPct": row.progress_pct,
                "breakdown": row.breakdown,
                "matchCounts": row.match_counts,
                "lastImprovement": row.last_improvement,
                "unscoredNationalMatches": row.unscored_national_matches,
            }
            for row in view.experience
        ],
        "loyalty": [
            {
                "htPlayerId": row.ht_player_id,
                "name": row.name,
                "nativeCountry": row.native_country,
                "countryCode": row.country_code,
                "age": f"{row.age_years}.{row.age_days}",
                "reportedLevel": row.reported_level,
                "calculatedLevel": row.calculated_level,
                "levelName": row.level_name,
                "decimalLevel": row.decimal_level,
                "progressPct": row.progress_pct,
                "daysInClub": row.days_in_club,
                "lastImprovement": row.last_improvement,
                "nextLevel": row.next_level,
                "daysToNextLevel": row.days_to_next_level,
                "dateSource": row.date_source,
            }
            for row in view.loyalty
        ],
        "stamina": [
            {
                "htPlayerId": row.ht_player_id,
                "name": row.name,
                "nativeCountry": row.native_country,
                "countryCode": row.country_code,
                "age": f"{row.age_years}.{row.age_days}",
                "level": row.level,
                "levelName": row.level_name,
                "effectiveTrainingPct": row.effective_training_pct,
                "expectedLevel": row.expected_level,
                "expectedLevelName": row.expected_level_name,
                "trend": row.trend,
                "lastImprovement": row.last_improvement,
            }
            for row in view.stamina
        ],
        "notes": view.notes,
    }


@router.get(
    "/teams/{team_id}/training/post-match",
    summary="Entrenamiento decidido a posteriori",
    dependencies=[Depends(require_team_owner)],
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


@router.get(
    "/teams/{team_id}/training/last",
    summary="El parte de la última actualización de entrenamiento",
    dependencies=[Depends(require_team_owner)],
)
async def ultimo_entrenamiento(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Qué pasó en la última actualización semanal: cuándo fue, con qué
    entrenamiento puesto y quién subió.

    El «cuándo» no se adivina: Hattrick publica la hora de la actualización de
    cada liga y se retrocede desde ahí. Las subidas son las que el propio
    Hattrick confirma, no diferencias entre fotos.
    """
    parte = await UltimoEntrenamientoQueryService(session).get(team_id)
    if parte is None:
        raise HTTPException(404, f"team {team_id} not found")
    return como_json(parte)
