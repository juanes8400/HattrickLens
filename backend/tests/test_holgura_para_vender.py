"""Partidos con el club y veces en venta, desde que llegó.

2026-11-23, pedido del usuario: Hattrick no deja poner en venta a un jugador
más veces que partidos ha jugado. Jugadores y la ficha enseñan los dos números
y la holgura, para saber quién puede venderse cuando haga falta.
"""

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from app.application.queries.squad import SquadQueryService, veces_en_venta_en_el_club
from app.infrastructure.chpp.parsers import parse_players
from app.infrastructure.db import models as m
from app.infrastructure.db.repositories import SqlAlchemyPlayerRepository
from tests.conftest import FIXTURES, seeded_session

CON_CUATRO = 490702763


def test_el_parser_lee_los_partidos_con_el_club() -> None:
    jugadores = parse_players((FIXTURES / "players.xml").read_bytes())["players"]
    assert (
        next(p for p in jugadores if p["ht_player_id"] == CON_CUATRO)["matches_current_team"] == 4
    )


def test_sin_el_dato_no_se_inventa_un_cero() -> None:
    # Hattrick no lo publica mientras hay un partido en juego.
    xml = (
        b"<?xml version='1.0'?><HattrickData><Team><PlayerList>"
        b"<Player><PlayerID>1</PlayerID></Player>"
        b"</PlayerList></Team></HattrickData>"
    )
    assert parse_players(xml)["players"][0]["matches_current_team"] is None


async def _plantilla_y_luego_un_partido_en_juego() -> tuple[int | None, int | None]:
    factory, team_id = await seeded_session()
    async with factory() as s:
        antes = await SquadQueryService(s).get(team_id)
        assert antes is not None
        con_cuatro = next(p for p in antes.players if p.ht_player_id == CON_CUATRO)

        jugador = await s.scalar(select(m.Player).where(m.Player.ht_player_id == CON_CUATRO))
        assert jugador is not None
        sync = m.Sync(
            user_id=1, team_id=team_id, kind="manual", status="completed",
            started_at=datetime(2030, 1, 1, tzinfo=UTC),
        )  # fmt: skip
        s.add(sync)
        await s.flush()
        await SqlAlchemyPlayerRepository(s).append_snapshot(
            sync.id,
            jugador.id,
            {
                "age_years": 30,
                "age_days": 1,
                "tsi": 1,
                "form": 5,
                "stamina": 5,
                "experience": 5,
                "salary": 1,
                "skills": {},
                "matches_current_team": None,
            },  # fmt: skip
            b"\x01" * 32,
            datetime(2030, 1, 1, tzinfo=UTC),
        )
        await s.commit()
        ultima = await s.scalar(
            select(m.PlayerSnapshot)
            .where(m.PlayerSnapshot.player_id == jugador.id)
            .order_by(m.PlayerSnapshot.captured_at.desc())
            .limit(1)
        )
        assert ultima is not None
        return con_cuatro.matches_with_club, ultima.matches_current_team


def test_la_plantilla_lo_sirve_y_un_partido_en_juego_no_lo_borra() -> None:
    en_plantilla, tras_el_partido_en_juego = asyncio.run(_plantilla_y_luego_un_partido_en_juego())
    assert en_plantilla == 4
    assert tras_el_partido_en_juego == 4


async def _veces_en_venta() -> dict[int, int]:
    factory, team_id = await seeded_session()
    async with factory() as s:
        jugadores = list((await s.execute(select(m.Player).limit(3))).scalars())
        una_vez, volvio, sin_pasos = jugadores
        una_vez.listing_count = 3
        volvio.listing_count = 5
        sin_pasos.listing_count = 2
        s.add(
            m.PlayerStint(
                player_id=una_vez.id, ht_player_id=una_vez.ht_player_id, team_id=team_id,
                arrived_at=datetime(2025, 1, 1),
            )
        )  # fmt: skip
        primero = m.PlayerStint(
            player_id=volvio.id, ht_player_id=volvio.ht_player_id, team_id=team_id,
            arrived_at=datetime(2024, 1, 1), left_at=datetime(2025, 1, 1),
        )  # fmt: skip
        ahora = m.PlayerStint(
            player_id=volvio.id, ht_player_id=volvio.ht_player_id, team_id=team_id,
            arrived_at=datetime(2026, 1, 1),
        )  # fmt: skip
        s.add_all([primero, ahora])
        await s.flush()
        for etapa in (primero, primero, ahora):
            s.add(
                m.PlayerListingAttempt(
                    player_id=volvio.id, ht_player_id=volvio.ht_player_id, stint_id=etapa.id,
                    detected_at=datetime(2026, 2, 1),
                )
            )  # fmt: skip
        await s.commit()
        veces = await veces_en_venta_en_el_club(s, [una_vez.id, volvio.id, sin_pasos.id])
        return {
            "una_vez": veces[una_vez.id],
            "volvio": veces[volvio.id],
            "sin_pasos": veces[sin_pasos.id],
        }


def test_las_veces_en_venta_son_las_de_su_paso_actual() -> None:
    veces = asyncio.run(_veces_en_venta())
    # Una sola etapa: el contador de siempre, que cuenta desde que llegó.
    assert veces["una_vez"] == 3
    # Se fue y volvió: sólo las de esta vez, no las cinco de toda su historia.
    assert veces["volvio"] == 1
    assert veces["sin_pasos"] == 2
