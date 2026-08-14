"""TrainingSquadQueryService — vista de plantilla al estilo Hattrick Control.

La pestaña que HC deja vacía: cuánto le falta a CADA jugador para su próximo
nivel — no solo el próximo pop de la habilidad que el club entrena hoy.
Reutiliza `TrainingContextService` para el `TrainingSetup` real (ayudantes,
entrenador, intensidad, condición) leído del CHPP, pero permite elegir
cualquier habilidad entrenable para mirarla, igual que
`compare_training_types` en el motor — solo que aquí es por jugador, con su
nivel y nombre reales, no un promedio de escuadra.

SEMANAS TRANSCURRIDAS. Hattrick Control corre en segundo plano y puede medir
esto con precisión de día. Lens sincroniza bajo demanda, así que no se
inventa esa precisión: se cuentan semanas de temporada completas desde la
última subida CONFIRMADA (trainingevents) que trajo al jugador a su nivel
actual — el mismo criterio que ya usa `TrainingContextService` para validar
la fórmula. Sin esa subida confirmada no hay semanas transcurridas que
mostrar, y se dice explícitamente en vez de poner un cero.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.squad import SKILL_COLS
from app.application.queries.training_context import TrainingContextService
from app.application.queries.weekly import (
    SEASON_WEEKS,
    latest_per_iso_week,
    season_week_label,
    season_week_offset_for,
)
from app.domain.engines import training_engine as te
from app.domain.value_objects.ht_constants import SKILL_LABELS, skill_name, training_name
from app.infrastructure.db import models as m

# `stamina` es entrenable (base_weeks la incluye) pero vive en su propia
# columna de PlayerSnapshot, no en el diccionario `skills` de las 7 técnicas.
TRAINABLE_SKILLS: dict[str, str] = {**SKILL_LABELS, "stamina": "Resistencia"}
SKILL_ORDER: list[str] = [
    "stamina", "keeper", "defending", "playmaking", "passing", "winger", "scoring", "set_pieces",
]


def _level_of(player_row: dict[str, Any], skill: str) -> int:
    if skill == "stamina":
        return int(player_row.get("stamina") or 0)
    return int(player_row.get("skills", {}).get(skill, 0))


def _skill_id_for(skill: str) -> int | None:
    cfg = te._config()
    for sid, name in cfg["skill_id_map"].items():
        if name == skill:
            return int(sid)
    return None


@dataclass
class SquadTrainingRow:
    ht_player_id: int
    name: str
    native_country: str | None
    age_years: int
    age_days: int
    level: int
    level_name: str
    weeks_elapsed: int | None
    weeks_total: float
    progress_pct: float | None
    has_reference: bool


@dataclass
class WeeklyLogEntry:
    season_week: str | None
    date: str
    training_type: str
    intensity: int
    stamina_share: int
    trainer_name: str


@dataclass
class TrainingSquadView:
    skill: str
    skill_label: str
    available_skills: list[tuple[str, str]]
    setup: te.TrainingSetup
    rows: list[SquadTrainingRow]
    weekly_log: list[WeeklyLogEntry]
    include_this_week: bool
    notes: list[str] = field(default_factory=list)


@dataclass
class ConfirmedPop:
    season_week: str
    from_level: int
    from_level_name: str
    to_level: int
    to_level_name: str
    weeks_between: int | None


@dataclass
class ForecastMilestone:
    level: int
    level_name: str
    weeks_for_this_level: float
    weeks_from_now: float
    season_week: str | None
    age_years: int
    age_days: int


@dataclass
class PlayerTrainingHistory:
    ht_player_id: int
    name: str
    skill: str
    skill_label: str
    current_level: int
    current_level_name: str
    confirmed: list[ConfirmedPop]
    forecast: list[ForecastMilestone]
    notes: list[str] = field(default_factory=list)


class TrainingSquadQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def _world(self, team: m.Team) -> m.WorldContext | None:
        if team.ht_league_id is None:
            return None
        return await self._s.scalar(
            select(m.WorldContext).where(m.WorldContext.ht_league_id == team.ht_league_id)
        )

    async def _roster(self, team_id: int) -> list[dict[str, Any]]:
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
            await self._s.execute(
                select(m.PlayerSnapshot, m.Player)
                .join(
                    latest,
                    (m.PlayerSnapshot.player_id == latest.c.pid)
                    & (m.PlayerSnapshot.captured_at == latest.c.mx),
                )
                .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
            )
        ).all()
        return [
            {
                "ht_player_id": ident.ht_player_id,
                "name": f"{ident.first_name} {ident.last_name}",
                "native_country": ident.native_country,
                "age_years": snap.age_years,
                "age_days": snap.age_days,
                "stamina": snap.stamina,
                "skills": {c: getattr(snap, c) or 0 for c in SKILL_COLS},
            }
            for snap, ident in rows
        ]

    async def _weekly_log(self, team_id: int, world: m.WorldContext | None, limit: int = 12) -> list[WeeklyLogEntry]:
        rows = (
            await self._s.execute(
                select(m.TrainingSnapshot)
                .where(m.TrainingSnapshot.team_id == team_id)
                .order_by(m.TrainingSnapshot.captured_at)
            )
        ).scalars().all()
        deduped = list(reversed(latest_per_iso_week(rows, lambda r: r.captured_at)))[:limit]
        out = []
        for snap in deduped:
            season_week = (
                season_week_label(world, weeks_offset=season_week_offset_for(world, snap.captured_at))
                if world is not None else None
            )
            out.append(WeeklyLogEntry(
                season_week=season_week,
                date=snap.captured_at.date().isoformat(),
                training_type=training_name(snap.training_type),
                intensity=snap.training_level,
                stamina_share=snap.stamina_part,
                trainer_name=snap.trainer_name,
            ))
        return out

    async def _pops_for_skill(
        self, team_id: int, skill_id: int, ht_player_id: int | None = None,
    ) -> list[m.SkillUp]:
        conditions = [m.SkillUp.team_id == team_id, m.SkillUp.skill_id == skill_id]
        if ht_player_id is not None:
            conditions.append(m.SkillUp.ht_player_id == ht_player_id)
        rows = (
            await self._s.execute(
                select(m.SkillUp).where(*conditions)
                .order_by(m.SkillUp.ht_player_id, m.SkillUp.season, m.SkillUp.match_round)
            )
        ).scalars().all()
        return list(rows)

    async def squad_view(
        self, team_id: int, skill: str | None = None, include_this_week: bool = True,
    ) -> TrainingSquadView | None:
        team = await self._s.get(m.Team, team_id)
        if team is None:
            return None
        ctx = await TrainingContextService(self._s).get(team_id)
        if ctx is None:
            return None

        chosen_skill = skill or ctx.trained_skill
        setup = replace(ctx.setup, skill=chosen_skill)
        world = await self._world(team)
        skill_id = _skill_id_for(chosen_skill)

        now_week: int | None = None
        if world is not None and world.season is not None and world.match_round is not None:
            now_week = world.season * SEASON_WEEKS + world.match_round

        pops_by_player: dict[int, list[m.SkillUp]] = {}
        if skill_id is not None:
            for u in await self._pops_for_skill(team_id, skill_id):
                pops_by_player.setdefault(u.ht_player_id, []).append(u)

        rows: list[SquadTrainingRow] = []
        for p in await self._roster(team_id):
            level = _level_of(p, chosen_skill)
            speed = te.weeks_to_next_level(chosen_skill, level, p["age_years"], p["age_days"], setup=setup)
            weeks_total = speed.weeks_to_next_level

            weeks_elapsed: int | None = None
            last_pop = next(
                (u for u in pops_by_player.get(p["ht_player_id"], []) if u.new_level == level), None,
            )
            if last_pop is not None and now_week is not None:
                pop_week = last_pop.season * SEASON_WEEKS + last_pop.match_round
                elapsed = now_week - pop_week - (0 if include_this_week else 1)
                weeks_elapsed = max(0, elapsed)

            progress_pct = (
                round(weeks_elapsed / weeks_total * 100, 1)
                if weeks_elapsed is not None and weeks_total > 0 else None
            )

            rows.append(SquadTrainingRow(
                ht_player_id=p["ht_player_id"], name=p["name"], native_country=p["native_country"],
                age_years=p["age_years"], age_days=p["age_days"],
                level=level, level_name=skill_name(level),
                weeks_elapsed=weeks_elapsed, weeks_total=weeks_total,
                progress_pct=progress_pct, has_reference=weeks_elapsed is not None,
            ))

        rows.sort(key=lambda r: (r.progress_pct is None, -(r.progress_pct or 0)))

        notes: list[str] = []
        if skill_id is None:
            notes.append(
                f"«{TRAINABLE_SKILLS.get(chosen_skill, chosen_skill)}» no tiene SkillID de "
                "trainingevents mapeado; no se pueden medir semanas transcurridas."
            )
        if now_week is None:
            notes.append(
                "Sin worlddetails.xml sincronizado no se puede fijar la semana actual — "
                "las semanas transcurridas quedan sin dato para todos."
            )

        return TrainingSquadView(
            skill=chosen_skill,
            skill_label=TRAINABLE_SKILLS.get(chosen_skill, chosen_skill),
            available_skills=[(s, TRAINABLE_SKILLS[s]) for s in SKILL_ORDER],
            setup=setup,
            rows=rows,
            weekly_log=await self._weekly_log(team_id, world),
            include_this_week=include_this_week,
            notes=notes,
        )

    async def player_levels(
        self, team_id: int, ht_player_id: int, skill: str | None = None,
    ) -> PlayerTrainingHistory | None:
        team = await self._s.get(m.Team, team_id)
        if team is None:
            return None
        ctx = await TrainingContextService(self._s).get(team_id)
        if ctx is None:
            return None

        chosen_skill = skill or ctx.trained_skill
        setup = replace(ctx.setup, skill=chosen_skill)

        player_row = next(
            (p for p in await self._roster(team_id) if p["ht_player_id"] == ht_player_id), None,
        )
        if player_row is None:
            return None
        level = _level_of(player_row, chosen_skill)
        skill_id = _skill_id_for(chosen_skill)

        confirmed: list[ConfirmedPop] = []
        if skill_id is not None:
            prev: m.SkillUp | None = None
            for u in await self._pops_for_skill(team_id, skill_id, ht_player_id):
                weeks_between = (
                    (u.season - prev.season) * SEASON_WEEKS + (u.match_round - prev.match_round)
                    if prev is not None else None
                )
                confirmed.append(ConfirmedPop(
                    season_week=f"{u.season:02d}-{u.match_round:02d}",
                    from_level=u.old_level, from_level_name=skill_name(u.old_level),
                    to_level=u.new_level, to_level_name=skill_name(u.new_level),
                    weeks_between=weeks_between,
                ))
                prev = u

        world = await self._world(team)
        chain = te.forecast_level_chain(
            chosen_skill, level, player_row["age_years"], player_row["age_days"], setup,
        )
        forecast = [
            ForecastMilestone(
                level=milestone.level,
                level_name=skill_name(milestone.level),
                weeks_for_this_level=milestone.weeks_for_this_level,
                weeks_from_now=milestone.weeks_from_now,
                season_week=(
                    season_week_label(world, weeks_offset=round(milestone.weeks_from_now))
                    if world is not None else None
                ),
                age_years=milestone.age_years,
                age_days=milestone.age_days,
            )
            for milestone in chain
        ]

        notes: list[str] = []
        if skill_id is None:
            notes.append(
                f"«{TRAINABLE_SKILLS.get(chosen_skill, chosen_skill)}» no tiene SkillID de "
                "trainingevents mapeado; no hay subidas confirmadas que mostrar."
            )
        elif not confirmed:
            notes.append("Todavía no hay subidas confirmadas de esta habilidad para este jugador.")

        return PlayerTrainingHistory(
            ht_player_id=ht_player_id, name=player_row["name"],
            skill=chosen_skill, skill_label=TRAINABLE_SKILLS.get(chosen_skill, chosen_skill),
            current_level=level, current_level_name=skill_name(level),
            confirmed=confirmed, forecast=forecast, notes=notes,
        )
