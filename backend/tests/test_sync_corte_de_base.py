"""Una sincronización sobrevive a un corte de la base (2026-09-15).

Reporte de un usuario en producción: la importación terminó con «This
Session's transaction has been rolled back due to a previous exception during
flush». Toda la sincronización iba en UNA transacción; tras un corte, cada paso
atrapaba el error y seguía con la sesión rota, y al final se deshacía todo,
fila de la sincronización incluida. Lo que se vigila aquí:

  * un fallo de la base en un fichero no rompe los siguientes,
  * lo ya guardado se conserva (commit por partes),
  * si la sincronización revienta, su fila queda en «failed» con el motivo.
"""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.sync_team import (
    MENSAJE_BASE_CORTADA,
    SyncTeamCommand,
    SyncTeamHandler,
    mensaje_de_error,
)
from app.infrastructure.chpp.parsers import get_parser
from app.infrastructure.db import models as m
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

FIXTURES = Path(__file__).parent / "fixtures"
OWN_HT_TEAM_ID = 537758


class FakeCHPP:
    async def fetch(self, file: str, version: str = "latest", **params: Any) -> dict[str, Any]:
        return get_parser(file)((FIXTURES / f"{file}.xml").read_bytes())

    async def aclose(self) -> None:
        pass


def _corte() -> OperationalError:
    return OperationalError("INSERT ...", {}, Exception("server closed the connection"))


async def _montar() -> tuple[async_sessionmaker, int, int]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    async with factory() as s:
        user = m.User(ht_user_id=999, login_name="tester", created_at=datetime.now(UTC))
        s.add(user)
        await s.flush()
        team = m.Team(ht_team_id=OWN_HT_TEAM_ID, name="Pulgas Arrechas", owner_user_id=user.id)
        s.add(team)
        await s.commit()
        return factory, user.id, team.id


def test_un_corte_en_un_fichero_no_rompe_los_siguientes_ni_borra_lo_guardado() -> None:
    async def run() -> None:
        factory, user_id, team_id = await _montar()
        handler = SyncTeamHandler(SqlAlchemyUnitOfWork(factory), FakeCHPP())
        original = handler._persist

        async def persist(uow, sync_id, team_id_, ht_team_id, file, *resto):  # type: ignore[no-untyped-def]
            if file == "training":
                # Algo se escribe y la base se cae antes de confirmarlo.
                uow.session.add(
                    m.SyncChange(
                        sync_id=sync_id,
                        team_id=team_id_,
                        category="x",
                        summary="a medias",
                        created_at=datetime.now(UTC),
                    )
                )
                raise _corte()
            return await original(uow, sync_id, team_id_, ht_team_id, file, *resto)

        handler._persist = persist  # type: ignore[method-assign]
        result = await handler.execute(
            SyncTeamCommand(
                user_id=user_id,
                team_id=team_id,
                ht_team_id=OWN_HT_TEAM_ID,
                files=["players", "training", "economy"],
            )
        )

        assert result.status == "partial"
        # Por el nombre legible, no por el del fichero (2026-09-20): el aviso
        # de un sync a medias se lee, no se descifra.
        assert any(e.startswith("entrenamiento:") for e in result.errors)
        # Ni el paso siguiente arrastró la sesión rota ni se perdió lo anterior.
        assert not any(e.startswith("economía:") for e in result.errors)
        async with factory() as s:
            assert (await s.scalar(select(func.count()).select_from(m.Player))) > 0
            assert (await s.scalar(select(func.count()).select_from(m.EconomySnapshot))) > 0
            fila = await s.get(m.Sync, result.sync_id)
            assert fila is not None and fila.status == "partial"
            a_medias = await s.scalar(
                select(func.count())
                .select_from(m.SyncChange)
                .where(m.SyncChange.summary == "a medias")
            )
            assert a_medias == 0, "lo del paso que falló no se confirma"

    asyncio.run(run())


def test_si_la_sincronizacion_revienta_su_fila_queda_fallida_con_el_motivo() -> None:
    async def run() -> None:
        factory, user_id, team_id = await _montar()
        handler = SyncTeamHandler(SqlAlchemyUnitOfWork(factory), FakeCHPP())

        async def revienta(*_a: Any, **_kw: Any) -> None:
            raise _corte()

        handler._resolver_moneda = revienta  # type: ignore[method-assign]
        with pytest.raises(OperationalError):
            await handler.execute(
                SyncTeamCommand(
                    user_id=user_id,
                    team_id=team_id,
                    ht_team_id=OWN_HT_TEAM_ID,
                    files=["players", "economy"],
                )
            )

        async with factory() as s:
            filas = list((await s.execute(select(m.Sync))).scalars())
            assert len(filas) == 1, "la fila ya no desaparece"
            assert filas[0].status == "failed"
            assert filas[0].error == MENSAJE_BASE_CORTADA
            # Lo que se descargó antes del corte sigue ahí.
            assert (await s.scalar(select(func.count()).select_from(m.Player))) > 0

    asyncio.run(run())


def test_el_mensaje_de_un_corte_de_base_es_legible() -> None:
    assert mensaje_de_error(_corte()) == MENSAJE_BASE_CORTADA
    assert mensaje_de_error(ValueError("otra cosa")) == "otra cosa"
