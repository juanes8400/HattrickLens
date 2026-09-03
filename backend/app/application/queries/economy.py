"""EconomyQueryService — HL-052, HL-053, HL-054, HL-055.

Lee los snapshots económicos acumulados y los convierte en las tres cosas que
un manager necesita decidir: qué ha pasado, qué va a pasar, y qué pasaría si.

Todos los importes salen ya convertidos a la moneda local del club. CHPP los
entrega en la moneda base del juego y cada país tiene su tasa; la conversión
vive aquí, en el borde de lectura, para que ninguna capa de arriba tenga que
acordarse.

Dos rutas de proyección conviven a propósito:

- **bottom-up** (`economy_engine.forecast_cash`) descompone la caja en salarios,
  personal, mantenimiento, patrocinios y taquilla, y simula. Funciona desde el
  primer día, incluso con un único snapshot, porque no aprende del histórico
  sino de la estructura.
- **series de tiempo** (`timeseries.auto_forecast`) no sabe nada de fútbol:
  mira la serie de caja y elige entre naive, drift, SES, Holt y Holt-Winters el
  que mejor habría predicho el propio histórico. Necesita historia para tener
  algo que decir.

El servicio devuelve las dos y dice cuál recomienda, en vez de esconder la
elección. Con pocas semanas la estructural es la buena; cuando la serie tenga
tamaño, el backtest decidirá sola.
"""

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.weekly import (
    season_for_datetime,
    season_week_for_datetime,
    season_week_label,
)
from app.domain.engines import timeseries as ts
from app.domain.engines.economy_engine import (
    HOME_MATCHES_PER_SEASON,
    SEASON_WEEKS,
    PlannedEvent,
    WeeklyStructure,
    estimate_residuals,
    forecast_cash,
    foreign_surcharge,
    is_foreign,
    total_sponsor_income,
)
from app.domain.value_objects.formatting import thousands
from app.infrastructure.db import models as m

# Con menos historia que esto, un modelo de series de tiempo está ajustando
# ruido. El backtest ni siquiera tiene particiones suficientes para puntuar.
MIN_WEEKS_FOR_TIMESERIES = 8


@dataclass
class SeriesPoint:
    date: str
    # "TT-ss" (temporada-semana, p. ej. "83-03") — `None` si el equipo
    # todavía no sincronizó worlddetails.xml (ver weekly.season_week_label).
    season_week: str | None
    cash: int
    income: int
    costs: int
    balance: int
    is_anomaly: bool = False
    # Para el balance sin transferencias — `None` si esta semana cerrada es de
    # antes de que se guardara el desglose (sync viejo), no si de verdad no
    # hubo compraventa.
    sold_players_income: int | None = None
    bought_players_costs: int | None = None


@dataclass
class FinanceItem:
    """Una sola partida oficial de economy.xml, sin agrupación."""

    code: str
    label: str
    amount: int | None


@dataclass
class WeeklyFinance:
    income: list[FinanceItem]
    costs: list[FinanceItem]
    income_total: int
    costs_total: int
    expected_balance: int


@dataclass
class BalanceWindow:
    label: str
    weeks_requested: int
    weeks_available: int
    income: int | None
    costs: int | None
    balance: int | None
    # Ingresos − gastos sin compraventa de jugadores: lo que el club gana o
    # pierde operando, sin que una venta puntual maquille un negocio
    # deficitario. `None` si falta el desglose de alguna semana del tramo.
    # `None` cuando alguna semana del tramo se leyó antes de que guardáramos el
    # desglose de compraventa. No se avisa en pantalla: no hay nada que el
    # usuario pueda hacer al respecto y el hueco se cierra solo en cuanto esa
    # semana sale de la ventana.
    balance_excl_transfers: int | None


@dataclass
class ForecastBand:
    weeks: list[int]
    p10: list[int]
    p50: list[int]
    p90: list[int]
    model: str
    backtest_mae: float | None = None
    candidates: dict[str, float] = field(default_factory=dict)
    # "TT-ss" por cada entrada de `weeks` (futuro, ver weekly.season_week_label)
    # — misma longitud que `weeks`, `None` en cada una si no hay WorldContext.
    week_labels: list[str | None] = field(default_factory=list)


@dataclass
class SankeyWindow:
    """Flujo agregado de N semanas — la última en curso más N-1 ya cerradas.
    `weeks_available` puede ser menor que `weeks` si todavía no hay tanto
    histórico o si el sync es de antes de que se guardara el desglose de
    semanas cerradas."""

    weeks: int
    weeks_available: int
    income: list[FinanceItem]
    costs: list[FinanceItem]


# ── Detalles (2026-08-09, pedido explícito: "la quiero como la imagen" —
# referencia visual de la pantalla Detalles de Hattrick Control). SubTotal /
# Otros calca el criterio de HC: SubTotal es lo recurrente/estructural de
# cada semana, Otros es lo ligado a compraventa de jugadores o a algo
# puntual. CHPP no expone un campo de "Intereses" separado como HC — el más
# parecido es CostsFinancial, que aquí se muestra aparte (no se inventa un
# número, es un campo real ya sincronizado, solo desagrupado de "Otros"
# donde vivía en el resto de la app).
#
# Todos los campos son `int | None`, no `int` — un sync viejo (el primero
# que hizo este club, verificado en vivo 2026-08-09) puede no traer el
# desglose de la semana cerrada en absoluto. `None` es "no lo sabemos",
# nunca se pisa con 0 — mismo criterio que `_sum_optional` ya usa en el
# resto de este fichero.
@dataclass
class IncomeBreakdown:
    spectators: int | None  # Aficionados
    sponsors: int | None  # Patrocinados (incl. bono si aplica — solo semana en curso)
    financial: int | None  # Financieros
    subtotal: int | None
    other: int | None  # Venta de jugadores + comisión + temporal
    total: int | None


