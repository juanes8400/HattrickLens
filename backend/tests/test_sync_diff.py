"""HL-140 · Diff de sync al estilo Hattrick Control.

2026-08-15: `diff_*` devuelve `Change`, no strings. `summaries()` deja los
tests de redacción igual de legibles que antes; los tests nuevos al final
verifican que los NÚMEROS viajan aparte de la frase — que es justo lo que
faltaba cuando la UI mostró "TSI 202" por re-parsear el texto.
"""
from app.domain.engines.sync_diff import (
    Change,
    MatchState,
    diff_economy,
    diff_match,
    diff_player_departure,
    diff_player_skills,
    diff_standing,
    diff_training,
)


def summaries(changes: list[Change]) -> list[str]:
    return [c.summary for c in changes]


def by_metric(changes: list[Change], metric: str) -> Change:
    return next(c for c in changes if c.metric == metric)

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
    assert summaries(out) == ["Raul Cobos se unió a la plantilla"]


def test_detects_skill_increase() -> None:
    new = {**PLAYER_OLD, "skills": {**PLAYER_OLD["skills"], "defending": 11}}
    out = diff_player_skills(PLAYER_OLD, new, "Raul Cobos")
    assert "Raul Cobos: Defensa subió de 10 a 11" in summaries(out)


def test_detects_skill_decrease() -> None:
    new = {**PLAYER_OLD, "skills": {**PLAYER_OLD["skills"], "passing": 7}}
    out = diff_player_skills(PLAYER_OLD, new, "Raul Cobos")
    assert "Raul Cobos: Pases bajó de 8 a 7" in summaries(out)


def test_no_change_gives_empty_list() -> None:
    assert diff_player_skills(PLAYER_OLD, dict(PLAYER_OLD), "Raul Cobos") == []


def test_detects_tsi_change() -> None:
    new = {**PLAYER_OLD, "tsi": 1200}
    out = diff_player_skills(PLAYER_OLD, new, "Raul Cobos")
    assert "Raul Cobos: TSI 1.000 -> 1.200" in summaries(out)


def test_detects_salary_form_and_stamina_changes() -> None:
    new = {**PLAYER_OLD, "salary": 5500, "form": 7, "stamina": 6}
    out = diff_player_skills(PLAYER_OLD, new, "Raul Cobos")
    assert "Raul Cobos: Salario 5.000 -> 5.500" in summaries(out)
    assert "Raul Cobos: Forma 6 -> 7" in summaries(out)
    assert "Raul Cobos: Resistencia 7 -> 6" in summaries(out)


def test_detects_injury_and_recovery() -> None:
    hurt = {**PLAYER_OLD, "injury_level": 3}
    out = diff_player_skills(PLAYER_OLD, hurt, "Raul Cobos")
    assert "Raul Cobos: se lesionó" in summaries(out)

    recovered = diff_player_skills(hurt, PLAYER_OLD, "Raul Cobos")
    assert "Raul Cobos: se recuperó de la lesión" in summaries(recovered)


def test_detects_loyalty_and_leadership_changes() -> None:
    """Pedido explícito 2026-08-14: son los dos rasgos de carácter que sí
    cambian con el tiempo (a diferencia de sociabilidad/agresividad/
    honestidad, fijos), así que merecen aparecer en "Qué cambió"."""
    new = {**PLAYER_OLD, "loyalty": 6, "leadership": 3}
    out = diff_player_skills({**PLAYER_OLD, "loyalty": 5, "leadership": 3}, new, "Raul Cobos")
    assert "Raul Cobos: Fidelidad 5 -> 6" in summaries(out)
    assert not any("Liderazgo" in c for c in summaries(out))  # sin cambio, no aparece

    new2 = {**PLAYER_OLD, "loyalty": 5, "leadership": 4}
    out2 = diff_player_skills({**PLAYER_OLD, "loyalty": 5, "leadership": 3}, new2, "Raul Cobos")
    assert "Raul Cobos: Liderazgo 3 -> 4" in summaries(out2)


def test_detects_transfer_listing() -> None:
    listed = {**PLAYER_OLD, "is_transfer_listed": True}
    out = diff_player_skills(PLAYER_OLD, listed, "Raul Cobos")
    assert "Raul Cobos: puesto en mercado" in summaries(out)


