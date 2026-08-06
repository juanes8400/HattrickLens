"""Season simulator.

Un simulador de temporada es fácil de escribir y difícil de calibrar: casi
cualquier implementación produce números que parecen razonables. Lo que se
prueba aquí no es que devuelva probabilidades, sino que tenga las propiedades
que hacen que esas probabilidades signifiquen algo.
"""
import pytest

from app.domain.engines.season_simulator import (
    SHRINKAGE_K,
    Fixture,
    TeamRecord,
    best_worst_case,
    forecast_match,
    model_info,
    simulate,
)


def team(i: int, played: int, gf: int, ga: int, pts: int) -> TeamRecord:
    won = pts // 3
    return TeamRecord(
        ht_team_id=i, name=f"Equipo {i}", played=played, won=won,
        drawn=pts - won * 3, lost=played - won - (pts - won * 3),
        goals_for=gf, goals_against=ga, points=pts,
    )


# Liga de 8 con un líder claro, un colista claro y seis en medio.
LEAGUE = [
    team(1, 10, 28, 8, 27),
    team(2, 10, 22, 12, 21),
    team(3, 10, 18, 14, 17),
    team(4, 10, 15, 15, 15),
    team(5, 10, 14, 16, 13),
    team(6, 10, 12, 18, 11),
    team(7, 10, 10, 22, 7),
    team(8, 10, 6, 30, 3),
]
REMAINING = [
    Fixture(home_ht_id=1, away_ht_id=8, match_round=11),
    Fixture(home_ht_id=2, away_ht_id=7, match_round=11),
    Fixture(home_ht_id=3, away_ht_id=6, match_round=11),
    Fixture(home_ht_id=4, away_ht_id=5, match_round=11),
]


def test_every_team_gets_a_proper_probability_distribution() -> None:
    sim = simulate(LEAGUE, REMAINING, runs=3000)
    assert len(sim.teams) == 8
    for t in sim.teams:
        total = sum(t.position_distribution.values())
        assert total == pytest.approx(1.0, abs=0.01), "las probabilidades suman 1"
        assert all(0.0 <= p <= 1.0 for p in t.position_distribution.values())
        assert set(t.position_distribution) == set(range(1, 9))


def test_exactly_one_champion_per_simulation() -> None:
    """La suma de probabilidades de título sobre todos los equipos es 1: en
    cada simulación gana exactamente uno. Si no cuadra, el ordenamiento de la
    tabla está mal."""
    sim = simulate(LEAGUE, REMAINING, runs=3000)
    assert sum(t.title_probability for t in sim.teams) == pytest.approx(1.0, abs=0.02)
    # Solo asciende el 1º de la serie: misma probabilidad que el título.
    assert sum(t.promotion_probability for t in sim.teams) == pytest.approx(1.0, abs=0.02)
    assert sum(t.relegation_probability for t in sim.teams) == pytest.approx(2.0, abs=0.03)


def test_promotion_probability_equals_title_probability() -> None:
    """Solo asciende el 1º de la serie — no hay ascenso por 2º puesto ni
    playoff, así que "probabilidad de ascenso" y "probabilidad de campeón"
    son el mismo evento."""
    sim = simulate(LEAGUE, REMAINING, runs=3000)
    for t in sim.teams:
        assert t.promotion_probability == t.title_probability


def test_second_to_fourth_probability_covers_exactly_those_places() -> None:
    """Título (1º) + 2º-4º + promoción (5º-6º) + descenso (7º-8º) parten la
    tabla completa de 8 sin huecos ni solapes: la suma por equipo es 1."""
    sim = simulate(LEAGUE, REMAINING, runs=3000)
    for t in sim.teams:
        total = (
            t.title_probability + t.second_to_fourth_probability
            + t.relegation_playoff_probability + t.relegation_probability
        )
        assert total == pytest.approx(1.0, abs=0.02)
    assert sum(t.second_to_fourth_probability for t in sim.teams) == pytest.approx(3.0, abs=0.03)


def test_relegation_playoff_covers_fifth_and_sixth_place() -> None:
    """5º-6º juegan una promoción para NO descender — HL-145. Con división
    desconocida (default) no se filtra nada, así que la suma es 2 (dos
    equipos, cada simulación)."""
    sim = simulate(LEAGUE, REMAINING, runs=3000)
    assert sum(t.relegation_playoff_probability for t in sim.teams) == pytest.approx(2.0, abs=0.03)


def test_top_division_has_no_promotion_but_keeps_relegation() -> None:
    """1º de la división más alta del país no asciende más — pero sigue
    pudiendo descender como cualquier otra división intermedia."""
    sim = simulate(LEAGUE, REMAINING, runs=3000, league_level=1, max_level=5)
    assert sim.is_top_division is True
    assert sim.is_bottom_division is False
    assert all(t.promotion_probability == 0.0 for t in sim.teams)
    assert sum(t.relegation_probability for t in sim.teams) == pytest.approx(2.0, abs=0.03)
    assert sum(t.relegation_playoff_probability for t in sim.teams) == pytest.approx(2.0, abs=0.03)


