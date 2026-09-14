"""El archivo de partidos, pedido en ventanas (2026-09-14).

Medido contra Hattrick: con un rango largo, matchesarchive lo ignora sin avisar
y devuelve los últimos tres meses. Lo que se vigila:
  · ninguna consulta pide más de `MATCH_ARCHIVE_WINDOW`;
  · una respuesta con partidos fuera de la ventana pedida NO sella el historial;
  · un historial sellado con la regla vieja se relee entero una vez, sin
    duplicar lo que ya estaba.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select

from app.application.commands.sync_team import (
    MATCH_ARCHIVE_WINDOW,
    VERSION_DEL_ARCHIVO,
    SyncResult,
    SyncTeamHandler,
)
from app.infrastructure.db import models as m
from tests.test_sync_flow import _setup

PROPIO = 537758
FUNDADO = datetime(2023, 1, 1, tzinfo=UTC)
HOY = datetime(2024, 1, 1, tzinfo=UTC)


def _fecha(p: dict[str, Any], clave: str) -> datetime:
    return datetime.strptime(p[clave], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)


def _partido(match_id: int, cuando: datetime) -> dict[str, Any]:
    return {
        "ht_match_id": match_id,
        "match_date": cuando.strftime("%Y-%m-%d %H:%M:%S"),
        "match_type": 1,
        "home_team_id": PROPIO,
        "away_team_id": 1,
        "home_team_name": "Pulgas Arrechas",
        "away_team_name": "Rival",
        "home_goals": 1,
        "away_goals": 0,
    }


class ArchivoRespetuoso:
    """Un partido a mitad de cada ventana, siempre dentro del rango pedido."""

    def __init__(self) -> None:
        self.consultas: list[dict[str, Any]] = []

    async def fetch(self, file: str, version: str = "latest", **params: Any) -> dict[str, Any]:
        assert file == "matchesarchive"
        self.consultas.append(params)
        desde, hasta = _fecha(params, "FirstMatchDate"), _fecha(params, "LastMatchDate")
        medio = desde + (hasta - desde) / 2
        return {"matches": [_partido(int(medio.timestamp()) // 3600, medio)]}


async def _equipo(uow, team_id: int, **campos: Any) -> None:
    async with uow as u:
        team = await u.session.get(m.Team, team_id)
        team.founded_at = FUNDADO
        for k, v in campos.items():
            setattr(team, k, v)
        await u.commit()


def test_el_archivo_se_pide_en_ventanas_y_se_sella_con_la_version() -> None:
    async def run() -> None:
        uow, _unused, team_id = await _setup()
        await _equipo(uow, team_id)
        chpp = ArchivoRespetuoso()
        handler = SyncTeamHandler(uow, chpp)
        result = SyncResult(sync_id=1, status="completed")
        async with uow as u:
            await handler._sync_match_history(u, team_id, PROPIO, HOY, result, on_progress=None)
            await u.commit()

        assert len(chpp.consultas) >= 5  # un año en ventanas de 12 semanas
        for c in chpp.consultas:
            assert _fecha(c, "LastMatchDate") - _fecha(c, "FirstMatchDate") <= MATCH_ARCHIVE_WINDOW
        assert _fecha(chpp.consultas[0], "FirstMatchDate") == FUNDADO
        assert _fecha(chpp.consultas[-1], "LastMatchDate") == HOY
        assert result.rescued_matches == len(chpp.consultas)
        async with uow as u:
            team = await u.session.get(m.Team, team_id)
            assert team.matches_history_complete is True
            assert team.matches_history_version == VERSION_DEL_ARCHIVO

    asyncio.run(run())


def test_si_hattrick_ignora_el_rango_no_se_sella() -> None:
    """La respuesta real con un rango largo: partidos recientes, sin error."""

    class ArchivoQueIgnoraElRango:
        async def fetch(self, file: str, version: str = "latest", **params: Any):
            return {"matches": [_partido(1, HOY + timedelta(days=200))]}

    async def run() -> None:
        uow, _unused, team_id = await _setup()
        await _equipo(uow, team_id)
        handler = SyncTeamHandler(uow, ArchivoQueIgnoraElRango())
        result = SyncResult(sync_id=1, status="completed")
        async with uow as u:
            await handler._sync_match_history(u, team_id, PROPIO, HOY, result, on_progress=None)
            await u.commit()

        assert result.status == "partial"
        assert any("ignoró el rango" in e for e in result.errors)
        async with uow as u:
            team = await u.session.get(m.Team, team_id)
            assert team.matches_history_complete is False
            total = await u.session.scalar(select(func.count()).select_from(m.Match))
        assert total == 0

    asyncio.run(run())


def test_un_historial_sellado_con_la_regla_vieja_se_relee_entero_una_vez() -> None:
    async def run() -> None:
        uow, _unused, team_id = await _setup()
        # Sellado por la versión 1: completo, con la marca en HOY.
        await _equipo(
            uow,
            team_id,
            matches_history_complete=True,
            matches_history_synced_until=HOY,
            matches_history_version=1,
        )
        chpp = ArchivoRespetuoso()
        handler = SyncTeamHandler(uow, chpp)

        async with uow as u:
            await handler._sync_match_history(
                u, team_id, PROPIO, HOY, SyncResult(sync_id=1, status="completed"), None
            )
            await u.commit()
        primeras = len(chpp.consultas)
        assert _fecha(chpp.consultas[0], "FirstMatchDate") == FUNDADO  # desde la fundación
        async with uow as u:
            total = await u.session.scalar(select(func.count()).select_from(m.Match))

        # Ya con la versión nueva: sólo la cola, y nada duplicado.
        chpp.consultas.clear()
        async with uow as u:
            await handler._sync_match_history(
                u,
                team_id,
                PROPIO,
                HOY + timedelta(days=7),
                SyncResult(sync_id=2, status="completed"),
                None,
            )
            await u.commit()
        assert len(chpp.consultas) == 1 < primeras
        async with uow as u:
            despues = await u.session.scalar(select(func.count()).select_from(m.Match))
        assert despues == total + 1

    asyncio.run(run())
