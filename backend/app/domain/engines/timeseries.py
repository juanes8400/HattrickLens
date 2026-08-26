"""Motor de series de tiempo — puro NumPy, sin dependencias pesadas.

Escalera de modelos, de menos a más exigente en datos:

    n >= 2   naive, drift
    n >= 4   suavizado exponencial simple (SES)
    n >= 6   Holt con tendencia amortiguada
    n >= 2m  Holt-Winters aditivo estacional (m = 16 semanas = temporada HT)

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


MODELS: dict[str, Callable[[np.ndarray, int], np.ndarray]] = {
    "naive": _naive,
    "drift": _drift,
    "ses": _ses,
    "holt": _holt,
    "holt_winters": _holt_winters,
}

MIN_POINTS = {"naive": 2, "drift": 2, "ses": 4, "holt": 6, "holt_winters": 2 * SEASON_WEEKS}


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
