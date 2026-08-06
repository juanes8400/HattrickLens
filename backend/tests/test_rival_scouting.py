"""Scouting de rivales: KDE de TSI, marcaje al hombre, rotación de lado."""
import math

from app.domain.engines.rival_scouting import (
    analyse_side_rotation,
    estimate_win_probability,
    gaussian_kde,
    suggest_man_marking,
    summarise_tactics,
    tsi_kde_comparison,
)


def test_kde_peaks_near_the_data_cluster() -> None:
    values = [100.0] * 5
    grid = [50.0 + i for i in range(101)]  # 50..150
    density = gaussian_kde(values, grid)
    peak_x = grid[density.index(max(density))]
    assert abs(peak_x - 100.0) < 2.0


def test_kde_integrates_to_roughly_one() -> None:
    values = [200.0, 210.0, 190.0, 205.0, 195.0]
    grid = [float(i) for i in range(-200, 601)]  # rango amplio: cubre las colas
    density = gaussian_kde(values, grid)
    area = sum(density) * (grid[1] - grid[0])
    assert abs(area - 1.0) < 0.05


def test_kde_empty_values_returns_zero_density() -> None:
    assert gaussian_kde([], [1.0, 2.0, 3.0]) == [0.0, 0.0, 0.0]


def test_tsi_comparison_excludes_keeper_by_position_code() -> None:
    own = [{"tsi": 1000, "position_code": 1}, {"tsi": 500, "position_code": 3}]
    rival = [{"tsi": 800, "position_code": 1}, {"tsi": 400, "position_code": 7}]
    out = tsi_kde_comparison(own, rival, exclude_keeper=True)
    assert out.own_values == [500.0]
    assert out.rival_values == [400.0]


def test_tsi_comparison_never_excludes_unknown_position() -> None:
    """Un jugador nunca visto en un matchlineup no tiene position_code: no se
    adivina que es el arquero solo para poder excluirlo."""
    own = [{"tsi": 500, "position_code": None}]
    out = tsi_kde_comparison(own, [], exclude_keeper=True)
    assert out.own_values == [500.0]


def test_tsi_comparison_log_transform() -> None:
    own = [{"tsi": 999, "position_code": 3}]
    out = tsi_kde_comparison(own, [], log_transform=True, exclude_keeper=True)
    assert out.own_values == [math.log1p(999)]


REAL_TRAINER_LIKE_RIVAL = [
    {"name": "Central Defender", "ht_player_id": 1, "position_code": 4, "tsi": 5000},
    {"name": "Wingback", "ht_player_id": 2, "position_code": 2, "tsi": 900},
]


def test_no_suggestion_when_rival_has_no_markable_player() -> None:
    """Un defensa central y un lateral no son marcables — nunca se puede
    recomendar marcar a ninguno de los dos."""
    own = [{"name": "Mi lateral", "ht_player_id": 10, "position_code": 6, "defending": 8}]
    assert suggest_man_marking(own, REAL_TRAINER_LIKE_RIVAL) is None


def test_suggests_wingback_for_rival_winger() -> None:
    rival = [{"name": "Extremo peligroso", "ht_player_id": 3, "position_code": 7, "tsi": 3000}]
    own = [
        {"name": "Mi lateral flojo", "ht_player_id": 10, "position_code": 2, "defending": 4},
        {"name": "Mi lateral fuerte", "ht_player_id": 11, "position_code": 6, "defending": 9},
        {"name": "Mi defensa central", "ht_player_id": 12, "position_code": 4, "defending": 10},
    ]
    out = suggest_man_marking(own, rival)
    assert out is not None
    assert out.target_name == "Extremo peligroso"
    assert out.marker_name == "Mi lateral fuerte"  # el lateral con más defensa, no el central


def test_marker_loss_is_fifty_percent_for_the_close_pairing() -> None:
    """Lateral↔extremo es la combinación "cerca" de la tabla del Manual no
    Escrito (-50%, la más eficiente) — se prefiere siempre que haya un
    marcador cercano disponible."""
    rival = [{"name": "Extremo peligroso", "ht_player_id": 3, "position_code": 7, "tsi": 3000}]
    own = [{"name": "Mi lateral", "ht_player_id": 11, "position_code": 6, "defending": 9}]
    out = suggest_man_marking(own, rival)
    assert out is not None
    assert out.marker_loss_pct == 0.50
    assert out.efficiency == "cerca"


def test_falls_back_to_far_marker_when_no_close_option_available() -> None:
    """Sin ningún lateral disponible para marcar a un extremo (la combinación
    "cerca"), un interior sigue siendo una orden LEGAL — "lejos", -65% en
    vez de no sugerir nada."""
    rival = [{"name": "Extremo peligroso", "ht_player_id": 3, "position_code": 7, "tsi": 3000}]
    own = [{"name": "Mi interior", "ht_player_id": 11, "position_code": 9, "defending": 9}]
    out = suggest_man_marking(own, rival)
    assert out is not None
    assert out.marker_name == "Mi interior"
    assert out.efficiency == "lejos"
    assert out.marker_loss_pct == 0.65


