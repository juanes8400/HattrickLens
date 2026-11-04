"""La pista que `currentbids.xml` regalaba y tirábamos a la basura.

2026-11-03, pedido por el usuario. La caza de comisiones de reventa trabaja
a ciegas: `economy.xml` dice que entró dinero pero no de quién, y hay cientos
de ex-jugadores en la cola, de los que se miran unos pocos por sincronización.

`currentbids.xml` --que ya se descarga en cada sync-- trae las pujas en las
que andamos metidos, y entre ellas los ex-jugadores nuestros que intentamos
recomprar. Ése es el dato: un ex-jugador EN EL MERCADO es una reventa con
fecha y hora, y de la reventa sale nuestra comisión de club anterior.

Lo que fijan estas pruebas:

1. Al ex-jugador que aparece en las pujas se le anota el plazo de la subasta.
2. A un jugador NUESTRO en venta no se le anota nada: ahí no hay reventa de
   nadie, lo estamos vendiendo nosotros.
3. Pasado el plazo, ese ex-jugador se mira PRIMERO, por delante de la
   alternancia reciente/azar.
4. Antes del plazo no se adelanta: la reventa todavía no ha pasado.
5. La pista se borra al mirarla, se venda o no se venda; si no, se quedaría
   para siempre a la cabeza de la cola robándole el turno a los demás.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.sync_team import SyncResult, SyncTeamHandler
from app.infrastructure.db import models as m
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

AHORA = datetime.now(UTC).replace(tzinfo=None)
# Las fechas se cuentan contra el reloj real porque el código pregunta por
# `datetime.now`: una constante fija caducaría el día que la prueba envejezca.
CERRADA = AHORA - timedelta(hours=3)
ABIERTA = AHORA + timedelta(hours=20)


class CHPPMudo:
    """No hace falta que responda: lo que se mide es a QUIÉN se pregunta."""

    async def fetch(self, file: str, version: str = "latest", **params: Any) -> dict:
        return {}


async def _monta() -> tuple[SqlAlchemyUnitOfWork, int]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        equipo = m.Team(ht_team_id=537758, name="Pulgas Arrechas")
        s.add(equipo)
        await s.flush()
        # El de la puja: vendido hace mucho Y revisado ahora mismo, así que es
        # el ÚLTIMO de la cola por los dos criterios que existen --recencia de
        # la venta si hay cacería abierta, antigüedad de la última mirada si
        # no--. Si aun así sale primero, sólo puede ser por la pista.
        s.add(
            m.Player(
                team_id=equipo.id,
                ht_player_id=483595362,
                first_name="Juan Pablo",
                last_name="Castaño",
                purchased_at=datetime(2024, 9, 21),
                sold_at=datetime(2025, 2, 1),
                left_team_at=datetime(2025, 2, 1),
                previous_club_bonus_checked_at=AHORA,
                purchase_price=1000,
            )
        )
        # Vendido ayer y nunca revisado: encabeza la cola por ambos criterios.
        s.add(
            m.Player(
                team_id=equipo.id,
                ht_player_id=900_000_001,
                first_name="Ex",
                last_name="Reciente",
                purchased_at=datetime(2024, 1, 1),
                sold_at=AHORA - timedelta(days=1),
                left_team_at=AHORA - timedelta(days=1),
                purchase_price=1000,
            )
        )
        # Nuestro, y en el mercado puesto por nosotros.
        s.add(
            m.Player(
                team_id=equipo.id,
                ht_player_id=900_000_002,
                first_name="Todavía",
                last_name="Nuestro",
                purchased_at=datetime(2026, 1, 1),
                currently_listed=True,
                purchase_price=1000,
            )
        )
        await s.commit()
        return SqlAlchemyUnitOfWork(factory), equipo.id


def _pujas(*entradas: tuple[int, datetime]) -> dict[str, Any]:
    return {
        "listed_players": [
            {
                "ht_player_id": ht_id,
                "player_name": "",
                # El persistidor espera la hora de Hattrick en texto, tal como
                # sale del parser, y la convierte él.
                "deadline": plazo.strftime("%Y-%m-%d %H:%M:%S"),
                "highest_bid": 16_575_000,
            }
            for ht_id, plazo in entradas
        ]
    }


def test_al_exjugador_en_el_mercado_se_le_anota_el_plazo() -> None:
    async def corre() -> None:
        uow, team_id = await _monta()
        async with uow:
            await SyncTeamHandler(uow, CHPPMudo())._persist_currentbids(
                uow,
                team_id,
                _pujas((483595362, ABIERTA), (900_000_002, ABIERTA)),
                AHORA,
                SyncResult(sync_id=1, status="running"),
            )
            await uow.commit()

            anotado = await uow.session.scalar(
                select(m.Player.resale_deadline).where(m.Player.ht_player_id == 483595362)
            )
            nuestro = await uow.session.scalar(
                select(m.Player.resale_deadline).where(m.Player.ht_player_id == 900_000_002)
            )

        assert anotado is not None, "el ex-jugador en las pujas tiene que quedar anotado"
        # Al segundo no: lo estamos vendiendo nosotros, ahí no revende nadie.
        assert nuestro is None

    asyncio.run(corre())


def test_la_pista_madura_se_mira_primero_y_se_consume() -> None:
    async def corre() -> None:
        uow, team_id = await _monta()
        dichos: list[str] = []

        async def apunta(mensaje: str) -> None:
            dichos.append(mensaje)

        async with uow:
            await SyncTeamHandler(uow, CHPPMudo())._persist_currentbids(
                uow,
                team_id,
                _pujas((483595362, CERRADA)),
                AHORA,
                SyncResult(sync_id=1, status="running"),
            )
            await uow.commit()
            await SyncTeamHandler(uow, CHPPMudo())._backfill_previous_club_bonus(
                uow,
                team_id,
                SyncResult(sync_id=1, status="running"),
                apunta,
            )
            await uow.commit()
            quedaba = await uow.session.scalar(
                select(m.Player.resale_deadline).where(m.Player.ht_player_id == 483595362)
            )

        # Primero el de la pista, aunque la venta más reciente sea la del otro.
        assert dichos, "tenía que mirar a alguien"
        assert "Castaño" in dichos[0], dichos
        # Y se dice por qué, para que una pista y un tiro al azar no se lean
        # igual en pantalla.
        assert "visto en el mercado" in dichos[0]
        # Consumida: haya salido comisión o no.
        assert quedaba is None

    asyncio.run(corre())


def test_antes_del_plazo_la_pista_no_adelanta_a_nadie() -> None:
    async def corre() -> None:
        uow, team_id = await _monta()
        dichos: list[str] = []

        async def apunta(mensaje: str) -> None:
            dichos.append(mensaje)

        async with uow:
            await SyncTeamHandler(uow, CHPPMudo())._persist_currentbids(
                uow,
                team_id,
                _pujas((483595362, ABIERTA)),
                AHORA,
                SyncResult(sync_id=1, status="running"),
            )
            await uow.commit()
            await SyncTeamHandler(uow, CHPPMudo())._backfill_previous_club_bonus(
                uow,
                team_id,
                SyncResult(sync_id=1, status="running"),
                apunta,
            )
            await uow.commit()
            sigue = await uow.session.scalar(
                select(m.Player.resale_deadline).where(m.Player.ht_player_id == 483595362)
            )

        assert dichos, "tenía que mirar a alguien"
        # La subasta sigue abierta: la reventa no ha pasado todavía, así que
        # manda el orden de siempre y nadie se adelanta.
        assert "Reciente" in dichos[0], dichos
        assert not any("visto en el mercado" in x for x in dichos), dichos
        # Y la pista se guarda para cuando cierre.
        assert sigue is not None

    asyncio.run(corre())
