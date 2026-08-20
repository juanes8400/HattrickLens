"""HL-120 a HL-123 · Optimizador de alineación sobre la plantilla real."""
from pathlib import Path

import pytest

from app.domain.engines.lineup_optimizer import (
    FORMATIONS,
    TEAM_SPIRIT_ATTITUDE_MULTIPLIER,
    best_formation,
    best_lineup,
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
            if p["ht_player_id"] in used or p.get("injury_level", -1) >= 1:
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


def test_a_bruised_player_is_still_available() -> None:
    """2026-08-16, error real: `InjuryLevel` 0 es MAGULLADO y en Hattrick sí
    puede jugar. Descartarlo sacaba del mejor once a gente disponible — el
    caso que lo destapó fue un delantero titular que desapareció por un
    magullón."""
    sano = [dict(p) for p in ROSTER]
    titulares_sano = {a.player["ht_player_id"] for a in best_lineup(sano, "4-4-2").assignments}

    magullado = [dict(p) for p in ROSTER]
    tocado = next(p for p in magullado if p["ht_player_id"] in titulares_sano)
    tocado["injury_level"] = 0

    lu = best_lineup(magullado, "4-4-2")
    assert tocado["ht_player_id"] in {a.player["ht_player_id"] for a in lu.assignments}


def test_keeper_slot_gets_the_goalkeeper() -> None:
    lu = best_lineup(ROSTER, "4-4-2")
    portero = next(a for a in lu.assignments if a.position == "keeper")
    assert portero.player["last_name"] == "Ebbesen"


def test_best_formation_ranks_every_formation() -> None:
    """Las diez de Hattrick, no un número escrito a mano: al añadir 5-2-3 y
    2-5-3 el 2026-08-19 este test habría seguido en verde con ocho."""
    from app.domain.engines.lineup_optimizer import FORMATIONS

    lu, ranking = best_formation(ROSTER)
    assert len(ranking) == len(FORMATIONS)
    assert lu.formation == next(iter(ranking))
    assert list(ranking.values()) == sorted(ranking.values(), reverse=True)


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


def test_no_formation_breaks_the_position_maximums() -> None:
    """Máximos del juego, confirmados por el usuario el 2026-08-19: 1 portero,
    3 defensas centrales, 2 laterales (uno por banda), 3 mediocentros,
    2 extremos (uno por banda) y 3 delanteros.

    De ahí sale la geometría de la cancha que dibuja la interfaz: con dos
    bandas y tres por el centro, ninguna línea pasa de cinco. Una formación que
    se saltara un máximo rompería ese dibujo en silencio.
    """
    from collections import Counter

    from app.domain.engines.lineup_optimizer import FORMATIONS
    from app.domain.value_objects.formations import (
        MAX_CENTRAL_DEFENDERS,
        MAX_FORWARDS,
        MAX_INNER_MIDFIELDERS,
        MAX_FLANK_PER_LINE,
    )

    MAX_PER_POSITION = {
        "keeper": 1,
        "central_defender": MAX_CENTRAL_DEFENDERS,
        "wingback": MAX_FLANK_PER_LINE,
        "inner_midfield": MAX_INNER_MIDFIELDERS,
        "winger": MAX_FLANK_PER_LINE,
        "forward": MAX_FORWARDS,
    }

    for nombre, puestos in FORMATIONS.items():
        assert len(puestos) == 11, nombre
        cuenta = Counter(puestos)
        assert set(cuenta) <= set(MAX_PER_POSITION), nombre
        for puesto, cuantos in cuenta.items():
            assert cuantos <= MAX_PER_POSITION[puesto], f"{nombre}: {puesto}={cuantos}"
        # Dos bandas y tres por el centro: cinco por línea como mucho.
        assert cuenta["wingback"] + cuenta["central_defender"] <= 5, nombre
        assert cuenta["winger"] + cuenta["inner_midfield"] <= 5, nombre


def test_every_formation_name_matches_how_it_is_built() -> None:
    """El nombre de una formación ES su composición: defensas-medios-delanteros,
    con el extremo contando en la línea del medio (así lo cuenta Hattrick).

    2026-08-19: "4-3-3" estaba armada con 3 mediocentros y 2 extremos, o sea
    CINCO medios y un solo delantero. Era un 4-5-1 con otro nombre, y el
    optimizador devolvía un once que no era el que se le pedía. Este test
    compara nombre contra composición para que no vuelva a pasar en silencio.
    """
    from collections import Counter

    from app.domain.engines.lineup_optimizer import FORMATIONS

    for nombre, puestos in FORMATIONS.items():
        cuenta = Counter(puestos)
        defensas = cuenta["wingback"] + cuenta["central_defender"]
        medios = cuenta["winger"] + cuenta["inner_midfield"]
        delanteros = cuenta["forward"]
        assert cuenta["keeper"] == 1, nombre
        assert f"{defensas}-{medios}-{delanteros}" == nombre


def test_the_catalogue_has_the_ten_hattrick_formations() -> None:
    """Hattrick tiene diez. Aquí había ocho hasta 2026-08-19: faltaban 5-2-3
    (preguntada por el usuario) y 2-5-3, así que ni el optimizador ni el once
    ideal de la liga podían proponerlas."""
    from app.domain.engines.lineup_optimizer import FORMATIONS
    from app.domain.engines.team_of_the_week import FORMATIONS as TOTW

    esperadas = {
        "5-5-0", "5-4-1", "5-3-2", "5-2-3", "4-5-1",
        "4-4-2", "4-3-3", "3-5-2", "3-4-3", "2-5-3",
    }
    assert set(FORMATIONS) == esperadas
    # Las dos tablas describen lo mismo desde ángulos distintos (once completo
    # contra conteo por línea): si se separan, el selector ofrecería una
    # formación que la otra no sabe armar.
    assert set(TOTW) == esperadas
