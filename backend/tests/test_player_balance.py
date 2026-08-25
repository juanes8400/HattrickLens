"""HL-161: saldo neto por jugador.

Cubre, en el orden en que se construyen: la sincronización a demanda de
transfersplayer.xml (precio de compra real para jugadores anteriores a esta
app), el contador de intentos de venta (currentbids.xml), el motor de
dominio que calcula el saldo, y el servicio de consulta que junta todo. Se
amplía según avanza la historia.
"""
import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.sync_team import (
    VERSION_DEL_LIBRO,
    SyncBackfillBatchCommand,
    SyncPlayerEnrichmentCommand,
    SyncTeamCommand,
    SyncTeamHandler,
    SyncTransfersHistoryCommand,
    SyncTransfersPlayerCommand,
)
from app.application.queries.player_balance import (
    PlayerBalanceQueryService,
    _bid_hour_bucket,
)
from app.domain.engines.player_balance import (
    PlayerTransferRecord,
    SalarySnapshot,
    agent_commission_pct,
    compute_balance,
)
from app.infrastructure.chpp.parsers import get_parser
from app.infrastructure.db import models as m
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from tests.conftest import seeded_session

FIXTURES_DIR = __file__.rsplit("\\", 1)[0] + "\\fixtures"


class FakeCHPP:
    """El libro de compraventas se sirve VACIO a proposito.

    2026-08-25: desde que "Sincronizar ahora" tambien recorre el libro, servir
    aqui el fixture de `transfersteam` metia compras y ventas reales encima de
    los escenarios que estas pruebas montan a mano, y les cambiaba el estado
    del jugador bajo los pies. Lo que se prueba aqui es el saldo, no el libro
    --ese tiene sus propias pruebas mas abajo, con su propio doble--.
    """

    async def fetch(self, file: str, version: str, **params: Any) -> dict[str, Any]:
        from pathlib import Path

        if file == "transfersteam":
            return {"transfers": [], "pages": 1}
        return get_parser(file)(
            (Path(FIXTURES_DIR) / f"{file}.xml").read_bytes()
        )


async def _setup_with_player(ht_player_id: int) -> tuple[SqlAlchemyUnitOfWork, FakeCHPP, int, int]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as s:
        team = m.Team(ht_team_id=537758, name="Pulgas Arrechas")
        s.add(team)
        await s.flush()
        team_id = team.id
        player = m.Player(
            ht_player_id=ht_player_id, team_id=team_id,
            first_name="Lander", last_name="Fripont",
        )
        s.add(player)
        await s.commit()

    return SqlAlchemyUnitOfWork(factory), FakeCHPP(), team_id, ht_player_id


def test_transfers_player_sync_finds_our_own_purchase() -> None:
    """El fixture real (transfersplayer.xml) tiene 3 transferencias: la más
    reciente nos tiene como VENDEDOR, la de en medio nos tiene como
    COMPRADOR (1.800.000, 2026-05-16) — esa es la que debe quedar guardada
    como precio de compra, ignorando las otras dos (no somos parte)."""
    async def run() -> None:
        uow, chpp, team_id, ht_player_id = await _setup_with_player(495018863)
        handler = SyncTeamHandler(uow, chpp)
        result = await handler.execute_transfers_player(
            SyncTransfersPlayerCommand(user_id=1, team_id=team_id, ht_player_id=ht_player_id)
        )
        assert result.status == "completed"
        assert result.snapshots_written == 1

        async with uow as u:
            player = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == ht_player_id)
            )
            assert player.purchase_price == 1800000
            # SQLite no conserva tzinfo en el viaje de ida y vuelta.
            # 16:10 en el fichero de CHPP son horas SUECAS (CEST en mayo, UTC+2),
            # así que se guardan como las 14:10 UTC. Ver `ht_time.ht_to_utc`.
            assert player.purchased_at == datetime(2026, 5, 16, 14, 10)

    asyncio.run(run())


def test_transfers_player_sync_leaves_purchase_price_unset_when_never_the_buyer() -> None:
    """Un jugador que aparece en transfersplayer.xml pero donde nuestro
    equipo NUNCA es comprador (p. ej. porque de verdad vino de la cantera)
    no debe quedar con un precio inventado — se deja en None para que el
    dominio aplique la regla de canterano por separado. 2026-08-05, pedido
    explícitamente ("backfill de un jugador máximo una vez"): se marca
    `tsi_at_purchase_attempted` de todas formas — transfersplayer.xml ya
    trae TODA la historia, así que si no aparecimos como compradores ahora,
    nunca vamos a aparecer, y no debe volver a pedirse este fichero."""
    async def run() -> None:
        # ht_team_id distinto de cualquier Buyer/Seller del fixture real.
        uow, chpp, team_id, ht_player_id = await _setup_with_player(495018863)
        async with uow as u:
            team = await u.session.get(m.Team, team_id)
            team.ht_team_id = 999999999
            await u.session.commit()

        handler = SyncTeamHandler(uow, chpp)
        result = await handler.execute_transfers_player(
            SyncTransfersPlayerCommand(user_id=1, team_id=team_id, ht_player_id=ht_player_id)
        )
        assert result.status == "completed"
        assert result.snapshots_written == 1
        assert result.unchanged == 0

        async with uow as u:
            player = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == ht_player_id)
            )
            assert player.purchase_price is None
            assert player.tsi_at_purchase_attempted is True

    asyncio.run(run())


def test_upsert_identity_clears_left_team_at_when_player_reappears_in_roster() -> None:
    """Edge case real 2026-08-05: un jugador despedido/vendido en tiempo
    real (`mark_departed` le puso `left_team_at`) que vuelve a aparecer en
    `players.xml` está de vuelta en la plantilla HOY — sin esto,
    `roster()`/`_latest()` lo seguiría excluyendo de "plantilla actual"
    para siempre, aunque un sync real ya lo vea otra vez."""
    async def run() -> None:
        uow, _, team_id, ht_player_id = await _setup_with_player(468921494)
        async with uow as u:
            player = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == ht_player_id)
            )
            player.left_team_at = datetime(2026, 1, 1)
            await u.session.commit()

        async with uow as u:
            await u.players.upsert_identity(ht_player_id, team_id, "Lander", "Fripont")
            await u.session.commit()

        async with uow as u:
            player = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == ht_player_id)
            )
            assert player.left_team_at is None

    asyncio.run(run())


def test_player_enrichment_backfill_reconstructs_age_and_fills_country_character_specialty() -> None:
    """Pedido explícitamente por el usuario 2026-08-04, SIN botón: una sola
    llamada a playerdetails.xml rellena edad-en-la-venta, país, carácter y
    especialidad de un tirón. Fixture real (jugador 468921494): Age=30,
    AgeDays=45 HOY, Agreeability=3, Specialty=0, NativeLeagueName=Colombia.
    Con una venta hace exactamente 20 días, la edad en la venta debe ser
    30a 25d (45-20=25, sin cruzar el año) — playerdetails.xml funciona
    aunque el jugador ya no esté en nuestro equipo."""
    async def run() -> None:
        uow, chpp, team_id, ht_player_id = await _setup_with_player(468921494)
        sold_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=20)
        async with uow as u:
            player = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == ht_player_id)
            )
            player.sold_at = sold_at
            await u.session.commit()

        handler = SyncTeamHandler(uow, chpp)
        result = await handler.execute_player_enrichment_backfill(
            SyncPlayerEnrichmentCommand(user_id=1, team_id=team_id, ht_player_id=ht_player_id)
        )
        assert result.status == "completed"
        assert result.snapshots_written == 1

        async with uow as u:
            player = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == ht_player_id)
            )
            assert player.age_years_at_sale == 30
            assert player.age_days_at_sale == 25
            assert player.native_country == "Colombia"
            assert player.agreeability == 3
            assert player.specialty == 0

    asyncio.run(run())


def test_player_balance_reads_skills_at_purchase_and_sale_from_real_snapshots() -> None:
    """2026-08-05, tabla Detalle de 43 columnas: a diferencia de la edad,
    una habilidad no es función pura del tiempo (entrenar la cambia), así
    que "al entrar"/"al salir" solo puede venir de un `player_snapshot`
    real cerca de esa fecha — nunca reconstruida. `snapshot_at_or_after`
    (compra) y `snapshot_at` (venta) deben devolver exactamente el
    snapshot correcto entre varios. Sin snapshot DESPUÉS de la venta a
    propósito: uno ahí significaría que volvió a la plantilla (ver
    `test_player_balance_query_service_treats_returning_player_as_active_not_sold`),
    no algo que este test deba mezclar."""
    async def run() -> None:
        uow, chpp, team_id, ht_player_id = await _setup_with_player(468921494)
        purchased_at = datetime(2026, 1, 1, 12, 0)
        sold_at = datetime(2026, 3, 1, 12, 0)
        async with uow as u:
            player = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == ht_player_id)
            )
            player.purchase_price = 1000000
            player.purchased_at = purchased_at
            player.sale_price = 2000000
            player.sold_at = sold_at
            u.session.add(m.Sync(
                id=1, user_id=1, team_id=team_id, kind="players",
                status="completed", started_at=purchased_at,
            ))
            await u.session.flush()
            # Snapshot ANTES de la compra: nunca debe usarse "al entrar"
            # (el jugador no era nuestro todavía).
            u.session.add(m.PlayerSnapshot(
                sync_id=1, player_id=player.id,
                captured_at=purchased_at - timedelta(days=30),
                age_years=20, age_days=0, tsi=100000, form=1, stamina=1,
                experience=1, salary=1000, leadership=1,
                keeper=1, defending=1, playmaking=1, winger=1,
                passing=1, scoring=1, set_pieces=1,
                injury_level=-1, content_hash=b"\x00" * 32,
            ))
            # Snapshot correcto "al entrar" (primero EN O DESPUÉS de la compra).
            u.session.add(m.PlayerSnapshot(
                sync_id=1, player_id=player.id,
                captured_at=purchased_at + timedelta(days=1),
                age_years=20, age_days=1, tsi=110000, form=5, stamina=6,
                experience=7, salary=1000, leadership=9,
                keeper=10, defending=11, playmaking=12, winger=13,
                passing=14, scoring=15, set_pieces=16,
                injury_level=-1, content_hash=b"\x01" * 32,
            ))
            # Snapshot correcto "al salir" (último EN O ANTES de la venta).
            u.session.add(m.PlayerSnapshot(
                sync_id=1, player_id=player.id,
                captured_at=sold_at - timedelta(days=1),
                age_years=20, age_days=59, tsi=150000, form=15, stamina=16,
                experience=17, salary=1000, leadership=19,
                keeper=20, defending=1, playmaking=2, winger=3,
                passing=4, scoring=5, set_pieces=6,
                injury_level=-1, content_hash=b"\x02" * 32,
            ))
            await u.session.commit()

        from app.application.queries.player_balance import PlayerBalanceQueryService
        async with uow as u:
            data = await PlayerBalanceQueryService(u.session).get(team_id)

        row = next(r for r in data.players if r.ht_player_id == ht_player_id)
        assert row.experience_at_purchase == 7
        assert row.leadership_at_purchase == 9
        assert row.keeper_at_purchase == 10
        assert row.set_pieces_at_purchase == 16
        assert row.experience_at_sale == 17
        assert row.keeper_at_sale == 20
        assert row.set_pieces_at_sale == 6

    asyncio.run(run())