def test_departure_with_sale_reports_the_price() -> None:
    """HL-2xx: un jugador vendido debe verse en "Qué cambió", no solo en
    `Player.sale_price` — bug real encontrado en vivo (Leopoldo Campus).

    2026-08-12, corrección pedida explícitamente: SIN ganancia/pérdida — un
    delta precio_venta − precio_compra no tiene en cuenta comisión de agente
    ni bono de TSI, así que mostrarlo aquí como si fuera el resultado real
    de la venta es engañoso frente a lo que sí calcula bien "Saldo por
    jugador"."""
    out = diff_player_departure("Leopoldo Campus", 8_690_000, "US$")
    assert out.summary == "Leopoldo Campus se vendió por 8.690.000 US$"
    # El precio también viaja como número, no sólo dentro de la frase.
    assert out.after == 8_690_000
    assert out.kind == "money"


def test_departure_without_sale_info_is_a_plain_exit() -> None:
    """Salida sin venta conocida (retiro, fin de préstamo, etc.) — no se
    inventa un precio."""
    out = diff_player_departure("Leopoldo Campus", None, "US$")
    assert out.summary == "Leopoldo Campus salió de la plantilla"
    assert out.after is None


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
    assert "Caja: 1.000.000 -> 1.200.000 US$" in summaries(out)


def test_cash_change_converts_from_sek_using_currency_rate() -> None:
    """Corrección 2026-08-05, bug real encontrado en vivo: economy.xml
    llega en SEK, no en la moneda local — sin `rate`, el mensaje mostraba
    el número crudo en SEK con la etiqueta de la moneda local (p. ej.
    "10,000 US$" para un cambio que, dividido por la tasa real de Colombia
    = 10, eran 1,000 US$ de verdad)."""
    new = {**ECON_OLD, "cash": ECON_OLD["cash"] + 10_000}
    out = diff_economy(ECON_OLD, new, currency="US$", rate=10.0)
    assert "Caja: 100.000 -> 101.000 US$" in summaries(out)
    # El valor convertido también viaja como número, listo para formatear.
    assert by_metric(out, "cash").before == 100_000
    assert by_metric(out, "cash").after == 101_000


def test_economy_change_that_rounds_away_after_conversion_is_not_reported() -> None:
    """Un cambio real en SEK que, tras dividir por la tasa, redondea al
    mismo entero en moneda local no debe generar un "X -> X" confuso."""
    new = {**ECON_OLD, "cash": ECON_OLD["cash"] + 3}
    out = diff_economy(ECON_OLD, new, currency="US$", rate=10.0)
    assert not any(c.startswith("Caja:") for c in summaries(out))


def test_detects_popularity_change_without_money_format() -> None:
    new = {**ECON_OLD, "supporters_popularity": 65}
    out = diff_economy(ECON_OLD, new)
    assert "Popularidad con la afición: 60 -> 65" in summaries(out)


def test_no_economy_change_is_empty() -> None:
    assert diff_economy(ECON_OLD, dict(ECON_OLD)) == []


TRAINING_OLD = {"training_type": 10, "training_level": 3, "trainer_name": "Volodymyr Manakin"}


def test_detects_training_type_change() -> None:
    """Con el NOMBRE del entrenamiento, no con su número. "tipo 10 -> 4" no lo
    entiende nadie, y este aviso existe para leerse de un vistazo."""
    new = {**TRAINING_OLD, "training_type": 4}
    out = diff_training(TRAINING_OLD, new)
    assert any(
        "Pases (defensas y centrocampistas) -> Anotación" in c for c in summaries(out)
    )


def test_detects_new_trainer() -> None:
    new = {**TRAINING_OLD, "trainer_name": "Nuevo DT"}
    out = diff_training(TRAINING_OLD, new)
    assert "Nuevo entrenador: Nuevo DT" in summaries(out)


def test_first_training_sync_has_no_diff() -> None:
    assert diff_training(None, TRAINING_OLD) == []


def test_standing_first_round_has_no_diff() -> None:
    assert diff_standing(None, 3, "Pulgas Arrechas") is None


