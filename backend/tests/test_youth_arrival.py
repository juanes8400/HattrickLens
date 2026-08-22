"""El suelo de la etapa de un canterano.

Regla del usuario (2026-08-22): en Hattrick nadie llega al primer equipo antes
de los 17 años, así que la fecha en que los cumplió es lo más atrás que tiene
sentido buscar sus partidos. Sirve para RECORRER, no para decir que llegó ese
día: no se guarda como fecha de llegada ni se enseña.
"""
from datetime import datetime

from app.domain.engines.youth_arrival import (
    cuando_cumplio_diecisiete,
    dias_desde_los_diecisiete,
    llegada_mas_temprana,
)
from app.domain.value_objects.skill import Age


def test_the_real_case_that_started_this() -> None:
    """Carlos Andrés Tocancipá: vendido el 25/02/2022 con 17 años y 4 días.
    Cumplió los 17 cuatro días antes, así que su etapa cabe en esa semana."""
    vendido = datetime(2022, 2, 25, 0, 16)
    assert cuando_cumplio_diecisiete(Age(17, 4), vendido) == datetime(2022, 2, 21, 0, 16)


def test_exactly_seventeen_means_the_floor_is_that_very_day() -> None:
    momento = datetime(2026, 8, 22, 12, 0)
    assert cuando_cumplio_diecisiete(Age(17, 0), momento) == momento
    assert dias_desde_los_diecisiete(Age(17, 0)) == 0


def test_an_older_player_pushes_the_floor_further_back() -> None:
    """Un canterano vendido con 21 años y 61 días lleva 509 días sobre los 17,
    así que hay que mirar año y medio hacia atrás. Es el caso caro, y sale
    solo de la aritmética: no se recorta."""
    assert dias_desde_los_diecisiete(Age(21, 61)) == 509
    vendido = datetime(2024, 9, 14)
    assert cuando_cumplio_diecisiete(Age(21, 61), vendido) == datetime(2023, 4, 24)


def test_a_hattrick_year_is_a_hundred_and_twelve_days() -> None:
    assert dias_desde_los_diecisiete(Age(18, 0)) == 112


def test_the_week_label_comes_from_outside() -> None:
    """El motor no sabe de temporadas: se le pasa quién traduce fechas, para
    que no dependa de la base."""
    r = llegada_mas_temprana(
        Age(17, 4), datetime(2022, 2, 25), semana_de=lambda _: "72-09"
    )
    assert r.fecha == datetime(2022, 2, 21)
    assert r.semana == "72-09"
    # Y sin traductor, la fecha sigue siendo válida.
    assert llegada_mas_temprana(Age(17, 4), datetime(2022, 2, 25)).semana is None
