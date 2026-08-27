"""Backfill dinámico de habilidad entrenada para etapas cerradas."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.weekly import season_for_datetime
from app.domain.engines.sold_training_assignment import (
    TRAINABLE_SKILLS,
    SoldPlayerEvidence,
    derive_training_assignments,
)
from app.domain.value_objects.ht_constants import training_target
from app.infrastructure.db import models as m


@dataclass(frozen=True)
class SoldTrainingBackfillResult:
    closed_stints: int
    direct: int
    by_season_levels: int
    by_season_players: int
    by_current_training: int
    by_skill_priority: int
    unresolved: int
    changed: int


def _before_or_at(value: datetime, cutoff: datetime) -> bool:
    """SQLite pierde tzinfo; Postgres no. Compara ambos como UTC naive."""

    left = value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value
    right = cutoff.astimezone(UTC).replace(tzinfo=None) if cutoff.tzinfo else cutoff
    return left <= right


def _skill_increases(
    snapshots: list[m.PlayerSnapshot],
    sold_at: datetime,
) -> dict[str, int]:
    relevant = [snap for snap in snapshots if _before_or_at(snap.captured_at, sold_at)]
    increases: dict[str, int] = {}
    for skill in TRAINABLE_SKILLS:
        values = [int(value) for snap in relevant if (value := getattr(snap, skill)) is not None]
        # "Cuántos niveles subió" nunca puede ser negativo. Una caída en una
        # habilidad principal sería una corrección de datos, no entrenamiento.
        increases[skill] = max(values[-1] - values[0], 0) if values else 0
    return increases


async def backfill_sold_training_assignments(
    session: AsyncSession,
    team_id: int,
) -> SoldTrainingBackfillResult:
    """Recalcula y persiste TODAS las etapas cerradas del equipo.

    Es idempotente y se ejecuta después de cada sincronización. Así una nueva
    venta con evidencia puede cambiar los niveles o jugadores de su temporada
    y mover automáticamente las asignaciones provisionales de otros exjugadores.
    """

    team = await session.get(m.Team, team_id)
    if team is None:
        return SoldTrainingBackfillResult(0, 0, 0, 0, 0, 0, 0, 0)

    world = (
        await session.scalar(
            select(m.WorldContext).where(m.WorldContext.ht_league_id == team.ht_league_id)
        )
        if team.ht_league_id is not None
        else None
    )
    stints = list(
        (
            await session.execute(
                select(m.PlayerStint).where(
                    m.PlayerStint.team_id == team_id,
                    m.PlayerStint.left_at.is_not(None),
                    m.PlayerStint.excluded.is_(False),
                )
            )
        ).scalars()
    )
    player_ids = {stint.player_id for stint in stints}
    snapshots = list(
        (
            await session.execute(
                select(m.PlayerSnapshot)
                .where(m.PlayerSnapshot.player_id.in_(player_ids or {-1}))
                .order_by(m.PlayerSnapshot.player_id, m.PlayerSnapshot.captured_at)
            )
        ).scalars()
    )
    snapshots_by_player: dict[int, list[m.PlayerSnapshot]] = {}
    for snapshot in snapshots:
        snapshots_by_player.setdefault(snapshot.player_id, []).append(snapshot)

    evidence_rows = [
        SoldPlayerEvidence(
            stint_id=stint.id,
            player_id=stint.player_id,
            sale_season=(
                season_for_datetime(world, stint.left_at) if stint.left_at is not None else None
            ),
            is_real_sale=stint.sale_price is not None,
            increases=_skill_increases(
                snapshots_by_player.get(stint.player_id, []),
                stint.left_at,
            ),
        )
        for stint in stints
        if stint.id is not None and stint.left_at is not None
    ]
    current_training = await session.scalar(
        select(m.TrainingSnapshot)
        .where(m.TrainingSnapshot.team_id == team_id)
        .order_by(m.TrainingSnapshot.captured_at.desc(), m.TrainingSnapshot.id.desc())
    )
    current_training_skill = (
        training_target(current_training.training_type) if current_training is not None else None
    )
    assignments = derive_training_assignments(
        evidence_rows,
        current_training_skill=current_training_skill,
    )

    changed = 0
    counts = {
        "direct_maximum": 0,
        "season_levels": 0,
        "season_players": 0,
        "season_current_training": 0,
        "season_skill_priority": 0,
        "insufficient_evidence": 0,
    }
    computed_at = datetime.now(UTC)
    for stint in stints:
        assignment = assignments.get(stint.id)
        if assignment is None:
            continue
        counts[assignment.method] += 1
        before = (
            stint.derived_training_skill,
            stint.derived_training_levels,
            stint.derived_training_method,
        )
        after = (assignment.skill, assignment.levels, assignment.method)
        if before != after:
            stint.derived_training_skill = assignment.skill
            stint.derived_training_levels = assignment.levels
            stint.derived_training_method = assignment.method
            stint.derived_training_computed_at = computed_at
            changed += 1

    await session.flush()
    return SoldTrainingBackfillResult(
        closed_stints=len(stints),
        direct=counts["direct_maximum"],
        by_season_levels=counts["season_levels"],
        by_season_players=counts["season_players"],
        by_current_training=counts["season_current_training"],
        by_skill_priority=counts["season_skill_priority"],
        unresolved=counts["insufficient_evidence"],
        changed=changed,
    )
