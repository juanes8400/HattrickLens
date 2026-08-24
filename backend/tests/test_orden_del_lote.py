"""El boton de Transferencias atiende primero a los mas recientes.

2026-08-24. Se ordenaron las consultas de `pendientes_de_ficha` y no basto:
el consumidor hacia `sorted(ficha | precio | ...)` sobre la UNION DE
CONJUNTOS, y eso ordena por numero de jugador, que sube con la antiguedad.
El lote empezaba siempre por los mas viejos.

Esta prueba mira lo que hace el BOTON, no lo que devuelve la consulta: es la
unica forma de que el fallo no vuelva a colarse por el mismo sitio.
"""
import asyncio
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.sync_team import SyncTeamHandler
from app.infrastructure.db import models as m
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork


class CHPPMudo:
    """No hace falta que responda nada: lo que se mide es a QUIEN se pregunta."""

    async def fetch(self, file: str, version: str = "latest", **params: Any) -> dict:
        return {}


VENTAS = [
    ("Viejo", 900_000_001, datetime(2020, 9, 10)),
    ("Medio", 900_000_002, datetime(2024, 7, 16)),
    ("Reciente", 900_000_003, datetime(2026, 8, 20)),
]


async def _monta() -> tuple[SqlAlchemyUnitOfWork, int]:
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
        for apellido, ht_id, vendido in VENTAS:
            s.add(m.Player(
                team_id=equipo.id, ht_player_id=ht_id,
                first_name="Ex", last_name=apellido,
                sold_at=vendido, purchased_at=datetime(2018, 1, 1),
                purchase_price=1000,
            ))
        await s.commit()
        return SqlAlchemyUnitOfWork(factory), equipo.id


def test_el_lote_empieza_por_la_venta_mas_reciente() -> None:
    async def corre() -> None:
        uow, team_id = await _monta()
        from app.application.commands.sync_team import SyncResult

        result = SyncResult(sync_id=1, status="running")
        async with uow:
            await SyncTeamHandler(uow, CHPPMudo())._backfill_sold_player_details(
                uow, team_id, datetime(2026, 8, 24), result,
            )
            await uow.commit()

        # `players_named` guarda los apellidos en el orden en que se
        # atendieron, que es justo lo que hay que comprobar.
        assert result.players_named == ["Reciente", "Medio", "Viejo"], (
            "el lote tiene que empezar por la venta mas reciente"
        )

    asyncio.run(corre())


def test_el_limite_se_lleva_a_los_mas_recientes() -> None:
    """Con lotes de uno, el numero 1 no puede ser el de 2020."""
    async def corre() -> None:
        uow, team_id = await _monta()
        from app.application.commands.sync_team import SyncResult

        result = SyncResult(sync_id=1, status="running")
        async with uow:
            await SyncTeamHandler(uow, CHPPMudo())._backfill_sold_player_details(
                uow, team_id, datetime(2026, 8, 24), result, limite=1,
            )
            await uow.commit()
        assert result.players_named == ["Reciente"]

    asyncio.run(corre())
