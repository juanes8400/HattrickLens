"""Tests de la ficha de jugador ampliada (HL-15x): historial real de
snapshots, histórico de rating por partido (con dedup) y distribuciones/
percentil de plantilla — contra DB real (sqlite in-memory) y fixtures CHPP
reales, mismo patrón que test_sync_flow.py.
"""
import asyncio
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.sync_team import (
    SyncPlayerDetailsCommand,
    SyncTeamCommand,
    SyncTeamHandler,
)
from app.application.queries.player_history import (
    PlayerHistoryQueryService,
    experience_category,
)
from app.infrastructure.chpp.parsers import get_parser
from app.infrastructure.db import models as m
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

FIXTURES = Path(__file__).parent / "fixtures"
PLAYER_ID = 468921494  # presente en players.xml y playerdetails.xml reales


def test_experience_category_distinguishes_secondary_cups() -> None:
    assert experience_category(3, 1) == "cup"
    assert experience_category(3, 2) == "cup_secondary"
    assert experience_category(3, 3) == "cup_secondary"


class FakeCHPP:
    async def fetch(self, file: str, version: str, **params: Any) -> dict[str, Any]:
        return get_parser(file)((FIXTURES / f"{file}.xml").read_bytes())


class NoPlayerDetailsCHPP(FakeCHPP):
    """2026-08-05: desde que `execute()` pide playerdetails.xml para toda la
    plantilla activa automáticamente (ya no depende del botón "Actualizar
    detalles de jugadores"), un `SyncTeamCommand(files=["players"])` de
    prueba ya NO simula "nunca se pidió playerdetails" por sí solo — hace
    falta este doble que se lo niegue a propósito, para las pruebas cuya
    premisa es justo esa ausencia."""
    async def fetch(self, file: str, version: str, **params: Any) -> dict[str, Any]:
        if file == "playerdetails":
            return {"chpp_error": True}
        return await super().fetch(file, version, **params)


async def _setup() -> tuple[SqlAlchemyUnitOfWork, FakeCHPP, int]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as s:
        team = m.Team(ht_team_id=537758, name="Pulgas Arrechas")
        s.add(team)
        await s.commit()
        team_id = team.id

    return SqlAlchemyUnitOfWork(factory), FakeCHPP(), team_id


def test_snapshot_history_returns_real_points_in_order() -> None:
    async def run() -> None:
        uow, chpp, team_id = await _setup()
        handler = SyncTeamHandler(uow, chpp)
        await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["players"])
        )

        async with uow as u:
            svc = PlayerHistoryQueryService(u.session)
            history = await svc.snapshot_history(PLAYER_ID)

        assert len(history) == 1
        pt = history[0]
        assert pt.tsi == 201460
        assert pt.salary == 723120
        assert pt.skills["scoring"] == 18
        assert pt.skills["experience"] == 9
        assert pt.skills["loyalty"] == 2

    asyncio.run(run())


def test_match_rating_history_dedups_same_match() -> None:
    """Sincronizar playerdetails dos veces con el mismo LastMatch (nada nuevo
    jugado) no debe duplicar la fila — HL-15x #21."""
    async def run() -> None:
        uow, chpp, team_id = await _setup()
        handler = SyncTeamHandler(uow, chpp)
        await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["players"])
        )

        cmd = SyncPlayerDetailsCommand(user_id=1, team_id=team_id, ht_player_id=PLAYER_ID)
        await handler.execute_player_details(cmd)
        await handler.execute_player_details(cmd)  # mismo LastMatch, no debe duplicar

        async with uow as u:
            svc = PlayerHistoryQueryService(u.session)
            history = await svc.match_rating_history(PLAYER_ID)

        assert len(history) == 1
        pt = history[0]
        assert pt.ht_match_id == 123456789
        assert pt.rating == 8.5
        assert pt.position_code == 13
        assert pt.played_minutes == 90

    asyncio.run(run())


