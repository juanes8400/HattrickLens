"""Economy Engine — proyección de caja a 52 semanas.

Diseño (ver docs/07). Tres capas, de más a menos determinista:

1. ESTRUCTURAL (conocido): salarios de la plantilla, staff, mantenimiento del
   estadio, patrocinio. Se calcula, no se estima. Es el ~90% del flujo.
2. ESTOCÁSTICO (modelado): taquilla, que depende de asistencia; premios que
   dependen de resultados. Se simula con Monte Carlo.
3. DISCRECIONAL (input del usuario): compras y ventas planificadas. Escenarios.

La idea clave, tomada del "Balance sin Otros" de Hattrick Control: separar el
balance estructural del ruido de transferencias. Un equipo puede parecer
rentable por vender jugadores mientras su operación pierde dinero cada semana.

Sobre series de tiempo: con pocas semanas de histórico, ajustar un modelo
autorregresivo produce ruido con aspecto de ciencia. En su lugar el histórico
se usa para corregir los RESIDUOS del modelo bottom-up (EWMA), que es donde la
serie aporta información real: captura lo que el modelo no sabe.
"""
from dataclasses import dataclass

import numpy as np

# La taquilla que reporta CHPP en un snapshot es el ingreso de ESA semana, no
# un promedio: 0 en semanas sin partido en casa, un bulto grande en las que sí
# hay. HL-052: "balance estructural" tiene que amortizarla a lo largo de la
# temporada o el resultado depende de qué semana te tocó sincronizar, no de
# la operación real del club — es el bug que motivó esta constante compartida
# (el dashboard y la pantalla de economía daban números casi opuestos).
SEASON_WEEKS = 16
HOME_MATCHES_PER_SEASON = 7


def structural_balance(
    income_sponsors: int,
    income_spectators: int,
    costs_players: int,
    costs_staff: int,
    costs_arena: int,
) -> int:
    """Balance semanal sin transferencias, con la taquilla ya amortizada.
    Única fuente de verdad: cualquier pantalla que muestre "balance
    estructural" debe llamar a esta función, no reimplementar la suma."""
    gate_per_week = (
        income_spectators * SEASON_WEEKS // HOME_MATCHES_PER_SEASON
        if income_spectators else 0
    )
    return income_sponsors + gate_per_week - costs_players - costs_staff - costs_arena


@dataclass(frozen=True)
class WeeklyStructure:
    """Componentes recurrentes conocidos, en moneda local por semana."""

    salaries: int
    staff: int
    arena_maintenance: int
    sponsors: int
    base_gate: int              # taquilla media observada/esperada
    other_fixed: int = 0

    @property
    def structural_balance(self) -> int:
        """Balance semanal sin transferencias — el número que importa."""
        return (
            self.sponsors + self.base_gate
            - self.salaries - self.staff - self.arena_maintenance - self.other_fixed
        )


@dataclass(frozen=True)
class PlannedEvent:
    """Movimiento discrecional del usuario en una semana futura."""

    week: int
    amount: int          # positivo = ingreso (venta), negativo = gasto (compra)
    label: str = ""


@dataclass
class ForecastResult:
    weeks: list[int]
    p10: list[float]
    p50: list[float]
    p90: list[float]
    structural_only: list[float]   # sin eventos discrecionales
    weeks_until_broke: int | None  # None si nunca queda en números rojos
    # Rellenados solo por forecast_from_history (ruta de series de tiempo)
    model: str = "bottom_up"
    backtest_mae: float | None = None
    candidates: dict[str, float] | None = None

    def summary(self) -> dict[str, float | int | None]:
        return {
            "finalP50": self.p50[-1],
            "finalP10": self.p10[-1],
            "finalP90": self.p90[-1],
            "weeksUntilBroke": self.weeks_until_broke,
        }


