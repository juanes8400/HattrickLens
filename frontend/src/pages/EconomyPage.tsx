import { EnlaceATransparencia } from "../components/EnlaceATransparencia";
import { useMemo, useState } from "react";
import type { EChartsOption } from "echarts";
import { economySankeyOption } from "../charts/chartOptions";
import { Chart } from "../charts/Chart";
import {
  DateRangeFilter,
  useDateRangeFilter,
} from "../components/DateRangeFilter";
import {
  ErrorState,
  Kpi,
  Loading,
  Panel,
  ProjectionPanel,
  SinDatos,
} from "../components/Panels";
import { Tabs, PanelDePestanas } from "../components/Tabs";
import { money, number } from "../hooks/useFormat";
import { useEconomy } from "../hooks/useTeam";
import type {
  CostsBreakdown,
  Economy,
  ForecastBand,
  IncomeBreakdown,
} from "../services/api";

type ObservedLayer = "income" | "costs" | "balance" | "cash";
type EconomySection = "resumen" | "kpis" | "proyeccion" | "detalles";
type Horizon = "4" | "8" | "12" | "16";

/**
 * Economía, en 3 secciones (2026-08-09, pedido explícito: mismo patrón de
 * `Tabs` píldora ya usado en Liga/Transferencias) — Resumen es lo que
 * Hattrick ya reportó, Proyección es nuestro modelo, Detalles es la
 * pantalla equivalente de Hattrick Control (desglose semana a semana).
 */
export function EconomyPage() {
  const [section, setSection] = useState<EconomySection>("resumen");
  const [horizon, setHorizon] = useState<Horizon>("8");
  const { data, isLoading, isError, error } = useEconomy(Number(horizon));

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return <SinDatos />;

  return (
    <div className="space-y-4">
      <header className="space-y-3">
        <div>
          <h1 className="text-xl font-semibold">Economía</h1>
          <p className="text-sm text-[var(--muted)]">
            {data.weeksOfHistory} semana(s) de histórico
          </p>
          <EnlaceATransparencia seccion="economia" calculo="estructural" />
        </div>
        <Tabs
          grupo="economia"
          tabs={[
            { key: "resumen", label: "Resumen" },
            { key: "kpis", label: "KPIs" },
            { key: "proyeccion", label: "Proyección" },
            { key: "detalles", label: "Detalles" },
          ]}
          active={section}
          onChange={setSection}
        />
      </header>

      <PanelDePestanas grupo="economia" activa={section} className="space-y-4">
        {section === "resumen" && (
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2 [&>*]:min-w-0">
              {/* «Caja actual» es `cash`, no `expectedCash`. Hasta el
                  2026-08-30 esta tarjeta enseñaba la caja PROYECTADA al cierre
                  de la semana con la etiqueta de la caja de hoy, y salia
                  exactamente un presupuesto semanal por debajo de la que enseña
                  el Panel --8.983.969 aqui contra 9.391.047 alli--. Dos
                  pantallas, dos cajas, y una de ellas jurando ser la actual.
                  La proyeccion no se pierde: va de pie de tarjeta, que es donde
                  dice algo, porque la resta entre las dos ES el resultado
                  presupuestado de la semana. */}
              <Kpi
                label="Caja actual"
                value={money(data.cash, data.currency)}
                hint={`cerrará la semana en ${money(data.expectedCash, data.currency)}`}
              />
              <Kpi
                label="Resultado de la última semana"
                value={money(data.weeklyBalance, data.currency)}
                tone={data.weeklyBalance >= 0 ? "positive" : "danger"}
              />
            </div>

            <WeeklyFinanceTable data={data} />
            <HattrickFlow data={data} />
            <ObservedHistory data={data} />
            <BalanceWindowsTable data={data} />

            {data.anomalies.length > 0 && (
              <Panel
                title="Anomalías observadas"
                meta="desviación robusta (MAD)"
              >
                <ul className="space-y-1 p-4 text-xs text-[var(--muted)]">
                  {data.anomalies.map((anomaly, index) => (
                    <li key={index}>{anomaly}</li>
                  ))}
                </ul>
              </Panel>
            )}
          </div>
        )}

        {section === "kpis" && (
          <KpisSection
            data={data}
            horizon={horizon}
            onHorizonChange={setHorizon}
          />
        )}

        {section === "proyeccion" && (
          <div className="space-y-4">
            <ForecastPanel
              data={data}
              horizon={horizon}
              onHorizonChange={setHorizon}
            />
            {!data.timeseriesForecast && <ProjectionTeaser data={data} />}
          </div>
        )}

        {section === "detalles" && <DetailsSection data={data} />}
      </PanelDePestanas>
    </div>
  );
}

/** Los indicadores de una sola cifra, juntos y en su propia pestaña.
 *
 *  2026-09-02, pedido del usuario. Estaban repartidos por las otras pestañas
 *  y compitiendo con las tablas y los gráficos que las llenan: la autonomía y
 *  la caja proyectada vivían dentro del panel de la proyección, o sea que
 *  para leer dos números había que cargar un gráfico. Aquí no hay ni una
 *  tabla ni una gráfica: sólo cifras con su supuesto al pie.
 */
