"""HL-140 · Diff de sync al estilo Hattrick Control."""
from app.domain.engines.sync_diff import (
    MatchState,
    diff_economy,
    diff_match,
    diff_player_skills,
    diff_standing,
    diff_training,
)

PLAYER_OLD = {
    "tsi": 1000,
    "salary": 5000,
    "form": 6,
    "stamina": 7,
    "experience": 4,
    "injury_level": -1,
    "is_transfer_listed": False,
    "skills": {"defending": 10, "passing": 8, "scoring": 5},
}


def test_new_player_is_announced_as_arrival() -> None:
    out = diff_player_skills(None, PLAYER_OLD, "Raul Cobos")
    assert out == ["Raul Cobos se unio a la plantilla"]


def test_detects_skill_increase() -> None:
    new = {**PLAYER_OLD, "skills": {**PLAYER_OLD["skills"], "defending": 11}}
    out = diff_player_skills(PLAYER_OLD, new, "Raul Cobos")
    assert "Raul Cobos: Defensa subio de 10 a 11" in out


def test_detects_skill_decrease() -> None:
    new = {**PLAYER_OLD, "skills": {**PLAYER_OLD["skills"], "passing": 7}}
    out = diff_player_skills(PLAYER_OLD, new, "Raul Cobos")
    assert "Raul Cobos: Pases bajo de 8 a 7" in out


def test_no_change_gives_empty_list() -> None:
    assert diff_player_skills(PLAYER_OLD, dict(PLAYER_OLD), "Raul Cobos") == []


def test_detects_tsi_change() -> None:
    new = {**PLAYER_OLD, "tsi": 1200}
    out = diff_player_skills(PLAYER_OLD, new, "Raul Cobos")
    assert "Raul Cobos: TSI 1,000 -> 1,200" in out


def test_detects_salary_form_and_stamina_changes() -> None:
    new = {**PLAYER_OLD, "salary": 5500, "form": 7, "stamina": 6}
    out = diff_player_skills(PLAYER_OLD, new, "Raul Cobos")
    assert "Raul Cobos: Salario 5,000 -> 5,500" in out
    assert "Raul Cobos: Forma 6 -> 7" in out
    assert "Raul Cobos: Resistencia 7 -> 6" in out


def test_detects_injury_and_recovery() -> None:
    hurt = {**PLAYER_OLD, "injury_level": 3}
    out = diff_player_skills(PLAYER_OLD, hurt, "Raul Cobos")
    assert "Raul Cobos: se lesiono" in out

    recovered = diff_player_skills(hurt, PLAYER_OLD, "Raul Cobos")
    assert "Raul Cobos: se recupero de la lesion" in recovered


def test_detects_transfer_listing() -> None:
    listed = {**PLAYER_OLD, "is_transfer_listed": True}
    out = diff_player_skills(PLAYER_OLD, listed, "Raul Cobos")
    assert "Raul Cobos: puesto en mercado" in out


ECON_OLD = {
    "cash": 1_000_000,
    "sponsors_popularity": 50,
    "supporters_popularity": 60,
    "fan_club_size": 200,
    "income_sum": 100_000,
    "costs_sum": 90_000,
}


def test_first_economy_sync_has_no_diff() -> None:
    assert diff_economy(None, ECON_OLD) == []


def test_detects_cash_change_with_currency() -> None:
    """Sin `rate` (por defecto 1.0, SEK == local) — caso de un país cuya
    tasa de cambio con SEK sea exactamente 1."""
    new = {**ECON_OLD, "cash": 1_200_000}
    out = diff_economy(ECON_OLD, new, currency="US$")
    assert "Caja: 1,000,000 -> 1,200,000 US$" in out


def test_cash_change_converts_from_sek_using_currency_rate() -> None:
    """Corrección 2026-08-05, bug real encontrado en vivo: economy.xml
    llega en SEK, no en la moneda local — sin `rate`, el mensaje mostraba
    el número crudo en SEK con la etiqueta de la moneda local (p. ej.
    "10,000 US$" para un cambio que, dividido por la tasa real de Colombia
    = 10, eran 1,000 US$ de verdad)."""
    new = {**ECON_OLD, "cash": ECON_OLD["cash"] + 10_000}
    out = diff_economy(ECON_OLD, new, currency="US$", rate=10.0)
    assert "Caja: 100,000 -> 101,000 US$" in out