def test_squad_distributions_include_all_active_players() -> None:
    async def run() -> None:
        uow, chpp, team_id = await _setup()
        handler = SyncTeamHandler(uow, chpp)
        await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["players"])
        )

        async with uow as u:
            svc = PlayerHistoryQueryService(u.session)
            dist = await svc.squad_distributions(team_id, PLAYER_ID, currency_rate=1.0)

        assert dist is not None
        assert set(dist) == {"tsi", "salary", "salaryPerTsi"}
        assert len(dist["tsi"].values) == 24
        assert dist["tsi"].own_value == 201460
        assert dist["salary"].own_value == 723120
        assert dist["salaryPerTsi"].own_value == 723120 / 201460
        # La rejilla KDE debe cubrir el rango real con margen, no estar vacía
        assert len(dist["tsi"].grid) > 0
        assert len(dist["tsi"].density) == len(dist["tsi"].grid)

    asyncio.run(run())


def test_squad_distributions_none_for_player_not_in_squad() -> None:
    async def run() -> None:
        uow, chpp, team_id = await _setup()
        handler = SyncTeamHandler(uow, chpp)
        await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["players"])
        )

        async with uow as u:
            svc = PlayerHistoryQueryService(u.session)
            dist = await svc.squad_distributions(team_id, ht_player_id=999999, currency_rate=1.0)

        assert dist is None

    asyncio.run(run())


def test_top_skill_distributions_excludes_set_pieces() -> None:
    async def run() -> None:
        uow, chpp, team_id = await _setup()
        handler = SyncTeamHandler(uow, chpp)
        await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["players"])
        )

        async with uow as u:
            svc = PlayerHistoryQueryService(u.session)
            dist = await svc.top_skill_distributions(team_id, PLAYER_ID, top_n=3)

        # skills reales del jugador: keeper 1, defending 4, playmaking 7,
        # winger 4, passing 13, scoring 18, set_pieces 9 — top 3 sin
        # set_pieces son scoring(18), passing(13), playmaking(7).
        assert dist is not None
        assert set(dist) == {"scoring", "passing", "playmaking"}
        assert "set_pieces" not in dist
        assert dist["scoring"].own_value == 18.0
        assert len(dist["scoring"].values) == 24

    asyncio.run(run())


async def _open_the_level_window_before(uow: SqlAlchemyUnitOfWork, ht_match_id: int) -> None:
    """Retrasa los snapshots del jugador a antes de ese partido.

    `experience_progress` solo cuenta partidos JUGADOS después de la primera
    vez que vimos al jugador en su nivel actual. En un sync de prueba el
    snapshot nace con la hora de ahora y el partido del fixture se jugó antes,
    así que sin esto la ventana está cerrada y no hay nada que contar — que es
    justo lo correcto, pero deja sin ejercitar el peso por minutos, que es lo
    que estas pruebas miden.
    """
    from datetime import timedelta

    from sqlalchemy import select

    async with uow as u:
        match = await u.session.scalar(
            select(m.Match).where(m.Match.ht_match_id == ht_match_id)
        )
        snapshots = (await u.session.execute(
            select(m.PlayerSnapshot)
            .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
            .where(m.Player.ht_player_id == PLAYER_ID)
        )).scalars().all()
        for snapshot in snapshots:
            snapshot.captured_at = match.played_at - timedelta(days=1)
        await u.commit()


def test_experience_progress_counts_real_matches_by_type() -> None:
    """Cruza player_match_ratings (ya poblado por execute_player_details, con
    el ht_match_id real 123456789 del fixture LastMatch) contra matches
    (match_type real) para contar partidos de liga desde el snapshot más
    antiguo con el nivel de experiencia actual (13, único snapshot, así que
    "desde siempre" en esta prueba). La fila de `matches` para ese
    ht_match_id ya no se crea a mano: `execute_player_details` la rellena
    sola (matchdetails.xml del fixture trae MatchType 1 = liga) — ver
    `test_execute_player_details_backfills_foreign_match_type`."""
    async def run() -> None:
        uow, chpp, team_id = await _setup()
        handler = SyncTeamHandler(uow, chpp)
        await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["players"])
        )
        await handler.execute_player_details(
            SyncPlayerDetailsCommand(user_id=1, team_id=team_id, ht_player_id=PLAYER_ID)
        )
        await _open_the_level_window_before(uow, 123456789)

        async with uow as u:
            svc = PlayerHistoryQueryService(u.session)
            progress = await svc.experience_progress(PLAYER_ID)

        assert progress is not None
        assert progress.breakdown.get("league", 0) > 0
        assert progress.percent >= 0

    asyncio.run(run())


