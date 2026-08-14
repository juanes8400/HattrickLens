"""TrainingSquadQueryService y sus endpoints — vista de plantilla al estilo
Hattrick Control: HL-2xx, pedido explícito con capturas de referencia
2026-08-14 ("un módulo así es el que quiero para Entrenamiento")."""
import asyncio
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.application.queries.training_squad import TrainingSquadQueryService
from app.domain.engines.loyalty_engine import loyalty_decimal, loyalty_level
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.main import app
from tests.conftest import seeded_session


def _run(coro):
    return asyncio.run(coro)


def _client(factory, team_id) -> TestClient:
    async def override_get_session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app)


# ── Vista de plantilla, contra el fixture real ──────────────────────────────

def test_squad_view_lists_every_active_player_for_the_current_skill() -> None:
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            return await TrainingSquadQueryService(s).squad_view(team_id)

    view = _run(go())
    assert view is not None
    assert view.skill == "passing"  # el tipo real de training.xml del fixture
    assert len(view.rows) > 0
    assert all(r.weeks_total > 0 for r in view.rows)
    assert len(view.available_skills) == 7  # las 7 habilidades técnicas


def test_squad_view_can_switch_to_any_supported_technical_skill() -> None:
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            return await TrainingSquadQueryService(s).squad_view(team_id, skill="scoring")

    view = _run(go())
    assert view.skill == "scoring"
    assert view.skill_label == "Anotación"


def test_squad_view_is_honest_about_missing_reference_points() -> None:
    """El fixture de trainingevents trae subidas confirmadas para IDs de
    prueba que no están en la plantilla activa real — ningún jugador real
    debe mostrar semanas transcurridas inventadas."""
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            return await TrainingSquadQueryService(s).squad_view(team_id)

    view = _run(go())
    assert all(r.weeks_elapsed is None for r in view.rows)
    assert all(r.has_reference is False for r in view.rows)


def test_squad_view_uses_a_real_snapshot_pop_when_trainingevents_is_unavailable() -> None:
    """A skill change seen in two real players.xml snapshots is valid fallback
    evidence; only its exact day inside the sync interval remains unknown."""
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            world = await s.scalar(select(m.WorldContext))
            team = await s.get(m.Team, team_id)
            assert world is not None and team is not None
            team.ht_league_id = world.ht_league_id

            latest = await s.scalar(
                select(m.PlayerSnapshot)
                .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
                .where(m.Player.team_id == team_id, m.Player.left_team_at.is_(None))
                .order_by(m.PlayerSnapshot.captured_at.desc())
            )
            assert latest is not None and latest.passing is not None
            values = {
                column.name: getattr(latest, column.name)
                for column in m.PlayerSnapshot.__table__.columns
                if column.name != "id"
            }
            values["captured_at"] = latest.captured_at + timedelta(days=7)
            values["passing"] = latest.passing + 1
            values["content_hash"] = b"observed-passing-pop"
            s.add(m.PlayerSnapshot(**values))
            world.refreshed_at = values["captured_at"] + timedelta(days=14)
            await s.commit()

            view = await TrainingSquadQueryService(s).squad_view(team_id, skill="passing")
            player = await s.get(m.Player, latest.player_id)
            row = next(r for r in view.rows if r.ht_player_id == player.ht_player_id)
            return row, view.notes

    row, notes = _run(go())
    assert row.has_reference is True
    assert row.weeks_elapsed == 2
    assert row.progress_pct is not None
    assert any("primera sincronización real" in note for note in notes)


def test_squad_view_includes_the_weekly_training_log() -> None:
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            return await TrainingSquadQueryService(s).squad_view(team_id)

    view = _run(go())
    assert len(view.weekly_log) > 0
    assert view.weekly_log[0].training_type  # nombre real, no vacío


