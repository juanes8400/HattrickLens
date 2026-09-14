"""Controles algebraicos del modelo de rutas Normal 30/40/30."""

from __future__ import annotations

import importlib
import sys

import numpy as np
import pytest

from scripts import comparar_agregadores_ataque

# El script se ejecuta también directamente y por eso importa a su hermano como
# módulo de primer nivel. Registrarlo aquí permite probarlo mediante el paquete
# ``scripts`` sin modificar el código del experimento.
sys.modules.setdefault("comparar_agregadores_ataque", comparar_agregadores_ataque)
rutas = importlib.import_module("scripts.comparar_rutas_normales")


def aporte_de_rutas(probabilidades: list[float], exponente: float) -> float:
    """Devuelve la suma ponderada, deshaciendo el logaritmo de ``eta``."""
    log_carriles = np.log(np.asarray([probabilidades], dtype=float))
    termino = rutas.termino_de_ataque(
        "rutas 30/40/30",
        exponente,
        log_carriles,
    )
    return float(np.exp(termino[0]))


def test_rutas_aplica_la_ecuacion_exacta_30_40_30() -> None:
    probabilidades = [0.2, 0.5, 0.8]
    exponente = 1.7

    observado = aporte_de_rutas(probabilidades, exponente)
    esperado = (
        0.30 * probabilidades[0] ** exponente
        + 0.40 * probabilidades[1] ** exponente
        + 0.30 * probabilidades[2] ** exponente
    )

    assert observado == pytest.approx(esperado)


def test_rutas_es_simetrico_entre_izquierda_y_derecha() -> None:
    original = aporte_de_rutas([0.15, 0.55, 0.90], exponente=1.3)
    lados_intercambiados = aporte_de_rutas([0.90, 0.55, 0.15], exponente=1.3)

    assert lados_intercambiados == pytest.approx(original)


def test_el_centro_recibe_cuarenta_por_ciento_del_incremento() -> None:
    base = aporte_de_rutas([0.2, 0.2, 0.2], exponente=1.0)
    centro_reforzado = aporte_de_rutas([0.2, 0.8, 0.2], exponente=1.0)
    banda_reforzada = aporte_de_rutas([0.8, 0.2, 0.2], exponente=1.0)

    assert centro_reforzado - base == pytest.approx(0.40 * (0.8 - 0.2))
    assert banda_reforzada - base == pytest.approx(0.30 * (0.8 - 0.2))


@pytest.mark.parametrize(
    ("probabilidad", "exponente"),
    [
        (1e-3, 0.25),
        (0.2, 1.0),
        (0.5, 1.7),
        (1.0, 3.0),
    ],
)
def test_carriles_iguales_equivalen_a_probabilidad_elevada(
    probabilidad: float,
    exponente: float,
) -> None:
    observado = aporte_de_rutas([probabilidad] * 3, exponente)

    assert observado == pytest.approx(probabilidad**exponente)


def test_rutas_produce_lambdas_y_probabilidades_1x2_finitas() -> None:
    ajuste = rutas.Ajuste(
        parametros=np.asarray([-0.2, 0.8, 1.4, -2.0, 0.2, 0.9, -0.05]),
        centro=-0.5,
        nll=0.0,
        convergio=True,
    )
    diseno = np.log(
        np.asarray(
            [
                [1e-3, 1e-3, 0.5, 1.0, 1e-3],
                [1.0, 1.0, 0.5, 1e-3, 1.0],
                [0.5, 0.2, 0.8, 0.4, 0.7],
                [0.5, 0.4, 0.8, 0.2, 0.3],
            ],
            dtype=float,
        )
    )

    intensidades = rutas.lambdas(ajuste, diseno, "rutas 30/40/30")
    probabilidades = rutas.probabilidades_resultado(intensidades)

    assert np.isfinite(intensidades).all()
    assert (intensidades > 0.0).all()
    assert np.isfinite(probabilidades).all()
    assert (probabilidades >= 0.0).all()
    assert (probabilidades <= 1.0).all()
    assert probabilidades.sum(axis=1) == pytest.approx(np.ones(2))
