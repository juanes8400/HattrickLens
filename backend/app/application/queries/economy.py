"""EconomyQueryService — HL-052, HL-053, HL-054, HL-055.

Lee los snapshots económicos acumulados y los convierte en las tres cosas que
un manager necesita decidir: qué ha pasado, qué va a pasar, y qué pasaría si.

Todos los importes salen ya convertidos a la moneda local del club. CHPP los
entrega en la moneda base del juego y cada país tiene su tasa; la conversión
vive aquí, en el borde de lectura, para que ninguna capa de arriba tenga que
acordarse.

Dos rutas de proyección conviven a propósito:

- **bottom-up** (`economy_engine.forecast_cash`) descompone la caja en salarios,
  personal, mantenimiento, patrocinios y taquilla, y simula. Funciona desde el
  primer día, incluso con un único snapshot, porque no aprende del histórico
  sino de la estructura.
- **series de tiempo** (`timeseries.auto_forecast`) no sabe nada de fútbol:
  mira la serie de caja y elige entre naive, drift, SES, Holt y Holt-Winters el
  que mejor habría predicho el propio histórico. Necesita historia para tener
  algo que decir.

El servicio devuelve las dos y dice cuál recomienda, en vez de esconder la
elección. Con pocas semanas la estructural es la buena; cuando la serie tenga
tamaño, el backtest decidirá sola.
"""
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.weekly import latest_per_iso_week
from app.domain.engines import timeseries as ts
from app.domain.engines.economy_engine import (
    HOME_MATCHES_PER_SEASON,
    SEASON_WEEKS,
    PlannedEvent,
    WeeklyStructure,
    estimate_residuals,
    forecast_cash,
)
from app.infrastructure.db import models as m

# Con menos historia que esto, un modelo de series de tiempo está ajustando
# ruido. El backtest ni siquiera tiene particiones suficientes para puntuar.
MIN_WEEKS_FOR_TIMESERIES = 8


@dataclass
class SeriesPoint:
    date: str
    cash: int
    income: int
    costs: int
    balance: int
    is_anomaly: bool = False
    # Para el balance sin transferencias — `None` si esta semana cerrada es de
    # antes de que se guardara el desglose (sync viejo), no si de verdad no
    # hubo compraventa.
    sold_players_income: int | None = None
    bought_players_costs: int | None = None


@dataclass
class FinanceItem:
    """Una sola partida oficial de economy.xml, sin agrupación."""
    code: str
    label: str
    amount: int | None


@dataclass
class WeeklyFinance:
    income: list[FinanceItem]
    costs: list[FinanceItem]
    income_total: int
    costs_total: int
    expected_balance: int


@dataclass
class BalanceWindow:
    label: str
    weeks_requested: int
    weeks_available: int
    income: int | None
    costs: int | None
    balance: int | None
    # Ingresos − gastos sin compraventa de jugadores: lo que el club gana o
    # pierde operando, sin que una venta puntual maquille un negocio
    # deficitario. `None` si falta el desglose de alguna semana del tramo.
    balance_excl_transfers: int | None


@dataclass
class ForecastBand:
    weeks: list[int]
    p10: list[int]
    p50: list[int]
    p90: list[int]
    model: str
    backtest_mae: float | None = None
    candidates: dict[str, float] = field(default_factory=dict)


@dataclass
class SankeyWindow:
    """Flujo agregado de N semanas — la última en curso más N-1 ya cerradas.
    `weeks_available` puede ser menor que `weeks` si todavía no hay tanto
    histórico o si el sync es de antes de que se guardara el desglose de
    semanas cerradas."""
    weeks: int
    weeks_available: int
    income: list[FinanceItem]
    costs: list[FinanceItem]


@dataclass
class EconomyResponse:
    team_name: str
    currency: str
    cash: int
    expected_cash: int
    weekly_balance: int
    structural_balance: int
    series: list[SeriesPoint]
    weekly_finance: WeeklyFinance
    sankey_windows: list[SankeyWindow]
    balance_windows: list[BalanceWindow]
    structural_forecast: ForecastBand
    timeseries_forecast: ForecastBand | None
    recommended_model: str
    recommendation_reason: str
    anomalies: list[str]
    weeks_of_history: int


class EconomyQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def _snapshots(self, team_id: int) -> list[m.EconomySnapshot]:
        rows = await self._s.execute(
            select(m.EconomySnapshot)
            .where(m.EconomySnapshot.team_id == team_id)
            .order_by(m.EconomySnapshot.captured_at)
        )
        # Las series y sus modelos temporales usan un cierre por semana. La
        # tabla conserva todas las lecturas intrasemanales para auditoría.
        return latest_per_iso_week(rows.scalars(), lambda row: row.captured_at)

    async def get(
        self,
        team_id: int,
        horizon_weeks: int = 52,
        planned: list[PlannedEvent] | None = None,
    ) -> EconomyResponse | None:
        team = await self._s.get(m.Team, team_id)
        if team is None:
            return None
        snaps = await self._snapshots(team_id)
        if not snaps:
            return None

        rate = team.currency_rate or 1.0

        def conv(v: float | None) -> int:
            return int(round((v or 0) / rate))

        def conv_opt(v: float | None) -> int | None:
            return None if v is None else conv(v)

        latest = snaps[-1]

        # ── Serie observada ────────────────────────────────────────────────
        cash_series = [conv(s.cash) for s in snaps]
        anomaly_idx = set(ts.detect_anomalies(cash_series))
        series = [
            SeriesPoint(
                date=_iso(s.captured_at),
                cash=conv(s.cash),
                income=conv(s.last_income_sum),
                costs=conv(s.last_costs_sum),
                balance=conv(s.last_weeks_total),
                is_anomaly=i in anomaly_idx,
                sold_players_income=conv_opt(s.last_income_sold_players),
                bought_players_costs=conv_opt(s.last_costs_bought_players),
            )
            for i, s in enumerate(snaps)
        ]

        live_income = _finance_items(_income_items(latest), conv)
        live_costs = _finance_items(_cost_items(latest), conv)
        closed_income = [_finance_items(_last_income_items(s), conv) for s in snaps]
        closed_costs = [_finance_items(_last_cost_items(s), conv) for s in snaps]
        sankey_windows = _sankey_windows(live_income, live_costs, closed_income, closed_costs)

        # ── Estructura semanal ─────────────────────────────────────────────
        # La taquilla se reparte entre todas las semanas: sólo entra dinero los
        # días de partido en casa, y el motor ya modela esa intermitencia.
        gate_per_home_match = (
            conv(latest.income_spectators) * SEASON_WEEKS // HOME_MATCHES_PER_SEASON
            if latest.income_spectators
            else 0
        )
        structure = WeeklyStructure(
            salaries=conv(latest.costs_players),
            staff=conv(latest.costs_staff),
            arena_maintenance=conv(latest.costs_arena),
            sponsors=conv(latest.income_sponsors),
            base_gate=gate_per_home_match,
            other_fixed=conv(latest.costs_youth) + conv(latest.costs_financial),
        )

        # Sesgo del modelo medido contra el histórico real, no supuesto cero.
        observed = [conv(s.last_weeks_total) for s in snaps[1:]]
        predicted = [structure.structural_balance] * len(observed)
        res_mean, res_std = (
            estimate_residuals(observed, predicted) if len(observed) >= 2 else (0.0, 0.0)
        )

        cash_now = conv(latest.cash)
        base = forecast_cash(
            starting_cash=cash_now,
            structure=structure,
            horizon_weeks=horizon_weeks,
            residual_mean=res_mean,
            residual_std=res_std,
            planned=planned or [],
        )
        structural = ForecastBand(
            weeks=base.weeks,
            p10=[int(v) for v in base.p10],
            p50=[int(v) for v in base.p50],
            p90=[int(v) for v in base.p90],
            model="bottom_up",
        )

        # ── Ruta de series de tiempo ───────────────────────────────────────
        timeseries: ForecastBand | None = None
        if len(cash_series) >= MIN_WEEKS_FOR_TIMESERIES:
            f = ts.auto_forecast(cash_series, horizon=horizon_weeks)
            timeseries = ForecastBand(
                weeks=list(range(1, horizon_weeks + 1)),
                p10=[int(v) for v in f.lower],
                p50=[int(v) for v in f.point],
                p90=[int(v) for v in f.upper],
                model=f.model,
                backtest_mae=f.backtest_mae,
                candidates=f.candidates,
            )

        if timeseries is None:
            recommended, reason = (
                "bottom_up",
                f"Con {len(cash_series)} lecturas no hay serie suficiente para "
                f"validar un modelo temporal; hacen falta {MIN_WEEKS_FOR_TIMESERIES}. "
                "La proyección estructural no necesita histórico porque "
                "descompone la caja en sus partes conocidas.",
            )
        else:
            recommended, reason = (
                timeseries.model,
                f"El modelo «{timeseries.model}» ganó el backtest de origen "
                f"rodante sobre {len(cash_series)} lecturas "
                f"(MAE {timeseries.backtest_mae:,.0f}). Se mantiene la "
                "proyección estructural al lado para contrastar.",
            )

        anomalies = [
            f"{series[i].date}: caja de {series[i].cash:,} — desviación "
            "atípica frente al resto de la serie"
            for i in sorted(anomaly_idx)
        ]

        return EconomyResponse(
            team_name=team.name,
            currency=team.currency_name or "",
            cash=cash_now,
            expected_cash=conv(latest.expected_cash),
            weekly_balance=conv(latest.last_weeks_total),
            structural_balance=structure.structural_balance,
            series=series,
            weekly_finance=WeeklyFinance(
                income=live_income,
                costs=live_costs,
                income_total=conv(latest.income_sum),
                costs_total=conv(latest.costs_sum),
                expected_balance=conv(latest.expected_weeks_total),
            ),
            sankey_windows=sankey_windows,
            balance_windows=_balance_windows(series),
            structural_forecast=structural,
            timeseries_forecast=timeseries,
            recommended_model=recommended,
            recommendation_reason=reason,
            anomalies=anomalies,
            weeks_of_history=len(cash_series),
        )