def test_player_balance_treats_departure_without_sale_as_zero_price() -> None:
    """2026-08-05, pedido explícitamente: un jugador despedido (sale de la
    plantilla, `left_team_at`, SIN que transfersteam.xml reporte nunca una
    venta real) debe contar como venta a $0, no como "sigue en la
    plantilla" ni "desconocido"."""
    async def run() -> None:
        uow, chpp, team_id, ht_player_id = await _setup_with_player(468921494)
        purchased_at = datetime(2026, 1, 1, 12, 0)
        left_at = datetime(2026, 2, 1, 12, 0)
        async with uow as u:
            player = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == ht_player_id)
            )
            player.purchase_price = 1000000
            player.purchased_at = purchased_at
            player.left_team_at = left_at
            # Nunca se le asigna sold_at/sale_price: no hubo venta real.
            await u.session.commit()

        from app.application.queries.player_balance import PlayerBalanceQueryService
        async with uow as u:
            data = await PlayerBalanceQueryService(u.session).get(team_id)

        row = next(r for r in data.players if r.ht_player_id == ht_player_id)
        assert row.is_sold is True
        assert row.sale_price == 0
        assert row.sold_at == left_at.isoformat()
        assert row.is_departure_without_sale is True
        assert row.saldo == -1000000

    asyncio.run(run())


class FakeChppErrorCHPP:
    """playerdetails.xml devuelve HTTP 200 con <Error>/<ErrorCode> (nunca un
    error HTTP real) para un playerID que ya no resuelve en Hattrick —
    verificado en vivo 2026-08-05 contra ~105 ventas viejas de esta cuenta."""

    async def fetch(self, file: str, version: str, **params: Any) -> dict[str, Any]:
        from pathlib import Path

        name = "chpperror" if file == "playerdetails" else file
        return get_parser(file)((Path(FIXTURES_DIR) / f"{name}.xml").read_bytes())


def test_player_enrichment_marks_enrichment_attempted_on_chpp_error() -> None:
    """Sin este flag, `_backfill_sold_player_details` volvía a pedir
    playerdetails.xml para estos ~105 jugadores en CADA sync, para
    siempre — CHPP nunca lanza un error HTTP para un playerID que ya no
    resuelve, solo un payload <Error>/<ErrorCode> con status 200."""
    async def run() -> None:
        uow, _, team_id, ht_player_id = await _setup_with_player(468921494)
        async with uow as u:
            player = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == ht_player_id)
            )
            player.sold_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=20)
            await u.session.commit()

        handler = SyncTeamHandler(uow, FakeChppErrorCHPP())
        result = await handler.execute_player_enrichment_backfill(
            SyncPlayerEnrichmentCommand(user_id=1, team_id=team_id, ht_player_id=ht_player_id)
        )
        assert result.status == "completed"
        assert result.snapshots_written == 1

        async with uow as u:
            player = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == ht_player_id)
            )
            assert player.enrichment_attempted is True
            assert player.age_years_at_sale is None
            assert player.native_country is None

    asyncio.run(run())


def test_destination_country_backfill_uses_teamdetails_of_the_buyer() -> None:
    """Pedido explícitamente 2026-08-04 ("País Destino" del Excel del
    usuario) — `teamdetails.xml` funciona para equipos ajenos, no solo el
    propio, y trae `Country/CountryName` directo."""
    async def run() -> None:
        uow, chpp, team_id, ht_player_id = await _setup_with_player(468921494)
        async with uow as u:
            player = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == ht_player_id)
            )
            player.sold_at = datetime.now(UTC).replace(tzinfo=None)
            player.buyer_team_id = 999999
            await u.session.commit()

        handler = SyncTeamHandler(uow, chpp)
        result = await handler.execute_destination_country_backfill(
            SyncPlayerEnrichmentCommand(user_id=1, team_id=team_id, ht_player_id=ht_player_id)
        )
        assert result.status == "completed"
        assert result.snapshots_written == 1

        async with uow as u:
            player = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == ht_player_id)
            )
            assert player.destination_country == "Colombia"

    asyncio.run(run())


def test_the_backfill_batch_fills_in_a_sold_players_profile() -> None:
    """Edad, país, carácter y especialidad de un jugador vendido.

    Hasta 2026-08-21 esto ocurría dentro de la sincronización normal, sin
    tope. Con una cuenta de historia larga eran cientos de llamadas a
    Hattrick en una sola petición y se cortaba por tiempo sin terminar
    ninguna, así que ahora vive en su propio botón y va por lotes; lo que se
    comprueba aquí es que el relleno sigue haciéndose.

    El caso reprodujo además un bug real: se le pasaba un "ahora" con zona
    horaria en vez de uno sin ella y reventaba con "can't subtract
    offset-naive and offset-aware datetimes" en cuanto había un vendido de
    verdad que rellenar."""
    async def run() -> None:
        uow, chpp, team_id, ht_player_id = await _setup_with_player(468921494)
        async with uow as u:
            player = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == ht_player_id)
            )
            # Vendido, sin nada de lo nuevo — justo lo que dispara el
            # backfill automático.
            player.sold_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=5)
            team = await u.session.get(m.Team, team_id)
            team.ht_team_id = 537758  # coincide con transfersteam.xml (fixture)
            await u.session.commit()

        handler = SyncTeamHandler(uow, chpp)
        await handler.execute(
            SyncTeamCommand(
                user_id=1, team_id=team_id, ht_team_id=537758, files=["transfersteam"],
            )
        )
        result = await handler.execute_backfill_batch(
            SyncBackfillBatchCommand(user_id=1, team_id=team_id, limite=40)
        )
        assert result.players_done >= 1
        # El CHPP de prueba no responde a `matchesarchive` ni a
        # `playerdetails` de un jugador cualquiera, asi que el censo de
        # partidos y la vigilancia de reventas fallan aqui a proposito; lo que
        # se comprueba es que el resto del lote se hizo igual, que es la razon
        # de que cada paso capture su error por separado.
        assert all(
            e.startswith(("censo_partidos:", "reventa:")) for e in result.errors
        ), result.errors

        async with uow as u:
            player = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == ht_player_id)
            )
            assert player.native_country == "Colombia"
            assert player.agreeability == 3
            assert player.specialty == 0

    asyncio.run(run())


def test_execute_sync_backfills_current_country_from_players_and_worlddetails() -> None:
    """CountryID de players.xml se resuelve contra worlddetails sin inferir.

    El orden real descarga players antes que worlddetails, por eso el cruce
    debe funcionar al terminar el sync y también para snapshots anteriores.
    """
    async def run() -> None:
        uow, chpp, team_id, ht_player_id = await _setup_with_player(468921494)
        async with uow as u:
            # Equivale a una fila ya sincronizada desde el LeagueList
            # completo de worlddetails (el fixture reducido solo trae
            # Colombia).
            u.session.add(m.WorldContext(
                ht_league_id=35, country_id=35, country_name="España"
            ))
            await u.session.commit()
        result = await SyncTeamHandler(uow, chpp).execute(
            SyncTeamCommand(
                user_id=1, team_id=team_id, ht_team_id=537758,
                files=["players"],
            )
        )
        assert result.status == "completed"
        assert result.errors == []

        async with uow as u:
            player = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == ht_player_id)
            )
            # El fixture players.xml identifica al jugador con CountryID=35;
            # worlddetails resuelve 35 a España.
            assert player.native_country == "España"

    asyncio.run(run())