def forecast_cash(
    starting_cash: int,
    structure: WeeklyStructure,
    horizon_weeks: int = 52,
    home_matches_per_season: int = 7,
    season_weeks: int = 16,
    gate_volatility: float = 0.25,
    residual_mean: float = 0.0,
    residual_std: float = 0.0,
    planned: list[PlannedEvent] | None = None,
    n_runs: int = 5000,
    seed: int = 42,
) -> ForecastResult:
    """Proyecta la caja semana a semana con bandas de confianza.

    `residual_mean/std` se estiman del histórico real (lo observado menos lo
    predicho) y corrigen el sesgo del modelo bottom-up.
    """
    planned = planned or []
    rng = np.random.default_rng(seed)

    # Ingresos deterministas por semana
    fixed = (
        structure.sponsors
        - structure.salaries
        - structure.staff
        - structure.arena_maintenance
        - structure.other_fixed
    )

    # La taquilla solo entra las semanas con partido en casa
    home_prob = home_matches_per_season / season_weeks

    events = np.zeros(horizon_weeks + 1)
    for e in planned:
        if 1 <= e.week <= horizon_weeks:
            events[e.week] += e.amount

    cash = np.full(n_runs, float(starting_cash))
    structural = float(starting_cash)
    p10, p50, p90, struct_series, weeks = [], [], [], [], []
    broke_at: int | None = None

    for w in range(1, horizon_weeks + 1):
        plays_home = rng.random(n_runs) < home_prob
        gate = np.where(
            plays_home,
            rng.normal(structure.base_gate, structure.base_gate * gate_volatility, n_runs),
            0.0,
        )
        residual = (
            rng.normal(residual_mean, residual_std, n_runs)
            if residual_std > 0
            else residual_mean
        )
        cash += fixed + gate + residual + events[w]
        structural += structure.structural_balance

        p10.append(float(np.percentile(cash, 10)))
        p50.append(float(np.percentile(cash, 50)))
        p90.append(float(np.percentile(cash, 90)))
        struct_series.append(structural)
        weeks.append(w)

        if broke_at is None and np.percentile(cash, 50) < 0:
            broke_at = w

    return ForecastResult(weeks, p10, p50, p90, struct_series, broke_at)


def forecast_from_history(
    starting_cash: int,
    weekly_balances: list[float],
    horizon_weeks: int = 52,
    planned: list[PlannedEvent] | None = None,
) -> ForecastResult:
    """Proyección dirigida por el histórico real (series de tiempo).

    Modela la serie de balances semanales con selección automática de modelo
    (naive / drift / SES / Holt / Holt-Winters según lo que mejor prediga el
    propio histórico) y acumula la caja sumando la proyección semana a semana.

    Es el camino que sustituye al bottom-up en cuanto hay suficientes semanas
    sincronizadas: aprende la estacionalidad real del club (partidos en casa
    cada dos semanas, rondas de copa, día económico) sin que nadie la programe.
    """
    from app.domain.engines.timeseries import auto_forecast

    planned = planned or []
    f = auto_forecast(weekly_balances, horizon=horizon_weeks)

    events = np.zeros(horizon_weeks + 1)
    for e in planned:
        if 1 <= e.week <= horizon_weeks:
            events[e.week] += e.amount

    cash_p10 = cash_p50 = cash_p90 = float(starting_cash)
    p10, p50, p90, struct, weeks = [], [], [], [], []
    broke_at: int | None = None
    running_structural = float(starting_cash)

    for i in range(horizon_weeks):
        cash_p50 += f.point[i] + events[i + 1]
        cash_p10 += f.lower[i] + events[i + 1]
        cash_p90 += f.upper[i] + events[i + 1]
        running_structural += f.point[i]

        p10.append(cash_p10)
        p50.append(cash_p50)
        p90.append(cash_p90)
        struct.append(running_structural)
        weeks.append(i + 1)
        if broke_at is None and cash_p50 < 0:
            broke_at = i + 1

    result = ForecastResult(weeks, p10, p50, p90, struct, broke_at)
    result.model = f.model
    result.backtest_mae = f.backtest_mae
    result.candidates = f.candidates
    return result


def estimate_residuals(observed: list[int], predicted: list[int]) -> tuple[float, float]:
    """Media y desviación de los residuos históricos (para realimentar el modelo).

    Con menos de 3 observaciones devuelve (0, 0): no hay señal suficiente y es
    preferible no corregir a corregir con ruido.
    """
    if len(observed) < 3 or len(observed) != len(predicted):
        return 0.0, 0.0
    r = np.array(observed, float) - np.array(predicted, float)
    return float(r.mean()), float(r.std(ddof=1))
