"""Los sectores de la serie para la flor del Dashboard (2026-09-13).

La regla que se vigila: la media sale de los ÚLTIMOS CINCO partidos OFICIALES
de cada equipo --los tuyos de tus partidos, los de los rivales de los que se
guardan--, y defensa y ataque son la suma de sus tres sectores (HatStats).
"""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.application.queries.flor_de_fuerza import sectores_de_la_serie
from app.infrastructure.db import models as m
from tests.conftest import HT_TEAM_ID, seeded_session

SERIE = 34162
RIVAL = 2512155
BASE = datetime(2026, 8, 1, tzinfo=UTC)


def _run(coro):
    return asyncio.run(coro)


def test_media_de_los_ultimos_cinco_oficiales_de_cada_equipo() -> None:
    async def run() -> None:
        factory, team_id = await seeded_session()
        async with factory() as s:
            sync = await s.scalar(select(m.Sync.id).limit(1))
            for ht_id, nombre, puesto in (
                (HT_TEAM_ID, "Pulgas Arrechas", 1),
                (RIVAL, "LosNeithas F.C", 2),
            ):
                s.add(
                    m.Standing(
                        sync_id=sync,
                        series_ht_id=SERIE,
                        season=83,
                        match_round=8,
                        captured_at=BASE,
                        team_ht_id=ht_id,
                        team_name=nombre,
                        position=puesto,
                        played=8,
                        won=0,
                        draws=0,
                        lost=0,
                        goals_for=0,
                        goals_against=0,
                        points=0,
                    )
                )
            # Seis oficiales tuyos: el más viejo (medio 1) no debe entrar. Y un
            # amistoso reciente (medio 99) tampoco.
            for i, medio in enumerate([1, 10, 12, 14, 16, 18]):
                s.add(
                    m.Match(
                        ht_match_id=700_000 + i,
                        played_at=BASE + timedelta(days=7 * i),
                        match_type=1,
                        status="FINISHED",
                        home_team_ht_id=HT_TEAM_ID,
                        away_team_ht_id=RIVAL,
                        home_team_name="Pulgas Arrechas",
                        away_team_name="LosNeithas F.C",
                        home_goals=1,
                        away_goals=0,
                    )
                )
                s.add(
                    m.MatchRating(
                        ht_match_id=700_000 + i,
                        team_ht_id=HT_TEAM_ID,
                        is_home=True,
                        midfield=medio,
                        left_def=10,
                        central_def=20,
                        right_def=30,
                        left_att=1,
                        central_att=2,
                        right_att=3,
                    )
                )
            s.add(
                m.Match(
                    ht_match_id=799_999,
                    played_at=BASE + timedelta(days=60),
                    match_type=4,
                    status="FINISHED",
                    home_team_ht_id=HT_TEAM_ID,
                    away_team_ht_id=1,
                    home_team_name="Pulgas Arrechas",
                    away_team_name="Amistoso",
                    home_goals=1,
                    away_goals=0,
                )
            )
            s.add(
                m.MatchRating(
                    ht_match_id=799_999,
                    team_ht_id=HT_TEAM_ID,
                    is_home=True,
                    midfield=99,
                    left_def=99,
                    central_def=99,
                    right_def=99,
                    left_att=99,
                    central_att=99,
                    right_att=99,
                )
            )
            for i, medio in enumerate([8, 9]):
                s.add(
                    m.RivalMatch(
                        team_ht_id=RIVAL,
                        ht_match_id=710_000 + i,
                        match_type=1,
                        played_at=BASE + timedelta(days=7 * i),
                        home_team_ht_id=RIVAL,
                        away_team_ht_id=3,
                        home_team_name="LosNeithas F.C",
                        away_team_name="Otro",
                        home_goals=0,
                        away_goals=0,
                        captured_at=BASE,
                        midfield=medio,
                        left_def=5,
                        central_def=5,
                        right_def=5,
                        left_att=4,
                        central_att=4,
                        right_att=4,
                    )
                )
            await s.commit()

        async with factory() as s:
            team = await s.get(m.Team, team_id)
            filas = {f.ht_team_id: f for f in await sectores_de_la_serie(s, team)}

        mia, suya = filas[HT_TEAM_ID], filas[RIVAL]
        assert mia.es_propio and not suya.es_propio
        assert mia.partidos == 5
        assert mia.medio == 14.0  # (10+12+14+16+18)/5: ni el viejo ni el amistoso
        assert mia.defensa == 60.0 and mia.ataque == 6.0
        assert suya.partidos == 2
        assert suya.medio == 8.5 and suya.defensa == 15.0 and suya.ataque == 12.0

    _run(run())


def test_sin_clasificacion_no_hay_serie() -> None:
    async def run() -> None:
        factory, team_id = await seeded_session()
        async with factory() as s:
            team = await s.get(m.Team, team_id)
            assert await sectores_de_la_serie(s, team) == []

    _run(run())