def _sum_optional(*values: int | None) -> int | None:
    """Suma varios campos CHPP que Hattrick agrupa en una sola categoría en su
    propio informe. `None` significa que ningún campo del grupo llegó en el
    sync; si al menos uno llegó, los ausentes cuentan como cero."""
    present = [v for v in values if v is not None]
    return sum(present) if present else None


# Mismo orden y mismos nombres que el informe de finanzas semanal de Hattrick.
# "Patrocinadores" agrupa IncomeSponsors + IncomeSponsorBonuses y "Temporal"
# agrupa los campos Financial + Temporary — no son agrupaciones inventadas por
# HT Lens, son cómo Hattrick presenta estas partidas.
def _income_items(snapshot: m.EconomySnapshot) -> list[tuple[str, str, int | None]]:
    return [
        ("IncomeSpectators", "Taquillas", snapshot.income_spectators),
        (
            "IncomeSponsors", "Patrocinadores",
            _sum_optional(snapshot.income_sponsors, snapshot.income_sponsor_bonuses),
        ),
        ("IncomeSoldPlayers", "Venta de jugadores", snapshot.income_sold_players),
        (
            "IncomeSoldPlayersCommission", "Comisiones",
            snapshot.income_sold_players_commission,
        ),
        (
            "IncomeOther", "Temporal",
            _sum_optional(snapshot.income_financial, snapshot.income_temporary),
        ),
    ]


def _cost_items(snapshot: m.EconomySnapshot) -> list[tuple[str, str, int | None]]:
    return [
        ("CostsPlayers", "Sueldos", snapshot.costs_players),
        ("CostsArena", "Mantenimiento del estadio", snapshot.costs_arena),
        ("CostsArenaBuilding", "Construcción del estadio", snapshot.costs_arena_building),
        ("CostsStaff", "Empleados", snapshot.costs_staff),
        ("CostsYouth", "Gastos juveniles", snapshot.costs_youth),
        ("CostsBoughtPlayers", "Compra de jugadores", snapshot.costs_bought_players),
        (
            "CostsOther", "Otros",
            _sum_optional(snapshot.costs_financial, snapshot.costs_temporary),
        ),
    ]


# Mismas categorías que arriba, pero de la semana YA CERRADA (campos Last*).
# Sin LastIncomeSponsorBonuses — ninguna versión de economy.xml lo expone
# para la semana cerrada — así que "Patrocinadores" en semanas pasadas es
# sólo LastIncomeSponsors cuando no hay bono que sumarle.
def _last_income_items(snapshot: m.EconomySnapshot) -> list[tuple[str, str, int | None]]:
    return [
        ("IncomeSpectators", "Taquillas", snapshot.last_income_spectators),
        ("IncomeSponsors", "Patrocinadores", snapshot.last_income_sponsors),
        ("IncomeSoldPlayers", "Venta de jugadores", snapshot.last_income_sold_players),
        (
            "IncomeSoldPlayersCommission", "Comisiones",
            snapshot.last_income_sold_players_commission,
        ),
        (
            "IncomeOther", "Temporal",
            _sum_optional(snapshot.last_income_financial, snapshot.last_income_temporary),
        ),
    ]


