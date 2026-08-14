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
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.squad import SKILL_COLS
from app.application.queries.player_history import PlayerHistoryQueryService
from app.application.queries.training_context import TrainingContextService
from app.application.queries.weekly import (
    SEASON_WEEKS,
    latest_per_iso_week,
    season_week_offset_for,
    season_week_label,
    season_week_for_datetime,
)
from app.domain.engines import training_engine as te
from app.domain.engines.loyalty_engine import days_for_level, loyalty_decimal, loyalty_level
from app.domain.value_objects.ht_constants import SKILL_LABELS, skill_name, training_name
from app.infrastructure.db import models as m

# Resistencia vive en su motor de referencia propio y no se mezcla con esta
# fórmula de habilidades técnicas.
TRAINABLE_SKILLS: dict[str, str] = dict(SKILL_LABELS)
SKILL_ORDER: list[str] = [
    "keeper", "defending", "playmaking", "passing", "winger", "scoring", "set_pieces",
]


def _level_of(player_row: dict[str, Any], skill: str) -> int:
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
class ExperienceRow:
    ht_player_id: int
    name: str
    native_country: str | None
    age_years: int
    age_days: int
    level: int
    level_name: str
    decimal_level: float | None
    points: float | None
    points_per_level: float
    remaining_points: float | None
    progress_pct: int | None
    breakdown: dict[str, float]
    unscored_national_matches: int


@dataclass
class LoyaltyRow:
    ht_player_id: int
    name: str
    native_country: str | None
    age_years: int
    age_days: int
    reported_level: int
    calculated_level: int | None
    level_name: str
    decimal_level: float | None
    progress_pct: int | None
    days_in_club: int | None
    next_level: int | None
    days_to_next_level: int | None
    date_source: str | None


