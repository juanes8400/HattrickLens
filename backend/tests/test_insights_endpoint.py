"""GET /teams/{id}/insights — HL-130 a nivel HTTP.

Caso real que motivó este test: el propio entrenador del club (Volodymyr
Manakin, 44 años) aparecía en la alerta "caros de entrenar" junto a los
veteranos genuinos. La identidad del entrenador viene de `TrainerID` en
training.xml (ya parseado como `TrainingSnapshot.trainer_ht_id`), no de una
heurística sobre sus stats — por eso este test usa el fixture real, donde el
entrenador (PlayerID 434712334) convive en el roster con un veterano genuino
(Robert Horhoi) que sí debe seguir apareciendo en la alerta.
"""
from datetime import UTC, datetime
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
def seeded() -> tuple[TestClient, int, Any]:
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
    yield client, team_id, factory
    app.dependency_overrides.clear()


def test_the_clubs_own_trainer_is_excluded_from_expensive_training_alert(
    seeded: tuple[TestClient, int, Any],
) -> None:
    client, team_id, _ = seeded
    resp = client.get(f"/api/v1/teams/{team_id}/insights")
    assert resp.status_code == 200

    training_alert = next(
        (i for i in resp.json() if i["key"] == "training.inefficient"), None
    )
    assert training_alert is not None
    flagged = training_alert["evidence"]["players"]
    assert "Volodymyr Manakin" not in flagged
    # La fórmula por tramos ya no castiga por edad solamente: un nivel técnico
    # nulo puede seguir siendo barato, mientras un nivel alto sí cruza el umbral.
    assert "Raúl Cobos" in flagged


def test_archiving_an_alert_moves_it_from_the_active_list_to_the_inbox(
    seeded: tuple[TestClient, int, Any],
) -> None:
    client, team_id, _ = seeded
    active = client.get(f"/api/v1/teams/{team_id}/insights").json()
    key = active[0]["key"]

    assert client.post(f"/api/v1/teams/{team_id}/insights/{key}/archive").status_code == 200

    keys_now = [i["key"] for i in client.get(f"/api/v1/teams/{team_id}/insights").json()]
    assert key not in keys_now
    assert len(keys_now) == len(active) - 1

    inbox = client.get(f"/api/v1/teams/{team_id}/insights/archived").json()
    assert [i["key"] for i in inbox] == [key]
    # El buzón guarda el texto, no una referencia: se sigue leyendo aunque la
    # condición que lo disparó desaparezca.
    assert inbox[0]["title"] == active[0]["title"]
    assert inbox[0]["detail"] == active[0]["detail"]
    assert inbox[0]["stillActive"] is True


def test_restoring_from_the_inbox_puts_the_alert_back(
    seeded: tuple[TestClient, int, Any],
) -> None:
    client, team_id, _ = seeded
    key = client.get(f"/api/v1/teams/{team_id}/insights").json()[0]["key"]
    client.post(f"/api/v1/teams/{team_id}/insights/{key}/archive")

    assert client.delete(f"/api/v1/teams/{team_id}/insights/{key}/archive").status_code == 200
    assert client.get(f"/api/v1/teams/{team_id}/insights/archived").json() == []
    assert key in [i["key"] for i in client.get(f"/api/v1/teams/{team_id}/insights").json()]


def test_an_archived_alert_comes_back_by_itself_when_its_content_changes(
    seeded: tuple[TestClient, int, Any],
) -> None:
    """Archivar acusa recibo de UN hecho, no apaga la regla.

    Si "pierdes 300.000 por semana" pasa a "pierdes 900.000 por semana", la
    huella del contenido deja de coincidir y la alerta vuelve sola a la lista
    activa. Sin esto, un clic distraído podría esconder para siempre un aviso
    financiero que empeora.
    """
    import asyncio

    from sqlalchemy import select

    client, team_id, factory = seeded
    key = client.get(f"/api/v1/teams/{team_id}/insights").json()[0]["key"]
    client.post(f"/api/v1/teams/{team_id}/insights/{key}/archive")
    assert key not in [i["key"] for i in client.get(f"/api/v1/teams/{team_id}/insights").json()]

    async def rewrite_fingerprint() -> None:
        async with factory() as s:
            row = await s.scalar(
                select(m.DismissedInsight).where(m.DismissedInsight.key == key)
            )
            row.fingerprint = "otra-cifra-otro-aviso"
            await s.commit()

    asyncio.run(rewrite_fingerprint())

    assert key in [i["key"] for i in client.get(f"/api/v1/teams/{team_id}/insights").json()]
    # Y el buzón lo dice sin rodeos: lo archivado ya no es lo que pasa hoy.
    assert client.get(f"/api/v1/teams/{team_id}/insights/archived").json()[0]["stillActive"] is False


