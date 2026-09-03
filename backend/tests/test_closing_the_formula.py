"""Cerrar la fórmula de entrenamiento: de supuestos a lecturas del CHPP.

El motor de entrenamiento tenía tres valores puestos a mano —la suma de niveles
de ayudantes, el nivel del entrenador y el %condición— que ajustaban los datos
pero que no venían del juego. Estos tests comprueban que ahora cada uno se lee
del fichero CHPP correcto, que no queda ningún supuesto escondido, y que la
fórmula se valida contra subidas de nivel que Hattrick confirma en vez de
inferirlas.
"""
import asyncio
from datetime import datetime
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

def test_club_parser_no_longer_reads_dead_staff_fields() -> None:
    """2026-08-12, corrección: club.xml v1.1 (verificado en vivo contra la
    cuenta real) ya no trae `<Staff>` ni `AssistantTrainerLevels` — solo
    `<Specialists>` (booleanos) y `<YouthSquad>`. El parser no debe fingir
    que sigue leyendo un campo que Hattrick dejó de enviar."""
    data = get_parser("club")((FIXTURES / "club.xml").read_bytes())
    assert "assistant_trainer_levels" not in data
    assert "form_coach_levels" not in data
    assert "medic_levels" not in data
    assert data["youth_investment"] == 11240
    assert data["youth_level"] == 4


def test_stafflist_parser_reads_the_real_trainer_and_staff() -> None:
    """El desglose real de asistentes vive aquí, no en club.xml — 2 personas
    de nivel 5 cada una (StaffType=1), no un agregado misterioso."""
    data = get_parser("stafflist")((FIXTURES / "stafflist.xml").read_bytes())
    tr = data["trainer"]
    assert tr["skill_level"] == 5
    assert tr["trainer_type"] == 2
    assert tr["trainer_type_name"] == "equilibrado"
    assert tr["leadership"] == 5
    assert data["total_staff"] == 3
    assistants = [m for m in data["staff_members"] if m["staff_type"] == 1]
    assert len(assistants) == 2
    assert all(a["level"] == 5 for a in assistants)


def test_worlddetails_parser_reads_currency_and_calendar() -> None:
    """La tasa de moneda y la temporada/jornada reales: el fin del ×10 a mano y
    del lío de temporada (HL-007). 2026-08-04: worlddetails.xml trae el
    `<LeagueList>` de TODOS los países, no uno solo — el fixture tiene el
    real de Colombia (LeagueID 19, no el 50 que resultó ser Grecia)."""
    data = get_parser("worlddetails")((FIXTURES / "worlddetails.xml").read_bytes())
    assert len(data["leagues"]) == 1
    colombia = data["leagues"][0]
    assert colombia["ht_league_id"] == 19
    assert colombia["country_id"] == 18
    assert colombia["country_code"] == "CO"
    assert colombia["country_name"] == "Colombia"
    assert colombia["currency_rate"] == 10.0
    assert colombia["currency_name"] == "US$"
    assert colombia["season"] == 84
    assert colombia["season_offset"] == -12
    assert colombia["match_round"] == 3
    assert colombia["number_of_levels"] == 7
    assert colombia["league_system_id"] == 1
    assert colombia["economy_date"] == "2026-07-27 00:00:00"
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
    # 10 = 5+5, los dos asistentes de entrenador reales del fixture
    # (StaffType=1) — ya no un agregado de club.xml (ver parse_club).
    assert staff[0].assistant_trainer_levels == 10
    assert staff[0].trainer_skill_level == 5
    assert len(world) == 1
    assert world[0].season == 84
    assert world[0].country_id == 18
    assert world[0].country_code == "CO"
    # 00:00 CEST del XML = 22:00 UTC del día anterior en la base.
    assert world[0].economy_date == datetime(2026, 7, 26, 22, 0)
    assert len(ups) == 5