function KpisSection({
  data,
  horizon,
  onHorizonChange,
}: {
  data: Economy;
  horizon: Horizon;
  onHorizonChange: (h: Horizon) => void;
}) {
  const preferred =
    data.recommendedModel === "bottom_up"
      ? data.structuralForecast
      : data.timeseriesForecast!;

  // Autonomía: sólo tiene sentido si el ritmo estructural actual es
  // deficitario. Con balance positivo la caja crece y no hay cuenta atrás.
  // Se cuenta desde la caja de HOY, no desde la proyectada al cierre: la
  // alerta de déficit dice «con la caja actual aguantas N semanas» y salía
  // con una semana más que esta tarjeta porque cada una partía de una caja
  // distinta (2026-08-31). La misma cuenta tiene que dar el mismo número.
  const runwayWeeks =
    data.structuralBalance < 0
      ? Math.floor(data.cash / Math.abs(data.structuralBalance))
      : null;
  // Más de dos temporadas de cuenta atrás no es una cuenta atrás. Cuando el
  // balance recurrente ronda el cero la división se dispara y «~441 semanas»
  // finge una precisión que no tiene: mueve el balance un 5% y salen 400 o
  // 500 (2026-09-02).
  const equilibrado = runwayWeeks != null && runwayWeeks > 32;

  const finalValue =
    preferred.p50[preferred.p50.length - 1] ?? data.expectedCash;
  const deltaAbs = finalValue - data.expectedCash;
  const deltaPct =
    data.expectedCash !== 0
      ? (deltaAbs / Math.abs(data.expectedCash)) * 100
      : 0;

  const { wageBill, weeklyStructure } = data;
  // Contra el ingreso RECURRENTE, no contra el de la semana en curso: una
  // semana con una venta dentro haría parecer barata una nómina que no se
  // movió.
  // `weeklyGate`, no `baseGate`: el segundo es la taquilla de un DÍA DE
  // PARTIDO y sumarlo a un ingreso semanal enseñaba 1.070.486 donde entran
  // 538.088. Es exactamente el mismo error que acabamos de quitar del motor.
  const ingresoFijo = weeklyStructure.sponsors + weeklyStructure.weeklyGate;
  const gastoFijo =
    weeklyStructure.salaries +
    weeklyStructure.staff +
    weeklyStructure.arenaMaintenance +
    weeklyStructure.otherFixed;
  // Contra el GASTO fijo, no contra el ingreso. Medirlo contra el ingreso
  // parecía lo natural, pero `baseGate` del modelo no es taquilla semanal
  // sino taquilla por partido en casa, y vale 0 en cuanto las dos últimas
  // semanas cerradas no tuvieron ninguno: el indicador saltaría de 359% a la
  // mitad según cayera el calendario, sin que la nómina se hubiera movido.
  // Contra el gasto fijo no depende de nada de eso (2026-09-02).
  const pesoNomina =
    gastoFijo > 0 ? (weeklyStructure.salaries / gastoFijo) * 100 : null;
  // Cuántas semanas de nómina hay en caja. NO es la autonomía: aquí no se
  // descuenta ningún ingreso, es el colchón desnudo.
  const semanasDeNomina =
    wageBill && wageBill.total > 0
      ? Math.floor(data.cash / wageBill.total)
      : null;

  return (
    <div className="space-y-4">
      <Panel title="Caja" meta={`proyección a +${horizon} semanas`}>
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border)] px-4 py-2">
          <span className="text-xs text-[var(--muted)]">
            Horizonte de la caja proyectada
          </span>
          <Tabs
            modo="filtro"
            label="Horizonte de la caja proyectada"
            tabs={HORIZON_OPTIONS}
            active={horizon}
            onChange={onHorizonChange}
          />
        </div>
        {/* Las dos primeras parten de supuestos OPUESTOS y hasta el
            2026-08-31 no lo decían: una cuenta las semanas que aguantas SIN
            volver a fichar ni vender, y la otra proyecta arrastrando el sesgo
            observado de tus últimas semanas, que incluye un mercado muy
            movido. Una decía «te quedan 20 semanas» y la de al lado «+49% de
            caja», las dos a la vez y sin una palabra que las reconciliara. */}
        <div className="grid gap-4 p-4 sm:grid-cols-3 [&>*]:min-w-0">
          <Kpi
            label="Autonomía sin fichar ni vender"
            value={
              runwayWeeks == null
                ? "caja creciendo"
                : equilibrado
                  ? "en equilibrio"
                  : `~${runwayWeeks} semanas`
            }
            hint={
              runwayWeeks == null
                ? "el balance recurrente semanal es positivo"
                : equilibrado
                  ? `pierde ${money(Math.abs(data.structuralBalance), data.currency)}/sem, que la caja cubre durante años`
                  : `sólo con lo recurrente: ${money(data.structuralBalance, data.currency)}/sem`
            }
            tone={runwayWeeks == null || equilibrado ? "positive" : "danger"}
          />
          <Kpi
            label={`Caja proyectada en +${horizon} semanas`}
            value={money(finalValue, data.currency)}
            hint={
              `${deltaAbs >= 0 ? "+" : ""}${money(deltaAbs, data.currency)} ` +
              `(${deltaPct >= 0 ? "+" : ""}${deltaPct.toFixed(0)}%) · si el mercado sigue como estas semanas`
            }
            tone={deltaAbs >= 0 ? "positive" : "danger"}
          />
          <Kpi
            label="Semanas de nómina en caja"
            value={semanasDeNomina != null ? `${semanasDeNomina}` : "sin datos"}
            hint={
              semanasDeNomina != null
                ? "sueldos que paga la caja sin ingresar nada"
                : "hace falta sincronizar la plantilla"
            }
          />
        </div>
      </Panel>

      <Panel
        title="Nómina"
        meta={wageBill ? `${wageBill.players} jugadores` : "sin datos"}
      >
        {wageBill ? (
          <>
            <div className="grid gap-4 p-4 sm:grid-cols-3 [&>*]:min-w-0">
              <Kpi
                label="Sueldos por semana"
                value={money(wageBill.total, data.currency)}
                hint={`${wageBill.players} jugadores en plantilla`}
              />
              {/* El indicador que pidió el usuario (2026-09-02). Hattrick
                  cobra un 20% más de sueldo por cada jugador cuyo país de
                  origen no es el del equipo, y ese recargo no se ve en
                  ninguna pantalla: viene ya sumado dentro del sueldo. Por eso
                  se despeja en vez de sumarse. */}
              <Kpi
                label="Recargo por extranjeros"
                value={`${money(wageBill.surcharge, data.currency)}/sem`}
                hint={
                  wageBill.foreignPlayers === wageBill.players
                    ? `los ${wageBill.players} vienen de fuera de ${wageBill.country}`
                    : `${wageBill.foreignPlayers} de ${wageBill.players} vienen de fuera de ${wageBill.country}`
                }
                tone={wageBill.surcharge > 0 ? "danger" : "positive"}
              />
              <Kpi
                label="Peso en el gasto fijo"
                value={
                  pesoNomina != null ? `${pesoNomina.toFixed(0)}%` : "sin datos"
                }
                hint="de cada peso fijo que sale, cuánto es sueldo"
              />
            </div>
            <p className="border-t border-[var(--border)] px-4 py-3 text-xs leading-relaxed text-[var(--muted)]">
              El recargo es un 20% sobre el sueldo base, así que el sueldo que
              ves ya lo lleva dentro: de cada{" "}
              {money(wageBill.foreignSalary, data.currency)} que pagas a
              jugadores de fuera, una sexta parte es recargo. No baja renovando
              ni esperando: sólo se va cuando se va el jugador.
              {wageBill.unknownCountry > 0 &&
                ` ${wageBill.unknownCountry} jugador(es) no tienen país conocido y quedan fuera de la cuenta.`}
            </p>
          </>
        ) : (
          <SinDatos />
        )}
      </Panel>

      <Panel title="Lo fijo de cada semana" meta="ritmo recurrente">
        <div className="grid gap-4 p-4 sm:grid-cols-3 [&>*]:min-w-0">
          <Kpi
            label="Entra"
            value={`${money(ingresoFijo, data.currency)}/sem`}
            hint={
              weeklyStructure.weeklyGate > 0
                ? "patrocinios y taquilla"
                : "patrocinios; sin partido en casa en las semanas cerradas"
            }
            tone="positive"
          />
          <Kpi
            label="Sale"
            value={`${money(gastoFijo, data.currency)}/sem`}
            hint="sueldos, cuerpo técnico y estadio"
            tone="danger"
          />
          <Kpi
            label="Queda"
            value={`${money(data.structuralBalance, data.currency)}/sem`}
            hint="sin contar ninguna compraventa"
            tone={data.structuralBalance >= 0 ? "positive" : "danger"}
          />
        </div>
      </Panel>
    </div>
  );
}

