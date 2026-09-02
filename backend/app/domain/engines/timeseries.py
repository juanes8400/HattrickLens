"""Motor de series de tiempo — puro NumPy, sin dependencias pesadas.

Escalera de modelos, de menos a más exigente en datos (m = 16 semanas = una
temporada de Hattrick):

    n >= 2   naive, drift
    n >= 3   media y mediana de las últimas k, drift amortiguado
    n >= 4   SES, Theta, Theil-Sen, y la combinación de los simples
    n >= 6   Holt con tendencia amortiguada, AR(1)
    n >= m+1 naive estacional
    n >= m+4 estacional con ciclos incompletos + Holt
    n >= 2m  Holt-Winters aditivo estacional

`auto_forecast` no elige el modelo por criterio del autor: hace **backtesting
de origen móvil** sobre el histórico real y se queda con el que menos error
comete. Con pocos datos ganan los modelos simples; a medida que la serie crece,
los complejos se ganan su sitio solos.

Los intervalos de predicción salen de los residuos observados un paso adelante,
escalados con sqrt(h). Es una aproximación —no asume normalidad de la serie,
solo la usa para el ancho de banda— y es honesta: si el modelo ha fallado
históricamente, las bandas serán anchas.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import numpy as np

SEASON_WEEKS = 16  # una temporada de Hattrick


@dataclass
class Forecast:
    model: str
    point: list[float]
    lower: list[float]  # p10
    upper: list[float]  # p90
    residual_std: float
    backtest_mae: float | None = None
    candidates: dict[str, float] = field(default_factory=dict)  # modelo → MAE

    @property
    def horizon(self) -> int:
        return len(self.point)


# ─────────────────────────── modelos ───────────────────────────


def _naive(y: np.ndarray, h: int) -> np.ndarray:
    return np.full(h, y[-1], dtype=float)


def _drift(y: np.ndarray, h: int) -> np.ndarray:
    if len(y) < 2:
        return _naive(y, h)
    slope = (y[-1] - y[0]) / (len(y) - 1)
    return np.asarray(y[-1] + slope * np.arange(1, h + 1), dtype=float)


def _ses(y: np.ndarray, h: int, alpha: float | None = None) -> np.ndarray:
    alpha = alpha if alpha is not None else _fit_alpha(y)
    level = y[0]
    for v in y[1:]:
        level = alpha * v + (1 - alpha) * level
    return np.full(h, level, dtype=float)


def _fit_alpha(y: np.ndarray) -> float:
    best, best_sse = 0.3, np.inf
    for a in np.arange(0.05, 1.0, 0.05):
        level, sse = y[0], 0.0
        for v in y[1:]:
            sse += (v - level) ** 2
            level = a * v + (1 - a) * level
        if sse < best_sse:
            best, best_sse = float(a), sse
    return best


def _holt(y: np.ndarray, h: int) -> np.ndarray:
    """Holt con tendencia amortiguada: evita extrapolaciones absurdas."""
    best_params, best_sse = (0.3, 0.1, 0.9), np.inf
    for a in (0.1, 0.3, 0.5, 0.7, 0.9):
        for b in (0.05, 0.1, 0.3, 0.5):
            for phi in (0.8, 0.9, 0.98):
                level, trend, sse = y[0], y[1] - y[0], 0.0
                for v in y[1:]:
                    pred = level + phi * trend
                    sse += (v - pred) ** 2
                    new_level = a * v + (1 - a) * pred
                    trend = b * (new_level - level) + (1 - b) * phi * trend
                    level = new_level
                if sse < best_sse:
                    best_sse, best_params = sse, (a, b, phi)

    a, b, phi = best_params
    level, trend = y[0], y[1] - y[0]
    for v in y[1:]:
        pred = level + phi * trend
        new_level = a * v + (1 - a) * pred
        trend = b * (new_level - level) + (1 - b) * phi * trend
        level = new_level
    damping = np.cumsum(phi ** np.arange(1, h + 1))
    return np.asarray(level + trend * damping, dtype=float)


def _holt_winters(y: np.ndarray, h: int, m: int = SEASON_WEEKS) -> np.ndarray:
    """Holt-Winters aditivo. Requiere al menos dos ciclos completos."""
    if len(y) < 2 * m:
        return _holt(y, h)
    n_cycles = len(y) // m
    seasonal = np.zeros(m)
    for i in range(m):
        idx = [i + c * m for c in range(n_cycles) if i + c * m < len(y)]
        seasonal[i] = y[idx].mean()
    seasonal -= seasonal.mean()

    deseason = y - np.tile(seasonal, len(y) // m + 1)[: len(y)]
    base = _holt(deseason, h)
    season_future = np.array([seasonal[(len(y) + i) % m] for i in range(h)])
    return np.asarray(base + season_future, dtype=float)


# ─────────────────── modelos añadidos el 2026-09-01 ───────────────────
#
# Pedidos por el usuario. Ninguno trae dependencias: siguen siendo numpy y
# aritmética, igual que los cinco de arriba.


def _mean_k(y: np.ndarray, h: int, k: int = 4) -> np.ndarray:
    """El promedio de las últimas k semanas, repetido.

    Suelo honesto para una serie plana con ruido, donde `naive` se cree la
    última lectura entera y `drift` inventa una pendiente que no existe.
    """
    k = min(k, len(y))
    return np.full(h, float(np.mean(y[-k:])), dtype=float)


def _median_k(y: np.ndarray, h: int, k: int = 5) -> np.ndarray:
    """La MEDIANA de las últimas k semanas.

    La misma idea que `_mean_k` pero inmune a la semana rara, y esta serie las
    tiene: una venta o el pago de una ampliación mueven la caja de golpe. El
    módulo ya sabe encontrar esos picos --`detect_anomalies`-- pero ningún
    modelo los ignoraba: todos los promediaban como si fueran rutina.
    """
    k = min(k, len(y))
    return np.full(h, float(np.median(y[-k:])), dtype=float)


def _drift_damped(y: np.ndarray, h: int, phi: float = 0.9) -> np.ndarray:
    """`drift`, pero con la pendiente apagándose.

    `drift` extrapola la misma recta durante las 52 semanas del horizonte. A
    ocho lecturas de distancia eso es una raya que puede acabar en cualquier
    parte; amortiguada, la proyección se aplana en vez de dispararse.
    """
    if len(y) < 2:
        return _naive(y, h)
    slope = (y[-1] - y[0]) / (len(y) - 1)
    damping = np.cumsum(phi ** np.arange(1, h + 1))
    return np.asarray(y[-1] + slope * damping, dtype=float)


def _theil_sen(y: np.ndarray, h: int) -> np.ndarray:
    """Tendencia robusta: la MEDIANA de las pendientes entre todos los pares.

    Sustituto de `drift`, que mira sólo el primer punto y el último: un
    traspaso justo en una de esas dos semanas inclina la proyección entera.
    Aquí una semana rara es un voto más entre muchos.
    """
    n = len(y)
    if n < 2:
        return _naive(y, h)
    t = np.arange(n, dtype=float)
    trozos = [(y[i + 1 :] - y[i]) / (t[i + 1 :] - t[i]) for i in range(n - 1)]
    slope = float(np.median(np.concatenate(trozos)))
    # Intercepto también robusto, o el ajuste se torcería en el último paso
    # por culpa del mismo dato del que se acaba de defender.
    inter = float(np.median(y - slope * t))
    return np.asarray(inter + slope * (n - 1 + np.arange(1, h + 1)), dtype=float)


def _theta(y: np.ndarray, h: int) -> np.ndarray:
    """El método Theta: nivel suavizado más media pendiente de la regresión.

    Ganó la competición M3 y sigue arriba en la M4 justo en el tramo que
    importa aquí --series cortas--. La formulación clásica combina la recta de
    regresión con la serie doblemente curvada, y equivale a esto: SES para el
    nivel, y la mitad de la pendiente lineal para el rumbo.
    """
    n = len(y)
    if n < 2:
        return _naive(y, h)
    slope = float(np.polyfit(np.arange(n, dtype=float), y, 1)[0])
    return np.asarray(_ses(y, h) + 0.5 * slope * np.arange(1, h + 1), dtype=float)


def _ar1(y: np.ndarray, h: int) -> np.ndarray:
    """Autorregresivo de orden 1: cuánto se vuelve a la media.

    Es la única forma de la lista que puede decir «esta semana fue alta, así
    que la siguiente bajará». Los suavizados no vuelven nunca: se quedan donde
    los deja la última lectura.
    """
    mu = float(np.mean(y))
    z = y - mu
    den = float(np.dot(z[:-1], z[:-1]))
    phi = float(np.dot(z[1:], z[:-1]) / den) if den > 0 else 0.0
    # Fuera del intervalo la serie explota; se recorta en vez de confiar en que
    # ocho lecturas hayan estimado bien el coeficiente.
    phi = max(-0.95, min(0.95, phi))
    salida, ultimo = [], float(z[-1])
    for _ in range(h):
        ultimo *= phi
        salida.append(mu + ultimo)
    return np.asarray(salida, dtype=float)


def _seasonal_naive(y: np.ndarray, h: int, m: int = SEASON_WEEKS) -> np.ndarray:
    """La semana w de la próxima temporada será como la semana w de ésta.

    La forma más barata de captar el ciclo de 16 semanas, y la única que entra
    con UNA temporada: `holt_winters` exige dos ciclos completos --32 lecturas,
    casi medio año más de espera--.
    """
    if len(y) < m:
        return _naive(y, h)
    base = y[len(y) - m :]
    return np.asarray([base[i % m] for i in range(h)], dtype=float)


def _seasonal_holt(y: np.ndarray, h: int, m: int = SEASON_WEEKS) -> np.ndarray:
    """Perfil estacional con ciclos INCOMPLETOS, más Holt sobre lo que queda.

    Lo mismo que `holt_winters`, salvo que no espera a tener dos temporadas
    enteras: usa las repeticiones que haya de cada posición del ciclo y encoge
    hacia cero las que se apoyan en una sola observación, que es de donde
    vendría el ruido. Con eso la estacionalidad entra sobre la lectura 20 en
    vez de la 32.
    """
    if len(y) < m + 4:
        return _holt(y, h)
    media = float(np.mean(y))
    estacional = np.zeros(m)
    for i in range(m):
        obs = y[i::m]
        if len(obs) == 0:
            continue
        # Encogimiento por conteo: con una observación el ajuste vale la mitad;
        # con cuatro, cuatro quintos. Nunca del todo.
        peso = len(obs) / (len(obs) + 1.0)
        estacional[i] = (float(np.mean(obs)) - media) * peso
    estacional -= estacional.mean()

    sin_estacion = y - np.tile(estacional, len(y) // m + 1)[: len(y)]
    base = _holt(sin_estacion, h)
    futuro = np.array([estacional[(len(y) + i) % m] for i in range(h)])
    return np.asarray(base + futuro, dtype=float)


#: Los que entran a la combinación. Simples a propósito: la mezcla existe para
#: estabilizar, y meter en ella al que más se mueve la haría moverse igual.
COMBO_BASE = ("naive", "median_k", "drift_damped", "ses", "theta")


def _combo(y: np.ndarray, h: int) -> np.ndarray:
    """La MEDIANA de lo que dicen varios modelos simples.

    Es el que más falta hacía, y no por afinar el error sino por la forma en
    que se elige al ganador. Con ocho lecturas el backtest compara entre dos y
    cinco veces según el modelo: con tan pocas comparaciones, el que gana lo
    hace medio por azar y puede cambiar de una semana a otra. Una pantalla que
    cada lunes recomienda un modelo distinto enseña menos que una quieta.

    Combinar pronósticos es de los resultados más firmes del campo: la media de
    varios modelos decentes suele batir fuera de muestra al que mejor pinta
    dentro. Aquí se usa la mediana y no la media, para que uno que se dispare
    no arrastre a los demás.

    No lleva backtest dentro --sería un backtest dentro de otro--: combina
    todos los de `COMBO_BASE` que tengan datos suficientes.
    """
    usables = [nombre for nombre in COMBO_BASE if len(y) >= MIN_POINTS[nombre]]
    if not usables:
        return _naive(y, h)
    predicciones = np.array([MODELS[nombre](y, h) for nombre in usables])
    return np.asarray(np.median(predicciones, axis=0), dtype=float)


MODELS: dict[str, Callable[[np.ndarray, int], np.ndarray]] = {
    "naive": _naive,
    "mean_k": _mean_k,
    "median_k": _median_k,
    "drift": _drift,
    "drift_damped": _drift_damped,
    "theil_sen": _theil_sen,
    "ses": _ses,
    "theta": _theta,
    "ar1": _ar1,
    "holt": _holt,
    "combo": _combo,
    "seasonal_naive": _seasonal_naive,
    "seasonal_holt": _seasonal_holt,
    "holt_winters": _holt_winters,
}

#: Cuántas lecturas necesita cada uno para que su resultado signifique algo. No
#: es lo que necesita para no reventar --casi todos caen a `naive`-- sino desde
#: dónde deja de ser un adorno.
MIN_POINTS = {
    "naive": 2,
    "mean_k": 3,
    "median_k": 3,
    "drift": 2,
    "drift_damped": 3,
    "theil_sen": 4,
    "ses": 4,
    "theta": 4,
    "ar1": 6,
    "holt": 6,
    "combo": 4,
    # Una temporada entera más una semana: ya hay un ciclo al que mirar.
    "seasonal_naive": SEASON_WEEKS + 1,
    # Un ciclo y un trozo del siguiente: suficiente para un perfil encogido.
    "seasonal_holt": SEASON_WEEKS + 4,
    "holt_winters": 2 * SEASON_WEEKS,
}


#: El nombre de cada modelo en la lengua de la pantalla.
#:
#: Vive aquí, pegado al registro, y no en el frontend: la frase que explica la
#: recomendación se arma en el servidor --como el resto de la prosa de la
#: aplicación-- y tener dos listas de nombres garantizaba que un día dijeran
#: cosas distintas. Un modelo sin nombre se enseña por su clave, que es feo
#: pero cierto (2026-09-01).
NOMBRES: dict[str, str] = {
    "naive": "última semana",
    "mean_k": "media de las últimas",
    "median_k": "mediana de las últimas",
    "drift": "tendencia recta",
    "drift_damped": "tendencia amortiguada",
    "theil_sen": "tendencia robusta (Theil-Sen)",
    "ses": "suavizado exponencial",
    "theta": "Theta",
    "ar1": "vuelta a la media (AR1)",
    "holt": "nivel y tendencia (Holt)",
    "combo": "combinación de modelos",
    "seasonal_naive": "misma semana de la temporada pasada",
    "seasonal_holt": "estacional parcial + Holt",
    "holt_winters": "estacional completo (Holt-Winters)",
}


def nombre_de(modelo: str) -> str:
    return NOMBRES.get(modelo, modelo)


# ─────────────────────────── selección ───────────────────────────


def backtest(y: np.ndarray, model: str, min_train: int = 3, horizon: int = 1) -> float:
    """Error absoluto medio con origen móvil. np.inf si no hay datos bastantes."""
    fn = MODELS[model]
    start = max(min_train, MIN_POINTS[model])
    if len(y) <= start:
        return float("inf")
    errors = []
    for t in range(start, len(y) - horizon + 1):
        pred = fn(y[:t], horizon)
        errors.append(abs(pred[horizon - 1] - y[t + horizon - 1]))
    return float(np.mean(errors)) if errors else float("inf")


def auto_forecast(
    history: Sequence[float] | np.ndarray,
    horizon: int = 52,
    season: int = SEASON_WEEKS,
) -> Forecast:
    """Proyecta eligiendo el modelo que mejor predice el histórico propio."""
    y = np.asarray(history, dtype=float)
    if len(y) == 0:
        raise ValueError("serie vacía")
    if len(y) == 1:
        return Forecast(
            "naive", [float(y[0])] * horizon, [float(y[0])] * horizon, [float(y[0])] * horizon, 0.0
        )

    usable = [m for m in MODELS if len(y) >= MIN_POINTS[m]]
    scores = {m: backtest(y, m) for m in usable}
    finite = {m: s for m, s in scores.items() if np.isfinite(s)}
    best = min(finite, key=lambda m: finite[m]) if finite else "naive"

    point = MODELS[best](y, horizon)

    # Residuos un paso adelante para el ancho de las bandas
    resid = []
    start = max(3, MIN_POINTS[best])
    for t in range(start, len(y)):
        resid.append(y[t] - MODELS[best](y[:t], 1)[0])
    if len(resid) > 1:
        sigma = float(np.std(resid, ddof=1))
    else:
        sigma = float(np.std(y, ddof=1)) if len(y) > 1 else 0.0

    # Suelo para la banda: un modelo que no falló NI UNA VEZ dentro de la
    # muestra no puede prometer certeza absoluta un año por delante.
    #
    # 2026-09-01, encontrado al añadir los modelos nuevos: con una serie que
    # alterna cada dos semanas, `seasonal_naive` la reproduce exacta --16 es
    # par-- y sigma salía CERO. La pantalla habría enseñado p10 = p50 = p90:
    # una raya sin incertidumbre, que es la mentira más cara que puede decir
    # una proyección. El riesgo creció con el catálogo, porque ahora hay
    # varios modelos capaces de clavar una serie corta.
    #
    # El suelo no se inventa: es cuánto se mueve la serie de una semana a la
    # siguiente. Si ni eso se mueve --una serie constante-- entonces cero es
    # la respuesta honesta y se queda en cero.
    if sigma == 0.0 and len(y) > 2:
        sigma = float(np.std(np.diff(y), ddof=1))

    spread = 1.2816 * sigma * np.sqrt(np.arange(1, horizon + 1))  # p10/p90
    return Forecast(
        model=best,
        point=[float(v) for v in point],
        lower=[float(v) for v in point - spread],
        upper=[float(v) for v in point + spread],
        residual_std=sigma,
        backtest_mae=finite.get(best),
        candidates={m: float(s) for m, s in finite.items()},
    )


def detect_anomalies(history: Sequence[float] | np.ndarray, z: float = 3.0) -> list[int]:
    """Índices con desviación robusta (MAD) superior a z — gastos raros, etc."""
    y = np.asarray(history, dtype=float)
    if len(y) < 5:
        return []
    med = np.median(y)
    mad = np.median(np.abs(y - med))
    if mad == 0:
        return []
    scores = 0.6745 * (y - med) / mad
    return [int(i) for i in np.where(np.abs(scores) > z)[0]]