@dataclass
class CostsBreakdown:
    arena: int | None  # Estadio (mantenimiento)
    players: int | None  # Jugadores (sueldos)
    financial: int | None  # Financieros (lo más parecido a "Intereses" de HC)
    staff: int | None  # Empleados
    youth: int | None  # Canteranos
    subtotal: int | None
    other: int | None  # Compra de jugadores + construcción de estadio + temporal
    total: int | None


@dataclass
class WeeklyBreakdownRow:
    season_week: str | None
    date: str
    # La semana en curso todavía no cerró — Hattrick puede seguir sumando
    # ingresos/gastos ahí hasta el cierre real.
    is_current: bool
    income: IncomeBreakdown
    costs: CostsBreakdown


@dataclass
class SeasonBreakdownTotals:
    season: int
    income: IncomeBreakdown
    costs: CostsBreakdown


@dataclass
class WageBill:
    """La nomina semanal de la plantilla, y cuanto de ella es recargo.

    Hattrick cobra un 20% mas de sueldo por cada jugador cuyo pais de origen
    no es el del equipo. El sueldo que llega ya lo lleva dentro, asi que el
    recargo no se suma: se despeja. Si el sueldo pagado es 1,2 veces el de
    base, el recargo es una sexta parte de lo que se paga.
    """

    total: int
    players: int
    foreign_players: int
    foreign_salary: int
    surcharge: int
    #: Pais del equipo, para poder decir respecto a que son extranjeros.
    country: str
    #: Jugadores sin pais conocido, que no cuentan en ninguno de los dos lados.
    unknown_country: int


@dataclass
class RecurringWeek:
    """Lo recurrente de una semana, ya en moneda local.

    Es la misma descomposicion con la que proyecta el modelo estructural. Se
    expone porque los indicadores que comparan un gasto con un ingreso
    necesitan el ritmo recurrente, no la semana en curso: una semana con una
    venta grande haria parecer barata una nomina que no cambio.
    """

    salaries: int
    staff: int
    arena_maintenance: int
    sponsors: int
    base_gate: int
    #: La taquilla ya repartida entre todas las semanas, que es la que suma
    #: el balance recurrente. `base_gate` es la de un día de partido.
    weekly_gate: int
    other_fixed: int


@dataclass
class EconomyResponse:
    team_name: str
    currency: str
    cash: int
    expected_cash: int
    weekly_balance: int
    structural_balance: int
    series: list[SeriesPoint]
    # La semana EN CURSO, con lo que lleva acumulado hasta ahora. Va aparte de
    # `series` a propósito: `series` son semanas cerradas y alimenta los
    # balances acumulados, la detección de anomalías y el modelo temporal, que
    # se corromperían con una semana a medio terminar. El gráfico sí la pinta,
    # porque sin ella la semana de hoy no existía en ninguna parte: el
    # histórico acababa en la anterior y la proyección empezaba en la
    # siguiente.
    current_week: SeriesPoint | None
    weekly_finance: WeeklyFinance
    sankey_windows: list[SankeyWindow]
    balance_windows: list[BalanceWindow]
    structural_forecast: ForecastBand
    timeseries_forecast: ForecastBand | None
    recommended_model: str
    #: El mismo modelo, ya en la lengua de la pantalla. Viaja resuelto desde
    #: aquí para que no haya una segunda lista de nombres en el frontend.
    recommended_model_label: str
    recommendation_reason: str
    anomalies: list[str]
    weeks_of_history: int
    # Detalles: más reciente primero (al revés que `series`, que va
    # ascendente porque alimenta gráficos).
    weekly_breakdown: list[WeeklyBreakdownRow]
    season_breakdown_totals: list[SeasonBreakdownTotals]
    # Umbral real usado para decidir si hay serie de tiempo — expuesto para
    # que el teaser de Proyección muestre progreso real, no un número
    # copiado a mano que puede desincronizarse.
    min_weeks_for_timeseries: int
    #: Nomina de la plantilla de HOY. Sale de los jugadores, no de los
    #: cierres economicos: el cierre da el total pagado, pero no quien lo
    #: cobra ni de donde es, que es justo lo que hace falta para el recargo.
    wage_bill: WageBill | None
    weekly_structure: RecurringWeek


# Los totales de la semana ya cerrada. Solo los TOTALES, no el desglose: un
# campo de detalle puede aparecer o corregirse entre dos syncs sin que haya
# pasado ninguna semana, y eso partiría una semana en dos puntos.
_CLOSED_WEEK_FIELDS: tuple[str, ...] = (
    "last_income_sum",
    "last_costs_sum",
    "last_weeks_total",
)


@dataclass(frozen=True)
class _WeeklyClose:
    """Un cierre económico REAL de Hattrick.

    `snapshot` es la primera lectura que ya trae los números nuevos: su `cash`
    es la caja con la que se cerró y sus `last_*` son los flujos de esa misma
    semana. `closed_at` es la última lectura que aún traía los viejos, o sea un
    instante DENTRO de la semana que se estaba cerrando: de ahí sale la
    etiqueta TT-ss.
    """

    closed_at: datetime
    snapshot: m.EconomySnapshot


