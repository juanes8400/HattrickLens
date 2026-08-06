import { useMemo, useState } from "react";
import type { EChartsOption } from "echarts";
import { economySankeyOption } from "../charts/chartOptions";
import { Chart } from "../charts/Chart";
import { DateRangeFilter, useDateRangeFilter } from "../components/DateRangeFilter";
import {
  ErrorState,
  Kpi,
  Loading,
  Panel,
  ProjectionPanel,
} from "../components/Panels";
import { money } from "../hooks/useFormat";
import { useEconomy } from "../hooks/useTeam";
import type { Economy, ForecastBand } from "../services/api";

type ObservedLayer = "income" | "costs" | "balance" | "cash";

export function EconomyPage() {
  const [horizon, setHorizon] = useState(8);
  const { data, isLoading, isError, error } = useEconomy(horizon);

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <header className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">Economía</h1>
          <p className="text-sm text-[var(--muted)]">
            {data.weeksOfHistory} semana(s) de histórico
          </p>
        </div>
        <label className="text-xs text-[var(--muted)]">
          Horizonte del escenario
          <select
            className="ml-2 rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-[var(--text)]"
            value={horizon}
            onChange={(event) => setHorizon(Number(event.target.value))}
          >
            <option value={4}>4 semanas</option>
            <option value={8}>8 semanas</option>
            <option value={12}>12 semanas</option>
            <option value={16}>16 semanas</option>
          </select>
        </label>
      </header>

      <div className="grid gap-4 sm:grid-cols-2">
        <Kpi label="Caja actual" value={money(data.expectedCash, data.currency)} />
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
        <Panel title="Anomalías observadas" meta="desviación robusta (MAD)">
          <ul className="space-y-1 p-4 text-xs text-[var(--muted)]">
            {data.anomalies.map((anomaly, index) => (
              <li key={index}>{anomaly}</li>
            ))}
          </ul>
        </Panel>
      )}

      <ForecastPanel data={data} horizon={horizon} />
    </div>
  );
}

