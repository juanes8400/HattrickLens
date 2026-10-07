"""Las dos alertas que miran el reloj van por su cuenta, y por un motivo.

2026-10-03. La lista entera se guardaba con un tope de QUINCE MINUTOS porque
dos reglas dependen de la hora: el clima del próximo partido y el aviso de
datos viejos. Las otras treinta dependen sólo del sync, y pagaban el tope:
cada cuarto de hora la siguiente visita al Panel volvía a derivarlo todo
--liga, academia, saldo de cada jugador, mejor once--, siete segundos medidos.

Lo que se vigila aquí es la separación, no el tiempo: que la parte cara ya no
contenga las reglas del reloj, que las del reloj sigan calculándose, y que la
pantalla siga enseñando las dos cosas juntas.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.analysis.alertas import (
    _derive_insights,
    _insights_del_reloj,
)
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
def sembrado() -> tuple[TestClient, int, Any]:
    import asyncio

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def preparar() -> int:
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)
        async with factory() as s:
            team = m.Team(
                ht_team_id=537758,
                name="Pulgas Arrechas",
                currency_rate=10.0,
                currency_name="US$",
            )
            s.add(team)
            await s.commit()
            team_id = team.id

        uow = SqlAlchemyUnitOfWork(factory)
        handler = SyncTeamHandler(uow, FakeCHPP())
        await handler.execute(SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758))

        # El sync que acaba de hacerse, envejecido tres días: así la regla de
        # «datos viejos» tiene algo que decir. Se retrasa el que hay en vez de
        # insertar otro, que es lo que de verdad pasa con el tiempo.
        from sqlalchemy import select as sa_select

        async with factory() as s:
            hace_tres_dias = datetime.now(UTC) - timedelta(days=3)
            for sync in (await s.execute(sa_select(m.Sync))).scalars():
                sync.started_at = hace_tres_dias
                sync.finished_at = hace_tres_dias
            await s.commit()
        return team_id

    team_id = asyncio.run(preparar())

    async def override_get_session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    yield client, team_id, factory
    app.dependency_overrides.clear()


def _claves(insights: list[Any]) -> set[str]:
    return {i.key for i in insights}


def test_la_parte_cara_ya_no_lleva_las_reglas_del_reloj(
    sembrado: tuple[TestClient, int, Any],
) -> None:
    """Si volvieran aquí, volvería el tope de quince minutos con ellas."""
    import asyncio

    _, team_id, factory = sembrado

    async def mirar() -> tuple[set[str], set[str]]:
        async with factory() as s:
            caras = _claves(await _derive_insights(s, team_id))
            reloj = _claves(await _insights_del_reloj(s, team_id))
            return caras, reloj

    caras, reloj = asyncio.run(mirar())
    assert "sync.stale" in reloj
    assert "sync.stale" not in caras
    # Y la parte cara sigue trayendo lo suyo: no se vació por el camino.
    assert caras


def test_la_pantalla_las_sigue_ensenando_juntas(
    sembrado: tuple[TestClient, int, Any],
) -> None:
    client, team_id, _ = sembrado
    respuesta = client.get(f"/api/v1/teams/{team_id}/insights")
    assert respuesta.status_code == 200
    claves = {fila["key"] for fila in respuesta.json()}
    assert "sync.stale" in claves, "el aviso de datos viejos tiene que llegar a la pantalla"
    assert len(claves) > 1, "y con el resto del catálogo, no él solo"
