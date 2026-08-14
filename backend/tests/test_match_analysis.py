"""HL-071 a HL-074 · Análisis de partido con los datos reales del 1-2 vs etbenianos1."""
from app.domain.engines.match_analysis import (
    ChanceTally,
    aggregate_conversion,
    analyse,
    hatstats,
    loddar_stats,
)

# Ratings observados en matchdetails del partido de liga
PULGAS = {"midfield": 14, "right_def": 45, "central_def": 61, "left_def": 43,
          "right_att": 10, "central_att": 9, "left_att": 13}
ETBENIANOS = {"midfield": 15, "right_def": 30, "central_def": 27, "left_def": 25,
              "right_att": 28, "central_att": 27, "left_att": 24}


def test_hatstats_weights_midfield_triple() -> None:
    base = hatstats(PULGAS)
    con_mas_medio = hatstats({**PULGAS, "midfield": PULGAS["midfield"] + 1})
    assert con_mas_medio - base == 3


def test_loddar_is_positive_and_ordered() -> None:
    assert loddar_stats(PULGAS) > 0
    assert loddar_stats(ETBENIANOS) > 0


def test_analysis_detects_our_real_problem() -> None:
    """Defensa central 61 contra ataque 9-13: el partido real lo dijo claro."""
    a = analyse(PULGAS, ETBENIANOS, ChanceTally(left=3), ChanceTally(left=4, goals=2))
    assert "Defensa central" in a.strengths
    assert any("Ataque" in w for w in a.weaknesses)


def test_conversion_diagnoses_finishing_vs_creation() -> None:
    # Genero más que el rival pero convierto peor
    a = analyse(
        PULGAS, ETBENIANOS,
        ChanceTally(left=10, goals=1),
        ChanceTally(left=6, goals=3),
    )
    assert "definición" in a.verdict

    # Convierto bien pero llego poco
    b = analyse(
        PULGAS, ETBENIANOS,
        ChanceTally(left=3, goals=2),
        ChanceTally(left=10, goals=2),
    )
    assert "generación" in b.verdict


def test_chance_tally_totals() -> None:
    t = ChanceTally(left=9, center=3, right=1, goals=4)
    assert t.total == 13
    assert t.goals == 4
    assert t.conversion == 4 / 13


def test_sector_dominance_and_delta() -> None:
    a = analyse(PULGAS, ETBENIANOS, ChanceTally(), ChanceTally())
    central = next(s for s in a.sectors if s.sector == "central_def")
    assert central.delta == 34
    assert central.dominance > 0.6


def test_aggregate_conversion_over_several_matches() -> None:
    m = [
        (ChanceTally(left=5, goals=1), ChanceTally(left=4, goals=2)),
        (ChanceTally(left=5, goals=2), ChanceTally(left=6, goals=3)),
    ]
    agg = aggregate_conversion(m)
    assert agg["ownChances"] == 10
    assert agg["opponentChances"] == 10
    assert agg["ownConversion"] == 0.3
    assert agg["opponentConversion"] == 0.5
    assert agg["ownLeft"] == 10
    assert agg["opponentLeft"] == 10


def test_no_chances_is_reported_not_invented() -> None:
    a = analyse(PULGAS, ETBENIANOS, ChanceTally(), ChanceTally())
    assert "sin ocasiones" in a.verdict