def test_development_view_uses_experience_history_and_the_fixed_loyalty_curve() -> None:
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            player = await s.scalar(
                select(m.Player).where(
                    m.Player.team_id == team_id,
                    m.Player.left_team_at.is_(None),
                )
            )
            assert player is not None
            player.purchased_at = datetime.now(UTC) - timedelta(days=91)
            await s.commit()

            view = await TrainingSquadQueryService(s).development_view(team_id)
            assert view is not None
            exp_row = next(r for r in view.experience if r.ht_player_id == player.ht_player_id)
            loyalty_row = next(r for r in view.loyalty if r.ht_player_id == player.ht_player_id)
            return exp_row, loyalty_row

    exp_row, loyalty_row = _run(go())
    assert exp_row.points_per_level == 100
    assert exp_row.progress_pct is not None
    assert loyalty_row.days_in_club == 91
    assert loyalty_row.calculated_level == loyalty_level(91)
    assert loyalty_row.decimal_level == loyalty_decimal(91)
    assert loyalty_row.date_source == "transferencia"


def test_development_view_never_invents_loyalty_progress_without_a_join_date() -> None:
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            view = await TrainingSquadQueryService(s).development_view(team_id)
            assert view is not None
            return view

    view = _run(go())
    undated = [row for row in view.loyalty if row.date_source is None]
    assert undated
    assert all(row.decimal_level is None for row in undated)
    assert all(row.progress_pct is None for row in undated)
    assert any("no tienen fecha de llegada" in note for note in view.notes)


# ── Previsión por jugador ────────────────────────────────────────────────────

def test_player_levels_forecast_is_always_available_even_without_history() -> None:
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            svc = TrainingSquadQueryService(s)
            view = await svc.squad_view(team_id)
            first = view.rows[0].ht_player_id
            return await svc.player_levels(team_id, first)

    history = _run(go())
    assert history is not None
    assert len(history.forecast) > 0
    assert history.confirmed == []
    assert any("Todavía no hay subidas confirmadas" in n for n in history.notes)


def test_player_levels_forecast_chain_ends_at_the_scale_top() -> None:
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            svc = TrainingSquadQueryService(s)
            view = await svc.squad_view(team_id)
            first = view.rows[0].ht_player_id
            return await svc.player_levels(team_id, first)

    history = _run(go())
    assert history.forecast[-1].level == 20
    assert history.forecast[-1].level_name == "divino"


def test_player_levels_404s_for_a_player_outside_the_active_roster() -> None:
    async def go():
        factory, team_id = await seeded_session()
        async with factory() as s:
            return await TrainingSquadQueryService(s).player_levels(team_id, 999999999)

    assert _run(go()) is None


# ── Con una subida confirmada real, insertada a mano ────────────────────────
# El fixture de trainingevents solo trae IDs de prueba que no están en la
# plantilla activa, así que para probar el camino "semanas transcurridas SÍ
# se conocen" se inserta una subida real para un jugador real del roster —
# el mismo criterio (season × 16 + match_round) que ya usa
# TrainingContextService para validar la fórmula.

async def _seed_confirmed_pop_for_a_real_player():
    factory, team_id = await seeded_session()
    async with factory() as s:
        world = await s.scalar(select(m.WorldContext))
        assert world is not None and world.season is not None and world.match_round is not None

        # `seeded_session()` never links Team.ht_league_id to the synced
        # WorldContext (that wiring is club.py's job, not this shared
        # fixture's) — without it `squad_view()` cannot resolve "now", so
        # weeks-elapsed is honestly always null. Link them here, exactly as
        # a real teamdetails.xml sync would, so the confirmed-pop path is
        # actually reachable in this test.
        team = await s.get(m.Team, team_id)
        team.ht_league_id = world.ht_league_id
        await s.commit()

        view = await TrainingSquadQueryService(s).squad_view(team_id)
        target = next(r for r in view.rows if r.level > 0)

        # Dos semanas de temporada antes de ahora mismo.
        pop_season, pop_round = world.season, world.match_round - 2
        if pop_round < 1:
            pop_round += 16
            pop_season -= 1

        s.add(m.SkillUp(
            team_id=team_id, ht_player_id=target.ht_player_id, skill_id=7,  # passing
            old_level=target.level - 1, new_level=target.level,
            season=pop_season, match_round=pop_round, day_number=0,
        ))
        await s.commit()
    return factory, team_id, target.ht_player_id, world.season * 16 + world.match_round - (pop_season * 16 + pop_round)