def estructura_semanal(cierres: list[m.EconomySnapshot], rate: float) -> WeeklyStructure | None:
    """Los componentes recurrentes del club, por semana y en moneda local.

    ES LA UNICA FORMA DE CALCULAR EL «BALANCE SIN TRANSFERENCIAS». Hasta el
    2026-08-30 habia tres:

      * aqui, promediando las dos ultimas semanas CERRADAS e incluyendo los
        gastos juveniles y financieros;
      * en el Panel y en la alerta de deficit, leyendo la semana EN CURSO y
        sin juveniles ni financieros.

    Las dos ultimas daban -414.969 donde esta daba -435.347, y la razon de
    fondo es peor que la diferencia: la semana en curso reporta taquilla 0
    hasta que se juega el partido en casa, asi que el numero se hundia y se
    recuperaba solo segun el dia, y de paso se comia los 20.000 semanales de
    la academia --que la pantalla de Club anuncia como «Inversion juvenil»--.
    Ese numero alimenta la alerta que le dice al usuario cuantas semanas de
    caja le quedan.

    La taquilla se reparte entre todas las semanas: solo entra dinero los dias
    de partido en casa, y el motor ya modela esa intermitencia.

    2026-08-09, pedido explicito del usuario: la base no sale de UNA sola
    semana --una con un gasto puntual o sin partido en casa distorsionaba sola
    toda la proyeccion--. Se promedian las dos ultimas cerradas disponibles
    (cae a 1 sola si todavia no hay dos) para los 6 componentes por igual,
    incluida la taquilla: mas estable, sin inventar un dato donde no lo hay.

    Devuelve `None` cuando no hay ni un cierre guardado, que es lo unico
    honesto: un 0 diria que el club no ingresa ni gasta nada.
    """
    recent = cierres[-2:]
    if not recent:
        return None

    def conv(v: float | None) -> int:
        return int(round((v or 0) / rate))

    def avg(field: str) -> float:
        return sum(getattr(s, field) or 0 for s in recent) / len(recent)

    avg_sponsors_total = sum(
        total_sponsor_income(s.income_sponsors, s.income_sponsor_bonuses) for s in recent
    ) / len(recent)
    # La taquilla se lee de `last_income_spectators`, NO de
    # `income_spectators`. Un cierre es la primera lectura que ya trae los
    # números nuevos, así que su `income_spectators` es lo que lleva
    # recaudado la semana que ACABA DE EMPEZAR: cero, salvo que el partido en
    # casa caiga el mismo día. Con las dos últimas semanas cerradas la
    # taquilla salía 0 casi siempre, y el balance recurrente de Pulgas
    # Arrechas decía -435.347 cuando la taquilla real promedia 380.240 a la
    # semana (2026-09-02).
    #
    # Y se promedia sobre TODAS las semanas cerradas, no sobre las dos
    # últimas como el resto: los sueldos o el mantenimiento son planos y dos
    # semanas bastan, pero la taquilla es intermitente por definición y con
    # una ventana de dos alterna entre el doble y cero según el calendario.
    taquillas = [s.last_income_spectators for s in cierres if s.last_income_spectators is not None]
    gate_per_week = conv(sum(taquillas) / len(taquillas)) if taquillas else 0
    return WeeklyStructure(
        salaries=conv(avg("costs_players")),
        staff=conv(avg("costs_staff")),
        arena_maintenance=conv(avg("costs_arena")),
        sponsors=conv(avg_sponsors_total),
        # Lo que se recauda en UN partido en casa, que es lo que sortea la
        # simulación. Reparte lo mismo: por 16/7 aquí, por 7/16 al sortear.
        base_gate=gate_per_week * SEASON_WEEKS // HOME_MATCHES_PER_SEASON,
        other_fixed=conv(avg("costs_youth")) + conv(avg("costs_financial")),
        weekly_gate=gate_per_week,
    )


def weekly_closes(rows: list[m.EconomySnapshot]) -> list[_WeeklyClose]:
    """Los cierres semanales que de verdad ocurrieron.

    Antes esto era `latest_per_iso_week`: la última lectura de cada semana del
    calendario. Dos fallos, los dos reportados por el usuario el 2026-08-19:

    1. La semana EN CURSO entraba como si hubiera cerrado. Su última lectura
       trae todavía la caja con la que empezó — la misma con la que cerró la
       anterior — así que el gráfico pintaba dos semanas seguidas con la misma
       cifra (83-03 y 83-04 en 9.017.240) y una proyección que arrancaba plana.
    2. Una semana sin sincronizar no dejaba punto, y una con dos lecturas a
       ambos lados del cierre dejaba la equivocada.

    El cierre se detecta por los campos `last_*`, que solo se mueven cuando
    Hattrick pasa la semana. La caja NO sirve de señal: cambia también al
    fichar o vender a media semana.
    """

    def flujos(row: m.EconomySnapshot) -> tuple[Any, ...]:
        return tuple(getattr(row, campo) for campo in _CLOSED_WEEK_FIELDS)

    salida: list[_WeeklyClose] = []
    anterior: m.EconomySnapshot | None = None
    for fila in rows:
        if anterior is not None and flujos(fila) == flujos(anterior):
            # La misma foto otra vez: varias lecturas de la misma semana.
            anterior = fila
            continue
        salida.append(
            _WeeklyClose(
                # La semana que se estaba cerrando es la de la lectura anterior.
                # Para la primera de todas no hay anterior, y lo más que se puede
                # afirmar es que sus `last_*` describen la semana previa a la
                # lectura: siete días atrás, que era el criterio de toda la serie
                # hasta este arreglo.
                closed_at=(
                    anterior.captured_at
                    if anterior is not None
                    else fila.captured_at - timedelta(days=7)
                ),
                snapshot=fila,
            )
        )
        anterior = fila
    return salida


class EconomyQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def _wage_bill(self, team: m.Team, rate: float) -> WageBill | None:
        """Nomina de la plantilla actual, separando el recargo por extranjeros.

        Un jugador es extranjero cuando su pais de origen no es el del pais en
        el que juega el equipo, que es lo que decide el recargo: no importa de
        donde lo compraste ni cuanto lleva contigo. El pais del equipo se saca
        de su liga, no del nombre de la liga, que es texto y cambia de idioma.

        Devuelve `None` cuando no se sabe de donde es NINGUN jugador: sin eso
        el indicador diria "0 extranjeros" a un equipo entero de extranjeros,
        que es peor que no decir nada.
        """
        pais_equipo = await self._s.scalar(
            select(m.WorldContext).where(m.WorldContext.ht_league_id == team.ht_league_id)
        )
        ultima = (
            select(
                m.PlayerSnapshot.player_id.label("pid"),
                func.max(m.PlayerSnapshot.captured_at).label("mx"),
            )
            .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
            .where(m.Player.team_id == team.id, m.Player.left_team_at.is_(None))
            .group_by(m.PlayerSnapshot.player_id)
            .subquery()
        )
        filas = await self._s.execute(
            select(m.PlayerSnapshot.salary, m.PlayerSnapshot.country_id).join(
                ultima,
                (m.PlayerSnapshot.player_id == ultima.c.pid)
                & (m.PlayerSnapshot.captured_at == ultima.c.mx),
            )
        )
        propio = pais_equipo.country_id if pais_equipo else 0
        total = extranjeros = sueldo_extranjero = desconocidos = 0
        jugadores = 0
        for salario, country_id in filas:
            jugadores += 1
            total += salario or 0
            if not country_id:
                desconocidos += 1
            elif is_foreign(country_id, propio):
                extranjeros += 1
                sueldo_extranjero += salario or 0
        if jugadores == 0 or desconocidos == jugadores or not propio:
            return None

        def conv(v: int) -> int:
            return int(round(v / rate))

        return WageBill(
            total=conv(total),
            players=jugadores,
            foreign_players=extranjeros,
            foreign_salary=conv(sueldo_extranjero),
            surcharge=foreign_surcharge(conv(sueldo_extranjero)),
            country=pais_equipo.country_name if pais_equipo else "",
            unknown_country=desconocidos,
        )

    async def _raw_snapshots(self, team_id: int) -> list[m.EconomySnapshot]:
        rows = await self._s.execute(
            select(m.EconomySnapshot)
            .where(m.EconomySnapshot.team_id == team_id)
            .order_by(m.EconomySnapshot.captured_at)
        )
        return list(rows.scalars())

    async def get(
        self,
        team_id: int,
        horizon_weeks: int = 52,
        planned: list[PlannedEvent] | None = None,
    ) -> EconomyResponse | None:
        team = await self._s.get(m.Team, team_id)
        if team is None:
            return None
        raw = await self._raw_snapshots(team_id)
        if not raw:
            return None
        # La lectura más nueva de todas: de ella salen los campos VIVOS (caja
        # de ahora, lo que lleva acumulado la semana en curso). No sirve para
        # la serie — la semana en curso todavía no ha cerrado.
        latest = raw[-1]
        closes = weekly_closes(raw)
        if not closes:
            return None
        snaps = [c.snapshot for c in closes]

        rate = team.currency_rate or 1.0

        def conv(v: float | None) -> int:
            return int(round((v or 0) / rate))

        def conv_opt(v: float | None) -> int | None:
            return None if v is None else conv(v)

        # "TT-ss" en cada punto/proyección — mismo filtro por `ht_league_id`
        # que `season_at()` en player_balance.py (bug real corregido
        # 2026-08-09: "la fila de WorldContext más reciente" daba cualquier
        # país al azar en cuanto había más de uno).
        world = (
            await self._s.scalar(
                select(m.WorldContext).where(m.WorldContext.ht_league_id == team.ht_league_id)
            )
            if team.ht_league_id is not None
            else None
        )

        # ── Serie observada ────────────────────────────────────────────────
        cash_series = [conv(s.cash) for s in snaps]
        anomaly_idx = set(ts.detect_anomalies(cash_series))
        # Cada punto es un CIERRE real (ver `weekly_closes`), fechado en la
        # semana que estaba corriendo cuando Hattrick movió la caja. Hasta
        # 2026-08-19 esto se resolvía restando siete días a la fecha de
        # captura, y con eso el histórico entero se corría una semana:
        # 9.017.240, que es el cierre de 83-04, aparecía como 83-03.
        series = [
            SeriesPoint(
                date=_iso(c.closed_at),
                season_week=season_week_for_datetime(world, c.closed_at),
                cash=conv(s.cash),
                income=conv(s.last_income_sum),
                costs=conv(s.last_costs_sum),
                balance=conv(s.last_weeks_total),
                is_anomaly=i in anomaly_idx,
                sold_players_income=conv_opt(s.last_income_sold_players),
                bought_players_costs=conv_opt(s.last_costs_bought_players),
            )
            for i, (c, s) in enumerate((c, c.snapshot) for c in closes)
        ]

        live_income_total = conv(latest.income_sum)
        live_costs_total = conv(latest.costs_sum)
        current_week = SeriesPoint(
            date=_iso(latest.captured_at),
            season_week=season_week_for_datetime(world, latest.captured_at),
            # `expected_cash`, no la caja cruda: cada punto de la serie es la
            # caja AL CIERRE de su semana (la lectura de una semana cerrada se
            # tomó ya cerrada), así que la semana en curso tiene que decir con
            # cuánto va a cerrar. 2026-08-16, razonado por el usuario: si hoy
            # tienes 9.017.240 y la semana va -1.136.597, el punto siguiente es
            # 7.880.644 — dibujar la caja cruda rompía esa aritmética a la
            # vista.
            cash=conv(latest.expected_cash),
            income=live_income_total,
            costs=live_costs_total,
            balance=live_income_total - live_costs_total,
            sold_players_income=conv_opt(latest.income_sold_players),
            bought_players_costs=conv_opt(latest.costs_bought_players),
        )

        live_income = _finance_items(_income_items(latest), conv)
        live_costs = _finance_items(_cost_items(latest), conv)
        closed_income = [_finance_items(_last_income_items(s), conv) for s in snaps]
        closed_costs = [_finance_items(_last_cost_items(s), conv) for s in snaps]
        sankey_windows = _sankey_windows(live_income, live_costs, closed_income, closed_costs)

        # ── Estructura semanal ─────────────────────────────────────────────
        structure = estructura_semanal(snaps, rate)
        assert structure is not None  # hay cierres: `closes` ya lo garantizó

        # Sesgo del modelo medido contra el histórico real, no supuesto cero.
        observed = [conv(s.last_weeks_total) for s in snaps[1:]]
        predicted = [structure.structural_balance] * len(observed)
        res_mean, res_std = (
            estimate_residuals(observed, predicted) if len(observed) >= 2 else (0.0, 0.0)
        )

        cash_now = conv(latest.cash)
        base = forecast_cash(
            # El cierre ESPERADO de la semana en curso, no la caja de hoy: la
            # semana que corre todavía tiene gastos por pasar, y arrancar de
            # la caja de hoy los ignoraba. Además dejaba un escalón visible
            # entre el último punto del histórico y el primero de la
            # proyección, que en el gráfico se lee como un salto de dinero
            # que nunca ocurre.
            starting_cash=conv(latest.expected_cash),
            structure=structure,
            horizon_weeks=horizon_weeks,
            residual_mean=res_mean,
            residual_std=res_std,
            planned=planned or [],
        )
        structural = ForecastBand(
            weeks=base.weeks,
            p10=[int(v) for v in base.p10],
            p50=[int(v) for v in base.p50],
            p90=[int(v) for v in base.p90],
            model="bottom_up",
            week_labels=[season_week_label(world, weeks_offset=w) for w in base.weeks],
        )

        # ── Ruta de series de tiempo ───────────────────────────────────────
        timeseries: ForecastBand | None = None
        if len(cash_series) >= MIN_WEEKS_FOR_TIMESERIES:
            f = ts.auto_forecast(cash_series, horizon=horizon_weeks)
            forecast_weeks = list(range(1, horizon_weeks + 1))
            timeseries = ForecastBand(
                weeks=forecast_weeks,
                p10=[int(v) for v in f.lower],
                p50=[int(v) for v in f.point],
                p90=[int(v) for v in f.upper],
                model=f.model,
                backtest_mae=f.backtest_mae,
                candidates=f.candidates,
                week_labels=[season_week_label(world, weeks_offset=w) for w in forecast_weeks],
            )

        # La frase dice TRES cosas y ninguna más: qué ruta ganó, con qué
        # modelo y con cuánto error. Antes recitaba también cuántas lecturas se
        # usaron, y en un momento se planteó enseñar la tabla entera de
        # candidatos con su error y sus pliegues de backtest -- descartado por
        # el usuario el 2026-09-01: el ranking de los perdedores no cambia
        # ninguna decisión y compite por la atención con la cifra de caja, que
        # es a lo que se viene a esta pantalla.
        if timeseries is None:
            recommended, etiqueta = "bottom_up", "estructural"
            reason = (
                "Ganó la ruta estructural, que descompone la caja en sus partes "
                f"conocidas y no necesita histórico. Faltan "
                f"{max(0, MIN_WEEKS_FOR_TIMESERIES - len(cash_series))} semana(s) "
                "para que compita también la de series de tiempo."
            )
        else:
            # El error medio puede no venir; entonces la frase lo omite en vez
            # de reventar o de inventarse un cero.
            mae = timeseries.backtest_mae
            recommended = timeseries.model
            etiqueta = ts.nombre_de(timeseries.model)
            detalle_mae = f" Error medio {thousands(mae)}." if mae is not None else ""
            reason = (
                f"Ganó la ruta de series de tiempo con el modelo «{etiqueta}», "
                f"elegido por backtest de origen rodante sobre tu histórico.{detalle_mae}"
            )

        anomalies = [
            f"{series[i].date}: caja de {thousands(series[i].cash)}, desviación "
            "atípica frente al resto de la serie"
            for i in sorted(anomaly_idx)
        ]

        # ── Detalles ────────────────────────────────────────────────────────
        # Más reciente primero (al revés que `series`) — igual que la
        # pantalla Detalles de Hattrick Control, y que la tabla que pidió el
        # usuario replicar.
        # Cada snapshot aporta UNA semana cerrada: la anterior a su captura
        # (ver el comentario del descuadre en `series`). La semana en curso no
        # sale de ningún `last_*` — vive en los campos vivos del último
        # snapshot — así que se añade como una fila propia al final, que es
        # justo la que faltaba en el histórico.
        weekly_rows = [
            (
                WeeklyBreakdownRow(
                    season_week=series[i].season_week,
                    date=series[i].date,
                    is_current=False,
                    income=_income_breakdown_closed(s, conv),
                    costs=_costs_breakdown_closed(s, conv),
                ),
                season_for_datetime(world, closes[i].closed_at),
            )
            for i, s in enumerate(snaps)
        ]
        weekly_rows.append(
            (
                WeeklyBreakdownRow(
                    season_week=season_week_for_datetime(world, latest.captured_at),
                    date=_iso(latest.captured_at),
                    is_current=True,
                    income=_income_breakdown_live(latest, conv),
                    costs=_costs_breakdown_live(latest, conv),
                ),
                season_for_datetime(world, latest.captured_at),
            )
        )
        weekly_rows.reverse()
        weekly_breakdown = [row for row, _season in weekly_rows]

        season_row_indices: dict[int, list[int]] = defaultdict(list)
        for i, (_row, season) in enumerate(weekly_rows):
            if season is not None:
                season_row_indices[season].append(i)
        season_breakdown_totals = [
            SeasonBreakdownTotals(
                season=season,
                income=_aggregate_income([weekly_breakdown[i].income for i in indices]),
                costs=_aggregate_costs([weekly_breakdown[i].costs for i in indices]),
            )
            for season, indices in sorted(season_row_indices.items(), reverse=True)
        ]

        return EconomyResponse(
            team_name=team.name,
            currency=team.currency_name or "",
            cash=cash_now,
            expected_cash=conv(latest.expected_cash),
            weekly_balance=conv(latest.last_weeks_total),
            structural_balance=structure.structural_balance,
            series=series,
            current_week=current_week,
            weekly_finance=WeeklyFinance(
                income=live_income,
                costs=live_costs,
                income_total=conv(latest.income_sum),
                costs_total=conv(latest.costs_sum),
                expected_balance=conv(latest.expected_weeks_total),
            ),
            sankey_windows=sankey_windows,
            balance_windows=_balance_windows(series),
            structural_forecast=structural,
            timeseries_forecast=timeseries,
            recommended_model=recommended,
            recommended_model_label=etiqueta,
            recommendation_reason=reason,
            anomalies=anomalies,
            weeks_of_history=len(cash_series),
            weekly_breakdown=weekly_breakdown,
            season_breakdown_totals=season_breakdown_totals,
            min_weeks_for_timeseries=MIN_WEEKS_FOR_TIMESERIES,
            wage_bill=await self._wage_bill(team, rate),
            weekly_structure=RecurringWeek(
                salaries=structure.salaries,
                staff=structure.staff,
                arena_maintenance=structure.arena_maintenance,
                sponsors=structure.sponsors,
                base_gate=structure.base_gate,
                weekly_gate=structure.gate_per_week,
                other_fixed=structure.other_fixed,
            ),
        )


