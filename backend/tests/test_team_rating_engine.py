"""HL-143 · Calificación de equipo por sector (fórmula exacta de comunidad).

No reemplaza a `lineup_optimizer` (benchmarkeado contra datos reales); es un
motor complementario que aplica la tabla de contribución EXACTA del Manual
no Escrito sobre un once ya armado.
"""
from app.domain.engines.position_engine import positions
from app.domain.engines.team_rating_engine import (
    POSITION_SECTOR_CONTRIBUTION,
    SECTORS,
    compute_sector_ratings,
)


def test_every_real_pitch_position_has_a_contribution_entry() -> None:
    """Ninguna de las 19 posiciones jugables debe quedar sin tabla — si un
    jugador cae en una posición sin entrada, su aporte se pierde en silencio."""
    assert set(positions()) == set(POSITION_SECTOR_CONTRIBUTION)


def test_pure_central_defender_only_feeds_defence_and_midfield() -> None:
    dc = {"name": "Muro", "skills": {"defending": 10, "playmaking": 4}}
    ratings = compute_sector_ratings([(dc, "central_defender", "Defensa central")])

    assert ratings.ratings["central_def"] == 10.0          # 100% de Defensa
    assert ratings.ratings["lateral_def"] == 5.2            # 52% de Defensa
    assert ratings.ratings["midfield"] == 1.0                # 25% de Jugadas
    assert ratings.ratings["central_att"] == 0.0
    assert ratings.ratings["lateral_att"] == 0.0


def test_pure_forward_only_feeds_attack_and_midfield() -> None:
    dn = {"name": "9", "skills": {"scoring": 10, "passing": 6, "playmaking": 4}}
    ratings = compute_sector_ratings([(dn, "forward", "Delantero")])

    assert ratings.ratings["central_att"] == round(10 * 1.00 + 6 * 0.33, 2)
    assert ratings.ratings["midfield"] == round(4 * 0.25, 2)
    assert ratings.ratings["central_def"] == 0.0
    assert ratings.ratings["lateral_def"] == 0.0


def test_contributions_from_multiple_players_add_up() -> None:
    dc1 = {"name": "DC1", "skills": {"defending": 8}}
    dc2 = {"name": "DC2", "skills": {"defending": 6}}
    ratings = compute_sector_ratings([
        (dc1, "central_defender", "Defensa central"),
        (dc2, "central_defender", "Defensa central"),
    ])
    # 2 DC en cancha: penalización de saturación -3.6% sobre ambos.
    assert ratings.ratings["central_def"] == round((8 + 6) * 0.964, 2)


def test_top_contributors_are_ranked_and_capped_at_three() -> None:
    players = [
        ({"name": f"MC{i}", "skills": {"playmaking": i}}, "inner_midfield", "Medio")
        for i in range(1, 6)
    ]
    ratings = compute_sector_ratings(players)
    top = ratings.top_contributors["midfield"]
    assert len(top) == 3
    assert [c.player_name for c in top] == ["MC5", "MC4", "MC3"]


def test_all_sectors_present_even_when_empty() -> None:
    ratings = compute_sector_ratings([])
    assert set(ratings.ratings) == set(SECTORS)
    assert all(v == 0.0 for v in ratings.ratings.values())


def test_unknown_position_is_ignored_not_crashed_on() -> None:
    player = {"name": "Rol especial", "skills": {"leadership": 8}}
    ratings = compute_sector_ratings([(player, "captain", "Capitán")])
    assert all(v == 0.0 for v in ratings.ratings.values())