function WeeklyFinanceTable({ data }: { data: Economy }) {
  const { weeklyFinance } = data;
  const rows = Math.max(weeklyFinance.income.length, weeklyFinance.costs.length);

  return (
    <Panel title="Finanzas de esta semana">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-sm">
          <thead className="border-b border-[var(--border)] text-left text-xs text-[var(--muted)]">
            <tr>
              <th className="px-4 py-3 font-medium">Ingreso</th>
              <th className="px-4 py-3 text-right font-medium">Valor</th>
              <th className="px-4 py-3 font-medium">Gasto</th>
              <th className="px-4 py-3 text-right font-medium">Valor</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {Array.from({ length: rows }).map((_, i) => {
              const income = weeklyFinance.income[i];
              const cost = weeklyFinance.costs[i];
              return (
                <tr key={i}>
                  <td className="px-4 py-2.5">{income?.label ?? ""}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-[var(--positive)]">
                    {income && income.amount != null ? money(income.amount, data.currency) : ""}
                  </td>
                  <td className="px-4 py-2.5">{cost?.label ?? ""}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-[var(--danger)]">
                    {cost && cost.amount != null ? money(cost.amount, data.currency) : ""}
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot className="border-t-2 border-[var(--border)] text-sm font-semibold">
            <tr>
              <td className="px-4 py-3">Total</td>
              <td className="px-4 py-3 text-right tabular-nums text-[var(--positive)]">
                {money(weeklyFinance.incomeTotal, data.currency)}
              </td>
              <td className="px-4 py-3">Total</td>
              <td className="px-4 py-3 text-right tabular-nums text-[var(--danger)]">
                {money(weeklyFinance.costsTotal, data.currency)}
              </td>
            </tr>
            <tr>
              <td className="px-4 py-3" colSpan={2}>Resultado semanal presupuestado</td>
              <td
                className={`px-4 py-3 text-right tabular-nums ${weeklyFinance.expectedBalance >= 0 ? "text-[var(--positive)]" : "text-[var(--danger)]"}`}
                colSpan={2}
              >
                {money(weeklyFinance.expectedBalance, data.currency)}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </Panel>
  );
}

function HattrickFlow({ data }: { data: Economy }) {
  const [weeks, setWeeks] = useState(1);
  const flow = data.sankeyWindows.find((w) => w.weeks === weeks) ?? data.sankeyWindows[0];

  return (
    <Panel
      title="Flujo"
      meta={
        flow && flow.weeksAvailable < flow.weeks
          ? `sólo ${flow.weeksAvailable} de ${flow.weeks} semana(s) disponibles`
          : undefined
      }
    >
      <div className="flex flex-wrap gap-1 border-b border-[var(--border)] px-4 py-2">
        {data.sankeyWindows.map((w) => (
          <button
            key={w.weeks}
            onClick={() => setWeeks(w.weeks)}
            className={
              w.weeks === weeks
                ? "rounded-md bg-[var(--accent)] px-2.5 py-1 text-xs font-medium text-white"
                : "rounded-md px-2.5 py-1 text-xs text-[var(--muted)] hover:text-[var(--text)]"
            }
          >
            {w.weeks === 1 ? "esta semana" : `${w.weeks} semanas`}
          </button>
        ))}
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
  const dates = useMemo(() => data.series.map((point) => point.date), [data.series]);
  const range = useDateRangeFilter(dates);
  const filtered = useMemo(
    () => range.indices.map((i) => data.series[i]).filter((p): p is Economy["series"][number] => !!p),
    [data.series, range.indices],
  );
  const option = useMemo(
    () => observedEconomyOption(filtered, visible),
    [filtered, visible],
  );

  return (
    <Panel title="Histórico semanal">
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
        <DateRangeFilter range={range.range} onChange={range.setRange} min={range.min} max={range.max} />
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
    <label className="inline-flex cursor-pointer items-center gap-2 text-[var(--muted)] hover:text-[var(--text)]">
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
      data: points.map((point) => point.date),
      boundaryGap: false,
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { opacity: 0.15 } },
      axisLabel: {
        formatter: (value: number) => value.toLocaleString("es-CO"),
      },
    },
    dataZoom: [{ type: "inside" }],
    tooltip: {
      trigger: "axis",
      valueFormatter: (value) => Number(value).toLocaleString("es-CO"),
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
              <th className="px-4 py-3 font-medium">Periodo</th>
              <th className="px-4 py-3 text-right font-medium">Ingresos</th>
              <th className="px-4 py-3 text-right font-medium">Gastos</th>
              <th className="px-4 py-3 text-right font-medium">Balance</th>
              <th className="px-4 py-3 text-right font-medium">Balance sin transferencias</th>
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
                    {complete && window.balanceExclTransfers == null && (
                      <div className="text-xs text-[var(--muted)]">
                        sin transferencias: falta desglose de compraventa
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
                      window.balanceExclTransfers != null && window.balanceExclTransfers < 0
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

function ForecastPanel({ data, horizon }: { data: Economy; horizon: number }) {
  const [showBoth, setShowBoth] = useState(false);
  const preferred =
    data.recommendedModel === "bottom_up"
      ? data.structuralForecast
      : data.timeseriesForecast!;

  // Autonomía: sólo tiene sentido si el ritmo estructural actual es
  // deficitario — con balance positivo la caja crece, no hay cuenta atrás.
  const runwayWeeks =
    data.structuralBalance < 0
      ? Math.floor(data.expectedCash / Math.abs(data.structuralBalance))
      : null;

  // Variación de caja proyectada: hoy vs. el final del horizonte elegido.
  const finalValue = preferred.p50[preferred.p50.length - 1] ?? data.expectedCash;
  const deltaAbs = finalValue - data.expectedCash;
  const deltaPct = data.expectedCash !== 0 ? (deltaAbs / Math.abs(data.expectedCash)) * 100 : 0;

  // Coincidencia entre modelos: sólo cuando hay serie de tiempo con la que
  // contrastar — antes de las 8 semanas de histórico no existe.
  const timeseriesFinal = data.timeseriesForecast
    ? data.timeseriesForecast.p50[data.timeseriesForecast.p50.length - 1] ?? null
    : null;
  const structuralFinal = data.structuralForecast.p50[data.structuralForecast.p50.length - 1] ?? null;
  const modelsAgreePct =
    timeseriesFinal != null && structuralFinal != null && (timeseriesFinal !== 0 || structuralFinal !== 0)
      ? (1 - Math.abs(timeseriesFinal - structuralFinal) / Math.max(Math.abs(timeseriesFinal), Math.abs(structuralFinal), 1)) * 100
      : null;

  return (
    <ProjectionPanel
      title="Escenario de caja, no resultado real"
      meta={`+${horizon} semanas · modelo ${data.recommendedModel}`}
    >
      <div className="grid gap-4 border-b border-dashed border-[var(--accent)] p-4 sm:grid-cols-3">
        <Kpi
          label="Autonomía al ritmo actual"
          value={runwayWeeks != null ? `~${runwayWeeks} semanas` : "caja creciendo"}
          hint={
            runwayWeeks != null
              ? `referencia estructural: ${money(data.structuralBalance, data.currency)}/sem`
              : "el balance estructural semanal es positivo"
          }
          tone={runwayWeeks != null ? "danger" : "positive"}
        />
        <Kpi
          label={`Caja proyectada en +${horizon} semanas`}
          value={money(finalValue, data.currency)}
          hint={`${deltaAbs >= 0 ? "+" : ""}${money(deltaAbs, data.currency)} (${deltaPct >= 0 ? "+" : ""}${deltaPct.toFixed(0)}%) vs. hoy`}
          tone={deltaAbs >= 0 ? "positive" : "danger"}
        />
        <Kpi
          label="Coincidencia entre modelos"
          value={modelsAgreePct != null ? `${modelsAgreePct.toFixed(0)}%` : "no disponible"}
          hint={
            modelsAgreePct != null
              ? "qué tan cerca terminan estructural y serie de tiempo"
              : "la serie de tiempo aún no existe — ver el motivo abajo"
          }
          tone={modelsAgreePct != null && modelsAgreePct < 70 ? "danger" : undefined}
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

/** Una sola línea de tiempo: caja real observada hasta hoy, y desde ahí la
 * banda proyectada — en vez de dos gráficas separadas con ejes distintos que
 * obligan a comparar mentalmente dónde termina una y empieza la otra. */
function unifiedCashOption(
  data: Economy,
  preferred: ForecastBand,
  showBoth: boolean,
): EChartsOption {
  const histDates = data.series.map((p) => p.date);
  const histCash = data.series.map((p) => p.cash);
  const today = histDates[histDates.length - 1] ?? "hoy";
  const labels = [...histDates, ...preferred.weeks.map((w) => `+${w}`)];
  const bridge = histCash[histCash.length - 1] ?? 0;
  const gap = (n: number): (number | null)[] => Array(n).fill(null);

  const actual: (number | null)[] = [...histCash, ...gap(preferred.weeks.length)];
  const median: (number | null)[] = [...gap(histDates.length - 1), bridge, ...preferred.p50];
  const low: (number | null)[] = [...gap(histDates.length - 1), bridge, ...preferred.p10];
  const high: (number | null)[] = [...gap(histDates.length - 1), bridge, ...preferred.p90];

  const series: NonNullable<EChartsOption["series"]> = [
    {
      name: "p10", type: "line", data: low, lineStyle: { opacity: 0 },
      stack: "band", symbol: "none",
    },
    {
      name: "p10–p90", type: "line",
      data: high.map((h, i) => (h == null || low[i] == null ? null : h - (low[i] as number))),
      lineStyle: { opacity: 0 }, areaStyle: { color: "#4f7cff", opacity: 0.16 },
      stack: "band", symbol: "none",
    },
    {
      name: "Proyección central", type: "line", data: median, smooth: true, symbol: "none",
      lineStyle: { width: 2, type: "dashed" },
      markLine: {
        silent: true, symbol: "none",
        lineStyle: { color: "#e5484d", type: "dashed" },
        label: { formatter: "sin fondos" },
        data: [{ yAxis: 0 }],
      },
    },
    {
      name: "Caja real", type: "line", data: actual, symbol: "circle", symbolSize: 5,
      lineStyle: { width: 2 },
      markLine: {
        silent: true, symbol: "none",
        lineStyle: { color: "#94a3b8" },
        label: { formatter: "hoy", position: "end" },
        data: [{ xAxis: today }],
      },
    },
  ];

  if (showBoth && data.timeseriesForecast) {
    series.push({
      name: `Proyección ${data.timeseriesForecast.model}`, type: "line", smooth: true,
      symbol: "none", lineStyle: { width: 2 },
      data: [...gap(histDates.length - 1), bridge, ...data.timeseriesForecast.p50],
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
      valueFormatter: (value) => (value == null ? "—" : Number(value).toLocaleString("es-CO")),
    },
    series,
  };
}
