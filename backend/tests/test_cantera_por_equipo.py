"""La cantera es de un club, no de la cuenta (2026-09-19).

Lo reporto un usuario con dos equipos: al entrar en el segundo club le salian
los juveniles del primero. La causa estaba en la descarga, no en la pantalla:
los dos ficheros juveniles se pedian sin decir QUE academia, y Hattrick
contesta entonces con la del club principal, que se guardaba a nombre del
segundo.

Aqui se fija lo que evita que vuelva a pasar: se pide la academia por su id, y
al guardarla se comprueba de que club es. Lo segundo importa mas que lo
primero: protege aunque el parametro cambie de nombre o Hattrick lo ignore.
"""

import asyncio
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.sync_team import SyncTeamCommand, SyncTeamHandler
from app.infrastructure.chpp.parsers import get_parser
from app.infrastructure.db import models as m
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

FIXTURES = Path(__file__).parent / "fixtures"

#: El club de la fixture y su academia.
PULGAS = 537758
CANTERA_DE_PULGAS = 3278056
#: El segundo club de la misma cuenta.
SCIENTISTA = 999999

FICHEROS = ["youthteamdetails", "youthplayerlist"]


class CHPPDeLaCuenta:
    """Contesta siempre con la academia de `madre`, como hace Hattrick cuando
    no se le dice cual se quiere."""

    def __init__(self, madre: int = PULGAS) -> None:
        self.madre = madre
        self.llamadas: list[tuple[str, dict[str, Any]]] = []

    async def fetch(self, file: str, version: str, **params: Any) -> dict[str, Any]:
        self.llamadas.append((file, params))
        datos = get_parser(file)((FIXTURES / f"{file}.xml").read_bytes())
        if file == "youthteamdetails":
            datos["mother_team_id"] = self.madre
        return datos

    def parametros(self, file: str) -> list[dict[str, Any]]:
        return [p for f, p in self.llamadas if f == file]


async def _base(
    clubes: list[tuple[int, int | None]],
) -> tuple[SqlAlchemyUnitOfWork, dict[int, int]]:
    """Una base con los clubes pedidos: (ht_team_id, id de su cantera)."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    ids: dict[int, int] = {}
    async with factory() as s:
        for ht_team_id, cantera in clubes:
            fila = m.Team(
                ht_team_id=ht_team_id,
                name=f"club {ht_team_id}",
                ht_youth_team_id=cantera,
            )
            s.add(fila)
            await s.flush()
            ids[ht_team_id] = fila.id
        await s.commit()
    return SqlAlchemyUnitOfWork(factory), ids


async def _sincronizar(uow: SqlAlchemyUnitOfWork, chpp: CHPPDeLaCuenta, team_id: int, ht: int):
    return await SyncTeamHandler(uow, chpp).execute(
        SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=ht, files=FICHEROS)
    )


def test_teamdetails_dice_la_cantera_de_cada_club() -> None:
    """El id de la academia va equipo por equipo en el fichero del club: es la
    unica fuente que lo da por club y no por cuenta."""
    payload = get_parser("teamdetails")((FIXTURES / "teamdetails.xml").read_bytes())
    equipo = payload["teams"][0]
    assert equipo["ht_team_id"] == PULGAS
    # La fixture es de julio, anterior a la academia: 0 = este club no tiene.
    assert equipo["ht_youth_team_id"] == 0
    assert equipo["youth_team_name"] == ""


def test_la_academia_dice_de_que_club_es() -> None:
    payload = get_parser("youthteamdetails")((FIXTURES / "youthteamdetails.xml").read_bytes())
    assert payload["ht_youth_team_id"] == CANTERA_DE_PULGAS
    assert payload["mother_team_id"] == PULGAS


def test_se_pide_la_cantera_por_su_id() -> None:
    async def run() -> None:
        uow, ids = await _base([(PULGAS, CANTERA_DE_PULGAS)])
        chpp = CHPPDeLaCuenta()
        await _sincronizar(uow, chpp, ids[PULGAS], PULGAS)

        for fichero in FICHEROS:
            pedidos = chpp.parametros(fichero)
            assert pedidos, fichero
            for p in pedidos:
                assert p.get("youthTeamId") == CANTERA_DE_PULGAS, (fichero, p)

    asyncio.run(run())


def test_no_se_guarda_la_cantera_de_otro_club() -> None:
    """El nucleo del fallo. Aunque Hattrick conteste con la academia ajena, no
    entra ni un juvenil ni el nombre de esa academia."""

    async def run() -> None:
        uow, ids = await _base([(SCIENTISTA, None)])
        chpp = CHPPDeLaCuenta(madre=PULGAS)
        resultado = await _sincronizar(uow, chpp, ids[SCIENTISTA], SCIENTISTA)

        assert resultado.status == "partial"
        assert any("no la de este club" in e for e in resultado.errors), resultado.errors
        async with uow as sesion:
            club = await sesion.session.get(m.Team, ids[SCIENTISTA])
            assert club is not None
            assert club.ht_youth_team_id is None
            assert club.youth_team_name is None
            juveniles = (await sesion.session.execute(select(m.YouthPlayer))).scalars().all()
            assert juveniles == []
        # Y no se llega siquiera a pedir la plantilla juvenil ajena: pedirla
        # incluye revelar habilidades, que es escribir en la otra academia.
        assert chpp.parametros("youthplayerlist") == []

    asyncio.run(run())


def test_un_club_sin_cantera_no_ensucia_el_parte() -> None:
    """Un segundo club sin academia es lo normal, no una anomalia: se
    descarta lo ajeno y la sincronizacion sale limpia."""

    async def run() -> None:
        uow, ids = await _base([(SCIENTISTA, 0)])
        chpp = CHPPDeLaCuenta(madre=PULGAS)
        resultado = await _sincronizar(uow, chpp, ids[SCIENTISTA], SCIENTISTA)

        assert resultado.status == "completed"
        assert resultado.errors == []
        async with uow as sesion:
            juveniles = (await sesion.session.execute(select(m.YouthPlayer))).scalars().all()
            assert juveniles == []

    asyncio.run(run())


def test_el_juvenil_vuelve_al_club_cuya_lista_lo_trae() -> None:
    """Reparacion de lo ya sembrado: los juveniles guardados a nombre del club
    equivocado vuelven solos en la siguiente sincronizacion del suyo."""

    async def run() -> None:
        uow, ids = await _base([(PULGAS, CANTERA_DE_PULGAS), (SCIENTISTA, 0)])
        async with uow as sesion:
            sesion.session.add(
                m.YouthPlayer(
                    ht_youth_player_id=424402061,
                    team_id=ids[SCIENTISTA],
                    first_name="Alirio",
                    last_name="Asprilla",
                )
            )
            await sesion.commit()

        chpp = CHPPDeLaCuenta(madre=PULGAS)
        await _sincronizar(uow, chpp, ids[PULGAS], PULGAS)

        async with uow as sesion:
            juvenil = await sesion.session.scalar(
                select(m.YouthPlayer).where(m.YouthPlayer.ht_youth_player_id == 424402061)
            )
            assert juvenil is not None
            assert juvenil.team_id == ids[PULGAS]

    asyncio.run(run())
