"""ArenaQueryService, HL-060, HL-061, HL-063, HL-064.

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

from app.application.queries.nombre_del_torneo import nombre_del_torneo, nombres_de_copa
from app.application.queries.weekly import season_for_datetime
from app.domain.engines.arena_engine import (
    analyse_expansion,
)
from app.domain.value_objects.ht_constants import (
    FRIENDLY_MATCH_TYPES,
    NON_OFFICIAL_MATCH_TYPES,
)
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

#: El reparto de asientos que la comunidad de Hattrick da por óptimo: 62,5 %
#: grada general, 25 % preferentes, 10 % tribunas y 2,5 % palcos. Es la
#: proporción en la que la demanda de cada sector suele llenarse a la vez, así
#: que un estadio lejos de ella deja asientos vacíos en un sector mientras
#: otro se queda corto (2026-09-13).
#: Los tres tamaños de ampliación que se evalúan, en asientos nuevos.
TAMANOS_DE_AMPLIACION: tuple[tuple[str, int], ...] = (
    ("Ampliación pequeña", 1000),
    ("Ampliación mediana", 2500),
    ("Ampliación grande", 5200),
)

REPARTO_RECOMENDADO: dict[str, float] = {
    "general": 0.625,
    "preferentes": 0.25,
    "tribunas": 0.10,
    "palcos": 0.025,
}


@dataclass
class MatchRow:
    date: str
    #: Contra quién se jugó. El eje de la gráfica lo enseña en vez de la fecha:
    #: «Cauca CF» dice de qué partido hablamos y «16/08» no (2026-09-01).
    rival: str
    match_type: int
    #: El torneo en palabras («Liga», «Copa», «Amistoso»...), para el tooltip
    #: debajo del rival (2026-09-14).
    tournament: str
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
    HT Supporter, y las reglas de CHPP prohíben replicarlas.

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
    #: Qué partidos se miran: «todos», «oficiales» o «amistosos».
    tipo: str = "todos"
    #: El aforo de HOY por sector, y el reparto que se da por óptimo.
    composition: dict[str, int] = field(default_factory=dict)
    recommended_shares: dict[str, float] = field(default_factory=dict)
    #: El selector de temporada, igual que en Partidos (2026-09-14): las que
    #: tienen algún partido en casa, la actual y la elegida (`None` = todas).
    available_seasons: list[int] = field(default_factory=list)
    current_season: int | None = None
    selected_season: int | None = None
    #: Si el aforo cambió, el día del primer partido con el aforo actual: desde
    #: ahí se cuenta todo lo de esta pantalla. `None` = nunca cambió.
    capacity_changed_on: str | None = None


class ArenaQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(
        self,
        team_id: int,
        fill_rate: float | None = None,
        tipo: str = "todos",
        season: int | None = None,
    ) -> ArenaResponse | None:
        team = await self._s.get(m.Team, team_id)
        if team is None:
            return None
        # Escaleras/Duelos/Torneos/Preparación se excluyen siempre (2026-08-12,
        # pedido explícito: "de TODOS los lugares de esta herramienta... ni
        # con botón, ni sin botón"), mezclarlos aquí sesga la calibración de
        # precios, la ocupación media y el retorno estimado de ampliar el estadio.
        query = (
            select(m.StadiumHistory)
            .where(m.StadiumHistory.team_id == team_id)
            .where(m.StadiumHistory.match_type.not_in(NON_OFFICIAL_MATCH_TYPES))
        )
        rows = list((await self._s.execute(query.order_by(m.StadiumHistory.played_at))).scalars())
        if not rows:
            return None
        # SI CAMBIÓ EL AFORO, EL CONTEO EMPIEZA DE NUEVO (2026-09-14, pedido del
        # usuario). Una ocupación medida contra el estadio de antes no dice nada
        # del de ahora: con más asientos, el mismo público llena menos. Cuenta
        # sólo desde el primer partido jugado con el aforo actual.
        aforo_cambio_en = None
        aforo_anterior = None
        for r in rows:
            aforo = r.capacity_total or 0
            if not aforo:
                continue
            if aforo_anterior is not None and aforo != aforo_anterior:
                aforo_cambio_en = r.played_at
            aforo_anterior = aforo
        if aforo_cambio_en is not None:
            rows = [r for r in rows if r.played_at >= aforo_cambio_en]
        # Oficiales o amistosos (2026-09-13, pedido del usuario): un amistoso
        # llena el estadio de otra manera y mezclarlos esconde la ocupación de
        # los partidos que cuentan. El aforo sale siempre de la última lectura.
        todas = rows
        if tipo == "oficiales":
            rows = [r for r in todas if r.match_type not in FRIENDLY_MATCH_TYPES]
        elif tipo == "amistosos":
            rows = [r for r in todas if r.match_type in FRIENDLY_MATCH_TYPES]

        # POR TEMPORADA, IGUAL QUE EN PARTIDOS (2026-09-14, pedido del usuario):
        # la misma regla para saber de qué temporada es cada partido, y la
        # lista de temporadas sale de todos los partidos en casa --no de los
        # del filtro de tipo--, para que el selector no cambie al tocarlo.
        world = (
            await self._s.scalar(
                select(m.WorldContext).where(m.WorldContext.ht_league_id == team.ht_league_id)
            )
            if team.ht_league_id is not None
            else None
        )
        temporada_de = {r.id: season_for_datetime(world, r.played_at) for r in todas}
        available_seasons = sorted(
            {s for s in temporada_de.values() if s is not None}, reverse=True
        )
        if season is not None:
            rows = [r for r in rows if temporada_de.get(r.id) == season]

        # El nombre del rival de cada partido. `stadium_history` sólo guarda
        # el identificador, así que hay que ir a `matches`. Se pide en una
        # sola consulta y no una por fila.
        rivales: dict[int, str] = {}
        #: La copa de cada partido de copa por su nivel e índice: «Copa
        #: Colombia», «Copa Cocuy Rubí»... y no sólo «Copa» (2026-09-14).
        copa_de: dict[int, tuple[int | None, int | None]] = {}
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
                copa_de[partido.ht_match_id] = (partido.cup_level, partido.cup_level_index)

        nombres = await nombres_de_copa(self._s, team) if copa_de else {}

        def torneo(r: m.StadiumHistory) -> str:
            nivel, indice = copa_de.get(r.ht_match_id, (None, None))
            return nombre_del_torneo(r.match_type, nivel, indice, nombres)

        rate = team.currency_rate or 1.0

        def conv(v: float | None) -> int:
            return int(round((v or 0) / rate))

        # El aforo TOTAL de hoy. No hay aforo histórico por partido, así que
        # todas las ocupaciones se miden contra el mismo.
        last = todas[-1]
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
                tournament=torneo(r),
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

        composicion = {
            "general": last.capacity_terraces or 0,
            "preferentes": last.capacity_basic or 0,
            "tribunas": last.capacity_roof or 0,
            "palcos": last.capacity_vip or 0,
        }
        # TODAS HACIA EL REPARTO RECOMENDADO (2026-09-13, pedido del usuario).
        # Antes eran tres repartos fijos escritos a ojo --casi todo general-- y
        # una cuarta aparte que sí seguía el reparto. Ahora cada tamaño reparte
        # sus asientos entre los cuatro sectores en la proporción recomendada.
        options = []
        for nombre, asientos in TAMANOS_DE_AMPLIACION:
            reparto = _hacia_el_reparto(composicion, asientos)
            options.append(
                _expansion(f"{nombre} ({_describir_reparto(reparto)})", reparto, effective_fill)
            )

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
            tipo=tipo,
            composition=composicion,
            recommended_shares=dict(REPARTO_RECOMENDADO),
            available_seasons=available_seasons,
            current_season=world.season if world is not None else None,
            selected_season=season,
            capacity_changed_on=(
                aforo_cambio_en.date().isoformat() if aforo_cambio_en is not None else None
            ),
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


def _describir_reparto(reparto: dict[str, int]) -> str:
    """«+1.000: 800 general, 200 tribunas», en el orden de los sectores."""

    def miles(n: int) -> str:
        return f"{n:,}".replace(",", ".")

    total = sum(reparto.values())
    partes = [
        f"{miles(reparto[s])} {SECTOR_LABELS[s].lower()}" for s in SECTOR_LABELS if reparto.get(s)
    ]
    return f"+{miles(total)}: {', '.join(partes)}"


def _hacia_el_reparto(actual: dict[str, int], nuevos: int) -> dict[str, int]:
    """Cómo repartir `nuevos` asientos según `REPARTO_RECOMENDADO`.

    Los cuatro sectores reciben su parte recomendada de los asientos nuevos,
    y la suma cuadra exacta con el tamaño de la ampliación.
    """
    # LOS CUATRO SECTORES, SIEMPRE EN LA PROPORCIÓN RECOMENDADA (2026-09-13,
    # decisión del usuario). Antes se repartía sólo entre los sectores por
    # debajo de su parte, y un estadio con tribunas de sobra no recibía
    # ninguna: la ampliación salía con tres sectores y parecía un fallo.
    # `actual` se conserva en la firma: lo usa quien compara el reparto.
    del actual
    pesos = dict(REPARTO_RECOMENDADO)
    suma = sum(pesos.values())
    # Mayor resto: redondear cada sector por separado podía sumar 2.501
    # asientos para una ampliación de 2.500. Se reparte la parte entera y los
    # asientos que falten van a los sectores con mayor resto.
    exactos = {s: nuevos * peso / suma for s, peso in pesos.items()}
    reparto = {s: int(v) for s, v in exactos.items()}
    sobrantes = nuevos - sum(reparto.values())
    for s in sorted(exactos, key=lambda k: exactos[k] - reparto[k], reverse=True)[:sobrantes]:
        reparto[s] += 1
    return {s: n for s, n in reparto.items() if n > 0}