def test_squad_view_computes_weeks_elapsed_from_a_real_confirmed_pop() -> None:
    async def go():
        return await _seed_confirmed_pop_for_a_real_player()

    factory, team_id, ht_player_id, expected_weeks = _run(go())

    async def reload():
        async with factory() as s:
            return await TrainingSquadQueryService(s).squad_view(team_id)

    view = _run(reload())
    row = next(r for r in view.rows if r.ht_player_id == ht_player_id)
    assert row.has_reference is True
    assert row.weeks_elapsed == expected_weeks
    assert row.progress_pct == round(expected_weeks / row.weeks_total * 100, 1)


def test_include_this_week_flag_shifts_elapsed_weeks_by_one() -> None:
    async def go():
        return await _seed_confirmed_pop_for_a_real_player()

    factory, team_id, ht_player_id, expected_weeks = _run(go())

    async def reload(include_this_week: bool):
        async with factory() as s:
            return await TrainingSquadQueryService(s).squad_view(
                team_id, include_this_week=include_this_week,
            )

    with_week = next(r for r in _run(reload(True)).rows if r.ht_player_id == ht_player_id)
    without_week = next(r for r in _run(reload(False)).rows if r.ht_player_id == ht_player_id)
    assert with_week.weeks_elapsed == expected_weeks
    assert without_week.weeks_elapsed == max(0, expected_weeks - 1)


def test_player_levels_confirmed_list_reports_the_real_pop() -> None:
    async def go():
        return await _seed_confirmed_pop_for_a_real_player()

    factory, team_id, ht_player_id, _ = _run(go())

    async def reload():
        async with factory() as s:
            return await TrainingSquadQueryService(s).player_levels(team_id, ht_player_id)

    history = _run(reload())
    assert len(history.confirmed) == 1
    pop = history.confirmed[0]
    assert pop.to_level == history.current_level
    assert pop.to_level_name == history.current_level_name
    assert not any("Todavía no hay subidas confirmadas" in n for n in history.notes)


# ── Endpoints ────────────────────────────────────────────────────────────────

def test_training_squad_endpoint_shape() -> None:
    factory, team_id = _run(seeded_session())
    client = _client(factory, team_id)
    try:
        resp = client.get(f"/api/v1/teams/{team_id}/training/squad")
        assert resp.status_code == 200
        body = resp.json()
        assert body["skill"] == "passing"
        assert len(body["players"]) > 0
        assert "weeksElapsed" in body["players"][0]
        assert "progressPct" in body["players"][0]
        assert len(body["availableSkills"]) == 7
        assert "weeklyLog" in body
    finally:
        app.dependency_overrides.clear()


def test_training_squad_endpoint_accepts_a_skill_override() -> None:
    factory, team_id = _run(seeded_session())
    client = _client(factory, team_id)
    try:
        resp = client.get(f"/api/v1/teams/{team_id}/training/squad", params={"skill": "scoring"})
        assert resp.status_code == 200
        assert resp.json()["skill"] == "scoring"
    finally:
        app.dependency_overrides.clear()


def test_training_development_endpoint_shape() -> None:
    factory, team_id = _run(seeded_session())
    client = _client(factory, team_id)
    try:
        resp = client.get(f"/api/v1/teams/{team_id}/training/development")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["experience"]) > 0
        assert len(body["loyalty"]) == len(body["experience"])
        assert "pointsPerLevel" in body["experience"][0]
        assert "daysInClub" in body["loyalty"][0]
        assert "notes" in body
    finally:
        app.dependency_overrides.clear()


def test_player_training_levels_endpoint_shape() -> None:
    factory, team_id = _run(seeded_session())
    client = _client(factory, team_id)
    try:
        squad = client.get(f"/api/v1/teams/{team_id}/training/squad").json()
        ht_player_id = squad["players"][0]["htPlayerId"]
        resp = client.get(f"/api/v1/teams/{team_id}/players/{ht_player_id}/training/levels")
        assert resp.status_code == 200
        body = resp.json()
        assert body["htPlayerId"] == ht_player_id
        assert len(body["forecast"]) > 0
        assert body["forecast"][-1]["level"] == 20
        assert "confirmed" in body
    finally:
        app.dependency_overrides.clear()


def test_player_training_levels_endpoint_404s_for_an_unknown_player() -> None:
    factory, team_id = _run(seeded_session())
    client = _client(factory, team_id)
    try:
        resp = client.get(f"/api/v1/teams/{team_id}/players/999999999/training/levels")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
