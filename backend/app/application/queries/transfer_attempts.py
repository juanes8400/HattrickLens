"""Los intentos de venta, uno por fila.

2026-08-22, pedido explícitamente. Hasta ahora la aplicación sabía cuántas
veces se había listado un jugador, pero no podía enseñar CADA intento con su
final: a qué precio se pedía, si terminó en venta o el jugador se quedó, y
cuántas veces lo miraron.

Ese último dato es el único de toda la aplicación que Hattrick no entrega por
CHPP. Solo lo dice en el texto de las noticias al cerrarse la puja ("este
jugador fue visto 8 veces mientras estaba en la lista de transferibles"), así
que lo teclea el usuario y aquí se sirve tal cual, sin estimarlo jamás.
"""
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db import models as m


@dataclass
class TransferAttemptRow:
    id: int
    ht_player_id: int | None
    name: str
    #: Cuándo apareció en el mercado y cuándo cerró la puja.
    detected_at: str
    deadline: str | None
    ended_at: str | None
    #: Todavía en el mercado: su final no se sabe aún.
    open: bool
    sold: bool
    #: La última puja que Hattrick reportó. `None` si nunca hubo ninguna.
    highest_bid: int | None
    #: Precio real de la venta, solo si terminó en venta.
    sale_price: int | None
    times_seen: int | None
    #: Ya se le preguntó al usuario por las visitas, respondiera o no.
    asked: bool


@dataclass
class TransferAttemptsResponse:
    currency: str
    rows: list[TransferAttemptRow] = field(default_factory=list)
    #: Los que terminaron y siguen sin saber cuántas visitas tuvieron. Es lo
    #: que la pantalla de Cambios convierte en un aviso que se puede ignorar.
    pending_question: list[TransferAttemptRow] = field(default_factory=list)


def _iso(valor: datetime | None) -> str | None:
    return valor.isoformat() if valor is not None else None


class TransferAttemptsQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, team_id: int) -> TransferAttemptsResponse | None:
        equipo = await self._s.get(m.Team, team_id)
        if equipo is None:
            return None
        tasa = equipo.currency_rate or 1.0

        def conv(valor: int | None) -> int | None:
            return None if valor is None else int(round(valor / tasa))

        filas = (
            await self._s.execute(
                select(m.PlayerListingAttempt, m.Player, m.PlayerStint)
                .join(m.Player, m.Player.id == m.PlayerListingAttempt.player_id)
                .outerjoin(
                    m.PlayerStint, m.PlayerStint.id == m.PlayerListingAttempt.stint_id
                )
                .where(m.Player.team_id == team_id)
                .order_by(m.PlayerListingAttempt.detected_at.desc())
            )
        ).all()

        salida: list[TransferAttemptRow] = []
        for intento, jugador, etapa in filas:
            abierto = intento.ended_at is None
            salida.append(TransferAttemptRow(
                id=intento.id,
                ht_player_id=intento.ht_player_id or jugador.ht_player_id,
                name=f"{jugador.first_name} {jugador.last_name}".strip(),
                detected_at=intento.detected_at.isoformat(),
                deadline=_iso(intento.deadline),
                ended_at=_iso(intento.ended_at),
                open=abierto,
                sold=intento.sold,
                highest_bid=conv(intento.last_highest_bid or intento.highest_bid),
                sale_price=(
                    conv(etapa.sale_price) if intento.sold and etapa is not None else None
                ),
                times_seen=intento.times_seen,
                asked=intento.times_seen_asked,
            ))

        return TransferAttemptsResponse(
            currency=equipo.currency_name,
            rows=salida,
            pending_question=[
                r for r in salida
                if not r.open and r.times_seen is None and not r.asked
            ],
        )
