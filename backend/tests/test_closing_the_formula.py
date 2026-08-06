"""Cerrar la fórmula de entrenamiento: de supuestos a lecturas del CHPP.

El motor de entrenamiento tenía tres valores puestos a mano —la suma de niveles
de ayudantes, el nivel del entrenador y el %condición— que ajustaban los datos
pero que no venían del juego. Estos tests comprueban que ahora cada uno se lee
del fichero CHPP correcto, que no queda ningún supuesto escondido, y que la
fórmula se valida contra subidas de nivel que Hattrick confirma en vez de
inferirlas.
"""
import asyncio
from pathlib import Path

from app.application.commands.sync_team import SyncTeamCommand, SyncTeamHandler
from app.application.queries.training_context import TrainingContextService
from app.infrastructure.chpp.parsers import get_parser
from app.infrastructure.db import models as m
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from tests.conftest import seeded_session

FIXTURES = Path(__file__).parent / "fixtures"


def _run(coro):
    return asyncio.run(coro)


# ── Los parsers nuevos leen lo que tienen que leer ──────────────────────────

def test_club_parser_reads_the_assistant_level_the_formula_needed() -> None:
    """`AssistantTrainerLevels` es un entero único 0–10: la variable que antes
    se fijaba a mano. No es una cuenta de ayudantes."""
    data = get_parser("club")((FIXTURES / "club.xml").read_bytes())
    assert data["assistant_trainer_levels"] == 7
    assert 0 <= data["assistant_trainer_levels"] <= 10
    assert data["youth_investment"] == 11240
    assert data["form_coach_levels"] == 3
    assert data["medic_levels"] == 2


def test_stafflist_parser_reads_the_real_trainer() -> None:
    data = get_parser("stafflist")((FIXTURES / "stafflist.xml").read_bytes())
    tr = data["trainer"]
    assert tr["skill_level"] == 5
    assert tr["trainer_type"] == 2
    assert tr["trainer_type_name"] == "equilibrado"
    assert tr["leadership"] == 5
    assert data["total_staff"] == 2


def test_worlddetails_parser_reads_currency_and_calendar() -> None:
    """La tasa de moneda y la temporada/jornada reales: el fin del ×10 a mano y
    del lío de temporada (HL-007). 2026-08-04: worlddetails.xml trae el
    `<LeagueList>` de TODOS los países, no uno solo — el fixture tiene el
    real de Colombia (LeagueID 19, no el 50 que resultó ser Grecia)."""
    data = get_parser("worlddetails")((FIXTURES / "worlddetails.xml").read_bytes())
    assert len(data["leagues"]) == 1
    colombia = data["leagues"][0]
    assert colombia["ht_league_id"] == 19
    assert colombia["country_name"] == "Colombia"
    assert colombia["currency_rate"] == 10.0
    assert colombia["currency_name"] == "US$"
    assert colombia["season"] == 84
    assert colombia["season_offset"] == -12
    assert colombia["match_round"] == 3
    assert colombia["number_of_levels"] == 7
    assert colombia["league_system_id"] == 1
    assert colombia["cup_match_date"] == "2026-07-23 23:40:00"
    assert len(colombia["cups"]) == 5
    national = next(c for c in colombia["cups"] if c["cup_level"] == 1)
    assert national["cup_name"] == "Copa Colombia"
    assert national["match_round"] == 2
    assert national["match_rounds_left"] == 9
    challenge_names = {
        c["cup_level_index"]: c["cup_name"]
        for c in colombia["cups"] if c["cup_level"] == 2
    }
    assert challenge_names == {
        1: "Copa Macarena Esmeralda", 2: "Copa Cocuy Rubí", 3: "Copa Tayrona Zafiro",
    }


