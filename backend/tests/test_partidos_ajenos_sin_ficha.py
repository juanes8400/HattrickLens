"""Minutos guardados de un partido que no es de nuestro club.

La casilla "ultimo partido" de la ficha de un jugador tambien atrapa partidos
ajenos: el ultimo que jugo en su equipo anterior, un amistoso internacional,
uno de seleccion. Los minutos se guardan, pero sin la ficha del partido el
calculo de experiencia los cruza con una union estricta y los tira en
silencio. Esta reparacion los recoge.
"""
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.sync_team import SyncTeamHandler
from app.infrastructure.chpp.parsers import get_parser
from app.infrastructure.db import models as m
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

FIXTURES = Path(__file__).parent / "fixtures"
PARTIDO_AJENO = 767192395


class CHPPQueLlevaCuenta:
    def __init__(self) -> None:
        self.pedidos: list[int] = []

    async def fetch(self, file: str, version: str, **params: Any) -> dict[str, Any]:
        assert file == "matchdetails"
        self.pedidos.append(params["matchID"])
        ficha = get_parser(file)((FIXTURES / "matchdetails.xml").read_bytes())
        ficha["ht_match_id"] = params["matchID"]
        return ficha


async def _preparar() -> tuple[SqlAlchemyUnitOfWork, CHPPQueLlevaCuenta]:
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
        jugador = m.Player(team_id=equipo.id, ht_player_id=99, first_name="A", last_name="B")
        s.add(jugador)
        await s.flush()
        # Minutos de un partido que no es nuestro: no hay fila en `matches`.
        s.add(m.PlayerMatchRating(
            player_id=jugador.id, ht_match_id=PARTIDO_AJENO, position_code=7,
            played_minutes=90, rating=4.5, captured_at=datetime(2026, 7, 29),
        ))
        await s.commit()
    return SqlAlchemyUnitOfWork(factory), CHPPQueLlevaCuenta()


def test_rescata_la_ficha_del_partido_ajeno() -> None:
    async def corre() -> None:
        uow, chpp = await _preparar()
        async with uow:
            rescatados = await SyncTeamHandler(uow, chpp)._reparar_partidos_ajenos_sin_ficha(uow)
            await uow.commit()
        assert rescatados == 1
        assert chpp.pedidos == [PARTIDO_AJENO]
        async with uow:
            ficha = await uow.session.scalar(
                select(m.Match).where(m.Match.ht_match_id == PARTIDO_AJENO)
            )
        assert ficha is not None, "sin ficha, la experiencia de ese partido no se cuenta"

    asyncio.run(corre())


def test_no_vuelve_a_pedir_lo_que_ya_tiene_ficha() -> None:
    """Una segunda pasada no gasta ni una llamada: es lo normal en cada sync."""
    async def corre() -> None:
        uow, chpp = await _preparar()
        async with uow:
            await SyncTeamHandler(uow, chpp)._reparar_partidos_ajenos_sin_ficha(uow)
            await uow.commit()
        async with uow:
            segunda = await SyncTeamHandler(uow, chpp)._reparar_partidos_ajenos_sin_ficha(uow)
            await uow.commit()
        assert segunda == 0
        assert len(chpp.pedidos) == 1

    asyncio.run(corre())


class CHPPDeDosMundos:
    """Un mismo numero de partido existe en dos espacios distintos.

    Sin la marca `htointegrated` CHPP no da error: da OTRO partido, uno de club
    con el mismo numero. Verificado en vivo con el 41943634.
    """

    def __init__(self) -> None:
        self.pedidos: list[dict[str, Any]] = []

    async def fetch(self, file: str, version: str, **params: Any) -> dict[str, Any]:
        self.pedidos.append(params)
        ficha = get_parser(file)((FIXTURES / "matchdetails.xml").read_bytes())
        ficha["ht_match_id"] = params["matchID"]
        if params.get("sourceSystem") == "htointegrated":
            ficha["match_type"] = 10
            ficha["match_date"] = "2026-08-21 20:00:00"
        else:
            ficha["match_type"] = 1
            ficha["match_date"] = "2005-08-27 19:00:00"
        return ficha


def test_un_partido_de_seleccion_no_se_confunde_con_uno_de_2005() -> None:
    async def corre() -> None:
        uow, _ = await _preparar()
        chpp = CHPPDeDosMundos()
        async with uow:
            await SyncTeamHandler(uow, chpp)._backfill_foreign_match_type(
                uow, PARTIDO_AJENO, jugado_el=datetime(2026, 8, 21, 18, 0),
            )
            await uow.commit()
        async with uow:
            ficha = await uow.session.scalar(
                select(m.Match).where(m.Match.ht_match_id == PARTIDO_AJENO)
            )
        assert ficha is not None
        assert ficha.match_type == 10, "se quedo con el partido equivocado"
        assert ficha.played_at.year == 2026
        assert any(p.get("sourceSystem") == "htointegrated" for p in chpp.pedidos)

    asyncio.run(corre())


def test_sin_fecha_con_que_comparar_no_se_gasta_una_segunda_llamada() -> None:
    async def corre() -> None:
        uow, _ = await _preparar()
        chpp = CHPPDeDosMundos()
        async with uow:
            await SyncTeamHandler(uow, chpp)._backfill_foreign_match_type(uow, PARTIDO_AJENO)
            await uow.commit()
        assert len(chpp.pedidos) == 1

    asyncio.run(corre())
