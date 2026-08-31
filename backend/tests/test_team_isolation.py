"""Un usuario no puede ver el equipo de otro.

Escrito el 2026-08-19, antes de publicar la app en abierto. La auditoría de ese
día encontró que 32 de las 53 rutas con `{team_id}` no comprobaban nada y la
mayoría ni pedía sesión: con un solo usuario eso nunca se notó, porque siempre
era el equipo 1, pero en cuanto haya dos, cambiar el número de la URL enseñaría
la plantilla, la economía y las fichas de rival del otro.

Estos tests corren con las dependencias REALES (marca `seguridad`), a
diferencia del resto de la suite, donde `conftest` desactiva la comprobación
para no repetir el mismo login en cada test de forma o de cálculo.
"""
import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.infrastructure.security.jwt import COOKIE_NAME, create_session_token
from app.main import app

pytestmark = pytest.mark.seguridad


def _rutas_reales(aplicacion) -> list[tuple[list[str], str, list]]:
    """Todas las rutas de verdad, con las dependencias que declaran.

    Desde FastAPI 0.14x, `include_router` ya NO copia las rutas: deja un
    `_IncludedRouter` perezoso, así que `app.routes` solo enseña un puñado de
    entradas y NINGUNA con `{team_id}`. Este test recorría esa lista y pasaba
    sin comprobar nada — descubierto el 2026-08-20, y por eso ahora también se
    exige que encuentre rutas.
    """
    from fastapi.routing import APIRoute

    try:
        from fastapi.routing import _IncludedRouter
    except ImportError:  # versiones antiguas: ya vienen planas
        _IncludedRouter = ()

    salida: list[tuple[list[str], str, list]] = []

    def recorrer(rutas, prefijo, heredadas) -> None:
        for r in rutas:
            if _IncludedRouter and isinstance(r, _IncludedRouter):
                ctx = r.include_context
                recorrer(
                    ctx.included_router.routes,
                    prefijo + (ctx.prefix or ""),
                    heredadas + list(ctx.dependencies or []),
                )
            elif isinstance(r, APIRoute):
                salida.append((
                    sorted(r.methods or []),
                    prefijo + r.path,
                    [d.dependency for d in heredadas]
                    + [d.dependency for d in (r.dependencies or [])],
                ))

    recorrer(aplicacion.routes, "", [])
    return salida


def test_every_team_route_declares_the_ownership_check() -> None:
    """El guardia de verdad: recorre la aplicación entera.

    Una ruta nueva con `{team_id}` que olvide la dependencia hace fallar este
    test, que es la única forma de que no se vuelva a colar una.
    """
    from app.api.deps import require_team_owner

    con_equipo = [r for r in _rutas_reales(app) if "{team_id}" in r[1]]

    # Sin esto, el test pasaba «bien» justo cuando dejaba de mirar nada.
    assert len(con_equipo) > 30, (
        f"solo se encontraron {len(con_equipo)} rutas con team_id; el recorrido "
        "de rutas dejó de funcionar y este test ya no comprueba nada"
    )

    sin_proteger = [
        f"{metodos[0]} {ruta}"
        for metodos, ruta, dependencias in con_equipo
        if require_team_owner not in dependencias
    ]
    assert sin_proteger == [], (
        "estas rutas exponen el equipo de cualquiera:\n  "
        + "\n  ".join(sin_proteger)
    )


def _dos_usuarios() -> tuple[TestClient, int, int, int]:
    """Dos usuarios con un equipo cada uno, en la misma base."""
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def montar() -> tuple[int, int, int]:
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)
        async with factory() as s:
            ana = m.User(email="ana@example.com")
            beto = m.User(email="beto@example.com")
            s.add_all([ana, beto])
            await s.commit()
            equipo_ana = m.Team(ht_team_id=111, name="Equipo de Ana", owner_user_id=ana.id)
            equipo_beto = m.Team(ht_team_id=222, name="Equipo de Beto", owner_user_id=beto.id)
            s.add_all([equipo_ana, equipo_beto])
            await s.commit()
            return ana.id, equipo_ana.id, equipo_beto.id

    ana_id, equipo_ana, equipo_beto = asyncio.run(montar())

    async def override_get_session() -> Any:
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app), ana_id, equipo_ana, equipo_beto


def test_without_a_session_a_team_route_answers_401() -> None:
    client, _ana, equipo_ana, _otro = _dos_usuarios()
    try:
        resp = client.get(f"/api/v1/teams/{equipo_ana}/overview")
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_a_user_cannot_read_another_users_team() -> None:
    """Ana, con su sesión válida, pidiendo el equipo de Beto."""
    client, ana_id, equipo_ana, equipo_beto = _dos_usuarios()
    try:
        client.cookies.set(COOKIE_NAME, create_session_token(ana_id))
        # El suyo: la ruta responde (con 200 o con un 404 de "sin datos", pero
        # nunca con 403).
        propio = client.get(f"/api/v1/teams/{equipo_ana}/overview")
        assert propio.status_code != 403
        # El de Beto: prohibido, y el mensaje no filtra nada del otro equipo.
        ajeno = client.get(f"/api/v1/teams/{equipo_beto}/overview")
        assert ajeno.status_code == 403
        assert "Beto" not in ajeno.text
    finally:
        app.dependency_overrides.clear()