def test_execute_sync_backfills_mandatory_listing_count_for_sold_players() -> None:
    """Pedido explícitamente por el usuario 2026-08-04: vender EXIGE listar
    primero en Hattrick (el solo hecho de ponerlo transferible cuesta
    1.000), así que cualquier jugador VENDIDO tuvo al menos un intento de
    venta — aunque `currentbids.xml` nunca lo haya pillado listado a tiempo
    (el caso normal, sobre todo para el backfill histórico de
    transfersteam.xml). Un jugador vendido con `listing_count=0` sube a 1;
    uno que YA tiene un conteo real (detectado vía currentbids.xml, puede
    ser >1 si se relistó) no se toca."""
    async def run() -> None:
        uow, chpp, team_id, ht_player_id = await _setup_with_player(468921494)
        async with uow as u:
            player = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == ht_player_id)
            )
            player.sold_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=5)
            player.listing_count = 0
            # Segundo jugador vendido, ya con un conteo real (relistado dos
            # veces) — no debe pisarse con el mínimo de 1.
            already_counted = m.Player(
                ht_player_id=900000099, team_id=team_id,
                first_name="Ya", last_name="Contado",
                sold_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=3),
                listing_count=2,
            )
            u.session.add(already_counted)
            team = await u.session.get(m.Team, team_id)
            team.ht_team_id = 537758
            await u.session.commit()

        handler = SyncTeamHandler(uow, chpp)
        result = await handler.execute(
            SyncTeamCommand(
                user_id=1, team_id=team_id, ht_team_id=537758, files=["transfersteam"],
            )
        )
        assert result.status == "completed"
        assert result.errors == []

        async with uow as u:
            player = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == ht_player_id)
            )
            assert player.listing_count == 1

            other = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == 900000099)
            )
            assert other.listing_count == 2  # no se pisa un conteo real mayor

    asyncio.run(run())


# ── Backfill paginado completo — "Actualizar transferencias" (HL-161, 2026-08-04) ──

class FakeTransfersHistoryCHPP:
    """2 páginas simuladas: page 1 trae 2 transferencias "nuevas", page 2
    trae 1 más vieja — ninguno de los 3 jugadores existe de antemano en la
    BD (el punto del backfill: crear la identidad mínima sobre la marcha)."""

    STATS = {
        "total_sum_of_buys": 150000, "total_sum_of_sales": 200000,
        "number_of_buys": 2, "number_of_sales": 1,
    }

    def __init__(self) -> None:
        self.calls: list[int] = []

    async def fetch(self, file: str, version: str, **params: Any) -> dict[str, Any]:
        assert file == "transfersteam"
        page = params.get("pageIndex", 1)
        self.calls.append(page)
        if page == 1:
            transfers = [
                {
                    "ht_transfer_id": 300, "ht_player_id": 555,
                    "player_name": "Foo Barbaz", "transfer_type": "B",
                    "buyer_team_id": 537758, "seller_team_id": 1,
                    "price": 100000, "deadline": "2026-01-10 10:00:00", "tsi": 500,
                },
                {
                    "ht_transfer_id": 200, "ht_player_id": 666,
                    "player_name": "Qux Quux", "transfer_type": "S",
                    "buyer_team_id": 999, "seller_team_id": 537758,
                    "price": 200000, "deadline": "2026-02-15 12:00:00", "tsi": 800,
                },
            ]
        elif page == 2:
            transfers = [
                {
                    "ht_transfer_id": 100, "ht_player_id": 777,
                    "player_name": "Old One", "transfer_type": "B",
                    "buyer_team_id": 537758, "seller_team_id": 2,
                    "price": 50000, "deadline": "2025-01-01 00:00:00", "tsi": 300,
                },
            ]
        else:
            transfers = []
        return {"transfers": transfers, "page_index": page, "pages": 2, "stats": self.STATS}


def test_transfers_history_backfill_creates_players_never_seen_in_roster() -> None:
    """Pedido explícitamente 2026-08-04: "traer toda la información posible
    (así hayan desconocidos)" — un jugador que nunca apareció en
    players.xml (comprado o vendido antes de esta app, o fuera de la única
    página que el sync normal ve) debe quedar creado igual, con lo que sí
    se puede saber (nombre partido de `PlayerName`, precio, TSI) y "?" en
    lo que no (skills, edad reconstruida aparte)."""
    async def run() -> None:
        uow, team_id = await _setup_roster([])
        async with uow as u:
            team = await u.session.get(m.Team, team_id)
            team.ht_team_id = 537758
            await u.session.commit()

        chpp = FakeTransfersHistoryCHPP()
        handler = SyncTeamHandler(uow, chpp)
        result = await handler.execute_transfers_history(
            SyncTransfersHistoryCommand(user_id=1, team_id=team_id, ht_team_id=537758)
        )
        assert result.status == "completed"
        assert result.errors == []
        assert result.pages_fetched == 2
        assert result.transfers_seen == 3
        assert result.transfers_new == 3
        assert chpp.calls == [1, 2]

        async with uow as u:
            bought = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == 555)
            )
            assert bought.first_name == "Foo"
            assert bought.last_name == "Barbaz"
            assert bought.purchase_price == 100000
            assert bought.tsi_at_purchase == 500

            sold = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == 666)
            )
            assert sold.last_name == "Quux"
            assert sold.sale_price == 200000
            assert sold.buyer_team_id == 999

            old = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == 777)
            )
            assert old.purchase_price == 50000

            team = await u.session.get(m.Team, team_id)
            assert team.transfer_total_buys == 150000
            assert team.transfer_number_buys == 2
            assert team.last_transfer_id_seen == 300

    asyncio.run(run())


def test_transfers_history_backfill_stops_early_once_re_run() -> None:
    """Segunda vez: la marca de agua (`last_transfer_id_seen`) ya está en
    300 — la página 1 completa ya es "conocida", así que ni siquiera debe
    pedirse la página 2 (pedido explícitamente: "no debe hacer fetch en
    todo de nuevo sino en lo que pueda o no faltarle").

    Desde 2026-08-21 hace falta además `transfers_history_complete`: una marca
    suelta ya no basta, porque podría venir de un recorrido que se cortó."""
    async def run() -> None:
        uow, team_id = await _setup_roster([])
        async with uow as u:
            team = await u.session.get(m.Team, team_id)
            team.ht_team_id = 537758
            team.last_transfer_id_seen = 300
            team.transfers_history_complete = True
            # Sellado con las reglas de hoy: si no, se relee entero a
            # proposito (ver `VERSION_DEL_LIBRO`).
            team.transfers_import_version = VERSION_DEL_LIBRO
            # Desde 2026-08-22 la marca solo vale si el libro de movimientos
            # está lleno: sin él no hay etapas que reconstruir, y el recorrido
            # se rehace aunque la marca diga que estaba completo.
            u.session.add(m.TeamTransfer(
                team_id=team_id, ht_transfer_id=300, ht_player_id=1,
                player_name="Ya", deadline=datetime(2026, 1, 1), price=1, is_buy=True,
            ))
            await u.session.commit()

        chpp = FakeTransfersHistoryCHPP()
        handler = SyncTeamHandler(uow, chpp)
        result = await handler.execute_transfers_history(
            SyncTransfersHistoryCommand(user_id=1, team_id=team_id, ht_team_id=537758)
        )
        assert result.status == "completed"
        assert result.pages_fetched == 1
        assert result.transfers_new == 0
        assert chpp.calls == [1]

        async with uow as u:
            # Ningún jugador de la página 1 (ya "conocida") se crea de nuevo.
            missing = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == 555)
            )
            assert missing is None

    asyncio.run(run())


# ── Contador de intentos de venta (currentbids.xml) ─────────────────────────

async def _setup_roster(ht_player_ids: list[int]) -> tuple[SqlAlchemyUnitOfWork, int]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as s:
        team = m.Team(ht_team_id=537758, name="Pulgas Arrechas")
        s.add(team)
        await s.flush()
        team_id = team.id
        for i, pid in enumerate(ht_player_ids):
            s.add(m.Player(
                ht_player_id=pid, team_id=team_id,
                first_name=f"Jugador{i}", last_name="Prueba",
            ))
        await s.commit()

    return SqlAlchemyUnitOfWork(factory), team_id


def _foto_en_venta(
    player_id: int, sync_id: int, cuando: datetime | None = None
) -> "m.PlayerSnapshot":
    """La foto que deja el paso de plantilla: en venta, segun players.xml."""
    return m.PlayerSnapshot(
        sync_id=sync_id, player_id=player_id,
        captured_at=cuando or datetime(2026, 8, 24, 11),
        age_years=25, age_days=0, tsi=1000, form=5, stamina=7,
        experience=5, salary=1000, is_transfer_listed=True,
        content_hash=b"x" * 32,
    )


def test_a_new_appearance_on_the_market_opens_one_attempt() -> None:
    """Quién está en venta lo dice players.xml (`TransferListed`), no
    `currentbids.xml` — pedido explícitamente el 2026-08-22: ese fichero es la
    lista de PUJAS, y tomarlo por un censo de transferibles es la forma de
    equivocarse. Aquí solo enriquece: plazo y puja más alta.

    Una aparición nueva abre un intento; seguir listado no abre otro.
    """
    async def run() -> None:
        uow, team_id = await _setup_roster([111, 222])
        handler = SyncTeamHandler(uow, chpp=None)  # type: ignore[arg-type]

        async with uow as u:
            # Lo que haría el sync de plantilla antes de llegar aquí.
            jugador = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == 111)
            )
            jugador.currently_listed = True
            # `_persist_currentbids` refresca la marca desde la ULTIMA foto
            # antes de decidir nada (2026-08-24), asi que la foto tiene que
            # existir: es lo que el paso de plantilla habria escrito.
            sync = m.Sync(user_id=1, team_id=team_id, kind="players",
                          status="completed", started_at=datetime(2026, 8, 24, 11))
            u.session.add(sync)
            await u.session.flush()
            u.session.add(_foto_en_venta(jugador.id, sync_id=sync.id))
            await u.session.commit()

        async with uow as u:
            payload = {"listed_players": [{"ht_player_id": 111}]}
            await handler._persist_currentbids(
                u, team_id, payload, datetime(2026, 8, 24, 12), _fresh_result()
            )
            await u.commit()

        async with uow as u:
            player = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == 111)
            )
            assert player.listing_count == 1
            otro = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == 222)
            )
            assert otro.listing_count == 0
            intentos = list((await u.session.execute(
                select(m.PlayerListingAttempt)
                .where(m.PlayerListingAttempt.player_id == player.id)
            )).scalars())
            assert len(intentos) == 1
            assert intentos[0].ended_at is None

        # Sigue listado: no se abre un segundo intento.
        async with uow as u:
            payload = {"listed_players": [{"ht_player_id": 111}]}
            await handler._persist_currentbids(
                u, team_id, payload, datetime(2026, 8, 24, 12), _fresh_result()
            )
            await u.commit()

        async with uow as u:
            player = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == 111)
            )
            assert player.listing_count == 1
            intentos = list((await u.session.execute(
                select(m.PlayerListingAttempt)
                .where(m.PlayerListingAttempt.player_id == player.id)
            )).scalars())
            assert len(intentos) == 1

    asyncio.run(run())