def _sum_optional(*values: int | None) -> int | None:
    """Suma varios campos CHPP que Hattrick agrupa en una sola categoría en su
    propio informe. `None` significa que ningún campo del grupo llegó en el
    sync; si al menos uno llegó, los ausentes cuentan como cero."""
    present = [v for v in values if v is not None]
    return sum(present) if present else None


# Mismo orden y mismos nombres que el informe de finanzas semanal de Hattrick.
# "Patrocinadores" agrupa IncomeSponsors + IncomeSponsorBonuses y "Temporal"
# agrupa los campos Financial + Temporary — no son agrupaciones inventadas por
# HT Lens, son cómo Hattrick presenta estas partidas.
def _income_items(snapshot: m.EconomySnapshot) -> list[tuple[str, str, int | None]]:
    return [
        ("IncomeSpectators", "Taquillas", snapshot.income_spectators),
        (
            "IncomeSponsors",
            "Patrocinadores",
            _sum_optional(snapshot.income_sponsors, snapshot.income_sponsor_bonuses),
        ),
        ("IncomeSoldPlayers", "Venta de jugadores", snapshot.income_sold_players),
        (
            "IncomeSoldPlayersCommission",
            "Comisiones",
            snapshot.income_sold_players_commission,
        ),
        (
            "IncomeOther",
            "Temporal",
            _sum_optional(snapshot.income_financial, snapshot.income_temporary),
        ),
    ]


