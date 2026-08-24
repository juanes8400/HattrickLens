"""La marca de "en venta" sobrevive a un sync en el que no cambia nada.

2026-08-24. `player_snapshots` escribe fila solo cuando algo cambia. Releer
la marca exigiendo una foto con la marca de tiempo EXACTA de este sync
borraba a todo el que no hubiera cambiado nada: su intento de venta se
cerraba solo y la pantalla le preguntaba las cosas de una venta ya cerrada.
Caso real: Enyo Kasaliyski, con plazo hasta las 15:11, cerrado a las 12:08.
"""
import asyncio
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.sync_team import SyncTeamHandler
from app.infrastructure.db import models as m
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

AYER = datetime(2026, 8, 23, 23, 32)
HOY = datetime(2026, 8, 24, 12, 6)


async def _monta(**kw: Any) -> tuple[SqlAlchemyUnitOfWork, int]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        equipo = m.Team(ht_team_id=1, name="Pulgas Arrechas")
        s.add(equipo)
        await s.flush()
        usuario = m.User(ht_user_id=1, login_name="yo")
        s.add(usuario)
        await s.flush()
        sync = m.Sync(user_id=usuario.id, team_id=equipo.id, kind="players",
                      status="completed", started_at=AYER)
        s.add(sync)
        await s.flush()
        jugador = m.Player(
            team_id=equipo.id, ht_player_id=483141997,
            first_name="Enyo", last_name="Kasaliyski",
            currently_listed=True, **kw,
        )
        s.add(jugador)
        await s.flush()
        # Su ultima foto es de AYER, con la marca puesta. Hoy no cambio nada,
        # asi que hoy no tiene foto.
        s.add(m.PlayerSnapshot(
            sync_id=sync.id, player_id=jugador.id, captured_at=AYER,
            is_transfer_listed=True, content_hash=b"x" * 32,
            age_years=25, age_days=100, tsi=19920, form=5, stamina=7,
            experience=9, salary=1000,
        ))
        await s.commit()
        return SqlAlchemyUnitOfWork(factory), equipo.id


def _marca(uow: SqlAlchemyUnitOfWork) -> bool:
    async def corre() -> bool:
        async with uow:
            await SyncTeamHandler(uow, None)._marcar_quien_esta_en_venta(
                uow, 1, HOY,
            )
            await uow.commit()
        async with uow:
            fila = await uow.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == 483141997)
            )
        return bool(fila.currently_listed)
    return asyncio.run(corre())


def test_sigue_en_venta_aunque_hoy_no_haya_foto_suya() -> None:
    uow, _ = asyncio.run(_monta())
    assert _marca(uow) is True


def test_quien_ya_no_es_nuestro_no_resucita() -> None:
    """Vendido en julio y aun marcado en agosto: el caso que trajo el borron."""
    uow, _ = asyncio.run(_monta(sold_at=datetime(2026, 7, 1)))
    assert _marca(uow) is False


def test_quien_dejo_el_club_tampoco() -> None:
    uow, _ = asyncio.run(_monta(left_team_at=datetime(2026, 7, 1)))
    assert _marca(uow) is False
