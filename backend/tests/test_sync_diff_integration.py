"""HL-140 · el sync detecta y guarda qué cambió — jugadores, economía,
entrenamiento, liga y partidos — usando el mismo diffing append-only que ya
existía, sin reconstruir nada a posteriori."""
import asyncio
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.sync_team import SyncTeamCommand, SyncTeamHandler
from app.infrastructure.chpp.parsers import get_parser
from app.infrastructure.db import models as m
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

FIXTURES = Path(__file__).parent / "fixtures"


class ScriptedCHPP:
    """Sirve una secuencia de payloads por-file, uno por llamada."""

    def __init__(self, scripts: dict[str, list[dict[str, Any]]]) -> None:
        self._scripts = scripts
        self._calls: dict[str, int] = {}

    async def fetch(self, file: str, version: str = "latest", **params: Any) -> dict[str, Any]:
        i = self._calls.get(file, 0)
        self._calls[file] = i + 1
        script = self._scripts.get(file, [])
        return script[min(i, len(script) - 1)]


async def _setup() -> tuple[SqlAlchemyUnitOfWork, int]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        team = m.Team(ht_team_id=537758, name="Pulgas Arrechas", currency_name="US$")
        s.add(team)
        await s.commit()
        team_id = team.id
    return SqlAlchemyUnitOfWork(factory), team_id


def test_player_skill_change_is_recorded() -> None:
    async def run() -> None:
        uow, team_id = await _setup()
        base = get_parser("players")((FIXTURES / "players.xml").read_bytes())
        p0 = base["players"][0]
        bumped = {**p0, "skills": {**p0["skills"], "defending": p0["skills"]["defending"] + 1}}
        after = {"players": [bumped, *base["players"][1:]]}

        chpp = ScriptedCHPP({"players": [base, after]})
        handler = SyncTeamHandler(uow, chpp)
        cmd = SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["players"])

        first = await handler.execute(cmd)
        # primer sync: todos "se unieron a la plantilla", no cambios de skill
        assert all("se unió a la plantilla" in c["summary"] for c in first.changes)

        second = await handler.execute(cmd)
        name = f"{p0['first_name']} {p0['last_name']}".strip()
        assert any(
                c["category"] == "jugadores" and "Defensa subió" in c["summary"]
            and name in c["summary"]
            for c in second.changes
        )

        async with uow as u:
            rows = (
                await u.session.execute(
                    select(m.SyncChange).where(m.SyncChange.sync_id == second.sync_id)
                )
            ).scalars().all()
            assert any("Defensa subió" in r.summary for r in rows)

    asyncio.run(run())


def test_economy_change_is_recorded_with_currency() -> None:
    async def run() -> None:
        uow, team_id = await _setup()
        base = get_parser("economy")((FIXTURES / "economy.xml").read_bytes())
        richer = {**base, "cash": base["cash"] + 100_000}

        chpp = ScriptedCHPP({"economy": [base, richer]})
        handler = SyncTeamHandler(uow, chpp)
        cmd = SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["economy"])

        first = await handler.execute(cmd)
        assert first.changes == []  # primer sync: sin "antes" que comparar

        second = await handler.execute(cmd)
        assert any(
            c["category"] == "economía" and "Caja" in c["summary"] and "US$" in c["summary"]
            for c in second.changes
        )

    asyncio.run(run())


def test_training_change_is_recorded() -> None:
    async def run() -> None:
        uow, team_id = await _setup()
        base = get_parser("training")((FIXTURES / "training.xml").read_bytes())
        retrained = {**base, "training_type": base["training_type"] + 1}

        chpp = ScriptedCHPP({"training": [base, retrained]})
        handler = SyncTeamHandler(uow, chpp)
        cmd = SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["training"])

        await handler.execute(cmd)
        second = await handler.execute(cmd)
        assert any(c["category"] == "entrenamiento" for c in second.changes)

    asyncio.run(run())


def test_match_result_change_is_recorded() -> None:
    async def run() -> None:
        uow, team_id = await _setup()
        upcoming = {
            "matches": [{
                "ht_match_id": 1, "home_team_id": 537758, "home_team_name": "Pulgas Arrechas",
                "away_team_id": 999, "away_team_name": "Rival FC",
                "match_date": "2026-01-01T00:00:00", "match_type": 1,
                "status": "UPCOMING", "home_goals": -1, "away_goals": -1,
            }]
        }
        finished = {
            "matches": [{**upcoming["matches"][0], "status": "FINISHED",
                         "home_goals": 2, "away_goals": 1}]
        }

        chpp = ScriptedCHPP({"matches": [upcoming, finished]})
        handler = SyncTeamHandler(uow, chpp)
        cmd = SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["matches"])

        first = await handler.execute(cmd)
        assert first.changes == []  # partido nuevo en el calendario, no un resultado

        second = await handler.execute(cmd)
        assert [(c["category"], c["summary"]) for c in second.changes] == [
            ("partidos", "Ganaste 2-1 vs Rival FC")
        ]
        # Desde 2026-08-15 cada cambio lleva también el dato crudo.
        assert second.changes[0]["detail"]["metric"] == "result"

    asyncio.run(run())


def test_standing_position_change_is_recorded() -> None:
    async def run() -> None:
        from app.infrastructure.db import models as m

        uow, team_id = await _setup()
        async with uow as u:
            u.session.add(m.WorldContext(ht_league_id=1, season=84))
            team = await u.session.get(m.Team, team_id)
            team.series_ht_id = 34162
            await u.commit()

        round1 = {
            "series_ht_id": 34162, "series_name": "V.92", "match_round": 1,
            "teams": [{"ht_team_id": 537758, "name": "Pulgas Arrechas", "position": 4,
                       "matches": 1, "won": 0, "draws": 0, "lost": 1,
                       "goals_for": 0, "goals_against": 1, "points": 0}],
        }
        round2 = {**round1, "match_round": 2, "teams": [
            {**round1["teams"][0], "position": 2, "matches": 2, "won": 1, "points": 3},
        ]}

        chpp = ScriptedCHPP({"leaguedetails": [round1, round2]})
        handler = SyncTeamHandler(uow, chpp)
        cmd = SyncTeamCommand(
            user_id=1, team_id=team_id, ht_team_id=537758, files=["leaguedetails"]
        )

        first = await handler.execute(cmd)
        assert first.changes == []  # primera jornada vista, sin anterior

        second = await handler.execute(cmd)
        assert [(c["category"], c["summary"]) for c in second.changes] == [
            ("liga", "Pulgas Arrechas subió de la posición 4 a la 2")
        ]
        assert second.changes[0]["detail"]["before"] == 4
        assert second.changes[0]["detail"]["after"] == 2

    asyncio.run(run())
