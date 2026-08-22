"""El comparador tiene que mirar TU partido, no uno cualquiera.

La ficha de un jugador trae su ultimo partido, y el de alguien recien comprado
es el que jugo en su club anterior. Ese partido llegaba en la sincronizacion
mas reciente y se colaba como "el ultimo partido" del equipo, con un solo
jugador nuestro dentro: la comparacion salia "0 de 0" en todas las lineas y el
marcador era de un partido ajeno.
"""
import asyncio
from datetime import datetime
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import require_team_owner
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.main import app

MI_EQUIPO = 537758
AJENO = 2163568
PARTIDO_MIO = 111
PARTIDO_AJENO = 222


def _montar() -> tuple[TestClient, int]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def preparar() -> int:
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)
        async with factory() as s:
            equipo = m.Team(ht_team_id=MI_EQUIPO, name="Pulgas Arrechas")
            s.add(equipo)
            await s.flush()

            s.add_all([
                m.Match(
                    ht_match_id=PARTIDO_MIO, played_at=datetime(2026, 8, 19, 22, 10),
                    match_type=1, status="FINISHED",
                    home_team_ht_id=MI_EQUIPO, away_team_ht_id=999,
                    home_team_name="Pulgas Arrechas", away_team_name="Charta F. C.",
                    home_goals=3, away_goals=0,
                ),
                # Jugado DESPUES y visto DESPUES, pero no es nuestro.
                m.Match(
                    ht_match_id=PARTIDO_AJENO, played_at=datetime(2026, 8, 20, 18, 0),
                    match_type=1, status="FINISHED",
                    home_team_ht_id=AJENO, away_team_ht_id=888,
                    home_team_name="Santana Red Devils", away_team_name="Manculicani",
                    home_goals=1, away_goals=0,
                ),
            ])

            titular = m.Player(
                ht_player_id=10, team_id=equipo.id,
                first_name="Anders", last_name="Ebbesen",
            )
            recien_comprado = m.Player(
                ht_player_id=20, team_id=equipo.id,
                first_name="José Vicente", last_name="Alvargonzález",
            )
            s.add_all([titular, recien_comprado])
            await s.flush()

            s.add_all([
                m.PlayerMatchRating(
                    player_id=titular.id, ht_match_id=PARTIDO_MIO,
                    position_code=100, played_minutes=90, rating=5.0,
                    captured_at=datetime(2026, 8, 19, 23, 0),
                ),
                m.PlayerMatchRating(
                    player_id=recien_comprado.id, ht_match_id=PARTIDO_AJENO,
                    position_code=103, played_minutes=90, rating=4.0,
                    captured_at=datetime(2026, 8, 22, 12, 0),   # visto mucho despues
                ),
            ])
            await s.commit()
            return equipo.id

    team_id = asyncio.run(preparar())

    async def sesion() -> Any:
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = sesion
    app.dependency_overrides[require_team_owner] = lambda: None
    return TestClient(app), team_id


def test_compara_el_partido_del_club_no_el_del_fichaje() -> None:
    client, team_id = _montar()
    try:
        cuerpo = client.get(f"/api/v1/teams/{team_id}/lineup/hindsight").json()
        assert cuerpo["matchId"] == PARTIDO_MIO, (
            f"escogio {cuerpo['matchLabel']}, que no es un partido de este club"
        )
        assert "Pulgas Arrechas" in (cuerpo["matchLabel"] or "")
    finally:
        app.dependency_overrides.clear()


def test_el_portero_que_si_jugo_no_sale_como_hueco() -> None:
    """El sintoma que lo delató: portería 0/0 proponiendo un portero."""
    client, team_id = _montar()
    try:
        cuerpo = client.get(f"/api/v1/teams/{team_id}/lineup/hindsight").json()
        porteria = next(l for l in cuerpo["lines"] if l["key"] == "keeper")
        assert porteria["usedCount"] == 1, "puso portero y salia como que no"
        assert porteria["used"][0]["player"] == "Anders Ebbesen"
    finally:
        app.dependency_overrides.clear()
