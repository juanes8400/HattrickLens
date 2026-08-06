"""Sync manual (user-initiated) contra CHPP real — herramienta de desarrollo.

Uso:
    DATABASE_URL=sqlite+aiosqlite:///dev.db python scripts/sync_once.py

Lee CHPP_DEV_ACCESS_TOKEN/SECRET del entorno (.env). Ejecuta el use case
SyncTeamHandler real: fetch → parse → diff → snapshots append-only.
"""
import asyncio
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main() -> None:
    from requests_oauthlib import OAuth1Session
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.application.commands.sync_team import SyncTeamCommand, SyncTeamHandler
    from app.infrastructure.chpp.parsers import get_parser
    from app.infrastructure.db import models as m
    from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

    db_url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///dev.db")
    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    # Gateway CHPP síncrono envuelto (dev tool; en producción: CHPPClient async)
    class DevCHPPGateway:
        def __init__(self) -> None:
            self._s = OAuth1Session(
                os.environ["CHPP_CONSUMER_KEY"],
                client_secret=os.environ["CHPP_CONSUMER_SECRET"],
                resource_owner_key=os.environ["CHPP_DEV_ACCESS_TOKEN"],
                resource_owner_secret=os.environ["CHPP_DEV_ACCESS_SECRET"],
            )
            self._s.headers["User-Agent"] = os.environ.get("CHPP_USER_AGENT", "HattrickLens/0.1.0")

        async def fetch(self, file: str, version: str, **params: Any) -> dict[str, Any]:
            r = await asyncio.to_thread(
                self._s.get,
                "https://chpp.hattrick.org/chppxml.ashx",
                params={"file": file, "version": version, **params},
            )
            r.raise_for_status()
            return get_parser(file)(r.content)

    chpp = DevCHPPGateway()

    # teamdetails → asegurar Team
    team_data = (await chpp.fetch("teamdetails", "3.6"))["teams"][0]
    async with factory() as s:
        team = await s.scalar(select(m.Team).where(m.Team.ht_team_id == team_data["ht_team_id"]))
        if team is None:
            team = m.Team(
                ht_team_id=team_data["ht_team_id"],
                name=team_data["name"],
                league_name=team_data["league_name"],
                series_name=team_data["series_name"],
            )
            s.add(team)
            await s.commit()
        team_id, team_name = team.id, team.name

    handler = SyncTeamHandler(SqlAlchemyUnitOfWork(factory), chpp)
    result = await handler.execute(
        SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=team_data["ht_team_id"])
    )
    print(f"Equipo: {team_name}")
    print(f"Sync #{result.sync_id}: {result.status}")
    print(f"  snapshots nuevos: {result.snapshots_written}")
    print(f"  sin cambios:      {result.unchanged}")
    if result.errors:
        print(f"  errores: {result.errors}")

    async with factory() as s:
        uow = SqlAlchemyUnitOfWork(factory)
        async with uow as u:
            total = await u.players.count_snapshots(team_id)
        print(f"  total snapshots en DB: {total}")


if __name__ == "__main__":
    asyncio.run(main())
