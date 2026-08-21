"""HTMS y HTMS28 contra los ejemplos publicados.

Los tres primeros tests reproducen los ejemplos del documento de referencia
(docs/reference/htms_formulas_hattrick.html). Si alguno cambia, HT Lens deja
de dar el mismo número que Foxtrick y la métrica pierde su gracia, que es
justamente poder compararla con la que ya usa la comunidad.
"""
from app.domain.engines import htms


def test_the_documented_ability_example_matches_to_the_point() -> None:
    """Portería 1, Defensa 16, Jugadas 12, Lateral 10, Pases 13,
    Anotación 5, Balón parado 7 → 2124."""
    assert htms.ability(1, 16, 12, 10, 13, 5, 7) == 2124


def test_a_seventeen_year_old_with_nothing_is_worth_his_remaining_training() -> None:
    """Un jugador de 17 años y 0 días con habilidad 0 tiene por delante once
    temporadas de entrenamiento: 1641 puntos."""
    assert htms.potential(0, 17, 0) == 1641


def test_days_already_lived_this_season_do_not_count_as_training_left() -> None:
    """17 años y 50 días: del año en curso solo quedan 62 días (8.857
    semanas × 10 puntos = 88.57), más las temporadas de 18 a 27."""
    assert htms.potential(400, 17, 50) == 1970
    # Y cuanto más viejo dentro del mismo año, menos le queda.
    assert htms.potential(400, 17, 0) > htms.potential(400, 17, 111)


def test_at_twenty_eight_the_potential_is_the_ability_itself() -> None:
    assert htms.potential(3000, 28, 0) == 3000


def test_past_twenty_eight_the_number_looks_backwards() -> None:
    """Para un veterano se descuenta lo entrenado de más: ya no es
    "potencial", es lo que valía a los 28."""
    assert htms.potential(3000, 30, 0) < 3000
    assert htms.potential(3000, 29, 0) > htms.potential(3000, 30, 0)


def test_an_unknown_skill_counts_as_nothing_not_as_zero_level() -> None:
    """Un rival sin ficha completa no debe salir con un HTMS inventado; las
    habilidades que no se conocen sencillamente no suman."""
    assert htms.ability(None, None, None, None, None, None, None) == 0
    assert htms.ability(None, 16, None, None, None, None, None) == 942


def test_a_skill_above_the_table_does_not_explode() -> None:
    """Divino (20) es el último nivel con nombre, pero la tabla llega a 23 y
    Hattrick puede dar más: se recorta al techo en vez de reventar."""
    assert htms.ability(0, 30, 0, 0, 0, 0, 0) == htms.ability(0, 23, 0, 0, 0, 0, 0)


def test_ability_and_potential_travel_together() -> None:
    r = htms.de_habilidades(20, 40, keeper=1, defending=16, playmaking=12,
                            winger=10, passing=13, scoring=5, set_pieces=7)
    assert r.ability == 2124
    assert r.potential == htms.potential(2124, 20, 40)
    assert r.margen == r.potential - r.ability