def test_trainingevents_parser_reads_confirmed_skill_ups() -> None:
    data = get_parser("trainingevents")((FIXTURES / "trainingevents.xml").read_bytes())
    ups = data["skill_ups"]
    assert len(ups) == 5
    first = ups[0]
    assert {"ht_player_id", "skill_id", "old_level", "new_level", "season",
            "match_round"} <= set(first)
    assert all(u["new_level"] == u["old_level"] + 1 for u in ups)


def test_sync_sets_team_currency_and_league_id_from_teamdetails_and_worlddetails() -> None:
    """2026-08-04, corrección importante pedida por el usuario:
    `Team.currency_rate`/`currency_name` NUNCA los ponía nada en el flujo
    real de sync (solo un script de desarrollo los había escrito a mano una
    vez) — se cruzan `teamdetails.xml` (Team.ht_league_id) contra
    `worlddetails.xml` (WorldContext por país) y se copian a Team los del
    país que de verdad coincide, no un valor fijo asumido."""
    async def go():
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
        from sqlalchemy.pool import StaticPool

        from tests.conftest import HT_TEAM_ID, FakeCHPP

        engine = create_async_engine(
            "sqlite+aiosqlite://", poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as s:
            team = m.Team(ht_team_id=HT_TEAM_ID, name="Pulgas Arrechas")
            s.add(team)
            await s.commit()
            team_id = team.id

        handler = SyncTeamHandler(SqlAlchemyUnitOfWork(factory), FakeCHPP())
        result = await handler.execute(
            SyncTeamCommand(
                user_id=1, team_id=team_id, ht_team_id=HT_TEAM_ID,
                files=["teamdetails", "worlddetails"],
            )
        )
        assert result.status == "completed"

        async with factory() as s:
            team = await s.get(m.Team, team_id)
            cups = (
                await s.execute(select(m.WorldCup).where(m.WorldCup.ht_league_id == 19))
            ).scalars().all()
            return team, cups

    team, cups = asyncio.run(go())
    assert team.ht_league_id == 19
    assert team.currency_rate == 10.0
    assert team.currency_name == "US$"
    assert team.still_in_cup is True
    assert team.current_cup_id == 18
    assert team.current_cup_match_round == 1
    assert team.current_cup_match_rounds_left == 11
    assert len(cups) == 5
    national = next(c for c in cups if c.cup_level == 1)
    assert national.cup_name == "Copa Colombia"
    assert national.match_round == 2
    assert national.match_rounds_left == 9
    challenge = {c.cup_level_index: c.cup_name for c in cups if c.cup_level == 2}
    assert challenge == {
        1: "Copa Macarena Esmeralda", 2: "Copa Cocuy Rubí", 3: "Copa Tayrona Zafiro",
    }


# ── El sync persiste y es idempotente ───────────────────────────────────────

def test_sync_persists_staff_world_and_skill_ups() -> None:
    async def go():
        from sqlalchemy import select

        factory, team_id = await seeded_session()
        async with factory() as s:
            staff = (await s.execute(select(m.StaffSnapshot))).scalars().all()
            world = (await s.execute(select(m.WorldContext))).scalars().all()
            ups = (await s.execute(select(m.SkillUp))).scalars().all()
            return staff, world, ups

    staff, world, ups = _run(go())
    assert len(staff) == 1
    # club y stafflist rellenan la MISMA fila, no dos.
    assert staff[0].assistant_trainer_levels == 7
    assert staff[0].trainer_skill_level == 5
    assert len(world) == 1
    assert world[0].season == 84
    assert len(ups) == 5


def test_skill_ups_are_idempotent() -> None:
    """Sincronizar trainingevents dos veces no cuenta un pop dos veces: la
    subida de un jugador a un nivel es un hecho único."""
    async def go():
        from sqlalchemy import select

        from app.application.commands.sync_team import SyncTeamCommand, SyncTeamHandler
        from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
        from tests.conftest import HT_TEAM_ID, FakeCHPP

        factory, team_id = await seeded_session()
        handler = SyncTeamHandler(SqlAlchemyUnitOfWork(factory), FakeCHPP())
        result = await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=HT_TEAM_ID,
                            files=["trainingevents"])
        )
        async with factory() as s:
            ups = (await s.execute(select(m.SkillUp))).scalars().all()
        return len(ups), result.unchanged

    count, unchanged = _run(go())
    assert count == 5              # no se duplicaron
    assert unchanged == 5          # todos reconocidos como ya vistos


