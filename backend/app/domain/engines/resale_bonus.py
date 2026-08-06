"""Reparto del ingreso por reventa futura de origen desconocido — HL-161.

Cuando alguien revende a un jugador que ya vendiste, Hattrick te acredita
automáticamente una parte de esa venta (derechos de formación / club
anterior) — pero `economy.xml` solo reporta un bulto semanal agregado
("Ingresos por venta de jugadores"), sin decir de qué jugador vino. No hay
forma de saber el origen exacto con los datos que CHPP deja ver.

Lo que SÍ se puede hacer: cada semana, si el ingreso reportado es MAYOR que
la suma de tus propias ventas directas de esa semana (que sí conoces, vía
`transfersteam.xml`), la diferencia es "de origen desconocido" — y el
usuario pidió repartirla, proporcional al precio de venta, entre todos los
jugadores que ya vendiste hasta esa semana. Es una aproximación explícita,
no una atribución real."""
from dataclasses import dataclass
from datetime import datetime, timedelta

# Cuántos días antes del cierre económico se considera "la venta de esa
# semana" — no hay un calendario exacto de jornada económica sincronizado,
# así que se aproxima con una ventana de 7 días.
_WEEK_WINDOW_DAYS = 7


@dataclass(frozen=True)
class WeeklyIncome:
    """Una semana YA CERRADA de economy.xml — `last_income_sold_players`,
    no el agregado en curso."""
    closed_at: datetime
    income_sold_players: int
    # 2026-08-05, confirmado explícitamente por el usuario: la temporada de
    # Hattrick en la que cerró esta semana ("Temporada N", mismo criterio
    # que `season_at` en player_balance.py) — el reparto solo debe
    # considerar ventas de la MISMA temporada, nunca toda la historia.
    season: str


@dataclass(frozen=True)
class ConfirmedSale:
    ht_player_id: int
    sale_price: int
    sold_at: datetime
    season: str


def distribute_resale_bonus(
    weekly_income: list[WeeklyIncome],
    sales: list[ConfirmedSale],
) -> dict[int, float]:
    """Devuelve, por `ht_player_id`, cuánto de la reventa futura de origen
    desconocido le corresponde — 0.0 para cualquier jugador vendido que
    nunca coincidió con un ingreso "de más". Confirmado explícitamente
    2026-08-05: repartido solo entre ventas de la MISMA temporada que el
    ingreso "de más" — una reventa que Hattrick acredita esta temporada no
    puede venir de un traspaso de hace 10 temporadas."""
    shares: dict[int, float] = {s.ht_player_id: 0.0 for s in sales}
    for week in weekly_income:
        window_start = week.closed_at - timedelta(days=_WEEK_WINDOW_DAYS)
        direct_this_week = sum(
            s.sale_price for s in sales if window_start < s.sold_at <= week.closed_at
        )
        mystery = (week.income_sold_players or 0) - direct_this_week
        if mystery <= 0:
            continue
        eligible = [
            s for s in sales if s.sold_at <= week.closed_at and s.season == week.season
        ]
        total_price = sum(s.sale_price for s in eligible)
        if total_price <= 0:
            continue
        for s in eligible:
            shares[s.ht_player_id] += mystery * (s.sale_price / total_price)
    return shares
