"""HL-120 a HL-123 · Optimizador de alineación sobre la plantilla real."""
from pathlib import Path

import pytest

from app.domain.engines.lineup_optimizer import (
    FORMATIONS,
    TEAM_SPIRIT_ATTITUDE_MULTIPLIER,
    best_formation,
    best_lineup,
    weather_impact,
)
from app.domain.engines.position_engine import rate
from app.infrastructure.chpp.parsers import parse_players

FIXTURES = Path(__file__).parent / "fixtures"
ROSTER = parse_players((FIXTURES / "players.xml").read_bytes())["players"]


def test_lineup_has_eleven_distinct_players() -> None:
    lu = best_lineup(ROSTER, "4-4-2")
    assert len(lu.assignments) == 11
    ids = [a.player["ht_player_id"] for a in lu.assignments]
    assert len(set(ids)) == 11


def test_every_formation_can_be_filled() -> None:
    for f in FORMATIONS:
        assert len(best_lineup(ROSTER, f).assignments) == 11


def test_optimal_beats_greedy_position_by_position() -> None:
    """El punto de usar asignación óptima en vez de elegir el mejor por puesto."""
    slots = FORMATIONS["4-4-2"]
    used: set[int] = set()
    greedy_total = 0.0
    for pos in slots:
        mejor, mejor_val = None, -1.0
        for p in ROSTER:
            if p["ht_player_id"] in used or p.get("injury_level", -1) > -1:
                continue
            v = rate(p, pos).rating
            if v > mejor_val:
                mejor, mejor_val = p, v
        used.add(mejor["ht_player_id"])
        greedy_total += mejor_val

    optimal = best_lineup(ROSTER, "4-4-2").total_rating
    assert optimal >= greedy_total


def test_excluded_players_stay_out() -> None:
    fuera = {ROSTER[0]["ht_player_id"], ROSTER[1]["ht_player_id"]}
    lu = best_lineup(ROSTER, "4-4-2", exclude=fuera)
    assert not any(a.player["ht_player_id"] in fuera for a in lu.assignments)


def test_injured_players_are_never_selected() -> None:
    roster = [dict(p) for p in ROSTER]
    roster[3]["injury_level"] = 2
    lu = best_lineup(roster, "4-4-2")
    assert roster[3]["ht_player_id"] not in {a.player["ht_player_id"] for a in lu.assignments}


def test_keeper_slot_gets_the_goalkeeper() -> None:
    lu = best_lineup(ROSTER, "4-4-2")
    portero = next(a for a in lu.assignments if a.position == "keeper")
    assert portero.player["last_name"] == "Ebbesen"


def test_best_formation_ranks_all_eight() -> None:
    lu, ranking = best_formation(ROSTER)
    assert len(ranking) == 8
    assert lu.formation == next(iter(ranking))
    assert list(ranking.values()) == sorted(ranking.values(), reverse=True)


def test_weather_changes_the_result() -> None:
    impacto = weather_impact(ROSTER, "4-4-2")
    assert set(impacto) == {"rain", "cloudy", "partly", "sun"}
    assert all(v > 0 for v in impacto.values())


def test_not_enough_players_raises() -> None:
    with pytest.raises(ValueError):
        best_lineup(ROSTER[:5], "4-4-2")


def test_unknown_formation_raises() -> None:
    with pytest.raises(KeyError):
        best_lineup(ROSTER, "9-0-1")


def test_bench_excludes_starters() -> None:
    lu = best_lineup(ROSTER, "4-4-2")
    titulares = {a.player["ht_player_id"] for a in lu.assignments}
    assert not any(b["ht_player_id"] in titulares for b in lu.bench)


def test_overcrowding_penalises_three_central_defenders_and_forwards() -> None:
    """3-4-3 alinea 3 DC y 3 DN a la vez — el Manual no Escrito documenta una
    penalización exacta (-10% DC, -13.5% DN) sobre TODOS los que comparten esa
    posición, no solo sobre el tercero."""
    lu = best_lineup(ROSTER, "3-4-3")
    penalised = [a for a in lu.assignments if a.position in ("central_defender", "forward")]
    assert len(penalised) == 6

    for a in penalised:
        raw = rate(a.player, a.position).rating
        expected_multiplier = 0.90 if a.position == "central_defender" else 0.865
        assert a.rating == pytest.approx(round(raw * expected_multiplier, 2), abs=0.02)


def test_no_overcrowding_penalty_with_a_single_forward() -> None:
    """4-5-1 alinea un solo Delantero — sin saturación, sin penalización."""
    lu = best_lineup(ROSTER, "4-5-1")
    forward = next(a for a in lu.assignments if a.position == "forward")
    raw = rate(forward.player, "forward").rating
    assert forward.rating == pytest.approx(raw, abs=0.01)


def test_team_spirit_attitude_table_is_monotonic_and_matches_the_manual() -> None:
    """Manual no Escrito: 10 filas, cada una PIC < Normal < MOTS, y crecientes
    de la peor fila a la mejor."""
    assert len(TEAM_SPIRIT_ATTITUDE_MULTIPLIER) == 10
    for _, pic, normal, mots in TEAM_SPIRIT_ATTITUDE_MULTIPLIER:
        assert pic < normal < mots

    normals = [row[2] for row in TEAM_SPIRIT_ATTITUDE_MULTIPLIER]
    assert normals == sorted(normals)

    worst, best = TEAM_SPIRIT_ATTITUDE_MULTIPLIER[0], TEAM_SPIRIT_ATTITUDE_MULTIPLIER[-1]
    assert worst[0] == "Muy agresivos" and worst[1:] == (0.63, 0.72, 0.81)
    assert best[0] == "¡Paraíso en la tierra!" and best[1:] == (1.22, 1.42, 1.62)
