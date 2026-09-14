"""E2E del use case de sync contra DB real (sqlite in-memory) y CHPP fake.

Verifica el invariante central del producto: append-only + diffing
un segundo sync sin cambios NO escribe filas nuevas.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.sync_team import (
    SyncMatchDetailsCommand,
    SyncPlayerDetailsCommand,
    SyncResult,
    SyncTeamCommand,
    SyncTeamHandler,
)
from app.infrastructure.chpp.parsers import get_parser
from app.infrastructure.db import models as m
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

FIXTURES = Path(__file__).parent / "fixtures"


class FakeCHPP:
    """Sirve el fixture real grabado de CHPP."""

    def __init__(self) -> None:
        self.calls = 0

    async def fetch(self, file: str, version: str, **params: Any) -> dict[str, Any]:
        self.calls += 1
        if file == "matchorders" and params.get("actionType") == "predictratings":
            predicted = get_parser(file)((FIXTURES / "matchorders_predictratings.xml").read_bytes())
            predicted["ht_match_id"] = params["matchID"]
            return predicted
        return get_parser(file)((FIXTURES / f"{file}.xml").read_bytes())


async def _setup() -> tuple[SqlAlchemyUnitOfWork, FakeCHPP, int]:
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

    return SqlAlchemyUnitOfWork(factory), FakeCHPP(), team_id


def test_first_sync_writes_all_snapshots() -> None:
    async def run() -> None:
        uow, chpp, team_id = await _setup()
        handler = SyncTeamHandler(uow, chpp)
        # Explícito: este test verifica el diffing de jugador/entrenamiento/
        # economía en particular, no el conjunto completo de DEFAULT_FILES
        # (que incluye liga/partidos y evoluciona con el producto).
        cmd = SyncTeamCommand(
            user_id=1,
            team_id=team_id,
            ht_team_id=537758,
            files=["players", "training", "economy"],
        )

        result = await handler.execute(cmd)
        assert result.status == "completed"
        # 24 players + training + economy + 24 playerdetails automáticos
        # (2026-08-05: "sincroniza todos los xml que importen cada vez que
        # sincronizamos", LastMatch/Caps ya no esperan un botón aparte).
        # 55 y no 50 desde el 2026-08-19: al sincronizar la plantilla se piden
        # también las subidas confirmadas por Hattrick, una llamada por
        # jugador (`trainingevents.xml` solo existe por playerID). El fixture
        # trae 5 eventos.
        # De 55 a 57 el 2026-08-25: el sync normal recorre ahora el libro de
        # compraventas, y el fixture trae dos. Son TUS movimientos y por eso
        # vienen con este boton, no con el de abajo.
        assert result.snapshots_written == 57
        # 115 repetidos ya en la PRIMERA sincronización: el fichero de subidas
        # se pide por jugador y el fixture devuelve los mismos 5 eventos para
        # todos, así que a partir del primero ya están guardados. Con datos
        # reales cada jugador trae los suyos.
        assert result.unchanged == 115

    asyncio.run(run())


def test_sync_progress_identifies_players_by_full_name() -> None:
    async def run() -> None:
        uow, chpp, team_id = await _setup()
        messages: list[str] = []

        async def capture(message: str) -> None:
            messages.append(message)

        await SyncTeamHandler(uow, chpp).execute(
            SyncTeamCommand(
                user_id=1,
                team_id=team_id,
                ht_team_id=537758,
                files=["players"],
            ),
            on_progress=capture,
        )

        assert "Descargando ficha de jugador Alberto Gutiérrez Caviedes..." in messages
        assert not any(
            message.startswith("Descargando ficha de jugador ")
            and any(character.isdigit() for character in message)
            for message in messages
        )

    asyncio.run(run())


def test_second_sync_without_changes_writes_nothing() -> None:
    async def run() -> None:
        uow, chpp, team_id = await _setup()
        handler = SyncTeamHandler(uow, chpp)
        cmd = SyncTeamCommand(
            user_id=1,
            team_id=team_id,
            ht_team_id=537758,
            files=["players", "training", "economy"],
        )

        await handler.execute(cmd)
        result2 = await handler.execute(cmd)

        assert result2.snapshots_written == 0
        # 146: los 26 de antes más los eventos de entrenamiento que se
        # vuelven a leer para cada jugador y ya estaban guardados. Que se
        # cuenten como "sin cambios" es justo lo que se quiere: la segunda
        # sincronización no escribe nada.
        assert result2.unchanged == 146

        async with uow as u:
            assert await u.players.count_snapshots(team_id) == 24  # sin duplicados

    asyncio.run(run())


def test_matches_are_upserted_by_ht_match_id() -> None:
    """`matches` no es un snapshot append-only: un partido se identifica por
    ht_match_id y se actualiza in-place (upcoming -> finished)."""

    async def run() -> None:
        uow, chpp, team_id = await _setup()
        handler = SyncTeamHandler(uow, chpp)
        cmd = SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["matches"])

        first = await handler.execute(cmd)
        # 17 <Match> entries en el fixture + 3 del backfill automático de
        # matchdetails.xml (2026-08-05: "sincroniza todos los xml que
        # importen"): 2 MatchRating (home/away) + 1 StadiumHistory, todos
        # del único partido cuyo matchID coincide con el fixture estático de
        # matchdetails (765274387), los demás partidos "pendientes" del
        # backfill no tienen fixture propio y se descartan sin escribir
        # nada (ver el guard en `_backfill_missing_match_details`).
        assert first.snapshots_written == 21
        assert first.unchanged == 0

        second = await handler.execute(cmd)
        assert second.snapshots_written == 0
        assert second.unchanged == 18

        from sqlalchemy import func, select

        async with uow as u:
            total = await u.session.scalar(select(func.count()).select_from(m.Match))
            assert total == 17  # sin duplicados por ht_match_id
            upcoming = await u.session.scalar(
                select(m.Match).where(m.Match.ht_match_id == 767370369)
            )
            assert upcoming is not None
            assert upcoming.source_system == "hattrick"
            assert upcoming.orders_given is True
            assert upcoming.submitted_tactic_type == 2
            assert len(json.loads(upcoming.submitted_lineup_json or "[]")) == 11
            assert upcoming.submitted_tactic_skill == 19
            assert upcoming.submitted_rating_midfield == 18
            assert upcoming.submitted_rating_central_def == 90
            assert upcoming.submitted_rating_left_att == 56
            assert upcoming.submitted_ratings_captured_at is not None

    asyncio.run(run())


ARCHIVO_CON_HUECO = b"""<?xml version="1.0" encoding="utf-8"?>
<HattrickData>
  <FileName>matchesarchive.xml</FileName>
  <Version>1.5</Version>
  <Team>
    <TeamID>537758</TeamID>
    <TeamName>Pulgas Arrechas</TeamName>
    <MatchList>
      <Match>
        <MatchID>767370369</MatchID>
        <HomeTeam>
          <HomeTeamID>537758</HomeTeamID><HomeTeamName>Pulgas Arrechas</HomeTeamName>
        </HomeTeam>
        <AwayTeam>
          <AwayTeamID>70</AwayTeamID><AwayTeamName>Leones de la Selva</AwayTeamName>
        </AwayTeam>
        <MatchDate>2026-07-22 23:40:00</MatchDate>
        <MatchType>3</MatchType>
        <MatchContextId>18</MatchContextId>
        <SourceSystem>Hattrick</SourceSystem>
        <CupId>18</CupId>
        <CupLevel>1</CupLevel>
        <CupLevelIndex>1</CupLevelIndex>
        <HomeGoals>1</HomeGoals>
        <AwayGoals>0</AwayGoals>
      </Match>
      <Match>
        <MatchID>770729379</MatchID>
        <HomeTeam>
          <HomeTeamID>537758</HomeTeamID><HomeTeamName>Pulgas Arrechas</HomeTeamName>
        </HomeTeam>
        <AwayTeam><AwayTeamID>71</AwayTeamID><AwayTeamName>Liga Magica</AwayTeamName></AwayTeam>
        <MatchDate>2026-07-29 23:40:00</MatchDate>
        <MatchType>3</MatchType>
        <MatchContextId>18</MatchContextId>
        <SourceSystem>Hattrick</SourceSystem>
        <CupId>18</CupId>
        <CupLevel>1</CupLevel>
        <CupLevelIndex>1</CupLevelIndex>
        <HomeGoals>1</HomeGoals>
        <AwayGoals>2</AwayGoals>
      </Match>
      <Match>
        <MatchID>999888777</MatchID>
        <HomeTeam>
          <HomeTeamID>537758</HomeTeamID><HomeTeamName>Pulgas Arrechas</HomeTeamName>
        </HomeTeam>
        <AwayTeam><AwayTeamID>72</AwayTeamID><AwayTeamName>Un amistoso</AwayTeamName></AwayTeam>
        <MatchDate>2026-07-26 23:40:00</MatchDate>
        <MatchType>9</MatchType>
        <MatchContextId>0</MatchContextId>
        <SourceSystem>Hattrick</SourceSystem>
        <CupId>0</CupId>
        <CupLevel>0</CupLevel>
        <CupLevelIndex>0</CupLevelIndex>
        <HomeGoals>0</HomeGoals>
        <AwayGoals>4</AwayGoals>
      </Match>
    </MatchList>
  </Team>
