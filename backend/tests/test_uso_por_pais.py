"""De donde es la gente que usa la aplicacion.

2026-09-28, pedido del usuario: un mapa del mundo con los paises de los
usuarios, coloreado por numero de clics.

El pais NO se pregunta ni se deduce de la conexion: sale de la liga del club,
que Hattrick ya publica. Lo que fijan estas pruebas es lo que puede salir mal
con esa eleccion:

- que con varios clubes se coja el que no es --el mismo fallo de la moneda, que
  costo un «x10» en todas las pantallas de dinero--,
- y que quien no tenga pais desaparezca de la suma en vez de contarse aparte.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user, require_admin
from app.domain.engines.uso_de_la_app import Evento, por_pais
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.main import app

T0 = datetime(2026, 9, 28, 10, 0, 0)


def _ev(usuario, sesion, tipo, minuto):
    return Evento(sesion, tipo, "Liga", None, T0 + timedelta(minutes=minuto), 0, usuario)


# ── La aritmetica ────────────────────────────────────────────────────────────


def test_se_agrupa_por_pais_y_se_ordena_por_clics() -> None:
    """El color del mapa va por CLICS, asi que ese es el orden.

    Dos personas de un pais que solo miran colorean menos que una de otro que
    trabaja dentro, y esa es justo la diferencia que el mapa viene a enseñar.
    """
    eventos = [
        _ev(1, "a", "page", 0),
        _ev(2, "b", "page", 1),
        _ev(2, "b", "click", 2),
        _ev(2, "b", "click", 3),
        _ev(3, "c", "click", 4),
    ]
    # 1 y 3 son del mismo pais; 2 es de otro.
    paises = por_pais(eventos, {1: ("co", "Colombia"), 2: ("se", "Suecia"), 3: ("co", "Colombia")})

    assert [p.codigo for p in paises] == ["se", "co"]
    suecia, colombia = paises
    assert suecia.clics == 2 and suecia.usuarios == 1 and suecia.paginas == 1
    assert colombia.clics == 1 and colombia.usuarios == 2 and colombia.sesiones == 2


def test_quien_no_tiene_pais_se_cuenta_aparte_y_no_se_pierde() -> None:
    """Sumar mal es peor que decir «de estos no se sabe».

    Hay dos maneras de quedarse sin pais: registrarse y no sincronizar nunca, y
    tener el club en una liga internacional, que no pertenece a ningun pais.
    Ninguna de las dos puede hacer que unos clics desaparezcan del total.
    """
    eventos = [_ev(1, "a", "click", 0), _ev(9, "z", "click", 1)]
    paises = por_pais(eventos, {1: ("co", "Colombia")})

    sin_pais = [p for p in paises if p.codigo == ""]
    assert len(sin_pais) == 1
    assert sin_pais[0].clics == 1
    assert sum(p.clics for p in paises) == 2


# ── De donde sale el pais ────────────────────────────────────────────────────


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
            await s.flush()
            # Dos ligas de dos paises, como las devuelve el mundo de Hattrick.
            s.add(m.WorldContext(ht_league_id=19, country_code="CO", country_name="Colombia"))
            s.add(m.WorldContext(ht_league_id=3, country_code="SE", country_name="Suecia"))
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
    yield TestClient(app), factory, user_id
    app.dependency_overrides.clear()


def _mandar_un_clic(client) -> None:
    ahora = (datetime.now(UTC) - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = client.post(
        "/api/v1/usage/events",
        json={
            "events": [
                {
                    "sessionId": "s1",
                    "kind": "click",
                    "module": "Liga",
                    "label": "Ordenar",
                    "at": ahora,
                    "visibleMs": 0,
                }
            ]
        },
    )
    assert r.status_code == 204, r.text


def _clubes(factory, user_id, clubes) -> None:
    async def guardar():
        async with factory() as s:
            for ht_team_id, liga, principal in clubes:
                s.add(
                    m.Team(
                        ht_team_id=ht_team_id,
                        name=f"club {ht_team_id}",
                        owner_user_id=user_id,
                        ht_league_id=liga,
                        is_primary_club=principal,
                    )
                )
            await s.commit()

    asyncio.run(guardar())


def test_el_pais_sale_de_la_liga_del_club(cliente) -> None:
    client, factory, user_id = cliente
    _clubes(factory, user_id, [(1, 19, True)])
    _mandar_un_clic(client)

    paises = client.get("/api/v1/usage?dias=0").json()["byCountry"]
    assert [(p["code"], p["users"], p["clicks"]) for p in paises] == [("co", 1, 1)]


def test_con_varios_clubes_manda_el_principal(cliente) -> None:
    """El mismo fallo que la moneda, por el mismo sitio.

    Un manager colombiano con un segundo club en Suecia es colombiano. Y no
    vale desempatar por la fecha de fundacion: al conectar la cuenta los clubes
    nacen SIN fecha y solo la reciben al sincronizarse uno a uno, asi que el
    principal puede perfectamente no tenerla todavia.
    """
    # El sueco va primero a proposito: si el orden de la tabla decidiera, seria
    # el que sale.
    _clubes(cliente[1], cliente[2], [(2, 3, False), (1, 19, True)])
    _mandar_un_clic(cliente[0])

    paises = cliente[0].get("/api/v1/usage?dias=0").json()["byCountry"]
    assert [p["code"] for p in paises] == ["co"]


def test_sin_club_sincronizado_se_cuenta_pero_sin_sitio_en_el_mapa(cliente) -> None:
    client, _, _ = cliente
    _mandar_un_clic(client)

    paises = client.get("/api/v1/usage?dias=0").json()["byCountry"]
    assert [(p["code"], p["clicks"]) for p in paises] == [("", 1)]