def test_bottom_division_has_no_relegation_but_keeps_promotion() -> None:
    """7º-8º de la última división del país no descienden más (nada debajo),
    ni el 5º-6º juega promoción para evitarlo — pero el 1º sigue ascendiendo."""
    sim = simulate(LEAGUE, REMAINING, runs=3000, league_level=5, max_level=5)
    assert sim.is_top_division is False
    assert sim.is_bottom_division is True
    assert all(t.relegation_probability == 0.0 for t in sim.teams)
    assert all(t.relegation_playoff_probability == 0.0 for t in sim.teams)
    assert sum(t.promotion_probability for t in sim.teams) == pytest.approx(1.0, abs=0.02)


def test_unknown_division_level_is_caveated() -> None:
    sim = simulate(LEAGUE, REMAINING, runs=500)
    assert any("no se sabe" in c.lower() for c in sim.caveats)

    known = simulate(LEAGUE, REMAINING, runs=500, league_level=3, max_level=5)
    assert not any("no se sabe" in c.lower() for c in known.caveats)


def test_a_loss_awards_zero_points_not_one() -> None:
    """Regresión: el marcador de puntos debía dar 3/1/0 (victoria/empate/
    derrota). Un bug reciente hacía que una derrota también diera 1 punto,
    igual que un empate — con un equipo muy superior, el punto que gana el
    perdedor casi siempre debería venir del empate, no de perder."""
    strong = team(1, 20, 100, 5, 58)
    weak = team(2, 20, 5, 100, 0)
    sim = simulate([strong, weak], [Fixture(1, 2, 21)], runs=20000)
    loser = next(t for t in sim.teams if t.ht_team_id == 2)
    added_points = loser.expected_points - loser.current_points
    # Con el bug, el mínimo esperado rondaría 1.0 (derrota y empate daban lo
    # mismo). Corregido, con un rival tan superior casi todo es derrota (0
    # puntos), así que el promedio debe quedar muy por debajo de 1.
    assert added_points < 0.5


def test_the_leader_is_favourite_and_the_bottom_team_is_not() -> None:
    sim = simulate(LEAGUE, REMAINING, runs=3000)
    by_id = {t.ht_team_id: t for t in sim.teams}
    assert by_id[1].title_probability > by_id[8].title_probability
    assert by_id[8].relegation_probability > by_id[1].relegation_probability
    assert by_id[1].expected_position < by_id[8].expected_position


def test_shrinkage_keeps_early_season_estimates_humble() -> None:
    """La propiedad que más importa. Con 2 jornadas, un equipo que ha marcado
    6 goles no es tres veces mejor que uno que ha marcado 2: es ruido. Sin
    encogimiento el simulador produciría certezas en septiembre."""
    early = [
        team(1, 2, 6, 0, 6), team(2, 2, 2, 2, 3), team(3, 2, 2, 3, 3),
        team(4, 2, 1, 6, 0),
    ]
    late = [
        team(1, 14, 42, 0, 42), team(2, 14, 14, 14, 21), team(3, 14, 14, 21, 21),
        team(4, 14, 7, 42, 0),
    ]
    fixtures = [Fixture(1, 4, 15), Fixture(2, 3, 15)]

    early_sim = simulate(early, fixtures, runs=3000)
    late_sim = simulate(late, fixtures, runs=3000)

    early_leader = next(t for t in early_sim.teams if t.ht_team_id == 1)
    late_leader = next(t for t in late_sim.teams if t.ht_team_id == 1)

    # Mismo ritmo de goles por partido, muchísima más evidencia al final.
    assert late_leader.attack_strength > early_leader.attack_strength
    assert any("encogimiento" in c for c in early_sim.caveats)


def test_shrinkage_weight_matches_the_documented_formula() -> None:
    """(observado + k × media) / (n + k). Con n = k, la evidencia propia y el
    prior pesan exactamente lo mismo."""
    n = int(SHRINKAGE_K)
    records = [
        team(1, n, 2 * n, n, n),      # marca el doble de la media
        team(2, n, n, 2 * n, 0),
    ]
    sim = simulate(records, [], runs=500)
    leader = next(t for t in sim.teams if t.ht_team_id == 1)
    # Su ataque real sería 1.33× la media de liga (2n goles vs 1.5n de media);
    # encogido al 50% queda estrictamente entre 1.0 y ese valor.
    assert 1.0 < leader.attack_strength < 1.34


def test_a_team_that_cannot_be_caught_has_no_relegation_risk() -> None:
    runaway = [
        team(1, 15, 50, 5, 45), team(2, 15, 20, 20, 20),
        team(3, 15, 18, 22, 18), team(4, 15, 10, 51, 5),
    ]
    sim = simulate(runaway, [Fixture(2, 3, 16)], runs=3000)
    leader = next(t for t in sim.teams if t.ht_team_id == 1)
    assert leader.title_probability == pytest.approx(1.0, abs=0.001)
    assert leader.relegation_probability == pytest.approx(0.0, abs=0.001)


