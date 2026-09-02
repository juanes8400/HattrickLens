"""Los nueve modelos añadidos el 2026-09-01, y por qué cada uno.

Pedidos por el usuario para la proyección de caja. Lo que se fija aquí no es
que «funcionen» --devolver números es fácil-- sino la propiedad por la que
cada uno entró: si esa propiedad se pierde, el modelo deja de aportar nada que
no aportara ya otro de la lista.

La serie de referencia imita a la de verdad: una caja que sube despacio con
una semana rara en medio, que es lo que hace un traspaso o el pago de una
ampliación.
"""

import numpy as np

from app.domain.engines import timeseries as ts

#: Ocho semanas, la última lectura del umbral. El 340 es el pico.
CON_PICO = np.array([100.0, 104.0, 101.0, 107.0, 340.0, 110.0, 113.0, 116.0])
TRANQUILA = np.array([100.0, 102.0, 101.0, 103.0, 102.0, 104.0, 103.0, 105.0])


def test_todo_modelo_registrado_declara_cuantos_datos_necesita() -> None:
    """El registro y la tabla de mínimos se leen juntos en `auto_forecast`, y
    un modelo sin mínimo reventaría con KeyError justo al añadirlo."""
    assert set(ts.MODELS) == set(ts.MIN_POINTS)


def test_ninguno_devuelve_infinitos_ni_huecos() -> None:
    for nombre, fn in ts.MODELS.items():
        salida = fn(CON_PICO, 6)
        assert len(salida) == 6, nombre
        assert np.all(np.isfinite(salida)), nombre


def test_la_mediana_movil_ignora_el_pico_y_la_media_no() -> None:
    """El motivo entero por el que entró `median_k`. La serie ronda 110 con un
    340 suelto: la media de las últimas semanas se lo come, la mediana no."""
    mediana = ts.MODELS["median_k"](CON_PICO, 1)[0]
    media = ts.MODELS["mean_k"](np.array([100.0, 340.0, 110.0, 113.0]), 1)[0]
    assert 100 <= mediana <= 120
    assert media > 130  # arrastrada por una sola semana


def test_theil_sen_aguanta_un_extremo_torcido_y_drift_no() -> None:
    """`drift` mira SÓLO el primer punto y el último, así que un traspaso justo
    en una de esas dos semanas inclina las 52 proyectadas."""
    limpia = np.array([100.0, 102.0, 104.0, 106.0, 108.0, 110.0, 112.0, 114.0])
    torcida = limpia.copy()
    torcida[-1] = 400.0  # la última semana se dispara

    drift_limpio = ts.MODELS["drift"](limpia, 1)[0]
    drift_torcido = ts.MODELS["drift"](torcida, 1)[0]
    sen_limpio = ts.MODELS["theil_sen"](limpia, 1)[0]
    sen_torcido = ts.MODELS["theil_sen"](torcida, 1)[0]

    assert abs(drift_torcido - drift_limpio) > 200
    assert abs(sen_torcido - sen_limpio) < abs(drift_torcido - drift_limpio)


def test_el_drift_amortiguado_no_se_dispara_a_52_semanas() -> None:
    """El horizonte de la pantalla es un año entero. `drift` extrapola la misma
    recta hasta el final; amortiguado se aplana, que es lo honesto cuando la
    pendiente sale de ocho lecturas."""
    sube = np.array([100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0, 170.0])
    recto = ts.MODELS["drift"](sube, 52)[-1]
    apagado = ts.MODELS["drift_damped"](sube, 52)[-1]
    assert recto > 650  # 170 + 10 por semana durante un año
    assert apagado < recto / 2


def test_theta_apunta_en_el_sentido_de_la_tendencia_pero_menos_que_drift() -> None:
    """Es medio camino a propósito: SES para el nivel y la mitad de la
    pendiente para el rumbo."""
    sube = np.array([100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0, 170.0])
    theta = ts.MODELS["theta"](sube, 8)[-1]
    plano = ts.MODELS["ses"](sube, 8)[-1]
    recto = ts.MODELS["drift"](sube, 8)[-1]
    assert plano < theta < recto


def test_ar1_vuelve_hacia_la_media_y_los_suavizados_no() -> None:
    """La propiedad que ninguno de los otros tenía: después de una semana alta
    puede decir que la siguiente baja."""
    alterna = np.array([100.0, 120.0, 100.0, 120.0, 100.0, 120.0, 100.0, 120.0])
    ar = ts.MODELS["ar1"](alterna, 40)
    media = float(np.mean(alterna))

    # Alterna alrededor de la media, como la serie: es lo que ninguno de los
    # otros sabe hacer. SES devolvería la misma cifra cuarenta veces.
    assert (ar[0] - media) * (ar[1] - media) < 0

    # Y se va acercando, sin quedarse clavado ni dispararse. Despacio, porque
    # el coeficiente se recorta a 0,95: cuarenta semanas después todavía queda
    # rastro, y eso es honesto -- la serie de verdad tampoco se apaga de golpe.
    distancias = np.abs(ar - media)
    assert distancias[-1] < distancias[0]
    assert np.all(np.diff(distancias) <= 1e-9)
    assert distancias[-1] < 2.0


