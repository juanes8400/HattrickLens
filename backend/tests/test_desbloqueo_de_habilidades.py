"""`unlockskills`: una sola llamada, antes de leer, y que nunca tumbe el sync.

2026-08-26. Las tres cosas que se fijan aquí son justo las que se rompen sin
darse cuenta: que sea UNA llamada para todo el equipo y no una por canterano,
que vaya ANTES de `details` --al revés se desbloquea después de haber leído y
la revelación se pierde una semana-- y que un 401 por permisos no aborte la
sincronización entera.
"""

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.sync_team import SyncTeamCommand, SyncTeamHandler
from app.infrastructure.chpp.parsers import get_parser
from app.infrastructure.db import models as m
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

FIXTURES = Path(__file__).parent / "fixtures"


class CHPPQueAnota:
    """Doble que apunta cada llamada, y opcionalmente revienta el desbloqueo."""

    def __init__(self, falla_el_desbloqueo: bool = False) -> None:
        self.llamadas: list[tuple[str, str | None]] = []
        self._falla = falla_el_desbloqueo

    async def fetch(self, file: str, version: str = "latest", **params: Any) -> dict[str, Any]:
        accion = params.get("actionType")
        self.llamadas.append((file, accion))
        if accion == "unlockskills":
            if self._falla:
                raise RuntimeError("401")
            return {}
        return get_parser(file)((FIXTURES / f"{file}.xml").read_bytes())


async def _sincronizar(chpp: CHPPQueAnota) -> Any:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        equipo = m.Team(ht_team_id=537758, name="Pulgas Arrechas")
        s.add(equipo)
        await s.commit()
        team_id = equipo.id
    handler = SyncTeamHandler(SqlAlchemyUnitOfWork(factory), chpp)
    return await handler.execute(
        SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["youthplayerlist"])
    )


@pytest.mark.asyncio
async def test_desbloquea_una_sola_vez_y_antes_de_leer():
    chpp = CHPPQueAnota()
    await _sincronizar(chpp)

    desbloqueos = [i for i, (f, a) in enumerate(chpp.llamadas) if a == "unlockskills"]
    lecturas = [i for i, (f, a) in enumerate(chpp.llamadas) if f == "youthplayerlist" and a == "details"]

    # Una sola: `unlockskills` destapa el equipo juvenil entero, no va por
    # canterano. Si algun dia se colara un bucle, esto lo caza.
    assert len(desbloqueos) == 1, chpp.llamadas
    assert lecturas, chpp.llamadas
    assert desbloqueos[0] < lecturas[0], "el desbloqueo tiene que ir ANTES de leer los niveles"


@pytest.mark.asyncio
async def test_el_desbloqueo_no_lleva_identificador_de_jugador():
    chpp = CHPPQueAnota()

    vistos: list[dict[str, Any]] = []
    original = chpp.fetch

    async def espia(file: str, version: str = "latest", **params: Any) -> dict[str, Any]:
        if params.get("actionType") == "unlockskills":
            vistos.append(params)
        return await original(file, version, **params)

    chpp.fetch = espia  # type: ignore[method-assign]
    await _sincronizar(chpp)

    assert vistos and "youthPlayerID" not in vistos[0]


@pytest.mark.asyncio
async def test_un_fallo_de_permisos_no_tumba_la_sincronizacion():
    """El caso real: token sin `manage_youthplayers` -> 401.

    La revelacion se pierde, pero los canteranos se guardan igual y el aviso
    dice que hay que reconectar.
    """
    chpp = CHPPQueAnota(falla_el_desbloqueo=True)
    resultado = await _sincronizar(chpp)

    assert any("unlockskills" in e for e in resultado.errors)
    assert any("reconecta" in e.lower() for e in resultado.errors)
    # Y lo importante: se siguio leyendo.
    assert any(a == "details" for _, a in chpp.llamadas)