function WeeklyFinanceTable({ data }: { data: Economy }) {
  const { weeklyFinance } = data;

  return (
    <Panel title="Finanzas de esta semana">
      {/* Eran DOS listas dentro de una sola tabla: ingresos y gastos puestos
          uno al lado del otro, con la cabecera «Valor» repetida y filas
          rellenadas con celdas vacías cuando una lista era más larga que la
          otra. A la vista funcionaba; leído en voz alta cada fila salía como
          «Taquillas, 0 US$, Sueldos, 444.946 US$», emparejando un ingreso con
          un gasto que no tienen nada que ver (2026-08-31).

          Ahora son dos tablas de verdad, cada una con su nombre y su total.
          De paso se apilan en un móvil en vez de arrastrar 560px de ancho. */}
      <div className="grid gap-4 p-4 sm:grid-cols-2 [&>*]:min-w-0">
        <ListaDeMovimientos
          titulo="Ingresos"
          filas={weeklyFinance.income}
          total={weeklyFinance.incomeTotal}
          moneda={data.currency}
          tono="var(--positive)"
        />
        <ListaDeMovimientos
          titulo="Gastos"
          filas={weeklyFinance.costs}
          total={weeklyFinance.costsTotal}
          moneda={data.currency}
          tono="var(--danger)"
        />
      </div>

      <div className="flex items-baseline justify-between gap-3 border-t-2 border-[var(--border)] px-4 py-3 text-sm font-semibold">
        <span>Resultado semanal presupuestado</span>
        <span
          className="tabular-nums"
          style={{
            color:
              weeklyFinance.expectedBalance >= 0
                ? "var(--positive)"
                : "var(--danger)",
          }}
        >
          {money(weeklyFinance.expectedBalance, data.currency)}
        </span>
      </div>
    </Panel>
  );
}

/** Una de las dos columnas de la semana: qué entró, o qué salió.
 *
 *  Es una tabla propia y no media tabla compartida porque son dos series
 *  independientes: no hay ninguna relación entre el tercer ingreso y el
 *  tercer gasto, y ponerlos en la misma fila afirmaba que la había. */