def test_el_naive_estacional_repite_la_temporada_anterior() -> None:
    m = ts.SEASON_WEEKS
    una_temporada = np.arange(m, dtype=float) * 10
    salida = ts.MODELS["seasonal_naive"](una_temporada, m)
    assert list(salida) == list(una_temporada)


def test_el_estacional_parcial_no_espera_a_tener_dos_temporadas() -> None:
    """Es su razón de ser: `holt_winters` exige 32 lecturas y éste trabaja con
    una temporada y pico."""
    m = ts.SEASON_WEEKS
    ciclo = np.tile(np.array([0.0, 5.0, -5.0, 2.0] * (m // 4)), 2)[: m + 6]
    serie = 100 + np.arange(len(ciclo)) * 1.0 + ciclo
    salida = ts.MODELS["seasonal_holt"](serie, 8)
    assert len(salida) == 8
    assert np.all(np.isfinite(salida))
    # Y con menos de un ciclo y pico cae a Holt en vez de inventarse la
    # estacionalidad.
    corta = serie[:10]
    assert np.allclose(ts.MODELS["seasonal_holt"](corta, 4), ts.MODELS["holt"](corta, 4))


def test_la_combinacion_se_queda_en_medio_y_nunca_en_un_extremo() -> None:
    """Es una mediana: por construcción no puede salirse del rango de lo que
    dicen sus componentes, que es justo lo que la hace estable."""
    combo = ts.MODELS["combo"](CON_PICO, 4)
    bases = np.array(
        [
            ts.MODELS[n](CON_PICO, 4)
            for n in ts.COMBO_BASE
            if len(CON_PICO) >= ts.MIN_POINTS[n]
        ]
    )
    assert np.all(combo >= bases.min(axis=0) - 1e-9)
    assert np.all(combo <= bases.max(axis=0) + 1e-9)


def test_la_combinacion_no_se_llama_a_si_misma() -> None:
    """Si `combo` entrara en `COMBO_BASE` el cálculo no terminaría nunca."""
    assert "combo" not in ts.COMBO_BASE


def test_a_las_ocho_lecturas_compiten_los_de_serie_corta_y_no_los_estacionales() -> None:
    """El umbral del que cuelga todo esto: con ocho semanas se abre la ruta
    temporal, pero lo estacional sigue fuera --no hay ciclo que mirar--."""
    f = ts.auto_forecast(TRANQUILA, horizon=4)
    assert "theta" in f.candidates
    assert "combo" in f.candidates
    assert "median_k" in f.candidates
    for estacional in ("seasonal_naive", "seasonal_holt", "holt_winters"):
        assert estacional not in f.candidates


def test_con_dos_temporadas_entran_todos() -> None:
    larga = 100 + np.arange(2 * ts.SEASON_WEEKS + 2, dtype=float) * 2
    f = ts.auto_forecast(larga, horizon=4)
    assert set(f.candidates) == set(ts.MODELS)


def test_el_ganador_sigue_saliendo_del_backtest_y_no_de_una_preferencia() -> None:
    """Una serie plana con ruido: los que inventan tendencia tienen que perder
    contra los que no."""
    plana = np.array([100.0, 101.0, 99.0, 100.0, 101.0, 99.0, 100.0, 101.0])
    f = ts.auto_forecast(plana, horizon=4)
    assert f.candidates[f.model] == min(f.candidates.values())
    assert np.all(np.isfinite(f.point))


def test_una_banda_nunca_se_cierra_del_todo() -> None:
    """Un modelo que no falló ni una vez dentro de la muestra no puede
    prometer certeza absoluta un año por delante.

    Con una serie que alterna cada dos semanas, `seasonal_naive` la reproduce
    exacta --16 es par-- y la desviación de sus residuos salía CERO: p10, p50 y
    p90 se pegaban en una raya. El suelo no se inventa: es cuánto se mueve la
    serie de una semana a la siguiente.
    """
    alterna = np.array([100.0, 160.0] * 12)
    f = ts.auto_forecast(alterna, horizon=12)
    assert f.residual_std > 0
    assert f.lower[-1] < f.point[-1] < f.upper[-1]


def test_una_serie_constante_si_puede_no_tener_banda() -> None:
    """La otra cara: si la serie no se mueve NUNCA, cero es la respuesta
    honesta y no se ensancha por ensanchar."""
    plana = np.full(12, 500.0)
    f = ts.auto_forecast(plana, horizon=6)
    assert f.residual_std == 0.0
    assert f.lower[-1] == f.point[-1] == f.upper[-1]
