"""El botón de Transferencias, por HTTP y de punta a punta.

2026-08-25. Tres arreglos seguidos de la barra se dieron por buenos sin haber
pasado nunca por la ruta real: el fallo estaba en la forma de la respuesta o
en el servidor, no en la lógica que sí se probaba. Esta prueba pulsa el botón
como lo pulsa el navegador.
"""
import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.infrastructure.security.tokens import encrypt_token
from app.main import app

VENTAS = [
    ("Reciente", 900_000_003, datetime(2026, 8, 20)),
    ("Medio", 900_000_002, datetime(2024, 7, 16)),
    ("Viejo", 900_000_001, datetime(2020, 9, 10)),
]


class CHPPMudo:
    """Lo que se mide es la respuesta de la ruta, no lo que diga Hattrick."""

    def __init__(self, *_a: Any, **_k: Any) -> None:
        pass

    async def fetch(self, file: str, version: str = "latest", **_p: Any) -> dict:
        return {}

    async def aclose(self) -> None:
        return None


@pytest.fixture
def cliente(monkeypatch: pytest.MonkeyPatch):
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def montar() -> tuple[int, int]:
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)
        async with factory() as s:
            equipo = m.Team(ht_team_id=537758, name="Pulgas Arrechas")
            usuario = m.User(ht_user_id=7, login_name="yo")
            s.add_all([equipo, usuario])
            await s.flush()
            s.add(m.CHPPToken(
                user_id=usuario.id, status="active",
                oauth_token_enc=encrypt_token("t"),
                oauth_secret_enc=encrypt_token("s"),
            ))
            for apellido, ht_id, vendido in VENTAS:
                s.add(m.Player(
                    team_id=equipo.id, ht_player_id=ht_id,
                    first_name="Ex", last_name=apellido,
                    sold_at=vendido, purchased_at=datetime(2018, 1, 1),
                    purchase_price=1000,
                ))
            await s.commit()
            return equipo.id, usuario.id

    team_id, user_id = asyncio.run(montar())

    async def sesion():
        async with factory() as s:
            yield s

    async def quien_soy():
        async with factory() as s:
            return await s.get(m.User, user_id)

    monkeypatch.setattr(
        "app.api.v1.endpoints.teams.CHPPClient", CHPPMudo, raising=True
    )
    # IMPRESCINDIBLE: la ruta no usa la sesion inyectada para el trabajo largo,
    # construye el manejador con `SessionLocal` global. Sin sustituirlo, esta
    # prueba escribe en la base de desarrollo de verdad --paso: marco siete
    # ex-jugadores como revisados sin haberlos revisado--.
    monkeypatch.setattr(
        "app.api.v1.endpoints.teams.SessionLocal", factory, raising=True
    )
    app.dependency_overrides[get_session] = sesion
    app.dependency_overrides[get_current_user] = quien_soy
    yield TestClient(app), team_id
    app.dependency_overrides.clear()


def test_el_boton_responde_con_el_mapa_del_barrido(cliente) -> None:
    """La forma exacta que pinta la barra. Si esto cambia, la barra se queda
    muda y cae al porcentaje de siempre sin decir nada."""
    client, team_id = cliente
    pulsacion = "2026-08-25T12:45:02.597000Z"

    r = client.post(
        f"/api/v1/teams/{team_id}/backfill/run?batch=1&since={pulsacion}"
    )
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert set(cuerpo) >= {"status", "done", "pending", "players", "queue"}
    mapa = cuerpo["queue"]
    assert mapa is not None, "sin mapa la barra no puede pintarse"
    assert set(mapa) == {"total", "done", "front"}
    assert mapa["total"] == 3
    assert mapa["done"] == [0], "el primero es la cabeza de la cola"
    assert mapa["front"] == 1


def test_el_eje_no_se_mueve_entre_pulsaciones(cliente) -> None:
    """Lo que se veia como "alumbra una parte y luego se quita": el ancho
    cambiaba y las marcas ya puestas saltaban de sitio o se apagaban."""
    client, team_id = cliente
    pulsacion = "2026-08-25T12:45:02.597000Z"

    mapas = []
    for _ in range(3):
        r = client.post(
            f"/api/v1/teams/{team_id}/backfill/run?batch=1&since={pulsacion}"
        )
        assert r.status_code == 200, r.text
        mapas.append(r.json()["queue"])

    assert [x["total"] for x in mapas] == [3, 3, 3], "el eje se congela"
    assert [len(x["done"]) for x in mapas] == [1, 2, 3]
    for antes, despues in zip(mapas, mapas[1:]):
        assert set(antes["done"]) < set(despues["done"]), "nada se apaga"
    assert mapas[-1]["front"] == 3, "barrido completo, barra llena"