function ListaDeMovimientos({
  titulo,
  filas,
  total,
  moneda,
  tono,
}: {
  titulo: string;
  filas: { label: string; amount: number | null }[];
  total: number;
  moneda: string;
  tono: string;
}) {
  return (
    <table className="w-full text-sm">
      <caption className="pb-2 text-left text-xs font-medium tracking-wide text-[var(--muted)] uppercase">
        {titulo}
      </caption>
      <tbody className="divide-y divide-[var(--border)]">
        {filas.map((fila) => (
          <tr key={fila.label}>
            <th scope="row" className="py-2 pr-3 text-left font-normal">
              {fila.label}
            </th>
            <td
              className="py-2 text-right tabular-nums"
              style={{ color: tono }}
            >
              {fila.amount != null ? money(fila.amount, moneda) : "—"}
            </td>
          </tr>
        ))}
      </tbody>
      <tfoot className="border-t-2 border-[var(--border)] font-semibold">
        <tr>
          <th scope="row" className="py-2 pr-3 text-left">
            Total
          </th>
          <td className="py-2 text-right tabular-nums" style={{ color: tono }}>
            {money(total, moneda)}
          </td>
        </tr>
      </tfoot>
    </table>
  );
}

function HattrickFlow({ data }: { data: Economy }) {
  const [weeks, setWeeks] = useState(1);
  const flow =
    data.sankeyWindows.find((w) => w.weeks === weeks) ?? data.sankeyWindows[0];

  return (
    <Panel
      title="Flujo"
      meta={
        flow && flow.weeksAvailable < flow.weeks
          ? `sólo ${flow.weeksAvailable} de ${flow.weeks} semana(s) disponibles`
          : undefined
      }
    >
      {/* Era el mismo control segmentado montado a mano por TERCERA vez:
          botones sueltos, sin `role`, sin estado y con su propio juego de
          clases. Ahora sale del componente compartido, en modo filtro --las
          cinco enseñan el mismo flujo con otra ventana-- así que declara
          `aria-pressed` como los demás (2026-08-31). */}
      <div className="border-b border-[var(--border)] px-4 py-2">
        <Tabs
          modo="filtro"
          label="Ventana de tiempo del flujo"
          tabs={data.sankeyWindows.map((w) => ({
            key: String(w.weeks),
            label: w.weeks === 1 ? "esta semana" : `${w.weeks} semanas`,
          }))}
          active={String(weeks)}
          onChange={(k) => setWeeks(Number(k))}
        />
      </div>
      {flow && (
        <Chart
          ariaLabel={`Sankey de ingresos y gastos de las últimas ${flow.weeksAvailable} semana(s)`}
          option={economySankeyOption(flow.income, flow.costs)}
          height={300}
        />
      )}
    </Panel>
  );
}

function ObservedHistory({ data }: { data: Economy }) {
  const [visible, setVisible] = useState<Record<ObservedLayer, boolean>>({
    income: true,
    costs: true,
    balance: true,
    cash: true,
  });
  const toggle = (layer: ObservedLayer) =>
    setVisible((current) => ({ ...current, [layer]: !current[layer] }));
  // La semana en curso va al final de la serie SÓLO para pintar: sin ella el
  // gráfico acababa en la semana pasada y Proyección arrancaba en la
  // siguiente, así que hoy no salía en ninguna de las dos.
  const points = useMemo(
    () => (data.currentWeek ? [...data.series, data.currentWeek] : data.series),
    [data.series, data.currentWeek],
  );
  const dates = useMemo(() => points.map((point) => point.date), [points]);
  const range = useDateRangeFilter(dates);
  const filtered = useMemo(
    () =>
      range.indices
        .map((i) => points[i])
        .filter((p): p is Economy["series"][number] => !!p),
    [points, range.indices],
  );
  const option = useMemo(
    () => observedEconomyOption(filtered, visible),
    [filtered, visible],
  );

  return (
    <Panel title="Economía">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] px-4 py-3 text-xs">
        <div className="flex flex-wrap gap-x-4 gap-y-2">
          <LayerToggle
            label="Ingresos"
            checked={visible.income}
            onChange={() => toggle("income")}
          />
          <LayerToggle
            label="Gastos"
            checked={visible.costs}
            onChange={() => toggle("costs")}
          />
          <LayerToggle
            label="Utilidad"
            checked={visible.balance}
            onChange={() => toggle("balance")}
          />
          <LayerToggle
            label="Efectivo disponible"
            checked={visible.cash}
            onChange={() => toggle("cash")}
          />
        </div>
        <DateRangeFilter
          range={range.range}
          onChange={range.setRange}
          min={range.min}
          max={range.max}
        />
      </div>
      <Chart
        ariaLabel="Evolución semanal de ingresos, gastos, utilidad y efectivo disponible"
        option={option}
        height={320}
      />
    </Panel>
  );
}

function LayerToggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: () => void;
}) {
  return (
    // `min-h-6`: la diana real es la etiqueta entera, y medía 16px de alto
    // --por debajo de los 24 mínimos-- aunque fuera ancha (2026-08-31).
    <label className="inline-flex min-h-6 cursor-pointer items-center gap-2 text-[var(--muted)] hover:text-[var(--text)]">
      <input
        type="checkbox"
        className="accent-[var(--accent)]"
        checked={checked}
        onChange={onChange}
      />
      {label}
    </label>
  );
}

// Colores fijos, no `var(--…)`: el renderer de canvas de ECharts pinta con
// el valor tal cual, sin resolver custom properties de CSS — un `var()` aquí
// se pintaba con el color por defecto de la paleta, no el que se pedía.
const OBSERVED_COLORS = {
  income: "#2fbf71", // verde
  costs: "#e5484d", // rojo
  balance: "#4f7cff", // azul
  cash: "#f5a524", // amarillo
} as const;

