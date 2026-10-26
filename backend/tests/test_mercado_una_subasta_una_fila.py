"""Una fila del fondo es UNA SUBASTA, no un jugador.

2026-10-26, decision del usuario preparando el barrido diario: «Jugador +
Plazo, aunque despues haya transferID cuando se termina».

La clave de antes era solo el jugador, y el barrido diario la rompe por los dos
lados: el mismo anuncio se ve dias seguidos (una subasta, no siete) y el mismo
jugador puede vender dos veces (dos subastas, no una). Hattrick cuenta las dos
--el 490357848 sale dos veces en su propio Comparador, a 215.220 y a 125.000,
medido en AP14-- asi que perder la primera era perder un comparable que el
juego si usa.
"""

import asyncio
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.mercado_comparable import guardar
from app.domain.engines.mercado_comparable import Guardado, Rasgo
from app.infrastructure.db import models as m

AHORA = datetime(2026, 10, 26, 12, 0, tzinfo=UTC)
LUNES = "2026-10-27 18:30:00"
MARTES = "2026-10-28 18:30:00"


def _venta(jugador: int = 777, *, precio: int = 1_000_000, firme: bool = False) -> Guardado:
    return Guardado(
        ht_player_id=jugador,
        nombre="Vendido",
        precio=precio,
        firme=firme,
        puja=precio,
        visto_el=AHORA,
        edad=25,
        primaria=Rasgo("scoring", 18),
        secundaria=Rasgo("passing", 13),
        terciaria=Rasgo("playmaking", 7),
    )


@pytest.fixture()
def fondo():
    """Un equipo con su fondo, en memoria."""
    motor = create_async_engine(
        "sqlite+aiosqlite:///:memory:", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    fabrica = async_sessionmaker(motor, expire_on_commit=False)

    async def montar() -> int:
        async with motor.begin() as conexion:
            await conexion.run_sync(m.Base.metadata.create_all)
        async with fabrica() as s:
            equipo = m.Team(ht_team_id=1, name="Pulgas", owner_user_id=1)
            s.add(equipo)
            await s.commit()
            return int(equipo.id)

    equipo_id = asyncio.run(montar())
    yield fabrica, equipo_id
    asyncio.run(motor.dispose())


def _filas(fabrica, equipo_id) -> list[m.MarketSale]:
    async def leer():
        async with fabrica() as s:
            return list(
                (
                    await s.execute(
                        select(m.MarketSale)
                        .where(m.MarketSale.team_id == equipo_id)
                        .order_by(m.MarketSale.deadline)
                    )
                ).scalars()
            )

    return asyncio.run(leer())


def _guardar(fabrica, equipo_id, ventas, plazos) -> int:
    async def correr():
        async with fabrica() as s:
            cuantas = await guardar(s, equipo_id, ventas, plazos)
            await s.commit()
            return cuantas

    return asyncio.run(correr())


# ── Las dos mitades de la regla ──────────────────────────────────────────────


def test_el_mismo_anuncio_visto_dos_dias_es_UNA_fila(fondo) -> None:
    """Lo que pasa todos los dias desde que el barrido es diario."""
    fabrica, equipo = fondo
    assert _guardar(fabrica, equipo, [_venta()], {777: LUNES}) == 1
    assert _guardar(fabrica, equipo, [_venta()], {777: LUNES}) == 0
    assert len(_filas(fabrica, equipo)) == 1


def test_dos_ventas_del_mismo_jugador_son_DOS_filas(fondo) -> None:
    """El caso medido en AP14, y el que la clave vieja perdia.

    Con `(equipo, jugador)` la segunda venta sobrescribia a la primera y nos
    quedabamos con un comparable donde Hattrick cuenta dos.
    """
    fabrica, equipo = fondo
    assert _guardar(fabrica, equipo, [_venta(precio=215_220)], {777: LUNES}) == 1
    assert _guardar(fabrica, equipo, [_venta(precio=125_000)], {777: MARTES}) == 1
    filas = _filas(fabrica, equipo)
    assert [f.price for f in filas] == [215_220, 125_000]
    assert len({f.deadline for f in filas}) == 2


def test_dos_jugadores_distintos_no_se_estorban(fondo) -> None:
    fabrica, equipo = fondo
    assert _guardar(fabrica, equipo, [_venta(1), _venta(2)], {1: LUNES, 2: LUNES}) == 2
    assert len(_filas(fabrica, equipo)) == 2


# ── Lo que el barrido diario romperia si no se mirara ────────────────────────


def test_volver_a_ver_el_anuncio_no_borra_los_intentos_de_resolucion(fondo) -> None:
    """Si los borrara, una venta que Hattrick nunca publica no se abandonaria.

    Los intentos se reinician SOLO en una fila nueva. Antes se ponian a cero en
    cada guardado, y con una busqueda semanal daba igual porque la fila era
    nueva casi siempre.
    """
    fabrica, equipo = fondo
    _guardar(fabrica, equipo, [_venta()], {777: LUNES})

    async def gastar_un_intento():
        async with fabrica() as s:
            fila = (await s.execute(select(m.MarketSale))).scalar_one()
            fila.resolve_attempts = 3
            await s.commit()

    asyncio.run(gastar_un_intento())
    _guardar(fabrica, equipo, [_venta()], {777: LUNES})
    assert _filas(fabrica, equipo)[0].resolve_attempts == 3


def test_un_precio_de_verdad_no_se_pisa_con_una_puja(fondo) -> None:
    """La fila resuelta se queda como esta.

    Antes no hacia falta mirarlo --una venta resuelta no volvia a verse porque
    la fila se buscaba por jugador-- pero ahora las filas duran, y cambiar un
    precio de cierre por una puja seria deshacer justo lo que la resolucion
    vino a arreglar.
    """
    fabrica, equipo = fondo
    _guardar(fabrica, equipo, [_venta(precio=5_090_000, firme=True)], {777: LUNES})
    _guardar(fabrica, equipo, [_venta(precio=4_990_000, firme=False)], {777: LUNES})
    fila = _filas(fabrica, equipo)[0]
    assert fila.price == 5_090_000 and fila.is_final is True


def test_sin_plazo_se_agrupa_por_el_jugador_en_vez_de_duplicar(fondo) -> None:
    """No deberia pasar, pero si pasara no puede crecer sin freno.

    La restriccion de la base no protege aqui: en SQL dos nulos son distintos,
    asi que cada barrido abriria otra fila y en una semana habria siete copias.
    """
    fabrica, equipo = fondo
    assert _guardar(fabrica, equipo, [_venta()], {}) == 1
    assert _guardar(fabrica, equipo, [_venta()], {}) == 0
    assert len(_filas(fabrica, equipo)) == 1