# ── La fórmula queda cerrada ────────────────────────────────────────────────

def test_every_formula_input_is_read_from_chpp() -> None:
    """El corazón de todo: ningún término de la fórmula sigue siendo un
    supuesto. Cada uno apunta a su fichero CHPP."""
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            return await TrainingContextService(s).get(team_id)

    ctx = _run(go())
    assert ctx is not None
    assert ctx.all_read is True

    expected_source = {
        "assistant_level_sum": "club.xml",
        "intensity": "training.xml",
        "stamina_share": "training.xml",
        "coach_level": "stafflist.xml",
    }
    for key, source in expected_source.items():
        prov = ctx.provenance[key]
        assert prov.is_read is True, f"{key} sigue siendo un supuesto"
        assert prov.source == source


def test_the_read_values_replace_the_hand_set_ones() -> None:
    """Los valores que yo había fijado (Σ=10, condición 12,5%) se sustituyen por
    los leídos (Σ=7, condición 25%)."""
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            return await TrainingContextService(s).get(team_id)

    ctx = _run(go())
    assert ctx.setup.assistant_level_sum == 7      # leído, no el 10 supuesto
    assert ctx.setup.stamina_share == 25           # leído, no el 12,5 supuesto
    assert ctx.setup.intensity == 100
    assert ctx.trained_skill == "passing"          # training type 10, confirmado


def test_the_formula_is_validated_against_confirmed_skill_ups() -> None:
    """La validación no se inventa: la distancia entre dos subidas confirmadas
    es el número real de semanas que costó subir, y se compara con la fórmula."""
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            return await TrainingContextService(s).get(team_id)

    ctx = _run(go())
    v = ctx.validation
    assert v.observations >= 1
    assert v.mean_error_weeks is not None
    assert v.mean_error_weeks < 1.5
    for sample in v.samples:
        assert sample["observed_weeks"] > 0
        assert sample["to_level"] == sample["from_level"] + 1
    # La aproximación de edad se declara, no se esconde.
    assert any("edad" in c.lower() for c in v.caveats)


def test_the_coach_scale_mismatch_is_declared_not_hidden() -> None:
    """Lo único que queda por reconciliar —la escala 1–5 del entrenador frente a
    la 7/8 de la fórmula— aparece como nota provisional, no como un mapeo
    silencioso."""
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            return await TrainingContextService(s).get(team_id)

    ctx = _run(go())
    coach = ctx.provenance["coach_level"]
    assert "PROVISIONAL" in coach.note or "provisional" in coach.note.lower()
    assert any("provisional" in n.lower() for n in ctx.notes)


def test_without_the_new_files_it_degrades_honestly() -> None:
    """Si un equipo no ha sincronizado club/stafflist, el contexto lo dice y
    marca qué términos siguen siendo supuestos, en vez de fingir que los lee."""
    async def go():
        from sqlalchemy import delete

        factory, team_id = await seeded_session()
        async with factory() as s:
            await s.execute(delete(m.StaffSnapshot))
            await s.commit()
        async with factory() as s:
            return await TrainingContextService(s).get(team_id)

    ctx = _run(go())
    assert ctx.all_read is False
    assert ctx.provenance["assistant_level_sum"].is_read is False
    assert ctx.provenance["coach_level"].is_read is False
    # intensidad y condición sí, porque vienen de training, que sí se sincronizó
    assert ctx.provenance["intensity"].is_read is True
    assert any("faltan" in n.lower() or "supuesto" in n.lower() for n in ctx.notes)
