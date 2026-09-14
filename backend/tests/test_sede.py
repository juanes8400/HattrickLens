"""La sede del partido que viene, que un resumen diluye.

2026-09-13. Medido: prediciendo con el promedio de los partidos anteriores, el
motor prometía un 41,5 % de victorias locales donde ocurrían un 50,1 %. La
ventaja de campo va dentro de los ratings --el medio campo en casa sale más
alto que fuera-- y un promedio mezcla partidos de casa y de fuera. Estos tests
fijan la corrección, no la cifra: la cifra vive en `RAZON_MEDIO_CASA_FUERA`.
"""

import math

import pytest

from app.api.v1.endpoints.rivals import _ratings_para_el_motor
from app.domain.engines.prediccion import (
    CAMPOS,
    RAZON_MEDIO_CASA_FUERA,
    corregir_sede,
    probabilidades_de_partido,
    resumen_de_lecturas,
)

CASA = math.sqrt(RAZON_MEDIO_CASA_FUERA)
SECTORES = ("midfield", "right_def", "central_def", "left_def", "right_att", "central_att", "left_att")


def _lectura(valor: float, en_casa: bool) -> dict[str, float]:
    return dict.fromkeys(CAMPOS, float(valor)) | {"en_casa": 1.0 if en_casa else 0.0}


def _plano(valor: float = 20.0) -> dict[str, float]:
    return dict.fromkeys(CAMPOS, valor)


def test_sin_sede_no_se_toca_nada() -> None:
    """Un partido hipotético, o en campo neutral: no hay ventaja que devolver."""
    lecturas = [_lectura(20, True), _lectura(20, False)]
    assert corregir_sede(_plano(), lecturas, None) == _plano()


def test_si_una_lectura_no_dice_donde_se_jugo_no_se_adivina() -> None:
    lecturas = [_lectura(20, True), _plano()]
    assert corregir_sede(_plano(), lecturas, True) == _plano()


def test_mitad_y_mitad_sube_en_casa_y_baja_fuera_y_solo_el_medio_campo() -> None:
    lecturas = [_lectura(20, True), _lectura(20, False)]
    en_casa = corregir_sede(_plano(), lecturas, True)
    fuera = corregir_sede(_plano(), lecturas, False)
    mezcla = 0.5 * CASA + 0.5 / CASA
    assert en_casa["midfield"] == pytest.approx(20 * CASA / mezcla)
    assert fuera["midfield"] == pytest.approx(20 / CASA / mezcla)
    # Entre las dos sedes queda exactamente la razón medida.
    assert en_casa["midfield"] / fuera["midfield"] == pytest.approx(RAZON_MEDIO_CASA_FUERA)
    for c in CAMPOS:
        if c != "midfield":
            assert en_casa[c] == fuera[c] == 20.0


def test_quien_solo_ha_jugado_en_casa_no_se_corrige_para_jugar_en_casa() -> None:
    """Usa la mezcla REAL del equipo: su promedio ya es de casa."""
    lecturas = [_lectura(20, True)] * 3
    assert corregir_sede(_plano(), lecturas, True)["midfield"] == pytest.approx(20.0)
    assert corregir_sede(_plano(), lecturas, False)["midfield"] == pytest.approx(
        20.0 / RAZON_MEDIO_CASA_FUERA
    )


def test_con_el_ultimo_partido_cuenta_la_sede_de_ese_partido() -> None:
    lecturas = [_lectura(20, True), _lectura(20, True), _lectura(20, False)]
    # El último fue fuera: si el próximo también es fuera, no hay nada que corregir.
    assert corregir_sede(_plano(), lecturas, False, "last")["midfield"] == pytest.approx(20.0)
    assert corregir_sede(_plano(), lecturas, True, "last")["midfield"] == pytest.approx(
        20.0 * RAZON_MEDIO_CASA_FUERA
    )


def test_el_resumen_de_lecturas_aplica_la_sede_si_se_la_dan() -> None:
    lecturas = [_lectura(20, True), _lectura(20, False)]
    sin = resumen_de_lecturas(lecturas)
    con = resumen_de_lecturas(lecturas, en_casa=True)
    assert sin is not None and con is not None
    assert con["midfield"] > sin["midfield"]
    assert con["left_att"] == sin["left_att"]


def test_el_local_sale_mejor_con_la_sede_que_sin_ella() -> None:
    """Dos equipos idénticos con historia mitad y mitad.

    Sin sede, sus promedios son iguales y el motor los ve igual de fuertes. Con
    ella, el local recupera la ventaja que el promedio le había quitado.
    """
    con_sede = [_lectura(20, True), _lectura(20, False)]
    sin_sede = [_plano(), _plano()]
    t_con = probabilidades_de_partido(con_sede, con_sede)
    t_sin = probabilidades_de_partido(sin_sede, sin_sede)
    assert t_con is not None and t_sin is not None
    assert t_con.victoria > t_sin.victoria
    assert t_con.derrota < t_sin.derrota


def test_rivales_corrige_el_resumen_y_no_la_alineacion_enviada() -> None:
    historia = [_lectura(20, True), _lectura(20, False)]
    sin, _ = _ratings_para_el_motor(historia, historia, "average")
    con, prestadas = _ratings_para_el_motor(historia, historia, "average", en_casa=True)
    assert not prestadas
    assert con["midfield"] > sin["midfield"]

    # La alineación enviada no es un partido jugado y no dice dónde: se deja
    # tal cual, aunque se sepa la sede del cruce.
    enviada = dict.fromkeys(SECTORES, 30)
    con_enviada, prestadas = _ratings_para_el_motor([enviada], historia, "submitted", en_casa=True)
    assert prestadas
    assert con_enviada["midfield"] == 30
