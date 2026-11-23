"""Qué precios cruzaron el precio de equilibrio entre dos momentos.

2026-11-21, pedido del usuario. Lo leen Cambios (desde tu visita anterior) y
Alertas (entre las dos últimas sincronizaciones). La regla vive en
`app.domain.engines.cruces_de_equilibrio`; aquí sólo se lee lo necesario.

NO PIDE NADA A HATTRICK. El precio de equilibrio de entonces se calcula con el
balance «a esa fecha» (sueldos cobrados hasta entonces, comisión del agente de
entonces); el precio, con las lecturas guardadas del precio comparable; lo
máximo pagado, con las ventas que ya se conocían; y la puja, con su historia.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.player_balance import PlayerBalanceQueryService
from app.application.queries.precio_comparable import maximos_y_pujas
from app.domain.engines import alertas_de_plantilla as ap
from app.domain.engines.cruces_de_equilibrio import Cruce, Senal, sentido_del_cruce
from app.infrastructure.db import models as m


def _utc(valor: datetime) -> datetime:
    return valor if valor.tzinfo else valor.replace(tzinfo=UTC)


async def _equilibrios(
    session: AsyncSession, team_id: int, momento: datetime
) -> dict[int, tuple[int, str]]:
    """El precio de equilibrio de cada jugador activo en `momento`, con su
    nombre. Fuera quien todavía no era del club entonces: no tenía umbral."""
    balance = await PlayerBalanceQueryService(session).get(
        team_id, a_la_fecha=momento, solo_activos=True
    )
    if balance is None:
        return {}
    salida: dict[int, tuple[int, str]] = {}
    for r in balance.players:
        if r.is_sold or r.agent_pct_if_sold_now is None or r.gastos <= 0:
            continue
        if r.purchased_at and _utc(datetime.fromisoformat(r.purchased_at)) > _utc(momento):
            continue
        equilibrio = ap.precio_de_equilibrio(
            ap.Venta(
                ht_player_id=r.ht_player_id,
                name=r.name,
                precio=None,
                gastos=float(r.gastos),
                comision_de_la_casa=r.agent_pct_if_sold_now,
                comision_de_reventa=float(r.resale_bonus_share or 0),
            )
        )
        if equilibrio is not None:
            salida[r.ht_player_id] = (equilibrio, r.name)
    return salida


async def _precios(session: AsyncSession, team_id: int, momento: datetime) -> dict[int, int]:
    """El precio por comparables de cada jugador en `momento`: su última
    lectura hasta entonces, la misma que usa el aviso del ±5 %."""
    equipo = await session.get(m.Team, team_id)
    tasa = (equipo.currency_rate or 1.0) if equipo else 1.0
    # Una consulta para todos, no una por jugador (2026-11-23): la última
    # lectura de cada uno hasta `momento`.
    ultimas = (
        select(
            m.MarketEstimate.ht_player_id.label("pid"),
            func.max(m.MarketEstimate.captured_at).label("cuando"),
        )
        .where(m.MarketEstimate.team_id == team_id, m.MarketEstimate.captured_at <= momento)
        .group_by(m.MarketEstimate.ht_player_id)
        .subquery()
    )
    filas = (
        await session.execute(
            select(m.MarketEstimate.ht_player_id, m.MarketEstimate.mean_price)
            .join(
                ultimas,
                (m.MarketEstimate.ht_player_id == ultimas.c.pid)
                & (m.MarketEstimate.captured_at == ultimas.c.cuando),
            )
            .where(m.MarketEstimate.team_id == team_id)
        )
    ).all()
    salida: dict[int, int] = {}
    for pid, precio in filas:
        if precio is not None:
            salida[int(pid)] = int(round(precio / tasa)) if tasa else int(precio)
    return salida


async def cruces_de_equilibrio(
    session: AsyncSession,
    team_id: int,
    desde: datetime,
    hasta: datetime,
) -> list[Cruce]:
    eq_antes = await _equilibrios(session, team_id, desde)
    eq_ahora = await _equilibrios(session, team_id, hasta)
    if not eq_ahora:
        return []
    precio_antes = await _precios(session, team_id, desde)
    precio_ahora = await _precios(session, team_id, hasta)
    mercado = await maximos_y_pujas(session, team_id, desde, hasta)

    cruces: list[Cruce] = []
    for pid, (equilibrio, nombre) in eq_ahora.items():
        if pid not in eq_antes:
            continue
        equilibrio_antes = eq_antes[pid][0]
        otro = mercado.get(pid)
        senales: list[tuple[Senal, int | None, int | None, bool]] = [
            ("precio", precio_antes.get(pid), precio_ahora.get(pid), False),
            (
                "maximo",
                otro.maximo_antes if otro else None,
                otro.maximo_ahora if otro else None,
                False,
            ),
            # Sin puja entonces es puja cero: estaba por debajo.
            (
                "puja",
                (otro.puja_antes or 0) if otro and otro.puja_ahora is not None else None,
                otro.puja_ahora if otro else None,
                True,
            ),
        ]
        for senal, antes, ahora, solo_subida in senales:
            sentido = sentido_del_cruce(
                antes, equilibrio_antes, ahora, equilibrio, solo_subida=solo_subida
            )
            if sentido is None or antes is None or ahora is None:
                continue
            cruces.append(
                Cruce(
                    ht_player_id=pid,
                    nombre=nombre,
                    senal=senal,
                    sentido=sentido,
                    antes=antes,
                    ahora=ahora,
                    equilibrio_antes=equilibrio_antes,
                    equilibrio_ahora=equilibrio,
                    cierra=otro.cierra if senal == "puja" and otro else None,
                )
            )
    return cruces


async def ultimas_dos_sincronizaciones(
    session: AsyncSession, team_id: int
) -> tuple[datetime, datetime] | None:
    """El final de la penúltima y de la última sincronización: la ventana de
    las alertas, que duran una sincronización."""
    filas = (
        await session.execute(
            select(m.Sync)
            .where(m.Sync.team_id == team_id, m.Sync.status.in_(("completed", "partial")))
            .order_by(m.Sync.started_at.desc())
            .limit(2)
        )
    ).scalars()
    fines = [s.finished_at or s.started_at for s in filas]
    if len(fines) < 2:
        return None
    return fines[1], fines[0]