</HattrickData>
"""


def test_the_archive_rescues_every_match_that_the_recent_calendar_no_longer_reaches() -> None:
    """La primera carga guarda todo lo que expone el archivo, no sólo la
    temporada actual. Partidos decide después si enseña competitivos,
    amistosos o ignora los no oficiales; el almacenamiento no los destruye."""

    async def run() -> None:
        from sqlalchemy import select

        uow, chpp, team_id = await _setup()

        class ConArchivo(FakeCHPP):
            async def fetch(self, file: str, version: str, **params: Any) -> dict[str, Any]:
                if file == "matchesarchive":
                    assert version == "1.5", "las versiones <1.3 no traen CupLevel"
                    # Como el archivo real: sólo los partidos de la ventana
                    # pedida. Devolver los mismos para cualquier rango es justo
                    # lo que hace Hattrick cuando IGNORA el rango, y eso ya no
                    # se toma por bueno (2026-09-14).
                    payload = get_parser(file)(ARCHIVO_CON_HUECO)
                    formato = "%Y-%m-%d %H:%M:%S"
                    desde = datetime.strptime(params["FirstMatchDate"], formato)
                    hasta = datetime.strptime(params["LastMatchDate"], formato)
                    payload["matches"] = [
                        mt
                        for mt in payload["matches"]
                        if desde <= datetime.strptime(mt["match_date"], formato) <= hasta
                    ]
                    return payload
                return await super().fetch(file, version, **params)

        handler = SyncTeamHandler(uow, ConArchivo())
        cmd = SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["matches"])
        primero = await handler.execute(cmd)
        # 767370369 ya venía en matches.xml; faltaban la copa y el amistoso.
        assert primero.rescued_matches == 2

        async with uow as u:
            rescatado = await u.session.scalar(
                select(m.Match).where(m.Match.ht_match_id == 770729379)
            )
            assert rescatado is not None
            assert rescatado.status == "FINISHED"
            assert (rescatado.home_goals, rescatado.away_goals) == (1, 2)
            # Sin esto el partido existe pero la pantalla de Copa no lo ve:
            # agrupa por esta pareja y un -1 no es ninguna copa.
            assert (rescatado.cup_level, rescatado.cup_level_index) == (1, 1)
            # El amistoso también queda guardado; el toggle de la pantalla es
            # quien decide si se muestra.
            amistoso = await u.session.scalar(
                select(m.Match).where(m.Match.ht_match_id == 999888777)
            )
            assert amistoso is not None
            # Y el que ya estaba no se duplica ni se pisa: matches.xml lo tenía
            # como próximo, con sus órdenes, y eso lo sabe mejor que el archivo.
            ya_estaba = await u.session.scalar(
                select(m.Match).where(m.Match.ht_match_id == 767370369)
            )
            assert ya_estaba is not None
            assert ya_estaba.orders_given is True

        segundo = await handler.execute(cmd)
        assert segundo.rescued_matches == 0  # incremental: no se repesca nada

    asyncio.run(run())


def test_match_archive_splits_the_50_result_limit_then_only_reads_the_new_tail() -> None:
    """No hay pageIndex en matchesarchive: 50 filas obligan a bisecar el
    rango. Tras completar esa primera lectura, el siguiente sync arranca en
    la marca de agua (con solape) y sólo inserta el partido nuevo."""

    async def run() -> None:
        from datetime import UTC, timedelta

        from sqlalchemy import func, select

        uow, _unused, team_id = await _setup()
        founded = datetime(2020, 1, 1, tzinfo=UTC)
        first_until = datetime(2022, 1, 1, tzinfo=UTC)

        async with uow as u:
            team = await u.session.get(m.Team, team_id)
            assert team is not None
            team.founded_at = founded
            await u.commit()

        def archived_match(match_id: int, when: datetime) -> dict[str, Any]:
            return {
                "ht_match_id": match_id,
                "match_date": when.strftime("%Y-%m-%d %H:%M:%S"),
                "match_type": 1,
                "home_team_id": 537758,
                "away_team_id": match_id,
                "home_team_name": "Pulgas Arrechas",
                "away_team_name": f"Rival {match_id}",
                "home_goals": 1,
                "away_goals": 0,
                "cup_level": 0,
                "cup_level_index": 0,
                "source_system": "hattrick",
            }

        class LimitedArchive:
            def __init__(self) -> None:
                self.phase = "initial"
                self.archive_calls: list[dict[str, Any]] = []
                self.matchdetails_calls = 0

            async def fetch(self, file: str, version: str, **params: Any) -> dict[str, Any]:
                if file == "arenadetails":
                    return {"current_capacity": {"total": 0}}
                if file == "matchdetails":
                    self.matchdetails_calls += 1
                    return {}
                assert file == "matchesarchive"
                self.archive_calls.append(params)
                since = datetime.strptime(params["FirstMatchDate"], "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=UTC
                )
                until = datetime.strptime(params["LastMatchDate"], "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=UTC
                )
                if self.phase == "initial":
                    if until - since > timedelta(days=500):
                        # La respuesta está potencialmente truncada. El
                        # contenido concreto no importa: debe descartarse y
                        # reconstruirse desde sus dos mitades completas.
                        return {
                            "matches": [
                                archived_match(800_000 + i, since + timedelta(minutes=i))
                                for i in range(50)
                            ]
                        }
                    if since == founded:
                        return {"matches": [archived_match(700_001, since + timedelta(days=1))]}
                    # 2026-09-14: con ventanas de 12 semanas, «un día después
                    # del inicio de la ventana» caía en la última, dentro de
                    # las 16 semanas recientes, y el backfill normal pedía su
                    # detalle. El segundo partido va en una fecha vieja fija y
                    # sólo lo devuelve la ventana que la contiene.
                    viejo = datetime(2021, 1, 1, tzinfo=UTC)
                    if since <= viejo < until:
                        return {"matches": [archived_match(700_002, viejo)]}
                    return {"matches": []}
                return {
                    "matches": [
                        archived_match(700_002, first_until - timedelta(days=1)),
                        archived_match(700_003, first_until + timedelta(days=1)),
                    ]
                }

        chpp = LimitedArchive()
        handler = SyncTeamHandler(uow, chpp)
        first = SyncResult(sync_id=1, status="completed")
        async with uow as u:
            await handler._sync_match_history(
                u, team_id, 537758, first_until, first, on_progress=None
            )
            # El backfill normal de detalles no toca las filas históricas.
            await handler._backfill_missing_match_details(
                u, team_id, 537758, first, on_progress=None
            )
            await u.commit()

        # 2026-09-14: dos años se piden en ventanas de 12 semanas --un rango
        # largo Hattrick lo ignora--, así que son nueve consultas y ninguna
        # llega al tope de 50 que obligaría a bisecar.
        from app.application.commands.sync_team import MATCH_ARCHIVE_WINDOW

        assert len(chpp.archive_calls) == 9
        for c in chpp.archive_calls:
            desde = datetime.strptime(c["FirstMatchDate"], "%Y-%m-%d %H:%M:%S")
            hasta = datetime.strptime(c["LastMatchDate"], "%Y-%m-%d %H:%M:%S")
            assert hasta - desde <= MATCH_ARCHIVE_WINDOW
        assert chpp.archive_calls[0]["FirstMatchDate"] == "2020-01-01 00:00:00"
        assert first.rescued_matches == 2
        assert chpp.matchdetails_calls == 0

        chpp.phase = "incremental"
        chpp.archive_calls.clear()
        second = SyncResult(sync_id=2, status="completed")
        second_until = first_until + timedelta(days=7)
        async with uow as u:
            await handler._sync_match_history(
                u, team_id, 537758, second_until, second, on_progress=None
            )
            await u.commit()

        assert len(chpp.archive_calls) == 1
        assert chpp.archive_calls[0]["FirstMatchDate"] == "2021-12-30 00:00:00"
        assert second.rescued_matches == 1
        async with uow as u:
            total = await u.session.scalar(select(func.count()).select_from(m.Match))
            team = await u.session.get(m.Team, team_id)
            new_match = await u.session.scalar(
                select(m.Match).where(m.Match.ht_match_id == 700_003)
            )
            assert total == 3
            assert team is not None and team.matches_history_complete is True
            assert team.matches_history_synced_until == second_until.replace(tzinfo=None)
            assert new_match is not None and new_match.history_summary_only is False

    asyncio.run(run())


def test_match_archive_error_does_not_seal_an_incomplete_history() -> None:
    """Un chpperror HTTP 200 no puede convertirse en «historial vacío» ni
    adelantar la marca de agua: el próximo sync debe volver a intentar todo."""

    async def run() -> None:
        from datetime import UTC

        uow, _unused, team_id = await _setup()

        class ArchiveError:
            async def fetch(self, file: str, version: str, **params: Any) -> dict[str, Any]:
                assert file == "matchesarchive"
                return {
                    "matches": [],
                    "chpp_error": True,
                    "chpp_error_code": 42,
                    "chpp_error_message": "Invalid date range",
                }

        handler = SyncTeamHandler(uow, ArchiveError())
        result = SyncResult(sync_id=1, status="completed")
        async with uow as u:
            await handler._sync_match_history(
                u,
                team_id,
                537758,
                datetime(2026, 9, 11, tzinfo=UTC),
                result,
                on_progress=None,
            )
            await u.commit()

        async with uow as u:
            team = await u.session.get(m.Team, team_id)
            assert team is not None
            assert team.matches_history_complete is False
            assert team.matches_history_synced_until is None
        assert result.status == "partial"
        assert result.errors == ["matchesarchive: CHPP 42: Invalid date range"]

    asyncio.run(run())


def test_players_missing_from_a_later_sync_are_marked_departed() -> None:
    """Un jugador que ya no viene en players.xml se fue del club, se marca
    left_team_at, nunca se borra, y deja de contar como plantilla activa.

    Bug real observado: tras conectar una cuenta real, el conteo de jugadores
    del dashboard mostraba 32 en vez de los 24 reales, porque un sync anterior
    (con una plantilla distinta) nunca marcó como salidos a quienes ya no
    estaban, se acumulaban para siempre."""

    async def run() -> None:
        from sqlalchemy import select

        uow, chpp, team_id = await _setup()
        handler = SyncTeamHandler(uow, chpp)
        full_roster = get_parser("players")((FIXTURES / "players.xml").read_bytes())
        assert len(full_roster["players"]) == 24

        await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["players"])
        )

        # Un segundo sync con una plantilla más chica: se vendieron 20 jugadores.
        reduced = {"players": full_roster["players"][:4]}

        class ReducedRosterCHPP:
            async def fetch(self, file: str, version: str, **params: Any) -> dict[str, Any]:
                return reduced if file == "players" else {}

        handler2 = SyncTeamHandler(uow, ReducedRosterCHPP())
        await handler2.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["players"])
        )

        kept_ids = {p["ht_player_id"] for p in reduced["players"]}
        async with uow as u:
            rows = (
                (await u.session.execute(select(m.Player).where(m.Player.team_id == team_id)))
                .scalars()
                .all()
            )
            # 25 y no 24 desde el 2026-08-25: el sync normal recorre el
            # libro de compraventas y este crea la ficha de quien esta app
            # nunca vio en la plantilla. Append-only: nadie se borra.
            assert len(rows) == 25
            active = [p for p in rows if p.left_team_at is None]
            departed = [p for p in rows if p.left_team_at is not None]
            assert len(active) == 4
            # 21: los veinte de la plantilla que ya no vienen, mas el que
            # entro por el libro y tampoco esta en el roster de hoy.
            assert len(departed) == 21
            assert {p.ht_player_id for p in active} == kept_ids

    asyncio.run(run())


def test_a_player_released_without_a_sale_is_also_announced() -> None:
    """HL-2xx, pedido explícito: no sólo las ventas, un jugador despedido
    (o cuyo préstamo terminó, etc.) SIN ninguna transacción en
    `transfersteam.xml` también debe verse en "Qué cambió", aunque no haya
    precio que anunciar."""

    async def run() -> None:
        from sqlalchemy import select

        uow, chpp, team_id = await _setup()
        handler = SyncTeamHandler(uow, chpp)
        full_roster = get_parser("players")((FIXTURES / "players.xml").read_bytes())
        released_player = full_roster["players"][4]
        released_name = f"{released_player['first_name']} {released_player['last_name']}".strip()

        await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["players"])
        )

        reduced = {"players": full_roster["players"][:4]}

        class ReducedRosterCHPP:
            async def fetch(self, file: str, version: str, **params: Any) -> dict[str, Any]:
                return reduced if file == "players" else {}

        handler2 = SyncTeamHandler(uow, ReducedRosterCHPP())
        result2 = await handler2.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["players"])
        )

        assert ("jugadores", f"{released_name} salió de la plantilla") in [
            (c["category"], c["summary"]) for c in result2.changes
        ]

        async with uow as u:
            change_row = await u.session.scalar(
                select(m.SyncChange).where(
                    m.SyncChange.summary == f"{released_name} salió de la plantilla"
                )
            )
            assert change_row is not None

    asyncio.run(run())


def test_a_player_sold_in_the_same_sync_is_announced_as_a_change() -> None:
    """HL-2xx, bug real: un jugador que sale del roster Y aparece vendido en
    `transfersteam.xml` del MISMO sync no generaba ninguna entrada en "Qué
    cambió", `mark_departed` (fichero `players`) no sabe todavía el precio,
    y `_persist_transfers` (fichero `transfersteam`, que corre después en la
    misma pasada) nunca anunciaba nada. La venta debe verse igual, sin
    importar el orden de los ficheros."""

    async def run() -> None:
        from sqlalchemy import select

        uow, chpp, team_id = await _setup()
        handler = SyncTeamHandler(uow, chpp)
        full_roster = get_parser("players")((FIXTURES / "players.xml").read_bytes())
        sold_player = full_roster["players"][4]
        sold_name = f"{sold_player['first_name']} {sold_player['last_name']}".strip()

        await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["players"])
        )

        reduced = {"players": full_roster["players"][:4]}
        transfers_payload = {
            "stats": {},
            "transfers": [
                {
                    "ht_player_id": sold_player["ht_player_id"],
                    "transfer_type": "S",
                    "seller_team_id": 537758,
                    "buyer_team_id": 999999,
                    "price": 8_690_000,
                    "deadline": "2026-08-12 15:08:00",
                    "tsi": 5000,
                }
            ],
        }

        class SoldPlayerCHPP:
            async def fetch(self, file: str, version: str, **params: Any) -> dict[str, Any]:
                if file == "players":
                    return reduced
                if file == "transfersteam":
                    return transfers_payload
                return {}

        handler2 = SyncTeamHandler(uow, SoldPlayerCHPP())
        result2 = await handler2.execute(
            SyncTeamCommand(
                user_id=1,
                team_id=team_id,
                ht_team_id=537758,
                files=["players", "transfersteam"],
            )
        )

        assert any(
            c["category"] == "jugadores" and c["summary"] == f"{sold_name} se vendió por 8.690.000"
            for c in result2.changes
        )

        async with uow as u:
            change_row = await u.session.scalar(
                select(m.SyncChange).where(m.SyncChange.summary.like(f"{sold_name} se vendió%"))
            )
            assert change_row is not None

    asyncio.run(run())


def test_teamdetails_persists_series_ht_id() -> None:
    """Sin series_ht_id (LeagueLevelUnitID) no hay forma de pedir leaguedetails:
    ese fichero se sincroniza por serie, no por equipo."""

    async def run() -> None:
        uow, chpp, team_id = await _setup()
        handler = SyncTeamHandler(uow, chpp)
        cmd = SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["teamdetails"])

        first = await handler.execute(cmd)
        assert first.status == "completed"
        assert first.snapshots_written == 1

        async with uow as u:
            team = await u.session.get(m.Team, team_id)
            assert team.series_ht_id == 34162
            assert team.series_name == "V.92"
            assert team.league_name == "Colombia"

        second = await handler.execute(cmd)
        assert second.snapshots_written == 0
        assert second.unchanged == 1

    asyncio.run(run())


def test_leaguedetails_requires_teamdetails_first() -> None:
    """Sin la serie conocida, pedir leaguedetails falla con un error claro en
    vez de adivinar o pedir el fichero equivocado."""

    async def run() -> None:
        uow, chpp, team_id = await _setup()
        handler = SyncTeamHandler(uow, chpp)
        result = await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["leaguedetails"])
        )
        assert result.status == "partial"
        assert result.errors and "serie" in result.errors[0]

    asyncio.run(run())


def test_leaguedetails_persists_standings_for_the_whole_series() -> None:
    async def run() -> None:
        uow, chpp, team_id = await _setup()
        handler = SyncTeamHandler(uow, chpp)

        await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["teamdetails"])
        )
        first = await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["leaguedetails"])
        )
        assert first.snapshots_written == 1  # una jornada = una escritura

        from sqlalchemy import func, select

        async with uow as u:
            total = await u.session.scalar(select(func.count()).select_from(m.Standing))
            assert total == 8  # las 8 filas del fixture, en una sola jornada
            own = await u.session.scalar(select(m.Standing).where(m.Standing.team_ht_id == 537758))
            # El fixture trae CurrentMatchRound=1 con Matches=0 para todos
            # los equipos, la foto de antes de jugar nada, jornada 0
            # realmente completada, no la 1.
            assert own.match_round == 0
            assert own.series_ht_id == 34162

        # Re-sincronizar la misma jornada no debe duplicar filas.
        second = await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["leaguedetails"])
        )
        assert second.snapshots_written == 0
        assert second.unchanged == 1
        async with uow as u:
            total = await u.session.scalar(select(func.count()).select_from(m.Standing))
            assert total == 8

    asyncio.run(run())


def test_match_details_persists_ratings_and_is_idempotent() -> None:
    async def run() -> None:
        uow, chpp, team_id = await _setup()
        handler = SyncTeamHandler(uow, chpp)
        cmd = SyncMatchDetailsCommand(user_id=1, team_id=team_id, ht_match_id=765274387)

        first = await handler.execute_match_details(cmd)
        assert first.status == "completed"
        assert first.snapshots_written == 2  # dos MatchRating: home + away

        from sqlalchemy import select

        async with uow as u:
            home = await u.session.scalar(
                select(m.MatchRating).where(
                    m.MatchRating.ht_match_id == 765274387,
                    m.MatchRating.team_ht_id == 537758,
                )
            )
            assert home is not None
            assert home.midfield == 14
            assert home.right_def == 45
            assert home.possession_first_half == 48

        second = await handler.execute_match_details(cmd)
        assert second.unchanged == 1
        assert second.snapshots_written == 0

    asyncio.run(run())


def test_match_details_backfills_home_stadium_history() -> None:
    """El detalle de partido trae ventas y arenadetails el aforo actual.
    Si los ratings ya estaban, el backfill aún debe poder completar el
    estadio una vez; un segundo intento no puede duplicarlo."""

    async def run() -> None:
        from sqlalchemy import select

        uow, chpp, team_id = await _setup()
        handler = SyncTeamHandler(uow, chpp)
        await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["matches"])
        )
        cmd = SyncMatchDetailsCommand(
            user_id=1,
            team_id=team_id,
            ht_match_id=765274387,
            arena_capacity={
                "terraces": 40000,
                "basic": 15000,
                "roof": 6000,
                "vip": 1500,
                "total": 62500,
            },
        )

        first = await handler.execute_match_details(cmd)
        assert first.status == "completed"
        async with uow as u:
            stadium = await u.session.scalar(
                select(m.StadiumHistory).where(m.StadiumHistory.ht_match_id == 765274387)
            )
            assert stadium is not None
            assert stadium.team_id == team_id
            assert stadium.capacity_total == 62500
            # Se guarda el total, no el desglose (2026-09-01).
            assert stadium.sold_total == 54979

        second = await handler.execute_match_details(cmd)
        assert second.unchanged == 1
        assert second.snapshots_written == 0

    asyncio.run(run())


def test_player_details_persists_last_match_and_mother_club() -> None:
    """HL-15x fase B: `playerdetails.xml` no es append-only, se escribe
    sobre el snapshot más reciente del jugador. `LastMatch` solo llega si
    se pide con `includeMatchInfo=true` (confirmado en vivo: sin ese
    parámetro CHPP omite el bloque entero), este fixture simula esa
    respuesta para fijar que el parseo y la escritura funcionan."""

    async def run() -> None:
        uow, chpp, team_id = await _setup()
        handler = SyncTeamHandler(uow, chpp)

        # El jugador tiene que existir ya (mismo PlayerID en players.xml y
        # playerdetails.xml, ambos fixtures reales) antes de poder
        # actualizar su snapshot más reciente.
        await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["players"])
        )

        result = await handler.execute_player_details(
            SyncPlayerDetailsCommand(user_id=1, team_id=team_id, ht_player_id=468921494)
        )
        assert result.status == "completed"
        assert result.errors == []

        from sqlalchemy import select

        async with uow as u:
            player = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == 468921494)
            )
            assert player is not None
            assert player.mother_club_team_name == "Otro Equipo FC"

            snap = await u.session.scalar(
                select(m.PlayerSnapshot)
                .where(m.PlayerSnapshot.player_id == player.id)
                .order_by(m.PlayerSnapshot.captured_at.desc())
                .limit(1)
            )
            assert snap is not None
            assert snap.last_match_ht_id == 123456789
            assert snap.last_match_position_code == 13
            assert snap.last_match_played_minutes == 90
            assert snap.last_match_rating == 8.5
            # 2026-08-09, pedido explícitamente: sin esta fecha, "Último
            # partido" no puede distinguir un dato reciente de uno viejo
            # (ver test_squad_last_match_recency.py para el filtro). SQLite
            # devuelve el valor sin tzinfo aunque se guardara con
            # `.replace(tzinfo=UTC)`, mismo patrón ya visto en
            # analysis.py/changes_history.py, se compara naive.
            # Hora sueca del fichero (CEST, UTC+2) guardada ya en UTC.
            assert snap.last_match_played_at == datetime(2026, 7, 19, 14, 0)
            # El fixture matchlineup.xml genérico es de OTRO equipo
            # (etbenianos1) y no incluye a este jugador, el best-effort de
            # `_fetch_last_match_behaviour` debe quedarse en None sin
            # romper el resto de playerdetails (ver
            # test_player_details_fills_in_the_real_individual_order abajo
            # para el caso en que sí aparece).
            assert snap.last_match_behaviour_code is None
            assert snap.career_caps == 0
            assert snap.career_caps_u20 == 0

    asyncio.run(run())


def test_player_details_fills_in_the_real_individual_order() -> None:
    """2026-08-09, pedido explícitamente: "Última semana" solo mostraba la
    posición base, nunca si la orden individual real fue
    Ofensivo/Defensivo/Hacia el medio/Hacia la banda, ese dato vive en
    `Behaviour` de matchlineup.xml PARA EL PARTIDO CONCRETO de
    `LastMatch`, no en `LastMatch` mismo. `_fetch_last_match_behaviour`
    encadena esa segunda llamada automáticamente."""

    class BehaviourCHPP(FakeCHPP):
        async def fetch(self, file: str, version: str, **params: Any) -> dict[str, Any]:
            if file == "matchlineup":
                self.calls += 1
                return {
                    "ht_match_id": params["matchID"],
                    "ht_team_id": params["teamID"],
                    "team_name": "Pulgas Arrechas",
                    "players": [
                        {
                            "ht_player_id": 468921494,
                            "name": "Alberto Gutiérrez Caviedes",
                            "role_id": 112,
                            "position_code": 112,
                            "rating_stars": 11.5,
                            "rating_stars_end": 11.0,
                            "behaviour": 1,
                        }
                    ],
                }
            return await super().fetch(file, version, **params)

    async def run() -> None:
        uow, _, team_id = await _setup()
        handler = SyncTeamHandler(uow, BehaviourCHPP())

        await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["players"])
        )
        result = await handler.execute_player_details(
            SyncPlayerDetailsCommand(user_id=1, team_id=team_id, ht_player_id=468921494)
        )
        assert result.status == "completed"

        from sqlalchemy import select

        async with uow as u:
            player = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == 468921494)
            )
            assert player is not None
            snap = await u.session.scalar(
                select(m.PlayerSnapshot)
                .where(m.PlayerSnapshot.player_id == player.id)
                .order_by(m.PlayerSnapshot.captured_at.desc())
                .limit(1)
            )
            assert snap is not None
            assert snap.last_match_behaviour_code == 1  # Ofensivo

    asyncio.run(run())


def test_a_later_players_sync_does_not_wipe_playerdetails_fields() -> None:
    """Bug real: `career_assists` y `last_match_*` solo llegan por
    `playerdetails.xml` (fase B), nunca por `players.xml` (fase A). Como
    `append_snapshot` crea una fila NUEVA en cuanto cambia cualquier campo
    de fase A (aquí, la forma), sin arrastrar lo anterior esos dos campos se
    resetearían a 0/None en cada sync normal posterior a una sincronización
    de fase B, silenciosamente, sin ningún error visible."""

    async def run() -> None:
        from sqlalchemy import select

        uow, chpp, team_id = await _setup()
        handler = SyncTeamHandler(uow, chpp)

        await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["players"])
        )
        details = await handler.execute_player_details(
            SyncPlayerDetailsCommand(user_id=1, team_id=team_id, ht_player_id=468921494)
        )
        assert details.errors == []

        async with uow as u:
            player = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == 468921494)
            )
            snap = await u.session.scalar(
                select(m.PlayerSnapshot)
                .where(m.PlayerSnapshot.player_id == player.id)
                .order_by(m.PlayerSnapshot.captured_at.desc())
                .limit(1)
            )
            assert snap.career_assists == 21
            assert snap.last_match_ht_id == 123456789

        # Un sync normal posterior, con la forma de ese jugador cambiada
        # dispara una fila NUEVA en player_snapshots (fase A, sin
        # career_assists/last_match en su payload).
        full_roster = get_parser("players")((FIXTURES / "players.xml").read_bytes())
        changed = {
            "players": [
                {**p, "form": (p["form"] % 7) + 1} if p["ht_player_id"] == 468921494 else p
                for p in full_roster["players"]
            ]
        }

        class ChangedFormCHPP:
            async def fetch(self, file: str, version: str, **params: Any) -> dict[str, Any]:
                return changed if file == "players" else {}

        handler2 = SyncTeamHandler(uow, ChangedFormCHPP())
        result2 = await handler2.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["players"])
        )
        assert result2.snapshots_written >= 1

        async with uow as u:
            player = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == 468921494)
            )
            rows = (
                (
                    await u.session.execute(
                        select(m.PlayerSnapshot)
                        .where(m.PlayerSnapshot.player_id == player.id)
                        .order_by(m.PlayerSnapshot.captured_at.desc())
                    )
                )
                .scalars()
                .all()
            )
            assert len(rows) == 2  # sí se creó una fila nueva
            newest = rows[0]
            assert newest.career_assists == 21  # arrastrado, no reseteado
            assert newest.last_match_ht_id == 123456789  # arrastrado, no reseteado
            assert newest.career_caps == 0  # arrastrado, no reseteado a None

    asyncio.run(run())


def test_sync_partial_on_chpp_failure() -> None:
    class BrokenCHPP:
        async def fetch(self, file: str, version: str, **params: Any) -> dict[str, Any]:
            raise ConnectionError("CHPP caído")

    async def run() -> None:
        uow, _, team_id = await _setup()
        handler = SyncTeamHandler(uow, BrokenCHPP())
        result = await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758)
        )
        assert result.status == "partial"
        assert result.errors and "players" in result.errors[0]

    asyncio.run(run())
