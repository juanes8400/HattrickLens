"""Garantías de comparabilidad del A/B entre el motor y Poisson pura."""

from __future__ import annotations

import pytest

from app.domain.engines import prediccion


def _ratings(valor: float) -> dict[str, float]:
    return {campo: valor + indice for indice, campo in enumerate(prediccion.CAMPOS)}


def test_el_motor_actual_es_exactamente_la_mezcla_publicada() -> None:
    local, visitante = _ratings(42), _ratings(31)
    poisson = prediccion.probabilidades_poisson(local, visitante)
    ordinal = prediccion.modelo_ajustado().probabilidades(
        prediccion.variables(local, visitante)
    )
    actual = prediccion.probabilidades_del_motor(local, visitante)

    assert pytest.approx(1.0) == prediccion.PESO_GOLES + prediccion.PESO_ORDINAL
    assert actual.victoria == pytest.approx(
        prediccion.PESO_GOLES * poisson.victoria
        + prediccion.PESO_ORDINAL * ordinal.victoria
    )
    assert actual.empate == pytest.approx(
        prediccion.PESO_GOLES * poisson.empate
        + prediccion.PESO_ORDINAL * ordinal.empate
    )
    assert actual.derrota == pytest.approx(
        prediccion.PESO_GOLES * poisson.derrota
        + prediccion.PESO_ORDINAL * ordinal.derrota
    )


def test_poner_la_ordinal_en_cero_es_poisson_pura(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local, visitante = _ratings(42), _ratings(31)
    esperado = prediccion.probabilidades_poisson(local, visitante)

    monkeypatch.setattr(prediccion, "PESO_ORDINAL", 0.0)
    monkeypatch.setattr(prediccion, "PESO_GOLES", 1.0)

    assert prediccion.probabilidades_del_motor(local, visitante) == esperado


def test_el_ab_conserva_las_mismas_lecturas_de_entrada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    local, visitante = _ratings(42), _ratings(31)
    esperado = prediccion.probabilidades_poisson(local, visitante)
    monkeypatch.setattr(prediccion, "PESO_ORDINAL", 0.0)
    monkeypatch.setattr(prediccion, "PESO_GOLES", 1.0)

    desde_el_flujo = prediccion.probabilidades_de_partido([local], [visitante])

    assert desde_el_flujo == esperado