def test_economy_change_that_rounds_away_after_conversion_is_not_reported() -> None:
    """Un cambio real en SEK que, tras dividir por la tasa, redondea al
    mismo entero en moneda local no debe generar un "X -> X" confuso."""
    new = {**ECON_OLD, "cash": ECON_OLD["cash"] + 3}
    out = diff_economy(ECON_OLD, new, currency="US$", rate=10.0)
    assert not any(c.startswith("Caja:") for c in out)


def test_detects_popularity_change_without_money_format() -> None:
    new = {**ECON_OLD, "sponsors_popularity": 55}
    out = diff_economy(ECON_OLD, new)
    assert "Popularidad con patrocinadores: 50 -> 55" in out


def test_no_economy_change_is_empty() -> None:
    assert diff_economy(ECON_OLD, dict(ECON_OLD)) == []


TRAINING_OLD = {"training_type": 10, "training_level": 3, "trainer_name": "Volodymyr Manakin"}


def test_detects_training_type_change() -> None:
    new = {**TRAINING_OLD, "training_type": 4}
    out = diff_training(TRAINING_OLD, new)
    assert any("tipo 10 -> 4" in c for c in out)


def test_detects_new_trainer() -> None:
    new = {**TRAINING_OLD, "trainer_name": "Nuevo DT"}
    out = diff_training(TRAINING_OLD, new)
    assert "Nuevo entrenador: Nuevo DT" in out


def test_first_training_sync_has_no_diff() -> None:
    assert diff_training(None, TRAINING_OLD) == []


def test_standing_first_round_has_no_diff() -> None:
    assert diff_standing(None, 3, "Pulgas Arrechas") is None


def test_standing_position_improves() -> None:
    assert diff_standing(4, 2, "Pulgas Arrechas") == "Pulgas Arrechas subio de la posicion 4 a la 2"


def test_standing_position_worsens() -> None:
    assert diff_standing(2, 5, "Pulgas Arrechas") == "Pulgas Arrechas bajo de la posicion 2 a la 5"


def test_standing_unchanged_position_is_none() -> None:
    assert diff_standing(3, 3, "Pulgas Arrechas") is None


def test_new_match_in_calendar_is_not_a_result_change() -> None:
    upcoming = MatchState(status="UPCOMING", home_goals=-1, away_goals=-1)
    assert diff_match(None, upcoming, is_home=True, opponent="Rival") is None


def test_match_becoming_finished_announces_result_home_win() -> None:
    before = MatchState(status="UPCOMING", home_goals=-1, away_goals=-1)
    after = MatchState(status="FINISHED", home_goals=2, away_goals=1)
    assert diff_match(before, after, is_home=True, opponent="Rival") == "Ganaste 2-1 vs Rival"


def test_match_result_away_loss() -> None:
    before = MatchState(status="UPCOMING", home_goals=-1, away_goals=-1)
    after = MatchState(status="FINISHED", home_goals=3, away_goals=1)
    assert diff_match(before, after, is_home=False, opponent="Rival") == "Perdiste 1-3 vs Rival"


def test_match_result_draw() -> None:
    before = MatchState(status="UPCOMING", home_goals=-1, away_goals=-1)
    after = MatchState(status="FINISHED", home_goals=1, away_goals=1)
    assert diff_match(before, after, is_home=True, opponent="Rival") == "Empataste 1-1 vs Rival"


def test_already_known_result_is_not_repeated() -> None:
    before = MatchState(status="FINISHED", home_goals=2, away_goals=1)
    after = MatchState(status="FINISHED", home_goals=2, away_goals=1)
    assert diff_match(before, after, is_home=True, opponent="Rival") is None


def test_match_still_upcoming_is_not_announced() -> None:
    before = MatchState(status="UPCOMING", home_goals=-1, away_goals=-1)
    after = MatchState(status="UPCOMING", home_goals=-1, away_goals=-1)
    assert diff_match(before, after, is_home=True, opponent="Rival") is None
