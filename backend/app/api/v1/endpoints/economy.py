"""Economía. HL-050 … HL-056."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.economy import EconomyQueryService
from app.domain.engines.economy_engine import PlannedEvent
from app.infrastructure.db.session import get_session

router = APIRouter()


@router.get(
    "/teams/{team_id}/economy",
    summary="Series y proyección a 52 semanas (HL-052/053/054/055)",
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
        "weeks": b.weeks, "p10": b.p10, "p50": b.p50, "p90": b.p90,
        "model": b.model, "backtestMae": b.backtest_mae, "candidates": b.candidates,
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
            {"date": p.date, "cash": p.cash, "income": p.income,
             "costs": p.costs, "balance": p.balance, "isAnomaly": p.is_anomaly}
            for p in d.series
        ],
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
    }