def test_the_bids_file_only_enriches_the_open_attempt() -> None:
    """La puja más alta y el plazo sí salen de `currentbids.xml`: para eso
    está. Lo que no puede hacer es decidir quién está en venta."""
    async def run() -> None:
        uow, team_id = await _setup_roster([111])
        handler = SyncTeamHandler(uow, chpp=None)  # type: ignore[arg-type]

        async with uow as u:
            jugador = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == 111)
            )
            jugador.currently_listed = True
            # `_persist_currentbids` refresca la marca desde la ULTIMA foto
            # antes de decidir nada (2026-08-24), asi que la foto tiene que
            # existir: es lo que el paso de plantilla habria escrito.
            sync = m.Sync(user_id=1, team_id=team_id, kind="players",
                          status="completed", started_at=datetime(2026, 8, 24, 11))
            u.session.add(sync)
            await u.session.flush()
            u.session.add(_foto_en_venta(jugador.id, sync_id=sync.id))
            await u.session.commit()

        async with uow as u:
            payload = {
                "listed_players": [
                    {"ht_player_id": 111, "highest_bid": 1500000,
                     "deadline": "2026-08-26 09:00:00"},
                ]
            }
            await handler._persist_currentbids(
                u, team_id, payload, datetime(2026, 8, 24, 12), _fresh_result()
            )
            await u.commit()

        async with uow as u:
            intento = await u.session.scalar(select(m.PlayerListingAttempt))
            assert intento.highest_bid == 1500000
            assert intento.deadline is not None

    asyncio.run(run())

def _fresh_result():
    from app.application.commands.sync_team import SyncResult

    return SyncResult(sync_id=0, status="completed")


# ── Motor de dominio: compute_balance ───────────────────────────────────────
# Validado fila a fila contra la hoja de cálculo REAL del usuario ("Compra vs
# Venta"), no solo contra números inventados — si esto pasa, el motor
# reproduce exactamente lo que el usuario ya viene calculando a mano.

def test_agent_commission_matches_the_official_hattrick_table() -> None:
    assert agent_commission_pct(0) == pytest.approx(0.12)
    assert agent_commission_pct(6) == pytest.approx(0.0883)
    assert agent_commission_pct(112) == pytest.approx(0.02)
    assert agent_commission_pct(2159) == pytest.approx(0.02)  # suelo, no sigue bajando


def test_agent_commission_interpolates_daily_between_weekly_breakpoints() -> None:
    """Hattrick publica un valor por SEMANA a partir del día 7 — los días
    intermedios se interpolan linealmente. Verificado contra la columna
    "Porc_2" de la hoja real del usuario: día 8 = 0,08467142857."""
    assert agent_commission_pct(8) == pytest.approx(0.08467142857, abs=1e-6)


def test_compute_balance_matches_real_spreadsheet_row_a_quintana() -> None:
    """Fila real "A. Quintana" de la hoja del usuario: comprado en
    4.162.000, salario plano 3.090/semana, 78 semanas de posesión, 1
    intento de venta, vendido en 8.000.000. Su hoja calcula
    Ganancia = 3.032.890, con % de agente = 0.07 (tabla, en el suelo de
    2% a 78 semanas, + 5% siempre — ALWAYS_CHARGED_PCT). Se consideró
    sumar también un 2% de derechos de formación (real en Hattrick), pero
    el usuario pidió explícitamente replicar su hoja tal cual — se deja
    fuera a propósito."""
    purchased_at = datetime(2020, 9, 30, tzinfo=UTC)
    sold_at = purchased_at + timedelta(weeks=78)
    record = PlayerTransferRecord(
        purchase_price=4162000,
        purchased_at=purchased_at,
        is_academy_graduate=False,
        salary_history=[SalarySnapshot(captured_at=purchased_at, salary=3090)],
        listing_count=1,
        sale_price=8000000,
        sold_at=sold_at,
    )
    balance = compute_balance(record)
    assert balance.agent_pct == pytest.approx(0.07)
    assert balance.saldo == 3032890


def test_compute_balance_never_uses_a_hypothetical_valuation_for_unsold_players() -> None:
    """Un jugador que sigue en la plantilla no vendido: el saldo refleja
    solo el gasto acumulado hasta ahora, nunca una valoración de mercado
    estimada como si fuera una venta real."""
    purchased_at = datetime(2026, 1, 1, tzinfo=UTC)
    as_of = purchased_at + timedelta(weeks=10)
    record = PlayerTransferRecord(
        purchase_price=1000000,
        purchased_at=purchased_at,
        is_academy_graduate=False,
        salary_history=[SalarySnapshot(captured_at=purchased_at, salary=5000)],
        listing_count=0,
        sale_price=None,
        sold_at=None,
        as_of=as_of,
    )
    balance = compute_balance(record)
    assert balance.is_sold is False
    assert balance.net_sale_proceeds == 0
    # 11 semanas de sueldo (10 + la extra de la compra), sin venta que compense.
    assert balance.saldo == -1000000 - 5000 * 11


def test_compute_balance_is_none_when_purchase_price_is_truly_unknown() -> None:
    """Sin precio de compra (ni real ni manual) y sin ser canterano: el
    saldo es None, nunca 0 ni una cifra inventada."""
    record = PlayerTransferRecord(
        purchase_price=None, purchased_at=None, is_academy_graduate=False,
        salary_history=[], listing_count=0, sale_price=None, sold_at=None,
    )
    balance = compute_balance(record)
    assert balance.saldo is None


def test_compute_balance_treats_academy_graduates_as_zero_cost_purchase() -> None:
    """Canterano: precio de compra 0, y agente fijo al 5% (no la tabla por
    días), tal como confirmó el usuario."""
    purchased_at = datetime(2025, 1, 1, tzinfo=UTC)
    sold_at = purchased_at + timedelta(weeks=5)
    record = PlayerTransferRecord(
        purchase_price=None, purchased_at=purchased_at, is_academy_graduate=True,
        salary_history=[SalarySnapshot(captured_at=purchased_at, salary=1000)],
        listing_count=1, sale_price=500000, sold_at=sold_at,
    )
    balance = compute_balance(record)
    assert balance.purchase_price == 0
    assert balance.agent_pct == pytest.approx(0.05)
    assert balance.saldo is not None


def test_salary_extrapolates_across_sync_gaps() -> None:
    """El salario solo tiene un snapshot al principio y otro a mitad de
    camino (como pasa cuando no cambia entre syncs, per Q5) — el motor
    debe usar el último valor conocido para las semanas sin dato propio,
    nunca interpolar ni inventar un promedio."""
    purchased_at = datetime(2026, 1, 1, tzinfo=UTC)
    sold_at = purchased_at + timedelta(weeks=4)
    record = PlayerTransferRecord(
        purchase_price=100000, purchased_at=purchased_at, is_academy_graduate=False,
        salary_history=[
            SalarySnapshot(captured_at=purchased_at, salary=1000),
            SalarySnapshot(captured_at=purchased_at + timedelta(weeks=2), salary=1500),
        ],
        listing_count=0, sale_price=None, sold_at=sold_at,
    )
    balance = compute_balance(record)
    # semanas 0,1 = 1000 (último conocido); semanas 2,3,4 = 1500 → 5 semanas
    assert balance.salary_total == 1000 * 2 + 1500 * 3


# ── Servicio de consulta: end-to-end contra datos reales sincronizados ──────

def test_player_balance_query_service_computes_saldo_for_a_sold_player() -> None:
    """`seeded_session()` sincroniza la plantilla REAL de la cuenta
    (players.xml, con historial de salario real) con `currency_rate=10.0`
    (Colombia). Se marca a mano UNA compra/venta (transfersteam.xml no
    forma parte de este seed) sobre un jugador real, con los importes tal
    como los devuelve CHPP de verdad — en la moneda BASE del juego, no en
    la local — y se comprueba que el servicio de consulta los convierte
    dividiendo por la tasa antes de calcular el saldo (confirmado por el
    usuario 2026-08-03: p.ej. compró a Humberto Granada en US$1000 real,
    pero CHPP devuelve 10000). No repite la validación numérica exacta del
    resto de la fórmula, que ya cubre `compute_balance` directamente."""
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            player = await s.scalar(
                select(m.Player).where(m.Player.team_id == team_id).limit(1)
            )
            # `seeded_session()` deja el snapshot fechado "ahora" — hay que
            # moverlo antes de la venta simulada, o el nuevo chequeo de
            # "volvió a la plantilla" (2026-08-05) lo confundiría con un
            # jugador vendido que ya regresó.
            snap = await s.scalar(
                select(m.PlayerSnapshot)
                .where(m.PlayerSnapshot.player_id == player.id)
                .order_by(m.PlayerSnapshot.captured_at)
            )
            snap.captured_at = datetime(2026, 1, 1, tzinfo=UTC)
            player.purchase_price = 5000000  # CHPP crudo → US$500.000 reales
            player.purchased_at = datetime(2026, 1, 1, tzinfo=UTC)
            player.sale_price = 9000000  # CHPP crudo → US$900.000 reales
            player.sold_at = datetime(2026, 3, 1, tzinfo=UTC)
            player.listing_count = 1
            ht_player_id = player.ht_player_id
            await s.commit()

        async with factory() as s:
            return await PlayerBalanceQueryService(s).get(team_id), ht_player_id

    data, ht_player_id = asyncio.run(go())
    assert data is not None
    assert len(data.players) > 1  # el resto de la plantilla real también aparece
    row = next(r for r in data.players if r.ht_player_id == ht_player_id)
    assert row.is_sold is True
    assert row.purchase_price == 500000
    assert row.sale_price == 900000
    assert row.saldo is not None
    # El resto de la plantilla, sin compra conocida, debe quedar en None —
    # nunca 0 ni una cifra inventada — y contar en unknown_purchase_count.
    others = [r for r in data.players if r.ht_player_id != ht_player_id]
    assert all(r.saldo is None for r in others)
    assert data.unknown_purchase_count == len(others)


