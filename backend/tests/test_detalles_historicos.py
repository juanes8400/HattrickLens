"""La historia completa de Partidos, de una vez (2026-09-14).

Lo que se vigila:
  · el primer sync pide el detalle de TODOS los partidos que sólo tenían
    marcador, y los guarda del más reciente al más antiguo;
  · al guardarlos se quita la marca, así que ninguno se pide dos veces;
  · el siguiente sync ya no pide nada;
  · torneos, escaleras y demás no oficiales nunca entran.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.application.commands.sync_team import SyncResult, SyncTeamHandler
from app.infrastructure.db import models as m
from tests.test_sync_flow import _setup

PROPIO = 537758
BASE = datetime(2024, 1, 1, tzinfo=UTC)
PENDIENTES = 25


class DobleDeHattrick:
    def __init__(self) -> None:
        self.pedidos: list[int] = []

    async def fetch(self, file: str, version: str = "latest", **params: Any) -> dict[str, Any]:
        if file == "arenadetails":
            return {"current_capacity": {"total": 0}}
        assert file == "matchdetails"
        match_id = params["matchID"]
        self.pedidos.append(match_id)
        ratings = {
            "midfield": 10,
            "right_def": 20,
            "central_def": 20,
            "left_def": 20,
            "right_att": 10,
            "central_att": 10,
            "left_att": 10,
        }
        return {
            "ht_match_id": match_id,
            "home": {"team_id": PROPIO, "ratings": ratings},
            "away": {"team_id": match_id, "ratings": ratings},
        }


def test_los_detalles_antiguos_llegan_por_tandas_y_no_se_repiten() -> None:
    async def run() -> None:
        uow, _unused, team_id = await _setup()
        async with uow as u:
            for i in range(PENDIENTES):
                u.session.add(
                    m.Match(
                        ht_match_id=600_000 + i,
                        played_at=BASE + timedelta(days=7 * i),
                        match_type=1 if i % 2 else 4,  # liga y amistosos
                        status="FINISHED",
                        home_team_ht_id=PROPIO,
                        away_team_ht_id=600_000 + i,
                        home_team_name="Pulgas Arrechas",
                        away_team_name=f"Rival {i}",
                        home_goals=1,
                        away_goals=0,
                        history_summary_only=True,
                    )
                )
            # Una escalera antigua con sólo marcador: no debe pedirse nunca.
            u.session.add(
                m.Match(
                    ht_match_id=699_999,
                    played_at=BASE + timedelta(days=1000),
                    match_type=62,
                    status="FINISHED",
                    home_team_ht_id=PROPIO,
                    away_team_ht_id=1,
                    home_team_name="Pulgas Arrechas",
                    away_team_name="Escalera",
                    home_goals=1,
                    away_goals=0,
                    history_summary_only=True,
                )
            )
            await u.commit()

        chpp = DobleDeHattrick()
        handler = SyncTeamHandler(uow, chpp)

        async def un_sync() -> list[int]:
            chpp.pedidos.clear()
            async with uow as u:
                await handler._completar_detalles_historicos(
                    u, team_id, PROPIO, SyncResult(sync_id=1, status="completed")
                )
                await u.commit()
            return list(chpp.pedidos)

        primera = await un_sync()
        # Todos de una vez, y ni uno repetido.
        assert sorted(primera) == [600_000 + i for i in range(PENDIENTES)]
        assert 699_999 not in primera

        segunda = await un_sync()
        assert segunda == []

        async with uow as u:
            sin_detalle = (
                (
                    await u.session.execute(
                        select(m.Match.ht_match_id).where(m.Match.history_summary_only.is_(True))
                    )
                )
                .scalars()
                .all()
            )
            con_ratings = (
                (
                    await u.session.execute(
                        select(m.MatchRating.ht_match_id).where(m.MatchRating.team_ht_id == PROPIO)
                    )
                )
                .scalars()
                .all()
            )
        assert list(sin_detalle) == [699_999]
        assert len(set(con_ratings)) == PENDIENTES

    asyncio.run(run())


def test_un_error_de_hattrick_no_bloquea_la_tanda() -> None:
    """Si Hattrick responde con error para un partido, se da por intentado y la
    tanda siguiente sigue con los demás en vez de volver a chocar con él."""

    async def run() -> None:
        uow, _unused, team_id = await _setup()
        async with uow as u:
            for i in range(2):
                u.session.add(
                    m.Match(
                        ht_match_id=610_000 + i,
                        played_at=BASE + timedelta(days=7 * i),
                        match_type=1,
                        status="FINISHED",
                        home_team_ht_id=PROPIO,
                        away_team_ht_id=5,
                        home_team_name="Pulgas Arrechas",
                        away_team_name="Rival",
                        home_goals=1,
                        away_goals=0,
                        history_summary_only=True,
                    )
                )
            await u.commit()

        class ConError(DobleDeHattrick):
            async def fetch(self, file: str, version: str = "latest", **params: Any):
                if file == "matchdetails" and params["matchID"] == 610_001:
                    self.pedidos.append(610_001)
                    # Lo que devuelve de verdad el lector cuando Hattrick
                    # responde sin <Match>.
                    return {}
                return await super().fetch(file, version, **params)

        chpp = ConError()
        handler = SyncTeamHandler(uow, chpp)
        result = SyncResult(sync_id=1, status="completed")
        async with uow as u:
            await handler._completar_detalles_historicos(u, team_id, PROPIO, result)
            await u.commit()
        assert sorted(chpp.pedidos) == [610_000, 610_001]
        assert any("610001" in e for e in result.errors)

        chpp.pedidos.clear()
        async with uow as u:
            await handler._completar_detalles_historicos(
                u, team_id, PROPIO, SyncResult(sync_id=2, status="completed")
            )
            await u.commit()
        assert chpp.pedidos == []

    asyncio.run(run())
