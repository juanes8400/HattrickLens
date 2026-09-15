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

import { tx } from "../i18n/tx";
type ObservedLayer = "income" | "costs" | "balance" | "cash";
type EconomySection = "resumen" | "proyeccion" | "detalles";
type Horizon = "2" | "4" | "8" | "12" | "16";

/**
 * Economía, en 3 secciones (2026-08-09, pedido explícito: mismo patrón de
 * `Tabs` píldora ya usado en Liga/Transferencias), Resumen es lo que
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
          <h1 className="text-xl font-semibold">{tx("Economía")}</h1>
          <p className="text-sm text-[var(--muted)]">
            {data.weeksOfHistory} {tx("semana(s) de histórico")}
          </p>
          <EnlaceATransparencia seccion="economia" calculo="estructural" />
        </div>
        <Tabs
          grupo="economia"
          tabs={[
            { key: "resumen", label: tx("Resumen") },
            { key: "proyeccion", label: tx("Proyección") },
            { key: "detalles", label: tx("Detalles") },
          ]}
          active={section}
          onChange={setSection}
        />
      </header>

      <PanelDePestanas grupo="economia" activa={section} className="space-y-4">
        {section === "resumen" && (
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 [&>*]:min-w-0">
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
                label={tx("Caja actual")}
                value={money(data.cash, data.currency)}
                hint={tx("cerrará la semana en {{v0}}", {
                  v0: money(data.expectedCash, data.currency),
                })}
              />
              {/* LAS TRES CIFRAS SEMANALES, JUNTAS Y CON SU NOMBRE (2026-09-13).
                  Salían en tres sitios con tres valores y ninguna pantalla decía
                  por qué no coincidían: lo que pasó, lo que va a pasar y el
                  fondo del club son preguntas distintas. */}
              <Kpi
                label={tx("Resultado de la semana pasada")}
                value={money(data.weeklyBalance, data.currency)}
                hint={tx("semana cerrada, compraventa incluida")}
                tone={data.weeklyBalance >= 0 ? "positive" : "danger"}
              />
              <Kpi
                label={tx("Presupuesto de esta semana")}
                value={money(data.weeklyFinance.expectedBalance, data.currency)}
                hint={tx(
                  "lo que Hattrick prevé; la taquilla entra al jugar en casa",
                )}
                tone={
                  data.weeklyFinance.expectedBalance >= 0
                    ? "positive"
                    : "danger"
                }
              />
              <Kpi
                label={
                  data.balanceSinTransferencias != null &&
                  data.balanceSinTransferencias < 0
                    ? tx("Déficit de fondo")
                    : tx("Balance de fondo")
                }
                value={
                  data.balanceSinTransferencias == null
                    ? tx("sin datos")
                    : money(data.balanceSinTransferencias, data.currency)
                }
                hint={tx("media de las semanas cerradas, sin compraventa")}
                tone={
                  data.balanceSinTransferencias == null
                    ? undefined
                    : data.balanceSinTransferencias >= 0
                      ? "positive"
                      : "danger"
                }
              />
            </div>

            <WeeklyFinanceTable data={data} />
            <HattrickFlow data={data} />
            <ObservedHistory data={data} />
            <BalanceWindowsTable data={data} />

            {data.anomalies.length > 0 && (
              <Panel
                title={tx("Anomalías observadas")}
                meta={tx("desviación robusta (MAD)")}
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

function WeeklyFinanceTable({ data }: { data: Economy }) {
  const { weeklyFinance } = data;

  return (
    <Panel title={tx("Finanzas de esta semana")}>
      {/* Eran DOS listas dentro de una sola tabla: ingresos y gastos puestos
          uno al lado del otro, con la cabecera «Valor» repetida y filas
          rellenadas con celdas vacías cuando una lista era más larga que la
          otra. A la vista funcionaba; leído en voz alta cada fila salía como
          «Taquillas, 0 US$, Sueldos, 444.946 US$», emparejando un ingreso con
          un gasto que no tienen nada que ver (2026-08-31).

          Ahora son dos tablas de verdad, cada una con su nombre y su total.
          De paso se apilan en un móvil en vez de arrastrar 560px de ancho. */}
      {/* Lado a lado sólo en pantalla ancha: con «Pasada» y «Cambio» cada
          tabla lleva cuatro columnas y a media anchura las cifras se partían
          en dos líneas (2026-09-13). */}
      <div className="grid gap-4 p-4 xl:grid-cols-2 [&>*]:min-w-0">
        <ListaDeMovimientos
          titulo={tx("Ingresos")}
          filas={weeklyFinance.income}
          total={weeklyFinance.incomeTotal}
          totalAnterior={weeklyFinance.previousIncomeTotal}
          moneda={data.currency}
          tono="var(--positive)"
        />
        <ListaDeMovimientos
          titulo={tx("Gastos")}
          filas={weeklyFinance.costs}
          total={weeklyFinance.costsTotal}
          totalAnterior={weeklyFinance.previousCostsTotal}
          moneda={data.currency}
          tono="var(--danger)"
          gastos
        />
      </div>

      <div className="flex items-baseline justify-between gap-3 border-t-2 border-[var(--border)] px-4 py-3 text-sm font-semibold">
        <span>{tx("Presupuesto de esta semana")}</span>
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
  totalAnterior,
  moneda,
  tono,
  gastos = false,
}: {
  titulo: string;
  filas: { label: string; amount: number | null; previous?: number | null }[];
  total: number;
  totalAnterior?: number | null;
  moneda: string;
  tono: string;
  /** En un gasto, subir es malo: la flecha sube pero va en rojo. */
  gastos?: boolean;
}) {
  // «Esta», «Pasada» y «Cambio» (2026-09-13, pedido del usuario): se ve de
  // dónde viene el cambio de cada rubro frente a la semana cerrada anterior,
  // en la misma tabla de siempre.
  const cambio = (
    actual: number | null,
    anterior: number | null | undefined,
  ) => {
    if (actual == null || anterior == null) {
      return <span className="text-[var(--muted)]">-</span>;
    }
    const d = actual - anterior;
    if (d === 0) return <span className="text-[var(--muted)]">=</span>;
    const bueno = gastos ? d < 0 : d > 0;
    return (
      <span
        style={{ color: bueno ? "var(--positive)" : "var(--danger)" }}
        className="whitespace-nowrap"
      >
        {d > 0 ? "▲" : "▼"} {money(Math.abs(d), moneda)}
      </span>
    );
  };
  return (
    <table className="w-full text-sm">
      <caption className="pb-2 text-left text-xs font-medium tracking-wide text-[var(--muted)] uppercase">
        {titulo}
      </caption>
      <thead className="text-xs text-[var(--muted)]">
        <tr>
          <th scope="col" className="pb-1 pr-3 text-left font-normal">
            <span className="sr-only">{tx("Partida")}</span>
          </th>
          {/* La moneda en todos lados, cabeceras y celdas (2026-09-13, pedido
              del usuario). Las celdas no parten línea. */}
          <th scope="col" className="pb-1 pl-2 text-right font-normal">
            {tx("Actual")}
            {moneda ? ` (${moneda})` : ""}
          </th>
          <th scope="col" className="pb-1 pl-2 text-right font-normal">
            {tx("Pasada")}
            {moneda ? ` (${moneda})` : ""}
          </th>
          <th scope="col" className="pb-1 pl-2 text-right font-normal">
            {tx("Cambio")}
            {moneda ? ` (${moneda})` : ""}
          </th>
        </tr>
      </thead>
      <tbody className="divide-y divide-[var(--border)]">
        {filas.map((fila) => (
          <tr key={fila.label}>
            <th scope="row" className="py-2 pr-3 text-left font-normal">
              {fila.label}
            </th>
            <td
              className="whitespace-nowrap py-2 pl-2 text-right tabular-nums"
              style={{ color: tono }}
            >
              {fila.amount != null ? money(fila.amount, moneda) : "-"}
            </td>
            <td className="whitespace-nowrap py-2 pl-2 text-right tabular-nums text-[var(--muted)]">
              {fila.previous != null ? money(fila.previous, moneda) : "-"}
            </td>
            <td className="py-2 pl-2 text-right tabular-nums">
              {cambio(fila.amount, fila.previous)}
            </td>
          </tr>
        ))}
      </tbody>
      <tfoot className="border-t-2 border-[var(--border)] font-semibold">
        <tr>
          <th scope="row" className="py-2 pr-3 text-left">
            {tx("Total")}
          </th>
          <td
            className="py-2 pl-2 text-right tabular-nums"
            style={{ color: tono }}
          >
            <span className="whitespace-nowrap">{money(total, moneda)}</span>
          </td>
          <td className="whitespace-nowrap py-2 pl-2 text-right tabular-nums text-[var(--muted)]">
            {totalAnterior != null ? money(totalAnterior, moneda) : "-"}
          </td>
          <td className="py-2 pl-2 text-right tabular-nums">
            {cambio(total, totalAnterior)}
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
      title={tx("Flujo")}
      meta={
        flow && flow.weeksAvailable < flow.weeks
          ? tx("sólo {{v0}} de {{v1}} semana(s) disponibles", {
              v0: flow.weeksAvailable,
              v1: flow.weeks,
            })
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
          label={tx("Ventana de tiempo del flujo")}
          tabs={data.sankeyWindows.map((w) => ({
            key: String(w.weeks),
            label:
              w.weeks === 1
                ? tx("esta semana")
                : tx("{{v0}} semanas", { v0: w.weeks }),
          }))}
          active={String(weeks)}
          onChange={(k) => setWeeks(Number(k))}
        />
      </div>
      {flow && (
        <Chart
          ariaLabel={tx(
            "Sankey de ingresos y gastos de las últimas {{v0}} semana(s)",
            { v0: flow.weeksAvailable },
          )}
          option={economySankeyOption(flow.income, flow.costs, data.currency)}
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
    <Panel title={tx("Economía")}>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] px-4 py-3 text-xs">
        <div className="flex flex-wrap gap-x-4 gap-y-2">
          <LayerToggle
            label={tx("Ingresos")}
            checked={visible.income}
            onChange={() => toggle("income")}
          />
          <LayerToggle
            label={tx("Gastos")}
            checked={visible.costs}
            onChange={() => toggle("costs")}
          />
          <LayerToggle
            label={tx("Utilidad")}
            checked={visible.balance}
            onChange={() => toggle("balance")}
          />
          <LayerToggle
            label={tx("Efectivo disponible")}
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
        ariaLabel={tx(
          "Evolución semanal de ingresos, gastos, utilidad y efectivo disponible",
        )}
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
// el valor tal cual, sin resolver custom properties de CSS, un `var()` aquí
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
      name: tx("Ingresos"),
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
      name: tx("Gastos"),
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
      name: tx("Utilidad"),
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
      name: tx("Efectivo disponible"),
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
      // "TT-ss" (temporada-semana, p. ej. "83-05"), cae a la fecha ISO si
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
      title={tx("Balances acumulados")}
      meta={tx("semanas cerradas reportadas por Hattrick")}
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="border-b border-[var(--border)] text-left text-xs text-[var(--muted)]">
            <tr>
              <th scope="col" className="px-4 py-3 font-medium">
                {tx("Periodo")}
              </th>
              <th scope="col" className="px-4 py-3 text-right font-medium">
                {tx("Ingresos")}
              </th>
              <th scope="col" className="px-4 py-3 text-right font-medium">
                {tx("Gastos")}
              </th>
              <th scope="col" className="px-4 py-3 text-right font-medium">
                {tx("Balance")}
              </th>
              <th scope="col" className="px-4 py-3 text-right font-medium">
                {tx("Balance sin transferencias")}
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
                        {tx("faltan datos:")} {window.weeksAvailable}/
                        {window.weeksRequested} {tx("semanas")}
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
      {value == null ? "-" : money(value, currency)}
    </td>
  );
}

const HORIZON_OPTIONS: { key: Horizon; label: string }[] = [
  { key: "2", label: tx("2 semanas") },
  { key: "4", label: tx("4 semanas") },
  { key: "8", label: tx("8 semanas") },
  { key: "12", label: tx("12 semanas") },
  { key: "16", label: tx("16 semanas") },
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
  // SIN COMPRAVENTA POR DEFECTO (2026-09-13). La serie de tiempo proyecta la
  // caja real, y la caja real lleva dentro cada venta y cada compra: repetir
  // «el ritmo de estas semanas» era suponer que se volverá a vender igual. La
  // estructural sólo cuenta lo recurrente. La otra queda como escenario.
  const preferred = data.structuralForecast;

  // Coincidencia entre modelos: sólo cuando hay serie de tiempo con la que
  // contrastar, antes de las N semanas de histórico no existe.
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

  // Cuánto aguanta la caja al ritmo de las últimas semanas cerradas, en dos
  // versiones: sin compraventa --lo que el club hace por sí mismo-- y con
  // ella. Pedido así el 2026-09-04: «Caja / (Ingresos - Gastos), si es
  // negativo avisar de X semanas de autonomía, si es positivo decir que es
  // sostenible».
  //
  // Los dos balances llegan calculados del servidor a partir de los TOTALES
  // que Hattrick reporta de cada semana cerrada, no de la suma de partidas:
  // las partidas suman menos que el total, justo el bono del patrocinador.
  const autonomia = (balance: number | null) => {
    if (balance == null) return null;
    if (balance >= 0) return { sostenible: true, semanas: 0, balance };
    return {
      sostenible: false,
      semanas: Math.floor(data.cash / Math.abs(balance)),
      balance,
    };
  };
  const sinTransferencias = autonomia(data.balanceSinTransferencias);
  const conTransferencias = autonomia(data.balanceConTransferencias);
  // Más de un año no se cuenta en semanas: «236 semanas» finge una precisión
  // que un promedio de cinco cierres no tiene.
  const plazo = (semanas: number) =>
    semanas > 52
      ? `${(semanas / 52).toFixed(1).replace(".", ",")} años`
      : `${semanas} semana${semanas === 1 ? "" : "s"}`;
  const finalValue =
    preferred.p50[preferred.p50.length - 1] ?? data.expectedCash;
  const deltaAbs = finalValue - data.expectedCash;
  const deltaPct =
    data.expectedCash !== 0
      ? (deltaAbs / Math.abs(data.expectedCash)) * 100
      : 0;
  const dinero = (v: number) => money(v, data.currency);

  return (
    <ProjectionPanel
      title={tx("Escenario de caja, no resultado real")}
      meta={tx("sin compraventa")}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-dashed border-[var(--accent)] px-4 py-2">
        {/* El mismo número hace de DOS cosas y la etiqueta lo dice: mira N
            semanas cerradas hacia atrás para promediar, y proyecta N hacia
            adelante. Decir sólo «horizonte» contaba la mitad. */}
        <span className="text-xs text-[var(--muted)]">
          {horizon}{" "}
          {tx("semanas: atrás para promediar, adelante para proyectar")}
        </span>
        {/* No son secciones: las cinco enseñan el MISMO flujo con otra
            ventana de tiempo. */}
        <Tabs
          modo="filtro"
          label={tx("Ventana de tiempo del flujo")}
          tabs={HORIZON_OPTIONS}
          active={horizon}
          onChange={onHorizonChange}
        />
      </div>
      {/* Las dos primeras miden lo mismo con y sin compraventa, y ahí está
          la gracia: un club puede perder dinero cada semana y aun así
          sostenerse comprando y vendiendo, o al revés. */}
      <div className="grid gap-4 border-b border-dashed border-[var(--accent)] p-4 sm:grid-cols-2 lg:grid-cols-4 [&>*]:min-w-0">
        <Kpi
          label={tx("Autonomía sin transferencias")}
          value={
            sinTransferencias == null
              ? tx("sin datos")
              : sinTransferencias.sostenible
                ? tx("se sostiene")
                : plazo(sinTransferencias.semanas)
          }
          hint={
            sinTransferencias == null
              ? tx("hace falta una semana cerrada con desglose")
              : sinTransferencias.sostenible
                ? tx("gana {{v0}}/sem sin contar compraventa", {
                    v0: dinero(sinTransferencias.balance),
                  })
                : tx("pierde {{v0}}/sem sin contar compraventa", {
                    v0: dinero(Math.abs(sinTransferencias.balance)),
                  })
          }
          tone={
            sinTransferencias == null
              ? undefined
              : sinTransferencias.sostenible
                ? "positive"
                : sinTransferencias.semanas > 52
                  ? undefined
                  : "danger"
          }
        />
        <Kpi
          label={tx("Autonomía con transferencias")}
          value={
            conTransferencias == null
              ? tx("sin datos")
              : conTransferencias.sostenible
                ? tx("se sostiene")
                : plazo(conTransferencias.semanas)
          }
          hint={
            conTransferencias == null
              ? tx("hace falta una semana cerrada con desglose")
              : conTransferencias.sostenible
                ? tx("gana {{v0}}/sem contando compraventa", {
                    v0: dinero(conTransferencias.balance),
                  })
                : tx("pierde {{v0}}/sem contando compraventa", {
                    v0: dinero(Math.abs(conTransferencias.balance)),
                  })
          }
          tone={
            conTransferencias == null
              ? undefined
              : conTransferencias.sostenible
                ? "positive"
                : conTransferencias.semanas > 52
                  ? undefined
                  : "danger"
          }
        />
        <Kpi
          label={tx("Caja proyectada en +{{v0}} semanas", { v0: horizon })}
          value={dinero(finalValue)}
          hint={
            `${deltaAbs >= 0 ? "+" : ""}${dinero(deltaAbs)} ` +
            `(${deltaPct >= 0 ? "+" : ""}${deltaPct.toFixed(0)}%) · sin compraventa`
          }
          tone={deltaAbs >= 0 ? "positive" : "danger"}
        />
        <Kpi
          label={tx("Coincidencia entre escenarios")}
          value={
            modelsAgreePct != null
              ? `${modelsAgreePct.toFixed(0)}%`
              : tx("no disponible")
          }
          hint={
            modelsAgreePct != null
              ? tx("qué tan cerca terminan sin y con compraventa")
              : tx(
                  "el escenario con compraventa aún no existe, ver el aviso abajo",
                )
          }
          tone={
            modelsAgreePct != null && modelsAgreePct < 70 ? "danger" : undefined
          }
        />
      </div>
      <div className="border-b border-dashed border-[var(--accent)] px-4 py-3 text-xs leading-relaxed text-[var(--muted)]">
        {/* Reescrito el 2026-09-13: el usuario no entendía «caja sin
            compraventa» ni «el otro escenario». Dicho con lo que es. */}
        {tx(
          "La línea discontinua es tu caja si desde hoy no compras ni vendes a nadie: sueldos, estadio, patrocinio y taquilla, semana a semana.",
        )}
        {data.timeseriesForecast && showBoth && (
          <>
            {" "}
            {tx(
              "La línea continua supone que sigues comprando y vendiendo al mismo ritmo que en las últimas semanas.",
            )}
          </>
        )}
        {data.timeseriesForecast && (
          <button
            className="ml-2 underline hover:text-[var(--text)]"
            onClick={() => setShowBoth((current) => !current)}
          >
            {showBoth
              ? tx("quitar la línea con compraventa")
              : tx("comparar con tu ritmo de compraventa")}
          </button>
        )}
      </div>
      <Chart
        ariaLabel={tx(
          "Caja real hasta hoy, seguida de la proyección con banda de incertidumbre",
        )}
        option={unifiedCashOption(data, preferred, showBoth)}
        height={340}
      />
    </ProjectionPanel>
  );
}

/** Aviso de que viene un modelo mejor, sin fabricar un solo número, barra
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
      title={tx("Viene un modelo más completo")}
      meta={`${data.weeksOfHistory}/${data.minWeeksForTimeseries} semanas`}
    >
      <div className="space-y-3 p-4">
        <p className="prosa text-xs leading-relaxed text-[var(--muted)]">
          {/* Aquí se enumeraban los cuatro modelos que había --naive, drift,
              suavizado exponencial y Holt-Winters--. Desde el 2026-09-01 son
              catorce, así que la lista dejó de caber y, sobre todo, dejó de
              importar: lo que hay que saber es que se elige por backtest
              contra tu propio historial, no cuáles compiten. */}
          {tx("Con")} {data.minWeeksForTimeseries}{" "}
          {tx(
            "semanas de histórico se activa una segunda ruta, de series de tiempo: varios modelos compiten y se queda el que mejor habría predicho tu propio historial, para contrastarlo con la proyección estructural de arriba.",
          )}
          {remaining > 0
            ? tx(" Faltan {{v0}} semana(s).", { v0: remaining })
            : ""}
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

/** Boceto puramente decorativo, sin ejes, sin cifras, sin datos reales ni
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
 * banda proyectada, en vez de dos gráficas separadas con ejes distintos que
 * obligan a comparar mentalmente dónde termina una y empieza la otra. */
function unifiedCashOption(
  data: Economy,
  preferred: ForecastBand,
  showBoth: boolean,
): EChartsOption {
  // "TT-ss" (temporada-semana, p. ej. "83-05"), cae a la fecha ISO/"+N"
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
      // de empezar en el p10 y empezaba en el cero del eje, por eso la línea
      // central parecía estar fuera de la sombra.
      stackStrategy: "all",
      symbol: "none",
    },
    {
      // Nombrada "p90" (no "p10–p90") para que el label de la leyenda diga
      // lo mismo que el tooltip, pedido explícito 2026-08-13. La serie
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
      name: tx("Proyección central"),
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
      name: tx("Caja real"),
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
      name: tx("Proyección con compraventa"),
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
      // banda, su valor crudo no dice nada por sí solo. Pedido explícito
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
        // de "p10" (azul), antes tomaba prestado el de p10Item y el color
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
            {tx("en curso")}
          </span>
        )}
      </span>
    ),
    income: row.income,
    costs: row.costs,
  }));
  const seasonRows = data.seasonBreakdownTotals.map((row) => ({
    key: String(row.season),
    label: tx("Temporada {{v0}}", { v0: row.season }),
    income: row.income,
    costs: row.costs,
  }));

  return (
    <div className="space-y-4">
      <Panel
        title={tx("Ingresos por semana")}
        meta={tx("más reciente primero")}
      >
        <IncomeBreakdownTable rows={weeklyRows} currency={data.currency} />
      </Panel>
      <Panel title={tx("Gastos por semana")} meta={tx("más reciente primero")}>
        <CostsBreakdownTable rows={weeklyRows} currency={data.currency} />
      </Panel>
      {seasonRows.length > 0 && (
        <>
          <Panel title={tx("Total ingresos por temporada")}>
            <IncomeBreakdownTable rows={seasonRows} currency={data.currency} />
          </Panel>
          <Panel title={tx("Total gastos por temporada")}>
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
      {value == null ? "-" : money(value, currency)}
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
              {tx("Semana")}
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              {tx("Aficionados")}
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              {tx("Patrocinados")}
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              {tx("Financieros")}
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              {tx("SubTotal")}
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              {tx("Otros")}
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              {tx("Total")}
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
              {tx("Semana")}
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              {tx("Estadio")}
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              {tx("Jugadores")}
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              {tx("Financieros")}
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              {tx("Empleados")}
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              {tx("Canteranos")}
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              {tx("SubTotal")}
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              {tx("Otros")}
            </th>
            <th scope="col" className="px-3 py-3 text-right font-medium">
              {tx("Total")}
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
