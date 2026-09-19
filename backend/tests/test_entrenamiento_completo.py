"""Cuando entrena la plantilla entera, ¿salen TODOS los cambios? (2026-09-19)

Lo preguntó el usuario: «creo que cuando hay entrenamiento me traes los cambios
por partes y no el 100%». Es una sospecha que se comprueba, no se opina, y este
test la deja fijada: se sube una habilidad a CADA jugador de la plantilla y se
cuenta cuántos cambios salen.

La respuesta es que salen todos. Lo que sí existe es un sync que se queda a
medias cuando Hattrick falla; eso se ve en el estado (`partial`) y se cuenta
aparte, nunca se disfraza de sincronización completa.
"""

import asyncio
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.sync_team import SyncTeamCommand, SyncTeamHandler
from app.infrastructure.chpp.parsers import get_parser
from app.infrastructure.db import models as m
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

FIXTURES = Path(__file__).parent / "fixtures"

#: La habilidad que "entrena" en el test.
ENTRENADA = "playmaking"


class CHPPQueEntrena:
    """El mismo fixture de siempre, con una subida a toda la plantilla en
    cuanto se enciende `entrena`."""

    def __init__(self) -> None:
        self.entrena = False

    async def fetch(self, file: str, version: str, **params: Any) -> dict[str, Any]:
        if file == "matchorders" and params.get("actionType") == "predictratings":
            datos = get_parser(file)((FIXTURES / "matchorders_predictratings.xml").read_bytes())
            datos["ht_match_id"] = params["matchID"]
            return datos
        datos = get_parser(file)((FIXTURES / f"{file}.xml").read_bytes())
        if self.entrena and file == "players":
            for jugador in datos.get("players", []):
                habilidades = jugador.get("skills") or {}
                if habilidades.get(ENTRENADA) is not None:
                    habilidades[ENTRENADA] += 1
        return datos


async def _setup() -> tuple[SqlAlchemyUnitOfWork, CHPPQueEntrena, int]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        team = m.Team(ht_team_id=537758, name="Pulgas Arrechas")
        s.add(team)
        await s.commit()
        team_id = team.id
    return SqlAlchemyUnitOfWork(factory), CHPPQueEntrena(), team_id


def test_una_subida_a_cada_jugador_sale_entera() -> None:
    async def run() -> None:
        uow, chpp, team_id = await _setup()
        handler = SyncTeamHandler(uow, chpp)
        cmd = SyncTeamCommand(
            user_id=1, team_id=team_id, ht_team_id=537758, files=["players"]
        )

        # Primera foto: la referencia contra la que se compara.
        await handler.execute(cmd)
        plantilla = len(
            get_parser("players")((FIXTURES / "players.xml").read_bytes())["players"]
        )
        assert plantilla > 1

        chpp.entrena = True
        resultado = await handler.execute(cmd)

        subidas = [
            c
            for c in resultado.changes
            if (c.get("detail") or {}).get("metric") == ENTRENADA
        ]
        # Uno por jugador, ni uno menos: eso es el 100% del entrenamiento.
        assert len(subidas) == plantilla, [c.get("summary") for c in subidas]
        # Y cada jugador aparece una sola vez, no dos sync a medias sumados.
        assert len({(c["detail"] or {}).get("subject") for c in subidas}) == plantilla

    asyncio.run(run())


def test_ningun_jugador_se_queda_sin_revisar() -> None:
    """La otra mitad de la pregunta: que nadie se caiga del recorrido. Cada
    jugador del fichero acaba con foto nueva o contado como sin cambios."""

    async def run() -> None:
        uow, chpp, team_id = await _setup()
        handler = SyncTeamHandler(uow, chpp)
        cmd = SyncTeamCommand(
            user_id=1, team_id=team_id, ht_team_id=537758, files=["players"]
        )
        await handler.execute(cmd)

        chpp.entrena = True
        await handler.execute(cmd)

        from sqlalchemy import func, select

        async with uow as sesion:
            con_foto = await sesion.session.scalar(
                select(func.count(func.distinct(m.PlayerSnapshot.player_id))).where(
                    m.PlayerSnapshot.sync_id
                    == select(func.max(m.Sync.id)).scalar_subquery()
                )
            )
        plantilla = len(
            get_parser("players")((FIXTURES / "players.xml").read_bytes())["players"]
        )
        assert con_foto == plantilla

    asyncio.run(run())
