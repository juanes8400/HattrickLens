"""El Historial de la serie con un equipo reemplazado a mitad de temporada.

2026-09-14, visto en vivo: Kivaré reemplazó a etbenianos1 después de la
jornada 7 con otro id. Las jornadas 1-7 --partidos y fotos de la clasificación--
quedaron con el id viejo y la 8 con el nuevo. El historial sólo contaba los
partidos de equipos de la clasificación de hoy, así que tiraba todos los del
viejo: las jornadas anteriores salían incompletas y la última sin los puntos
ganados contra él (Pulgas con 19 en vez de 22, LosNeithas BAJANDO de 17 a 16).

Aquí, una liga de cuatro: «Viejo» juega las jornadas 1 y 2 y «Nuevo» la 3.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from app.application.queries.league import LeagueQueryService
from app.infrastructure.db import models as m
from tests.conftest import HT_TEAM_ID, seeded_session

SERIE = 7777
BASE = datetime(2026, 8, 1, tzinfo=UTC)
A, B, VIEJO, NUEVO = 600001, 600002, 600009, 600099
NOMBRES = {HT_TEAM_ID: "Pulgas Arrechas", A: "Uno", B: "Dos", VIEJO: "Viejo", NUEVO: "Nuevo"}


def test_el_historial_une_al_equipo_viejo_con_el_que_lo_reemplazo() -> None:
    async def run() -> None:
        factory, team_id = await seeded_session()
        async with factory() as s:
            sync = m.Sync(
                user_id=1, team_id=team_id, kind="manual", status="completed", started_at=BASE
            )
            s.add(sync)
            await s.flush()

            def foto(ronda: int, filas: list[tuple[int, int, int]]) -> None:
                for puesto, (ht_id, pj, pts) in enumerate(filas, start=1):
                    s.add(
                        m.Standing(
                            sync_id=sync.id,
                            series_ht_id=SERIE,
                            season=83,
                            match_round=ronda,
                            captured_at=BASE + timedelta(days=7 * ronda),
                            team_ht_id=ht_id,
                            team_name=NOMBRES[ht_id],
                            position=puesto,
                            played=pj,
                            won=0,
                            draws=0,
                            lost=0,
                            goals_for=0,
                            goals_against=0,
                            points=pts,
                        )
                    )

            # La foto de la jornada 2, todavía con el viejo; la de la 3, con el nuevo.
            foto(2, [(HT_TEAM_ID, 2, 6), (A, 2, 3), (B, 2, 1), (VIEJO, 2, 1)])
            foto(3, [(HT_TEAM_ID, 3, 7), (NUEVO, 3, 4), (A, 3, 3), (B, 3, 2)])

            partidos = [
                (1, HT_TEAM_ID, A, 1, 0),
                (1, B, VIEJO, 0, 0),
                (2, HT_TEAM_ID, VIEJO, 2, 0),
                (2, A, B, 1, 0),
                (3, HT_TEAM_ID, B, 1, 1),
                (3, NUEVO, A, 3, 0),
                (4, HT_TEAM_ID, NUEVO, -1, -1),
                (4, A, B, -1, -1),
            ]
            for i, (ronda, local, visita, gl, gv) in enumerate(partidos):
                s.add(
                    m.Match(
                        ht_match_id=900_000 + i,
                        played_at=BASE + timedelta(days=7 * ronda),
                        match_type=1,
                        status="finished" if gl >= 0 else "upcoming",
                        home_team_ht_id=local,
                        away_team_ht_id=visita,
                        home_team_name=NOMBRES[local],
                        away_team_name=NOMBRES[visita],
                        home_goals=gl,
                        away_goals=gv,
                        series_ht_id=SERIE,
                        match_round=ronda,
                    )
                )
            await s.commit()

        async with factory() as s:
            liga = await LeagueQueryService(s).get(team_id, runs=1000)

        assert liga is not None
        assert liga.history.rounds == [0, 1, 2, 3]
        puntos = {t.name: t.points for t in liga.history.teams}
        assert set(puntos) == {"Pulgas Arrechas", "Uno", "Dos", "Nuevo"}
        # El nuevo hereda la línea entera del viejo, con su nombre de hoy.
        assert puntos["Nuevo"] == [0, 1, 1, 4]
        # Y los puntos ganados contra el viejo siguen contando.
        assert puntos["Pulgas Arrechas"] == [0, 3, 6, 7]
        assert puntos["Dos"] == [0, 1, 1, 2]
        assert puntos["Uno"] == [0, 0, 3, 3]
        for serie in puntos.values():
            assert serie == sorted(serie), "los puntos acumulados no pueden bajar"

    asyncio.run(run())