def test_a_missing_trainer_element_does_not_wipe_the_last_known_trainer() -> None:
    """2026-08-12, riesgo real encontrado al verificar en vivo: CHPP a veces
    omite `<Trainer>` por completo de stafflist.xml. Antes de esta guarda,
    ese "sin dato" se escribía como 0/tipo-por-defecto en cada sync — ahora
    que club+stafflist entran en cada sync normal (ver DEFAULT_FILES), eso
    habría borrado el entrenador real en la próxima sincronización."""
    from typing import Any

    async def go():
        from sqlalchemy import select

        factory, team_id = await seeded_session()

        no_trainer_payload = dict(
            get_parser("stafflist")((FIXTURES / "stafflist.xml").read_bytes())
        )
        no_trainer_payload["trainer"] = {}

        class NoTrainerCHPP:
            async def fetch(self, file: str, version: str, **params: Any) -> dict[str, Any]:
                return no_trainer_payload if file == "stafflist" else {}

        handler = SyncTeamHandler(SqlAlchemyUnitOfWork(factory), NoTrainerCHPP())
        await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["stafflist"])
        )

        async with factory() as s:
            rows = (
                await s.execute(
                    select(m.StaffSnapshot)
                    .where(m.StaffSnapshot.team_id == team_id)
                    .order_by(m.StaffSnapshot.captured_at.desc())
                )
            ).scalars().all()
            return rows[0]

    latest = _run(go())
    assert latest.trainer_skill_level == 5   # el real, no reseteado a 0
    assert latest.trainer_type == 2
    assert latest.trainer_leadership == 5
    # El roster de asistentes SÍ se actualiza — <StaffMembers> siguió llegando.
    assert latest.assistant_trainer_levels == 10


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

def test_ningun_termino_de_la_formula_es_un_supuesto() -> None:
    """El corazón de todo: ningún término de la fórmula sigue siendo un
    supuesto. Cada uno apunta a la pantalla de Hattrick de la que se leyó.

    El nombre del origen es TEXTO DE USUARIO --se pinta tal cual en la
    pantalla de transparencia--, así que desde el 2026-08-31 no puede nombrar
    un fichero de la API. Aquí se fija además esa regla."""
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            return await TrainingContextService(s).get(team_id)

    ctx = _run(go())
    assert ctx is not None
    assert ctx.all_read is True

    expected_source = {
        # 2026-08-12: el agregado dejó de venir con los datos del club
        # (verificado en vivo) — ahora es la suma real de tus asistentes.
        "assistant_level_sum": "Cuerpo técnico",
        "intensity": "Entrenamiento",
        "stamina_share": "Entrenamiento",
        "training_type": "Entrenamiento",
        "coach_level": "Cuerpo técnico",
    }
    for key, source in expected_source.items():
        prov = ctx.provenance[key]
        assert prov.is_read is True, f"{key} sigue siendo un supuesto"
        assert prov.source == source

    # Ningún origen ni ninguna nota puede delatar la API: los dos se pintan.
    for key, prov in ctx.provenance.items():
        assert ".xml" not in prov.source, key
        assert "CHPP" not in prov.source, key
        assert ".xml" not in prov.note, key
        assert "CHPP" not in prov.note, key


def test_the_read_values_replace_the_hand_set_ones() -> None:
    """El %condición fijado a mano (12,5%) se sustituye por el leído (25%).
    El agregado de ayudantes fijado a mano también era 10 — coincide con el
    real (2 asistentes de nivel 5), pero por una razón distinta: éste es la
    suma de personas reales de stafflist.xml, no un número inventado."""
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            return await TrainingContextService(s).get(team_id)

    ctx = _run(go())
    assert ctx.setup.assistant_level_sum == 10     # leído (5+5), no un supuesto
    assert ctx.setup.stamina_share == 25           # leído, no el 12,5 supuesto
    assert ctx.setup.intensity == 100
    assert ctx.setup.training_type == 10
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
    for sample in v.samples:
        assert sample["observed_weeks"] > 0
        assert sample["to_level"] == sample["from_level"] + 1
    # La aproximación de edad se declara, no se esconde.
    assert any("edad" in c.lower() for c in v.caveats)


def test_the_coach_scale_is_mapped_to_the_public_formula() -> None:
    """StaffLevel 1–5 maps directly to HT-Tools' formula scale 4–8."""
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            return await TrainingContextService(s).get(team_id)

    ctx = _run(go())
    coach = ctx.provenance["coach_level"]
    assert coach.value == 8
    assert "HT-Tools" in coach.note
    assert not any("calibr" in n.lower() for n in ctx.notes)


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


def test_without_training_xml_stamina_falls_back_to_the_configured_default() -> None:
    """Bug real corregido 2026-08-14: sin training.xml, el supuesto de
    %condición caía en 0 en vez del `default_stamina_share` (12.5) que el
    propio training.yaml documenta para este caso — 0% habría predicho un
    entrenamiento más rápido de lo que ese supuesto pretende representar."""
    async def go():
        from sqlalchemy import delete

        factory, team_id = await seeded_session()
        async with factory() as s:
            await s.execute(delete(m.TrainingSnapshot))
            await s.commit()
        async with factory() as s:
            return await TrainingContextService(s).get(team_id)

    ctx = _run(go())
    assert ctx.provenance["stamina_share"].is_read is False
    assert ctx.setup.stamina_share == 12.5