def test_a_returning_player_shows_one_row_per_stint() -> None:
    """Caso real (Humberto Granada, 461351045): vendido en 2022 y de vuelta en
    2026. Hasta 2026-08-22 la app tenía una sola fila por jugador, así que
    tenía que ADIVINAR si "sigue en la plantilla" mirando si había snapshots
    posteriores a la venta, y la fila mezclaba la compra nueva con la venta
    vieja.

    Con una fila por etapa la ambigüedad desaparece: la etapa cerrada está
    vendida y la abierta está en curso, cada una con su propio saldo."""
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            player = await s.scalar(
                select(m.Player).where(m.Player.team_id == team_id).limit(1)
            )
            s.add_all([
                m.PlayerStint(
                    player_id=player.id, ht_player_id=player.ht_player_id,
                    team_id=team_id, arrived_at=datetime(2021, 1, 1),
                    arrival_price=1000000, arrival_transfer_id=1,
                    left_at=datetime(2022, 1, 1), sale_price=9000000,
                    sale_transfer_id=2,
                ),
                m.PlayerStint(
                    player_id=player.id, ht_player_id=player.ht_player_id,
                    team_id=team_id, arrived_at=datetime(2026, 1, 1),
                    arrival_price=2000000, arrival_transfer_id=3,
                ),
            ])
            ht_player_id = player.ht_player_id
            await s.commit()

        async with factory() as s:
            return await PlayerBalanceQueryService(s).get(team_id), ht_player_id

    data, ht_player_id = asyncio.run(go())
    assert data is not None
    filas = [r for r in data.players if r.ht_player_id == ht_player_id]
    assert len(filas) == 2, "una fila por etapa"

    vendida = next(r for r in filas if r.is_sold)
    abierta = next(r for r in filas if not r.is_sold)
    assert vendida.sale_price == 900000      # 9.000.000 en moneda base
    assert abierta.sale_price is None
    assert abierta.sold_at is None
    # Y ninguna dice haberse vendido antes de comprarse.
    assert vendida.purchased_at < vendida.sold_at

def test_player_balance_query_service_flags_academy_graduate_by_mother_club() -> None:
    """Pedido explícitamente 2026-08-04: "canterano" real =
    `MotherClub/TeamID` igual al `ht_team_id` de este equipo — NO si el
    jugador pasó por el escaneo de cantera (`YouthPlayer`/
    `FormerYouthPlayer`) de esta app. Un jugador nunca visto por ese
    escaneo (el caso normal del backfill histórico de transferencias) debe
    quedar igual marcado como canterano si su `mother_club_team_id`
    coincide — y uno con precio de compra real, aunque comparta esa
    coincidencia por azar, NO debe confundirse con uno sin ningún dato de
    cantera."""
    async def go():
        uow, team_id = await _setup_roster([111, 222])
        async with uow as u:
            team = await u.session.get(m.Team, team_id)
            team.ht_team_id = 537758

            graduate = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == 111)
            )
            graduate.mother_club_team_id = 537758  # coincide con el club
            graduate.sale_price = 1000000
            graduate.sold_at = datetime(2026, 1, 1)
            graduate.listing_count = 1

            bought = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == 222)
            )
            bought.mother_club_team_id = 999999  # otro club — no es canterano
            bought.purchase_price = 500000
            bought.purchased_at = datetime(2025, 1, 1)
            bought.sale_price = 1000000
            bought.sold_at = datetime(2026, 1, 1)
            bought.listing_count = 1
            await u.session.commit()

        async with uow as u:
            return await PlayerBalanceQueryService(u.session).get(team_id)

    data = asyncio.run(go())
    assert data is not None
    graduate_row = next(r for r in data.players if r.ht_player_id == 111)
    bought_row = next(r for r in data.players if r.ht_player_id == 222)
    assert graduate_row.is_academy_graduate is True
    assert bought_row.is_academy_graduate is False
    # Canterano real: su "precio de compra" es lo que costó ascenderlo, no 0
    # (2026-08-19). Nunca None ni un precio de mercado inventado.
    assert graduate_row.purchase_price == graduate_row.promotion_cost
    assert graduate_row.promotion_cost > 0
    assert bought_row.promotion_cost == 0
    assert graduate_row.saldo is not None


def test_bid_hour_bucket_formats_as_12_hour_ranges() -> None:
    """Pedido explícitamente 2026-08-03: "14-16" no dice nada de un
    vistazo — formato de 12 horas, un solo sufijo am/pm cuando ambos
    extremos caen en el mismo periodo, los dos cuando cruza mediodía o
    medianoche."""
    cases = [
        (datetime(2026, 1, 1, 0, 30), "12:00 a 2:00 a.m."),
        (datetime(2026, 1, 1, 10, 0), "10:00 a.m. a 12:00 p.m."),   # cruza mediodía
        (datetime(2026, 1, 1, 15, 30), "2:00 a 4:00 p.m."),
        (datetime(2026, 1, 1, 22, 0), "10:00 p.m. a 12:00 a.m."),  # cruza medianoche
    ]
    for when, expected in cases:
        assert _bid_hour_bucket(when) == expected


def test_player_balance_query_service_breaks_down_saldo_by_season_age_and_top_skill() -> None:
    """Pedido explícitamente por el usuario 2026-08-03: desglosar el saldo
    también por Temporada, Edad y Habilidad más alta (sin Balón Parado) —
    igual que ya existía por Entrenamiento. Los tres usan el mismo criterio:
    el snapshot MÁS RECIENTE anterior o igual a `sold_at` (nunca uno
    posterior, que sería mirar al futuro). El jugador real de
    `seeded_session()` (Alberto Gutiérrez Caviedes) tiene, en su único
    snapshot sincronizado: age_years=30 (cubo "29–31") y scoring=18 como
    máximo entre las 6 habilidades de campo (set_pieces=9 se ignora a
    propósito, aunque no sea el máximo en este caso igualmente). También
    cubre "por hora de cierre de puja" (pedido 2026-08-03, bloques de 2h en
    formato de 12 horas): vendido a las 15:30 → cubo "2:00 a 4:00 p.m."."""
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            player = await s.scalar(
                select(m.Player).where(m.Player.team_id == team_id).limit(1)
            )
            snap = await s.scalar(
                select(m.PlayerSnapshot)
                .where(m.PlayerSnapshot.player_id == player.id)
                .order_by(m.PlayerSnapshot.captured_at)
            )
            # Forzamos el snapshot a una fecha ANTERIOR a la venta simulada
            # abajo — si quedara posterior (como al sincronizarlo "ahora"),
            # season_at/snapshot_at lo descartarían por ser del futuro
            # respecto a la venta, que es exactamente el comportamiento
            # correcto que ya prueban los otros tests de este archivo.
            snap.captured_at = datetime(2026, 1, 1)

            # `seeded_session()` sincroniza worlddetails (temporada 84,
            # semana 3, Colombia — LeagueID 19). La venta se fija una hora
            # DESPUÉS del sync, reproduciendo el bug real de Comolli: la
            # fórmula antigua veía un timedelta negativo, floor-dividía a
            # -1 e inventaba la temporada 85. La regla semanal canónica debe
            # mantenerla en la misma semana y temporada.
            world = await s.scalar(select(m.WorldContext))
            world.refreshed_at = datetime(2026, 3, 1, 14, 30)
            team = await s.get(m.Team, team_id)
            team.ht_league_id = world.ht_league_id

            player.purchase_price = 5000000
            player.purchased_at = datetime(2026, 1, 1)
            player.sale_price = 9000000
            player.sold_at = datetime(2026, 3, 1, 15, 30)
            player.listing_count = 1
            await s.commit()

        async with factory() as s:
            return await PlayerBalanceQueryService(s).get(team_id)

    data = asyncio.run(go())
    assert data is not None
    assert data.by_season == {"Temporada 84": pytest.approx(data.total_saldo)}
    assert data.by_age_bucket == {"29–31": pytest.approx(data.total_saldo)}
    assert data.by_top_skill == {"Anotación": pytest.approx(data.total_saldo)}
    assert data.by_bid_hour == {"2:00 a 4:00 p.m.": pytest.approx(data.total_saldo)}


def test_player_balance_query_service_labels_season_as_unknown_before_any_worlddetails_sync() -> None:
    """Sin `worlddetails.xml` sincronizado nunca, una venta no tiene forma
    honesta de saber en qué temporada cayó — se etiqueta "Temporada
    desconocida" en vez de inventar un número. `seeded_session()` sí lo
    sincroniza por defecto (hace falta para la fórmula de entrenamiento), así
    que este test borra esa fila para simular una cuenta que nunca lo trajo."""
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            await s.execute(delete(m.WorldContext))
            player = await s.scalar(
                select(m.Player).where(m.Player.team_id == team_id).limit(1)
            )
            snap = await s.scalar(
                select(m.PlayerSnapshot)
                .where(m.PlayerSnapshot.player_id == player.id)
                .order_by(m.PlayerSnapshot.captured_at)
            )
            snap.captured_at = datetime(2026, 1, 1)
            player.purchase_price = 5000000
            player.purchased_at = datetime(2026, 1, 1)
            player.sale_price = 9000000
            player.sold_at = datetime(2026, 3, 1)
            player.listing_count = 1
            await s.commit()

        async with factory() as s:
            return await PlayerBalanceQueryService(s).get(team_id)

    data = asyncio.run(go())
    assert data is not None
    assert data.by_season == {"Temporada desconocida": pytest.approx(data.total_saldo)}


def test_player_balance_query_service_computes_season_by_elapsed_days_like_age() -> None:
    """Pedido explícitamente por el usuario 2026-08-04: "el cálculo se parece
    a la edad, es Temporada = Temporada Actual - (Hoy-Fecha_transferencia)/112"
    — aritmética pura, no depende de tener un `Standing` sincronizado cerca
    de esa fecha. Una venta exactamente 112 días antes de la última
    sincronización de worlddetails.xml (temporada 84) cae en la temporada
    83, por vieja que sea — a diferencia del `Standing`-based `season_at`
    anterior, que la habría dejado en un único cubo "temporada anterior"
    sin distinguir cuántas temporadas atrás."""
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            player = await s.scalar(
                select(m.Player).where(m.Player.team_id == team_id).limit(1)
            )
            snap = await s.scalar(
                select(m.PlayerSnapshot)
                .where(m.PlayerSnapshot.player_id == player.id)
                .order_by(m.PlayerSnapshot.captured_at)
            )
            snap.captured_at = datetime(2025, 1, 1)
            world = await s.scalar(select(m.WorldContext))
            world.season = 84
            world.refreshed_at = datetime(2026, 6, 1)
            team = await s.get(m.Team, team_id)
            team.ht_league_id = world.ht_league_id
            player.purchase_price = 5000000
            player.purchased_at = datetime(2025, 1, 1)
            player.sale_price = 9000000
            player.sold_at = datetime(2026, 6, 1) - timedelta(days=112)
            player.listing_count = 1
            await s.commit()

        async with factory() as s:
            return await PlayerBalanceQueryService(s).get(team_id)

    data = asyncio.run(go())
    assert data is not None
    assert data.by_season == {"Temporada 83": pytest.approx(data.total_saldo)}


def test_player_balance_query_service_filters_by_season() -> None:
    """Pedido explícitamente 2026-08-04: "Solo falta un filtro general de
    temporadas" — con dos jugadores vendidos en temporadas distintas,
    pedir `season="Temporada 83"` deja SOLO ese jugador en "Detalle" y en
    los desgloses no-temporada (entrenamiento aquí), sin tocar el otro.
    Sin filtro (`season=None`), ambos aparecen."""
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            world = await s.scalar(select(m.WorldContext))
            world.season = 84
            world.refreshed_at = datetime(2026, 6, 1)
            team = await s.get(m.Team, team_id)
            team.ht_league_id = world.ht_league_id

            older = await s.scalar(
                select(m.Player).where(m.Player.team_id == team_id).limit(1)
            )
            older_snap = await s.scalar(
                select(m.PlayerSnapshot)
                .where(m.PlayerSnapshot.player_id == older.id)
                .order_by(m.PlayerSnapshot.captured_at)
            )
            older_snap.captured_at = datetime(2025, 1, 1)
            older.purchase_price = 1000000
            older.purchased_at = datetime(2025, 1, 1)
            older.sale_price = 2000000
            # 112 días antes de refreshed_at -> una temporada atrás (83).
            older.sold_at = datetime(2026, 6, 1) - timedelta(days=112)
            older.listing_count = 1

            newer = m.Player(
                ht_player_id=900000555, team_id=team_id,
                first_name="Nuevo", last_name="Jugador",
                purchase_price=1000000, purchased_at=datetime(2026, 5, 1),
                sale_price=2000000, sold_at=datetime(2026, 6, 1),
                listing_count=1,
            )
            s.add(newer)
            await s.commit()

        async with factory() as s:
            unfiltered = await PlayerBalanceQueryService(s).get(team_id)
        async with factory() as s:
            filtered = await PlayerBalanceQueryService(s).get(team_id, season="Temporada 83")
        return unfiltered, filtered

    unfiltered, filtered = asyncio.run(go())
    assert unfiltered is not None and filtered is not None

    assert {r.name for r in unfiltered.players if r.is_sold} == {
        "Alberto Gutiérrez Caviedes", "Nuevo Jugador",
    }
    assert set(unfiltered.by_season) == {"Temporada 83", "Temporada 84"}

    assert {r.name for r in filtered.players if r.is_sold} == {"Alberto Gutiérrez Caviedes"}
    assert set(filtered.by_season) == {"Temporada 83"}
    # KPI de "Resumen" (transfer_total_*) NUNCA se recortan por temporada —
    # son el agregado de TODA la historia que entrega transfersteam.xml.
    assert filtered.transfer_number_buys == unfiltered.transfer_number_buys
    assert filtered.transfer_total_buys == unfiltered.transfer_total_buys


def test_player_balance_query_service_falls_back_to_backfilled_age_at_sale() -> None:
    """Pedido explícitamente por el usuario 2026-08-04: sin un
    `player_snapshots` de antes de la venta, si `age_years_at_sale` ya fue
    reconstruido (ver `execute_player_enrichment_backfill`), se usa ese valor en
    vez de caer directo en "Edad desconocida"."""
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            player = await s.scalar(
                select(m.Player).where(m.Player.team_id == team_id).limit(1)
            )
            # Venta ANTES de cualquier snapshot real sincronizado (que
            # `seeded_session()` deja fechado "ahora") — sin backfill,
            # `snapshot_at` no encontraría nada. Se borra ese snapshot en
            # vez de solo adelantarlo: este test quiere CERO snapshots
            # relevantes (para forzar el fallback al backfill), no uno
            # movido antes de la venta — que sí sería "relevante" y además
            # dispararía el nuevo chequeo de "volvió a la plantilla"
            # (2026-08-05) al quedar antes de esta venta tan vieja.
            await s.execute(delete(m.PlayerSnapshot).where(m.PlayerSnapshot.player_id == player.id))
            player.purchase_price = 5000000
            player.purchased_at = datetime(2020, 1, 1)
            player.sale_price = 9000000
            player.sold_at = datetime(2020, 3, 1)
            player.listing_count = 1
            player.age_years_at_sale = 19
            player.age_days_at_sale = 50
            await s.commit()

        async with factory() as s:
            return await PlayerBalanceQueryService(s).get(team_id)

    data = asyncio.run(go())
    assert data is not None
    assert data.by_age_bucket == {"19–21": pytest.approx(data.total_saldo)}


def test_player_balance_query_service_handles_a_team_with_no_players() -> None:
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            await s.execute(m.Player.__table__.delete().where(m.Player.team_id == team_id))
            await s.commit()
        async with factory() as s:
            return await PlayerBalanceQueryService(s).get(team_id)

    data = asyncio.run(go())
    assert data is not None
    assert data.players == []
    assert data.total_saldo == 0.0


def test_the_week_of_a_transfer_drops_the_season() -> None:
    """2026-08-19, pedido explícito: las cascadas de Transferencias agrupan por
    la SEMANA de la temporada, no por la temporada.

    Una venta de 83-05 y otra de 81-05 son la misma columna, la 05: la
    pregunta que responde el gráfico es en qué semana del calendario conviene
    comprar o vender, y para eso la temporada sobra.
    """
    from app.application.queries.weekly import season_week_for_datetime

    class _Mundo:
        season = 83
        match_round = 5
        refreshed_at = datetime(2026, 8, 16, tzinfo=UTC)

    etiqueta = season_week_for_datetime(_Mundo(), datetime(2026, 8, 16, tzinfo=UTC))
    assert etiqueta is not None and "-" in etiqueta
    semana = int(etiqueta.split("-")[1])
    # Dos temporadas distintas, misma semana: misma columna.
    hace_dos_temporadas = datetime(2026, 8, 16, tzinfo=UTC) - timedelta(days=112 * 2)
    otra = season_week_for_datetime(_Mundo(), hace_dos_temporadas)
    assert otra is not None
    assert int(otra.split("-")[1]) == semana
    assert otra.split("-")[0] != etiqueta.split("-")[0]


def test_promoting_a_youth_costs_money_and_it_lands_in_his_balance() -> None:
    """2026-08-19, aportado por el usuario: ascender a un canterano cuesta
    20.000 en la moneda base del juego.

    CHPP no publica ese cargo por ninguna parte (las nueve partidas de gasto de
    `economy.xml` no lo incluyen), así que el número es del juego y vive
    declarado en el motor. Hasta ahora un canterano entraba con coste 0 y su
    saldo salía inflado por ese importe.
    """
    from app.domain.engines.player_balance import (
        YOUTH_PROMOTION_COST,
        PlayerTransferRecord,
        compute_balance,
    )

    def canterano(coste: int) -> float | None:
        return compute_balance(
            PlayerTransferRecord(
                purchase_price=None,
                purchased_at=datetime(2026, 1, 1, tzinfo=UTC),
                is_academy_graduate=True,
                promotion_cost=coste,
                salary_history=[],
                listing_count=0,
                sale_price=1_000_000,
                sold_at=datetime(2026, 6, 1, tzinfo=UTC),
            )
        ).saldo

    assert YOUTH_PROMOTION_COST == 20_000
    con_coste = canterano(2_000)
    gratis = canterano(0)
    assert gratis is not None and con_coste is not None
    # La diferencia es exactamente lo que cuesta el ascenso, ni más ni menos.
    assert gratis - con_coste == 2_000


def test_a_failed_first_history_run_does_not_mark_the_past_as_already_seen() -> None:
    """2026-08-21, con la app publicada: un usuario estrenando la herramienta
    veía Transferencias vacía salvo una operación reciente, y volver a pulsar
    el botón no arreglaba nada.

    Su primer recorrido se cortó a la mitad, pero la marca de agua se guardaba
    igual, apuntando a lo más reciente. Desde entonces cada intento leía la
    primera página, reconocía esa marca y concluía que ya estaba al día: el
    hueco de temporadas anteriores no se rellenaba nunca.
    """
    async def run() -> None:
        uow, team_id = await _setup_roster([])
        async with uow as u:
            team = await u.session.get(m.Team, team_id)
            team.ht_team_id = 537758
            await u.session.commit()

        class CHPPQueSeCaeEnLaSegundaPagina(FakeTransfersHistoryCHPP):
            async def fetch(self, file: str, version: str = "latest", **params: object):
                if params.get("pageIndex") == 2:
                    raise RuntimeError("Hattrick se cayó a mitad del recorrido")
                return await super().fetch(file, version, **params)

        handler = SyncTeamHandler(uow, CHPPQueSeCaeEnLaSegundaPagina())
        roto = await handler.execute_transfers_history(
            SyncTransfersHistoryCommand(user_id=1, team_id=team_id, ht_team_id=537758)
        )
        assert roto.status == "partial"

        async with uow as u:
            team = await u.session.get(m.Team, team_id)
            assert team.transfers_history_complete is False
            # Lo importante: no puede quedar diciendo que ya vio la historia.
            assert team.last_transfer_id_seen is None

        # Y al siguiente intento, con Hattrick sano, se recorre entera.
        sano = SyncTeamHandler(uow, FakeTransfersHistoryCHPP())
        segundo = await sano.execute_transfers_history(
            SyncTransfersHistoryCommand(user_id=1, team_id=team_id, ht_team_id=537758)
        )
        assert segundo.status == "completed"
        assert segundo.pages_fetched == 2
        assert segundo.transfers_new == 3

        async with uow as u:
            team = await u.session.get(m.Team, team_id)
            assert team.transfers_history_complete is True
            assert team.last_transfer_id_seen == 300

    asyncio.run(run())


def test_the_watermark_is_only_trusted_once_the_history_is_known_to_be_whole() -> None:
    """Una marca de agua heredada de un recorrido incompleto no debe frenar
    nada: es justo el estado en el que quedaron los primeros usuarios."""
    async def run() -> None:
        uow, team_id = await _setup_roster([])
        async with uow as u:
            team = await u.session.get(m.Team, team_id)
            team.ht_team_id = 537758
            # Marca envenenada: apunta al final, pero nunca se recorrió todo.
            team.last_transfer_id_seen = 300
            team.transfers_history_complete = False
            await u.session.commit()

        chpp = FakeTransfersHistoryCHPP()
        result = await SyncTeamHandler(uow, chpp).execute_transfers_history(
            SyncTransfersHistoryCommand(user_id=1, team_id=team_id, ht_team_id=537758)
        )
        # Se ignora la marca y se recorre la historia entera.
        assert result.pages_fetched == 2
        assert result.transfers_new == 3

        async with uow as u:
            team = await u.session.get(m.Team, team_id)
            assert team.transfers_history_complete is True

    asyncio.run(run())


def test_a_player_who_came_and_went_between_syncs_still_costs_his_salary() -> None:
    """2026-08-21, caso real (Horst Angel): comprado el 08 y vendido el 20, y
    la primera sincronización de la cuenta fue una hora después de que se
    fuera. No dejó ni un snapshot, así que su coste de salarios salía 0 y su
    saldo aparecía mejor de lo que fue.

    `playerdetails.xml` sí devuelve `<Salary>` de un jugador que ya juega en
    otro club — verificado en vivo —, así que el dato existe: no hay nada que
    estimar, solo que guardarlo (`last_known_salary`).
    """
    from app.domain.engines.player_balance import (
        PlayerTransferRecord,
        compute_balance,
    )

    comprado = datetime(2026, 8, 8, 12, 48)
    vendido = datetime(2026, 8, 20, 12, 40)

    sin_nada = compute_balance(PlayerTransferRecord(
        purchase_price=512000, salary_history=[], listing_count=0,
        sale_price=712000, purchased_at=comprado, sold_at=vendido,
        is_academy_graduate=False,
    ))
    assert sin_nada.salary_total == 0
    assert sin_nada.salary_known is False

    con_salario = compute_balance(PlayerTransferRecord(
        purchase_price=512000, salary_history=[], listing_count=0,
        sale_price=712000, purchased_at=comprado, sold_at=vendido,
        is_academy_graduate=False, fallback_salary=4740,
    ))
    # 12 días son 1 semana cumplida, y el primer sueldo se paga entero: 2.
    assert con_salario.salary_total == 4740 * 2
    assert con_salario.salary_known is True
    # Y el saldo empeora justo en lo que costaba tenerlo.
    assert con_salario.saldo == sin_nada.saldo - 4740 * 2


def test_real_snapshots_always_win_over_the_last_known_salary() -> None:
    """El respaldo es para cuando no hay nada. Si hay historial de verdad, se
    usa ese: es lo que cobró cada semana, medido."""
    from app.domain.engines.player_balance import (
        PlayerTransferRecord,
        SalarySnapshot,
        compute_balance,
    )

    comprado = datetime(2026, 8, 8, 12, 48)
    r = compute_balance(PlayerTransferRecord(
        purchase_price=512000,
        salary_history=[SalarySnapshot(captured_at=comprado, salary=1000)],
        listing_count=0, sale_price=712000, purchased_at=comprado,
        sold_at=datetime(2026, 8, 20, 12, 40),
        is_academy_graduate=False, fallback_salary=99999,
    ))
    assert r.salary_total == 2000


def test_players_known_only_from_the_transfer_history_stop_counting_as_squad() -> None:
    """2026-08-21, medido en producción: el equipo tenía 479 jugadores
    "activos" donde debía tener 24.

    `left_team_at` lo pone el sync cuando alguien DESAPARECE de players.xml.
    Los cientos de jugadores que crea el historial de transferencias nunca
    aparecieron ahí, así que nunca desaparecían y se quedaban contados como
    plantilla. Cada sincronización normal pedía entonces su ficha y su
    entrenamiento: ~950 llamadas a Hattrick que en un plan gratuito no
    terminan nunca, y por eso ningún relleno del pasado avanzaba.
    """
    async def run() -> None:
        uow, team_id = await _setup_roster([])
        async with uow as u:
            team = await u.session.get(m.Team, team_id)
            team.ht_team_id = 537758
            await u.session.commit()

        handler = SyncTeamHandler(uow, FakeTransfersHistoryCHPP())
        await handler.execute_transfers_history(
            SyncTransfersHistoryCommand(user_id=1, team_id=team_id, ht_team_id=537758)
        )

        async with uow as u:
            vendidos = (await u.session.execute(
                select(m.Player).where(
                    m.Player.team_id == team_id, m.Player.sold_at.is_not(None)
                )
            )).scalars().all()
            assert vendidos, "el fixture tiene al menos una venta"
            for p in vendidos:
                assert p.left_team_at is not None, f"{p.last_name} sigue contando como plantilla"
                assert p.left_team_at == p.sold_at

            activos = (await u.session.execute(
                select(m.Player).where(
                    m.Player.team_id == team_id, m.Player.left_team_at.is_(None)
                )
            )).scalars().all()
            # Los comprados y nunca vendidos sí siguen siendo plantilla.
            assert all(p.sold_at is None for p in activos)

    asyncio.run(run())


def test_a_re_signed_player_is_not_marked_as_gone() -> None:
    """Si volvió a fichar por el club, sus lecturas posteriores a la venta lo
    demuestran y no se le puede dar por ido."""
    async def run() -> None:
        uow, team_id = await _setup_roster([])
        async with uow as u:
            team = await u.session.get(m.Team, team_id)
            team.ht_team_id = 537758
            await u.session.commit()

        handler = SyncTeamHandler(uow, FakeTransfersHistoryCHPP())
        await handler.execute_transfers_history(
            SyncTransfersHistoryCommand(user_id=1, team_id=team_id, ht_team_id=537758)
        )

        async with uow as u:
            vendido = (await u.session.execute(
                select(m.Player).where(
                    m.Player.team_id == team_id, m.Player.sold_at.is_not(None)
                )
            )).scalars().first()
            # Vuelve al club: una lectura posterior a la venta.
            vendido.left_team_at = None
            sync = m.Sync(
                user_id=1, team_id=team_id, kind="players", status="completed",
                started_at=vendido.sold_at + timedelta(days=1),
            )
            u.session.add(sync)
            await u.session.flush()
            u.session.add(m.PlayerSnapshot(
                sync_id=sync.id, player_id=vendido.id,
                captured_at=vendido.sold_at + timedelta(days=1),
                age_years=25, age_days=0, tsi=1000, form=5, stamina=5,
                experience=5, salary=1000, content_hash=b"x",
            ))
            await u.session.commit()

        async with uow as u:
            await handler._marcar_salidas_de_vendidos(u, team_id)
            await u.session.commit()

        async with uow as u:
            de_nuevo = await u.session.get(m.Player, vendido.id)
            assert de_nuevo.left_team_at is None
    asyncio.run(run())


