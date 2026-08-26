"""ArenaQueryService — HL-060, HL-061, HL-063, HL-064.

El estadio es el único activo del club que produce dinero sin salario, y el
único cuya ampliación es irreversible. Por eso lo que más importa aquí no es la
ocupación media sino la **demanda censurada**: cuando un sector se agota, la
asistencia observada deja de medir cuánta gente quería entrar y pasa a medir
cuántos asientos hay. Decidir una ampliación con esa media es decidir con un
número que, por construcción, no puede decir que te has quedado corto.

Así que el servicio separa tres cosas que suelen ir mezcladas:

- lo que se vendió (hecho),
- lo que se habría vendido (estimación, y sólo si el sector NO se agotó),
- lo que se dejó de ingresar (aritmética sobre lo anterior).

Y cuando la demanda está censurada lo dice en vez de rellenar el hueco.
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.engines.arena_engine import (
    SECTORS,
    TICKET_PRICES,
    TICKET_PRICES_VERIFIED,
    ArenaCapacity,
    Attendance,
    analyse_expansion,
    analyse_match,
    estimate_true_demand,
)
from app.domain.value_objects.ht_constants import NON_OFFICIAL_MATCH_TYPES
from app.infrastructure.db import models as m

SECTOR_LABELS = {
    "general": "General",
    "preferentes": "Preferentes",
    "tribunas": "Tribunas",
    "palcos": "Palcos",
}

# Coste de construcción por asiento y mantenimiento semanal. De la
# especificación; no verificados contra la pantalla del club todavía.
BUILD_COST_PER_SEAT = {"general": 450.0, "preferentes": 750.0, "tribunas": 1500.0, "palcos": 3000.0}
WEEKLY_MAINTENANCE_PER_SEAT = 3.5
HOME_MATCHES_PER_SEASON = 7


@dataclass
class SectorRow:
    sector: str
    label: str
    capacity: int
    sold_avg: int
    occupancy: float
    times_sold_out: int
    price: float
    price_is_verified: bool
    demand_is_censored: bool


@dataclass
class MatchRow:
    date: str
    match_type: int
    capacity: int
    sold: int
    occupancy: float
    revenue: int
    sold_out_sectors: list[str]
    empty_seats: int
    revenue_left: int


@dataclass
class ExpansionOption:
    label: str
    added_seats: dict[str, int]
    build_cost: int
    added_weekly_maintenance: int
    added_revenue_per_match: int
    net_per_season: int
    payback_seasons: float | None
    verdict: str


@dataclass
class ArenaResponse:
    team_name: str
    currency: str
    capacity_total: int
    capacity_is_real: bool
    matches_analysed: int
    avg_occupancy: float
    total_revenue: int
    # Ingreso teórico con el estadio 100% lleno menos el real. OJO: no es
    # "dinero perdido" salvo que los sectores se agoten — con 29% de ocupación
    # el límite es la demanda, no los asientos. Se conserva porque alimenta el
    # simulador de ampliación, pero NO se muestra como KPI (2026-08-15).
    revenue_left_on_table: int
    # Partidos en los que SÍ se dejó gente fuera: el único caso en que se
    # puede afirmar que hubo demanda sin atender.
    sold_out_matches: int
    sectors: list[SectorRow]
    matches: list[MatchRow]
    expansion_options: list[ExpansionOption]
    demand_is_censored: bool
    censored_sectors: list[str]
    notes: list[str] = field(default_factory=list)


class ArenaQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(
        self,
        team_id: int,
        fill_rate: float | None = None,
    ) -> ArenaResponse | None:
        team = await self._s.get(m.Team, team_id)
        if team is None:
            return None
        # Escaleras/Duelos/Torneos/Preparación se excluyen siempre (2026-08-12,
        # pedido explícito: "de TODOS los lugares de esta herramienta... ni
        # con botón, ni sin botón") — mezclarlos aquí sesga la calibración de
        # precios, la ocupación media y el retorno estimado de ampliar el estadio.
        query = (
            select(m.StadiumHistory)
            .where(m.StadiumHistory.team_id == team_id)
            .where(m.StadiumHistory.match_type.not_in(NON_OFFICIAL_MATCH_TYPES))
        )
        rows = list((await self._s.execute(query.order_by(m.StadiumHistory.played_at))).scalars())
        if not rows:
            return None

        rate = team.currency_rate or 1.0

        def conv(v: float | None) -> int:
            return int(round((v or 0) / rate))

        # La capacidad por sector es la del último partido: es la única lectura
        # que corresponde al estadio de hoy.
        last = rows[-1]
        capacity, capacity_is_real = _capacity_from(last)

        attendances = [_attendance_from(r) for r in rows]
        reports = [analyse_match(capacity, a) for a in attendances]

        matches = [
            MatchRow(
                date=r.played_at.date().isoformat(),
                match_type=r.match_type,
                capacity=capacity.total,
                sold=a.total,
                occupancy=round(rep.total_occupancy, 1),
                revenue=conv(r.revenue) if r.revenue else int(rep.revenue),
                sold_out_sectors=[SECTOR_LABELS[s] for s in rep.sold_out],
                empty_seats=max(capacity.total - a.total, 0),
                revenue_left=int(rep.revenue_left_on_table),
            )
            for r, a, rep in zip(rows, attendances, reports, strict=True)
        ]

        # Partidos donde SÍ se dejó gente fuera: el único caso en que se puede
        # afirmar que hubo demanda sin atender.
        sold_out_matches = sum(1 for mm in matches if mm.sold_out_sectors)

        sectors: list[SectorRow] = []
        censored: list[str] = []
        for s in SECTORS:
            avg, is_censored = estimate_true_demand(capacity, attendances, s)
            cap = capacity.get(s)
            times_out = sum(1 for a in attendances if cap and a.get(s) >= cap)
            if is_censored:
                censored.append(SECTOR_LABELS[s])
            sectors.append(
                SectorRow(
                    sector=s,
                    label=SECTOR_LABELS[s],
                    capacity=cap,
                    sold_avg=int(round(avg)),
                    occupancy=round(avg / cap * 100, 1) if cap else 0.0,
                    times_sold_out=times_out,
                    price=TICKET_PRICES[s],
                    price_is_verified=s in TICKET_PRICES_VERIFIED,
                    demand_is_censored=is_censored,
                )
            )

        # El fill rate por defecto es la ocupación media observada, pero SÓLO
        # es honesto usarlo cuando nada se agotó. Si hubo lleno, la ocupación
        # observada es un suelo, no una estimación, y se dice.
        observed_fill = (
            sum(r.total_occupancy for r in reports) / len(reports) / 100 if reports else 0.0
        )
        effective_fill = fill_rate if fill_rate is not None else observed_fill

        options = [
            _expansion(label, seats, effective_fill)
            for label, seats in [
                ("Ampliación pequeña (+1.000 general)", {"general": 1000}),
                (
                    "Ampliación media (+2.000 general, +500 preferentes)",
                    {"general": 2000, "preferentes": 500},
                ),
                (
                    "Ampliación grande (+4.000 general, +1.000 pref., +200 tribunas)",
                    {"general": 4000, "preferentes": 1000, "tribunas": 200},
                ),
            ]
        ]

        notes: list[str] = []
        if capacity_is_real:
            notes.append(
                "Todas las ocupaciones se calculan con el aforo de HOY, porque no hay un "
                "aforo histórico por partido. Si ampliaste el estadio, la ocupación de los "
                "partidos anteriores sale más baja de lo que fue."
            )
        if not capacity_is_real:
            notes.append(
                "No fíes las cifras por sector: falta la capacidad real de cada uno, así "
                "que el total se repartió en proporción a lo vendido. Con ese reparto la "
                "ocupación sale idéntica en todos los sectores y un lleno es indetectable."
            )
        # 2026-08-16: el aviso de demanda censurada se retiró a petición del
        # usuario. El dato sigue en `demand_is_censored` y `sold_out_matches`,
        # que es lo que consumen los KPI y las alertas — sólo se deja de
        # imprimir el párrafo.
        if not censored:
            notes.append(
                "Ningún sector se agotó, así que la ocupación observada sí mide "
                "demanda y el retorno estimado de la ampliación es directo."
            )
        if fill_rate is not None:
            notes.append(
                f"Ocupación esperada de los asientos nuevos fijada a mano: {fill_rate:.0%}."
            )

        total_revenue = sum(mm.revenue for mm in matches)
        return ArenaResponse(
            team_name=team.name,
            currency=team.currency_name or "",
            capacity_total=capacity.total,
            capacity_is_real=capacity_is_real,
            matches_analysed=len(rows),
            avg_occupancy=round(observed_fill * 100, 1),
            total_revenue=total_revenue,
            revenue_left_on_table=sum(mm.revenue_left for mm in matches),
            sold_out_matches=sold_out_matches,
            sectors=sectors,
            matches=matches,
            expansion_options=options,
            demand_is_censored=bool(censored) and capacity_is_real,
            censored_sectors=censored,
            notes=notes,
        )


def _capacity_from(r: m.StadiumHistory) -> tuple[ArenaCapacity, bool]:
    """Capacidad por sector. Devuelve también si es real o derivada.

    Cuando CHPP da el desglose se usa tal cual. Cuando no, se reparte el total
    en proporción a lo vendido — y hay que saber que ese reparto **hace
    imposible detectar un lleno**: si la capacidad se deduce de las ventas, la
    ocupación de cada sector sale idéntica y la demanda censurada se vuelve
    invisible. Por eso el segundo valor se propaga hasta la respuesta en vez de
    quedarse aquí.
    """
    real = [r.capacity_terraces, r.capacity_basic, r.capacity_roof, r.capacity_vip]
    sold = [r.sold_terraces, r.sold_basic, r.sold_roof, r.sold_vip]
    if all(v is not None and v > 0 for v in real):
        real_ints = [v for v in real if v is not None]
        caps = [max(c, s) for c, s in zip(real_ints, sold, strict=True)]
        return ArenaCapacity(*caps), True

    total = r.capacity_total or sum(sold)
    sold_sum = sum(sold) or 1
    caps = [max(int(total * v / sold_sum), v) for v in sold]
    return ArenaCapacity(*caps), False


def _attendance_from(r: m.StadiumHistory) -> Attendance:
    return Attendance(
        general=r.sold_terraces,
        preferentes=r.sold_basic,
        tribunas=r.sold_roof,
        palcos=r.sold_vip,
    )


def _expansion(label: str, seats: dict[str, int], fill: float) -> ExpansionOption:
    a = analyse_expansion(
        added_seats=seats,
        build_cost_per_seat=BUILD_COST_PER_SEAT,
        weekly_maintenance_per_seat=WEEKLY_MAINTENANCE_PER_SEAT,
        expected_fill_rate=fill,
        home_matches_per_season=HOME_MATCHES_PER_SEASON,
    )
    return ExpansionOption(
        label=label,
        added_seats=seats,
        build_cost=int(a.build_cost),
        added_weekly_maintenance=int(a.added_weekly_maintenance),
        added_revenue_per_match=int(a.added_revenue_per_match),
        net_per_season=int(a.net_per_season),
        payback_seasons=round(a.payback_weeks / 16, 2) if a.payback_weeks else None,
        verdict=a.verdict,
    )
