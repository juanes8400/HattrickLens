"""La pantalla de Copa habla de la temporada EN CURSO, y el relleno es de Copa.

Dos instrucciones del usuario del 2026-09-28:

  · «la seccion Copa solo debe hablar de las copas de la temporada actual, no
    todas». Sin ese corte, la taquilla sumaba sesenta y seis partidos de
    varias temporadas y se leia como si fueran los de esta.
  · «que el proceso no solo priorice sino que solo lo programe hacer en Copa».
    El desglose por sector solo lo usa esta pantalla, asi que pedirlo para los
    partidos de liga seria gastar llamadas en un dato que nadie mira: en el
    club del usuario son 65 partidos de Copa frente a 720 en casa contando
    todo.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.cup import CUP_MATCH_TYPE, _cup_economy
from app.application.commands.sync_team import SyncResult, SyncTeamHandler
from app.infrastructure.db import models as m
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

EQUIPO = 537758
LIGA_DEL_PAIS = 19
#: Un partido de esta temporada y otro de hace una temporada larga.
AHORA = datetime(2026, 9, 20, 21, 40, tzinfo=UTC)
HACE_UNA_TEMPORADA = AHORA - timedelta(weeks=20)

#: Las mismas entradas del partido que mando el usuario.
DESGLOSE = {"sold_terraces": 30627, "sold_basic": 13639, "sold_roof": 4527, "sold_vip": 1272}
TAQUILLA = 481_312


async def _base(con_amistoso: bool = False):
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as s:
        equipo = m.Team(
            ht_team_id=EQUIPO,
            name="Pulgas Arrechas",
            currency_name="US$",
            currency_rate=10.0,
            ht_league_id=LIGA_DEL_PAIS,
        )
        s.add(equipo)
        s.add(
            m.WorldContext(
                ht_league_id=LIGA_DEL_PAIS,
                league_name="Colombia",
                season=83,
                match_round=8,
                refreshed_at=AHORA,
            )
        )
        await s.flush()

        partidos = [
            ("copa-de-ahora", AHORA, CUP_MATCH_TYPE),
            ("copa-vieja", HACE_UNA_TEMPORADA, CUP_MATCH_TYPE),
        ]
        if con_amistoso:
            partidos.append(("amistoso-de-ahora", AHORA, 4))
        for i, (_nombre, cuando, tipo) in enumerate(partidos, start=1):
            s.add(
                m.Match(
                    ht_match_id=900_000 + i,
                    played_at=cuando,
                    match_type=tipo,
                    status="FINISHED",
                    home_team_ht_id=EQUIPO,
                    away_team_ht_id=600_000 + i,
                    home_team_name="Pulgas Arrechas",
                    away_team_name=f"Rival {i}",
                    home_goals=2,
                    away_goals=1,
                )
            )
            s.add(
                m.StadiumHistory(
                    team_id=equipo.id,
                    ht_match_id=900_000 + i,
                    played_at=cuando,
                    match_type=tipo,
                    capacity_total=60_002,
                    sold_total=sum(DESGLOSE.values()),
                )
            )
        await s.commit()
        return factory, equipo.id


class _CHPPConDesglose:
    """Hattrick devolviendo el detalle de un partido, con su `<Arena>`."""

    def __init__(self) -> None:
        self.pedidos: list[int] = []

    async def fetch(self, file: str, version: str = "latest", **params):
        assert file == "matchdetails"
        self.pedidos.append(params["matchID"])
        return {"ht_match_id": params["matchID"], "arena": dict(DESGLOSE)}


def test_la_copa_solo_cuenta_los_partidos_de_esta_temporada() -> None:
    async def caso():
        factory, team_id = await _base()
        async with factory() as s:
            equipo = await s.get(m.Team, team_id)
            from sqlalchemy import select

            world = await s.scalar(
                select(m.WorldContext).where(m.WorldContext.ht_league_id == LIGA_DEL_PAIS)
            )
            # Los dos partidos tienen desglose; solo uno es de esta temporada.
            for foto in (
                await s.execute(select(m.StadiumHistory).order_by(m.StadiumHistory.id))
            ).scalars():
                for columna, valor in DESGLOSE.items():
                    setattr(foto, columna, valor)
            await s.commit()
            return await _cup_economy(s, equipo, None, None, world)

    d = asyncio.run(caso())
    assert d["observed_home_matches"] == 1, "el de la temporada pasada no cuenta"
    assert d["matches_with_gate"] == 1
    assert d["observed_gross_gate"] == TAQUILLA
    # El 67 % del local; el 33 % restante es del visitante.
    assert d["observed_share"] == round(TAQUILLA * 0.67)
    assert d["share_percent"] == 67


def test_el_relleno_del_desglose_solo_pide_partidos_de_copa() -> None:
    """Un amistoso en casa del mismo dia no se pide: nadie mira su taquilla."""

    async def caso():
        factory, team_id = await _base(con_amistoso=True)
        chpp = _CHPPConDesglose()
        handler = SyncTeamHandler(SqlAlchemyUnitOfWork(factory), chpp)
        async with SqlAlchemyUnitOfWork(factory) as uow:
            await handler._completar_desglose_de_taquilla(
                uow, team_id, EQUIPO, SyncResult(sync_id=0, status="ok")
            )
            await uow.commit()
        return chpp.pedidos

    pedidos = asyncio.run(caso())
    # Los dos de Copa (el de esta temporada y el viejo), nunca el amistoso.
    assert sorted(pedidos) == [900_001, 900_002]
