"""Que se guarda de cada club al CONECTAR la cuenta, antes de sincronizar nada.

El alta es un momento especial: los detalles del club se piden sin decir cual,
y Hattrick contesta con TODOS los del manager de una vez. Es la unica ocasion
en que se sabe de todos a la vez, y de ahi salen las dos cosas que luego
deciden a quien pertenece que --cual es el principal y en que pais juega cada
uno--; todo lo demas espera a que se sincronice cada club, uno a uno.

Esto ha fallado DOS VECES seguidas, las dos por lo mismo: un campo que llegaba
en la respuesta y no se guardaba.

- PR #6: no se guardaba cual era el principal, y un club de liga internacional
  sincronizado antes que el principal heredaba la moneda del que no era.
- PR #7: no se guardaba la liga del pais, y el mapa de Uso cruza justo por ese
  campo, asi que el principal todavia sin sincronizar no cruzaba con ningun
  pais y la persona salia en el del club secundario.

Por eso la prueba mira campo a campo y no «que funcione».
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.auth_chpp import guardar_los_clubes
from app.infrastructure.db import models as m

#: Tal cual lo devuelve el lector de los detalles del club: dos clubes de un
#: mismo manager, en dos paises distintos, y Hattrick diciendo cual es cual.
CLUBES = [
    {
        "ht_team_id": 537758,
        "name": "Pulgas Arrechas",
        "league_name": "Colombia",
        "series_name": "V.92",
        "series_ht_id": 123456,
        "ht_league_id": 19,
        "is_primary_club": True,
    },
    {
        "ht_team_id": 600001,
        "name": "Pulgas Femme",
        "league_name": "Hattrick Femme",
        "series_name": "II.3",
        "series_ht_id": 999,
        "ht_league_id": 1000,
        "is_primary_club": False,
    },
]


async def _alta(clubes):
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as s:
        u = m.User(ht_user_id=10857807, login_name="juanes840")
        s.add(u)
        await s.flush()
        primero = await guardar_los_clubes(s, u.id, clubes)
        await s.commit()
    async with factory() as s:
        equipos = (
            (await s.execute(select(m.Team).order_by(m.Team.ht_team_id))).scalars().all()
        )
    return primero, equipos


def test_el_alta_guarda_el_pais_y_el_principal_de_cada_club() -> None:
    """Los dos campos que no se pueden esperar a la sincronizacion.

    `ht_league_id` es el pais y `is_primary_club` es de quien manda. Sin
    cualquiera de los dos, un manager con varios clubes queda atribuido al que
    no es hasta que sincronice el principal, que puede no pasar nunca.
    """
    _, equipos = asyncio.run(_alta(CLUBES))

    principal, femme = equipos
    assert principal.ht_team_id == 537758
    assert principal.is_primary_club is True
    assert principal.ht_league_id == 19
    assert femme.is_primary_club is False
    assert femme.ht_league_id == 1000


def test_el_alta_deja_los_dos_clubes_del_mismo_dueno() -> None:
    """Si el segundo se quedara sin dueño, no saldria en ninguna de las dos
    consultas que recorren «los clubes de esta persona»."""
    _, equipos = asyncio.run(_alta(CLUBES))

    duenos = {e.owner_user_id for e in equipos}
    assert len(duenos) == 1 and None not in duenos


def test_se_devuelve_el_primero_para_llevar_alli_al_navegador() -> None:
    primero, equipos = asyncio.run(_alta(CLUBES))
    assert primero == next(e.id for e in equipos if e.ht_team_id == 537758)


def test_un_club_sin_id_se_ignora_en_vez_de_crear_una_fila_vacia() -> None:
    """`ht_team_id` es la identidad: sin el no hay nada que guardar, y una fila
    con id cero se llevaria por delante a la siguiente que llegase igual."""
    _, equipos = asyncio.run(_alta([{"name": "sin id"}, *CLUBES]))
    assert [e.ht_team_id for e in equipos] == [537758, 600001]


def test_volver_a_conectar_no_duplica_ni_borra_lo_que_ya_habia() -> None:
    """Reconectar es lo normal --caduca el permiso, se cambia de navegador-- y
    no puede crear un club nuevo ni vaciar lo que ya tenia."""

    async def caso():
        engine = create_async_engine(
            "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as s:
            u = m.User(ht_user_id=10857807, login_name="juanes840")
            s.add(u)
            await s.flush()
            await guardar_los_clubes(s, u.id, CLUBES)
            await s.commit()
            # Lo que llega despues, al sincronizar: la moneda de verdad.
            equipo = await s.scalar(select(m.Team).where(m.Team.ht_team_id == 537758))
            equipo.currency_name = "US$"
            equipo.currency_rate = 10.0
            await s.commit()
            await guardar_los_clubes(s, u.id, CLUBES)
            await s.commit()
        async with factory() as s:
            return (await s.execute(select(m.Team))).scalars().all()

    equipos = asyncio.run(caso())
    assert len(equipos) == 2
    principal = next(e for e in equipos if e.ht_team_id == 537758)
    assert principal.currency_name == "US$" and principal.currency_rate == 10.0
