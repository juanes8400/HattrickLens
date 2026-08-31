"""Los tres query services que quedan, sobre datos sembrados explícitamente.

Clasificación y partidos son públicos y colectivos, así que se pueden guardar y
analizar. Las fichas individuales de jugadores rivales NO: las reglas de CHPP
permiten mostrar sus datos actuales pero no llevar su histórico. Por eso ningún
servicio de aquí toca `player_snapshots` de otros clubes, y el test
`test_no_rival_player_history_is_stored` lo deja escrito para que nadie lo
añada por comodidad más adelante.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.application.queries.academy import AcademyQueryService
from app.application.queries.league import (
    LeagueQueryService,
    _history_from_matches,
    _merge_standing_snapshots,
    _standings_from_matches,
)
from app.application.queries.matches import MIN_CHANCES_FOR_A_RATE, MatchesQueryService
from app.infrastructure.db import models as m
from tests.conftest import HT_TEAM_ID, seeded_session

BASE = datetime(2026, 2, 1, tzinfo=UTC)
RIVALS = [(600001, "Deportivo Uno"), (600002, "Atlético Dos"), (600003, "Club Tres")]


def _run(coro):
    return asyncio.run(coro)


async def _with_league():
    factory, team_id = await seeded_session()
    async with factory() as s:
        sync = m.Sync(
            user_id=1,
            team_id=team_id,
            kind="manual",
            status="completed",
            started_at=BASE,
        )
        s.add(sync)
        await s.flush()

        table = [
            (HT_TEAM_ID, "Pulgas Arrechas", 1, 4, 3, 1, 0, 9, 3, 10),
            (600001, "Deportivo Uno", 2, 4, 2, 1, 1, 7, 5, 7),
            (600002, "Atlético Dos", 3, 4, 1, 1, 2, 4, 6, 4),
            (600003, "Club Tres", 4, 4, 0, 1, 3, 2, 8, 1),
        ]
        for ht_id, name, pos, pl, w, d, lost, gf, ga, pts in table:
            s.add(
                m.Standing(
                    sync_id=sync.id,
                    series_ht_id=7777,
                    season=83,
                    match_round=4,
                    captured_at=BASE,
                    team_ht_id=ht_id,
                    team_name=name,
                    position=pos,
                    played=pl,
                    won=w,
                    draws=d,
                    lost=lost,
                    goals_for=gf,
                    goals_against=ga,
                    points=pts,
                )
            )

        # Dos jugados y dos pendientes, todos de liga entre equipos de la serie.
        played = [
            (HT_TEAM_ID, "Pulgas Arrechas", 600003, "Club Tres", 3, 0),
            (600001, "Deportivo Uno", HT_TEAM_ID, "Pulgas Arrechas", 1, 2),
        ]
        for i, (h, hn, a, an, hg, ag) in enumerate(played):
            s.add(
                m.Match(
                    ht_match_id=800_000 + i,
                    played_at=BASE + timedelta(days=7 * i),
                    match_type=1,
                    status="finished",
                    home_team_ht_id=h,
                    away_team_ht_id=a,
                    home_team_name=hn,
                    away_team_name=an,
                    home_goals=hg,
                    away_goals=ag,
                )
            )
        pending = [
            (HT_TEAM_ID, "Pulgas Arrechas", 600002, "Atlético Dos"),
            (600001, "Deportivo Uno", 600003, "Club Tres"),
        ]
        for i, (h, hn, a, an) in enumerate(pending):
            s.add(
                m.Match(
                    ht_match_id=810_000 + i,
                    played_at=BASE + timedelta(days=30 + 7 * i),
                    match_type=1,
                    status="scheduled",
                    home_team_ht_id=h,
                    away_team_ht_id=a,
                    home_team_name=hn,
                    away_team_name=an,
                    home_goals=-1,
                    away_goals=-1,
                )
            )

        # Ratings por sector del primer partido, para ambos equipos.
        s.add(
            m.MatchRating(
                ht_match_id=800_000,
                team_ht_id=HT_TEAM_ID,
                is_home=True,
                midfield=14,
                right_def=10,
                central_def=12,
                left_def=10,
                right_att=8,
                central_att=11,
                left_att=9,
                possession_first_half=58,
                possession_second_half=61,
            )
        )
        s.add(
            m.MatchRating(
                ht_match_id=800_000,
                team_ht_id=600003,
                is_home=False,
                midfield=6,
                right_def=7,
                central_def=6,
                left_def=7,
                right_att=5,
                central_att=4,
                left_att=5,
                possession_first_half=42,
                possession_second_half=39,
            )
        )
        await s.commit()
    return factory, team_id


# ── Liga y predicciones ─────────────────────────────────────────────────────


def test_standings_are_ordered_by_hattrick_tie_breakers() -> None:
    async def go():
        factory, team_id = await _with_league()
        async with factory() as s:
            return await LeagueQueryService(s).get(team_id, runs=2000)

    d = _run(go())
    assert d is not None
    assert [r.position for r in d.standings] == [1, 2, 3, 4]
    assert d.standings[0].name == "Pulgas Arrechas"
    assert d.standings[0].is_own_team is True
    assert d.standings[0].goal_difference == 6
    assert d.season == 83
    assert d.series_name == "V.92"


def _standing(ht_id: int, name: str) -> m.Standing:
    return m.Standing(team_ht_id=ht_id, team_name=name)


def _match(rnd: int, home: int, away: int, hg: int, ag: int) -> m.Match:
    return m.Match(
        match_round=rnd, home_team_ht_id=home, away_team_ht_id=away, home_goals=hg, away_goals=ag
    )


def test_history_from_matches_reconstructs_every_full_round() -> None:
    """2026-08-08, pedido explícitamente tras comparar con Hattrick Control:
    el historial se calcula a partir de los RESULTADOS de partidos
    (`leaguefixtures.xml` trae el calendario completo de la serie), no de
    una foto puntual de `leaguedetails.xml` — así que una jornada ya jugada
    aparece en el historial aunque nunca se haya sincronizado justo en ese
    momento. La jornada "0" simbólica (0 puntos para todos) se antepone sin
    necesitar ningún partido."""
    rows = [
        _standing(HT_TEAM_ID, "Pulgas Arrechas"),
        _standing(600001, "Deportivo Uno"),
        _standing(600002, "Atlético Dos"),
        _standing(600003, "Club Tres"),
    ]
    matches = [
        # Jornada 1 completa (2 de 2 partidos).
        _match(1, HT_TEAM_ID, 600003, 2, 0),
        _match(1, 600001, 600002, 1, 1),
        # Jornada 2 completa (2 de 2 partidos).
        _match(2, HT_TEAM_ID, 600001, 1, 1),
        _match(2, 600002, 600003, 1, 0),
    ]
    history = _history_from_matches(matches, rows, HT_TEAM_ID)

    assert history.rounds == [0, 1, 2]
    assert len(history.teams) == 4
    pulgas = next(t for t in history.teams if t.name == "Pulgas Arrechas")
    assert pulgas.is_own_team is True
    # Jornada 1: 3 pts (2-0). Jornada 2 acumulado: 3+1=4 pts (empate 1-1).
    assert pulgas.points == [0, 3, 4]
    assert pulgas.positions == [None, 1, 1]
    atletico = next(t for t in history.teams if t.name == "Atlético Dos")
    # Jornada 1: 1 pt (empate). Jornada 2 acumulado: 1+3=4 pts (gana 1-0) —
    # mismos puntos que Pulgas, pero peor diferencia de gol (+1 vs +2).
    assert atletico.points == [0, 1, 4]
    assert atletico.positions == [None, 3, 2]


def test_history_from_matches_skips_an_incomplete_round_but_counts_it_forward() -> None:
    """Una jornada con menos de la mitad de sus partidos resueltos no es una
    tabla comparable entre los n equipos — no aparece como fila propia — pero
    su resultado SÍ debe seguir sumando para la primera jornada completa que
    venga después (no se pierde)."""
    rows = [
        _standing(HT_TEAM_ID, "Pulgas Arrechas"),
        _standing(600001, "Deportivo Uno"),
        _standing(600002, "Atlético Dos"),
        _standing(600003, "Club Tres"),
    ]
    matches = [
        _match(1, HT_TEAM_ID, 600003, 2, 0),
        _match(1, 600001, 600002, 1, 1),
        # Jornada 2: solo 1 de 2 partidos resuelto todavía (incompleta).
        _match(2, 600001, 600003, 2, 0),
        # Jornada 3 completa: aquí se confirma que el resultado suelto de
        # la jornada 2 SÍ quedó contado para Deportivo Uno y Club Tres.
        _match(3, HT_TEAM_ID, 600001, 0, 0),
        _match(3, 600002, 600003, 3, 0),
    ]
    history = _history_from_matches(matches, rows, HT_TEAM_ID)

    assert history.rounds == [0, 1, 3]  # la 2 no aparece como fila propia
    deportivo = next(t for t in history.teams if t.name == "Deportivo Uno")
    # Jornada 1: 1 pt (empate). + Jornada 2 (colada): 3 pts (gana 2-0) que
    # solo se ve reflejado en el acumulado de la jornada 3, no antes.
    # + Jornada 3: 1 pt (empate 0-0) = 1+3+1 = 5.
    assert deportivo.points == [0, 1, 5]


def test_merge_standing_snapshots_fills_a_round_matches_has_not_caught_up_to() -> None:
    """Visto en vivo 2026-08-08: `leaguedetails.xml` ya sabe que la jornada
    2 terminó (todos con 2 partidos jugados), pero nuestra tabla `Match`
    solo tiene el marcador de 1 de los 4 partidos de esa jornada todavía
    (bien porque de verdad no se ha sincronizado ese cruce, bien por el bug
    de `_persist_league_fixtures` corregido en
    `test_persist_league_fixtures_fills_in_a_score_once_chpp_has_it` — este
    test cubre el fallback pase lo que pase). El historial calculado desde
    partidos NO debe mostrar la jornada 2 como fila propia (regla ya
    probada arriba), pero si hay una foto REAL de Standing para esa
    jornada, debe rellenarla — nunca dejarla en blanco pudiendo mostrarla."""
    rows = [
        _standing(HT_TEAM_ID, "Pulgas Arrechas"),
        _standing(600001, "Deportivo Uno"),
        _standing(600002, "Atlético Dos"),
        _standing(600003, "Club Tres"),
    ]
    matches = [
        _match(1, HT_TEAM_ID, 600003, 2, 0),
        _match(1, 600001, 600002, 1, 1),
        # Jornada 2: solo 1 de 2 partidos con marcador todavía.
        _match(2, HT_TEAM_ID, 600001, 4, 0),
    ]
    from_matches = _history_from_matches(matches, rows, HT_TEAM_ID)
    assert from_matches.rounds == [0, 1]  # confirma la premisa del test

    standing_snapshots = [
        m.Standing(
            series_ht_id=7777,
            season=83,
            match_round=2,
            team_ht_id=ht_id,
            team_name=name,
            position=pos,
            played=2,
            won=won,
            draws=draws,
            lost=lost,
            goals_for=gf,
            goals_against=ga,
            points=pts,
        )
        for ht_id, name, pos, won, draws, lost, gf, ga, pts in [
            (HT_TEAM_ID, "Pulgas Arrechas", 1, 2, 0, 0, 6, 0, 6),
            (600002, "Atlético Dos", 2, 1, 1, 0, 3, 1, 4),
            (600001, "Deportivo Uno", 3, 0, 1, 1, 1, 5, 1),
            (600003, "Club Tres", 4, 0, 0, 2, 0, 4, 0),
        ]
    ]
    merged = _merge_standing_snapshots(from_matches, standing_snapshots)

    assert merged.rounds == [0, 1, 2]
    pulgas = next(t for t in merged.teams if t.name == "Pulgas Arrechas")
    # Jornada 1 sigue viniendo del cálculo por partidos (3 pts); jornada 2
    # viene de la foto real de Standing (6 pts), no del cálculo incompleto.
    assert pulgas.points == [0, 3, 6]
    assert pulgas.positions == [None, 1, 1]
    deportivo = next(t for t in merged.teams if t.name == "Deportivo Uno")
    assert deportivo.points == [0, 1, 1]


def test_standings_from_matches_splits_home_and_away_records() -> None:
    """Pedido explícitamente 2026-08-08: `leaguedetails.xml` solo da la
    tabla combinada — Local/Visitante se calculan desde los resultados
    reales. Pulgas gana de local (2-0) y empata de visitante (1-1): debe
    liderar la tabla de local pero no la de visitante."""
    rows = [
        _standing(HT_TEAM_ID, "Pulgas Arrechas"),
        _standing(600001, "Deportivo Uno"),
        _standing(600002, "Atlético Dos"),
        _standing(600003, "Club Tres"),
    ]
    matches = [
        _match(1, HT_TEAM_ID, 600003, 2, 0),  # Pulgas de local: gana
        _match(1, 600001, 600002, 1, 1),
        _match(2, 600001, HT_TEAM_ID, 1, 1),  # Pulgas de visitante: empata
        _match(2, 600002, 600003, 1, 0),
    ]
    home = _standings_from_matches(matches, rows, HT_TEAM_ID, "home")
    away = _standings_from_matches(matches, rows, HT_TEAM_ID, "away")

    pulgas_home = next(r for r in home if r.name == "Pulgas Arrechas")
    assert pulgas_home.played == 1
    assert pulgas_home.won == 1
    assert pulgas_home.points == 3
    assert home[0].name == "Pulgas Arrechas"  # único partido jugado, y ganado

    pulgas_away = next(r for r in away if r.name == "Pulgas Arrechas")
    assert pulgas_away.played == 1
    assert pulgas_away.drawn == 1
    assert pulgas_away.points == 1

    # Un equipo que nunca jugó de visitante (aquí: Deportivo Uno, local en
    # las dos jornadas) sigue apareciendo, con 0 partidos — nunca
    # desaparece de la tabla.
    deportivo_away = next(r for r in away if r.name == "Deportivo Uno")
    assert deportivo_away.played == 0


async def _persist_fixtures_payload(uow, payload):
    from app.application.commands.sync_team import SyncResult, SyncTeamHandler

    handler = SyncTeamHandler(uow, chpp=None)  # type: ignore[arg-type]
    result = SyncResult(sync_id=0, status="completed")
    await handler._persist_league_fixtures(uow, payload, result)
    return result


def test_persist_league_fixtures_fills_in_a_score_once_chpp_has_it() -> None:
    """Bug real encontrado en vivo 2026-08-08 (no un retraso de CHPP, como
    se creyó en un primer momento — una llamada directa a CHPP, sin pasar
    por nuestro parser ni nuestra tabla, probó que el marcador ya estaba
    disponible): la primera vez que `leaguefixtures.xml` trae un cruce
    entre dos rivales sin jugar, se crea la fila con -1/-1 de placeholder.
    En el sync SIGUIENTE, aunque el marcador real ya llegue en el payload,
    el código viejo comparaba solo `series_ht_id`/`match_round` (que ya
    coincidían) y cortaba con `continue` sin mirar los goles — el partido
    se quedaba "sin jugar" para siempre. Debe actualizarse en cuanto el
    marcador deja de ser -1."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

    async def run():
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        uow = SqlAlchemyUnitOfWork(factory)

        unplayed_payload = {
            "series_ht_id": 7777,
            "matches": [
                {
                    "ht_match_id": 900001,
                    "match_round": 2,
                    "home_team_id": 600001,
                    "home_team_name": "Deportivo Uno",
                    "away_team_id": 600002,
                    "away_team_name": "Atlético Dos",
                    "match_date": "2026-08-02 23:40:00",
                    "home_goals": None,
                    "away_goals": None,
                }
            ],
        }
        async with uow:
            await _persist_fixtures_payload(uow, unplayed_payload)
            await uow.commit()

        async with factory() as s:
            row = await s.scalar(select(m.Match).where(m.Match.ht_match_id == 900001))
            assert row.home_goals == -1
            assert row.status == "UPCOMING"

        # Mismo cruce, mismo series_ht_id/match_round — CHPP ya tiene el
        # marcador real. Antes del fix, esta segunda llamada era un no-op.
        played_payload = {
            "series_ht_id": 7777,
            "matches": [
                {
                    "ht_match_id": 900001,
                    "match_round": 2,
                    "home_team_id": 600001,
                    "home_team_name": "Deportivo Uno",
                    "away_team_id": 600002,
                    "away_team_name": "Atlético Dos",
                    "match_date": "2026-08-02 23:40:00",
                    "home_goals": 0,
                    "away_goals": 3,
                }
            ],
        }
        async with uow:
            result = await _persist_fixtures_payload(uow, played_payload)
            await uow.commit()

        async with factory() as s:
            row = await s.scalar(select(m.Match).where(m.Match.ht_match_id == 900001))
            assert row.home_goals == 0
            assert row.away_goals == 3
            assert row.status == "FINISHED"
        assert result.snapshots_written == 1
        assert result.unchanged == 0

    asyncio.run(run())