@dataclass
class DevelopmentView:
    experience: list[ExperienceRow]
    loyalty: list[LoyaltyRow]
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
                "experience": snap.experience,
                "loyalty": snap.loyalty,
                "purchased_at": ident.purchased_at,
                "purchased_at_manual": ident.purchased_at_manual,
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
                season_week_for_datetime(world, snap.captured_at)
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

    async def _snapshot_pop_weeks(
        self,
        team_id: int,
        skill: str,
        current_levels: dict[int, int],
        world: m.WorldContext | None,
        include_this_week: bool,
    ) -> dict[int, int]:
        """Use an observed snapshot increase when CHPP exposes no event.

        This is still real evidence: Lens saw the skill change between two
        ``players.xml`` snapshots. The exact day inside that interval is not
        known, so the first sync containing the new level becomes the baseline
        and elapsed time is deliberately kept at whole-week precision.

        NULL stays distinct from level 0. Older rows created before a skill
        field existed can be NULL, and NULL -> 13 must never become a fake pop.
        """
        if world is None or skill not in SKILL_ORDER:
            return {}

        skill_column = getattr(m.PlayerSnapshot, skill)
        observed = (
            await self._s.execute(
                select(
                    m.Player.ht_player_id,
                    m.PlayerSnapshot.captured_at,
                    skill_column,
                )
                .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
                .where(
                    m.Player.team_id == team_id,
                    m.Player.left_team_at.is_(None),
                )
                .order_by(m.Player.ht_player_id, m.PlayerSnapshot.captured_at)
            )
        ).all()

        previous: dict[int, int] = {}
        first_seen_at_current: dict[int, Any] = {}
        for ht_player_id, captured_at, observed_level in observed:
            if observed_level is None:
                continue
            level = int(observed_level)
            old_level = previous.get(ht_player_id)
            if (
                old_level is not None
                and level > old_level
                and level == current_levels.get(ht_player_id)
            ):
                first_seen_at_current[ht_player_id] = captured_at
            previous[ht_player_id] = level

        weeks: dict[int, int] = {}
        for ht_player_id, captured_at in first_seen_at_current.items():
            elapsed = -season_week_offset_for(world, captured_at)
            if not include_this_week:
                elapsed -= 1
            weeks[ht_player_id] = max(0, elapsed)
        return weeks

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
        setup = replace(
            ctx.setup,
            skill=chosen_skill,
            training_type=(ctx.setup.training_type if chosen_skill == ctx.trained_skill else None),
        )
        world = await self._world(team)
        skill_id = _skill_id_for(chosen_skill)

        now_week: int | None = None
        if world is not None and world.season is not None and world.match_round is not None:
            now_week = world.season * SEASON_WEEKS + world.match_round

        pops_by_player: dict[int, list[m.SkillUp]] = {}
        if skill_id is not None:
            for u in await self._pops_for_skill(team_id, skill_id):
                pops_by_player.setdefault(u.ht_player_id, []).append(u)

        roster = await self._roster(team_id)
        current_levels = {
            p["ht_player_id"]: _level_of(p, chosen_skill)
            for p in roster
        }
        snapshot_pop_weeks = await self._snapshot_pop_weeks(
            team_id,
            chosen_skill,
            current_levels,
            world,
            include_this_week,
        )

        rows: list[SquadTrainingRow] = []
        snapshot_references_used = 0
        for p in roster:
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
            elif p["ht_player_id"] in snapshot_pop_weeks:
                weeks_elapsed = snapshot_pop_weeks[p["ht_player_id"]]
                snapshot_references_used += 1

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

        if snapshot_references_used:
            notes.append(
                f"En {snapshot_references_used} jugador(es), trainingevents.xml no expuso "
                "el historial y se usó como referencia la primera sincronización real "
                "donde Lens observó el nuevo nivel."
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

    async def development_view(self, team_id: int) -> DevelopmentView | None:
        """Progreso de Experiencia y Fidelidad para toda la plantilla.

        Experiencia reutiliza el historial real de partidos/minutos del motor
        de experiencia. Fidelidad reutiliza exclusivamente la fecha de llegada
        y la curva temporal acordada; no ajusta ninguna regresión con datos de
        la cuenta.
        """
        team = await self._s.get(m.Team, team_id)
        if team is None:
            return None

        roster = await self._roster(team_id)
        history = PlayerHistoryQueryService(self._s)
        experience_rows: list[ExperienceRow] = []
        loyalty_rows: list[LoyaltyRow] = []
        missing_purchase_dates = 0
        today = datetime.now(UTC).date()

        for player in roster:
            progress = await history.experience_progress(player["ht_player_id"])
            level = int(player["experience"])
            fraction = (
                progress.points / progress.points_per_level
                if progress is not None and progress.points_per_level > 0
                else None
            )
            experience_rows.append(ExperienceRow(
                ht_player_id=player["ht_player_id"],
                name=player["name"],
                native_country=player["native_country"],
                age_years=player["age_years"],
                age_days=player["age_days"],
                level=level,
                level_name=skill_name(level),
                decimal_level=(round(level + fraction, 2) if fraction is not None else None),
                points=(progress.points if progress is not None else None),
                points_per_level=(progress.points_per_level if progress is not None else 100.0),
                remaining_points=(progress.remaining_points if progress is not None else None),
                progress_pct=(progress.percent if progress is not None else None),
                breakdown=(progress.breakdown if progress is not None else {}),
                unscored_national_matches=(
                    progress.unscored_national_matches if progress is not None else 0
                ),
            ))

            joined_at = player["purchased_at"] or player["purchased_at_manual"]
            date_source = (
                "transferencia" if player["purchased_at"] is not None
                else "manual" if player["purchased_at_manual"] is not None
                else None
            )
            days_in_club: int | None = None
            calculated: int | None = None
            decimal: float | None = None
            next_level: int | None = None
            days_to_next: int | None = None
            progress_pct: int | None = None
            if joined_at is not None:
                joined_date = (
                    joined_at if joined_at.tzinfo else joined_at.replace(tzinfo=UTC)
                ).date()
                days_in_club = max((today - joined_date).days, 0)
                calculated = loyalty_level(days_in_club)
                decimal = loyalty_decimal(days_in_club)
                if calculated is not None and decimal is not None:
                    if calculated >= 20:
                        progress_pct = 100
                    else:
                        progress_pct = int(round((decimal - calculated) * 100))
                        next_level = calculated + 1
                        days_to_next = max(days_for_level(next_level) - days_in_club, 0)
            else:
                missing_purchase_dates += 1

            display_level = calculated if calculated is not None else int(player["loyalty"])
            loyalty_rows.append(LoyaltyRow(
                ht_player_id=player["ht_player_id"],
                name=player["name"],
                native_country=player["native_country"],
                age_years=player["age_years"],
                age_days=player["age_days"],
                reported_level=int(player["loyalty"]),
                calculated_level=calculated,
                level_name=skill_name(display_level),
                decimal_level=decimal,
                progress_pct=progress_pct,
                days_in_club=days_in_club,
                next_level=next_level,
                days_to_next_level=days_to_next,
                date_source=date_source,
            ))

        experience_rows.sort(key=lambda row: (row.progress_pct is None, -(row.progress_pct or 0)))
        loyalty_rows.sort(key=lambda row: (row.days_in_club is None, -(row.days_in_club or 0)))
        notes = [
            "Experiencia suma los puntos de partidos y minutos reales observados desde el nivel "
            "actual; no estima partidos anteriores al primer snapshot disponible.",
            "Fidelidad usa solo días calendario desde la compra o la fecha manual de llegada y "
            "la curva temporal acordada.",
        ]
        if missing_purchase_dates:
            notes.append(
                f"{missing_purchase_dates} jugador(es) no tienen fecha de llegada: se muestra el "
                "nivel CHPP, pero no un progreso decimal inventado."
            )
        return DevelopmentView(
            experience=experience_rows,
            loyalty=loyalty_rows,
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
        setup = replace(
            ctx.setup,
            skill=chosen_skill,
            training_type=(ctx.setup.training_type if chosen_skill == ctx.trained_skill else None),
        )

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