def test_execute_player_details_backfills_foreign_match_type() -> None:
    """2026-08-05, pedido explícitamente: LastMatch puede apuntar a un
    partido que el club nunca sincronizó (selección nacional, Masters,
    juvenil) — matches.xml solo trae los partidos del propio equipo.
    `execute_player_details` debe rellenar esa fila de `matches` pidiendo
    matchdetails.xml, una sola vez, para que ese partido deje de ser
    invisible para experience_progress."""
    async def run() -> None:
        from sqlalchemy import select

        uow, chpp, team_id = await _setup()
        handler = SyncTeamHandler(uow, chpp)
        await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["players"])
        )
        cmd = SyncPlayerDetailsCommand(user_id=1, team_id=team_id, ht_player_id=PLAYER_ID)
        await handler.execute_player_details(cmd)
        await handler.execute_player_details(cmd)  # segunda vez: no debe duplicar/fallar

        async with uow as u:
            match = await u.session.scalar(
                select(m.Match).where(m.Match.ht_match_id == 123456789)
            )

        assert match is not None
        assert match.match_type == 1  # MatchType del fixture matchdetails.xml

    asyncio.run(run())


def test_experience_progress_weights_by_minutes_played() -> None:
    """2026-08-05, pedido explícitamente: jugar menos de 90 minutos da puntos
    proporcionales (jugar 45 de 90 = mitad de los puntos de esa competencia),
    nunca el partido completo por solo haber salido de titular."""
    async def run() -> None:
        from sqlalchemy import select

        uow, chpp, team_id = await _setup()
        handler = SyncTeamHandler(uow, chpp)
        await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["players"])
        )
        await handler.execute_player_details(
            SyncPlayerDetailsCommand(user_id=1, team_id=team_id, ht_player_id=PLAYER_ID)
        )

        async with uow as u:
            rating = await u.session.scalar(
                select(m.PlayerMatchRating).where(m.PlayerMatchRating.ht_match_id == 123456789)
            )
            rating.played_minutes = 45  # medio partido
            await u.commit()
        await _open_the_level_window_before(uow, 123456789)

        async with uow as u:
            svc = PlayerHistoryQueryService(u.session)
            progress = await svc.experience_progress(PLAYER_ID)

        # matchdetails.xml (fixture) da MatchType 1 = liga (3.5 puntos completos)
        assert progress is not None
        assert progress.breakdown["league"] == pytest.approx(1.75)
        assert progress.match_counts["league"] == 1

    asyncio.run(run())


def test_experience_progress_never_awards_more_than_full_match() -> None:
    """Más de 90 minutos (prórroga) no da un bono — el tope sigue siendo el
    100% de los puntos de esa competencia."""
    async def run() -> None:
        from sqlalchemy import select

        uow, chpp, team_id = await _setup()
        handler = SyncTeamHandler(uow, chpp)
        await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["players"])
        )
        await handler.execute_player_details(
            SyncPlayerDetailsCommand(user_id=1, team_id=team_id, ht_player_id=PLAYER_ID)
        )

        async with uow as u:
            rating = await u.session.scalar(
                select(m.PlayerMatchRating).where(m.PlayerMatchRating.ht_match_id == 123456789)
            )
            rating.played_minutes = 120  # prórroga
            await u.commit()
        await _open_the_level_window_before(uow, 123456789)

        async with uow as u:
            svc = PlayerHistoryQueryService(u.session)
            progress = await svc.experience_progress(PLAYER_ID)

        assert progress is not None
        assert progress.breakdown["league"] == pytest.approx(3.5)  # tope, no 4.67

    asyncio.run(run())


