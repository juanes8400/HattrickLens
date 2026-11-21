"""«Precio de venta vs costo» de un jugador, semana a semana.

2026-11-21, pedido y definido por el usuario para el Comparador de
transferencias: dos líneas sobre el mismo eje desde la llegada del jugador.

· **Costo**: lo mismo que «Costo hasta ahora» de Plantilla actual (compra o
  ascenso, sueldos e intentos de venta), calculado a cada fecha.
· **Precio de venta**: el precio por comparables de esa semana menos la
  comisión que se habría llevado el agente entonces. Antes de la primera
  lectura de precio no hay número, y no se inventa.

Donde las dos líneas se cruzan, el precio es el precio de equilibrio.
No pide nada a Hattrick.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.player_balance import PlayerBalanceQueryService
from app.infrastructure.db import models as m


@dataclass(frozen=True, slots=True)
class PuntoDeVenta:
    fecha: str
    costo: int
    precio: int | None
    comision: float | None
    venta: int | None


@dataclass(frozen=True, slots=True)
class VentaVsCosto:
    moneda: str
    puntos: tuple[PuntoDeVenta, ...]


def _utc(valor: datetime) -> datetime:
    return valor if valor.tzinfo else valor.replace(tzinfo=UTC)


async def venta_vs_costo(
    session: AsyncSession, team_id: int, ht_player_id: int
) -> VentaVsCosto | None:
    equipo = await session.get(m.Team, team_id)
    if equipo is None:
        return None
    tasa = equipo.currency_rate or 1.0
    costos = await PlayerBalanceQueryService(session).serie_de_costo(team_id, ht_player_id)
    lecturas = [
        (_utc(f.captured_at), f.mean_price)
        for f in (
            await session.execute(
                select(m.MarketEstimate)
                .where(
                    m.MarketEstimate.team_id == team_id,
                    m.MarketEstimate.ht_player_id == ht_player_id,
                    m.MarketEstimate.mean_price.is_not(None),
                )
                .order_by(m.MarketEstimate.captured_at)
            )
        ).scalars()
    ]
    puntos = []
    for c in costos:
        momento = _utc(c.momento)
        previas = [precio for cuando, precio in lecturas if cuando <= momento]
        precio = int(round(previas[-1] / tasa)) if previas and previas[-1] is not None else None
        puntos.append(
            PuntoDeVenta(
                fecha=momento.isoformat(),
                costo=int(round(c.costo)),
                precio=precio,
                comision=c.comision,
                venta=(
                    int(round(precio * (1 - c.comision)))
                    if precio is not None and c.comision is not None
                    else None
                ),
            )
        )
    return VentaVsCosto(moneda=equipo.currency_name or "", puntos=tuple(puntos))
