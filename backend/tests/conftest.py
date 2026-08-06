"""Fixtures compartidos: una base sembrada con los datos reales del club.

Los tests de los query services no usan mocks. Sincronizan los ficheros CHPP
reales de Pulgas Arrechas contra SQLite en memoria y leen de ahí, así que si un
parser cambia de forma o un query service asume una columna que no existe, el
test se entera. Un mock habría seguido pasando.
"""
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.sync_team import SyncTeamCommand, SyncTeamHandler
from app.infrastructure.chpp.parsers import get_parser
from app.infrastructure.db import models as m
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

FIXTURES = Path(__file__).parent / "fixtures"
HT_TEAM_ID = 537758


class FakeCHPP:
    async def fetch(self, file: str, version: str, **params: Any) -> dict[str, Any]:
        # 2026-08-05: `execute()` ahora pide playerdetails.xml para toda la
        # plantilla activa automáticamente en cuanto "players" está en
        # `files` (ver sync_team.py). El fixture de playerdetails no
        # distingue por jugador (siempre el mismo LastMatch/ht_match_id), así
        # que servirlo aquí crearía un partido "fantasma" para CADA test que
        # use `seeded_session()` — justo lo que este helper ya declaraba
        # evitar ("no deben chocar con los reales del fixture"). Se le niega
        # a propósito; los tests que sí quieren probar ese camino (p. ej.
        # test_sync_flow.py, test_player_history.py) usan su propio FakeCHPP.
        if file == "playerdetails":
            return {"chpp_error": True}
        return get_parser(file)((FIXTURES / f"{file}.xml").read_bytes())


async def seeded_session() -> tuple[async_sessionmaker, int]:
    """Base en memoria con el equipo real ya sincronizado."""
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
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
    # Explícito, no el default: los tests de liga/partidos (`_with_league` en
    # test_league_matches_academy_queries.py) siembran su propio escenario de
    # standings/matches encima de esta base y no deben chocar con los reales
    # del fixture — aunque el sync por defecto del producto sí los incluya.
    await handler.execute(
        SyncTeamCommand(
            user_id=1, team_id=team_id, ht_team_id=HT_TEAM_ID,
            files=["players", "training", "economy"],
        )
    )
    # Los ficheros que cierran la fórmula de entrenamiento: staff, mundo y pops
    # confirmados. Sincronizados aparte para que los tests puedan comprobar el
    # antes/después de "cerrar la fórmula".
    await handler.execute(
        SyncTeamCommand(
            user_id=1, team_id=team_id, ht_team_id=HT_TEAM_ID,
            files=["club", "stafflist", "worlddetails", "trainingevents"],
        )
    )
    return factory, team_id


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES
