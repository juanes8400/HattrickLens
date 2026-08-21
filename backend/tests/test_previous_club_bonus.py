"""Comisión de club anterior EXACTA — HL-161, 2026-08-14.

Cubre, en orden: la tabla oficial de partidos → % (tramos, no
interpolación), qué tipos de partido cuentan, el criterio "jugó de
verdad" (RatingStars > 0), y el flujo completo por jugador
(`_check_previous_club_bonus`/`execute_previous_club_bonus`) contra una
cadena de transferencias sintética — sin depender de fixtures XML reales,
para poder ejercitar a propósito los casos límite (sin reventa todavía,
cadena rota, idempotencia). Termina con la integración en
`PlayerBalanceQueryService`, que reemplaza por completo el reparto
heurístico que vivía en `resale_bonus.py`.
"""
import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.sync_team import (
    SyncPreviousClubBonusCommand,
    SyncTeamHandler,
)
from app.application.queries.player_balance import PlayerBalanceQueryService
from app.domain.engines.previous_club_bonus import (
    counts_toward_games_played,
    did_play,
    previous_club_bonus_pct,
)
from app.infrastructure.db import models as m
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

OUR_HT_TEAM_ID = 537758
PLAYER_ID = 999001


# ── Tabla oficial: partidos → % ─────────────────────────────────────────────

def test_previous_club_bonus_pct_matches_the_official_table() -> None:
    assert previous_club_bonus_pct(0) == 0.0
    assert previous_club_bonus_pct(1) == pytest.approx(0.0025)
    assert previous_club_bonus_pct(2) == pytest.approx(0.005)
    assert previous_club_bonus_pct(3) == pytest.approx(0.01)
    assert previous_club_bonus_pct(4) == pytest.approx(0.015)
    assert previous_club_bonus_pct(5) == pytest.approx(0.02)
    assert previous_club_bonus_pct(7) == pytest.approx(0.025)
    assert previous_club_bonus_pct(10) == pytest.approx(0.03)
    assert previous_club_bonus_pct(20) == pytest.approx(0.035)
    assert previous_club_bonus_pct(40) == pytest.approx(0.04)


def test_previous_club_bonus_pct_holds_flat_between_thresholds() -> None:
    """8 partidos cae en el tramo "7 a 9" — 2,5%, no a medio camino entre
    2,5% y 3% (no se interpola, a diferencia de la tabla del agente)."""
    assert previous_club_bonus_pct(6) == pytest.approx(0.02)   # sigue en el tramo de 5
    assert previous_club_bonus_pct(8) == pytest.approx(0.025)  # tramo de 7
    assert previous_club_bonus_pct(9) == pytest.approx(0.025)
    assert previous_club_bonus_pct(19) == pytest.approx(0.03)  # tramo de 10


def test_previous_club_bonus_pct_caps_beyond_forty_games() -> None:
    assert previous_club_bonus_pct(41) == pytest.approx(0.04)
    assert previous_club_bonus_pct(200) == pytest.approx(0.04)


# ── Qué partidos cuentan ─────────────────────────────────────────────────────

def test_counts_toward_games_played_includes_league_cup_and_friendlies() -> None:
    """Confirmado explícitamente por el usuario 2026-08-14: liga, copa,
    promoción y amistosos SÍ cuentan."""
    assert counts_toward_games_played(1)   # liga
    assert counts_toward_games_played(2)   # promoción
    assert counts_toward_games_played(3)   # copa
    assert counts_toward_games_played(4)   # amistoso
    assert counts_toward_games_played(9)   # amistoso internacional (reglas de copa)


def test_counts_toward_games_played_excludes_tournaments_duels_ladders_preparation() -> None:
    assert not counts_toward_games_played(50)  # torneo: liga
    assert not counts_toward_games_played(51)  # torneo: playoff
    assert not counts_toward_games_played(61)  # duelo
    assert not counts_toward_games_played(62)  # escalera
    assert not counts_toward_games_played(80)  # preparación


def test_did_play_requires_a_nonzero_rating() -> None:
    """Un suplente no utilizado siempre trae RatingStars=0 exacto en
    matchlineup.xml v2.1 — verificado en vivo 2026-08-14."""
    assert not did_play(0)
    assert not did_play(0.0)
    assert did_play(0.1)
    assert did_play(5.5)


# ── Flujo completo por jugador, contra una cadena sintética de CHPP ─────────

class FakePreviousClubBonusCHPP:
    """Devuelve payloads ya parseados (mismo shape que los parsers reales)
    a mano, en vez de leer fixtures XML — permite ejercitar a propósito
    los casos límite (sin reventa, cadena rota) sin fabricar ficheros
    enteros para cada variante."""

    def __init__(
        self,
        transfers: list[dict[str, Any]],
        matches: list[dict[str, Any]],
        lineups: dict[int, list[dict[str, Any]]],
    ) -> None:
        self.transfers = transfers
        self.matches = matches
        self.lineups = lineups
        self.matchlineup_calls: list[int] = []

    async def fetch(self, file: str, version: str, **params: Any) -> dict[str, Any]:
        if file == "transfersplayer":
            return {"ht_player_id": PLAYER_ID, "player_name": "Test Player", "transfers": self.transfers}
        if file == "matchesarchive":
            return {"matches": self.matches}
        if file == "matchlineup":
            match_id = params["matchID"]
            self.matchlineup_calls.append(match_id)
            return {"ht_match_id": match_id, "ht_team_id": OUR_HT_TEAM_ID, "players": self.lineups.get(match_id, [])}
        raise AssertionError(f"unexpected file: {file}")


async def _setup(
    transfers: list[dict[str, Any]],
    matches: list[dict[str, Any]] | None = None,
    lineups: dict[int, list[dict[str, Any]]] | None = None,
    purchased_at: datetime = datetime(2025, 1, 1),
    sold_at: datetime = datetime(2026, 1, 1),
) -> tuple[SqlAlchemyUnitOfWork, FakePreviousClubBonusCHPP, int]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as s:
        team = m.Team(ht_team_id=OUR_HT_TEAM_ID, name="Pulgas Arrechas")
        s.add(team)
        await s.flush()
        team_id = team.id
        s.add(m.Player(
            ht_player_id=PLAYER_ID, team_id=team_id,
            first_name="Test", last_name="Player",
            purchased_at=purchased_at, sold_at=sold_at,
            sale_price=200000,
        ))
        await s.commit()

    chpp = FakePreviousClubBonusCHPP(transfers, matches or [], lineups or {})
    return SqlAlchemyUnitOfWork(factory), chpp, team_id


def _transfer(transfer_id: int, buyer: int, seller: int, price: int, deadline: str) -> dict[str, Any]:
    return {
        "ht_transfer_id": transfer_id, "buyer_team_id": buyer, "seller_team_id": seller,
        "price": price, "deadline": deadline, "tsi": 0,
    }


def _match(match_id: int, match_type: int) -> dict[str, Any]:
    return {"ht_match_id": match_id, "match_type": match_type}


def _lineup_entry(ht_player_id: int, rating_stars: float) -> dict[str, Any]:
    return {"ht_player_id": ht_player_id, "name": "Test Player", "rating_stars": rating_stars}


def test_finds_a_real_resale_and_computes_the_exact_commission() -> None:
    """Cadena: club X nos vendió → nosotros le vendimos al club 2 → el club
    2 acaba de revender al club 3. Somos "club anterior" de ESA última
    venta. 1 partido real jugado con nosotros (el otro es banca, el
    tercero es un torneo que no cuenta) → 0,25% × 500.000 = 1.250."""
    transfers = [
        _transfer(103, buyer=3, seller=2, price=500000, deadline="2026-08-10 10:00:00"),  # reventa
        _transfer(102, buyer=2, seller=OUR_HT_TEAM_ID, price=200000, deadline="2026-01-01 00:00:00"),  # nuestra venta
        _transfer(101, buyer=OUR_HT_TEAM_ID, seller=1, price=100000, deadline="2025-01-01 00:00:00"),  # nuestra compra
    ]
    matches = [_match(1, match_type=1), _match(2, match_type=4), _match(3, match_type=50)]
    lineups = {
        1: [_lineup_entry(PLAYER_ID, 5.0)],   # jugó
        2: [_lineup_entry(PLAYER_ID, 0.0)],   # banca, no jugó
        # partido 3 (torneo) nunca debería pedirse
    }

    async def run() -> None:
        uow, chpp, team_id = await _setup(transfers, matches, lineups)
        handler = SyncTeamHandler(uow, chpp)
        result = await handler.execute_previous_club_bonus(
            SyncPreviousClubBonusCommand(user_id=1, team_id=team_id, ht_player_id=PLAYER_ID)
        )
        assert result.status == "completed"
        assert result.snapshots_written == 1
        assert 3 not in chpp.matchlineup_calls  # el torneo nunca se pide

        async with uow as u:
            bonus = await u.session.scalar(select(m.PreviousClubBonus))
            assert bonus is not None
            assert bonus.resale_transfer_id == 103
            assert bonus.resale_price == 500000
            assert bonus.games_played_with_us == 1
            assert bonus.pct_applied == pytest.approx(0.0025)
            assert bonus.amount == 1250
            assert bonus.buyer_team_id == 3
            assert bonus.seller_team_id == 2

            player = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == PLAYER_ID)
            )
            assert player.ht_purchase_transfer_id == 101
            assert player.ht_sale_transfer_id == 102
            assert player.games_played_for_us == 1
            assert player.previous_club_bonus_checked_at is not None

    asyncio.run(run())


def test_running_twice_never_double_counts_the_same_resale() -> None:
    transfers = [
        _transfer(103, buyer=3, seller=2, price=500000, deadline="2026-08-10 10:00:00"),
        _transfer(102, buyer=2, seller=OUR_HT_TEAM_ID, price=200000, deadline="2026-01-01 00:00:00"),
        _transfer(101, buyer=OUR_HT_TEAM_ID, seller=1, price=100000, deadline="2025-01-01 00:00:00"),
    ]
    matches = [_match(1, match_type=1)]
    lineups = {1: [_lineup_entry(PLAYER_ID, 5.0)]}

    async def run() -> None:
        uow, chpp, team_id = await _setup(transfers, matches, lineups)
        handler = SyncTeamHandler(uow, chpp)
        cmd = SyncPreviousClubBonusCommand(user_id=1, team_id=team_id, ht_player_id=PLAYER_ID)
        first = await handler.execute_previous_club_bonus(cmd)
        second = await handler.execute_previous_club_bonus(cmd)
        assert first.snapshots_written == 1
        assert second.snapshots_written == 0
        assert second.unchanged == 1

        async with uow as u:
            count = len((await u.session.execute(select(m.PreviousClubBonus))).scalars().all())
            assert count == 1

    asyncio.run(run())


def test_our_sale_being_the_most_recent_transfer_means_no_resale_yet() -> None:
    """Nadie nos ha revendido todavía — nuestra venta es la más reciente
    en la lista (índice 0). No se calcula nada, no se llama a
    matchesarchive (sería una llamada CHPP desperdiciada)."""
    transfers = [
        _transfer(102, buyer=2, seller=OUR_HT_TEAM_ID, price=200000, deadline="2026-01-01 00:00:00"),
        _transfer(101, buyer=OUR_HT_TEAM_ID, seller=1, price=100000, deadline="2025-01-01 00:00:00"),
    ]

    async def run() -> None:
        uow, chpp, team_id = await _setup(transfers)
        handler = SyncTeamHandler(uow, chpp)
        result = await handler.execute_previous_club_bonus(
            SyncPreviousClubBonusCommand(user_id=1, team_id=team_id, ht_player_id=PLAYER_ID)
        )
        assert result.snapshots_written == 0
        assert result.unchanged == 1

        async with uow as u:
            assert (await u.session.scalar(select(m.PreviousClubBonus.id))) is None
            player = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == PLAYER_ID)
            )
            # Los TransferID de nuestro propio stint sí se rellenan de una vez.
            assert player.ht_purchase_transfer_id == 101
            assert player.ht_sale_transfer_id == 102

    asyncio.run(run())


def test_a_broken_chain_never_invents_a_commission() -> None:
    """Defensivo: la transacción inmediatamente anterior a nuestra venta
    en la lista no encaja con quien nos compró (no debería pasar en la
    práctica) — no se inventa una comisión sobre una cadena que no se
    puede confirmar."""
    transfers = [
        _transfer(103, buyer=3, seller=999, price=500000, deadline="2026-08-10 10:00:00"),  # seller no encaja
        _transfer(102, buyer=2, seller=OUR_HT_TEAM_ID, price=200000, deadline="2026-01-01 00:00:00"),
        _transfer(101, buyer=OUR_HT_TEAM_ID, seller=1, price=100000, deadline="2025-01-01 00:00:00"),
    ]

    async def run() -> None:
        uow, chpp, team_id = await _setup(transfers)
        handler = SyncTeamHandler(uow, chpp)
        result = await handler.execute_previous_club_bonus(
            SyncPreviousClubBonusCommand(user_id=1, team_id=team_id, ht_player_id=PLAYER_ID)
        )
        assert result.snapshots_written == 0
        async with uow as u:
            assert (await u.session.scalar(select(m.PreviousClubBonus.id))) is None

    asyncio.run(run())


# ── Integración: PlayerBalanceQueryService ──────────────────────────────────

def test_player_balance_uses_the_exact_bonus_sum_currency_converted() -> None:
    """El saldo/ROI de un jugador con una comisión exacta ya calculada
    debe reflejarla, convertida a moneda local — sin ningún reparto
    heurístico de por medio."""
    async def run() -> None:
        uow, _chpp, team_id = await _setup(transfers=[])
        async with uow as u:
            team = await u.session.get(m.Team, team_id)
            team.currency_rate = 10.0
            team.currency_name = "Col$"
            player = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == PLAYER_ID)
            )
            u.session.add(m.PreviousClubBonus(
                player_id=player.id, ht_player_id=PLAYER_ID,
                resale_transfer_id=103, resale_price=500000,
                resale_deadline=datetime(2026, 8, 10, tzinfo=UTC),
                buyer_team_id=3, seller_team_id=2,
                games_played_with_us=1, pct_applied=0.0025, amount=1250,
                computed_at=datetime.now(UTC),
            ))
            await u.session.commit()

        async with uow as u:
            data = await PlayerBalanceQueryService(u.session).get(team_id)
        assert data is not None
        row = next(r for r in data.players if r.ht_player_id == PLAYER_ID)
        assert row.resale_bonus_share == pytest.approx(125.0)  # 1250 / 10

    asyncio.run(run())


def test_player_balance_resale_share_is_zero_without_a_bonus_record() -> None:
    """Ningún jugador vendido tiene todavía una reventa detectada — 0.0,
    nunca una aproximación repartida entre candidatos."""
    async def run() -> None:
        uow, _chpp, team_id = await _setup(transfers=[])
        async with uow as u:
            data = await PlayerBalanceQueryService(u.session).get(team_id)
        assert data is not None
        row = next(r for r in data.players if r.ht_player_id == PLAYER_ID)
        assert row.resale_bonus_share == 0.0

    asyncio.run(run())


def test_an_ex_player_whose_commission_is_already_recorded_gets_closed() -> None:
    """Caso real (Adrian-Ioan Burlac): comisión guardada desde 2020 y el
    jugador seguía en la cola de vigilancia, para siempre. La comprobación de
    reventa contesta False cuando no escribe nada nuevo, así que el cierre no
    puede depender de su valor: depende de que EXISTA la fila de comisión.
    """
    async def run() -> None:
        # Sin reventa nueva que encontrar: solo nuestra propia venta.
        uow, chpp, team_id = await _setup(
            [_transfer(1, 999, OUR_HT_TEAM_ID, 200000, "2026-01-01 12:00:00")]
        )
        async with uow as u:
            jugador = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == PLAYER_ID)
            )
            u.session.add(m.PreviousClubBonus(
                player_id=jugador.id, ht_player_id=PLAYER_ID,
                resale_transfer_id=342838107, resale_price=7803000,
                resale_deadline=datetime(2026, 7, 12, 19, 16),
                buyer_team_id=1, seller_team_id=999,
                games_played_with_us=10, pct_applied=0.03, amount=234090,
                computed_at=datetime(2026, 7, 13),
            ))
            await u.session.commit()

        handler = SyncTeamHandler(uow, chpp)
        async with uow as u:
            await handler._vigilar_reventa(u, team_id, PLAYER_ID)
            await u.session.commit()

        async with uow as u:
            jugador = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == PLAYER_ID)
            )
            assert jugador.resale_closed is True
            assert jugador.resale_closed_reason == "revendido"

    asyncio.run(run())
