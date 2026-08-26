"""Post-match training choice.

This query answers a very Hattrick-specific question:

    "Given the minutes and positions my players actually played this week,
     which training type would harvest those minutes best?"

It deliberately separates facts from judgement:

- facts: player skills, age, current training setup, match minutes/positions
- rules: a small position -> training exposure table
- judgement: a transparent score used to rank candidate training types
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.squad import SKILL_COLS, SquadQueryService
from app.application.queries.training_context import TrainingContextService
from app.domain.engines.training_engine import (
    TrainingSetup,
    default_setup,
    training_exposure,
    weeks_to_next_level,
)
from app.domain.value_objects.ht_constants import (
    NON_OFFICIAL_MATCH_TYPES,
    TRAINING_TARGET_SKILL,
    match_position_name,
    match_role_name,
    match_type_name,
    training_name,
    training_target,
)
from app.infrastructure.db import models as m

KEEPERS = frozenset({1, 100})
WINGBACKS = frozenset({2, 6, 101, 105})
CENTRAL_DEFENDERS = frozenset({3, 4, 5, 102, 103, 104})
DEFENDERS = WINGBACKS | CENTRAL_DEFENDERS
WINGERS = frozenset({7, 11, 106, 110})
INNER_MIDS = frozenset({8, 9, 10, 107, 108, 109})
FORWARDS = frozenset({12, 13, 14, 111, 112, 113})
FIELD_PLAYERS = DEFENDERS | WINGERS | INNER_MIDS | FORWARDS
ALL_POSITIONS = KEEPERS | FIELD_PLAYERS
DEPRECATED_TRAINING_TYPES = frozenset({0, 1})


# The values are position share labels from training.yaml:
# full = 100%, partial = 50%, none/missing = no training.
TRAINING_POSITION_SHARES: dict[int, dict[str, str]] = {
    1: {"all": "full"},  # stamina
    2: {"all": "full"},  # set pieces
    3: {"defender": "full"},
    4: {"forward": "full"},
    5: {"winger": "full", "wingback": "partial"},
    6: {"forward": "full", "all": "partial"},  # scoring + set pieces
    7: {"inner_mid": "full", "winger": "full", "forward": "full"},
    8: {"inner_mid": "full", "winger": "partial"},
    9: {"keeper": "full"},
    # En Hattrick, "defensas" incluye centrales y laterales; "centrocampistas"
    # incluye medios interiores y extremos. La pantalla oficial de minutos de
    # entrenamiento confirma los cuatro grupos para los tipos 10 y 11.
    10: {"defender": "full", "wingback": "full", "inner_mid": "full", "winger": "full"},
    11: {"defender": "full", "wingback": "full", "inner_mid": "full", "winger": "full"},
    12: {"winger": "full", "forward": "full"},
}


@dataclass(frozen=True)
class PlayedSegment:
    ht_player_id: int
    player_name: str
    ht_match_id: int | None
    position_code: int
    played_minutes: int
    rating: float | None
    played_at: datetime | None
    match_type: int | None
    source: str


@dataclass(frozen=True)
class TrainingWeekExposure:
    """Minutos equivalentes observados para el último entrenamiento cerrado."""

    exposure: float
    equivalent_minutes: float
    matches: int


@dataclass(frozen=True)
class ObservedTrainingProgress:
    """Avance técnico verificable desde la primera lectura del nivel actual."""

    total_exposure: float
    latest_exposure: float
    latest_equivalent_minutes: float
    observed_cycles: int


class PostMatchTrainingService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, team_id: int) -> dict[str, Any] | None:
        team = await self._s.get(m.Team, team_id)
        if team is None:
            return None

        players = await self._players(team_id)
        if not players:
            return {
                "team": {"id": team.id, "htTeamId": team.ht_team_id, "name": team.name},
                "options": [],
                "recommendation": None,
                "players": [],
                "notes": ["No hay plantilla sincronizada todavia."],
            }

        training = await self._latest_training(team_id)
        ctx = await TrainingContextService(self._s).get(team_id)
        setup = (
            ctx.setup
            if ctx is not None
            else default_setup(
                training_target(training.training_type) if training else "playmaking",
                training_type=training.training_type if training else None,
                intensity=training.training_level if training else 100,
                stamina_share=training.stamina_part if training else None,
            )
        )

        deadline = await self._training_deadline(team_id)
        since = deadline - timedelta(days=8)
        segments, data_notes = await self._played_segments(team_id, since, deadline)
        by_player: dict[int, list[PlayedSegment]] = {}
        for seg in segments:
            by_player.setdefault(seg.ht_player_id, []).append(seg)

        current_type = training.training_type if training else None
        trainer_ht_id = training.trainer_ht_id if training else None
        options = [
            self._score_training_type(type_id, players, by_player, setup, trainer_ht_id)
            for type_id in sorted(TRAINING_TARGET_SKILL)
            if type_id != 0
        ]
        options = [o for o in options if o["trainedSkill"] is not None]
        options.sort(key=lambda o: (o["recommendable"], o["score"]), reverse=True)
        recommendation = next((o for o in options if o["recommendable"]), None)

        player_rows = [
            self._player_row(p, by_player.get(p["ht_player_id"], []), options) for p in players
        ]

        notes: list[str] = list(data_notes)
        if current_type and recommendation and recommendation["trainingType"] != current_type:
            notes.append(
                "El entrenamiento actual no es el que más aprovecha los minutos ya jugados esta semana."  # noqa: E501
            )
        elif current_type and recommendation:
            notes.append("El entrenamiento actual coincide con la mejor opción calculada.")

        return {
            "team": {"id": team.id, "htTeamId": team.ht_team_id, "name": team.name},
            "trainingWindow": {
                "from": since.isoformat(),
                "to": deadline.isoformat(),
                "trainingDate": deadline.isoformat(),
            },
            "currentTraining": (
                {
                    "trainingType": current_type,
                    "name": training_name(current_type),
                    "trainedSkill": training_target(current_type),
                    "intensity": training.training_level,
                    "staminaPart": training.stamina_part,
                }
                if training is not None and current_type is not None
                else None
            ),
            "recommendation": recommendation,
            "options": options,
            "players": player_rows,
            "notes": notes,
        }

    async def _players(self, team_id: int) -> list[dict[str, Any]]:
        rows = await SquadQueryService(self._s)._latest(team_id)
        out: list[dict[str, Any]] = []
        for snap, ident in rows:
            out.append(
                {
                    "db_id": ident.id,
                    "ht_player_id": ident.ht_player_id,
                    "name": f"{ident.first_name} {ident.last_name}",
                    "age_years": snap.age_years,
                    "age_days": snap.age_days,
                    "skills": {
                        **{c: getattr(snap, c) or 0 for c in SKILL_COLS},
                        "stamina": snap.stamina or 0,
                    },
                    "last_match_ht_id": snap.last_match_ht_id,
                    "last_match_position_code": snap.last_match_position_code,
                    "last_match_played_minutes": snap.last_match_played_minutes,
                    "last_match_rating": snap.last_match_rating,
                }
            )
        return out

    async def _latest_training(self, team_id: int) -> m.TrainingSnapshot | None:
        return await self._s.scalar(
            select(m.TrainingSnapshot)
            .where(m.TrainingSnapshot.team_id == team_id)
            .order_by(m.TrainingSnapshot.captured_at.desc())
            .limit(1)
        )

    async def _training_deadline(self, team_id: int | None = None) -> datetime:
        if team_id is not None:
            team = await self._s.get(m.Team, team_id)
            if team is not None and team.ht_league_id is not None:
                team_world = await self._s.scalar(
                    select(m.WorldContext)
                    .where(m.WorldContext.ht_league_id == team.ht_league_id)
                    .limit(1)
                )
                if team_world is not None and team_world.training_date is not None:
                    return _aware(team_world.training_date)
        world = await self._s.scalar(
            select(m.WorldContext)
            .order_by(m.WorldContext.refreshed_at.desc().nullslast(), m.WorldContext.id.desc())
            .limit(1)
        )
        if world and world.training_date:
            return _aware(world.training_date)
        return datetime.now(UTC)

    async def _latest_completed_training_deadline(self, team_id: int) -> datetime:
        """Último corte semanal de entrenamiento que ya ocurrió."""
        deadline = await self._training_deadline(team_id)
        now = datetime.now(UTC)
        while deadline > now:
            deadline -= timedelta(days=7)
        while deadline + timedelta(days=7) <= now:
            deadline += timedelta(days=7)
        return deadline

    async def latest_completed_training_exposure(
        self,
        team_id: int,
        training_type: int,
    ) -> dict[int, TrainingWeekExposure]:
        """Exposición real del ciclo de entrenamiento más reciente ya cerrado.

        ``worlddetails.xml`` suele entregar la próxima fecha de entrenamiento.
        Para no sumar partidos futuros ni una semana completa a toda la
        plantilla, retrocedemos al último corte ya ocurrido y leemos únicamente
        los partidos reales de los siete días anteriores. Cada jugador queda
        limitado a 90 minutos equivalentes, tal como hace Hattrick.
        """
        deadline = await self._latest_completed_training_deadline(team_id)
        since = deadline - timedelta(days=7)

        segments, _notes = await self._played_segments(team_id, since, deadline)
        by_player: dict[int, list[PlayedSegment]] = {}
        for segment in segments:
            # Sin fecha de partido no hay evidencia para ubicar los minutos en
            # este ciclo. Esos LastMatch quedan disponibles como respaldo en la
            # vista a posteriori, pero nunca se atribuyen a una semana concreta.
            if segment.played_at is None:
                continue
            by_player.setdefault(segment.ht_player_id, []).append(segment)

        result: dict[int, TrainingWeekExposure] = {}
        for ht_player_id, player_segments in by_player.items():
            exposure = min(
                sum(
                    self._segment_exposure(
                        training_type,
                        segment.position_code,
                        segment.played_minutes,
                    )
                    for segment in player_segments
                ),
                1.0,
            )
            if exposure <= 0:
                continue
            result[ht_player_id] = TrainingWeekExposure(
                exposure=round(exposure, 4),
                equivalent_minutes=round(exposure * 90.0, 1),
                matches=len({segment.ht_match_id for segment in player_segments}),
            )
        return result

    async def observed_training_progress(
        self,
        team_id: int,
        skill: str,
        baselines: dict[int, datetime],
        *,
        include_latest: bool,
    ) -> dict[int, ObservedTrainingProgress]:
        """Suma todas las exposiciones semanales observables desde una base.

        La base de cada jugador es la primera sincronización del tramo continuo
        en su nivel entero actual. No pretende reconstruir el subnivel que tenía
        antes de esa lectura; conserva únicamente el avance nuevo demostrado por
        minutos, posición y tipo de entrenamiento reales.
        """
        if not baselines:
            return {}

        latest_deadline = await self._latest_completed_training_deadline(team_id)
        # 2026-08-16, error real: el ciclo EN CURSO no se contaba nunca. Sus
        # partidos ya se jugaron y sus minutos son un hecho, pero su corte
        # todavía no ha llegado, así que no existía como ciclo — y un jugador
        # que anoche jugó 82' aparecía con cero. `include_latest` es justo el
        # toggle "Incluir los partidos de esta semana": lo que añade es esta
        # semana abierta, no el último ciclo ya cerrado (ese es un hecho
        # consumado y cuenta siempre).
        open_deadline = latest_deadline + timedelta(days=7)
        earliest_baseline = min(_aware(value) for value in baselines.values())
        deadlines: list[datetime] = []
        deadline = latest_deadline
        while deadline > earliest_baseline:
            deadlines.append(deadline)
            deadline -= timedelta(days=7)
        deadlines.reverse()
        if include_latest:
            deadlines.append(open_deadline)
        if not deadlines:
            return {}

        training_rows = (
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
        if not training_rows:
            return {}

        segments, _notes = await self._played_segments(
            team_id,
            deadlines[0] - timedelta(days=7),
            deadlines[-1],
        )
        exact_segments = [segment for segment in segments if segment.played_at is not None]

        totals: dict[int, float] = {}
        latest_values: dict[int, float] = {}
        cycle_counts: dict[int, int] = {}
        for cycle_deadline in deadlines:
            # La configuración se consulta bajo demanda. Una lectura hecha
            # justo después del corte puede ser la primera evidencia del
            # entrenamiento que acaba de aplicarse; una lectura anterior
            # también sigue siendo válida si fue la más cercana. La base del
            # jugador impide usar esta aproximación para reconstruir ciclos
            # anteriores a la primera vez que Lens lo observó.
            nearby_training = [
                row
                for row in training_rows
                if abs((_aware(row.captured_at) - cycle_deadline).total_seconds())
                <= timedelta(days=7).total_seconds()
            ]
            training = min(
                nearby_training,
                key=lambda row: (
                    abs((_aware(row.captured_at) - cycle_deadline).total_seconds()),
                    _aware(row.captured_at) > cycle_deadline,
                ),
                default=None,
            )
            if training is None or training_target(training.training_type) != skill:
                continue
            cycle_start = cycle_deadline - timedelta(days=7)
            by_player: dict[int, list[PlayedSegment]] = {}
            for segment in exact_segments:
                played_at = _aware(segment.played_at)
                baseline = baselines.get(segment.ht_player_id)
                if baseline is None or cycle_deadline <= _aware(baseline):
                    continue
                if cycle_start < played_at <= cycle_deadline:
                    by_player.setdefault(segment.ht_player_id, []).append(segment)

            for ht_player_id, player_segments in by_player.items():
                exposure = min(
                    sum(
                        self._segment_exposure(
                            training.training_type,
                            segment.position_code,
                            segment.played_minutes,
                        )
                        for segment in player_segments
                    ),
                    1.0,
                )
                if exposure <= 0:
                    continue
                totals[ht_player_id] = totals.get(ht_player_id, 0.0) + exposure
                cycle_counts[ht_player_id] = cycle_counts.get(ht_player_id, 0) + 1
                # "Esta semana" es la que está corriendo, no la última cerrada.
                if cycle_deadline == open_deadline:
                    latest_values[ht_player_id] = exposure

        return {
            ht_player_id: ObservedTrainingProgress(
                total_exposure=round(total, 4),
                latest_exposure=round(latest_values.get(ht_player_id, 0.0), 4),
                latest_equivalent_minutes=round(
                    latest_values.get(ht_player_id, 0.0) * 90.0,
                    1,
                ),
                observed_cycles=cycle_counts.get(ht_player_id, 0),
            )
            for ht_player_id, total in totals.items()
        }

    async def _played_segments(
        self, team_id: int, since: datetime, deadline: datetime
    ) -> tuple[list[PlayedSegment], list[str]]:
        rows = (
            await self._s.execute(
                select(m.PlayerMatchRating, m.Player, m.Match)
                .join(m.Player, m.Player.id == m.PlayerMatchRating.player_id)
                .outerjoin(m.Match, m.Match.ht_match_id == m.PlayerMatchRating.ht_match_id)
                .where(m.Player.team_id == team_id, m.Player.left_team_at.is_(None))
                .order_by(m.PlayerMatchRating.captured_at.desc())
            )
        ).all()

        segments: list[PlayedSegment] = []
        for rating, player, match in rows:
            if match is not None:
                # Escaleras, Duelos, Torneos y Preparación no son partidos
                # reales — pedido explícito 2026-08-11: no deben influir en
                # qué entrenamiento conviene según los minutos jugados.
                if match.match_type in NON_OFFICIAL_MATCH_TYPES:
                    continue
                played_at = _aware(match.played_at)
                if not (since <= played_at <= deadline):
                    continue
                if match.status and match.status.lower() not in {"finished", "finished_available"}:
                    continue
                match_type = match.match_type
            else:
                played_at = None
                match_type = None
            segments.append(
                PlayedSegment(
                    ht_player_id=player.ht_player_id,
                    player_name=f"{player.first_name} {player.last_name}",
                    ht_match_id=rating.ht_match_id,
                    position_code=rating.position_code,
                    played_minutes=rating.played_minutes,
                    rating=rating.rating,
                    played_at=played_at,
                    match_type=match_type,
                    source="playerdetails-history",
                )
            )

        notes: list[str] = []
        if segments:
            return segments, notes

        fallback = await self._fallback_last_match_segments(team_id)
        if fallback:
            notes.append(
                "No hay historial de partidos dentro de la ventana; se usa LastMatch de playerdetails como respaldo."  # noqa: E501
            )
            return fallback, notes

        notes.append(
            "No hay minutos/posiciones sincronizados. Sincroniza playerdetails o matchlineup para activar esta recomendación."  # noqa: E501
        )
        return [], notes

    async def _fallback_last_match_segments(self, team_id: int) -> list[PlayedSegment]:
        rows = await SquadQueryService(self._s)._latest(team_id)
        out: list[PlayedSegment] = []
        for snap, ident in rows:
            if not snap.last_match_position_code or not snap.last_match_played_minutes:
                continue
            out.append(
                PlayedSegment(
                    ht_player_id=ident.ht_player_id,
                    player_name=f"{ident.first_name} {ident.last_name}",
                    ht_match_id=snap.last_match_ht_id,
                    position_code=snap.last_match_position_code,
                    played_minutes=snap.last_match_played_minutes,
                    rating=snap.last_match_rating,
                    played_at=None,
                    match_type=None,
                    source="playerdetails-last-match",
                )
            )
        return out

    def _score_training_type(
        self,
        training_type: int,
        players: list[dict[str, Any]],
        by_player: dict[int, list[PlayedSegment]],
        setup: TrainingSetup,
        trainer_ht_id: int | None,
    ) -> dict[str, Any]:
        skill = training_target(training_type)
        candidate_setup = TrainingSetup(
            skill=skill or setup.skill,
            training_type=training_type,
            intensity=setup.intensity,
            stamina_share=setup.stamina_share,
            coach_level=setup.coach_level,
            coach_is_excellent=setup.coach_is_excellent,
            assistant_level_sum=setup.assistant_level_sum,
        )

        trainees: list[dict[str, Any]] = []
        total_equivalent_minutes = 0.0
        development_score = 0.0
        pops_soon = 0
        total_exposure = 0.0

        for p in players:
            if trainer_ht_id and p["ht_player_id"] == trainer_ht_id:
                continue
            exposure = min(
                sum(
                    self._segment_exposure(training_type, seg.position_code, seg.played_minutes)
                    for seg in by_player.get(p["ht_player_id"], [])
                ),
                1.0,
            )
            if exposure <= 0 or skill is None:
                continue

            level = int(p["skills"].get(skill, 0))
            speed = (
                None
                if skill == "stamina"
                else weeks_to_next_level(
                    skill,
                    level,
                    int(p["age_years"]),
                    int(p["age_days"]),
                    setup=candidate_setup,
                    exposure=exposure,
                )
            )
            equivalent_minutes = exposure * 90
            age = float(p["age_years"]) + float(p["age_days"]) / 112.0
            age_weight = max(0.35, min(1.25, (30.0 - age) / 12.0))
            level_weight = max(1.0, 21.0 - level)
            development_score += exposure * age_weight * level_weight
            total_equivalent_minutes += equivalent_minutes
            total_exposure += exposure
            if speed is not None and speed.weeks_to_next_level <= 3.0:
                pops_soon += 1
            trainees.append(
                {
                    "htPlayerId": p["ht_player_id"],
                    "name": p["name"],
                    "exposure": round(exposure, 3),
                    "equivalentMinutes": round(equivalent_minutes, 1),
                    "currentLevel": level,
                    "weeksToPop": speed.weeks_to_next_level if speed is not None else None,
                }
            )

        trainees.sort(
            key=lambda x: (
                -x["exposure"],
                x["weeksToPop"] if x["weeksToPop"] is not None else float("inf"),
                x["name"],
            )
        )
        score = total_equivalent_minutes + development_score * 10.0 + pops_soon * 30.0
        trained_count = len(trainees)
        rationale = [
            f"{trained_count} jugadores reciben entrenamiento",
            f"{sum(1 for t in trainees if t['exposure'] >= 0.99)} con exposición full",
            f"{round(total_equivalent_minutes, 1)} minutos equivalentes",
        ]
        if pops_soon:
            rationale.append(f"{pops_soon} posible(s) subida(s) en <= 3 semanas")
        if training_type in DEPRECATED_TRAINING_TYPES:
            rationale.append(
                "tipo obsoleto según CHPP: no compite y sus semanas usan un motor separado"
            )
        return {
            "trainingType": training_type,
            "name": training_name(training_type),
            "trainedSkill": skill,
            "recommendable": training_type not in DEPRECATED_TRAINING_TYPES,
            "rationale": rationale,
            "score": round(score, 2),
            "trainedPlayers": trained_count,
            "fullTrainingPlayers": sum(1 for t in trainees if t["exposure"] >= 0.99),
            "partialTrainingPlayers": sum(1 for t in trainees if 0 < t["exposure"] < 0.99),
            "equivalentMinutes": round(total_equivalent_minutes, 1),
            "averageExposure": round(total_exposure / trained_count, 3) if trained_count else 0.0,
            "popsSoon": pops_soon,
            "topTrainees": trainees[:8],
        }

    def _segment_exposure(self, training_type: int, position_code: int, minutes: int) -> float:
        share = self._position_share(training_type, position_code)
        return training_exposure(max(minutes, 0), share)

    def _position_share(self, training_type: int, position_code: int) -> str:
        role = position_role(position_code)
        shares = TRAINING_POSITION_SHARES.get(training_type, {})
        return shares.get(role) or shares.get("all") or "none"

    def _player_row(
        self,
        player: dict[str, Any],
        segments: list[PlayedSegment],
        options: list[dict[str, Any]],
    ) -> dict[str, Any]:
        exposure_by_type: dict[int, float] = {}
        for type_id in TRAINING_TARGET_SKILL:
            exposure_by_type[type_id] = min(
                sum(
                    self._segment_exposure(type_id, s.position_code, s.played_minutes)
                    for s in segments
                ),
                1.0,
            )
        best = max(exposure_by_type.items(), key=lambda kv: kv[1], default=(0, 0.0))
        return {
            "htPlayerId": player["ht_player_id"],
            "name": player["name"],
            "segments": [
                {
                    "matchId": s.ht_match_id,
                    "playedAt": s.played_at.isoformat() if s.played_at else None,
                    "matchType": s.match_type,
                    "matchTypeName": match_type_name(s.match_type) if s.match_type else None,
                    "positionCode": s.position_code,
                    "position": position_name(s.position_code),
                    "minutes": s.played_minutes,
                    "rating": s.rating,
                    "source": s.source,
                }
                for s in segments
            ],
            "bestExposureTrainingType": best[0],
            "bestExposureTrainingName": training_name(best[0]) if best[0] else None,
            "bestExposure": round(best[1], 3),
            "exposureByTrainingType": {
                str(k): round(v, 3) for k, v in exposure_by_type.items() if v > 0
            },
        }


def position_role(code: int) -> str:
    if code in KEEPERS:
        return "keeper"
    if code in WINGBACKS:
        return "wingback"
    if code in CENTRAL_DEFENDERS:
        return "defender"
    if code in WINGERS:
        return "winger"
    if code in INNER_MIDS:
        return "inner_mid"
    if code in FORWARDS:
        return "forward"
    return "unknown"


def position_name(code: int) -> str:
    if code >= 100:
        return match_role_name(code)
    return match_position_name(code)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
