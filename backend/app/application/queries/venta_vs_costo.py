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

CADA PRECIO EN SU SEMANA DE HATTRICK (7.0.1, visto por el usuario el mismo
día: «unos jugadores tienen una semana de historia en un tab y varias en el
otro»). La 7.0.0 colocaba cada precio en la fecha en que se ESCRIBIÓ su fila
(`captured_at`), y una semana pasada se escribe tarde --cuando se resuelve una
venta que cerró en ella, o cuando el barrido llega a ventas viejas--, así que
semanas enteras de precio se apilaban al final. Ahora se colocan por
`season_week`, igual que la pestaña «Precio»: las dos dicen las mismas semanas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.player_balance import PlayerBalanceQueryService
from app.application.queries.weekly import season_week_for_datetime
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


def precio_de_la_semana(semanas: list[tuple[str, int | None]], semana: str | None) -> int | None:
    """El precio de la semana de Hattrick `semana` («TT-ss»), o el de la última
    semana anterior que tuvo precio. Lo que manda es la semana en que
    cerraron las ventas, no cuándo se escribió la fila."""
    if semana is None:
        return None
    previas = [p for sw, p in semanas if sw <= semana and p is not None]
    return previas[-1] if previas else None


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
    world = await session.scalar(
        select(m.WorldContext)
        .join(m.Team, m.Team.ht_league_id == m.WorldContext.ht_league_id)
        .where(m.Team.id == team_id)
    )
    # Una fila por semana de Hattrick («TT-ss», con ceros: se ordena como
    # texto). Las de antes de la 0113 no tienen semana y tampoco se dibujan en
    # la pestaña «Precio».
    semanas = [
        (f.season_week, f.mean_price)
        for f in (
            await session.execute(
                select(m.MarketEstimate)
                .where(
                    m.MarketEstimate.team_id == team_id,
                    m.MarketEstimate.ht_player_id == ht_player_id,
                    m.MarketEstimate.mean_price.is_not(None),
                    m.MarketEstimate.season_week != "",
                )
                .order_by(m.MarketEstimate.season_week)
            )
        ).scalars()
    ]
    puntos = []
    for c in costos:
        momento = _utc(c.momento)
        semana = season_week_for_datetime(world, momento) if world else None
        base = precio_de_la_semana(semanas, semana)
        precio = int(round(base / tasa)) if base is not None else None
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