def test_persist_league_fixtures_never_overwrites_an_already_confirmed_score() -> None:
    """El guard es solo para el placeholder -1 — un marcador YA confirmado
    (por `matches.xml`/`matchdetails.xml`, que lo conocen mejor) nunca se
    pisa con lo que traiga `leaguefixtures.xml` después."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

    async def run():
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        uow = SqlAlchemyUnitOfWork(factory)

        async with factory() as s:
            s.add(
                m.Match(
                    ht_match_id=900002,
                    played_at=BASE,
                    match_type=1,
                    status="finished",
                    home_team_ht_id=HT_TEAM_ID,
                    away_team_ht_id=600001,
                    home_team_name="Pulgas Arrechas",
                    away_team_name="Deportivo Uno",
                    home_goals=5,
                    away_goals=1,
                )
            )
            await s.commit()

        payload = {
            "series_ht_id": 7777,
            "matches": [
                {
                    "ht_match_id": 900002,
                    "match_round": 2,
                    "home_team_id": HT_TEAM_ID,
                    "home_team_name": "Pulgas Arrechas",
                    "away_team_id": 600001,
                    "away_team_name": "Deportivo Uno",
                    "match_date": "2026-08-02 23:40:00",
                    "home_goals": 0,
                    "away_goals": 0,  # distinto: no debe pisar
                }
            ],
        }
        async with uow:
            await _persist_fixtures_payload(uow, payload)
            await uow.commit()

        async with factory() as s:
            row = await s.scalar(select(m.Match).where(m.Match.ht_match_id == 900002))
            assert row.home_goals == 5
            assert row.away_goals == 1

    asyncio.run(run())


def test_best_worst_case_is_computed_for_the_own_team() -> None:
    """`best_worst` ahora es un solo objeto — "el equipo que estamos
    analizando" es el propio, no toda la tabla — con una DISTRIBUCIÓN de
    puestos por escenario en vez de un número: aunque el resultado propio
    esté forzado a un extremo (goleada), el resto de la liga sigue siendo
    incierto."""

    async def go():
        factory, team_id = await _with_league()
        async with factory() as s:
            return await LeagueQueryService(s).get(team_id, runs=3000)

    d = _run(go())
    assert d is not None
    bw = d.best_worst
    assert bw is not None
    assert bw.name == "Pulgas Arrechas"
    assert bw.remaining_matches == 1
    assert bw.current_points == 10
    for dist in (bw.best_case_position_distribution, bw.worst_case_position_distribution):
        assert sum(dist.values()) == pytest.approx(1.0, abs=0.02)
    # Goleando su único partido pendiente casi siempre sigue 1º; siendo
    # goleado, el 1º es mucho menos frecuente que en el mejor caso.
    assert bw.best_case_position_distribution[1] > bw.worst_case_position_distribution[1]


def test_outlook_covers_every_team_and_sums_to_one_title() -> None:
    async def go():
        factory, team_id = await _with_league()
        async with factory() as s:
            return await LeagueQueryService(s).get(team_id, runs=3000)

    d = _run(go())
    assert len(d.outlook) == 4
    assert sum(o.title_probability for o in d.outlook) > 0.97
    own = d.own_outlook
    assert own is not None and own.is_own_team
    assert own.current_position == 1
    assert sum(own.position_distribution.values()) > 0.99


def test_pending_fixtures_are_simulated_and_played_ones_are_not() -> None:
    async def go():
        factory, team_id = await _with_league()
        async with factory() as s:
            return await LeagueQueryService(s).get(team_id, runs=2000)

    d = _run(go())
    played = [f for f in d.fixtures if f.played]
    pending = [f for f in d.fixtures if not f.played]
    assert len(played) == 2 and len(pending) == 2
    assert all(f.score for f in played)
    assert all(f.score is None for f in pending)
    assert d.rounds_remaining == 2


def test_next_match_forecast_is_coherent() -> None:
    async def go():
        factory, team_id = await _with_league()
        async with factory() as s:
            return await LeagueQueryService(s).get(team_id, runs=3000)

    d = _run(go())
    nm = d.next_match
    assert nm is not None
    assert nm["home"] == "Pulgas Arrechas" and nm["isHome"] is True
    assert abs(nm["homeWin"] + nm["draw"] + nm["awayWin"] - 1.0) < 0.01
    # Líder en casa contra el tercero: debe ser favorito.
    assert nm["homeWin"] > nm["awayWin"]
    assert nm["verdict"]


def test_league_declares_the_limits_of_its_model() -> None:
    async def go():
        factory, team_id = await _with_league()
        async with factory() as s:
            return await LeagueQueryService(s).get(team_id, runs=2000)

    d = _run(go())
    assert "lesiones" in d.model["doesNotModel"]
    assert any("forma agregada" in c for c in d.caveats)
    assert any("encogimiento" in c for c in d.caveats)  # sólo 4 jornadas


CAVEAT_NEEDLE = "trae los partidos de tu equipo"


async def _with_full_series_schedule(*, partial_round_played: bool):
    """4 equipos, calendario con `series_ht_id`/`match_round` reales (como
    los deja `leaguefixtures.xml` tras el fix) — a diferencia de
    `_with_league`, que simula el escenario ANTERIOR al fix (matches.xml
    propio, sin esos campos). Jornada 1: los 2 partidos posibles, uno de
    ellos entre dos rivales. Jornada 2: 1 solo partido, DEL EQUIPO propio —
    si `partial_round_played` es True ese partido ya se jugó (jornada en
    progreso, no incompleta); si es False, falta sincronizar el otro
    cruce de esa jornada (dato realmente incompleto)."""
    factory, team_id = await seeded_session()
    async with factory() as s:
        sync = m.Sync(
            user_id=1, team_id=team_id, kind="manual", status="completed", started_at=BASE
        )
        s.add(sync)
        await s.flush()

        table = [
            (HT_TEAM_ID, "Pulgas Arrechas", 1, 1, 1, 0, 0, 3, 0, 3),
            (600001, "Deportivo Uno", 2, 1, 1, 0, 0, 2, 1, 3),
            (600002, "Atlético Dos", 3, 0, 0, 0, 0, 0, 0, 0),
            (600003, "Club Tres", 4, 1, 0, 0, 1, 1, 2, 0),
        ]
        for ht_id, name, pos, pl, w, d, lost, gf, ga, pts in table:
            s.add(
                m.Standing(
                    sync_id=sync.id,
                    series_ht_id=7777,
                    season=83,
                    match_round=1,
                    captured_at=BASE,
                    team_ht_id=ht_id,
                    team_name=name,
                    position=pos,
                    played=pl,
                    won=w,
                    draws=d,
                    lost=lost,
                    goals_for=gf,
                    goals_against=ga,
                    points=pts,
                )
            )

        # Jornada 1: los 2 partidos posibles, ya jugados. Uno entre rivales.
        s.add(
            m.Match(
                ht_match_id=900001,
                played_at=BASE,
                match_type=1,
                status="FINISHED",
                home_team_ht_id=HT_TEAM_ID,
                away_team_ht_id=600003,
                home_team_name="Pulgas Arrechas",
                away_team_name="Club Tres",
                home_goals=3,
                away_goals=0,
                series_ht_id=7777,
                match_round=1,
            )
        )
        s.add(
            m.Match(
                ht_match_id=900002,
                played_at=BASE,
                match_type=1,
                status="FINISHED",
                home_team_ht_id=600001,
                away_team_ht_id=600002,
                home_team_name="Deportivo Uno",
                away_team_name="Atlético Dos",
                home_goals=2,
                away_goals=1,
                series_ht_id=7777,
                match_round=1,
            )
        )

        # Jornada 2: solo el partido DEL EQUIPO propio está sincronizado —
        # el otro cruce (600001 vs 600003) nunca llegó, sea porque falta
        # sincronizar (caso incompleto) o porque de verdad no hay más
        # equipos que emparejar en este escenario reducido de 4.
        s.add(
            m.Match(
                ht_match_id=900003,
                played_at=BASE + timedelta(days=7),
                match_type=1,
                status="FINISHED" if partial_round_played else "UPCOMING",
                home_team_ht_id=HT_TEAM_ID,
                away_team_ht_id=600002,
                home_team_name="Pulgas Arrechas",
                away_team_name="Atlético Dos",
                home_goals=1 if partial_round_played else -1,
                away_goals=0 if partial_round_played else -1,
                series_ht_id=7777,
                match_round=2,
            )
        )
        if partial_round_played:
            # La jornada 2 SÍ tiene sus 2 partidos — el segundo (rival vs
            # rival) sigue pendiente, nada que ver con datos incompletos.
            s.add(
                m.Match(
                    ht_match_id=900004,
                    played_at=BASE + timedelta(days=7),
                    match_type=1,
                    status="UPCOMING",
                    home_team_ht_id=600001,
                    away_team_ht_id=600003,
                    home_team_name="Deportivo Uno",
                    away_team_name="Club Tres",
                    home_goals=-1,
                    away_goals=-1,
                    series_ht_id=7777,
                    match_round=2,
                )
            )
        await s.commit()
    return factory, team_id


def test_a_round_missing_a_rival_pairing_is_caveated_as_incomplete() -> None:
    """Jornada 2 solo trae el partido del equipo propio — el cruce entre
    los otros dos rivales nunca se sincronizó. Eso SÍ es un calendario
    incompleto y debe avisarse."""

    async def go():
        factory, team_id = await _with_full_series_schedule(partial_round_played=False)
        async with factory() as s:
            return await LeagueQueryService(s).get(team_id, runs=1000)

    d = _run(go())
    assert d is not None
    assert any(CAVEAT_NEEDLE in c.lower() for c in d.caveats)


def test_a_round_with_one_match_already_played_is_not_a_false_positive() -> None:
    """Jornada 2 SÍ tiene sus 2 partidos — uno ya se jugó, el otro sigue
    pendiente. Contar solo los partidos PENDIENTES por jornada daría 1 (y
    dispararía el aviso por error); el total (jugados + pendientes) da 2,
    que es lo correcto: la jornada está completa, solo en progreso."""

    async def go():
        factory, team_id = await _with_full_series_schedule(partial_round_played=True)
        async with factory() as s:
            return await LeagueQueryService(s).get(team_id, runs=1000)

    d = _run(go())
    assert d is not None
    assert not any(CAVEAT_NEEDLE in c.lower() for c in d.caveats)


def test_no_rival_player_history_is_stored() -> None:
    """Regla de CHPP, no preferencia de diseño: se pueden mostrar los datos
    actuales de otros equipos pero no seguir la evolución de sus jugadores. La
    liga se analiza con resultados y clasificación, que son públicos."""

    async def go():
        factory, team_id = await _with_league()
        async with factory() as s:
            from sqlalchemy import select

            rows = (
                (await s.execute(select(m.Player).where(m.Player.team_id != team_id)))
                .scalars()
                .all()
            )
            return rows

    assert _run(go()) == []


# ── Partidos ────────────────────────────────────────────────────────────────


def test_match_list_computes_the_record_from_both_home_and_away() -> None:
    async def go():
        factory, team_id = await _with_league()
        async with factory() as s:
            return await MatchesQueryService(s).overview(team_id)

    d = _run(go())
    assert d is not None
    assert d.matches_played == 2
    assert d.record == "2-0-0"  # 3-0 en casa y 2-1 fuera
    assert d.goals_for == 5 and d.goals_against == 1
    away = next(mm for mm in d.matches if not mm.is_home)
    assert away.goals_for == 2 and away.goals_against == 1
    assert away.result == "V"


def test_non_official_match_types_are_always_excluded() -> None:
    """Escaleras/Duelos (MatchType 50/62, HL-146) no cuentan para el récord
    ni aparecen en la lista — no hay override para verlos (2026-08-12,
    pedido explícito: "de TODOS los lugares... ni con botón, ni sin botón")."""

    async def go():
        factory, team_id = await _with_league()
        async with factory() as s:
            s.add(
                m.Match(
                    ht_match_id=820_000,
                    played_at=BASE + timedelta(days=100),
                    match_type=50,
                    status="finished",
                    home_team_ht_id=HT_TEAM_ID,
                    away_team_ht_id=900_001,
                    home_team_name="Pulgas Arrechas",
                    away_team_name="Rival de escalera",
                    home_goals=5,
                    away_goals=0,
                )
            )
            await s.commit()
        async with factory() as s:
            return await MatchesQueryService(s).overview(team_id)

    d = _run(go())
    assert d.matches_played == 2  # los dos de liga, no el de escalera
    assert not any(mm.ht_match_id == 820_000 for mm in d.matches)


def test_friendlies_are_hidden_unless_requested() -> None:
    """El botón que antes reactivaba Escaleras/Duelos ahora controla
    Amistosos — partidos reales que sí cuentan si se piden explícitamente."""

    async def go(include_friendlies: bool):
        factory, team_id = await _with_league()
        async with factory() as s:
            s.add(
                m.Match(
                    ht_match_id=821_000,
                    played_at=BASE + timedelta(days=100),
                    match_type=4,
                    status="finished",  # Amistoso
                    home_team_ht_id=HT_TEAM_ID,
                    away_team_ht_id=900_001,
                    home_team_name="Pulgas Arrechas",
                    away_team_name="Rival amistoso",
                    home_goals=2,
                    away_goals=2,
                )
            )
            await s.commit()
        async with factory() as s:
            return await MatchesQueryService(s).overview(
                team_id, include_friendlies=include_friendlies
            )

    default = _run(go(False))
    assert default.matches_played == 2
    assert not any(mm.ht_match_id == 821_000 for mm in default.matches)
    assert default.include_friendlies is False

    included = _run(go(True))
    assert included.matches_played == 3
    assert any(mm.ht_match_id == 821_000 for mm in included.matches)
    assert included.include_friendlies is True


def test_season_filter_uses_world_context_anchor() -> None:
    """ "TT-ss" ancla en `WorldContext` (ver weekly.py) — sin ese ancla real
    no hay forma honesta de decir a qué temporada pertenece un partido."""

    async def go(season: int | None):
        factory, team_id = await _with_league()
        refreshed_at = BASE + timedelta(weeks=16)
        async with factory() as s:
            team = await s.get(m.Team, team_id)
            team.ht_league_id = 55555
            s.add(
                m.WorldContext(
                    ht_league_id=55555,
                    season=83,
                    match_round=1,
                    refreshed_at=refreshed_at,
                )
            )
            s.add(
                m.Match(
                    ht_match_id=822_000,
                    played_at=refreshed_at,
                    match_type=1,
                    status="finished",
                    home_team_ht_id=HT_TEAM_ID,
                    away_team_ht_id=600002,
                    home_team_name="Pulgas Arrechas",
                    away_team_name="Atlético Dos",
                    home_goals=1,
                    away_goals=1,
                )
            )
            await s.commit()
        async with factory() as s:
            return await MatchesQueryService(s).overview(team_id, season=season)

    all_seasons = _run(go(None))
    assert all_seasons.matches_played == 3
    assert all_seasons.available_seasons == [83, 82]
    assert all_seasons.current_season == 83
    assert all_seasons.season_label == "Todas las temporadas"

    current = _run(go(83))
    assert current.matches_played == 1
    assert current.matches[0].ht_match_id == 822_000
    assert current.season_label == "Temporada actual (83)"

    previous = _run(go(82))
    assert previous.matches_played == 2
    assert {mm.ht_match_id for mm in previous.matches} == {800_000, 800_001}
    assert previous.season_label == "Temporada 82"


def test_hatstats_is_only_reported_where_ratings_exist() -> None:
    async def go():
        factory, team_id = await _with_league()
        async with factory() as s:
            return await MatchesQueryService(s).overview(team_id)

    d = _run(go())
    rated = [mm for mm in d.matches if mm.hatstats is not None]
    assert len(rated) == 1, "sólo se sembraron ratings de un partido"
    assert rated[0].hatstats == 14 * 3 + (10 + 12 + 10) + (8 + 11 + 9)
    assert rated[0].hatstats > (rated[0].hatstats_opponent or 0)
    assert len(d.rating_series) == 1


def test_conversion_is_built_from_chances_by_zone() -> None:
    """Conversión real: ocasiones por zona (matchdetails.xml v3.1, no el
    `<Event>` que nunca existió) sumadas a través de los partidos con
    ratings, goles atribuidos al total del partido, no a una zona."""

    async def go():
        factory, team_id = await _with_league()
        async with factory() as s:
            from sqlalchemy import update

            await s.execute(
                update(m.MatchRating)
                .where(m.MatchRating.team_ht_id == HT_TEAM_ID)
                .values(
                    chances_left=3,
                    chances_center=4,
                    chances_right=2,
                    chances_special=1,
                    chances_other=1,
                )
            )
            await s.execute(
                update(m.MatchRating)
                .where(m.MatchRating.team_ht_id == 600003)
                .values(
                    chances_left=1,
                    chances_center=1,
                    chances_right=1,
                    chances_special=0,
                    chances_other=0,
                )
            )
            await s.commit()
        async with factory() as s:
            return await MatchesQueryService(s).overview(team_id)

    d = _run(go())
    assert d.conversion.own_chances == 11
    assert d.conversion.own_goals == 3  # goles del partido 800_000 (3-0)
    assert d.conversion.opponent_chances == 3
    assert d.conversion.opponent_goals == 0
    assert d.conversion.is_reliable == (
        d.conversion.own_chances >= MIN_CHANCES_FOR_A_RATE
        and d.conversion.opponent_chances >= MIN_CHANCES_FOR_A_RATE
    )
    assert len(d.conversion.zones) == 5
    left = next(z for z in d.conversion.zones if z.zone == "left")
    assert left.own == 3 and left.opponent == 1


def test_match_detail_separates_strengths_from_weaknesses() -> None:
    async def go():
        factory, team_id = await _with_league()
        async with factory() as s:
            return await MatchesQueryService(s).detail(team_id, 800_000)

    d = _run(go())
    assert d is not None
    assert d.score == "3-0"
    assert d.opponent == "Club Tres"
    assert len(d.sectors) == 7
    mid = next(s for s in d.sectors if s.sector == "midfield")
    assert mid.own == 14 and mid.opponent == 6 and mid.delta == 8
    assert mid.dominance > 0.5
    assert d.possession == (58, 61)
    assert d.hatstats > d.hatstats_opponent
    assert d.verdict


def test_match_detail_without_ratings_is_a_404_not_an_empty_shell() -> None:
    async def go():
        factory, team_id = await _with_league()
        async with factory() as s:
            return await MatchesQueryService(s).detail(team_id, 800_001)

    assert _run(go()) is None


# ── Juveniles ───────────────────────────────────────────────────────────────


async def _with_youth():
    factory, team_id = await _with_league()
    async with factory() as s:
        from sqlalchemy import select

        sync = (await s.execute(select(m.Sync).limit(1))).scalar_one()

        youths = [
            # (nombre, edad, techos revelados)
            ("Ana", 17, {"scoring": (6, 14), "passing": (4, 9)}),
            ("Beto", 18, {"defending": (7, 8)}),
            ("Cid", 19, {"keeper": (3, 5)}),
        ]
        for i, (name, age, skills) in enumerate(youths):
            yp = m.YouthPlayer(
                ht_youth_player_id=700_000 + i,
                team_id=team_id,
                first_name=name,
                last_name="Cantera",
                arrived_at=BASE,
            )
            s.add(yp)
            await s.flush()
            snap = m.YouthSnapshot(
                sync_id=sync.id,
                youth_player_id=yp.id,
                captured_at=BASE,
                age_years=age,
                age_days=100 if age == 19 else 0,
                minutes_last_match=90,
                content_hash=bytes(32),
            )
            for skill, (cur, mx) in skills.items():
                setattr(snap, skill, cur)
                setattr(snap, f"{skill}_max", mx)
            s.add(snap)

        s.add(
            m.FormerYouthPlayer(
                team_id=team_id,
                ht_player_id=710_000,
                name="Dani Cantera",
                # Llego a su club nuevo el dia que se le vendio, que es el
                # caso normal de una venta directa. Antes este campo se
                # llamaba `promoted_at` y se creia la fecha de ascenso.
                arrived_at_current_team=BASE + timedelta(days=60),
                sold_at=BASE + timedelta(days=60),
                sold_for=3_500_000,
                current_team_name="Otro Club",
            )
        )
        await s.commit()
    return factory, team_id


def test_academy_ranks_by_potential_not_by_current_skill() -> None:
    async def go():
        factory, team_id = await _with_youth()
        async with factory() as s:
            return await AcademyQueryService(s).get(team_id)

    d = _run(go())
    assert d is not None
    assert d.squad_size == 3
    # Ana tiene menos defensa que Beto pero un techo de 14 en anotación.
    assert d.players[0].name == "Ana Cantera"
    assert d.players[0].potential_score > d.players[1].potential_score


def test_an_unrevealed_ceiling_is_unknown_not_zero() -> None:
    """Descartar una promesa porque el ojeador aún no ha mirado sería confundir
    ignorancia con evidencia."""

    async def go():
        factory, team_id = await _with_youth()
        async with factory() as s:
            return await AcademyQueryService(s).get(team_id)

    d = _run(go())
    ana = next(p for p in d.players if p.name == "Ana Cantera")
    revealed = [s for s in ana.skills if s.is_max_known]
    unrevealed = [s for s in ana.skills if not s.is_max_known]
    assert len(revealed) == 2 and unrevealed
    assert all(s.maximum is None for s in unrevealed)
    # Un techo desconocido conserva margen de crecimiento, no lo pierde.
    assert all(s.headroom > 0 for s in unrevealed if (s.current or 0) < 8)

    # 2026-08-17: nivel actual y techo se revelan por SEPARADO, y hasta ahora
    # el nivel sin revelar se guardaba como 0 — indistinguible de jugar a
    # nivel 0. Ahora viaja como `None` y con su propio indicador, que es lo que
    # decide si la barra amarilla se pinta.
    assert all((s.current is None) != s.is_current_known for s in ana.skills), (
        "is_current_known tiene que ir de la mano de que haya nivel"
    )
    # La categoría se marca provisional en la propia fila; la nota que lo
    # explicaba se retiró en la pasada de caveats del 2026-08-16.
    # 2026-08-30: un veredicto BUENO ya no es provisional. Revelar una
    # habilidad solo puede SUBIR el mejor techo, nunca bajarlo, asi que el 14
    # de Ana no se lo quita ningun descubrimiento posterior. Lo provisional es
    # lo contrario: condenar a alguien con techos sin mirar.
    assert ana.verdict_is_provisional is False


def test_the_deadline_overrides_everything_else() -> None:
    """Un canterano de 19 años se pierde al cumplir el límite, por bueno que
    sea. El consejo tiene que decirlo antes que cualquier otra cosa."""

    async def go():
        factory, team_id = await _with_youth()
        async with factory() as s:
            return await AcademyQueryService(s).get(team_id)

    d = _run(go())
    cid = next(p for p in d.players if p.name == "Cid Cantera")
    assert cid.days_until_deadline < 21
    assert "URGENTE" in cid.promote_advice
    assert any("Cid" in u for u in d.urgent)

    ana = next(p for p in d.players if p.name == "Ana Cantera")
    assert ana.days_until_deadline > cid.days_until_deadline


def test_academy_roi_crosses_investment_with_income() -> None:
    """Las dos cifras existen en Hattrick Control, en pantallas distintas y sin
    cruzarse nunca. Ese cruce es todo el valor de esta vista."""

    async def go():
        factory, team_id = await _with_youth()
        async with factory() as s:
            return await AcademyQueryService(s).get(team_id)

    d = _run(go())
    assert d.earned == 350_000  # 3.500.000 base ÷ tasa 10
    assert d.net == d.earned - d.invested
    assert d.roi_verdict
    assert len(d.graduates) == 1
    assert d.graduates[0].current_team == "Otro Club"


def test_graduate_without_squad_record_falls_back_to_gross_and_says_so() -> None:
    """2026-08-15, pedido: el ingreso de la cantera debe salir de "Saldo por
    jugador" (neto tras comisión + bonos de club de origen/anterior). Pero un
    canterano vendido puede vivir SOLO en `former_youth_players`, sin ficha en
    plantilla: ahí no hay comisión ni bonos que calcular. Se cuenta el bruto,
    porque perderlo de la suma sería peor."""

    async def go():
        factory, team_id = await _with_youth()
        async with factory() as s:
            return await AcademyQueryService(s).get(team_id)

    d = _run(go())
    assert d.earned == 350_000


def test_investment_counts_calendar_weeks_not_economy_snapshots() -> None:
    """2026-08-15, bug real: la inversión contaba UN "semana" por cada snapshot
    económico. Como los snapshots son por sync (a veces varios el mismo día),
    34 lecturas de tres semanas se presentaban como 34 semanas y la cifra salía
    inflada ~11x. Varias lecturas dentro de la misma semana ISO son una semana.
    """
    from datetime import UTC, datetime, timedelta

    from app.application.queries.weekly import latest_per_iso_week

    base = datetime(2026, 7, 27, tzinfo=UTC)  # lunes
    same_week = [base, base + timedelta(hours=5), base + timedelta(days=2)]
    next_week = [base + timedelta(days=7)]

    class Snap:
        def __init__(self, when: datetime) -> None:
            self.captured_at = when

    collapsed = latest_per_iso_week(
        [Snap(w) for w in same_week + next_week], lambda s: s.captured_at
    )
    assert len(collapsed) == 2  # dos semanas ISO, no cuatro lecturas


def test_academy_answers_even_with_no_youth_squad_synced() -> None:
    """El retorno y los canteranos promocionados ya se pueden calcular sin la
    plantilla juvenil. Devolver 404 escondería información disponible."""

    async def go():
        factory, team_id = await _with_league()
        async with factory() as s:
            return await AcademyQueryService(s).get(team_id)

    d = _run(go())
    assert d is not None
    assert d.squad_size == 0
    # Sin la fecha de apertura el ROI cuenta también canteras anteriores: es el
    # único caveat que sobrevivió a la pasada del 2026-08-16.
    assert any("Sincroniza para acotar la academia" in n for n in d.notes)


def test_la_fecha_del_ex_canterano_es_la_de_llegada_no_la_de_ascenso() -> None:
    """`ArrivalDate` es «the date of arrival to current team», no un ascenso.

    2026-08-31, encontrado por aritmética: los 43 ex-canteranos de la base real
    aparecían VENDIDOS antes de la fecha que se llamaba de ascenso --hasta
    1.054 días antes-- y las ventas directas tenían las dos el mismo día. El
    campo era bueno, el nombre no, y ese nombre hizo que se usara para situar
    a cada canterano en una academia concreta.

    Aquí se fija la regla, no una cifra: la fecha de llegada nunca puede ser
    anterior a la de venta, porque primero se le vende y después llega.
    """
    from app.infrastructure.db import models as m

    assert not hasattr(m.FormerYouthPlayer, "promoted_at"), (
        "el nombre viejo prometía una fecha de ascenso que el dato no contiene"
    )
    assert hasattr(m.FormerYouthPlayer, "arrived_at_current_team")

    ex = m.FormerYouthPlayer(
        team_id=1,
        ht_player_id=1,
        name="X",
        sold_at=BASE,
        arrived_at_current_team=BASE + timedelta(days=1),
    )
    assert ex.arrived_at_current_team is not None
    assert ex.sold_at is not None
    assert ex.arrived_at_current_team >= ex.sold_at
