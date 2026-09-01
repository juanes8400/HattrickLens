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
    analyse_expansion,
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
class MatchRow:
    date: str
    #: Contra quién se jugó. El eje de la gráfica lo enseña en vez de la fecha:
    #: «Cauca CF» dice de qué partido hablamos y «16/08» no (2026-09-01).
    rival: str
    match_type: int
    capacity: int
    sold: int
    occupancy: float
    revenue: int
    empty_seats: int


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
    """El estadio con lo que Hattrick hace público, y nada más.

    Hasta el 2026-09-01 esto traía el desglose de asistencia POR SECTOR:
    cuánto se vendió en cada uno, su ocupación, cuántas veces se agotó y una
    estimación de demanda censurada. Todo eso salía de `SoldTerraces`,
    `SoldBasic`, `SoldRoof` y `SoldVIP` de matchdetails, que es una función de
    HT Supporter — y las reglas de CHPP prohíben replicarlas.

    Lo que queda es lo que cualquiera ve en la página de un partido: cuánta
    gente entró en total y cuánto se recaudó. La ocupación se calcula contra
    el aforo TOTAL, y el simulador de ampliación sigue funcionando porque sólo
    necesita los asientos que añadirías y el llenado medio, no quién se sienta
    dónde.
    """

    team_name: str
    currency: str
    capacity_total: int
    matches_analysed: int
    avg_occupancy: float
    total_revenue: int
    matches: list[MatchRow]
    expansion_options: list[ExpansionOption]
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

        # El nombre del rival de cada partido. `stadium_history` sólo guarda
        # el identificador, así que hay que ir a `matches`. Se pide en una
        # sola consulta y no una por fila.
        rivales: dict[int, str] = {}
        if rows:
            partidos = await self._s.execute(
                select(m.Match).where(m.Match.ht_match_id.in_([r.ht_match_id for r in rows]))
            )
            for partido in partidos.scalars():
                # El historial de estadio es de partidos EN CASA, así que el
                # rival es siempre el visitante. Aun así se comprueba, para que
                # una fila rara no acabe enseñando tu propio nombre.
                rivales[partido.ht_match_id] = (
                    partido.away_team_name
                    if partido.home_team_ht_id == team.ht_team_id
                    else partido.home_team_name
                )

        rate = team.currency_rate or 1.0

        def conv(v: float | None) -> int:
            return int(round((v or 0) / rate))

        # El aforo TOTAL de hoy. No hay aforo histórico por partido, así que
        # todas las ocupaciones se miden contra el mismo.
        last = rows[-1]
        capacity_total = last.capacity_total or 0

        def ocupacion(vendido: int) -> float:
            return round(vendido / capacity_total * 100, 1) if capacity_total else 0.0

        matches = [
            MatchRow(
                date=r.played_at.date().isoformat(),
                # Sin nombre guardado se cae a la fecha: es lo que había antes
                # y sigue identificando la barra.
                rival=rivales.get(r.ht_match_id) or r.played_at.date().isoformat(),
                match_type=r.match_type,
                capacity=capacity_total,
                sold=r.sold_total,
                occupancy=ocupacion(r.sold_total),
                # La recaudación es la que Hattrick reporta. Antes, si faltaba,
                # se estimaba multiplicando las entradas de cada sector por su
                # precio; sin el desglose eso ya no se puede, y tampoco se
                # inventa: un hueco se queda en hueco.
                revenue=conv(r.revenue) if r.revenue else 0,
                empty_seats=max(capacity_total - r.sold_total, 0),
            )
            for r in rows
        ]

        # El llenado medio observado, sobre totales. Sirve de valor por defecto
        # para el simulador de ampliación.
        observed_fill = sum(mm.occupancy for mm in matches) / len(matches) / 100 if matches else 0.0
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

        notes: list[str] = [
            "Todas las ocupaciones se calculan con el aforo de HOY, porque no hay un "
            "aforo histórico por partido. Si ampliaste el estadio, la ocupación de los "
            "partidos anteriores sale más baja de lo que fue.",
        ]
        # La nota de «sin recaudación» se quitó con el KPI de ingresos: la
        # taquilla por partido no llega por ningún sitio --`revenue` existe y
        # nunca se rellena-- y avisar de que falta algo que nunca hubo sólo
        # añade ruido. El campo se conserva por si algún día se recoge.
        if fill_rate is not None:
            notes.append(
                f"Ocupación esperada de los asientos nuevos fijada a mano: {fill_rate:.0%}."
            )

        total_revenue = sum(mm.revenue for mm in matches)
        return ArenaResponse(
            team_name=team.name,
            currency=team.currency_name or "",
            capacity_total=capacity_total,
            matches_analysed=len(rows),
            avg_occupancy=round(observed_fill * 100, 1),
            total_revenue=total_revenue,
            matches=matches,
            expansion_options=options,
            notes=notes,
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
