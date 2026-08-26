"""Las dos rutas de uso, por HTTP.

2026-08-26. Lo que se fija aqui no es que "funcione", sino los limites: que no
se pueda inundar la tabla, que una fecha imposible no ensucie los resumenes y
que el resumen cuadre con lo que se mando.
"""
import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user, require_admin
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.main import app


@pytest.fixture
def cliente():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def montar() -> int:
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)
        async with factory() as s:
            u = m.User(ht_user_id=7, login_name="yo")
            s.add(u)
            await s.commit()
            return u.id

    user_id = asyncio.run(montar())

    async def sesion():
        async with factory() as s:
            yield s

    async def quien_soy():
        async with factory() as s:
            return await s.get(m.User, user_id)

    async def soy_el_admin():
        async with factory() as s:
            return await s.get(m.User, user_id)

    app.dependency_overrides[get_session] = sesion
    app.dependency_overrides[get_current_user] = quien_soy
    # El candado se prueba aparte, en `test_solo_el_admin_ve_el_uso`: repetir
    # aqui la comprobacion en cada prueba de forma escondería lo que miden.
    app.dependency_overrides[require_admin] = soy_el_admin
    yield TestClient(app), factory
    app.dependency_overrides.clear()


def _evento(**cambios):
    base = {
        "sessionId": "s1", "kind": "page", "module": "Juveniles",
        "label": None, "at": "2026-08-26T10:00:00Z", "visibleMs": 60_000,
    }
    base.update(cambios)
    return base


def test_una_tanda_se_guarda_y_sale_en_el_resumen(cliente) -> None:
    client, _ = cliente
    r = client.post("/api/v1/usage/events", json={"events": [
        _evento(),
        _evento(kind="click", label="Qué entrenar", visibleMs=0),
    ]})
    assert r.status_code == 204, r.text

    d = client.get("/api/v1/usage").json()
    assert d["totals"]["pages"] == 1
    assert d["totals"]["clicks"] == 1
    assert d["totals"]["sessions"] == 1
    assert d["modules"][0]["module"] == "Juveniles"
    assert d["modules"][0]["minutes"] == 1.0
    assert d["topControls"][0]["label"] == "Juveniles · Qué entrenar"


def test_no_se_puede_inundar_la_tabla_de_una_vez(cliente) -> None:
    """Sin tope, una pestana con un fallo mandaria un millon de filas."""
    client, _ = cliente
    r = client.post("/api/v1/usage/events", json={
        "events": [_evento() for _ in range(51)]
    })
    assert r.status_code == 422


def test_una_etiqueta_larguisima_se_rechaza(cliente) -> None:
    """El limite es la puerta que impide que alguien meta ahi un texto entero."""
    client, _ = cliente
    r = client.post("/api/v1/usage/events", json={
        "events": [_evento(kind="click", label="x" * 500)]
    })
    assert r.status_code == 422


def test_un_tipo_inventado_se_rechaza(cliente) -> None:
    client, _ = cliente
    r = client.post("/api/v1/usage/events", json={"events": [_evento(kind="loquesea")]})
    assert r.status_code == 422


def test_una_fecha_futura_se_recorta_a_ahora(cliente) -> None:
    """El reloj del navegador puede ir adelantado. Una fecha futura ordenaria
    mal todo y dejaria sesiones que 'duran' semanas."""
    client, factory = cliente
    futuro = (datetime.now(UTC) + timedelta(days=400)).isoformat()
    assert client.post(
        "/api/v1/usage/events", json={"events": [_evento(at=futuro)]}
    ).status_code == 204

    async def leer():
        from sqlalchemy import select
        async with factory() as s:
            return (await s.execute(select(m.UiEvent.at))).scalars().all()

    guardada = asyncio.run(leer())[0]
    assert guardada <= datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=5)


def test_un_tiempo_visible_imposible_se_rechaza(cliente) -> None:
    """Mas de un dia en una sola pantalla no es un dato, es un fallo."""
    client, _ = cliente
    r = client.post("/api/v1/usage/events", json={
        "events": [_evento(visibleMs=99 * 60 * 60 * 1000)]
    })
    assert r.status_code == 422


def test_sin_eventos_el_resumen_no_revienta(cliente) -> None:
    client, _ = cliente
    d = client.get("/api/v1/usage").json()
    assert d["totals"]["sessions"] == 0
    assert d["modules"] == [] and d["recentSessions"] == []


