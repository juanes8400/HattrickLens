"""GET /teams/{id}/insights — HL-130 a nivel HTTP.

Caso real que motivó este test: el propio entrenador del club (Volodymyr
Manakin, 44 años) aparecía en la alerta "caros de entrenar" junto a los
veteranos genuinos. La identidad del entrenador viene de `TrainerID` en
training.xml (ya parseado como `TrainingSnapshot.trainer_ht_id`), no de una
heurística sobre sus stats — por eso este test usa el fixture real, donde el
entrenador (PlayerID 434712334) convive en el roster con un veterano genuino
(Robert Horhoi) que sí debe seguir apareciendo en la alerta.
"""
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.sync_team import SyncTeamCommand, SyncTeamHandler
from app.infrastructure.chpp.parsers import get_parser
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures"


class FakeCHPP:
    async def fetch(self, file: str, version: str = "latest", **_params: Any) -> dict[str, Any]:
        return get_parser(file)((FIXTURES / f"{file}.xml").read_bytes())


@pytest.fixture
def seeded() -> tuple[TestClient, int]:
    import asyncio

    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def setup() -> int:
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)
        async with factory() as s:
            team = m.Team(
                ht_team_id=537758, name="Pulgas Arrechas",
                currency_rate=10.0, currency_name="US$",
            )
            s.add(team)
            await s.commit()
            team_id = team.id

        uow = SqlAlchemyUnitOfWork(factory)
        handler = SyncTeamHandler(uow, FakeCHPP())
        await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758)
        )
        return team_id

    team_id = asyncio.run(setup())

    async def override_get_session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    yield client, team_id
    app.dependency_overrides.clear()


def test_the_clubs_own_trainer_is_excluded_from_expensive_training_alert(
    seeded: tuple[TestClient, int],
) -> None:
    client, team_id = seeded
    resp = client.get(f"/api/v1/teams/{team_id}/insights")
    assert resp.status_code == 200

    training_alert = next(
        (i for i in resp.json() if i["key"] == "training.inefficient"), None
    )
    assert training_alert is not None
    flagged = training_alert["evidence"]["players"]
    assert "Volodymyr Manakin" not in flagged
    assert "Robert Horhoi" in flagged
