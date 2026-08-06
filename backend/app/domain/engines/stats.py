"""Estadística genérica compartida — no específica de rivales ni de ninguna
página en particular. Extraído de rival_scouting.py (HL-099) porque HL-15x
la reutiliza para distribuciones de la propia plantilla (KDE de TSI, $/TSI,
salario en la ficha de jugador), donde "rival" no tiene sentido.
"""
import math

# ── KDE ──────────────────────────────────────────────────────────────────────


def gaussian_kde(
    values: list[float], grid: list[float], bandwidth: float | None = None
) -> list[float]:
    """Estimación de densidad por kernel gaussiano, sin dependencias pesadas.

    Ancho de banda de Silverman si no se da uno: `0.9 * min(sd, IQR/1.34) * n^-1/5`,
    la regla estándar cuando no se conoce la forma real de la distribución.
    """
    n = len(values)
    if n == 0:
        return [0.0 for _ in grid]
    if bandwidth is None:
        bandwidth = _silverman_bandwidth(values)
    if bandwidth <= 0:
        bandwidth = 1.0
    norm = 1.0 / (n * bandwidth * math.sqrt(2 * math.pi))
    density = []
    for x in grid:
        s = sum(math.exp(-0.5 * ((x - v) / bandwidth) ** 2) for v in values)
        density.append(norm * s)
    return density


def _silverman_bandwidth(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 1.0
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    sd = math.sqrt(variance)
    sorted_v = sorted(values)
    q1 = _percentile(sorted_v, 25)
    q3 = _percentile(sorted_v, 75)
    iqr = q3 - q1
    spread = min(sd, iqr / 1.34) if iqr > 0 else sd
    if spread <= 0:
        spread = sd if sd > 0 else 1.0
    return 0.9 * spread * math.pow(n, -1 / 5)


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * (pct / 100)
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def kde_grid(values: list[float], grid_points: int = 200) -> list[float]:
    """Rejilla de evaluación con padding del 10% a cada lado — misma
    convención que ya usaba `tsi_kde_comparison`."""
    if not values:
        return [i / (grid_points - 1) for i in range(grid_points)]
    lo, hi = min(values), max(values)
    if lo == hi:
        hi = lo + 1.0
    pad = (hi - lo) * 0.1
    return [lo - pad + (hi - lo + 2 * pad) * i / (grid_points - 1) for i in range(grid_points)]


def percentile_rank(values: list[float], x: float) -> float:
    """Qué porcentaje de `values` es <= x. 0-100. Con empates, cuenta todos
    los iguales como "por debajo o igual" (percentil inclusivo estándar)."""
    if not values:
        return 0.0
    below_or_equal = sum(1 for v in values if v <= x)
    return 100.0 * below_or_equal / len(values)