def test_standing_position_improves() -> None:
    change = diff_standing(4, 2, "Pulgas Arrechas")
    assert change is not None
    assert change.summary == "Pulgas Arrechas subió de la posición 4 a la 2"
    # En una tabla, bajar de número es mejorar: el flag lo refleja.
    assert change.good is True


def test_standing_position_worsens() -> None:
    change = diff_standing(2, 5, "Pulgas Arrechas")
    assert change is not None
    assert change.summary == "Pulgas Arrechas bajó de la posición 2 a la 5"
    assert change.good is False


def test_standing_unchanged_position_is_none() -> None:
    assert diff_standing(3, 3, "Pulgas Arrechas") is None


def test_new_match_in_calendar_is_not_a_result_change() -> None:
    upcoming = MatchState(status="UPCOMING", home_goals=-1, away_goals=-1)
    assert diff_match(None, upcoming, is_home=True, opponent="Rival") is None


def test_match_becoming_finished_announces_result_home_win() -> None:
    before = MatchState(status="UPCOMING", home_goals=-1, away_goals=-1)
    after = MatchState(status="FINISHED", home_goals=2, away_goals=1)
    change = diff_match(before, after, is_home=True, opponent="Rival")
    assert change is not None
    assert change.summary == "Ganaste 2-1 vs Rival"
    assert change.good is True


def test_match_result_away_loss() -> None:
    before = MatchState(status="UPCOMING", home_goals=-1, away_goals=-1)
    after = MatchState(status="FINISHED", home_goals=3, away_goals=1)
    change = diff_match(before, after, is_home=False, opponent="Rival")
    assert change is not None
    assert change.summary == "Perdiste 1-3 vs Rival"
    assert change.good is False


def test_match_result_draw() -> None:
    before = MatchState(status="UPCOMING", home_goals=-1, away_goals=-1)
    after = MatchState(status="FINISHED", home_goals=1, away_goals=1)
    change = diff_match(before, after, is_home=True, opponent="Rival")
    assert change is not None
    assert change.summary == "Empataste 1-1 vs Rival"
    assert change.good is None  # un empate no es ni bueno ni malo


def test_already_known_result_is_not_repeated() -> None:
    before = MatchState(status="FINISHED", home_goals=2, away_goals=1)
    after = MatchState(status="FINISHED", home_goals=2, away_goals=1)
    assert diff_match(before, after, is_home=True, opponent="Rival") is None


def test_match_still_upcoming_is_not_announced() -> None:
    before = MatchState(status="UPCOMING", home_goals=-1, away_goals=-1)
    after = MatchState(status="UPCOMING", home_goals=-1, away_goals=-1)
    assert diff_match(before, after, is_home=True, opponent="Rival") is None


# ── El dato viaja aparte de la frase ────────────────────────────────────────
# La regresión que motivó todo esto: la UI sacaba el TSI de la frase con una
# regex, y al cambiar el separador de miles a punto `Number("202.210")` pasó a
# valer 202,21 — se mostró "TSI 202" para un jugador de 202 mil.

def test_big_numbers_survive_intact_next_to_the_formatted_phrase() -> None:
    new = {**PLAYER_OLD, "tsi": 202_210}
    change = by_metric(diff_player_skills({**PLAYER_OLD, "tsi": 198_930}, new, "Herilala"), "tsi")
    assert change.summary == "Herilala: TSI 198.930 -> 202.210"
    # Lo que de verdad importa: los enteros, sin pasar por el texto.
    assert (change.before, change.after) == (198_930, 202_210)
    assert change.detail()["before"] == 198_930
    assert change.detail()["after"] == 202_210


def test_detail_carries_what_the_ui_needs_to_render_without_parsing() -> None:
    change = by_metric(
        diff_player_skills(PLAYER_OLD, {**PLAYER_OLD, "tsi": 1200}, "Raul Cobos"), "tsi"
    )
    detail = change.detail()
    assert detail["metric"] == "tsi"
    assert detail["label"] == "TSI"
    assert detail["subject"] == "Raul Cobos"
    assert detail["kind"] == "count"
    assert detail["good"] is True


