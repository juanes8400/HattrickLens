"""Quién cambió de clase desde la sincronización anterior (2026-11-18)."""

import asyncio
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.application.queries.cambios_de_clase import comparar
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.main import app
from tests.test_team_overview import seeded  # noqa: F401  (el mismo equipo de prueba)


def _clases(t: str = "titular", r: str = "estrellas", e: str = "pico") -> dict[str, str]:
    return {"titularidad": t, "rentabilidad": r, "etapa": e}


def test_cada_clasificacion_que_cambia_es_un_cambio() -> None:
    cambios = comparar(
        {1: _clases(), 2: _clases()},
        {1: _clases(t="suplencia", e="veterano"), 2: _clases()},
        {1: "Horhoi", 2: "Cobos"},
    )
    assert [(c.name, c.clasificacion, c.antes, c.ahora) for c in cambios] == [
        ("Horhoi", "titularidad", "titular", "suplencia"),
        ("Horhoi", "etapa", "pico", "veterano"),
    ]


def test_quien_llega_o_se_va_no_cambia_de_clase() -> None:
    assert comparar({1: _clases()}, {2: _clases()}, {}) == ()


def test_un_valor_vacio_no_es_un_cambio() -> None:
    # Sin experiencia leída la titularidad sale vacía; no es que bajara.
    assert comparar({1: _clases(t="")}, {1: _clases()}, {}) == ()


def test_la_primera_lectura_se_guarda_y_no_compara_con_nada(
    seeded: tuple[TestClient, int],  # noqa: F811
) -> None:
    client, team_id = seeded
    url = f"/api/v1/teams/{team_id}/player-classes/changes"
    primera = client.get(url).json()
    assert primera["syncId"] is not None
    assert primera["previousSyncId"] is None
    assert primera["changes"] == []
    # Pedirla otra vez no duplica la lectura ni inventa cambios.
    assert client.get(url).json() == primera


def test_con_una_lectura_anterior_salen_los_cambios(
    seeded: tuple[TestClient, int],  # noqa: F811
) -> None:
    client, team_id = seeded
    url = f"/api/v1/teams/{team_id}/player-classes/changes"
    hoy = client.get(url).json()
    jugadores = client.get(f"/api/v1/teams/{team_id}/player-classes").json()["players"]
    alguno = jugadores[0]
    otra = "reserva" if alguno["titularidad"] != "reserva" else "titular"

    async def plantar_la_anterior() -> None:
        gen = app.dependency_overrides[get_session]()
        s = await gen.__anext__()
        for j in jugadores:
            s.add(
                m.PlayerClassReading(
                    team_id=team_id,
                    sync_id=hoy["syncId"] - 1,
                    ht_player_id=j["htPlayerId"],
                    titularidad=otra if j is alguno else j["titularidad"],
                    rentabilidad=j["rentabilidad"],
                    etapa=j["etapa"]["stage"],
                    created_at=datetime.now(UTC),
                )
            )
        await s.commit()
        await gen.aclose()

    asyncio.run(plantar_la_anterior())
    body = client.get(url).json()
    assert body["previousSyncId"] == hoy["syncId"] - 1
    assert body["changes"] == [
        {
            "htPlayerId": alguno["htPlayerId"],
            "playerName": alguno["name"],
            "classification": "titularidad",
            "before": otra,
            "after": alguno["titularidad"],
        }
    ]
