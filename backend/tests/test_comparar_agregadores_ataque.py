"""Controles algebraicos de la comparación producto frente a noisy-OR."""

from __future__ import annotations

from itertools import permutations

import numpy as np
import pytest

from scripts.comparar_agregadores_ataque import (
    caracteristica_noisy_or,
    caracteristica_producto,
    probabilidades_resultado,
)


def test_valores_exactos_para_dos_tres_cuatro_decimas() -> None:
    probabilidades = [0.2, 0.3, 0.4]

    assert caracteristica_producto(probabilidades) == pytest.approx(
        np.log(0.2 * 0.3 * 0.4)
    )
    assert caracteristica_noisy_or(probabilidades) == pytest.approx(
        np.log(1.0 - (1.0 - 0.2) * (1.0 - 0.3) * (1.0 - 0.4))
    )


@pytest.mark.parametrize(
    "agregador", [caracteristica_producto, caracteristica_noisy_or]
)
def test_el_orden_de_las_tres_vias_no_cambia_el_resultado(agregador) -> None:
    resultados = [
        agregador(list(probabilidades))
        for probabilidades in permutations((0.2, 0.3, 0.4))
    ]

    assert resultados == pytest.approx([resultados[0]] * len(resultados))


@pytest.mark.parametrize(
    "agregador", [caracteristica_producto, caracteristica_noisy_or]
)
def test_es_finito_y_monotono_en_el_dominio_operativo(agregador) -> None:
    minimo = agregador([1e-3, 1e-3, 1e-3])
    intermedio = agregador([1e-3, 0.5, 1e-3])
    maximo = agregador([1.0, 1.0, 1.0])

    assert np.isfinite([minimo, intermedio, maximo]).all()
    assert minimo < intermedio <= maximo


def test_las_probabilidades_1x2_suman_uno() -> None:
    probabilidades = probabilidades_resultado(
        np.asarray([0.2, 0.3, 1.2, 0.8, 8.0, 0.05], dtype=float)
    )

    assert probabilidades.shape == (3, 3)
    assert (probabilidades >= 0.0).all()
    assert (probabilidades <= 1.0).all()
    assert probabilidades.sum(axis=1) == pytest.approx(np.ones(3))
