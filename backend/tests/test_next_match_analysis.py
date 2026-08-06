from app.domain.engines.next_match_analysis import direct_condition_summary, probable_starters


PLAYERS = [
    {"ht_player_id": 1, "name": "Más recurrente", "tsi": 1200, "stamina": 8, "form": 7, "experience": 6},
    {"ht_player_id": 2, "name": "Más reciente", "tsi": 9000, "stamina": 4, "form": 6, "experience": 8},
    {"ht_player_id": 3, "name": "Solo TSI", "tsi": 99999, "stamina": 5, "form": 5, "experience": 5},
]


def test_probable_starters_prioritises_recurrence_then_recency() -> None:
    appearances = [
        {"match_id": 10, "ht_player_id": 1, "name": "Más recurrente", "position_code": 4, "rating_stars": 5.5, "rating_stars_end": 5.0},
        {"match_id": 10, "ht_player_id": 2, "name": "Más reciente", "position_code": 13},
        {"match_id": 11, "ht_player_id": 1, "name": "Más recurrente", "position_code": 4, "rating_stars": 6.0, "rating_stars_end": 5.0},
        {"match_id": 12, "ht_player_id": 2, "name": "Más reciente", "position_code": 13},
        {"match_id": 13, "ht_player_id": 1, "name": "Más recurrente", "position_code": 4, "rating_stars": 6.0, "rating_stars_end": 5.0},
    ]

    rows = probable_starters(PLAYERS, appearances, limit=3)

    assert [row["ht_player_id"] for row in rows] == [1, 2, 3]
    assert rows[0]["starts_in_sample"] == 3
    assert rows[0]["line"] == "Defensa"
    assert rows[0]["rating_star_drop"] == 1.0
    assert rows[2]["position_code"] is None


def test_condition_summary_uses_direct_values_and_keeps_zero_valid() -> None:
    rows = [
        {"line": "Defensa", "stamina": 0, "form": 4, "experience": 2},
        {"line": "Defensa", "stamina": 8, "form": 6, "experience": 6},
    ]

    out = direct_condition_summary(rows)

    assert out["players"] == 2
    assert out["stamina_available"] is True
    assert out["stamina_avg"] == 4.0
    assert out["stamina_median"] == 4.0
    assert out["low_stamina_count"] == 1
    assert out["by_line"] == [{
        "line": "Defensa", "players": 2, "stamina_avg": 4.0,
        "form_avg": 5.0, "experience_avg": 4.0,
    }]


def test_condition_summary_marks_a_missing_skill_as_unavailable_not_zero() -> None:
    out = direct_condition_summary([
        {"line": "Defensa", "stamina": None, "form": 6, "experience": 5},
        {"line": "Mediocampo", "stamina": None, "form": 7, "experience": 4},
    ])

    assert out["stamina_available"] is False
    assert out["stamina_avg"] is None
    assert out["low_stamina_count"] == 0
