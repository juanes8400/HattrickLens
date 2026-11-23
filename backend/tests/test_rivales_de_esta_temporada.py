"""Los rivales vigilados de tu serie son los de ESTA temporada.

2026-11-23: los fichajes de rivales y la precarga de sus partidos tomaban
cualquier equipo que hubiera salido alguna vez en una tabla de tu serie. Al
quedarte en ella, los que ascendieron o descendieron seguían vigilados.
"""

import asyncio
from datetime import UTC, datetime

from app.application.commands.sync_team.comun import equipos_de_tu_serie
from app.infrastructure.db import models as m
from tests.conftest import HT_TEAM_ID, seeded_session

SERIE, OTRA = 33334, 34162
ANTES = datetime(2026, 7, 20, tzinfo=UTC)
AHORA = datetime(2026, 11, 22, tzinfo=UTC)
SE_QUEDAN = [600001, 600002]
SE_FUERON = [600003, 600004]
LLEGARON = [700001, 700002]


def _fila(sync_id: int, serie: int, temporada: int, jornada: int, cuando: datetime, ht_id: int):
    return m.Standing(
        sync_id=sync_id, series_ht_id=serie, season=temporada, match_round=jornada,
        captured_at=cuando, team_ht_id=ht_id, team_name=str(ht_id), position=1,
        played=jornada, won=0, draws=0, lost=0, goals_for=0, goals_against=0, points=0,
    )  # fmt: skip


async def _serie_con_dos_temporadas() -> set[int]:
    factory, _team_id = await seeded_session()
    async with factory() as s:
        sync = m.Sync(
            user_id=1, team_id=_team_id, kind="manual", status="completed", started_at=AHORA
        )
        s.add(sync)
        await s.flush()
        for ht_id in [HT_TEAM_ID, *SE_QUEDAN, *SE_FUERON]:
            s.add(_fila(sync.id, SERIE, 83, 14, ANTES, ht_id))
        for ht_id in [HT_TEAM_ID, *SE_QUEDAN, *LLEGARON]:
            s.add(_fila(sync.id, SERIE, 84, 0, AHORA.replace(day=9), ht_id))
            s.add(_fila(sync.id, SERIE, 84, 2, AHORA, ht_id))
        # Otra serie que no es la tuya no entra nunca.
        s.add(_fila(sync.id, OTRA, 84, 2, AHORA, 900001))
        await s.commit()
        return await equipos_de_tu_serie(s, HT_TEAM_ID)


def test_solo_los_de_tu_tabla_actual() -> None:
    assert asyncio.run(_serie_con_dos_temporadas()) == {*SE_QUEDAN, *LLEGARON}


def test_sin_clasificacion_no_hay_a_quien_vigilar() -> None:
    async def go() -> set[int]:
        factory, _ = await seeded_session()
        async with factory() as s:
            return await equipos_de_tu_serie(s, HT_TEAM_ID)

    assert asyncio.run(go()) == set()
