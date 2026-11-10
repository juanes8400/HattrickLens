"""La Copa predice lo mismo que la ficha de rival, y lo hace aunque la bandera
de Hattrick todavía diga que estás eliminado.

2026-11-09, lo vio el usuario el primer día de la temporada 84: «se supone que
ya debemos [tener] predicción de copa, pero no aparece predicción (debe ser la
misma de si me voy a "Rivales")».

DOS COSAS LA TAPABAN, y aquí se fija que no vuelvan:

  · `still_in_cup` sigue en «no» desde la eliminación de la temporada pasada
    hasta que se juega el primer partido de la copa nueva. La pantalla se
    fiaba de la bandera antes que del cruce ya programado: tarjeta de
    eliminado, y ni un intento de predecir.
  · La predicción propia de Copa miraba hacia atrás sólo las semanas ya
    jugadas de la temporada. En la semana 1 es una, sin oficiales dentro.

La segunda desaparece con el cálculo viejo: Copa ya no resume nada por su
cuenta, le pide la predicción a la ficha de ese rival. Por eso lo que se
prueba aquí es la plomería --cuándo se pide, con qué, y que lo que llega se
pinta tal cual--; el número lo prueban las pruebas de la ficha.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.main import app
from tests.test_cup_endpoint import seeded  # noqa: F401  (es la base de estas pruebas)

#: El cruce de copa que trae la base de pruebas: contra Leones de la Selva.
PARTIDO = 767370369

#: Lo que contestaría la ficha de rival, ya con sus nombres de salida.
FICHA = {
    "prediction": {
        "esCopa": True,
        "hayCruce": True,
        "metodoPropio": "submitted",
        "metodoRival": "max",
        "indirectasPrestadas": False,
        "ownProbability": 0.6123,
        "drawProbability": None,
        "rivalProbability": 0.3877,
        "expectedOwnGoals": 2.14,
        "expectedRivalGoals": 1.37,
        "mostLikelyScore": "2-1",
        "ownMatches": 5,
        "rivalMatches": 4,
    },
    # Se pidió «alineación enviada» y no había: la ficha cayó al promedio.
    "pitchZoneMethodOwn": "average",
    "pitchZoneMethodRival": "max",
}


async def _preparar(*, bandera: bool | None, cuando: datetime) -> int:
    """Pone la bandera, la fecha del cruce y un dueño. Devuelve el id del rival."""
    gen = app.dependency_overrides[get_session]()
    session = await gen.__anext__()
    usuario = m.User(login_name="dueño")
    session.add(usuario)
    await session.flush()
    equipo = (await session.execute(select(m.Team))).scalar_one()
    equipo.still_in_cup = bandera
    equipo.owner_user_id = usuario.id
    partido = (
        await session.execute(select(m.Match).where(m.Match.ht_match_id == PARTIDO))
    ).scalar_one()
    partido.played_at = cuando
    rival = (
        partido.away_team_ht_id
        if partido.home_team_ht_id == equipo.ht_team_id
        else partido.home_team_ht_id
    )
    await session.commit()
    await gen.aclose()
    return int(rival)


class _FichaFalsa:
    """Hace de ficha de rival y apunta con qué la llamaron."""

    def __init__(self, respuesta: dict[str, Any] | Exception) -> None:
        self.respuesta = respuesta
        self.llamadas: list[dict[str, Any]] = []

    async def __call__(self, team_id: int, rival_ht_team_id: int, **resto: Any) -> dict[str, Any]:
        self.llamadas.append({"team_id": team_id, "rival": rival_ht_team_id, **resto})
        if isinstance(self.respuesta, Exception):
            raise self.respuesta
        return self.respuesta


@pytest.fixture
def ficha(monkeypatch: pytest.MonkeyPatch) -> _FichaFalsa:
    falsa = _FichaFalsa(FICHA)
    monkeypatch.setattr("app.api.v1.endpoints.rivals.rival_scouting", falsa)
    return falsa


MANANA = datetime.now(UTC) + timedelta(days=1)
AYER = datetime.now(UTC) - timedelta(days=1)


def test_con_la_bandera_en_NO_y_un_cruce_programado_HAY_prediccion(
    seeded: tuple[TestClient, int],  # noqa: F811
    ficha: _FichaFalsa,
) -> None:
    """El caso del usuario: eliminado la temporada pasada, cruce nuevo a la vista."""
    client, team_id = seeded
    rival = asyncio.run(_preparar(bandera=False, cuando=MANANA))

    body = client.get(f"/api/v1/teams/{team_id}/cup").json()

    assert body["status"]["stillInCup"] is True, "un cruce programado es seguir en la copa"
    assert body["prediction"] is not None
    assert len(ficha.llamadas) == 1
    assert ficha.llamadas[0]["rival"] == rival
    assert ficha.llamadas[0]["team_id"] == team_id


def test_lo_que_se_pinta_es_LO_QUE_DICE_LA_FICHA_sin_recalcular(
    seeded: tuple[TestClient, int],  # noqa: F811
    ficha: _FichaFalsa,
) -> None:
    """«Debe ser la misma de si me voy a Rivales»: ni un decimal de diferencia."""
    client, team_id = seeded
    asyncio.run(_preparar(bandera=True, cuando=MANANA))

    dicho = client.get(f"/api/v1/teams/{team_id}/cup").json()["prediction"]

    de_la_ficha = FICHA["prediction"]
    assert isinstance(de_la_ficha, dict)
    for campo in (
        "ownProbability",
        "rivalProbability",
        "expectedOwnGoals",
        "expectedRivalGoals",
        "mostLikelyScore",
        "ownMatches",
        "rivalMatches",
        "indirectasPrestadas",
    ):
        assert dicho[campo] == de_la_ficha[campo], campo
    # El método que de verdad se usó, no el que se pidió: la ficha cayó al
    # promedio porque no había alineación enviada, y el selector lo enseña.
    assert dicho["metodoPropio"] == "average"
    assert dicho["metodoRival"] == "max"


def test_los_dos_selectores_viajan_hasta_la_ficha(
    seeded: tuple[TestClient, int],  # noqa: F811
    ficha: _FichaFalsa,
) -> None:
    client, team_id = seeded
    asyncio.run(_preparar(bandera=True, cuando=MANANA))

    client.get(
        f"/api/v1/teams/{team_id}/cup",
        params={"pitch_zone_method_own": "last", "pitch_zone_method_rival": "max"},
    )

    llamada = ficha.llamadas[0]
    assert llamada["pitch_zone_method_own"] == "last"
    assert llamada["pitch_zone_method_rival"] == "max"
    # Los oficiales, que es lo que la ficha enseña al abrirla.
    assert llamada["include_competitive"] is True
    assert llamada["include_friendlies"] is False


def test_un_partido_viejo_sin_cerrar_NO_resucita_a_un_eliminado(
    seeded: tuple[TestClient, int],  # noqa: F811
    ficha: _FichaFalsa,
) -> None:
    """«Programado» es con la fecha por delante. Un partido de esta temporada
    que se quedó sin marcar como terminado no vale más que la bandera."""
    client, team_id = seeded
    asyncio.run(_preparar(bandera=False, cuando=AYER))

    body = client.get(f"/api/v1/teams/{team_id}/cup").json()

    assert body["status"]["stillInCup"] is False
    assert body["prediction"] is None
    assert ficha.llamadas == [], "y no se gasta ni una llamada en predecir"


def test_si_la_ficha_no_puede_contestar_la_pantalla_SIGUE_EN_PIE(
    seeded: tuple[TestClient, int],  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sin sesión de Hattrick o con Hattrick caído, la ficha contesta con un
    error porque es su pantalla. En Copa es un panel más: se queda vacío y el
    resto se pinta."""
    caida = _FichaFalsa(HTTPException(503, "Hattrick no responde"))
    monkeypatch.setattr("app.api.v1.endpoints.rivals.rival_scouting", caida)
    client, team_id = seeded
    asyncio.run(_preparar(bandera=True, cuando=MANANA))

    resp = client.get(f"/api/v1/teams/{team_id}/cup")

    assert resp.status_code == 200
    body = resp.json()
    assert body["prediction"] is None
    assert len(body["nextMatches"]) == 1, "el cruce se sigue enseñando"
    assert len(caida.llamadas) == 1