def test_archiving_an_alert_that_is_not_active_is_a_404(
    seeded: tuple[TestClient, int, Any],
) -> None:
    client, team_id, _ = seeded
    resp = client.post(f"/api/v1/teams/{team_id}/insights/inventada.no.existe/archive")
    assert resp.status_code == 404


def test_an_orphaned_archived_row_never_shows_up_in_the_inbox(
    seeded: tuple[TestClient, int, Any],
) -> None:
    """Una archivada de una regla borrada se queda en la base sin nada que
    pueda regenerarla. Enseñarla sería prometer un aviso que no llega."""
    import asyncio

    client, team_id, factory = seeded

    async def archive_a_dead_rule() -> None:
        async with factory() as s:
            s.add(m.DismissedInsight(
                team_id=team_id, key="player.overpaid.474426586",
                fingerprint="x", severity="warning",
                title="Regla borrada", detail="", action="", module="plantilla",
                dismissed_at=datetime.now(UTC),
            ))
            await s.commit()

    asyncio.run(archive_a_dead_rule())
    inbox = client.get(f"/api/v1/teams/{team_id}/insights/archived").json()
    assert "player.overpaid.474426586" not in [i["key"] for i in inbox]


def test_only_the_current_weeks_deficit_survives_in_the_inbox(
    seeded: tuple[TestClient, int, Any],
) -> None:
    """El déficit lleva la semana en la clave a propósito, para que archivar el
    de una semana no tape el de la siguiente. El efecto secundario era que cada
    semana archivada dejaba su fila para siempre: en una temporada, dieciséis
    filas de lo mismo en el buzón.

    2026-08-17, pedido explícito: solo sobrevive la de la semana en curso. Al
    archivar la nueva, la vieja se borra de la base — y mientras tanto no se
    enseña, porque su semana ya no vuelve.
    """
    import asyncio

    from sqlalchemy import func, select

    client, team_id, factory = seeded
    activas = client.get(f"/api/v1/teams/{team_id}/insights").json()
    esta_semana = next(
        i["key"] for i in activas if i["key"].startswith("economy.structural_deficit")
    )
    assert esta_semana != "economy.structural_deficit", "la clave debe llevar la semana"

    async def archive_last_week() -> None:
        async with factory() as s:
            s.add(m.DismissedInsight(
                team_id=team_id, key="economy.structural_deficit.83-01",
                fingerprint="x", severity="warning",
                title="Tu club pierde dinero esta semana (83-01)",
                detail="", action="", module="economía",
                dismissed_at=datetime.now(UTC),
            ))
            await s.commit()

    async def count_rows() -> int:
        async with factory() as s:
            return await s.scalar(select(func.count()).select_from(m.DismissedInsight))

    asyncio.run(archive_last_week())

    # La semana pasada no se enseña, aunque su fila siga en la base.
    inbox = client.get(f"/api/v1/teams/{team_id}/insights/archived").json()
    assert [i["key"] for i in inbox] == []
    assert asyncio.run(count_rows()) == 1

    # Y al archivar la de esta semana, la vieja se va de verdad.
    assert client.post(
        f"/api/v1/teams/{team_id}/insights/{esta_semana}/archive"
    ).status_code == 200
    inbox = client.get(f"/api/v1/teams/{team_id}/insights/archived").json()
    assert [i["key"] for i in inbox] == [esta_semana]
    assert asyncio.run(count_rows()) == 1

    # Archivar el déficit no puede llevarse por delante alertas de otra familia.
    otra = next(i["key"] for i in activas if not i["key"].startswith("economy."))
    client.post(f"/api/v1/teams/{team_id}/insights/{otra}/archive")
    assert client.post(
        f"/api/v1/teams/{team_id}/insights/{esta_semana}/archive"
    ).status_code == 200
    inbox_keys = {i["key"] for i in client.get(
        f"/api/v1/teams/{team_id}/insights/archived").json()}
    assert inbox_keys == {esta_semana, otra}
