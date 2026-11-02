"""`leaguefixtures.xml` dice de qué temporada es cada partido, y se guarda.

2026-11-02. Una serie guarda los partidos de TODAS sus temporadas bajo el
mismo `series_ht_id`, y hasta hoy nada decía de cuál era cada uno: al ascender,
los catorce cruces del año pasado salían como «calendario completo» de la
temporada que todavía no ha empezado. El lector ya sacaba `<Season>` --«la
temporada a la que se refieren los datos»-- y el sincronizador la tiraba.
"""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

from sqlalchemy import select

from app.application.commands.sync_team import SyncTeamHandler
from app.application.commands.sync_team.comun import SyncResult
from app.infrastructure.chpp.parsers import parse_leaguefixtures
from app.infrastructure.db import models as m
from tests.conftest import seeded_session

SERIE = 34162


def _payload(temporada: int | None, ht_match_id: int, goles: tuple[int, int] | None):
    return {
        "series_ht_id": SERIE,
        "season": temporada,
        "matches": [
            {
                "ht_match_id": ht_match_id,
                "match_round": 3,
                "match_date": "2026-09-06 21:40:00",
                "home_team_id": 111,
                "home_team_name": "Uno",
                "away_team_id": 222,
                "away_team_name": "Dos",
                "home_goals": goles[0] if goles else None,
                "away_goals": goles[1] if goles else None,
            }
        ],
    }


async def _guardar(factory, payload) -> None:
    async with factory() as s:
        await SyncTeamHandler._persist_league_fixtures(
            None,  # type: ignore[arg-type]
            SimpleNamespace(session=s),  # type: ignore[arg-type]
            payload,
            SyncResult(sync_id=0, status="running"),
        )
        await s.commit()


def test_el_partido_nuevo_nace_con_su_temporada() -> None:
    async def run() -> None:
        factory, _ = await seeded_session()
        await _guardar(factory, _payload(83, 960_001, (2, 1)))
        async with factory() as s:
            fila = await s.scalar(select(m.Match).where(m.Match.ht_match_id == 960_001))
        assert fila is not None
        assert fila.series_season == 83

    asyncio.run(run())


def test_lo_guardado_sin_temporada_se_pone_al_dia() -> None:
    """La fila vieja no se queda sin etiqueta: el fichero trae el calendario
    entero de la temporada en curso en cada sync, así que el primero la
    rellena aunque la jornada y la serie ya cuadren."""

    async def run() -> None:
        factory, _ = await seeded_session()
        async with factory() as s:
            s.add(
                m.Match(
                    ht_match_id=960_002,
                    played_at=datetime(2026, 9, 6, tzinfo=UTC),
                    match_type=1,
                    status="FINISHED",
                    series_ht_id=SERIE,
                    match_round=3,
                    home_team_ht_id=111,
                    away_team_ht_id=222,
                    home_team_name="Uno",
                    away_team_name="Dos",
                    home_goals=2,
                    away_goals=1,
                )
            )
            await s.commit()
        await _guardar(factory, _payload(84, 960_002, (2, 1)))
        async with factory() as s:
            fila = await s.scalar(select(m.Match).where(m.Match.ht_match_id == 960_002))
        assert fila is not None
        assert fila.series_season == 84

    asyncio.run(run())


def test_sin_season_en_el_fichero_no_se_inventa() -> None:
    async def run() -> None:
        factory, _ = await seeded_session()
        await _guardar(factory, _payload(None, 960_003, None))
        async with factory() as s:
            fila = await s.scalar(select(m.Match).where(m.Match.ht_match_id == 960_003))
        assert fila is not None
        assert fila.series_season is None

    asyncio.run(run())


def test_el_lector_saca_la_temporada_del_fichero_de_verdad() -> None:
    with open("tests/fixtures/leaguefixtures.xml", "rb") as f:
        leido = parse_leaguefixtures(f.read())
    assert leido["season"] == 83
    assert leido["series_ht_id"] == SERIE