def test_experience_progress_detects_a_national_cap_never_captured_by_lastmatch() -> None:
    """2026-08-05, pedido explícitamente: si Caps sube más de lo que
    player_match_ratings puede explicar (el club jugó después y LastMatch
    quedó sobrescrito antes del siguiente sync), ese partido de selección
    sigue contando como detectado — sin inventar sus puntos exactos."""
    async def run() -> None:
        from datetime import timedelta

        from sqlalchemy import select

        uow, _default_chpp, team_id = await _setup()
        # `execute()` ya pide playerdetails.xml para toda la plantilla activa
        # sola (ver `NoPlayerDetailsCHPP`) — esta prueba simula justo el caso
        # contrario, así que se le niega esa respuesta a propósito.
        handler = SyncTeamHandler(uow, NoPlayerDetailsCHPP())
        await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["players"])
        )

        async with uow as u:
            player = await u.session.scalar(
                select(m.Player).where(m.Player.ht_player_id == PLAYER_ID)
            )
            base = await u.session.scalar(
                select(m.PlayerSnapshot)
                .where(m.PlayerSnapshot.player_id == player.id)
                .order_by(m.PlayerSnapshot.captured_at.desc())
                .limit(1)
            )
            # Snapshot "de antes": mismo nivel de experiencia, caps=2 —
            # ancla el `since_date` del que parte experience_progress.
            u.session.add(m.PlayerSnapshot(
                sync_id=base.sync_id, player_id=player.id,
                captured_at=base.captured_at - timedelta(days=7),
                age_years=base.age_years, age_days=base.age_days,
                tsi=base.tsi, form=base.form, stamina=base.stamina,
                experience=base.experience, salary=base.salary,
                injury_level=base.injury_level, career_caps=2,
                content_hash=b"\x01" * 32,
            ))
            # Snapshot actual: caps subió a 3 — un partido de selección se
            # jugó, pero nunca vimos su LastMatch (ningún PlayerMatchRating
            # nuevo desde entonces).
            base.career_caps = 3
            base.captured_at = base.captured_at + timedelta(hours=1)
            await u.commit()

        async with uow as u:
            svc = PlayerHistoryQueryService(u.session)
            progress = await svc.experience_progress(PLAYER_ID)

        assert progress is not None
        assert progress.unscored_national_matches == 1
        assert progress.breakdown == {}  # ningún partido puntuable visto

    asyncio.run(run())


def test_experience_progress_none_without_history() -> None:
    async def run() -> None:
        uow, chpp, team_id = await _setup()
        async with uow as u:
            svc = PlayerHistoryQueryService(u.session)
            progress = await svc.experience_progress(999999)
        assert progress is None

    asyncio.run(run())


def test_dominant_skill_percentile_of_known_player() -> None:
    async def run() -> None:
        uow, chpp, team_id = await _setup()
        handler = SyncTeamHandler(uow, chpp)
        await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=537758, files=["players"])
        )

        async with uow as u:
            svc = PlayerHistoryQueryService(u.session)
            pct = await svc.dominant_skill_percentile(team_id, PLAYER_ID)

        assert pct is not None
        assert pct["skill"] == "scoring"  # su skill más alto es 18 (scoring)
        assert pct["value"] == 18.0
        assert pct["squadSize"] == 24
        assert 0.0 <= pct["percentile"] <= 100.0

    asyncio.run(run())


def _seed_experience_case(
    snapshots: list[tuple[str, int]], matches: list[tuple[str, str]]
) -> tuple[async_sessionmaker, int]:
    """Monta a mano la historia de UN jugador: (captura, experiencia) y
    (jugado_en, capturado_en) por partido de liga. Los timestamps son el
    objeto del test, así que no salen de un fixture CHPP."""
    from datetime import datetime

    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    def ts(text: str) -> datetime:
        return datetime.fromisoformat(text)

    async def build() -> int:
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)
        async with factory() as s:
            team = m.Team(ht_team_id=537758, name="Pulgas Arrechas")
            s.add(team)
            await s.flush()
            player = m.Player(
                ht_player_id=483141997, team_id=team.id,
                first_name="Enyo", last_name="Kasaliyski",
            )
            s.add(player)
            sync = m.Sync(team_id=team.id, user_id=1, kind="players",
                          status="completed", started_at=ts(snapshots[0][0]))
            s.add(sync)
            await s.flush()

            for captured, level in snapshots:
                s.add(m.PlayerSnapshot(
                    sync_id=sync.id, player_id=player.id, captured_at=ts(captured),
                    age_years=25, age_days=0, tsi=1000, form=5, stamina=7,
                    experience=level, salary=1000, injury_level=-1,
                    is_transfer_listed=False, specialty=0, loyalty=1, leadership=3,
                    agreeability=2, aggressiveness=2, honesty=2, mother_club_bonus=False,
                    country_id=1, league_goals=0, cup_goals=0, friendlies_goals=0,
                    career_goals=0, career_hattricks=0, career_assists=0,
                    player_trainer_skill_level=0, player_trainer_type=0,
                    content_hash=f"h{captured}".encode(),
                ))
            for i, (played, captured) in enumerate(matches):
                ht_match_id = 900000 + i
                s.add(m.Match(
                    ht_match_id=ht_match_id, played_at=ts(played),
                    match_type=1, status="FINISHED", home_team_ht_id=537758,
                    away_team_ht_id=1, home_team_name="Pulgas", away_team_name="Rival",
                    home_goals=1, away_goals=0, cup_level=0, cup_level_index=0,
                ))
                s.add(m.PlayerMatchRating(
                    player_id=player.id, ht_match_id=ht_match_id, position_code="im",
                    played_minutes=90, rating=5.0, captured_at=ts(captured),
                ))
            await s.commit()
        return player.id

    asyncio.run(build())
    return factory, 483141997