def test_suggests_central_defender_for_rival_forward() -> None:
    rival = [{"name": "9 letal", "ht_player_id": 3, "position_code": 13, "tsi": 4000}]
    own = [
        {"name": "Mi DC", "ht_player_id": 12, "position_code": 4, "defending": 9},
        {"name": "Mi lateral", "ht_player_id": 11, "position_code": 6, "defending": 9},
    ]
    out = suggest_man_marking(own, rival)
    assert out is not None
    assert out.marker_name == "Mi DC"


def test_picks_the_highest_tsi_markable_target() -> None:
    rival = [
        {"name": "Extremo menor", "ht_player_id": 1, "position_code": 7, "tsi": 500},
        {"name": "Delantero estrella", "ht_player_id": 2, "position_code": 13, "tsi": 9000},
    ]
    own = [
        {"name": "Mi lateral", "ht_player_id": 10, "position_code": 6, "defending": 8},
        {"name": "Mi DC", "ht_player_id": 11, "position_code": 4, "defending": 8},
    ]
    out = suggest_man_marking(own, rival)
    assert out is not None
    assert out.target_name == "Delantero estrella"


def test_no_suggestion_when_no_eligible_marker_available() -> None:
    rival = [{"name": "Interior rival", "ht_player_id": 1, "position_code": 9, "tsi": 1000}]
    own = [{"name": "Mi delantero", "ht_player_id": 10, "position_code": 13, "defending": 1}]
    assert suggest_man_marking(own, rival) is None


def test_players_never_seen_in_a_lineup_are_ignored_as_targets() -> None:
    rival = [{"name": "Fantasma", "ht_player_id": 1, "position_code": None, "tsi": 9999}]
    own = [{"name": "Mi DC", "ht_player_id": 10, "position_code": 4, "defending": 9}]
    assert suggest_man_marking(own, rival) is None


RATINGS_CONSISTENT_LEFT = [
    {"left_att": 60, "central_att": 40, "right_att": 30},
    {"left_att": 55, "central_att": 35, "right_att": 25},
    {"left_att": 65, "central_att": 45, "right_att": 20},
]

RATINGS_ROTATING = [
    {"left_att": 60, "central_att": 40, "right_att": 30},
    {"left_att": 20, "central_att": 30, "right_att": 65},
    {"left_att": 25, "central_att": 60, "right_att": 20},
]


def test_detects_consistent_strong_side() -> None:
    out = analyse_side_rotation(RATINGS_CONSISTENT_LEFT)
    assert out is not None
    assert out.strong_side == "izquierda"
    assert out.rotates is False
    # domina en los 3 de 3 partidos, sin excepción
    assert out.dominant_pct == 100.0
    assert out.dominant_side_by_match == ["izquierda", "izquierda", "izquierda"]
    # las 3 series tienen la misma dispersión (±5 alrededor de su media)
    assert out.attack_left_std == 4.1
    assert out.attack_central_std == 4.1
    assert out.attack_right_std == 4.1


def test_detects_rotating_attack() -> None:
    out = analyse_side_rotation(RATINGS_ROTATING)
    assert out is not None
    assert out.rotates is True
    # cada lado domina en un partido distinto: ninguno se repite
    assert out.dominant_side_by_match == ["izquierda", "derecha", "centro"]
    assert out.dominant_pct < 50.0


def test_no_matches_returns_none() -> None:
    assert analyse_side_rotation([]) is None


def test_win_probability_is_fifty_fifty_when_tsi_is_equal() -> None:
    out = estimate_win_probability(100_000, 100_000)
    assert out.own_probability == 0.5


def test_win_probability_favours_the_stronger_tsi() -> None:
    out = estimate_win_probability(150_000, 50_000)
    assert out.own_probability == 0.75


def test_win_probability_handles_zero_total_without_crashing() -> None:
    out = estimate_win_probability(0, 0)
    assert out.own_probability == 0.5


def test_win_probability_declares_low_confidence() -> None:
    out = estimate_win_probability(100, 50)
    assert "baja" in out.confidence
    assert "no" in out.confidence.lower()


def test_summarise_tactics_none_with_no_matches() -> None:
    assert summarise_tactics([], [], []) is None


def test_summarise_tactics_counts_frequencies_and_picks_most_common() -> None:
    out = summarise_tactics([1, 1, 4, 1], [8, 6, 0, 7], ["4-4-2", "4-4-2", "4-3-3", "4-4-2"])
    assert out is not None
    assert out.matches_analysed == 4
    assert out.most_common_tactic is not None
    assert out.most_common_tactic.code == 1
    assert out.most_common_tactic.label == "Presionar"
    assert out.most_common_tactic.count == 3
    assert out.most_common_tactic.pct == 75.0
    # TacticSkill=0 es un valor real (partido sin táctica especial), no se filtra
    assert out.avg_tactic_skill == 5.2  # (8+6+0+7)/4 = 5.25, redondeado a 1 decimal
    assert out.most_common_formation is not None
    assert out.most_common_formation.formation == "4-4-2"
    assert out.most_common_formation.count == 3
    assert out.most_common_formation.pct == 75.0


def test_summarise_tactics_formations_empty_when_all_unknown() -> None:
    out = summarise_tactics([0, 0], [0, 0], ["", ""])
    assert out is not None
    assert out.avg_tactic_skill == 0.0
    assert out.formations == []
    assert out.most_common_formation is None
