"""La comparacion es contra la alineacion que YA enviaste.

2026-08-22, pedido por el usuario: comparar contra el ultimo partido jugado no
media nada util --se jugo con otra formacion, o con alguien dentro porque
necesitaba entrenar--. Y ademas se colaba un partido ajeno: la ficha de un
jugador trae su ultimo partido, y el de un recien comprado es el de su club
anterior, asi que entraba con UN solo jugador nuestro dentro y las lineas
salian "0 de 0", porteria incluida.
"""
import asyncio
import json
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
PROXIMO = 111
UNO_AJENO = 222

#: role_id de matchorders: 100 portero, 101-105 defensa, 106-110 medio,
#: 111-113 ataque.
ONCE = [
    {"role_id": 100, "ht_player_id": 10, "behaviour": 0},
    *[{"role_id": r, "ht_player_id": 20 + r, "behaviour": 0} for r in range(101, 111)],
]


def _montar(con_alineacion: bool = True) -> tuple[TestClient, int]:
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

            s.add(m.Match(
                ht_match_id=PROXIMO, played_at=datetime(2026, 8, 23, 21, 40),
                match_type=1, status="UPCOMING",
                home_team_ht_id=MI_EQUIPO, away_team_ht_id=999,
                home_team_name="Pulgas Arrechas", away_team_name="San Andrés",
                home_goals=-1, away_goals=-1,
                submitted_lineup_json=json.dumps(ONCE) if con_alineacion else None,
            ))
            # Un partido AJENO, mas reciente, con alineacion enviada de otro:
            # no debe ganar por ser mas nuevo ni por nada.
            s.add(m.Match(
                ht_match_id=UNO_AJENO, played_at=datetime(2026, 8, 21, 18, 0),
                match_type=1, status="UPCOMING",
                home_team_ht_id=2163568, away_team_ht_id=888,
                home_team_name="Santana Red Devils", away_team_name="Manculicani",
                home_goals=-1, away_goals=-1,
                submitted_lineup_json=json.dumps(ONCE),
            ))

            s.add(m.Player(
                ht_player_id=10, team_id=equipo.id,
                first_name="Anders", last_name="Ebbesen",
            ))
            for r in range(101, 111):
                s.add(m.Player(
                    ht_player_id=20 + r, team_id=equipo.id,
                    first_name="J", last_name=str(r),
                ))
            await s.commit()
            return equipo.id

    team_id = asyncio.run(preparar())

    async def sesion() -> Any:
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = sesion
    app.dependency_overrides[require_team_owner] = lambda: None
    return TestClient(app), team_id


def test_compara_contra_la_alineacion_enviada_del_proximo_partido() -> None:
    client, team_id = _montar()
    try:
        cuerpo = client.get(f"/api/v1/teams/{team_id}/lineup/hindsight").json()
        assert cuerpo["matchId"] == PROXIMO
        assert "Pulgas Arrechas" in cuerpo["matchLabel"]
        assert any("ya enviaste" in n for n in cuerpo["notes"]), (
            "falta el mensaje que dice contra que se compara"
        )
    finally:
        app.dependency_overrides.clear()


def test_el_partido_de_otro_club_no_entra() -> None:
    client, team_id = _montar()
    try:
        cuerpo = client.get(f"/api/v1/teams/{team_id}/lineup/hindsight").json()
        assert cuerpo["matchId"] != UNO_AJENO
        assert "Santana" not in (cuerpo["matchLabel"] or "")
    finally:
        app.dependency_overrides.clear()


def test_el_portero_que_pusiste_cuenta_como_puesto() -> None:
    """El sintoma que lo delato: porteria 0/0 proponiendo un portero."""
    client, team_id = _montar()
    try:
        cuerpo = client.get(f"/api/v1/teams/{team_id}/lineup/hindsight").json()
        porteria = next(l for l in cuerpo["lines"] if l["key"] == "keeper")
        assert porteria["usedCount"] == 1
        assert porteria["used"][0]["player"] == "Anders Ebbesen"
    finally:
        app.dependency_overrides.clear()


def test_sin_alineacion_enviada_lo_dice_en_vez_de_inventar() -> None:
    client, team_id = _montar(con_alineacion=False)
    try:
        cuerpo = client.get(f"/api/v1/teams/{team_id}/lineup/hindsight").json()
        assert cuerpo["matchId"] is None
        assert cuerpo["lines"] == []
        assert any("No has enviado alineación" in n for n in cuerpo["notes"])
    finally:
        app.dependency_overrides.clear()