def test_the_match_that_caused_the_level_up_does_not_count_for_the_next_one() -> None:
    """Caso real de Enyo Kasaliyski, 2026-08-16.

    Jugó liga el 16/08 23:40 y subió a experiencia 5; el sync del 17/08 00:22
    trajo a la vez el snapshot con el nivel nuevo Y la ficha de ese partido,
    con el mismo `captured_at`. Filtrando por la marca de sincronización, el
    partido que pagó el nivel se contaba otra vez para el siguiente. Al subir
    de nivel el contador tiene que arrancar de cero.
    """
    factory, ht_player_id = _seed_experience_case(
        snapshots=[
            ("2026-08-15 22:02:41", 4),
            ("2026-08-17 00:22:12", 5),
        ],
        matches=[
            ("2026-08-09 23:40:00", "2026-08-10 00:41:30"),
            ("2026-08-16 23:40:00", "2026-08-17 00:22:12"),
        ],
    )

    async def run() -> None:
        async with factory() as s:
            progress = await PlayerHistoryQueryService(s).experience_progress(ht_player_id)
        assert progress is not None
        assert progress.match_counts.get("league", 0) == 0
        assert progress.points == 0.0
        assert progress.percent == 0

    asyncio.run(run())


def test_matches_played_after_the_level_up_do_count() -> None:
    """El reverso: reiniciar no puede significar dejar de contar. El partido
    posterior a la subida sí abre el nivel nuevo."""
    factory, ht_player_id = _seed_experience_case(
        snapshots=[
            ("2026-08-15 22:02:41", 4),
            ("2026-08-17 00:22:12", 5),
            ("2026-08-24 00:30:00", 5),
        ],
        matches=[
            ("2026-08-16 23:40:00", "2026-08-17 00:22:12"),
            ("2026-08-23 23:40:00", "2026-08-24 00:30:00"),
        ],
    )

    async def run() -> None:
        async with factory() as s:
            progress = await PlayerHistoryQueryService(s).experience_progress(ht_player_id)
        assert progress is not None
        assert progress.match_counts.get("league", 0) == 1

    asyncio.run(run())


def test_a_second_sync_in_the_same_week_does_not_swallow_matches_after_the_pop() -> None:
    """El corte se busca sobre snapshots crudos, no sobre la última lectura de
    cada semana: si subes el martes y vuelves a sincronizar el viernes, el
    partido del miércoles sigue contando para el nivel nuevo."""
    factory, ht_player_id = _seed_experience_case(
        snapshots=[
            ("2026-08-10 09:00:00", 4),   # lunes, nivel viejo
            ("2026-08-11 09:00:00", 5),   # martes, sube
            ("2026-08-14 09:00:00", 5),   # viernes, misma semana ISO
        ],
        matches=[
            ("2026-08-10 23:40:00", "2026-08-11 09:00:00"),  # el que provocó la subida
            ("2026-08-12 23:40:00", "2026-08-14 09:00:00"),  # miércoles, ya del nivel nuevo
        ],
    )

    async def run() -> None:
        async with factory() as s:
            progress = await PlayerHistoryQueryService(s).experience_progress(ht_player_id)
        assert progress is not None
        assert progress.match_counts.get("league", 0) == 1

    asyncio.run(run())