def test_the_backfill_goes_in_batches_until_there_is_nothing_left() -> None:
    """2026-08-21, por reportes de usuarios: en la copia publicada quedaban 60
    precios y 416 nacionalidades sin resolver y no avanzaban nunca, porque el
    intento se hacía entero dentro de la sincronización normal y se cortaba
    por tiempo antes de terminar.

    Troceado, cada pulsación termina lo que empieza. Lo que se protege aquí es
    que el trabajo SE AGOTA: que pulsar repetidamente llega a cero y que una
    pulsación de más no vuelve a pedirle nada a Hattrick. Sin eso el bucle de
    la pantalla no pararía nunca — pasó de verdad, con la barra marcando
    "55 de 11".
    """
    async def run() -> None:
        uow, chpp, team_id, _ = await _setup_with_player(468921494)
        async with uow as u:
            team = await u.session.get(m.Team, team_id)
            team.ht_team_id = 537758
            await u.session.commit()

        handler = SyncTeamHandler(uow, chpp)
        # Una pulsación = una pasada. La vigilancia de reventas no se agota
        # sola (un ex-jugador sin vender sigue pudiendo dar dinero mañana), así
        # que el corte lo marca el momento en que se pulsó.
        pulsacion = datetime.now(UTC).replace(tzinfo=None)

        # 2026-08-25: la primera vuelta ya NO recorre el historial. TUS
        # compras y TUS ventas las trae "Sincronizar ahora"; este boton es
        # solo para la vigilancia de comisiones de reventa.
        vueltas = 0
        lote = await handler.execute_backfill_batch(
            SyncBackfillBatchCommand(
                user_id=1, team_id=team_id, limite=1, revisar_desde=pulsacion,
            )
        )
        assert lote.pages_fetched == 0, "el libro no es cosa de este boton"
        assert lote.players_done == 1

        while lote.players_pending > 0 and vueltas < 50:
            vueltas += 1
            lote = await handler.execute_backfill_batch(
                SyncBackfillBatchCommand(
                    user_id=1, team_id=team_id, limite=1, revisar_desde=pulsacion,
                )
            )
        assert lote.players_pending == 0, "el trabajo se agota"

        # Y una vuelta más deja la cuenta en cero otra vez, sin volver a
        # recorrer el historial: eso se hizo una vez y no se repite.
        sobrante = await handler.execute_backfill_batch(
            SyncBackfillBatchCommand(
                user_id=1, team_id=team_id, limite=40, revisar_desde=pulsacion,
            )
        )
        assert sobrante.players_pending == 0
        assert sobrante.pages_fetched == 0

    asyncio.run(run())


def test_a_whole_press_leaves_a_single_sync_row() -> None:
    """Con un jugador por petición, crear una fila de sincronización en cada
    lote llenaba el histórico de cientos de entradas vacías que no cuentan
    nada. El instante del clic, que ya viaja para acotar la vigilancia,
    identifica la pulsación: una fila, no una por jugador."""
    async def run() -> None:
        uow, chpp, team_id, _ = await _setup_with_player(468921494)
        async with uow as u:
            team = await u.session.get(m.Team, team_id)
            team.ht_team_id = 537758
            await u.session.commit()

        handler = SyncTeamHandler(uow, chpp)
        pulsacion = datetime.now(UTC).replace(tzinfo=None)
        for _ in range(4):
            await handler.execute_backfill_batch(SyncBackfillBatchCommand(
                user_id=1, team_id=team_id, limite=1, revisar_desde=pulsacion,
            ))

        async with uow as u:
            filas = (await u.session.execute(
                select(m.Sync).where(
                    m.Sync.team_id == team_id, m.Sync.kind == "backfill_batch"
                )
            )).scalars().all()
            assert len(filas) == 1, f"{len(filas)} filas para una sola pulsación"

        # Otra pulsación, otra fila: el histórico distingue las dos sesiones.
        await handler.execute_backfill_batch(SyncBackfillBatchCommand(
            user_id=1, team_id=team_id, limite=1,
            revisar_desde=datetime.now(UTC).replace(tzinfo=None),
        ))
        async with uow as u:
            filas = (await u.session.execute(
                select(m.Sync).where(
                    m.Sync.team_id == team_id, m.Sync.kind == "backfill_batch"
                )
            )).scalars().all()
            assert len(filas) == 2

    asyncio.run(run())


def test_a_player_who_comes_back_gets_a_second_stint() -> None:
    """2026-08-22, caso real de la base del usuario (Humberto Granada): la
    compra y la venta vivían encima de la fila del jugador, así que volver al
    club pisaba la etapa anterior y salía una fila imposible, "comprado el
    01/08/2026, vendido el 17/07/2022".

    Cada paso por el club es su propio registro, y se derivan del libro de
    transferencias: una compra abre etapa y la venta siguiente la cierra.
    """
    async def run() -> None:
        uow, team_id = await _setup_roster([])
        async with uow as u:
            team = await u.session.get(m.Team, team_id)
            team.ht_team_id = 537758
            u.session.add(m.Player(
                ht_player_id=777, team_id=team_id, first_name="Ida", last_name="Vuelta",
            ))
            await u.session.commit()

        def mov(tid: int, compra: bool, cuando: datetime, precio: int) -> m.TeamTransfer:
            return m.TeamTransfer(
                team_id=team_id, ht_transfer_id=tid, ht_player_id=777,
                player_name="Ida Vuelta", deadline=cuando, price=precio,
                is_buy=compra, counterpart_team_id=999,
            )

        async with uow as u:
            u.session.add_all([
                mov(1, True, datetime(2020, 1, 1), 100000),
                mov(2, False, datetime(2020, 6, 1), 150000),
                mov(3, True, datetime(2024, 1, 1), 300000),
                mov(4, False, datetime(2024, 9, 1), 500000),
            ])
            await u.session.commit()

        handler = SyncTeamHandler(uow, None)  # type: ignore[arg-type]
        async with uow as u:
            assert await handler._reconstruir_etapas(u, team_id) == 2
            await u.commit()

        async with uow as u:
            etapas = (await u.session.execute(
                select(m.PlayerStint)
                .where(m.PlayerStint.ht_player_id == 777)
                .order_by(m.PlayerStint.arrived_at)
            )).scalars().all()
            assert len(etapas) == 2
            assert etapas[0].arrival_price == 100000
            assert etapas[0].sale_price == 150000
            assert etapas[1].arrival_price == 300000
            assert etapas[1].sale_price == 500000
            # Y ninguna dice haberse vendido antes de comprarse.
            for e in etapas:
                assert e.arrived_at < e.left_at

    asyncio.run(run())


def test_a_sale_without_a_purchase_is_an_academy_stint() -> None:
    """A un canterano no se le compra, así que su etapa no tiene compra
    delante. Abrirle etapa igual es lo que permite calcular su saldo y sus
    comisiones futuras."""
    async def run() -> None:
        uow, team_id = await _setup_roster([])
        async with uow as u:
            team = await u.session.get(m.Team, team_id)
            team.ht_team_id = 537758
            u.session.add(m.Player(
                ht_player_id=888, team_id=team_id, first_name="De", last_name="Cantera",
            ))
            u.session.add(m.TeamTransfer(
                team_id=team_id, ht_transfer_id=9, ht_player_id=888,
                player_name="De Cantera", deadline=datetime(2022, 2, 25),
                price=40000, is_buy=False, counterpart_team_id=1337055,
            ))
            await u.session.commit()

        handler = SyncTeamHandler(uow, None)  # type: ignore[arg-type]
        async with uow as u:
            await handler._reconstruir_etapas(u, team_id)
            await u.commit()

        async with uow as u:
            etapa = await u.session.scalar(
                select(m.PlayerStint).where(m.PlayerStint.ht_player_id == 888)
            )
            assert etapa.from_academy is True
            assert etapa.arrived_at is None, "no se inventa una fecha de llegada"
            assert etapa.sale_price == 40000
            assert etapa.buyer_team_id == 1337055

    asyncio.run(run())


def test_rebuilding_stints_keeps_what_cannot_be_recalculated() -> None:
    """Las etapas se derivan, así que se rehacen enteras. Lo que NO se puede
    derivar —los partidos ya censados, lo atribuido a mano, lo excluido— tiene
    que sobrevivir a la reconstrucción, o cada recorrido del historial borraría
    el trabajo del usuario."""
    async def run() -> None:
        uow, team_id = await _setup_roster([])
        async with uow as u:
            team = await u.session.get(m.Team, team_id)
            team.ht_team_id = 537758
            u.session.add(m.Player(
                ht_player_id=555, team_id=team_id, first_name="Con", last_name="Notas",
            ))
            u.session.add_all([
                m.TeamTransfer(
                    team_id=team_id, ht_transfer_id=11, ht_player_id=555,
                    player_name="Con Notas", deadline=datetime(2021, 1, 1),
                    price=1000, is_buy=True,
                ),
                m.TeamTransfer(
                    team_id=team_id, ht_transfer_id=12, ht_player_id=555,
                    player_name="Con Notas", deadline=datetime(2021, 5, 1),
                    price=2000, is_buy=False,
                ),
            ])
            await u.session.commit()

        handler = SyncTeamHandler(uow, None)  # type: ignore[arg-type]
        async with uow as u:
            await handler._reconstruir_etapas(u, team_id)
            await u.commit()
        async with uow as u:
            etapa = await u.session.scalar(
                select(m.PlayerStint).where(m.PlayerStint.ht_player_id == 555)
            )
            etapa.games_played_for_us = 7
            etapa.excluded = True
            etapa.top_skill_manual = "scoring"
            await u.session.commit()

        async with uow as u:
            await handler._reconstruir_etapas(u, team_id)
            await u.commit()

        async with uow as u:
            etapa = await u.session.scalar(
                select(m.PlayerStint).where(m.PlayerStint.ht_player_id == 555)
            )
            assert etapa.games_played_for_us == 7
            assert etapa.excluded is True
            assert etapa.top_skill_manual == "scoring"

    asyncio.run(run())
