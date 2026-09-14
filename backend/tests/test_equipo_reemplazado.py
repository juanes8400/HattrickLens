"""Un equipo reemplazado a mitad de temporada (etbenianos1 → Kivaré, 2026-09-13).

El sitio en la serie es el mismo y el id no: los partidos pendientes tienen que
pasar al equipo nuevo para que todas las pantallas lo encuentren, y los jugados
se quedan con el viejo, que fue quien los jugó.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.application.commands.sync_team import trasladar_equipo_reemplazado
from app.infrastructure.db import models as m
from tests.conftest import seeded_session

SERIE = 34162
BASE = datetime(2026, 9, 6, tzinfo=UTC)
VIEJO, NUEVO = 2688899, 3442324


def _partido(i: int, local: tuple[int, str], visita: tuple[int, str], goles: int) -> m.Match:
    return m.Match(
        ht_match_id=950_000 + i,
        played_at=BASE + timedelta(days=7 * i),
        match_type=1,
        status="finished" if goles >= 0 else "upcoming",
        home_team_ht_id=local[0],
        away_team_ht_id=visita[0],
        home_team_name=local[1],
        away_team_name=visita[1],
        home_goals=goles,
        away_goals=goles,
        series_ht_id=SERIE,
        match_round=8 + i,
    )


def test_los_pendientes_pasan_al_equipo_nuevo_y_los_jugados_no() -> None:
    async def run() -> None:
        factory, _ = await seeded_session()
        pulgas, viejo = (537758, "Pulgas Arrechas"), (VIEJO, "etbenianos1")
        cauca = (3271519, "Cauca CF")
        async with factory() as s:
            s.add(_partido(0, cauca, viejo, 1))  # jugado
            s.add(_partido(1, pulgas, viejo, -1))  # pendiente, visitante
            s.add(_partido(2, viejo, cauca, -1))  # pendiente, local
            await s.commit()
        equipos = [
            {"ht_team_id": 537758, "name": "Pulgas Arrechas"},
            {"ht_team_id": NUEVO, "name": "Kivaré"},
            {"ht_team_id": 3271519, "name": "Cauca CF"},
        ]
        async with factory() as s:
            assert await trasladar_equipo_reemplazado(s, SERIE, equipos) == 2
            await s.commit()
            # Una segunda pasada ya no encuentra nada que trasladar.
            assert await trasladar_equipo_reemplazado(s, SERIE, equipos) == 0
        async with factory() as s:
            filas = {
                mt.match_round: mt
                for mt in (
                    await s.execute(select(m.Match).where(m.Match.series_ht_id == SERIE))
                ).scalars()
            }
        assert filas[8].away_team_ht_id == VIEJO and filas[8].away_team_name == "etbenianos1"
        assert filas[9].away_team_ht_id == NUEVO and filas[9].away_team_name == "Kivaré"
        assert filas[10].home_team_ht_id == NUEVO and filas[10].home_team_name == "Kivaré"

    asyncio.run(run())


def test_el_calendario_toma_de_hattrick_el_equipo_tambien_en_los_jugados() -> None:
    """Hattrick le atribuye al equipo nuevo hasta los partidos ya jugados de ese
    sitio de la serie; el marcador guardado no se toca."""
    from types import SimpleNamespace

    from app.application.commands.sync_team import SyncResult, SyncTeamHandler

    async def run() -> None:
        factory, _ = await seeded_session()
        cauca, viejo = (3271519, "Cauca CF"), (VIEJO, "etbenianos1")
        async with factory() as s:
            s.add(_partido(0, cauca, viejo, 1))
            await s.commit()
        payload = {
            "series_ht_id": SERIE,
            "matches": [
                {
                    "ht_match_id": 950_000,
                    "match_round": 8,
                    "match_date": "2026-09-06 21:40:00",
                    "home_team_id": 3271519,
                    "home_team_name": "Cauca CF",
                    "away_team_id": NUEVO,
                    "away_team_name": "Kivaré",
                    "home_goals": 1,
                    "away_goals": 1,
                }
            ],
        }
        async with factory() as s:
            resultado = SyncResult(sync_id=0, status="running")
            await SyncTeamHandler._persist_league_fixtures(
                None,  # type: ignore[arg-type]
                SimpleNamespace(session=s),  # type: ignore[arg-type]
                payload,
                resultado,
            )
            await s.commit()
        async with factory() as s:
            fila = await s.scalar(select(m.Match).where(m.Match.ht_match_id == 950_000))
        assert fila is not None
        assert fila.away_team_ht_id == NUEVO and fila.away_team_name == "Kivaré"
        assert (fila.home_goals, fila.away_goals) == (1, 1)

    asyncio.run(run())


def test_sin_un_hueco_claro_no_se_toca_nada() -> None:
    """Si faltan o sobran dos equipos a la vez no hay forma de saber quién
    reemplazó a quién, y no se adivina."""

    async def run() -> None:
        factory, _ = await seeded_session()
        async with factory() as s:
            s.add(_partido(1, (1, "A"), (2, "B"), -1))
            await s.commit()
        async with factory() as s:
            equipos = [{"ht_team_id": 3, "name": "C"}, {"ht_team_id": 4, "name": "D"}]
            assert await trasladar_equipo_reemplazado(s, SERIE, equipos) == 0

    asyncio.run(run())
