"""Las dos salvaguardias del libro de transferencias.

1. Un movimiento sin identificador de jugador no se tira: usa el numero de su
   transferencia, y la etapa queda marcada como "sin origen conocido" en vez de
   pasar por canterana.
2. Cuando el club esta en los dos lados, la venta es tan real como la compra y
   se anotan las dos.
"""
import asyncio
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.sync_team import SyncTeamHandler
from app.infrastructure.db import models as m
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

MI_EQUIPO = 537758
OTRO = 999


async def _uow() -> tuple[SqlAlchemyUnitOfWork, int]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        equipo = m.Team(ht_team_id=MI_EQUIPO, name="Pulgas Arrechas")
        s.add(equipo)
        await s.commit()
        return SqlAlchemyUnitOfWork(factory), equipo.id


def _venta_sin_identificador() -> dict[str, Any]:
    return {
        "ht_transfer_id": 349926669, "ht_player_id": 0,
        "player_name": "Anders Byström", "deadline": "2021-06-26 18:00:00",
        "price": 99140000, "buyer_team_id": OTRO, "seller_team_id": MI_EQUIPO,
        "tsi": 1000,
    }


def test_una_venta_sin_identificador_ya_no_se_tira() -> None:
    async def corre() -> None:
        uow, team_id = await _uow()
        async with uow:
            await SyncTeamHandler(uow, None)._guardar_transferencia(
                uow, team_id, MI_EQUIPO, _venta_sin_identificador()
            )
            await uow.commit()
        async with uow:
            fila = await uow.session.scalar(select(m.TeamTransfer))
        assert fila is not None, "la venta se perdio"
        assert fila.ht_player_id == 349926669, "no tomo prestado el numero de la transferencia"
        assert fila.is_buy is False

    asyncio.run(corre())


def test_el_numero_prestado_no_le_pisa_el_sitio_a_nadie() -> None:
    """Salvaguardia: si ese numero ya es de un jugador real, se pierde la venta.

    Atribuirsela al jugador equivocado seria peor que no tenerla.
    """
    async def corre() -> None:
        uow, team_id = await _uow()
        async with uow:
            uow.session.add(m.Player(
                ht_player_id=349926669, team_id=team_id,
                first_name="Alguien", last_name="Real",
            ))
            await uow.session.flush()
            await SyncTeamHandler(uow, None)._guardar_transferencia(
                uow, team_id, MI_EQUIPO, _venta_sin_identificador()
            )
            await uow.commit()
        async with uow:
            assert await uow.session.scalar(select(m.TeamTransfer)) is None

    asyncio.run(corre())


def test_estar_en_los_dos_lados_deja_dos_filas() -> None:
    async def corre() -> None:
        uow, team_id = await _uow()
        movimiento = {
            "ht_transfer_id": 400, "ht_player_id": 77, "player_name": "Patrice Ramsey",
            "deadline": "2026-01-26 00:40:00", "price": 7760000,
            "buyer_team_id": MI_EQUIPO, "seller_team_id": MI_EQUIPO, "tsi": 5,
        }
        async with uow:
            h = SyncTeamHandler(uow, None)
            await h._guardar_transferencia(uow, team_id, MI_EQUIPO, movimiento)
            await uow.commit()
        async with uow:
            filas = (await uow.session.execute(select(m.TeamTransfer))).scalars().all()
        assert sorted(f.is_buy for f in filas) == [False, True], "falta un lado"

        # Y volver a pasarlo no duplica ninguno de los dos.
        async with uow:
            await SyncTeamHandler(uow, None)._guardar_transferencia(
                uow, team_id, MI_EQUIPO, movimiento
            )
            await uow.commit()
        async with uow:
            filas = (await uow.session.execute(select(m.TeamTransfer))).scalars().all()
        assert len(filas) == 2

    asyncio.run(corre())


def test_la_etapa_no_pasa_por_canterana() -> None:
    async def corre() -> None:
        uow, team_id = await _uow()
        async with uow:
            h = SyncTeamHandler(uow, None)
            await h._guardar_transferencia(
                uow, team_id, MI_EQUIPO, _venta_sin_identificador()
            )
            await uow.commit()
        async with uow:
            await SyncTeamHandler(uow, None)._reconstruir_etapas(uow, team_id)
            await uow.commit()
        async with uow:
            etapa = await uow.session.scalar(select(m.PlayerStint))
            jugador = await uow.session.scalar(select(m.Player))
        assert etapa is not None, "la venta no llego a ser una etapa"
        assert etapa.unknown_origin is True
        assert etapa.from_academy is False, "un dato que falta no es un canterano"
        assert etapa.sale_price == 99140000
        assert jugador.ht_player_id_is_transfer is True
        assert jugador.last_name == "Byström"

    asyncio.run(corre())


def _mov(tid: int, nombre: str, compra: bool, fecha: str, precio: int) -> dict[str, Any]:
    return {
        "ht_transfer_id": tid, "ht_player_id": 0, "player_name": nombre,
        "deadline": fecha, "price": precio,
        "buyer_team_id": MI_EQUIPO if compra else OTRO,
        "seller_team_id": OTRO if compra else MI_EQUIPO,
        "tsi": 1,
    }


