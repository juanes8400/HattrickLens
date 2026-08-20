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


@pytest.fixture(autouse=True)
def _sin_comprobacion_de_dueno(request: pytest.FixtureRequest):
    """Los tests de datos no tienen que autenticarse; los de seguridad sí.

    2026-08-19: `require_team_owner` se añadió a las 45 rutas con `{team_id}`
    antes de publicar la app. Pedir sesión y comprobar el dueño en cada test de
    forma o de cálculo no probaría nada nuevo y escondería lo que sí prueban,
    así que aquí se desactiva la dependencia.

    Que la protección FUNCIONE se comprueba aparte, en `test_team_isolation.py`,
    donde esta desactivación no se aplica (marca `seguridad`): un test recorre
    la aplicación entera y falla si alguna ruta con `{team_id}` se la salta, y
    otros dos comprueban en vivo el 401 sin sesión y el 403 con el equipo de
    otro.
    """
    from app.api.deps import require_team_owner
    from app.main import app

    if request.node.get_closest_marker("seguridad"):
        yield
        return
    app.dependency_overrides[require_team_owner] = lambda: None
    yield
    app.dependency_overrides.pop(require_team_owner, None)
