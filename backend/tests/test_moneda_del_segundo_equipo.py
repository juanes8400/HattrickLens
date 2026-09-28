"""Un segundo equipo hereda la moneda del PRIMERO, no la de cualquiera.

2026-09-28, decision del usuario: «usa la moneda del pais del primer equipo
(y misma tasa de cambio) para los segundos o terceros equipos».

DE DONDE VIENE. Las ligas internacionales --Hattrick Femme y compania-- no
tienen pais ni moneda propios en el catalogo del mundo, asi que su moneda hay
que sacarla de otro club del mismo manager. Eso ya se hacia, pero con un
`limit(1)` SIN ORDENAR: con un solo club hermano acertaba de casualidad, y con
dos en paises distintos el que saliera dependia del orden de la tabla. El
mismo club podia cambiar de moneda entre sincronizaciones.

Ahi esta el «×10» que reporto un usuario: entre un pais de tasa 10 --Colombia--
y otro de tasa 1 la diferencia es exactamente esa, y la aplicacion DIVIDE por
la tasa para enseñar, asi que coger la que no es multiplica o divide por diez
todo el dinero de la pantalla.

Se comprobo antes de elegir esta regla que el pais DEL MANAGER no llega por
ningun lado: los detalles del club traen el idioma del usuario, no su pais, y
el compendio del manager tampoco. Asi que el primer equipo es lo mas cercano
y, sobre todo, lo estable.
"""

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.sync_team import SyncTeamHandler
from app.infrastructure.db import models as m
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

DUENO = 1
#: El club principal: el mas antiguo, de un pais con tasa 10.
PRINCIPAL = (537758, datetime(2015, 10, 6, tzinfo=UTC), "US$", 10.0)
#: Un segundo club, mas nuevo y de un pais con tasa 1.
SEGUNDO = (600001, datetime(2024, 3, 1, tzinfo=UTC), "€", 1.0)
#: El internacional, sin pais ni moneda: es el que hay que resolver.
INTERNACIONAL = 700001


async def _base(orden_de_insercion: tuple[tuple, ...], principal: int | None = None):
    """Los hermanos se insertan en el orden que se pida.

    El orden IMPORTA: es justo lo que hacia que la regla vieja acertara o
    fallara, asi que las pruebas lo fijan a proposito en los dos sentidos.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as s:
        s.add(m.User(id=DUENO, ht_user_id=10857807, login_name="juanes840"))
        await s.flush()
        for ht_team_id, fundado, moneda, tasa in orden_de_insercion:
            s.add(
                m.Team(
                    ht_team_id=ht_team_id,
                    name=f"club {ht_team_id}",
                    owner_user_id=DUENO,
                    founded_at=fundado,
                    currency_name=moneda,
                    currency_rate=tasa,
                    is_primary_club=(None if principal is None else ht_team_id == principal),
                )
            )
            await s.flush()
        internacional = m.Team(
            ht_team_id=INTERNACIONAL,
            name="Pulgas Femme",
            owner_user_id=DUENO,
            founded_at=datetime(2026, 1, 1, tzinfo=UTC),
            # Sin pais: es lo que devuelve el catalogo para una liga
            # internacional, y por eso las dos primeras vias no dan nada.
            ht_league_id=None,
            league_name="",
            currency_name="",
            currency_rate=1.0,
        )
        s.add(internacional)
        await s.commit()
        return factory, internacional.id


async def _resolver(orden: tuple[tuple, ...], principal: int | None = None) -> m.Team:
    factory, team_id = await _base(orden, principal)
    handler = SyncTeamHandler(SqlAlchemyUnitOfWork(factory), None)
    async with SqlAlchemyUnitOfWork(factory) as uow:
        await handler._resolver_moneda(uow, team_id)
        await uow.commit()
    async with factory() as s:
        equipo = await s.scalar(select(m.Team).where(m.Team.id == team_id))
        assert equipo is not None
        return equipo


def test_hereda_la_del_club_principal_venga_en_el_orden_que_venga() -> None:
    """El caso del «×10»: dos hermanos, uno de tasa 10 y otro de tasa 1.

    Con la regla vieja salia uno u otro segun el orden de la tabla. Ahora sale
    SIEMPRE el club mas antiguo, que es el principal del manager.
    """
    primero_el_principal = asyncio.run(_resolver((PRINCIPAL, SEGUNDO)))
    primero_el_segundo = asyncio.run(_resolver((SEGUNDO, PRINCIPAL)))

    for equipo in (primero_el_principal, primero_el_segundo):
        assert equipo.currency_name == "US$"
        assert equipo.currency_rate == 10.0


def test_nunca_se_copia_una_moneda_vacia() -> None:
    """Copiar un vacio deja al club igual de mudo, pero sin vias que probar."""
    sin_moneda = (600002, datetime(2014, 1, 1, tzinfo=UTC), "", 1.0)
    equipo = asyncio.run(_resolver((sin_moneda, PRINCIPAL)))

    # El mas antiguo no tiene moneda, asi que se salta y se coge el siguiente.
    assert equipo.currency_name == "US$"
    assert equipo.currency_rate == 10.0


def test_sin_ningun_hermano_util_se_queda_como_estaba() -> None:
    """Mejor sin moneda que con una inventada: la pantalla ya sabe callarse."""
    equipo = asyncio.run(_resolver(()))

    assert equipo.currency_name == ""


def test_el_principal_gana_aunque_no_tenga_fecha_de_fundacion() -> None:
    """El caso que señalo la revision de la PR #6.

    Al conectar la cuenta los clubes nacen SIN fecha de fundacion: solo se
    rellena al sincronizar cada uno. Si se sincroniza antes un club secundario,
    el principal se queda sin fecha y, ordenando solo por fecha, PIERDE la
    eleccion: el internacional heredaba la moneda del secundario.

    Hattrick dice cual es el principal (`IsPrimaryClub`), y eso se sabe desde
    el alta, que recorre todos los clubes del manager de una vez.
    """
    # El principal, sin fecha. El secundario, con fecha y de otro pais.
    principal_sin_fecha = (PRINCIPAL[0], None, PRINCIPAL[2], PRINCIPAL[3])

    equipo = asyncio.run(_resolver((principal_sin_fecha, SEGUNDO), principal=PRINCIPAL[0]))
    assert equipo.currency_name == "US$"
    assert equipo.currency_rate == 10.0


def test_un_club_del_que_no_consta_si_es_principal_no_se_castiga() -> None:
    """`None` es «no consta», no «no es el principal».

    Un club dado de alta antes de que se guardara ese dato no puede quedar por
    detras de otro marcado explicitamente como NO principal: seria repetir el
    mismo fallo por otro camino.
    """

    async def caso():
        factory, team_id = await _base((PRINCIPAL, SEGUNDO))
        async with factory() as s:
            # Del principal no consta; del secundario consta que NO lo es.
            for equipo in (await s.execute(select(m.Team))).scalars():
                if equipo.ht_team_id == SEGUNDO[0]:
                    equipo.is_primary_club = False
            await s.commit()
        handler = SyncTeamHandler(SqlAlchemyUnitOfWork(factory), None)
        async with SqlAlchemyUnitOfWork(factory) as uow:
            await handler._resolver_moneda(uow, team_id)
            await uow.commit()
        async with factory() as s:
            return await s.scalar(select(m.Team).where(m.Team.id == team_id))

    equipo = asyncio.run(caso())
    assert equipo.currency_name == "US$"