function observedEconomyOption(
  points: Economy["series"],
  visible: Record<ObservedLayer, boolean>,
): EChartsOption {
  const series: NonNullable<EChartsOption["series"]> = [];

  if (visible.income) {
    series.push({
      name: "Ingresos",
      type: "line",
      data: points.map((point) => point.income),
      symbol: "circle",
      symbolSize: 5,
      lineStyle: { width: 2, color: OBSERVED_COLORS.income },
      itemStyle: { color: OBSERVED_COLORS.income },
    });
  }
  if (visible.costs) {
    series.push({
      name: "Gastos",
      type: "line",
      data: points.map((point) => point.costs),
      symbol: "circle",
      symbolSize: 5,
      lineStyle: { width: 2, type: "dashed", color: OBSERVED_COLORS.costs },
      itemStyle: { color: OBSERVED_COLORS.costs },
    });
  }
  if (visible.balance) {
    series.push({
      name: "Utilidad",
      type: "line",
      data: points.map((point) => point.balance),
      symbol: "diamond",
      symbolSize: 7,
      lineStyle: { width: 3, color: OBSERVED_COLORS.balance },
      itemStyle: { color: OBSERVED_COLORS.balance },
    });
  }
  if (visible.cash) {
    series.push({
      name: "Efectivo disponible",
      type: "line",
      data: points.map((point) => point.cash),
      symbol: "none",
      lineStyle: { width: 3, color: OBSERVED_COLORS.cash },
      itemStyle: { color: OBSERVED_COLORS.cash },
    });
  }

  return {
    legend: { bottom: 0, type: "scroll" },
    grid: { left: 50, right: 16, top: 24, bottom: 40, containLabel: true },
    xAxis: {
      type: "category",
      // "TT-ss" (temporada-semana, p. ej. "83-05") — cae a la fecha ISO si
      // el equipo todavía no sincronizó worlddetails.xml.
      data: points.map((point) => point.seasonWeek ?? point.date),
      boundaryGap: false,
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { opacity: 0.15 } },
      axisLabel: {
        formatter: (value: number) => number(value),
      },
    },
    dataZoom: [{ type: "inside" }],
    tooltip: {
      trigger: "axis",
      valueFormatter: (value) => number(Number(value)),
    },
    series,
  };
}

