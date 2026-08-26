"""Economía. HL-050 … HL-056."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_team_owner
from app.application.queries.economy import EconomyQueryService
from app.domain.engines.economy_engine import PlannedEvent
from app.infrastructure.db.session import get_session

router = APIRouter()


@router.get(
    "/teams/{team_id}/economy",
    summary="Series y proyección a 52 semanas (HL-052/053/054/055)",
    dependencies=[Depends(require_team_owner)],
)
async def economy(
    team_id: int,
    horizon_weeks: int = Query(52, ge=4, le=104),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """La foto económica completa: lo observado, lo proyectado y lo hipotético.

    Se devuelven **dos** proyecciones, no una. La estructural descompone la caja
    en salarios, personal, estadio, patrocinios y taquilla y simula desde ahí,
    así que funciona con un solo snapshot. La de series de tiempo elige entre
    naive, drift, SES, Holt y Holt-Winters según cuál habría predicho mejor el
    propio histórico, y por tanto necesita histórico. `recommendedModel` dice
    cuál usar hoy y `recommendationReason` por qué, en vez de esconder la
    elección detrás de un único número.
    """
    data = await EconomyQueryService(session).get(team_id, horizon_weeks=horizon_weeks)
    if data is None:
        raise HTTPException(404, f"no economy data for team {team_id}")
    return _serialise(data)


@router.post(
    "/teams/{team_id}/economy/forecast",
    summary="Proyección con movimientos planificados (HL-053)",
    dependencies=[Depends(require_team_owner)],
)
async def economy_with_plan(
    team_id: int,
    events: list[dict[str, Any]],
    horizon_weeks: int = Query(52, ge=4, le=104),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Recalcula la proyección añadiendo compras y ventas previstas.

    Cada evento es `{"week": 6, "amount": -4500000, "label": "fichaje"}`:
    positivo entra, negativo sale. Sirve para responder «¿aguanto este fichaje?»
    antes de pujar, que es cuando la respuesta todavía vale algo.
    """
    try:
        planned = [
            PlannedEvent(
                week=int(e["week"]), amount=int(e["amount"]), label=str(e.get("label", ""))
            )
            for e in events
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(422, f"evento mal formado: {exc}") from exc

    data = await EconomyQueryService(session).get(
        team_id, horizon_weeks=horizon_weeks, planned=planned
    )
    if data is None:
        raise HTTPException(404, f"no economy data for team {team_id}")
    return _serialise(data)


def _band(b: Any) -> dict[str, Any] | None:
    if b is None:
        return None
    return {
        "weeks": b.weeks,
        "p10": b.p10,
        "p50": b.p50,
        "p90": b.p90,
        "model": b.model,
        "backtestMae": b.backtest_mae,
        "candidates": b.candidates,
        "weekLabels": b.week_labels,
    }


def _income_breakdown(b: Any) -> dict[str, Any]:
    return {
        "spectators": b.spectators,
        "sponsors": b.sponsors,
        "financial": b.financial,
        "subtotal": b.subtotal,
        "other": b.other,
        "total": b.total,
    }


def _costs_breakdown(b: Any) -> dict[str, Any]:
    return {
        "arena": b.arena,
        "players": b.players,
        "financial": b.financial,
        "staff": b.staff,
        "youth": b.youth,
        "subtotal": b.subtotal,
        "other": b.other,
        "total": b.total,
    }


def _serialise(d: Any) -> dict[str, Any]:
    return {
        "teamName": d.team_name,
        "currency": d.currency,
        "cash": d.cash,
        "expectedCash": d.expected_cash,
        "weeklyBalance": d.weekly_balance,
        "structuralBalance": d.structural_balance,
        "weeksOfHistory": d.weeks_of_history,
        "series": [
            {
                "date": p.date,
                "seasonWeek": p.season_week,
                "cash": p.cash,
                "income": p.income,
                "costs": p.costs,
                "balance": p.balance,
                "isAnomaly": p.is_anomaly,
            }
            for p in d.series
        ],
        "currentWeek": (
            {
                "date": d.current_week.date,
                "seasonWeek": d.current_week.season_week,
                "cash": d.current_week.cash,
                "income": d.current_week.income,
                "costs": d.current_week.costs,
                "balance": d.current_week.balance,
                "isAnomaly": False,
            }
            if d.current_week is not None
            else None
        ),
        "weeklyFinance": {
            "income": [
                {"code": item.code, "label": item.label, "amount": item.amount}
                for item in d.weekly_finance.income
            ],
            "costs": [
                {"code": item.code, "label": item.label, "amount": item.amount}
                for item in d.weekly_finance.costs
            ],
            "incomeTotal": d.weekly_finance.income_total,
            "costsTotal": d.weekly_finance.costs_total,
            "expectedBalance": d.weekly_finance.expected_balance,
        },
        "sankeyWindows": [
            {
                "weeks": w.weeks,
                "weeksAvailable": w.weeks_available,
                "income": [
                    {"code": item.code, "label": item.label, "amount": item.amount}
                    for item in w.income
                ],
                "costs": [
                    {"code": item.code, "label": item.label, "amount": item.amount}
                    for item in w.costs
                ],
            }
            for w in d.sankey_windows
        ],
        "balanceWindows": [
            {
                "label": window.label,
                "weeksRequested": window.weeks_requested,
                "weeksAvailable": window.weeks_available,
                "income": window.income,
                "costs": window.costs,
                "balance": window.balance,
                "balanceExclTransfers": window.balance_excl_transfers,
            }
            for window in d.balance_windows
        ],
        "structuralForecast": _band(d.structural_forecast),
        "timeseriesForecast": _band(d.timeseries_forecast),
        "recommendedModel": d.recommended_model,
        "recommendationReason": d.recommendation_reason,
        "anomalies": d.anomalies,
        "weeklyBreakdown": [
            {
                "seasonWeek": row.season_week,
                "date": row.date,
                "isCurrent": row.is_current,
                "income": _income_breakdown(row.income),
                "costs": _costs_breakdown(row.costs),
            }
            for row in d.weekly_breakdown
        ],
        "seasonBreakdownTotals": [
            {
                "season": row.season,
                "income": _income_breakdown(row.income),
                "costs": _costs_breakdown(row.costs),
            }
            for row in d.season_breakdown_totals
        ],
        "minWeeksForTimeseries": d.min_weeks_for_timeseries,
    }