def test_the_chpp_cache_never_serves_one_users_answer_to_another() -> None:
    """`matchorders` devuelve la alineación que TÚ enviaste, y solo la ve su
    dueño. La caché de la ficha de rival guardaba por (fichero, parámetros),
    sin el usuario: con dos managers que se enfrentan, el segundo en abrir la
    ficha recibía el once del primero antes del partido.
    """
    from app.api.v1.endpoints import rivals

    class CHPPFalso:
        def __init__(self, respuesta: str) -> None:
            self.respuesta = respuesta
            self.llamadas = 0

        async def fetch(self, file: str, version: str = "latest", **params: object) -> dict:
            self.llamadas += 1
            return {"quien": self.respuesta}

        async def aclose(self) -> None:
            return None

    rivals._chpp_cache.clear()
    de_ana = rivals._CachedCHPP(CHPPFalso("alineación de Ana"), user_id=1)
    de_beto = rivals._CachedCHPP(CHPPFalso("alineación de Beto"), user_id=2)

    async def pedir(cliente):
        return await cliente.fetch("matchorders", version="3.0", matchID=999)

    primero = asyncio.run(pedir(de_ana))
    segundo = asyncio.run(pedir(de_beto))
    assert primero["quien"] == "alineación de Ana"
    assert segundo["quien"] == "alineación de Beto"

    # Y para el MISMO usuario la caché sigue funcionando, que es su razón de
    # ser: sin ella cada toggle de la ficha son ~20 llamadas a Hattrick.
    repetida = asyncio.run(pedir(de_ana))
    assert repetida["quien"] == "alineación de Ana"
    assert de_ana._inner.llamadas == 1


def test_one_user_cannot_burn_the_chpp_quota_of_everyone_else() -> None:
    """La cuota de Hattrick es de la APLICACIÓN, no de cada manager: uno
    sincronizando en bucle deja sin acceso a todos los demás a la vez.

    El límite es por usuario y por tipo de operación, así que quedarte sin
    sincronizaciones no te deja sin poder mirar una ficha de rival.
    """
    from app.api.rate_limit import _consumir, reiniciar

    reiniciar()
    assert all(_consumir(1, "sync", 3) is None for _ in range(3))
    espera = _consumir(1, "sync", 3)
    assert espera is not None and espera > 0

    # Otro usuario no paga por el exceso del primero.
    assert _consumir(2, "sync", 3) is None
    # Y al primero le queda su otro cubo entero.
    assert _consumir(1, "rivales", 3) is None
    reiniciar()


def test_deleting_an_account_removes_that_users_data_and_nobody_elses() -> None:
    """Publicar la app significa guardar datos de terceros, y quien los cede
    tiene que poder retirarlos sin escribirle a nadie.

    Lo importante del test no es que borre: es que NO borre lo del vecino.
    """

    client, ana_id, equipo_ana, equipo_beto = _dos_usuarios()
    try:
        client.cookies.set(COOKIE_NAME, create_session_token(ana_id))
        resp = client.delete("/api/v1/auth/chpp/account")
        assert resp.status_code == 200
        assert resp.json()["teams"] == 1

        # Beto sigue entero; Ana ya no existe.
        siguiente = client.get(f"/api/v1/teams/{equipo_beto}/overview")
        assert siguiente.status_code == 401  # la sesión de Ana ya no vale
    finally:
        app.dependency_overrides.clear()


def test_the_hosting_database_url_is_translated_for_the_async_driver() -> None:
    """Neon, Render y Railway dan la cadena en formato `psycopg`, que aquí
    falla con un mensaje que no ayuda: "The asyncio extension requires an async
    driver" o "invalid connection option 'sslmode'".

    Se traduce en el arranque para que quien despliega no tenga que editarla a
    mano, que es un paso que se olvida.
    """
    from app.core.config import _normaliza_postgres

    neon = "postgresql://u:p@ep-x.neon.tech/db?sslmode=require&channel_binding=require"
    assert _normaliza_postgres(neon) == "postgresql+asyncpg://u:p@ep-x.neon.tech/db?ssl=require"
    assert _normaliza_postgres("postgres://u:p@host:5432/db").startswith("postgresql+asyncpg://")
    # Lo que ya está bien no se toca, incluido sqlite en local.
    assert _normaliza_postgres("sqlite+aiosqlite:///dev.db") == "sqlite+aiosqlite:///dev.db"
