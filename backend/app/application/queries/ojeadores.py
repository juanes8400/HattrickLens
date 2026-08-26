"""La cuenta de cada ojeador: lo que cuesta y lo que ha traído.

2026-08-26, pedido por el usuario. La aritmética vive en
`app/domain/engines/cuenta_del_ojeador.py`; aquí sólo se reúnen los datos.

Las cifras de dinero salen de `PlayerBalanceQueryService`, la MISMA fuente que
usa el ROI de la cantera. Es a propósito: si un canterano vale 183.600 en una
pantalla, no puede valer otra cosa en la otra.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.player_balance import PlayerBalanceQueryService
from app.domain.engines import cuenta_del_ojeador as motor
from app.infrastructure.db import models as m


@dataclass(frozen=True)
class Descubrimiento:
    """Un canterano, con lo que dejó si ya salió."""

    nombre: str
    venta_neta: int
    reventas: int
    sigue_en_el_club: bool
    ht_player_id: int | None


class OjeadoresQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, team_id: int) -> dict[str, Any]:
        ojeadores = list(
            (
                await self._s.execute(select(m.YouthScout).where(m.YouthScout.team_id == team_id))
            ).scalars()
        )
        if not ojeadores:
            return {"scouts": [], "totals": None, "weeklyCost": motor.COSTE_SEMANAL}

        # Quién trajo a quién. `scout_id = 0` es "ningún ojeador": son los
        # catorce de la hornada fundacional, que llegaron solos al abrir la
        # academia. El usuario pidió expresamente dejarlos fuera.
        informes = list(
            (
                await self._s.execute(
                    select(m.YouthScoutReport, m.YouthPlayer)
                    .join(m.YouthPlayer, m.YouthPlayer.id == m.YouthScoutReport.youth_player_id)
                    .where(m.YouthPlayer.team_id == team_id)
                )
            ).all()
        )

        # El puente academia -> primer equipo. Hattrick le da un identificador
        # NUEVO al ascender, así que se cruza por nombre: es lo único que
        # sobrevive al ascenso. Comprobado contra la cuenta real: casa en 42 de
        # 43. Quien no case sale como "sin enlazar" en vez de desaparecer.
        ex_canteranos = {
            (f.name or "").strip().casefold(): f
            for f in (
                await self._s.execute(
                    select(m.FormerYouthPlayer).where(m.FormerYouthPlayer.team_id == team_id)
                )
            ).scalars()
        }

        # El techo de cada juvenil, de su ultima foto: sin ventas todavia, es
        # lo unico que dice si un ojeador trae bueno o relleno.
        techos: dict[int, int] = {}
        for jid, *maximos in (
            await self._s.execute(
                select(
                    m.YouthSnapshot.youth_player_id,
                    m.YouthSnapshot.keeper_max,
                    m.YouthSnapshot.defending_max,
                    m.YouthSnapshot.playmaking_max,
                    m.YouthSnapshot.winger_max,
                    m.YouthSnapshot.passing_max,
                    m.YouthSnapshot.scoring_max,
                    m.YouthSnapshot.set_pieces_max,
                ).order_by(m.YouthSnapshot.captured_at)
            )
        ).all():
            conocidos = [x for x in maximos if x is not None]
            if conocidos:
                techos[jid] = max(conocidos)

        balance = await PlayerBalanceQueryService(self._s).get(team_id)
        por_jugador = {r.ht_player_id: r for r in (balance.players if balance else [])}

        descubrimientos: dict[int, list[motor.Descubrimiento]] = {}
        sin_enlazar: list[str] = []
        for informe, juvenil in informes:
            if not informe.scout_id:
                continue
            nombre = f"{juvenil.first_name} {juvenil.last_name}".strip()
            sigue = juvenil.left_at is None
            venta = reventas = 0
            if not sigue:
                ex = ex_canteranos.get(nombre.casefold())
                fila = por_jugador.get(ex.ht_player_id) if ex else None
                if fila is None:
                    sin_enlazar.append(nombre)
                else:
                    # La venta MENOS la comisión del agente, dicho así por el
                    # usuario: lo que de verdad entró, no el escaparate.
                    venta = round((fila.sale_price or 0) * (1 - (fila.agent_pct or 0.0)))
                    reventas = round(fila.resale_bonus_share)
            descubrimientos.setdefault(informe.scout_id, []).append(
                motor.Descubrimiento(
                    nombre=nombre,
                    venta_neta=venta,
                    reventas=reventas,
                    sigue_en_el_club=sigue,
                    llegada=juvenil.arrived_at,
                    techo=techos.get(juvenil.id),
                )
            )

        ahora = datetime.now(UTC).replace(tzinfo=None)
        filas = motor.cuenta(
            [
                motor.Ojeador(
                    ht_scout_id=o.ht_scout_id,
                    nombre=o.name,
                    contratado=o.hired_at,
                    se_fue=o.gone_at,
                    region=o.region_name,
                )
                for o in ojeadores
            ],
            descubrimientos,
            ahora,
        )
        t = motor.totales(filas)
        return {
            "weeklyCost": motor.COSTE_SEMANAL,
            "currency": balance.currency if balance else "",
            "scouts": [
                {
                    "htScoutId": f.ojeador.ht_scout_id,
                    "name": f.ojeador.nombre,
                    "region": f.ojeador.region,
                    "hiredAt": f.ojeador.contratado.isoformat() if f.ojeador.contratado else None,
                    "goneAt": f.ojeador.se_fue.isoformat() if f.ojeador.se_fue else None,
                    "stillHired": f.sigue_contratado,
                    "weeks": f.semanas,
                    "cost": f.coste,
                    "income": f.ingresos,
                    "balance": f.saldo,
                    "found": f.traidos,
                    "sold": f.vendidos,
                    "costPerFind": f.coste_por_canterano,
                    "daysSinceLastFind": f.dias_sin_traer(ahora),
                    "players": [
                        {
                            "name": d.nombre,
                            "net": d.venta_neta,
                            "resale": d.reventas,
                            "stillHere": d.sigue_en_el_club,
                            "arrivedAt": d.llegada.isoformat() if d.llegada else None,
                            "ceiling": d.techo,
                        }
                        for d in f.descubrimientos
                    ],
                }
                for f in filas
            ],
            "totals": {
                "cost": t.coste,
                "income": t.ingresos,
                "balance": t.saldo,
                "scouts": t.ojeadores,
                "found": t.traidos,
            },
            #: Canteranos que salieron de la academia y no se pudieron enlazar
            #: con su ficha de mayores. Se dicen en vez de callarlos: su dinero
            #: no está en la cuenta.
            "unlinked": sin_enlazar,
        }
