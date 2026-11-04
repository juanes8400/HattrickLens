"""El canal del autor hacia quien usa la herramienta.

2026-11-03, pedido por el usuario: «un módulo para comunicarle cosas a los
usuarios de la herramienta: que yo escriba un mensaje que quiera que les llegue
en forma de alerta y ellos lo vean».

Lo que se fija aquí es lo que hace que el aviso LLEGUE y que se pueda parar:

1. Publicado, sale como alerta con su clave propia (`author.notice.{id}`), de
   modo que dos avisos se archivan por separado.
2. Retirado, deja de salir, pero la fila sigue: quien lo archivó tiene un
   apunte que apunta a esa clave, y borrarla lo dejaría huérfano para siempre.
3. Caducado por su propia fecha, deja de salir sin que nadie toque nada. Es la
   única de las tres que pasa sola, así que es la que hay que comprobar contra
   el reloj.
4. Una severidad que no reconozcamos no tira el Panel: se degrada a `info`.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user, require_admin
from app.api.v1.endpoints.analysis import alertas
from app.domain.engines import insights as ins
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.main import app


@pytest.fixture
def cliente():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
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

    app.dependency_overrides[get_session] = sesion
    app.dependency_overrides[get_current_user] = quien_soy
    app.dependency_overrides[require_admin] = quien_soy
    yield TestClient(app), factory
    app.dependency_overrides.clear()


def _publica(c: TestClient, **extra) -> int:
    cuerpo = {
        "title": "El domingo Hattrick corta la API",
        "detail": "De 08:00 a 12:00 no se podrá sincronizar.",
    }
    cuerpo.update(extra)
    r = c.post("/api/v1/avisos", json=cuerpo)
    assert r.status_code == 201, r.text
    return int(r.json()["id"])


def _vivos(factory, ahora: datetime | None = None) -> list[ins.Insight]:
    async def corre() -> list[ins.Insight]:
        async with factory() as s:
            avisos = await alertas._avisos_vivos(
                s, ahora or datetime.now(UTC).replace(tzinfo=None)
            )
            return ins.avisos_del_autor(avisos)

    return asyncio.run(corre())


def test_lo_publicado_sale_como_alerta_con_clave_propia(cliente) -> None:
    c, factory = cliente
    primero = _publica(c)
    segundo = _publica(c, title="Otra cosa", detail="Y otro cuerpo.")

    salida = _vivos(factory)
    claves = [i.key for i in salida]
    # Una clave por aviso: si compartieran clave, archivar uno taparía el otro.
    assert claves == [f"author.notice.{segundo}", f"author.notice.{primero}"]
    # Y la clave tiene que ser reconocible para el buzón, o su archivado se
    # descartaría como huérfano en la siguiente carga.
    assert all(ins.is_known_key(k) for k in claves)
    assert salida[1].title == "El domingo Hattrick corta la API"
    assert salida[1].detail == "De 08:00 a 12:00 no se podrá sincronizar."


def test_retirado_deja_de_salir_pero_la_fila_se_queda(cliente) -> None:
    c, factory = cliente
    aviso_id = _publica(c)
    assert len(_vivos(factory)) == 1

    assert c.post(f"/api/v1/avisos/{aviso_id}/retirar").status_code == 204
    assert _vivos(factory) == []

    # Sigue en la lista del autor, marcado: es el único sitio donde queda qué
    # se dijo y cuándo.
    filas = c.get("/api/v1/avisos").json()["avisos"]
    assert len(filas) == 1
    assert filas[0]["retiredAt"] is not None
    assert filas[0]["vivo"] is False

    # Y se puede volver a publicar sin escribirlo otra vez.
    assert c.post(f"/api/v1/avisos/{aviso_id}/retirar?retirado=false").status_code == 204
    assert len(_vivos(factory)) == 1


def test_caduca_solo_a_su_hora(cliente) -> None:
    c, factory = cliente
    ahora = datetime.now(UTC).replace(tzinfo=None)
    _publica(c, until=(ahora + timedelta(hours=2)).isoformat())

    # Antes de la hora se ve.
    assert len(_vivos(factory, ahora)) == 1
    # Después, no, y sin que nadie haya tocado nada: es lo que distingue a
    # `until` de retirar a mano.
    assert _vivos(factory, ahora + timedelta(hours=3)) == []


def test_una_severidad_desconocida_no_tira_el_panel(cliente) -> None:
    c, factory = cliente
    # Por HTTP se rechaza, que es donde hay que verlo: un error de dedo se
    # corrige al escribir, no en el Panel de doce personas.
    r = c.post(
        "/api/v1/avisos",
        json={"title": "x", "detail": "y", "severity": "gravísimo"},
    )
    assert r.status_code == 422

    # Pero si una fila vieja o una migración dejara una severidad rara, la
    # regla la degrada en vez de reventar.
    salida = ins.avisos_del_autor(
        [ins.AvisoDelAutor(id=1, title="x", detail="y", action="", severity="gravísimo")]
    )
    assert salida[0].severity is ins.Severity.INFO


def test_cada_severidad_llega_tal_como_se_eligio(cliente) -> None:
    c, factory = cliente
    for severidad in ("info", "opportunity", "warning", "danger"):
        _publica(c, severity=severidad, detail=f"cuerpo {severidad}")
    salida = _vivos(factory)
    # Al revés, porque se listan del más nuevo al más viejo.
    assert [i.severity.value for i in salida] == [
        "danger",
        "warning",
        "opportunity",
        "info",
    ]


def test_un_aviso_vacio_no_se_publica(cliente) -> None:
    c, _ = cliente
    assert c.post("/api/v1/avisos", json={"title": "", "detail": "algo"}).status_code == 422
    assert c.post("/api/v1/avisos", json={"title": "algo", "detail": ""}).status_code == 422


def test_retirar_lo_que_no_existe_es_un_404(cliente) -> None:
    c, _ = cliente
    assert c.post("/api/v1/avisos/999/retirar").status_code == 404
