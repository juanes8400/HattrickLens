"""Minutos jugados a partir del once inicial y los cambios.

El fixture es un partido de selección real (matchID 41943634, Rwanda contra
Guinea Ecuatorial, 2026-08-21), pedido con `sourceSystem=htointegrated`.
"""
from pathlib import Path

from app.domain.engines.national_team import Cambio, minutos_jugados
from app.infrastructure.chpp.parsers import get_parser

FIXTURES = Path(__file__).parent / "fixtures"

TITULAR_SUSTITUIDO = 487733739
SUPLENTE_QUE_ENTRO = 487848026
TITULAR_COMPLETO = 488580012
CAMBIO_DE_POSICION = 486496709   # sale y entra él mismo: no es un cambio
SUPLENTE_NO_USADO = 489806840


def _del_partido_real() -> tuple[set[int], list[Cambio]]:
    d = get_parser("matchlineup")((FIXTURES / "matchlineup_seleccion.xml").read_bytes())
    titulares = set(d["starting_lineup"])
    cambios = [Cambio(**c) for c in d["substitutions"]]
    return titulares, cambios


def test_el_fixture_trae_las_tres_piezas() -> None:
    titulares, cambios = _del_partido_real()
    assert len(titulares) == 11
    assert len(cambios) == 4
    assert all(c.minuto == 60 for c in cambios)


def test_titular_que_juega_entero() -> None:
    titulares, cambios = _del_partido_real()
    assert minutos_jugados(titulares, cambios, TITULAR_COMPLETO) == 90


def test_titular_sustituido_en_el_60() -> None:
    titulares, cambios = _del_partido_real()
    assert minutos_jugados(titulares, cambios, TITULAR_SUSTITUIDO) == 60


def test_suplente_que_entra_en_el_60() -> None:
    titulares, cambios = _del_partido_real()
    assert minutos_jugados(titulares, cambios, SUPLENTE_QUE_ENTRO) == 30


def test_suplente_que_nunca_entra() -> None:
    titulares, cambios = _del_partido_real()
    assert minutos_jugados(titulares, cambios, SUPLENTE_NO_USADO) == 0


def test_cambiar_de_posicion_no_es_salir() -> None:
    """Mismo jugador a los dos lados del cambio: sigue en el campo."""
    titulares, cambios = _del_partido_real()
    assert minutos_jugados(titulares, cambios, CAMBIO_DE_POSICION) == 90


def test_quien_no_estuvo_convocado() -> None:
    titulares, cambios = _del_partido_real()
    assert minutos_jugados(titulares, cambios, 1) == 0


def test_entra_y_vuelve_a_salir() -> None:
    """Entra en el 30 por lesión de otro y sale en el 70: 40 minutos."""
    cambios = [Cambio(sale=10, entra=20, minuto=30), Cambio(sale=20, entra=30, minuto=70)]
    assert minutos_jugados({10, 11}, cambios, 20) == 40


def test_un_minuto_fuera_de_rango_no_da_negativos() -> None:
    cambios = [Cambio(sale=10, entra=20, minuto=120)]
    assert minutos_jugados({10}, cambios, 10) == 90
    assert minutos_jugados({10}, cambios, 20) == 0