def test_una_pulsacion_nueva_empieza_un_barrido_nuevo(cliente) -> None:
    """Cada pulsacion manda su propia marca de tiempo y congela su propio eje:
    la barra arranca de cero, no continua la de antes.

    Las marcas van con el reloj de verdad --el navegador manda
    `new Date().toISOString()`-- porque el mapa se deduce comparando la hora
    de cada revision con la del arranque del barrido. Con horas inventadas en
    el pasado, revisiones posteriores contarian como ya hechas.
    """
    client, team_id = cliente

    primera = datetime.now(UTC).replace(tzinfo=None)
    r1 = client.post(
        f"/api/v1/teams/{team_id}/backfill/run"
        f"?batch=1&since={primera.isoformat()}Z"
    )
    assert r1.status_code == 200, r1.text
    assert r1.json()["queue"]["done"] == [0]

    # El instante de la pulsacion, ni antes ni despues: la revision de la
    # primera quedo detras y la de esta caera delante.
    segunda = datetime.now(UTC).replace(tzinfo=None)
    r2 = client.post(
        f"/api/v1/teams/{team_id}/backfill/run"
        f"?batch=1&since={segunda.isoformat()}Z"
    )
    assert r2.status_code == 200, r2.text
    # Una sola marca: la del barrido nuevo. Cual sea depende del turno --la
    # segunda pulsacion toca al azar-- y fijarla seria una prueba tramposa;
    # lo que se exige es que NO arrastre la del barrido anterior.
    mapa = r2.json()["queue"]
    assert len(mapa["done"]) == 1, "el barrido nuevo empieza de cero"
    assert mapa["total"] == 3, "y vuelve a congelar su propio eje"


def test_sin_marca_de_tiempo_no_se_inventa_un_mapa(cliente) -> None:
    """El goteo automatico llama sin `since`. Devolver ahi el eje guardado de
    otro barrido pintaria una barra que no corresponde a nada."""
    client, team_id = cliente
    r = client.post(f"/api/v1/teams/{team_id}/backfill/run?batch=1")
    assert r.status_code == 200, r.text
    assert r.json()["queue"] is None


def test_el_informe_llega_con_cada_lote(cliente) -> None:
    """Pedido el 2026-08-25: al parar --a mano o al acabarse la cola-- hay que
    poder decir cuantos siguen, cuantos faltan y que se cerro, por motivo.

    Viaja en CADA respuesta, no solo en la ultima: el usuario puede pulsar
    "Parar" en cualquier momento y la pantalla tiene que poder pintarlo con lo
    ultimo que recibio.
    """
    client, team_id = cliente
    pulsacion = "2026-08-25T12:45:02.597000Z"

    r = client.post(
        f"/api/v1/teams/{team_id}/backfill/run?batch=1&since={pulsacion}"
    )
    assert r.status_code == 200, r.text
    b = r.json()["balance"]
    assert b is not None
    assert set(b) == {"open", "toCheck", "closed", "closedTotal", "commissions"}
    assert b["open"] == 3, "los tres siguen vivos"
    assert b["toCheck"] == 2, "se miro uno de tres"
    assert b["closed"] == {}
    assert b["closedTotal"] == 0


def test_lo_que_falta_baja_a_cero_al_terminar(cliente) -> None:
    client, team_id = cliente
    pulsacion = "2026-08-25T12:45:02.597000Z"

    for _ in range(3):
        r = client.post(
            f"/api/v1/teams/{team_id}/backfill/run?batch=1&since={pulsacion}"
        )
        assert r.status_code == 200, r.text
    assert r.json()["balance"]["toCheck"] == 0


def test_sin_marca_de_tiempo_tampoco_hay_informe(cliente) -> None:
    """Mismo criterio que el mapa: sin barrido no hay nada que resumir."""
    client, team_id = cliente
    r = client.post(f"/api/v1/teams/{team_id}/backfill/run?batch=1")
    assert r.status_code == 200, r.text
    assert r.json()["balance"] is None