def _cost_items(snapshot: m.EconomySnapshot) -> list[tuple[str, str, int | None]]:
    return [
        ("CostsPlayers", "Sueldos", snapshot.costs_players),
        ("CostsArena", "Mantenimiento del estadio", snapshot.costs_arena),
        ("CostsArenaBuilding", "Construcción del estadio", snapshot.costs_arena_building),
        ("CostsStaff", "Empleados", snapshot.costs_staff),
        ("CostsYouth", "Gastos juveniles", snapshot.costs_youth),
        ("CostsBoughtPlayers", "Compra de jugadores", snapshot.costs_bought_players),
        (
            "CostsOther",
            "Otros",
            _sum_optional(snapshot.costs_financial, snapshot.costs_temporary),
        ),
    ]


# Mismas categorías que arriba, pero de la semana YA CERRADA (campos Last*).
# Sin LastIncomeSponsorBonuses — ninguna versión de economy.xml lo expone
# para la semana cerrada — así que "Patrocinadores" en semanas pasadas es
# sólo LastIncomeSponsors cuando no hay bono que sumarle.
def _last_income_items(snapshot: m.EconomySnapshot) -> list[tuple[str, str, int | None]]:
    return [
        ("IncomeSpectators", "Taquillas", snapshot.last_income_spectators),
        ("IncomeSponsors", "Patrocinadores", _closed_sponsor_income(snapshot)),
        ("IncomeSoldPlayers", "Venta de jugadores", snapshot.last_income_sold_players),
        (
            "IncomeSoldPlayersCommission",
            "Comisiones",
            snapshot.last_income_sold_players_commission,
        ),
        (
            "IncomeOther",
            "Temporal",
            _sum_optional(snapshot.last_income_financial, snapshot.last_income_temporary),
        ),
    ]


