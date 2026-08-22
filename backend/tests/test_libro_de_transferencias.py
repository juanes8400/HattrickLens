"""Las dos salvaguardias del libro de transferencias.

1. Un movimiento sin identificador de jugador no se tira: usa el numero de su
   transferencia, y la etapa queda marcada como "sin origen conocido" en vez de
   pasar por canterana.
2. Cuando el club esta en los dos lados, la venta es tan real como la compra y
   se anotan las dos.
"""
import asyncio
from datetime import datetime
from typing import Any

import pytest
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