def _last_cost_items(snapshot: m.EconomySnapshot) -> list[tuple[str, str, int | None]]:
    return [
        ("CostsPlayers", "Sueldos", snapshot.last_costs_players),
        ("CostsArena", "Mantenimiento del estadio", snapshot.last_costs_arena),
        (
            "CostsArenaBuilding", "Construcción del estadio",
            snapshot.last_costs_arena_building,
        ),
        ("CostsStaff", "Empleados", snapshot.last_costs_staff),
        ("CostsYouth", "Gastos juveniles", snapshot.last_costs_youth),
        ("CostsBoughtPlayers", "Compra de jugadores", snapshot.last_costs_bought_players),
        (
            "CostsOther", "Otros",
            _sum_optional(snapshot.last_costs_financial, snapshot.last_costs_temporary),
        ),
    ]


def _finance_items(
    items: list[tuple[str, str, int | None]], conv: Callable[[int], int]
) -> list[FinanceItem]:
    return [
        FinanceItem(code=code, label=label, amount=conv(amount) if amount is not None else None)
        for code, label, amount in items
    ]


def _merge_finance_items(*item_lists: list[FinanceItem]) -> list[FinanceItem]:
    """Suma listas de FinanceItem del mismo orden/códigos, una lista por
    semana. `None` en una categoría sólo si NINGUNA de las semanas del grupo
    tuvo dato ahí — nunca se rellena con cero lo que no se sabe."""
    base = item_lists[0]
    return [
        FinanceItem(
            code=item.code, label=item.label,
            amount=_sum_optional(*(lst[i].amount for lst in item_lists)),
        )
        for i, item in enumerate(base)
    ]


def _sankey_windows(
    live_income: list[FinanceItem], live_costs: list[FinanceItem],
    closed_income: list[list[FinanceItem]], closed_costs: list[list[FinanceItem]],
) -> list[SankeyWindow]:
    """1 semana es la semana en curso tal cual `weekly_finance`; cada ventana
    mayor le suma las N-1 semanas ya cerradas más recientes (`closed_*`, en
    orden cronológico ascendente, igual que `_balance_windows`)."""
    windows: list[SankeyWindow] = []
    for weeks in (1, 2, 4, 8, 16):
        extra = weeks - 1
        available = min(extra, len(closed_income))
        chosen_income = closed_income[-available:] if available else []
        chosen_costs = closed_costs[-available:] if available else []
        windows.append(
            SankeyWindow(
                weeks=weeks,
                weeks_available=1 + available,
                income=_merge_finance_items(live_income, *chosen_income),
                costs=_merge_finance_items(live_costs, *chosen_costs),
            )
        )
    return windows


def _balance_excl_transfers(points: list[SeriesPoint]) -> int | None:
    sold = [p.sold_players_income for p in points]
    bought = [p.bought_players_costs for p in points]
    if any(v is None for v in sold) or any(v is None for v in bought):
        return None
    income_excl = sum(p.income for p in points) - sum(v for v in sold if v is not None)
    costs_excl = sum(p.costs for p in points) - sum(v for v in bought if v is not None)
    return income_excl - costs_excl


def _balance_windows(series: list[SeriesPoint]) -> list[BalanceWindow]:
    rows: list[BalanceWindow] = []
    for weeks in (2, 4, 8, 16):
        if len(series) < weeks:
            rows.append(
                BalanceWindow(
                    label=f"Últimas {weeks} semanas",
                    weeks_requested=weeks,
                    weeks_available=len(series),
                    income=None,
                    costs=None,
                    balance=None,
                    balance_excl_transfers=None,
                )
            )
            continue
        points = series[-weeks:]
        label = (
            "Balance bisemanal (últimas 2 semanas)"
            if weeks == 2
            else f"Últimas {weeks} semanas"
        )
        rows.append(
            BalanceWindow(
                label=label,
                weeks_requested=weeks,
                weeks_available=weeks,
                income=sum(point.income for point in points),
                costs=sum(point.costs for point in points),
                balance=sum(point.balance for point in points),
                balance_excl_transfers=_balance_excl_transfers(points),
            )
        )
    return rows


def _iso(dt: datetime) -> str:
    return dt.date().isoformat()