def _last_cost_items(snapshot: m.EconomySnapshot) -> list[tuple[str, str, int | None]]:
    return [
        ("CostsPlayers", "Sueldos", snapshot.last_costs_players),
        ("CostsArena", "Mantenimiento del estadio", snapshot.last_costs_arena),
        (
            "CostsArenaBuilding",
            "Construcción del estadio",
            snapshot.last_costs_arena_building,
        ),
        ("CostsStaff", "Empleados", snapshot.last_costs_staff),
        ("CostsYouth", "Gastos juveniles", snapshot.last_costs_youth),
        ("CostsBoughtPlayers", "Compra de jugadores", snapshot.last_costs_bought_players),
        (
            "CostsOther",
            "Otros",
            _sum_optional(snapshot.last_costs_financial, snapshot.last_costs_temporary),
        ),
    ]


def _conv_opt(v: int | None, conv: Callable[[float | None], int]) -> int | None:
    return None if v is None else conv(v)


def _income_breakdown(
    spectators: int | None,
    sponsors: int | None,
    financial: int | None,
    sold_players: int | None,
    commission: int | None,
    temporary: int | None,
    conv: Callable[[float | None], int],
) -> IncomeBreakdown:
    spectators_c = _conv_opt(spectators, conv)
    sponsors_c = _conv_opt(sponsors, conv)
    financial_c = _conv_opt(financial, conv)
    subtotal = _sum_optional(spectators_c, sponsors_c, financial_c)
    other = _sum_optional(
        _conv_opt(sold_players, conv),
        _conv_opt(commission, conv),
        _conv_opt(temporary, conv),
    )
    return IncomeBreakdown(
        spectators=spectators_c,
        sponsors=sponsors_c,
        financial=financial_c,
        subtotal=subtotal,
        other=other,
        total=_sum_optional(subtotal, other),
    )


def _income_breakdown_live(
    snapshot: m.EconomySnapshot, conv: Callable[[float | None], int]
) -> IncomeBreakdown:
    return _income_breakdown(
        snapshot.income_spectators,
        total_sponsor_income(snapshot.income_sponsors, snapshot.income_sponsor_bonuses),
        snapshot.income_financial,
        snapshot.income_sold_players,
        snapshot.income_sold_players_commission,
        snapshot.income_temporary,
        conv,
    )


def _closed_sponsor_income(snapshot: m.EconomySnapshot) -> int | None:
    """Patrocinadores de la semana cerrada, bono incluido.

    Ninguna versión de `economy.xml` expone `LastIncomeSponsorBonuses`, así que
    la fila de patrocinadores salía sin el bono y el desglose sumaba MENOS que
    el total oficial. Caso real 2026-08-16: 205.000 de diferencia cada semana,
    exactamente el bono que sí se ve en la semana en curso.

    No hace falta suponerlo. `LastIncomeSum` es el total oficial y las demás
    partidas vienen desglosadas: lo que sobra al restarlas ES el bono, por
    definición. Es aritmética sobre datos que CHPP ya dio, no una estimación —
    si falta cualquier pieza se devuelve la cifra sin bono en vez de inventar.
    """
    parts = (
        snapshot.last_income_spectators,
        snapshot.last_income_sponsors,
        snapshot.last_income_sold_players,
        snapshot.last_income_sold_players_commission,
        snapshot.last_income_financial,
        snapshot.last_income_temporary,
    )
    if snapshot.last_income_sum is None or any(p is None for p in parts):
        return snapshot.last_income_sponsors
    remainder = snapshot.last_income_sum - sum(p or 0 for p in parts)
    if remainder <= 0:
        return snapshot.last_income_sponsors
    return (snapshot.last_income_sponsors or 0) + remainder


def _income_breakdown_closed(
    snapshot: m.EconomySnapshot, conv: Callable[[float | None], int]
) -> IncomeBreakdown:
    return _income_breakdown(
        snapshot.last_income_spectators,
        _closed_sponsor_income(snapshot),
        snapshot.last_income_financial,
        snapshot.last_income_sold_players,
        snapshot.last_income_sold_players_commission,
        snapshot.last_income_temporary,
        conv,
    )


def _costs_breakdown(
    arena: int | None,
    players: int | None,
    financial: int | None,
    staff: int | None,
    youth: int | None,
    bought_players: int | None,
    arena_building: int | None,
    temporary: int | None,
    conv: Callable[[float | None], int],
) -> CostsBreakdown:
    arena_c = _conv_opt(arena, conv)
    players_c = _conv_opt(players, conv)
    financial_c = _conv_opt(financial, conv)
    staff_c = _conv_opt(staff, conv)
    youth_c = _conv_opt(youth, conv)
    subtotal = _sum_optional(arena_c, players_c, financial_c, staff_c, youth_c)
    other = _sum_optional(
        _conv_opt(bought_players, conv),
        _conv_opt(arena_building, conv),
        _conv_opt(temporary, conv),
    )
    return CostsBreakdown(
        arena=arena_c,
        players=players_c,
        financial=financial_c,
        staff=staff_c,
        youth=youth_c,
        subtotal=subtotal,
        other=other,
        total=_sum_optional(subtotal, other),
    )