function BalanceWindowsTable({ data }: { data: Economy }) {
  return (
    <Panel
      title="Balances acumulados"
      meta="semanas cerradas reportadas por Hattrick"
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="border-b border-[var(--border)] text-left text-xs text-[var(--muted)]">
            <tr>
              <th scope="col" className="px-4 py-3 font-medium">
                Periodo
              </th>
              <th scope="col" className="px-4 py-3 text-right font-medium">
                Ingresos
              </th>
              <th scope="col" className="px-4 py-3 text-right font-medium">
                Gastos
              </th>
              <th scope="col" className="px-4 py-3 text-right font-medium">
                Balance
              </th>
              <th scope="col" className="px-4 py-3 text-right font-medium">
                Balance sin transferencias
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {data.balanceWindows.map((window) => {
              const complete = window.balance != null;
              return (
                <tr key={window.weeksRequested}>
                  <td className="px-4 py-3">
                    <div>{window.label}</div>
                    {!complete && (
                      <div className="text-xs text-[var(--muted)]">
                        faltan datos: {window.weeksAvailable}/
                        {window.weeksRequested} semanas
                      </div>
                    )}
                  </td>
                  <MoneyCell
                    value={window.income}
                    currency={data.currency}
                    tone="positive"
                  />
                  <MoneyCell
                    value={window.costs}
                    currency={data.currency}
                    tone="danger"
                  />
                  <MoneyCell
                    value={window.balance}
                    currency={data.currency}
                    tone={
                      window.balance != null && window.balance < 0
                        ? "danger"
                        : "positive"
                    }
                  />
                  <MoneyCell
                    value={window.balanceExclTransfers}
                    currency={data.currency}
                    tone={
                      window.balanceExclTransfers != null &&
                      window.balanceExclTransfers < 0
                        ? "danger"
                        : "positive"
                    }
                  />
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function MoneyCell({
  value,
  currency,
  tone,
}: {
  value: number | null;
  currency: string;
  tone: "positive" | "danger";
}) {
  return (
    <td
      className={`px-4 py-3 text-right tabular-nums ${
        tone === "positive" ? "text-[var(--positive)]" : "text-[var(--danger)]"
      }`}
    >
      {value == null ? "—" : money(value, currency)}
    </td>
  );
}

const HORIZON_OPTIONS: { key: Horizon; label: string }[] = [
  { key: "4", label: "4 semanas" },
  { key: "8", label: "8 semanas" },
  { key: "12", label: "12 semanas" },
  { key: "16", label: "16 semanas" },
];

function ForecastPanel({
  data,
  horizon,
  onHorizonChange,
}: {
  data: Economy;
  horizon: Horizon;
  onHorizonChange: (h: Horizon) => void;
}) {
  const [showBoth, setShowBoth] = useState(false);
  const preferred =
    data.recommendedModel === "bottom_up"
      ? data.structuralForecast
      : data.timeseriesForecast!;

  // Coincidencia entre modelos: sólo cuando hay serie de tiempo con la que
  // contrastar — antes de las N semanas de histórico no existe.
  const timeseriesFinal = data.timeseriesForecast
    ? (data.timeseriesForecast.p50[data.timeseriesForecast.p50.length - 1] ??
      null)
    : null;
  const structuralFinal =
    data.structuralForecast.p50[data.structuralForecast.p50.length - 1] ?? null;
  const modelsAgreePct =
    timeseriesFinal != null &&
    structuralFinal != null &&
    (timeseriesFinal !== 0 || structuralFinal !== 0)
      ? (1 -
          Math.abs(timeseriesFinal - structuralFinal) /
            Math.max(Math.abs(timeseriesFinal), Math.abs(structuralFinal), 1)) *
        100
      : null;

  return (
    <ProjectionPanel
      title="Escenario de caja, no resultado real"
      meta={`modelo: ${data.recommendedModelLabel}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-dashed border-[var(--accent)] px-4 py-2">
        <span className="text-xs text-[var(--muted)]">
          Horizonte del escenario
        </span>
        {/* No son secciones: las cinco enseñan el MISMO flujo con otra
            ventana de tiempo. */}
        <Tabs
          modo="filtro"
          label="Ventana de tiempo del flujo"
          tabs={HORIZON_OPTIONS}
          active={horizon}
          onChange={onHorizonChange}
        />
      </div>
      <div className="grid gap-4 border-b border-dashed border-[var(--accent)] p-4 [&>*]:min-w-0">
        {/* Aquí queda sólo la tarjeta que habla del propio gráfico. Las
            otras dos, autonomía y caja proyectada, se fueron a la pestaña
            KPIs, que es donde el usuario espera encontrarlas: eran dos cifras
            sueltas escondidas dentro del panel de un gráfico (2026-09-02). */}
        <Kpi
          label="Coincidencia entre modelos"
          value={
            modelsAgreePct != null
              ? `${modelsAgreePct.toFixed(0)}%`
              : "no disponible"
          }
          hint={
            modelsAgreePct != null
              ? "qué tan cerca terminan estructural y serie de tiempo"
              : "la serie de tiempo aún no existe, ver el aviso abajo"
          }
          tone={
            modelsAgreePct != null && modelsAgreePct < 70 ? "danger" : undefined
          }
        />
      </div>
      <div className="border-b border-dashed border-[var(--accent)] px-4 py-3 text-xs leading-relaxed text-[var(--muted)]">
        {data.recommendationReason}
        {data.timeseriesForecast && (
          <button
            className="ml-2 underline hover:text-[var(--text)]"
            onClick={() => setShowBoth((current) => !current)}
          >
            {showBoth
              ? "ver sólo el escenario recomendado"
              : "comparar ambos escenarios"}
          </button>
        )}
      </div>
      <Chart
        ariaLabel="Caja real hasta hoy, seguida de la proyección con banda de incertidumbre"
        option={unifiedCashOption(data, preferred, showBoth)}
        height={340}
      />
    </ProjectionPanel>
  );
}

/** Aviso de que viene un modelo mejor, sin fabricar un solo número — barra
 * de progreso real (semanas de histórico / umbral) más un boceto abstracto
 * (sin ejes ni cifras) que solo ilustra "banda de incertidumbre", nunca un
 * resultado simulado. 2026-08-09, pedido explícito. */
function ProjectionTeaser({ data }: { data: Economy }) {
  const progress = Math.min(
    data.weeksOfHistory / data.minWeeksForTimeseries,
    1,
  );
  const remaining = Math.max(
    data.minWeeksForTimeseries - data.weeksOfHistory,
    0,
  );

  return (
    <Panel
      title="Viene un modelo más completo"
      meta={`${data.weeksOfHistory}/${data.minWeeksForTimeseries} semanas`}
    >
      <div className="space-y-3 p-4">
        <p className="prosa text-xs leading-relaxed text-[var(--muted)]">
          {/* Aquí se enumeraban los cuatro modelos que había --naive, drift,
              suavizado exponencial y Holt-Winters--. Desde el 2026-09-01 son
              catorce, así que la lista dejó de caber y, sobre todo, dejó de
              importar: lo que hay que saber es que se elige por backtest
              contra tu propio historial, no cuáles compiten. */}
          Con {data.minWeeksForTimeseries} semanas de histórico se activa una
          segunda ruta, de series de tiempo: varios modelos compiten y se queda
          el que mejor habría predicho tu propio historial, para contrastarlo
          con la proyección estructural de arriba.
          {remaining > 0 ? ` Faltan ${remaining} semana(s).` : ""}
        </p>
        <div className="h-2 overflow-hidden rounded-full bg-[var(--surface-2)]">
          <div
            className="h-full rounded-full bg-[var(--accent)] transition-all"
            style={{ width: `${progress * 100}%` }}
          />
        </div>
        <TeaserSketch />
      </div>
    </Panel>
  );
}

/** Boceto puramente decorativo — sin ejes, sin cifras, sin datos reales ni
 * simulados. Solo comunica "banda de proyección", nunca un resultado. */
function TeaserSketch() {
  return (
    <svg
      viewBox="0 0 240 60"
      className="h-14 w-full text-[var(--muted)] opacity-50"
      aria-hidden="true"
    >
      <path
        d="M0,48 Q60,20 120,32 T240,10"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeDasharray="5 4"
      />
      <path
        d="M0,58 Q60,34 120,46 T240,26 L240,4 Q180,26 120,14 T0,30 Z"
        fill="var(--accent)"
        opacity="0.12"
      />
    </svg>
  );
}

/** Una sola línea de tiempo: caja real observada hasta hoy, y desde ahí la
 * banda proyectada — en vez de dos gráficas separadas con ejes distintos que
 * obligan a comparar mentalmente dónde termina una y empieza la otra. */
function unifiedCashOption(
  data: Economy,
  preferred: ForecastBand,
  showBoth: boolean,
): EChartsOption {
  // "TT-ss" (temporada-semana, p. ej. "83-05") — cae a la fecha ISO/"+N"
  // relativo si el equipo todavía no sincronizó worlddetails.xml.
  //
  // `series` son semanas CERRADAS, así que termina en la anterior a hoy. La
  // semana en curso llega aparte en `currentWeek` y hay que engancharla aquí:
  // sin ella "hoy" apuntaba a la semana pasada y el eje saltaba de 83-03 a
  // 83-05, dejando fuera precisamente la semana que se está jugando.
  const historyPoints = data.currentWeek
    ? [...data.series, data.currentWeek]
    : data.series;
  const histLabels = historyPoints.map((p) => p.seasonWeek ?? p.date);
  const histCash = historyPoints.map((p) => p.cash);
  const today = histLabels[histLabels.length - 1] ?? "hoy";
  const forecastLabels = preferred.weeks.map(
    (w, i) => preferred.weekLabels[i] ?? `+${w}`,
  );
  const labels = [...histLabels, ...forecastLabels];
  // La caja de la semana en curso ya viene siendo `expectedCash` desde el
  // backend (cada punto es la caja AL CIERRE de su semana), así que aquí no
  // hay que pisar nada. Antes se sobrescribía el último punto a mano, lo que
  // desde que `series` son sólo semanas cerradas habría falseado una semana
  // ya cerrada en los equipos que aún no tienen `currentWeek`.
  const bridge = data.expectedCash;
  const gap = (n: number): (number | null)[] => Array(n).fill(null);

  const actual: (number | null)[] = [
    ...histCash,
    ...gap(preferred.weeks.length),
  ];
  const median: (number | null)[] = [
    ...gap(histLabels.length - 1),
    bridge,
    ...preferred.p50,
  ];
  const low: (number | null)[] = [
    ...gap(histLabels.length - 1),
    bridge,
    ...preferred.p10,
  ];
  const high: (number | null)[] = [
    ...gap(histLabels.length - 1),
    bridge,
    ...preferred.p90,
  ];

  const series: NonNullable<EChartsOption["series"]> = [
    {
      name: "p10",
      type: "line",
      data: low,
      lineStyle: { opacity: 0 },
      stack: "band",
      // Imprescindible con caja proyectada en negativo: ECharts apila lo
      // positivo y lo negativo en pilas distintas, y sin esto la banda dejaba
      // de empezar en el p10 y empezaba en el cero del eje — por eso la línea
      // central parecía estar fuera de la sombra.
      stackStrategy: "all",
      symbol: "none",
    },
    {
      // Nombrada "p90" (no "p10–p90") para que el label de la leyenda diga
      // lo mismo que el tooltip — pedido explícito 2026-08-13. La serie
      // sigue dibujando el delta apilado (p90 - p10) para la banda; el
      // tooltip ya calcula y muestra el p90 real a partir de ese delta.
      name: "p90",
      type: "line",
      data: high.map((h, i) =>
        h == null || low[i] == null ? null : h - (low[i] as number),
      ),
      lineStyle: { opacity: 0 },
      areaStyle: { color: "#4f7cff", opacity: 0.16 },
      stack: "band",
      stackStrategy: "all",
      symbol: "none",
    },
    {
      name: "Proyección central",
      type: "line",
      data: median,
      smooth: true,
      symbol: "none",
      lineStyle: { width: 2, type: "dashed" },
      markLine: {
        silent: true,
        symbol: "none",
        lineStyle: { color: "#e5484d", type: "dashed" },
        label: { formatter: "sin fondos" },
        data: [{ yAxis: 0 }],
      },
    },
    {
      name: "Caja real",
      type: "line",
      data: actual,
      symbol: "circle",
      symbolSize: 5,
      lineStyle: { width: 2 },
      markLine: {
        silent: true,
        symbol: "none",
        lineStyle: { color: "#94a3b8" },
        label: { formatter: "hoy", position: "end" },
        data: [{ xAxis: today }],
      },
    },
  ];

  if (showBoth && data.timeseriesForecast) {
    series.push({
      name: `Proyección ${data.timeseriesForecast.model}`,
      type: "line",
      smooth: true,
      symbol: "none",
      lineStyle: { width: 2 },
      data: [
        ...gap(histLabels.length - 1),
        bridge,
        ...data.timeseriesForecast.p50,
      ],
    });
  }

  return {
    legend: { bottom: 0, type: "scroll" },
    grid: { left: 56, right: 16, top: 24, bottom: 40, containLabel: true },
    xAxis: { type: "category", data: labels, boundaryGap: false },
    yAxis: { type: "value", splitLine: { lineStyle: { opacity: 0.15 } } },
    dataZoom: [{ type: "inside" }],
    tooltip: {
      trigger: "axis",
      // La serie "p90" dibuja el delta apilado (p90 - p10) para pintar la
      // banda — su valor crudo no dice nada por sí solo. Pedido explícito
      // 2026-08-11: mostrar el p90 real (p10 + ese delta) en vez de
      // ocultarlo o mostrar el delta sin explicar qué es.
      formatter: (params) => {
        const items = Array.isArray(params) ? params : [params];
        if (items.length === 0) return "";
        const axisLabel = String(items[0]?.name ?? "");
        const byName = new Map(items.map((p) => [String(p.seriesName), p]));
        const fmt = (v: unknown) => (v == null ? null : number(Number(v)));
        const rows: string[] = [];
        const push = (marker: unknown, label: string, value: unknown) => {
          const formatted = fmt(value);
          if (formatted != null)
            rows.push(`${marker} ${label}: <b>${formatted}</b>`);
        };

        const p10Item = byName.get("p10");
        const deltaItem = byName.get("p90");
        const p90Value =
          p10Item?.value != null && deltaItem?.value != null
            ? Number(p10Item.value) + Number(deltaItem.value)
            : null;
        // El marcador debe ser el de la propia serie "p90" (verde), no el
        // de "p10" (azul) — antes tomaba prestado el de p10Item y el color
        // no coincidía con el de la leyenda. Pedido explícito 2026-08-13.
        if (deltaItem) push(deltaItem.marker, "p90", p90Value);

        for (const name of ["Proyección central", "p10", "Caja real"]) {
          const item = byName.get(name);
          if (item) push(item.marker, name, item.value);
        }
        for (const [name, item] of byName) {
          if (name.startsWith("Proyección ") && name !== "Proyección central") {
            push(item.marker, name, item.value);
          }
        }

        return `${axisLabel}<br/>${rows.join("<br/>")}`;
      },
    },
    series,
  };
}

// ── Detalles ────────────────────────────────────────────────────────────────
// Réplica de la pantalla Detalles de Hattrick Control (referencia visual del
// usuario 2026-08-09): desglose semana a semana con SubTotal (lo
// recurrente/estructural) y Otros (lo ligado a compraventa de jugadores o a
// algo puntual), más los totales acumulados por temporada.

type BreakdownRow = { key: string; label: React.ReactNode };

function DetailsSection({ data }: { data: Economy }) {
  const weeklyRows = data.weeklyBreakdown.map((row) => ({
    key: row.date,
    label: (
      <span className="whitespace-nowrap">
        {row.seasonWeek ?? row.date}
        {row.isCurrent && (
          <span className="ml-1.5 rounded-full bg-[var(--accent-soft)] px-1.5 py-0.5 text-[10px] font-medium text-[var(--accent)]">
            en curso
          </span>
        )}
      </span>
    ),
    income: row.income,
    costs: row.costs,
  }));
  const seasonRows = data.seasonBreakdownTotals.map((row) => ({
    key: String(row.season),
    label: `Temporada ${row.season}`,
    income: row.income,
    costs: row.costs,
  }));

  return (
    <div className="space-y-4">
      <Panel title="Ingresos por semana" meta="más reciente primero">
        <IncomeBreakdownTable rows={weeklyRows} currency={data.currency} />
      </Panel>
      <Panel title="Gastos por semana" meta="más reciente primero">
        <CostsBreakdownTable rows={weeklyRows} currency={data.currency} />
      </Panel>
      {seasonRows.length > 0 && (
        <>
          <Panel title="Total ingresos por temporada">
            <IncomeBreakdownTable rows={seasonRows} currency={data.currency} />
          </Panel>
          <Panel title="Total gastos por temporada">
            <CostsBreakdownTable rows={seasonRows} currency={data.currency} />
          </Panel>
        </>
      )}
    </div>
  );
}

function BreakdownTd({
  value,
  currency,
  emphasis,
  tone,
}: {
  value: number | null;
  currency: string;
  emphasis?: boolean;
  tone?: "positive" | "danger";
}) {
  return (
    <td
      className={`px-3 py-2.5 text-right tabular-nums ${emphasis ? "font-semibold" : ""} ${
        tone === "positive"
          ? "text-[var(--positive)]"
          : tone === "danger"
            ? "text-[var(--danger)]"
            : ""
      }`}
    >
      {value == null ? "—" : money(value, currency)}
    </td>
  );
}

function IncomeBreakdownTable({
  rows,
  currency,
}: {
  rows: (BreakdownRow & { income: IncomeBreakdown })[];
  currency: string;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[680px] text-sm">
        <thead className="border-b border-[var(--border)] text-left text-xs text-[var(--muted)]">
          <tr>
            <th scope="col" className="px-3 py-3 font-medium">
              Semana
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              Aficionados
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              Patrocinados
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              Financieros
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              SubTotal
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              Otros
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              Total
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--border)]">
          {rows.map((row) => (
            <tr key={row.key}>
              <td className="px-3 py-2.5">{row.label}</td>
              <BreakdownTd value={row.income.spectators} currency={currency} />
              <BreakdownTd value={row.income.sponsors} currency={currency} />
              <BreakdownTd value={row.income.financial} currency={currency} />
              <BreakdownTd
                value={row.income.subtotal}
                currency={currency}
                emphasis
              />
              <BreakdownTd value={row.income.other} currency={currency} />
              <BreakdownTd
                value={row.income.total}
                currency={currency}
                emphasis
                tone="positive"
              />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CostsBreakdownTable({
  rows,
  currency,
}: {
  rows: (BreakdownRow & { costs: CostsBreakdown })[];
  currency: string;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[820px] text-sm">
        <thead className="border-b border-[var(--border)] text-left text-xs text-[var(--muted)]">
          <tr>
            <th scope="col" className="px-3 py-3 font-medium">
              Semana
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              Estadio
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              Jugadores
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              Financieros
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              Empleados
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              Canteranos
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              SubTotal
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              Otros
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              Total
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--border)]">
          {rows.map((row) => (
            <tr key={row.key}>
              <td className="px-3 py-2.5">{row.label}</td>
              <BreakdownTd value={row.costs.arena} currency={currency} />
              <BreakdownTd value={row.costs.players} currency={currency} />
              <BreakdownTd value={row.costs.financial} currency={currency} />
              <BreakdownTd value={row.costs.staff} currency={currency} />
              <BreakdownTd value={row.costs.youth} currency={currency} />
              <BreakdownTd
                value={row.costs.subtotal}
                currency={currency}
                emphasis
              />
              <BreakdownTd value={row.costs.other} currency={currency} />
              <BreakdownTd
                value={row.costs.total}
                currency={currency}
                emphasis
                tone="danger"
              />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
