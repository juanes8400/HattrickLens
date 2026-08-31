"""Recalcula la habilidad entrenada de todas las ventas históricas.

Uso desde ``backend``::

    uv run python scripts/backfill_sold_training.py
    uv run python scripts/backfill_sold_training.py --team-id 1

Es idempotente: se puede volver a ejecutar después de incorporar snapshots o
ventas antiguas. Las asignaciones cambian si cambia la evidencia de niveles,
jugadores o entrenamiento actual.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from sqlalchemy import select

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def run(team_id: int | None) -> None:
    from app.application.commands.backfill_sold_training import (
        backfill_sold_training_assignments,
    )
    from app.infrastructure.db import models as m
    from app.infrastructure.db.session import SessionLocal, engine

    async with SessionLocal() as session:
        if team_id is None:
            team_ids = list((await session.scalars(select(m.Team.id).order_by(m.Team.id))).all())
        else:
            team_ids = [team_id]

        for current_team_id in team_ids:
            result = await backfill_sold_training_assignments(session, current_team_id)
            print(
                f"team={current_team_id} cerradas={result.closed_stints} "
                f"directas={result.direct} niveles={result.by_season_levels} "
                f"jugadores={result.by_season_players} "
                f"entrenamiento_actual={result.by_current_training} "
                f"prioridad_fija={result.by_skill_priority} "
                f"sin_resolver={result.unresolved} cambiadas={result.changed}"
            )
        await session.commit()
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--team-id", type=int)
    args = parser.parse_args()
    asyncio.run(run(args.team_id))


if __name__ == "__main__":
    main()
