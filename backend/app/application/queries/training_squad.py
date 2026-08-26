"""TrainingSquadQueryService — vista de plantilla al estilo Hattrick Control.

La pestaña que HC deja vacía: cuánto le falta a CADA jugador para su próximo
nivel — no solo el próximo pop de la habilidad que el club entrena hoy.
Reutiliza `TrainingContextService` para el `TrainingSetup` real (ayudantes,
entrenador, intensidad, condición) leído del CHPP, pero permite elegir
cualquier habilidad entrenable para mirarla, igual que
`compare_training_types` en el motor — solo que aquí es por jugador, con su
nivel y nombre reales, no un promedio de escuadra.

SEMANAS TRANSCURRIDAS. Lens no reconstruye el subnivel anterior a la primera
lectura de un jugador. Desde esa lectura sí acumula cada exposición semanal
demostrada por entrenamiento, posición y minutos reales. Cuando observa que
el nivel entero cambia, empieza un tramo nuevo desde la primera lectura del
nivel actual.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.player_history import PlayerHistoryQueryService
from app.application.queries.post_match_training import PostMatchTrainingService
from app.application.queries.squad import SKILL_COLS
from app.application.queries.training_context import TrainingContextService
from app.application.queries.weekly import (
    SEASON_WEEKS,
    latest_per_iso_week,
    season_week_for_datetime,
    season_week_label,
)
from app.domain.engines import training_engine as te
from app.domain.engines.loyalty_engine import (
    days_for_level,
    loyalty_decimal,
    loyalty_level,
    loyalty_progress_pct,
)
from app.domain.value_objects.ht_constants import SKILL_LABELS, skill_name, training_name
from app.domain.value_objects.stamina_reference import (
    STAMINA_MAX_TABLE_AGE,
    STAMINA_MIN_TABLE_AGE,
    stamina_forecast_level,
)
from app.infrastructure.db import models as m

# Resistencia vive en su motor de referencia propio y no se mezcla con esta
# fórmula de habilidades técnicas.
TRAINABLE_SKILLS: dict[str, str] = dict(SKILL_LABELS)
SKILL_ORDER: list[str] = [
    "keeper",
    "defending",
    "playmaking",
    "passing",
    "winger",
    "scoring",
    "set_pieces",
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
    country_code: str | None
    age_years: int
    age_days: int
    level: int
    level_name: str
    weeks_elapsed: float | None
    weeks_total: float
    progress_pct: float | None
    has_reference: bool
    has_historical_reference: bool
    current_week_minutes: float
    current_week_exposure: float
    # "83-03": la semana de la última subida confirmada. Cadena vacía
    # cuando no hay ninguna, que no es lo mismo que no haber mejorado nunca:
    # es que Hattrick no reporta ninguna.
    last_improvement: str = ""


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
    country_code: str | None
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
    match_counts: dict[str, int]
    unscored_national_matches: int
    # "83-03": la semana de la última subida confirmada. Cadena vacía
    # cuando no hay ninguna, que no es lo mismo que no haber mejorado nunca:
    # es que Hattrick no reporta ninguna.
    last_improvement: str = ""


@dataclass
class LoyaltyRow:
    ht_player_id: int
    name: str
    native_country: str | None
    country_code: str | None
    age_years: int
    age_days: int
    reported_level: int
    calculated_level: int | None
    level_name: str
    decimal_level: float | None
    progress_pct: float | None
    days_in_club: int | None
    next_level: int | None
    days_to_next_level: int | None
    date_source: str | None
    # "83-03": la semana de la última subida confirmada. Cadena vacía
    # cuando no hay ninguna, que no es lo mismo que no haber mejorado nunca:
    # es que Hattrick no reporta ninguna.
    last_improvement: str = ""


@dataclass
class StaminaRow:
    """Resistencia — HL-2xx, tabla comunitaria de Federación Ocerin
    (`stamina_reference.py`): a diferencia de Fidelidad/Experiencia, el
    nivel esperado puede subir O BAJAR según si el % REAL de esfuerzo en
    resistencia (intensidad × stamina_share, no el share crudo) alcanza
    para la edad del jugador."""

    ht_player_id: int
    name: str
    native_country: str | None
    country_code: str | None
    age_years: int
    age_days: int
    level: int
    level_name: str
    effective_training_pct: float
    expected_level: int | None
    expected_level_name: str | None
    trend: str  # "sube" | "baja" | "estable" | "sin_dato"
    last_improvement: str = ""


@dataclass
class DevelopmentView:
    experience: list[ExperienceRow]
    loyalty: list[LoyaltyRow]
    stamina: list[StaminaRow]
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
        country_rows = (
            await self._s.execute(
                select(
                    m.WorldContext.country_id,
                    m.WorldContext.country_code,
                    m.WorldContext.country_name,
                ).where(m.WorldContext.country_code != "")
            )
        ).all()
        country_codes = {
            int(country_id): str(country_code).upper()
            for country_id, country_code, _country_name in country_rows
        }
        country_names = {
            int(country_id): str(country_name)
            for country_id, _country_code, country_name in country_rows
            if country_name
        }
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
                "native_country": ident.native_country or country_names.get(snap.country_id),
                "country_code": country_codes.get(snap.country_id),
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

    async def _weekly_log(
        self, team_id: int, world: m.WorldContext | None, limit: int = 12
    ) -> list[WeeklyLogEntry]:
        rows = (
            (
                await self._s.execute(
                    select(m.TrainingSnapshot)
                    .where(m.TrainingSnapshot.team_id == team_id)
                    .order_by(m.TrainingSnapshot.captured_at)
                )
            )
            .scalars()
            .all()
        )
        deduped = list(reversed(latest_per_iso_week(rows, lambda r: r.captured_at)))[:limit]
        out = []
        for snap in deduped:
            season_week = (
                season_week_for_datetime(world, snap.captured_at) if world is not None else None
            )
            out.append(
                WeeklyLogEntry(
                    season_week=season_week,
                    date=snap.captured_at.date().isoformat(),
                    training_type=training_name(snap.training_type),
                    intensity=snap.training_level,
                    stamina_share=snap.stamina_part,
                    trainer_name=snap.trainer_name,
                )
            )
        return out

    async def _pops_for_skill(
        self,
        team_id: int,
        skill_id: int,
        ht_player_id: int | None = None,
    ) -> list[m.SkillUp]:
        conditions = [m.SkillUp.team_id == team_id, m.SkillUp.skill_id == skill_id]
        if ht_player_id is not None:
            conditions.append(m.SkillUp.ht_player_id == ht_player_id)
        rows = (
            (
                await self._s.execute(
                    select(m.SkillUp)
                    .where(*conditions)
                    .order_by(m.SkillUp.ht_player_id, m.SkillUp.season, m.SkillUp.match_round)
                )
            )
            .scalars()
            .all()
        )
        return list(rows)

    async def _observed_level_baselines(
        self,
        team_id: int,
        skill: str,
        current_levels: dict[int, int],
    ) -> dict[int, datetime]:
        """Primera lectura del tramo continuo en el nivel entero actual.

        Una primera lectura no revela el subnivel anterior y por eso empieza
        en cero. Desde ese momento sí permite conservar todas las semanas
        fraccionarias que Lens compruebe. Un cambio posterior de nivel reinicia
        la base. ``NULL`` nunca se interpreta como nivel cero ni como pop.
        """
        if skill not in SKILL_ORDER:
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

        baselines: dict[int, datetime] = {}
        for ht_player_id, captured_at, observed_level in observed:
            if observed_level is None:
                continue
            level = int(observed_level)
            if level == current_levels.get(ht_player_id):
                baselines.setdefault(ht_player_id, captured_at)
            else:
                # Si el historial vuelve más tarde al nivel actual, la primera
                # observación de ese nuevo tramo reemplazará la base anterior.
                baselines.pop(ht_player_id, None)
        return baselines

    async def _last_improvements(self, team_id: int) -> dict[tuple[int, int], str]:
        """La última subida confirmada de cada (jugador, habilidad), como
        "83-03".

        Sale de `skill_ups`, que guarda lo que reporta `trainingevents.xml`:
        Hattrick da temporada y jornada por separado, así que la etiqueta no se
        deduce de una fecha. Sin fila para ese par, no hay mejora que enseñar y
        la celda se queda vacía.
        """
        filas = (
            await self._s.execute(
                select(
                    m.SkillUp.ht_player_id,
                    m.SkillUp.skill_id,
                    m.SkillUp.season,
                    m.SkillUp.match_round,
                )
                .where(m.SkillUp.team_id == team_id)
                .order_by(m.SkillUp.season, m.SkillUp.match_round)
            )
        ).all()
        # Ordenado de más viejo a más nuevo: el último que se escribe gana.
        return {
            (fila.ht_player_id, fila.skill_id): f"{fila.season}-{fila.match_round:02d}"
            for fila in filas
        }

    async def _snapshot_improvements(self, team_id: int, campo: str) -> dict[int, str]:
        """La semana en que subió un campo de cada jugador, según el histórico.

        Fidelidad y Experiencia no llegan por `trainingevents` (la primera no
        está en el mapa de habilidades de Hattrick y de la segunda esta cuenta
        no tiene ni un evento), así que hay que verlas subir entre dos
        snapshots propios. Eso limita lo que se puede afirmar a la resolución
        de tus sincronizaciones y a desde cuándo sincronizas.
        """
        equipo = await self._s.get(m.Team, team_id)
        # Filtrado por liga, no "el WorldContext más reciente": con más de un
        # país guardado, ese atajo devolvía el calendario de otro y las semanas
        # salían de temporadas que no existen (fidelidad en 80-02 el
        # 2026-08-19, con la app sincronizando desde la 83).
        world = (
            await self._s.scalar(
                select(m.WorldContext).where(
                    m.WorldContext.ht_league_id == (equipo.ht_league_id if equipo else None)
                )
            )
            if equipo is not None and equipo.ht_league_id is not None
            else None
        )
        columna = getattr(m.PlayerSnapshot, campo)
        filas = (
            await self._s.execute(
                select(
                    m.Player.ht_player_id,
                    m.PlayerSnapshot.captured_at,
                    columna.label("valor"),
                )
                .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
                .where(m.Player.team_id == team_id)
                .order_by(m.Player.ht_player_id, m.PlayerSnapshot.captured_at)
            )
        ).all()
        ultimo: dict[int, int] = {}
        salida: dict[int, str] = {}
        for fila in filas:
            previo = ultimo.get(fila.ht_player_id)
            # `previo > 0`: la columna de fidelidad se añadió después del
            # primer sync y los snapshots viejos quedaron a 0. El salto de ese
            # 0 al primer valor real no es una subida, es la columna
            # estrenándose, y sin este filtro todos los jugadores compartían
            # la misma "mejora" de aquella semana.
            if previo and (fila.valor or 0) > previo:
                etiqueta = season_week_for_datetime(world, fila.captured_at)
                if etiqueta:
                    salida[fila.ht_player_id] = etiqueta
            ultimo[fila.ht_player_id] = fila.valor or 0
        return salida

    async def squad_view(
        self,
        team_id: int,
        skill: str | None = None,
        include_this_week: bool = True,
    ) -> TrainingSquadView | None:
        team = await self._s.get(m.Team, team_id)
        if team is None:
            return None
        ctx = await TrainingContextService(self._s).get(team_id)
        if ctx is None:
            return None
        mejoras = await self._last_improvements(team_id)

        chosen_skill = skill or ctx.trained_skill
        setup = replace(
            ctx.setup,
            skill=chosen_skill,
            training_type=(ctx.setup.training_type if chosen_skill == ctx.trained_skill else None),
        )
        world = await self._world(team)
        skill_id = _skill_id_for(chosen_skill)

        roster = await self._roster(team_id)
        current_levels = {p["ht_player_id"]: _level_of(p, chosen_skill) for p in roster}
        baselines = await self._observed_level_baselines(
            team_id,
            chosen_skill,
            current_levels,
        )
        observed_progress = await PostMatchTrainingService(
            self._s,
        ).observed_training_progress(
            team_id,
            chosen_skill,
            baselines,
            include_latest=include_this_week,
        )

        rows: list[SquadTrainingRow] = []
        for p in roster:
            level = _level_of(p, chosen_skill)
            speed = te.weeks_to_next_level(
                chosen_skill, level, p["age_years"], p["age_days"], setup=setup
            )
            weeks_total = speed.weeks_to_next_level
            observed = observed_progress.get(p["ht_player_id"])
            weeks_elapsed = observed.total_exposure if observed is not None else None
            current_week_exposure = observed.latest_exposure if observed is not None else 0.0
            current_week_minutes = (
                observed.latest_equivalent_minutes if observed is not None else 0.0
            )
            historical_exposure = (
                weeks_elapsed - current_week_exposure if weeks_elapsed is not None else 0.0
            )

            progress_pct = (
                round(weeks_elapsed / weeks_total * 100, 1)
                if weeks_elapsed is not None and weeks_total > 0
                else None
            )

            rows.append(
                SquadTrainingRow(
                    # La habilidad que se está mirando, no el parámetro crudo:
                    # `skill` llega vacío cuando se pide la vista por defecto.
                    last_improvement=mejoras.get((p["ht_player_id"], skill_id or -1), ""),
                    ht_player_id=p["ht_player_id"],
                    name=p["name"],
                    native_country=p["native_country"],
                    country_code=p["country_code"],
                    age_years=p["age_years"],
                    age_days=p["age_days"],
                    level=level,
                    level_name=skill_name(level),
                    weeks_elapsed=weeks_elapsed,
                    weeks_total=weeks_total,
                    progress_pct=progress_pct,
                    has_reference=weeks_elapsed is not None,
                    has_historical_reference=historical_exposure > 0.00005,
                    current_week_minutes=current_week_minutes,
                    current_week_exposure=current_week_exposure,
                )
            )

        rows.sort(key=lambda r: (r.progress_pct is None, -(r.progress_pct or 0)))

        notes: list[str] = []
        if skill_id is None:
            notes.append(
                f"No se puede medir el avance de «{TRAINABLE_SKILLS.get(chosen_skill, chosen_skill)}»: "  # noqa: E501
                "Hattrick no confirma subidas de esa habilidad."
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
        ctx = await TrainingContextService(self._s).get(team_id)

        roster = await self._roster(team_id)
        # Las mismas dos fuentes que en la vista de entrenamiento: lo que
        # Hattrick confirma y, para Fidelidad, el histórico propio.
        mejoras = await self._last_improvements(team_id)
        subidas_fidelidad = await self._snapshot_improvements(team_id, "loyalty")
        subidas_experiencia = await self._snapshot_improvements(team_id, "experience")
        history = PlayerHistoryQueryService(self._s)
        experience_rows: list[ExperienceRow] = []
        loyalty_rows: list[LoyaltyRow] = []
        stamina_rows: list[StaminaRow] = []
        missing_purchase_dates = 0
        players_outside_stamina_table = 0
        today = datetime.now(UTC).date()
        effective_stamina_pct = ctx.setup.effective_stamina_intensity if ctx is not None else 0.0

        for player in roster:
            progress = await history.experience_progress(player["ht_player_id"])
            level = int(player["experience"])
            fraction = (
                progress.points / progress.points_per_level
                if progress is not None and progress.points_per_level > 0
                else None
            )
            experience_rows.append(
                ExperienceRow(
                    # Del histórico propio: Hattrick no reporta subidas de
                    # experiencia por `trainingevents` (0 eventos en esta cuenta
                    # frente a decenas de habilidades).
                    last_improvement=subidas_experiencia.get(player["ht_player_id"], ""),
                    ht_player_id=player["ht_player_id"],
                    name=player["name"],
                    native_country=player["native_country"],
                    country_code=player["country_code"],
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
                    match_counts=(progress.match_counts if progress is not None else {}),
                    unscored_national_matches=(
                        progress.unscored_national_matches if progress is not None else 0
                    ),
                )
            )

            joined_at = player["purchased_at"] or player["purchased_at_manual"]
            date_source = (
                "transferencia"
                if player["purchased_at"] is not None
                else "manual"
                if player["purchased_at_manual"] is not None
                else None
            )
            days_in_club: int | None = None
            calculated: int | None = None
            decimal: float | None = None
            next_level: int | None = None
            days_to_next: int | None = None
            progress_pct: float | None = None
            if joined_at is not None:
                joined_date = (
                    joined_at if joined_at.tzinfo else joined_at.replace(tzinfo=UTC)
                ).date()
                days_in_club = max((today - joined_date).days, 0)
                calculated = loyalty_level(days_in_club)
                decimal = loyalty_decimal(days_in_club)
                if calculated is not None and decimal is not None:
                    if calculated >= 20:
                        progress_pct = 100.0
                    else:
                        progress_pct = loyalty_progress_pct(days_in_club)
                        next_level = calculated + 1
                        days_to_next = max(days_for_level(next_level) - days_in_club, 0)
            else:
                missing_purchase_dates += 1

            display_level = calculated if calculated is not None else int(player["loyalty"])
            loyalty_rows.append(
                LoyaltyRow(
                    last_improvement=subidas_fidelidad.get(player["ht_player_id"], ""),
                    ht_player_id=player["ht_player_id"],
                    name=player["name"],
                    native_country=player["native_country"],
                    country_code=player["country_code"],
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
                )
            )

            stamina_level = int(player["stamina"])
            expected = stamina_forecast_level(player["age_years"], effective_stamina_pct)
            if not STAMINA_MIN_TABLE_AGE <= player["age_years"] <= STAMINA_MAX_TABLE_AGE:
                players_outside_stamina_table += 1
            if expected > stamina_level:
                trend = "sube"
            elif expected < stamina_level:
                trend = "baja"
            else:
                trend = "estable"
            stamina_rows.append(
                StaminaRow(
                    last_improvement=mejoras.get(
                        (player["ht_player_id"], _skill_id_for("stamina") or -1), ""
                    ),
                    ht_player_id=player["ht_player_id"],
                    name=player["name"],
                    native_country=player["native_country"],
                    country_code=player["country_code"],
                    age_years=player["age_years"],
                    age_days=player["age_days"],
                    level=stamina_level,
                    level_name=skill_name(stamina_level),
                    effective_training_pct=round(effective_stamina_pct, 1),
                    expected_level=expected,
                    expected_level_name=skill_name(expected),
                    trend=trend,
                )
            )

        experience_rows.sort(key=lambda row: (row.progress_pct is None, -(row.progress_pct or 0)))
        loyalty_rows.sort(key=lambda row: (row.days_in_club is None, -(row.days_in_club or 0)))
        stamina_rows.sort(key=lambda row: (row.trend != "baja", row.trend != "sube"))
        # Sólo queda lo condicional: lo fijo describía el método, no un límite,
        # y el frontend lo pintaba en las tres pestañas a la vez.
        notes: list[str] = []
        if ctx is None:
            notes.append(
                "Sincroniza el entrenamiento: sin él no se conoce el esfuerzo real en "
                "resistencia y se asume 0%."
            )
        return DevelopmentView(
            experience=experience_rows,
            loyalty=loyalty_rows,
            stamina=stamina_rows,
            notes=notes,
        )

    async def player_levels(
        self,
        team_id: int,
        ht_player_id: int,
        skill: str | None = None,
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
            (p for p in await self._roster(team_id) if p["ht_player_id"] == ht_player_id),
            None,
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
                    if prev is not None
                    else None
                )
                confirmed.append(
                    ConfirmedPop(
                        season_week=f"{u.season:02d}-{u.match_round:02d}",
                        from_level=u.old_level,
                        from_level_name=skill_name(u.old_level),
                        to_level=u.new_level,
                        to_level_name=skill_name(u.new_level),
                        weeks_between=weeks_between,
                    )
                )
                prev = u

        world = await self._world(team)
        chain = te.forecast_level_chain(
            chosen_skill,
            level,
            player_row["age_years"],
            player_row["age_days"],
            setup,
        )
        forecast = [
            ForecastMilestone(
                level=milestone.level,
                level_name=skill_name(milestone.level),
                weeks_for_this_level=milestone.weeks_for_this_level,
                weeks_from_now=milestone.weeks_from_now,
                season_week=(
                    season_week_label(world, weeks_offset=round(milestone.weeks_from_now))
                    if world is not None
                    else None
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
            ht_player_id=ht_player_id,
            name=player_row["name"],
            skill=chosen_skill,
            skill_label=TRAINABLE_SKILLS.get(chosen_skill, chosen_skill),
            current_level=level,
            current_level_name=skill_name(level),
            confirmed=confirmed,
            forecast=forecast,
            notes=notes,
        )
