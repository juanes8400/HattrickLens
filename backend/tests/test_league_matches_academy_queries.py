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
from app.application.queries.league import LeagueQueryService
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
            user_id=1, team_id=team_id, kind="manual",
            status="completed", started_at=BASE,
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
                    sync_id=sync.id, series_ht_id=7777, season=83, match_round=4,
                    captured_at=BASE, team_ht_id=ht_id, team_name=name, position=pos,
                    played=pl, won=w, draws=d, lost=lost,
                    goals_for=gf, goals_against=ga, points=pts,
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
                    ht_match_id=800_000 + i, played_at=BASE + timedelta(days=7 * i),
                    match_type=1, status="finished",
                    home_team_ht_id=h, away_team_ht_id=a,
                    home_team_name=hn, away_team_name=an,
                    home_goals=hg, away_goals=ag,
                )
            )
        pending = [
            (HT_TEAM_ID, "Pulgas Arrechas", 600002, "Atlético Dos"),
            (600001, "Deportivo Uno", 600003, "Club Tres"),
        ]
        for i, (h, hn, a, an) in enumerate(pending):
            s.add(
                m.Match(
                    ht_match_id=810_000 + i, played_at=BASE + timedelta(days=30 + 7 * i),
                    match_type=1, status="scheduled",
                    home_team_ht_id=h, away_team_ht_id=a,
                    home_team_name=hn, away_team_name=an,
                    home_goals=-1, away_goals=-1,
                )
            )

        # Ratings por sector del primer partido, para ambos equipos.
        s.add(
            m.MatchRating(
                ht_match_id=800_000, team_ht_id=HT_TEAM_ID, is_home=True, midfield=14,
                right_def=10, central_def=12, left_def=10,
                right_att=8, central_att=11, left_att=9,
                possession_first_half=58, possession_second_half=61,
            )
        )
        s.add(
            m.MatchRating(
                ht_match_id=800_000, team_ht_id=600003, is_home=False, midfield=6,
                right_def=7, central_def=6, left_def=7,
                right_att=5, central_att=4, left_att=5,
                possession_first_half=42, possession_second_half=39,
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


def test_history_tracks_position_and_points_per_synced_round() -> None:
    """Cada sync guarda una foto de TODA la serie (Standing), no solo del
    equipo propio — con jornadas sincronizadas hay una serie temporal real.
    El fixture solo sincronizó la jornada 4, más la jornada 0 simbólica
    (0 puntos para todos antes de jugar nada — un hecho, no un dato
    inventado; el puesto ahí no tiene valor real, así que queda None)."""
    async def go():
        factory, team_id = await _with_league()
        async with factory() as s:
            return await LeagueQueryService(s).get(team_id, runs=2000)

    d = _run(go())
    assert d is not None
    assert d.history.rounds == [0, 4]
    assert len(d.history.teams) == 4
    pulgas = next(t for t in d.history.teams if t.name == "Pulgas Arrechas")
    assert pulgas.is_own_team is True
    assert pulgas.positions == [None, 1]
    assert pulgas.points == [0, 10]


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
    assert any("encogimiento" in c for c in d.caveats)   # sólo 4 jornadas


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
        sync = m.Sync(user_id=1, team_id=team_id, kind="manual", status="completed", started_at=BASE)
        s.add(sync)
        await s.flush()

        table = [
            (HT_TEAM_ID, "Pulgas Arrechas", 1, 1, 1, 0, 0, 3, 0, 3),
            (600001, "Deportivo Uno", 2, 1, 1, 0, 0, 2, 1, 3),
            (600002, "Atlético Dos", 3, 0, 0, 0, 0, 0, 0, 0),
            (600003, "Club Tres", 4, 1, 0, 0, 1, 1, 2, 0),
        ]
        for ht_id, name, pos, pl, w, d, lost, gf, ga, pts in table:
            s.add(m.Standing(
                sync_id=sync.id, series_ht_id=7777, season=83, match_round=1,
                captured_at=BASE, team_ht_id=ht_id, team_name=name, position=pos,
                played=pl, won=w, draws=d, lost=lost,
                goals_for=gf, goals_against=ga, points=pts,
            ))

        # Jornada 1: los 2 partidos posibles, ya jugados. Uno entre rivales.
        s.add(m.Match(
            ht_match_id=900001, played_at=BASE, match_type=1, status="FINISHED",
            home_team_ht_id=HT_TEAM_ID, away_team_ht_id=600003,
            home_team_name="Pulgas Arrechas", away_team_name="Club Tres",
            home_goals=3, away_goals=0, series_ht_id=7777, match_round=1,
        ))
        s.add(m.Match(
            ht_match_id=900002, played_at=BASE, match_type=1, status="FINISHED",
            home_team_ht_id=600001, away_team_ht_id=600002,
            home_team_name="Deportivo Uno", away_team_name="Atlético Dos",
            home_goals=2, away_goals=1, series_ht_id=7777, match_round=1,
        ))

        # Jornada 2: solo el partido DEL EQUIPO propio está sincronizado —
        # el otro cruce (600001 vs 600003) nunca llegó, sea porque falta
        # sincronizar (caso incompleto) o porque de verdad no hay más
        # equipos que emparejar en este escenario reducido de 4.
        s.add(m.Match(
            ht_match_id=900003,
            played_at=BASE + timedelta(days=7),
            match_type=1,
            status="FINISHED" if partial_round_played else "UPCOMING",
            home_team_ht_id=HT_TEAM_ID, away_team_ht_id=600002,
            home_team_name="Pulgas Arrechas", away_team_name="Atlético Dos",
            home_goals=1 if partial_round_played else -1,
            away_goals=0 if partial_round_played else -1,
            series_ht_id=7777, match_round=2,
        ))
        if partial_round_played:
            # La jornada 2 SÍ tiene sus 2 partidos — el segundo (rival vs
            # rival) sigue pendiente, nada que ver con datos incompletos.
            s.add(m.Match(
                ht_match_id=900004,
                played_at=BASE + timedelta(days=7),
                match_type=1, status="UPCOMING",
                home_team_ht_id=600001, away_team_ht_id=600003,
                home_team_name="Deportivo Uno", away_team_name="Club Tres",
                home_goals=-1, away_goals=-1,
                series_ht_id=7777, match_round=2,
            ))
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
                await s.execute(
                    select(m.Player).where(m.Player.team_id != team_id)
                )
            ).scalars().all()
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
    assert d.record == "2-0-0"          # 3-0 en casa y 2-1 fuera
    assert d.goals_for == 5 and d.goals_against == 1
    away = next(mm for mm in d.matches if not mm.is_home)
    assert away.goals_for == 2 and away.goals_against == 1
    assert away.result == "V"


def test_non_official_match_types_are_excluded_by_default() -> None:
    """Escaleras/Duelos (MatchType 50/62, HL-146) no cuentan para el récord
    ni aparecen en la lista salvo que se pida explícitamente."""
    async def go(include_non_official: bool):
        factory, team_id = await _with_league()
        async with factory() as s:
            s.add(m.Match(
                ht_match_id=820_000, played_at=BASE + timedelta(days=100),
                match_type=50, status="finished",
                home_team_ht_id=HT_TEAM_ID, away_team_ht_id=900_001,
                home_team_name="Pulgas Arrechas", away_team_name="Rival de escalera",
                home_goals=5, away_goals=0,
            ))
            await s.commit()
        async with factory() as s:
            return await MatchesQueryService(s).overview(team_id, include_non_official)

    default = _run(go(False))
    assert default.matches_played == 2  # los dos de liga, no el de escalera
    assert not any(mm.ht_match_id == 820_000 for mm in default.matches)
    assert any("Escaleras y Duelos no se muestran" in n for n in default.notes)

    included = _run(go(True))
    assert included.matches_played == 3
    assert any(mm.ht_match_id == 820_000 for mm in included.matches)
    assert not any("Escaleras y Duelos no se muestran" in n for n in included.notes)


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


def test_conversion_rates_carry_their_sample_size() -> None:
    """Con pocas ocasiones, la diferencia entre 20% y 40% es azar. La tasa se
    muestra igualmente pero marcada, porque ocultarla sería peor."""
    async def go():
        factory, team_id = await _with_league()
        async with factory() as s:
            return await MatchesQueryService(s).overview(team_id)

    d = _run(go())
    assert d.conversion
    for c in d.conversion:
        assert c.is_reliable == (c.chances >= MIN_CHANCES_FOR_A_RATE)
        assert 0.0 <= c.rate <= 1.0


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
                ht_youth_player_id=700_000 + i, team_id=team_id,
                first_name=name, last_name="Cantera", arrived_at=BASE,
            )
            s.add(yp)
            await s.flush()
            snap = m.YouthSnapshot(
                sync_id=sync.id, youth_player_id=yp.id, captured_at=BASE,
                age_years=age, age_days=100 if age == 19 else 0,
                minutes_last_match=90, content_hash=bytes(32),
            )
            for skill, (cur, mx) in skills.items():
                setattr(snap, skill, cur)
                setattr(snap, f"{skill}_max", mx)
            s.add(snap)

        s.add(
            m.FormerYouthPlayer(
                team_id=team_id, ht_player_id=710_000, name="Dani Cantera",
                promoted_at=BASE, sold_at=BASE + timedelta(days=60),
                sold_for=3_500_000, current_team_name="Otro Club",
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
    revealed = [s for s in ana.skills if s.is_revealed]
    unrevealed = [s for s in ana.skills if not s.is_revealed]
    assert len(revealed) == 2 and unrevealed
    assert all(s.maximum is None for s in unrevealed)
    # Un techo desconocido conserva margen de crecimiento, no lo pierde.
    assert all(s.headroom > 0 for s in unrevealed if s.current < 8)
    assert ana.verdict_is_provisional is True
    assert any("provisional" in n.lower() for n in d.notes)


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
    assert d.earned == 350_000          # 3.500.000 base ÷ tasa 10
    assert d.net == d.earned - d.invested
    assert d.roi_verdict
    assert len(d.graduates) == 1
    assert d.graduates[0].current_team == "Otro Club"


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
    assert any("youthteamdetails" in n for n in d.notes)