def test_detail_omits_empty_keys() -> None:
    """Un evento sin par numérico no debe guardar before/after nulos."""
    change = diff_player_skills(None, PLAYER_OLD, "Raul Cobos")[0]
    detail = change.detail()
    assert "before" not in detail
    assert "after" not in detail
    assert detail["kind"] == "event"


def test_spirit_change_keeps_both_the_level_and_its_name() -> None:
    out = diff_training({**TRAINING_OLD, "morale": 4}, {**TRAINING_OLD, "morale": 6})
    change = by_metric(out, "morale")
    assert (change.before, change.after) == (4, 6)
    assert change.before_label and change.after_label
    assert change.kind == "level"


def test_training_diff_ignores_temporary_psychology_placeholders() -> None:
    old = {**TRAINING_OLD, "morale": 6, "self_confidence": 5}

    # Ocultarse durante el partido no es bajar y reaparecer no es subir.
    assert not any(
        c.metric == "morale" for c in diff_training(old, {**old, "morale": -1})
    )
    assert not any(
        c.metric == "morale" for c in diff_training({**old, "morale": -1}, old)
    )
    assert not any(
        c.metric == "self_confidence"
        for c in diff_training(old, {**old, "self_confidence": None})
    )


def test_invalid_spirit_does_not_hide_a_real_confidence_change() -> None:
    old = {**TRAINING_OLD, "morale": 6, "self_confidence": 5}
    out = diff_training(old, {**old, "morale": -1, "self_confidence": 6})

    assert [change.metric for change in out] == ["self_confidence"]
    assert out[0].before == 5
    assert out[0].after == 6


def test_a_rival_signing_reads_as_competition_intel_not_as_my_own_change() -> None:
    """2026-08-19, pedido explícito: avisar cuando un club de tu liga o tu
    próximo rival de Copa, Masters o Promoción ficha.

    Va en su propia categoría porque no es un cambio TUYO: mezclarlo con las
    subidas de tu plantilla haría leer "fichó" como si hubieras fichado tú.
    """
    from app.domain.engines.sync_diff import diff_rival_purchase

    cambio = diff_rival_purchase(
        team_name="Charta F. C.",
        player_name="Arttu-Pekka Suutarinen",
        tsi=4730,
        price=552_000,
        competition="Copa",
        best_rating=6.5,
        currency="US$",
    )
    assert cambio.category == "rivales"
    assert "Charta F. C." in cambio.summary
    assert "Copa" in cambio.summary
    assert "4.730" in cambio.summary
    assert "6,5" in cambio.summary


def test_a_signing_that_has_not_played_yet_says_so_instead_of_showing_a_zero() -> None:
    """Un fichaje de ayer no tiene notas. Un 0 lo haría parecer malo en vez de
    nuevo, que son cosas distintas."""
    from app.domain.engines.sync_diff import diff_rival_purchase

    cambio = diff_rival_purchase(
        team_name="Cauca CF", player_name="Nuevo", tsi=100, price=1000,
        competition="tu liga", best_rating=None,
    )
    assert "todavía sin jugar" in cambio.summary
    assert "0,0" not in cambio.summary


def test_the_training_change_reaches_the_changes_screen() -> None:
    """2026-08-22, reportado por el usuario: cambió el tipo de entrenamiento y
    no aparecía en Cambios por ninguna parte.

    El cambio se guardaba desde siempre; lo que faltaba era sitio donde
    enseñarlo. La pantalla pinta el informe del club, y ese informe solo traía
    ánimo, confianza y economía.
    """
    from app.application.queries.sync_comparison import _club_item
    from app.domain.value_objects.ht_constants import TRAINING_TYPES

    fila = _club_item(
        "training_type", "Tipo de entrenamiento", 10, 2, TRAINING_TYPES,
        solo_nombre=True,
    )
    assert fila["beforeDisplay"] == "Pases (defensas y centrocampistas)"
    assert fila["currentDisplay"] == "Balón parado"
    assert fila["changed"] is True
    # Un tipo de entrenamiento es una categoría, no una cantidad: restar 10
    # menos 2 daría un "-8" sin ningún significado.
    assert fila["delta"] is None