def _costs_breakdown_live(
    snapshot: m.EconomySnapshot, conv: Callable[[float | None], int]
) -> CostsBreakdown:
    return _costs_breakdown(
        snapshot.costs_arena,
        snapshot.costs_players,
        snapshot.costs_financial,
        snapshot.costs_staff,
        snapshot.costs_youth,
        snapshot.costs_bought_players,
        snapshot.costs_arena_building,
        snapshot.costs_temporary,
        conv,
    )


def _costs_breakdown_closed(
    snapshot: m.EconomySnapshot, conv: Callable[[float | None], int]
) -> CostsBreakdown:
    return _costs_breakdown(
        snapshot.last_costs_arena,
        snapshot.last_costs_players,
        snapshot.last_costs_financial,
        snapshot.last_costs_staff,
        snapshot.last_costs_youth,
        snapshot.last_costs_bought_players,
        snapshot.last_costs_arena_building,
        snapshot.last_costs_temporary,
        conv,
    )


def _aggregate_income(rows: list[IncomeBreakdown]) -> IncomeBreakdown:
    return IncomeBreakdown(
        spectators=_sum_optional(*(r.spectators for r in rows)),
        sponsors=_sum_optional(*(r.sponsors for r in rows)),
        financial=_sum_optional(*(r.financial for r in rows)),
        subtotal=_sum_optional(*(r.subtotal for r in rows)),
        other=_sum_optional(*(r.other for r in rows)),
        total=_sum_optional(*(r.total for r in rows)),
    )


def _aggregate_costs(rows: list[CostsBreakdown]) -> CostsBreakdown:
    return CostsBreakdown(
        arena=_sum_optional(*(r.arena for r in rows)),
        players=_sum_optional(*(r.players for r in rows)),
        financial=_sum_optional(*(r.financial for r in rows)),
        staff=_sum_optional(*(r.staff for r in rows)),
        youth=_sum_optional(*(r.youth for r in rows)),
        subtotal=_sum_optional(*(r.subtotal for r in rows)),
        other=_sum_optional(*(r.other for r in rows)),
        total=_sum_optional(*(r.total for r in rows)),
    )


def _finance_items(
    items: list[tuple[str, str, int | None]], conv: Callable[[int], int]
) -> list[FinanceItem]:
    return [
        FinanceItem(code=code, label=label, amount=conv(amount) if amount is not None else None)
        for code, label, amount in items
    ]


def _merge_finance_items(*item_lists: list[FinanceItem]) -> list[FinanceItem]:
    """Suma listas de FinanceItem del mismo orden/códigos, una lista por
    semana. `None` en una categoría sólo si NINGUNA de las semanas del grupo
    tuvo dato ahí — nunca se rellena con cero lo que no se sabe."""
    base = item_lists[0]
    return [
        FinanceItem(
            code=item.code,
            label=item.label,
            amount=_sum_optional(*(lst[i].amount for lst in item_lists)),
        )
        for i, item in enumerate(base)
    ]


def _sankey_windows(
    live_income: list[FinanceItem],
    live_costs: list[FinanceItem],
    closed_income: list[list[FinanceItem]],
    closed_costs: list[list[FinanceItem]],
) -> list[SankeyWindow]:
    """1 semana es la semana en curso tal cual `weekly_finance`; cada ventana
    mayor le suma las N-1 semanas ya cerradas más recientes (`closed_*`, en
    orden cronológico ascendente, igual que `_balance_windows`)."""
    windows: list[SankeyWindow] = []
    for weeks in (1, 2, 4, 8, 16):
        extra = weeks - 1
        available = min(extra, len(closed_income))
        chosen_income = closed_income[-available:] if available else []
        chosen_costs = closed_costs[-available:] if available else []
        windows.append(
            SankeyWindow(
                weeks=weeks,
                weeks_available=1 + available,
                income=_merge_finance_items(live_income, *chosen_income),
                costs=_merge_finance_items(live_costs, *chosen_costs),
            )
        )
    return windows


def _balance_excl_transfers(points: list[SeriesPoint]) -> int | None:
    sold = [p.sold_players_income for p in points]
    bought = [p.bought_players_costs for p in points]
    if any(v is None for v in sold) or any(v is None for v in bought):
        return None
    income_excl = sum(p.income for p in points) - sum(v for v in sold if v is not None)
    costs_excl = sum(p.costs for p in points) - sum(v for v in bought if v is not None)
    return income_excl - costs_excl


def _balance_windows(series: list[SeriesPoint]) -> list[BalanceWindow]:
    rows: list[BalanceWindow] = []
    for weeks in (2, 4, 8, 16):
        if len(series) < weeks:
            rows.append(
                BalanceWindow(
                    label=f"Últimas {weeks} semanas",
                    weeks_requested=weeks,
                    weeks_available=len(series),
                    income=None,
                    costs=None,
                    balance=None,
                    balance_excl_transfers=None,
                )
            )
            continue
        points = series[-weeks:]
        label = (
            "Balance bisemanal (últimas 2 semanas)" if weeks == 2 else f"Últimas {weeks} semanas"
        )
        rows.append(
            BalanceWindow(
                label=label,
                weeks_requested=weeks,
                weeks_available=weeks,
                income=sum(point.income for point in points),
                costs=sum(point.costs for point in points),
                balance=sum(point.balance for point in points),
                balance_excl_transfers=_balance_excl_transfers(points),
            )
        )
    return rows


def _iso(dt: datetime) -> str:
    return dt.date().isoformat()
