"""La «Preparación para 120 minutos» del próximo rival de Copa (2026-11-27,
pedido del usuario): la misma ficha que la tuya, con sus 11 de mayor TSI y sus
últimas formaciones en Liga y en Copa."""

import asyncio
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints import rivals
from app.api.v1.endpoints.cup import _bandas_de_resistencia, _preparacion_del_rival
from app.infrastructure.chpp import client as modulo_del_cliente
from app.infrastructure.db import models as m
from app.infrastructure.security import tokens

RIVAL = 536551


def _jugador(i: int, resistencia: int, tsi: int, leida: bool = True) -> dict[str, Any]:
    return {"ht_player_id": i, "stamina": resistencia, "stamina_is_read": leida, "tsi": tsi}


def _partido(mid: int, tipo: int, fecha: str, contrario: str) -> dict[str, Any]:
    return {
        "ht_match_id": mid,
        "match_type": tipo,
        "status": "FINISHED",
        "match_date": fecha,
        "home_team_id": RIVAL,
        "home_team_name": "Once Miserables",
        "away_team_id": 1,
        "away_team_name": contrario,
    }


class _Hattrick:
    def __init__(self, plantilla: list[dict[str, Any]]) -> None:
        self.plantilla = plantilla
        self.pedidos: list[str] = []

    def __call__(self, *_: Any) -> "_Hattrick":
        return self

    async def fetch(self, file: str, version: str = "latest", **params: Any) -> dict[str, Any]:
        self.pedidos.append(file)
        if file == "players":
            return {"players": self.plantilla}
        if file == "matches":
            return {
                "matches": [
                    _partido(10, 1, "2026-11-15 20:00:00", "Viejo de Liga"),
                    _partido(11, 1, "2026-11-22 20:00:00", "Guaviare Rayo"),
                    _partido(12, 3, "2026-11-25 20:00:00", "Red Maiden"),
                ]
            }
        # Liga: del 1 al 11. Copa: del 5 al 15, con el 15 ya vendido.
        primero = 1 if params["matchID"] == 11 else 5
        return {
            "players": [
                {"ht_player_id": i, "role_id": 0, "position_code": n + 1}
                for n, i in enumerate(range(primero, primero + 11))
            ]
            # El banquillo no cuenta.
            + [{"ht_player_id": 99, "role_id": 0, "position_code": 0}]
        }

    async def aclose(self) -> None:
        return None


async def _base() -> tuple[async_sessionmaker, m.Team]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        u = m.User(ht_user_id=1, login_name="prueba")
        s.add(u)
        await s.flush()
        s.add(m.CHPPToken(user_id=u.id, oauth_token_enc=b"t", oauth_secret_enc=b"s"))
        team = m.Team(ht_team_id=537758, name="Pulgas Arrechas", owner_user_id=u.id)
        s.add(team)
        await s.commit()
    return factory, team


def test_las_bandas_de_resistencia() -> None:
    hecho = _bandas_de_resistencia([3, 5, 6, 7, 8, 9])
    assert hecho["average_stamina"] == 6.3
    assert [b["count"] for b in hecho["stamina_bands"]] == [2, 2, 2]
    assert _bandas_de_resistencia([])["average_stamina"] is None


def test_la_preparacion_del_rival_trae_sus_tres_referencias(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rivals._chpp_cache.clear()
    plantilla = [_jugador(i, resistencia=i % 10, tsi=1000 * i) for i in range(1, 15)]
    hattrick = _Hattrick(plantilla)
    monkeypatch.setattr(modulo_del_cliente, "CHPPClient", hattrick)
    monkeypatch.setattr(tokens, "decrypt_token", lambda v: "x")

    async def run() -> dict[str, Any] | None:
        factory, team = await _base()
        async with factory() as s:
            return await _preparacion_del_rival(s, team, RIVAL, None)

    hecho = asyncio.run(run())
    assert hecho is not None
    por_modo = {v["mode"]: v for v in hecho["reference_variants"]}
    assert list(por_modo) == ["top_tsi", "last_league", "last_cup"]
    # Los 11 de mayor TSI son los jugadores 4 a 14.
    assert por_modo["top_tsi"]["starters_count"] == 11
    # La última de Liga es la del 22-nov, no la del 15.
    assert por_modo["last_league"]["source_opponent"] == "Guaviare Rayo"
    assert por_modo["last_league"]["source_date"] == "2026-11-22"
    # En Copa jugaron del 5 al 15; el 15 ya no está, quedan diez.
    assert por_modo["last_cup"]["starters_count"] == 10
    assert hecho["default_mode"] == "last_cup"


def test_sin_la_resistencia_del_rival_no_hay_ficha(monkeypatch: pytest.MonkeyPatch) -> None:
    rivals._chpp_cache.clear()
    hattrick = _Hattrick([_jugador(i, 7, 1000, leida=i != 3) for i in range(1, 15)])
    monkeypatch.setattr(modulo_del_cliente, "CHPPClient", hattrick)
    monkeypatch.setattr(tokens, "decrypt_token", lambda v: "x")

    async def run() -> dict[str, Any] | None:
        factory, team = await _base()
        async with factory() as s:
            return await _preparacion_del_rival(s, team, RIVAL + 1, None)

    assert asyncio.run(run()) is None
