"""El libro de visitas: leer firmas y dejar una.

2026-09-05. Lo que se protege aqui es que una firma diga quien la escribio
--el CLUB, no la cuenta-- y que no se pueda firmar sin sesion: un libro
abierto en internet se llena de basura en un dia.
"""

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.main import app


@pytest.fixture
def cliente() -> Any:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def setup() -> int:
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)
        async with factory() as s:
            user = m.User(ht_user_id=1, login_name="juanes")
            s.add(user)
            await s.flush()
            s.add(
                m.Team(
                    ht_team_id=537758,
                    name="Pulgas Arrechas",
                    league_name="Colombia",
                    owner_user_id=user.id,
                )
            )
            await s.commit()
            return user.id

    user_id = asyncio.run(setup())

    async def override_session() -> Any:
        async with factory() as s:
            yield s

    async def override_user() -> m.User:
        async with factory() as s:
            return await s.get(m.User, user_id)

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = override_user
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_una_firma_sale_con_el_nombre_del_club_y_no_con_el_de_la_cuenta(
    cliente: TestClient,
) -> None:
    """En Hattrick uno se conoce por su equipo. Publicar el login de alguien
    seria dar un dato que no hace falta para nada."""
    r = cliente.post("/api/v1/guestbook", json={"message": "Me falta ver la copa"})
    assert r.status_code == 201
    firma = r.json()
    assert firma["teamName"] == "Pulgas Arrechas"
    assert firma["country"] == "Colombia"
    assert "juanes" not in str(firma), "el nombre de la cuenta no puede salir"


def test_las_firmas_se_leen_de_la_mas_nueva_a_la_mas_vieja(cliente: TestClient) -> None:
    for texto in ("primera", "segunda", "tercera"):
        assert cliente.post("/api/v1/guestbook", json={"message": texto}).status_code == 201
    mensajes = [f["message"] for f in cliente.get("/api/v1/guestbook").json()["entries"]]
    assert mensajes == ["tercera", "segunda", "primera"]


def test_un_mensaje_de_solo_espacios_no_es_una_firma(cliente: TestClient) -> None:
    """Pydantic exige un caracter y un espacio lo es, asi que sin esto quedaba
    una firma en blanco en el libro."""
    assert cliente.post("/api/v1/guestbook", json={"message": "   "}).status_code == 422
    assert cliente.get("/api/v1/guestbook").json()["entries"] == []


def test_el_mensaje_tiene_tope(cliente: TestClient) -> None:
    """Mil caracteres son unos tres parrafos: sitio para contar que te falta y
    poco para convertir el libro en un blog."""
    assert cliente.post("/api/v1/guestbook", json={"message": "a" * 1001}).status_code == 422
    assert cliente.post("/api/v1/guestbook", json={"message": "a" * 1000}).status_code == 201


def test_una_firma_escondida_no_se_lee(cliente: TestClient) -> None:
    """La moderacion esconde, no borra: sin la fila no habria forma de saber
    que decia cuando alguien pregunte por que desaparecio."""
    creada = cliente.post("/api/v1/guestbook", json={"message": "spam"}).json()
    assert len(cliente.get("/api/v1/guestbook").json()["entries"]) == 1

    async def esconder() -> None:
        gen = app.dependency_overrides[get_session]()
        s = await gen.__anext__()
        fila = await s.get(m.GuestbookEntry, creada["id"])
        fila.hidden = True
        await s.commit()

    asyncio.run(esconder())
    assert cliente.get("/api/v1/guestbook").json()["entries"] == []
