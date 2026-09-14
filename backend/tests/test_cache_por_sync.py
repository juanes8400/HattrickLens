"""La caché que dura hasta el próximo sync (2026-09-14).

Lo que se vigila:
  · con el mismo sync terminado, lo guardado se devuelve sin recalcular;
  · un sync nuevo TERMINADO lo invalida; uno a medias («running») no;
  · dos peticiones iguales a la vez calculan una sola vez;
  · un fallo no se guarda.
"""

import asyncio
from datetime import UTC, datetime

import pytest

from app.api.cache_por_sync import por_sync
from app.infrastructure.db import models as m
from tests.test_sync_flow import _setup


async def _sync(uow, team_id: int, status: str) -> None:
    async with uow as u:
        u.session.add(
            m.Sync(
                user_id=1,
                team_id=team_id,
                kind="test",
                status=status,
                started_at=datetime.now(UTC),
            )
        )
        await u.commit()


def test_se_guarda_hasta_que_termina_un_sync_nuevo() -> None:
    async def run() -> None:
        uow, _unused, team_id = await _setup()
        await _sync(uow, team_id, "completed")
        calculos = 0

        async def calcular() -> int:
            nonlocal calculos
            calculos += 1
            return calculos

        async def pedir() -> int:
            async with uow as u:
                return await por_sync(u.session, team_id, "prueba", (1,), calcular)

        assert await pedir() == 1
        assert await pedir() == 1  # guardado
        await _sync(uow, team_id, "running")
        assert await pedir() == 1  # un sync a medias no invalida
        await _sync(uow, team_id, "completed")
        assert await pedir() == 2  # uno terminado, sí
        assert calculos == 2

    asyncio.run(run())


def test_dos_peticiones_iguales_a_la_vez_calculan_una_sola_vez() -> None:
    async def run() -> None:
        uow, _unused, team_id = await _setup()
        await _sync(uow, team_id, "completed")
        calculos = 0

        async def calcular() -> str:
            nonlocal calculos
            calculos += 1
            await asyncio.sleep(0.05)
            return "listo"

        async def pedir() -> str:
            async with uow as u:
                return await por_sync(u.session, team_id, "prueba", (), calcular)

        assert await asyncio.gather(pedir(), pedir()) == ["listo", "listo"]
        assert calculos == 1

    asyncio.run(run())


def test_un_fallo_no_se_guarda() -> None:
    async def run() -> None:
        uow, _unused, team_id = await _setup()
        await _sync(uow, team_id, "completed")
        intentos = 0

        async def calcular() -> str:
            nonlocal intentos
            intentos += 1
            if intentos == 1:
                raise RuntimeError("Hattrick no contesta")
            return "bien"

        async with uow as u:
            with pytest.raises(RuntimeError):
                await por_sync(u.session, team_id, "prueba", (), calcular)
            assert await por_sync(u.session, team_id, "prueba", (), calcular) == "bien"

    asyncio.run(run())
