"""Vigilancia por persona: el resumen desglosado y el registro crudo.

2026-09-01, pedido del usuario: «quiero la información mucho más desglosada por
usuario, casi tan precisa como un log y con unas excelentes sumarizaciones».

Lo que se fija aquí es lo que la ruta tiene que sostener para que eso sea cierto
y no una tabla bonita:

  * que cada evento llegue con SU dueño --antes el endpoint leía `user_id` y lo
    tiraba, así que todo se agregaba en un solo número--,
  * que el registro se pueda filtrar y paginar en el servidor,
  * que la lista de pantallas conocidas no se desincronice del frontend, porque
    de ella sale «lo que nadie abrió» y una lista vieja miente en silencio.
"""

import asyncio
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user, require_admin
from app.api.v1.endpoints.uso import MODULOS_CONOCIDOS
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.main import app


@pytest.fixture
def cliente():
    """Dos usuarios, a propósito: con uno solo, un desglose por persona pasa
    todas las pruebas sin desglosar nada."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def montar() -> tuple[int, int]:
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)
        async with factory() as s:
            ana = m.User(ht_user_id=7, login_name="Ana")
            beto = m.User(ht_user_id=8, login_name="Beto")
            s.add_all([ana, beto])
            await s.commit()
            return ana.id, beto.id

    ana, beto = asyncio.run(montar())
    quien = {"id": ana}

    async def sesion():
        async with factory() as s:
            yield s

    async def usuario_actual():
        async with factory() as s:
            return await s.get(m.User, quien["id"])

    app.dependency_overrides[get_session] = sesion
    app.dependency_overrides[get_current_user] = usuario_actual
    app.dependency_overrides[require_admin] = usuario_actual
    yield TestClient(app), quien, ana, beto
    app.dependency_overrides.clear()


def _ev(modulo, **c):
    base = {
        "sessionId": "s1",
        "kind": "page",
        "module": modulo,
        "label": None,
        "at": "2026-08-26T10:00:00Z",
        "visibleMs": 60_000,
    }
    base.update(c)
    return base


def _sembrar(client, quien, ana, beto):
    """Ana vive en Juveniles; Beto entra a Economía y toca dos cosas."""
    quien["id"] = ana
    assert (
        client.post(
            "/api/v1/usage/events",
            json={
                "events": [
                    _ev("Juveniles"),
                    _ev("Juveniles", at="2026-08-27T10:00:00Z", sessionId="s2"),
                    _ev("Juveniles", kind="click", label="Ojeadores", visibleMs=0),
                ]
            },
        ).status_code
        == 204
    )
    quien["id"] = beto
    assert (
        client.post(
            "/api/v1/usage/events",
            json={
                "events": [
                    _ev("Economía", sessionId="b1"),
                    _ev("Economía", kind="click", label="Proyección", visibleMs=0, sessionId="b1"),
                    _ev("Economía", kind="click", label="Patrocinio", visibleMs=0, sessionId="b1"),
                ]
            },
        ).status_code
        == 204
    )
    quien["id"] = ana


def test_el_resumen_dice_quien_hizo_cada_cosa(cliente) -> None:
    """La prueba que habría cazado el fallo original: el endpoint construía los
    eventos SIN `user_id`, así que todo el mundo era el usuario 0."""
    client, quien, ana, beto = cliente
    _sembrar(client, quien, ana, beto)

    d = client.get("/api/v1/usage?dias=365").json()
    por_nombre = {u["name"]: u for u in d["byUser"]}
    assert set(por_nombre) == {"Ana", "Beto"}
    assert por_nombre["Ana"]["pages"] == 2 and por_nombre["Ana"]["clicks"] == 1
    assert por_nombre["Beto"]["pages"] == 1 and por_nombre["Beto"]["clicks"] == 2
    # Ana volvió otro día; Beto no. Es la señal de que algo se usa de verdad.
    assert por_nombre["Ana"]["activeDays"] == 2
    assert por_nombre["Beto"]["activeDays"] == 1
    assert por_nombre["Ana"]["favouriteModule"] == "Juveniles"
    # Y cada persona trae su propio desglose, sin otra petición.
    assert [x["module"] for x in por_nombre["Beto"]["modules"]] == ["Economía"]


def test_la_adopcion_se_mide_contra_los_activos(cliente) -> None:
    client, quien, ana, beto = cliente
    _sembrar(client, quien, ana, beto)

    d = client.get("/api/v1/usage?dias=365").json()
    assert d["activeUsers"] == 2
    assert d["registeredUsers"] == 2
    filas = {a["module"]: a for a in d["adoption"]}
    assert filas["Juveniles"]["users"] == 1
    assert filas["Juveniles"]["reach"] == 50.0
    assert filas["Economía"]["clicksPerVisit"] == 2.0


def test_lo_que_nadie_abrio_sale_por_su_nombre(cliente) -> None:
    client, quien, ana, beto = cliente
    _sembrar(client, quien, ana, beto)

    d = client.get("/api/v1/usage?dias=365").json()
    assert "Juveniles" not in d["untouched"]
    assert "Copa" in d["untouched"]


def test_dentro_de_cada_pantalla_se_ve_lo_suyo(cliente) -> None:
    client, quien, ana, beto = cliente
    _sembrar(client, quien, ana, beto)

    d = client.get("/api/v1/usage?dias=365").json()
    dentro = {x["module"]: x["controls"] for x in d["insideEach"]}
    assert {c["label"] for c in dentro["Economía"]} == {"Proyección", "Patrocinio"}


# ── El registro crudo ───────────────────────────────────────────────────────


def test_el_registro_viene_del_mas_reciente_al_mas_viejo(cliente) -> None:
    client, quien, ana, beto = cliente
    _sembrar(client, quien, ana, beto)

    d = client.get("/api/v1/usage/log?dias=365").json()
    assert d["total"] == 6
    marcas = [f["at"] for f in d["rows"]]
    assert marcas == sorted(marcas, reverse=True)
    assert d["rows"][0]["name"] in ("Ana", "Beto")


def test_se_filtra_por_persona_pantalla_y_tipo(cliente) -> None:
    client, quien, ana, beto = cliente
    _sembrar(client, quien, ana, beto)

    solo_beto = client.get(f"/api/v1/usage/log?dias=365&usuario={beto}").json()
    assert solo_beto["total"] == 3
    assert {f["name"] for f in solo_beto["rows"]} == {"Beto"}

    solo_clics = client.get("/api/v1/usage/log?dias=365&tipo=click").json()
    assert solo_clics["total"] == 3

    solo_juveniles = client.get("/api/v1/usage/log?dias=365&modulo=Juveniles").json()
    assert solo_juveniles["total"] == 3


def test_se_busca_por_la_etiqueta_del_control(cliente) -> None:
    client, quien, ana, beto = cliente
    _sembrar(client, quien, ana, beto)

    d = client.get("/api/v1/usage/log?dias=365&buscar=proyec").json()
    assert d["total"] == 1
    assert d["rows"][0]["label"] == "Proyección"


def test_la_pagina_no_se_arma_en_el_navegador(cliente) -> None:
    """`total` cuenta TODO lo que cumple el filtro, no lo que cabe en la página.
    Sin eso el navegador no puede saber si hay más y la paginación miente."""
    client, quien, ana, beto = cliente
    _sembrar(client, quien, ana, beto)

    primera = client.get("/api/v1/usage/log?dias=365&cuantas=2").json()
    assert primera["total"] == 6 and len(primera["rows"]) == 2

    segunda = client.get("/api/v1/usage/log?dias=365&cuantas=2&desde_fila=2").json()
    assert segunda["total"] == 6 and len(segunda["rows"]) == 2
    assert {f["id"] for f in primera["rows"]}.isdisjoint({f["id"] for f in segunda["rows"]})


def test_un_tipo_inventado_no_pasa(cliente) -> None:
    client, _, _, _ = cliente
    assert client.get("/api/v1/usage/log?tipo=loquesea").status_code == 422


# ── La lista de pantallas ───────────────────────────────────────────────────

MAPA = Path(__file__).resolve().parents[2] / "frontend" / "src" / "services" / "telemetria.ts"


def test_la_lista_de_pantallas_no_se_queda_atras() -> None:
    """De `MODULOS_CONOCIDOS` sale «lo que nadie abrió». Si el frontend añade
    una pantalla y aquí no se añade, esa pantalla no aparece jamás --ni usada ni
    olvidada--, y el hueco no se ve. Al revés miente igual: una que ya no existe
    saldría para siempre como abandonada.

    Ya pasó algo así el 2026-08-31 con «Motor»/«Transparencia»: el mapa se quedó
    sin la entrada nueva unas horas y el módulo más consultado del mes cayó en
    «Otros».
    """
    fuente = MAPA.read_text(encoding="utf-8")
    trozo = fuente.split("const MODULOS")[1].split("];")[0]
    del_frontend = set(re.findall(r'"([^"]+)"\]', trozo))
    assert del_frontend, "no se pudo leer el mapa del frontend"
    assert del_frontend == set(MODULOS_CONOCIDOS), (
        "sobran aquí: "
        + ", ".join(sorted(MODULOS_CONOCIDOS - del_frontend))
        + " | faltan aquí: "
        + ", ".join(sorted(del_frontend - MODULOS_CONOCIDOS))
    )