def test_la_compra_y_la_venta_del_mismo_nombre_son_una_etapa() -> None:
    """El caso Byström: dos transferencias sin identificador, una persona."""
    async def corre() -> None:
        uow, team_id = await _uow()
        async with uow:
            h = SyncTeamHandler(uow, None)
            await h._guardar_transferencia(
                uow, team_id, MI_EQUIPO,
                _mov(348652609, "Anders Byström", True, "2021-04-24 18:00:00", 84200000))
            await h._guardar_transferencia(
                uow, team_id, MI_EQUIPO,
                _mov(349926669, "Anders Byström", False, "2021-06-26 18:00:00", 99140000))
            await uow.commit()
        async with uow:
            await SyncTeamHandler(uow, None)._reconstruir_etapas(uow, team_id)
            await uow.commit()
        async with uow:
            etapas = (await uow.session.execute(select(m.PlayerStint))).scalars().all()
            jugadores = (await uow.session.execute(select(m.Player))).scalars().all()
        assert len(jugadores) == 1, "el mismo nombre partido en dos fichas"
        assert len(etapas) == 1, "la compra no encontro a su venta"
        assert etapas[0].arrival_price == 84200000
        assert etapas[0].sale_price == 99140000
        assert etapas[0].from_academy is False
        assert etapas[0].unknown_origin is False, "tiene compra: su origen se sabe"

    asyncio.run(corre())


def test_dos_etapas_seguidas_del_mismo_nombre() -> None:
    """Ontiveros: compra, venta, compra, venta. Dos etapas, en orden."""
    async def corre() -> None:
        uow, team_id = await _uow()
        async with uow:
            h = SyncTeamHandler(uow, None)
            for tid, compra, fecha, precio in (
                (1, True, "2018-12-05 18:00:00", 510000),
                (2, False, "2019-01-13 18:00:00", 10000000),
                (3, True, "2020-01-19 18:00:00", 1000000),
                (4, False, "2020-02-27 18:00:00", 3000000),
            ):
                await h._guardar_transferencia(
                    uow, team_id, MI_EQUIPO,
                    _mov(tid, "Baldemar Ontiveros", compra, fecha, precio))
            await uow.commit()
        async with uow:
            await SyncTeamHandler(uow, None)._reconstruir_etapas(uow, team_id)
            await uow.commit()
        async with uow:
            etapas = (await uow.session.execute(
                select(m.PlayerStint).order_by(m.PlayerStint.arrived_at)
            )).scalars().all()
        assert len(etapas) == 2
        assert [e.arrival_price for e in etapas] == [510000, 1000000]
        assert [e.sale_price for e in etapas] == [10000000, 3000000]

    asyncio.run(corre())


def test_a_un_jugador_con_identificador_propio_no_se_le_toca() -> None:
    """Emparejar por nombre es el ultimo recurso: nunca alcanza a un real."""
    async def corre() -> None:
        uow, team_id = await _uow()
        async with uow:
            uow.session.add(m.Player(
                ht_player_id=555, team_id=team_id,
                first_name="Anders", last_name="Byström",
            ))
            await uow.session.flush()
            h = SyncTeamHandler(uow, None)
            # Una compra suya, con identificador de verdad.
            real = _mov(700, "Anders Byström", True, "2021-04-24 18:00:00", 84200000)
            real["ht_player_id"] = 555
            await h._guardar_transferencia(uow, team_id, MI_EQUIPO, real)
            # Y una venta huerfana con el mismo nombre.
            await h._guardar_transferencia(
                uow, team_id, MI_EQUIPO,
                _mov(701, "Anders Byström", False, "2021-06-26 18:00:00", 99140000))
            await uow.commit()
        async with uow:
            await SyncTeamHandler(uow, None)._reconstruir_etapas(uow, team_id)
            await uow.commit()
        async with uow:
            etapas = (await uow.session.execute(select(m.PlayerStint))).scalars().all()
        assert len(etapas) == 2, "el huerfano se colo en la etapa del jugador real"
        conNombre = {e.ht_player_id for e in etapas}
        assert 555 in conNombre and 701 in conNombre

    asyncio.run(corre())


def test_sin_nombre_no_se_agrupa_con_nadie() -> None:
    async def corre() -> None:
        uow, team_id = await _uow()
        async with uow:
            h = SyncTeamHandler(uow, None)
            await h._guardar_transferencia(
                uow, team_id, MI_EQUIPO, _mov(10, "", True, "2020-01-01 18:00:00", 100))
            await h._guardar_transferencia(
                uow, team_id, MI_EQUIPO, _mov(11, "", False, "2020-02-01 18:00:00", 200))
            await uow.commit()
        async with uow:
            await SyncTeamHandler(uow, None)._reconstruir_etapas(uow, team_id)
            await uow.commit()
        async with uow:
            jugadores = (await uow.session.execute(select(m.Player))).scalars().all()
        assert len(jugadores) == 2, "dos anonimos no son la misma persona"

    asyncio.run(corre())