def test_without_fixtures_the_table_is_simply_frozen() -> None:
    sim = simulate(LEAGUE, [], runs=1000)
    for t in sim.teams:
        assert t.expected_points == float(t.current_points)
        assert t.position_distribution[t.current_position] == pytest.approx(1.0, abs=0.001)
    assert any("calendario" in c for c in sim.caveats)


def test_home_advantage_is_applied_to_the_home_side() -> None:
    a, b = team(1, 10, 15, 15, 15), team(2, 10, 15, 15, 15)
    records = [a, b]
    at_home = forecast_match(a, b, records, runs=20000)
    away = forecast_match(b, a, records, runs=20000)
    # Dos equipos idénticos: la única diferencia posible es el campo.
    assert at_home.home_win > at_home.away_win
    assert at_home.expected_home_goals > at_home.expected_away_goals
    assert at_home.home_win == pytest.approx(away.home_win, abs=0.03)


def test_match_forecast_probabilities_sum_to_one() -> None:
    f = forecast_match(LEAGUE[0], LEAGUE[-1], LEAGUE, runs=20000)
    assert f.home_win + f.draw + f.away_win == pytest.approx(1.0, abs=0.001)
    assert f.verdict
    assert "-" in f.most_likely_score


def test_simulation_is_reproducible() -> None:
    """Misma semilla, mismo resultado. Una probabilidad que baila entre
    recargas de la página no es una probabilidad, es ruido con decimales."""
    a = simulate(LEAGUE, REMAINING, runs=2000, seed=1)
    b = simulate(LEAGUE, REMAINING, runs=2000, seed=1)
    assert [t.expected_points for t in a.teams] == [t.expected_points for t in b.teams]


def test_model_declares_what_it_does_not_model() -> None:
    info = model_info()
    assert "lesiones" in info["doesNotModel"]
    assert info["tieBreakers"][0] == "puntos"
    assert info["shrinkageK"] == SHRINKAGE_K


def test_an_empty_league_is_an_error_not_an_empty_answer() -> None:
    with pytest.raises(ValueError):
        simulate([], [])


def test_best_worst_case_is_a_position_distribution() -> None:
    """El nuevo mejor/peor caso re-simula con el motor real: goleando o
    siendo goleado en lo propio, pero el resto de la liga sigue siendo
    incierta — por eso el resultado es una distribución, no un número."""
    case = best_worst_case(LEAGUE, REMAINING, target_team_id=4, runs=4000)
    assert case is not None
    assert case.remaining_matches == 1
    for dist in (case.best_case_position_distribution, case.worst_case_position_distribution):
        assert sum(dist.values()) == pytest.approx(1.0, abs=0.01)
        assert set(dist) == set(range(1, 9))


def test_best_worst_case_pushes_expected_points_to_the_extremes() -> None:
    """Equipo 4 (15 pts, mitad de tabla): en su mejor caso gana su único
    partido pendiente (goleada) y en el peor lo pierde igual de claro — los
    puntos esperados deben separarse en +3/+0 sobre los actuales, con el
    resto de la liga aportando algo de ruido alrededor."""
    case = best_worst_case(LEAGUE, REMAINING, target_team_id=4, runs=8000)
    assert case is not None
    assert case.best_case_expected_points == pytest.approx(18.0, abs=0.5)
    assert case.worst_case_expected_points == pytest.approx(15.0, abs=0.5)


def test_best_worst_case_moves_the_leader_up_and_the_bottom_team_down() -> None:
    """Goleando en su único partido pendiente, el líder (Equipo 1) casi
    siempre queda 1º en su mejor caso y sigue mucho más arriba que en su
    peor caso; el colista (Equipo 8) casi siempre queda último en su peor
    caso."""
    leader = best_worst_case(LEAGUE, REMAINING, target_team_id=1, runs=8000)
    bottom = best_worst_case(LEAGUE, REMAINING, target_team_id=8, runs=8000)
    assert leader is not None and bottom is not None
    assert leader.best_case_position_distribution[1] > 0.9
    assert bottom.worst_case_position_distribution[8] > 0.9


def test_best_worst_case_matches_current_position_with_no_fixtures_left() -> None:
    """Sin partidos pendientes no hay nada que forzar: el puesto queda
    fijo en el actual en ambos escenarios, con probabilidad 1."""
    case = best_worst_case(LEAGUE, [], target_team_id=1, runs=1000)
    assert case is not None
    assert case.remaining_matches == 0
    assert case.best_case_position_distribution[case.current_position] == pytest.approx(1.0, abs=0.001)
    assert case.worst_case_position_distribution[case.current_position] == pytest.approx(1.0, abs=0.001)


def test_best_worst_case_empty_league_returns_none() -> None:
    assert best_worst_case([], [], target_team_id=1) is None


def test_best_worst_case_unknown_team_returns_none() -> None:
    assert best_worst_case(LEAGUE, REMAINING, target_team_id=999) is None
