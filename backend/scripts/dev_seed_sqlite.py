"""Siembra dev.db (SQLite) con los fixtures XML reales de Pulgas Arrechas.

Mismo pipeline que los tests (fetch → parse → diff → snapshot), pero contra un
fichero persistente en vez de :memory:, para poder levantar `uvicorn` sin
Postgres/Redis y navegar la API con datos reales. Herramienta de desarrollo
local, no toca CHPP.

Uso:
    python scripts/dev_seed_sqlite.py
"""
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = Path(__file__).resolve().parent.parent / "dev.db"
FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
HT_TEAM_ID = 537758


async def main() -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.application.commands.sync_team import (
        SyncMatchDetailsCommand,
        SyncTeamCommand,
        SyncTeamHandler,
    )
    from app.infrastructure.chpp.parsers import get_parser
    from app.infrastructure.db import models as m
    from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

    if DB_PATH.exists():
        DB_PATH.unlink()

    class FakeCHPP:
        async def fetch(self, file: str, version: str, **params: Any) -> dict[str, Any]:
            return get_parser(file)((FIXTURES / f"{file}.xml").read_bytes())

    engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}")
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as s:
        team = m.Team(
            ht_team_id=HT_TEAM_ID, name="Pulgas Arrechas",
            league_name="Colombia", series_name="V.92",
            currency_rate=10.0, currency_name="US$",
        )
        s.add(team)
        await s.commit()
        team_id = team.id

    handler = SyncTeamHandler(SqlAlchemyUnitOfWork(factory), FakeCHPP())
    result = await handler.execute(
        SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=HT_TEAM_ID)
    )
    await handler.execute(
        SyncTeamCommand(
            user_id=1, team_id=team_id, ht_team_id=HT_TEAM_ID,
            # orden importa: teamdetails antes que leaguedetails (esta última
            # se pide por serie — series_ht_id — que sale de teamdetails).
            files=[
                "club", "stafflist", "worlddetails", "trainingevents", "matches",
                "teamdetails", "leaguedetails",
            ],
        )
    )
    # matchdetails se pide por partido: solo tenemos el fixture real de uno.
    await handler.execute_match_details(
        SyncMatchDetailsCommand(user_id=1, team_id=team_id, ht_match_id=765274387)
    )
    await engine.dispose()
    print(f"OK: team_id={team_id} status={result.status} "
          f"snapshots={result.snapshots_written} unchanged={result.unchanged} "
          f"db={DB_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
