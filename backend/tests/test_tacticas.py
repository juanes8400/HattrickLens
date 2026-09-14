"""La corrección por táctica: qué hace y qué no.

2026-09-12. El modelo mira ratings y no sabe qué táctica se jugó, y eso dejaba
un sesgo medido: Presionar prometía medio gol de más. Estos tests fijan el
contrato de la corrección, no los números del ajuste --ésos viven en
`FACTOR_POR_TACTICA` y se remiden cuando haya más partidos--.
"""

from __future__ import annotations

import pytest

from app.application.queries.prediccion_liga import reparto_de_tacticas
from app.domain.engines.prediccion import (
    FACTOR_POR_TACTICA,
    factor_de_tactica,
    goles_esperados,
    probabilidades_del_motor,
)

PRESIONAR, CONTRAATAQUES, NORMAL = 1, 2, 0


def _r(v: float) -> dict[str, float]:
    return {
        c: float(v)
        for c in (
            "midfield", "left_def", "central_def", "right_def",
            "left_att", "central_att", "right_att", "sp_def", "sp_att",
        )
    }


def test_sin_saber_la_tactica_no_se_toca_nada() -> None:
    """El caso por defecto tiene que ser exactamente el de antes.

    Es lo que corre cuando no hay historia del rival: media docena de sitios
    llaman al motor sin táctica, y ninguno puede cambiar de comportamiento por
    haber añadido esto.
    """
    assert factor_de_tactica() == 1.0
    assert factor_de_tactica(reparto={}) == 1.0
    assert factor_de_tactica(reparto=None, exacta=None) == 1.0
    ratings = _r(40)
    assert goles_esperados(ratings, ratings) == goles_esperados(ratings, ratings, 1.0)


def test_presionar_baja_los_goles_y_contraataques_los_sube() -> None:
    """La dirección importa más que el número: Presionar recorta ocasiones."""
    assert FACTOR_POR_TACTICA[PRESIONAR] < 1.0
    assert FACTOR_POR_TACTICA[CONTRAATAQUES] > 1.0
    ratings = _r(40)
    base = goles_esperados(ratings, ratings)
    presionando = goles_esperados(ratings, ratings, factor_de_tactica(exacta=PRESIONAR))
    contra = goles_esperados(ratings, ratings, factor_de_tactica(exacta=CONTRAATAQUES))
    assert presionando < base < contra


def test_una_tactica_desconocida_no_inventa_correccion() -> None:
    """Si Hattrick añade una táctica nueva, no se corrige: se deja en 1."""
    assert factor_de_tactica(exacta=999) == 1.0


def test_el_reparto_promedia_los_factores() -> None:
    """Ponderar, no apostar.

    Con la mitad de los partidos en Normal y la mitad presionando, el factor
    es el punto medio de los dos, no el de la más frecuente.
    """
    f = factor_de_tactica(reparto={NORMAL: 5, PRESIONAR: 5})
    esperado = (FACTOR_POR_TACTICA[NORMAL] + FACTOR_POR_TACTICA[PRESIONAR]) / 2
    assert f == pytest.approx(esperado)
    # Y con el reparto desbalanceado se acerca a la que más se usa.
    casi_normal = factor_de_tactica(reparto={NORMAL: 9, PRESIONAR: 1})
    assert casi_normal > f


def test_la_tactica_sabida_manda_sobre_el_reparto() -> None:
    """Si mandaste alineación, tu táctica no se adivina."""
    f = factor_de_tactica(reparto={NORMAL: 100}, exacta=PRESIONAR)
    assert f == FACTOR_POR_TACTICA[PRESIONAR]


def test_el_factor_escala_los_goles_en_proporcion() -> None:
    """Es un factor multiplicativo sobre lambda, no un sumando."""
    ratings = _r(35)
    base = goles_esperados(ratings, ratings)
    assert goles_esperados(ratings, ratings, 0.5) == pytest.approx(base * 0.5)


def test_presionar_cambia_la_terna_del_motor() -> None:
    """La corrección llega hasta las tres probabilidades, no se queda en los goles."""
    ratings = _r(40)
    normal = probabilidades_del_motor(ratings, ratings)
    # Yo presiono y el rival no: marco menos, así que gano menos.
    presionando = probabilidades_del_motor(
        ratings, ratings, factor_de_tactica(exacta=PRESIONAR), 1.0
    )
    assert presionando.victoria < normal.victoria
    assert presionando.derrota > normal.derrota
    assert presionando.victoria + presionando.empate + presionando.derrota == pytest.approx(1.0)


def test_el_reparto_se_cuenta_de_las_lecturas() -> None:
    """`reparto_de_tacticas` es lo que conecta las lecturas con el factor."""
    lecturas = [
        {"midfield": 10.0, "tactic_type": 0.0},
        {"midfield": 11.0, "tactic_type": 1.0},
        {"midfield": 12.0, "tactic_type": 1.0},
        {"midfield": 13.0},  # una lectura vieja, sin táctica guardada
    ]
    assert reparto_de_tacticas(lecturas) == {0: 1.0, 1: 2.0}
    # Y de ahí sale un factor que pesa dos tercios Presionar.
    esperado = (FACTOR_POR_TACTICA[NORMAL] + 2 * FACTOR_POR_TACTICA[PRESIONAR]) / 3
    assert factor_de_tactica(reparto_de_tacticas(lecturas)) == pytest.approx(esperado)