def test_la_poda_borra_lo_viejo_y_respeta_lo_reciente(cliente) -> None:
    """Sin poda la tabla crece sin fin: con cien usuarios son millones de filas
    al año y la base del plan gratuito ronda 1 GB."""
    client, factory = cliente
    from app.api.v1.endpoints.uso import DIAS_QUE_SE_GUARDA, podar_eventos_viejos

    async def corre():
        from sqlalchemy import select
        ahora = datetime.now(UTC).replace(tzinfo=None)
        async with factory() as s:
            s.add(m.UiEvent(
                user_id=1, session_id="viejo", kind="page", module="Liga",
                at=ahora - timedelta(days=DIAS_QUE_SE_GUARDA + 1), visible_ms=0,
            ))
            s.add(m.UiEvent(
                user_id=1, session_id="nuevo", kind="page", module="Liga",
                at=ahora - timedelta(days=1), visible_ms=0,
            ))
            await s.commit()
        async with factory() as s:
            borrados = await podar_eventos_viejos(s)
        async with factory() as s:
            quedan = (await s.execute(select(m.UiEvent.session_id))).scalars().all()
        return borrados, quedan

    borrados, quedan = asyncio.run(corre())
    assert borrados == 1
    assert quedan == ["nuevo"]


# ── El candado de administrador ─────────────────────────────────────────────

def test_sin_administrador_configurado_no_entra_nadie(cliente, monkeypatch) -> None:
    """Falla CERRADO. Un despiste al configurar no puede acabar en que
    cualquier manager vea el uso de todos los demás.

    El valor se fija a `None` a mano en vez de confiar en que el entorno lo
    tenga vacío: al configurar la variable en el `.env` de desarrollo, esta
    prueba pasaba suelta y fallaba dentro de la suite.
    """
    client, _ = cliente
    from app.api.deps import require_admin as real
    from app.core.config import settings
    from app.main import app as la_app

    la_app.dependency_overrides.pop(real, None)   # el candado de verdad
    monkeypatch.setattr(settings, "admin_ht_user_id", None)
    r = client.get("/api/v1/usage")
    assert r.status_code == 403
    assert "administrador" in r.json()["detail"]


def test_otro_manager_no_ve_el_uso(cliente, monkeypatch) -> None:
    """El resumen es de TODOS los usuarios: la comprobacion normal de sesion no
    basta, porque cualquiera con cuenta la pasa."""
    client, _ = cliente
    from app.api.deps import require_admin as real
    from app.core.config import settings
    from app.main import app as la_app

    la_app.dependency_overrides.pop(real, None)
    monkeypatch.setattr(settings, "admin_ht_user_id", 999_999)  # no es el 7
    r = client.get("/api/v1/usage")
    assert r.status_code == 403
    assert "para ti" in r.json()["detail"]


def test_el_admin_si_entra(cliente, monkeypatch) -> None:
    client, _ = cliente
    from app.api.deps import require_admin as real
    from app.core.config import settings
    from app.main import app as la_app

    la_app.dependency_overrides.pop(real, None)
    monkeypatch.setattr(settings, "admin_ht_user_id", 7)   # el del fixture
    assert client.get("/api/v1/usage").status_code == 200


def test_cualquiera_puede_MANDAR_sus_eventos(cliente) -> None:
    """La recogida no lleva candado a proposito: la manda el navegador de cada
    usuario sobre si mismo. Con candado no se mediria a nadie salvo al dueno."""
    client, _ = cliente
    from app.api.deps import require_admin as real
    from app.main import app as la_app

    la_app.dependency_overrides.pop(real, None)
    assert client.post(
        "/api/v1/usage/events", json={"events": [_evento()]}
    ).status_code == 204


# ── La exportacion ──────────────────────────────────────────────────────────

def test_el_csv_sale_abrible_en_Excel(cliente) -> None:
    """Con coma y sin BOM, Excel en espanol mete la fila entera en una columna
    y destroza los acentos."""
    client, _ = cliente
    client.post("/api/v1/usage/events", json={"events": [
        _evento(kind="click", label="Qué entrenar", visibleMs=0),
    ]})
    r = client.get("/api/v1/usage/export.csv")
    assert r.status_code == 200
    texto = r.content.decode("utf-8")
    assert texto.startswith("﻿"), "sin BOM, Excel rompe los acentos"
    assert "cuando;sesion;usuario;tipo;modulo;etiqueta;visible_ms" in texto
    assert "Qué entrenar" in texto
    assert "attachment" in r.headers["content-disposition"]
    assert ".csv" in r.headers["content-disposition"]


def test_el_csv_tambien_lleva_candado(cliente, monkeypatch) -> None:
    client, _ = cliente
    from app.api.deps import require_admin as real
    from app.core.config import settings
    from app.main import app as la_app

    la_app.dependency_overrides.pop(real, None)
    monkeypatch.setattr(settings, "admin_ht_user_id", 999_999)   # no es el 7
    assert client.get("/api/v1/usage/export.csv").status_code == 403
