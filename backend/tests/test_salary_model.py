"""La curva que estima el sueldo de quien nadie lo anotó.

2026-09-04. De las 599 etapas de Pulgas Arrechas, 515 llevan el sueldo a cero
por ignorancia: el jugador pasó por el club antes de que existiera HT Lens y
Hattrick no publica hacia atrás lo que cobraba. Contarlo como cero es
equivocarse el 100%, así que se estima y se marca.
"""

import math

import pytest

from app.domain.engines.salary_model import (
    MINIMO_DE_LECTURAS,
    LecturaDeSueldo,
    ajustar,
)


def _sintetico(n: int = 60, a: float = 3.7, b: float = 0.73, c: float = -0.01):
    """Lecturas que siguen exactamente la curva, para poder recuperarla."""
    salida = []
    for i in range(n):
        tsi = 500 + i * 900
        edad = 17 + (i % 14)
        sueldo = math.exp(a + b * math.log(tsi) + c * edad)
        salida.append(LecturaDeSueldo(tsi=tsi, edad=edad, salario=round(sueldo)))
    return salida


def test_recupera_la_curva_con_la_que_se_generaron_los_datos() -> None:
    modelo = ajustar(_sintetico())
    assert modelo is not None
    assert modelo.a == pytest.approx(3.7, abs=0.05)
    assert modelo.b == pytest.approx(0.73, abs=0.01)
    assert modelo.c == pytest.approx(-0.01, abs=0.005)


def test_sin_lecturas_suficientes_no_se_inventa_una_curva() -> None:
    """Mejor sin estimación que con una recta ajustada a cuatro puntos."""
    assert ajustar(_sintetico(n=MINIMO_DE_LECTURAS - 1)) is None
    assert ajustar([]) is None


def test_sin_variacion_de_tsi_tampoco() -> None:
    """Todos con el mismo TSI: la pendiente no se puede estimar y el ajuste
    degeneraría en una constante disfrazada de modelo."""
    iguales = [LecturaDeSueldo(tsi=20_000, edad=20 + i % 5, salario=9_000) for i in range(40)]
    assert ajustar(iguales) is None


def test_el_ancla_de_un_jugador_corrige_toda_su_carrera() -> None:
    """El hallazgo que hace útil el relleno de fichas.

    Cada jugador se sienta a una distancia estable de la curva --su sesgo
    personal resultó 8,2 veces mayor que su propio ruido-- así que UNA lectura
    suya fija el nivel y arregla el resto de su etapa.
    """
    modelo = ajustar(_sintetico())
    assert modelo is not None
    # Un jugador que cobra un 40% más de lo que la curva dice.
    sesgo = math.log(1.40)
    lectura = LecturaDeSueldo(
        tsi=30_000,
        edad=25,
        salario=round(modelo.estimar(30_000, 25) * 1.40),
    )
    ancla = modelo.ancla_de(lectura)
    assert ancla == pytest.approx(sesgo, abs=0.01)

    # Con el ancla, otra semana suya se estima bien; sin ella, se queda corta.
    real = round(modelo.estimar(45_000, 26) * 1.40)
    con_ancla = modelo.estimar(45_000, 26, ancla=ancla)
    sin_ancla = modelo.estimar(45_000, 26)
    assert abs(con_ancla - real) / real < 0.01
    assert abs(sin_ancla - real) / real > 0.2


def test_sin_tsi_no_hay_estimacion() -> None:
    """Sin la única entrada del modelo no se devuelve un número: se devuelve
    nada, que es lo que la pantalla enseñará como desconocido."""
    modelo = ajustar(_sintetico())
    assert modelo is not None
    assert modelo.estimar(None, 25) is None
    assert modelo.estimar(0, 25) is None


def test_la_edad_puede_faltar_sin_romper_nada() -> None:
    """La edad al vender se conoce en 352 de 598 etapas. Donde falta, la curva
    sigue estimando: peor (33,9 % en vez de 28,7 %) pero estimando."""
    modelo = ajustar(_sintetico())
    assert modelo is not None
    assert modelo.estimar(30_000, None) is not None


def test_todas_las_edades_iguales_cae_a_la_curva_de_solo_tsi() -> None:
    """Sistema singular por la columna de edad constante. En vez de rendirse
    se reajusta sin ese término, que es lo que hace la versión de sólo TSI."""
    planas = [
        LecturaDeSueldo(tsi=1_000 + i * 700, edad=20, salario=round(math.exp(3.7 + 0.73 * math.log(1_000 + i * 700))))
        for i in range(40)
    ]
    modelo = ajustar(planas)
    assert modelo is not None
    assert modelo.c == 0.0
    assert modelo.b == pytest.approx(0.73, abs=0.02)
