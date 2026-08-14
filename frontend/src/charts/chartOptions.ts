import type { EChartsOption } from "echarts";
import { number } from "../hooks/useFormat";

/** Horizontal bars — the most common shape in this product. */
export function barOption(
  labels: string[],
  values: number[],
  name: string,
): EChartsOption {
  return {
    xAxis: { type: "value", splitLine: { lineStyle: { opacity: 0.15 } } },
    yAxis: {
      type: "category",
      data: labels,
      inverse: true,
      axisLabel: { width: 150, overflow: "truncate" },
    },
    series: [
      {
        type: "bar",
        name,
        data: values,
        barMaxWidth: 18,
        itemStyle: { borderRadius: 3 },
      },
    ],
    tooltip: { trigger: "item" },
  };
}

/** Radar for skill profiles. */
export function radarOption(
  indicators: { name: string; max: number }[],
  series: { name: string; value: number[] }[],
): EChartsOption {
  return {
    tooltip: {},
    legend:
      series.length > 1
        ? { bottom: 0, data: series.map((s) => s.name) }
        : undefined,
    radar: { indicator: indicators, radius: "60%", splitNumber: 4 },
    series: [
      {
        type: "radar",
        data: series,
        areaStyle: { opacity: 0.15 },
        lineStyle: { width: 2 },
      },
    ],
  };
}

/** Serie(s) de tiempo, categoría en el eje X (fechas ya formateadas).
 * `dashed: true` en una serie la pinta como proyección (línea punteada,
 * sin símbolos) en vez de dato real — p.ej. la previsión de Resistencia
 * sobre el mismo eje que las habilidades observadas. `null` en `values`
 * deja un hueco real en la línea (semana sin dato), no la interpola. */
export function timelineOption(
  dates: string[],
  series: { name: string; values: (number | null)[]; dashed?: boolean }[],
): EChartsOption {
  return {
    legend: { bottom: 0, type: "scroll" },
    grid: { left: 48, right: 16, top: 24, bottom: 40, containLabel: true },
    xAxis: { type: "category", data: dates, boundaryGap: false },
    yAxis: { type: "value", splitLine: { lineStyle: { opacity: 0.15 } } },
    dataZoom: [{ type: "inside" }],
    tooltip: { trigger: "axis" },
    series: series.map((s) => ({
      name: s.name,
      type: "line",
      data: s.values,
      smooth: false,
      symbol: s.dashed ? "none" : "circle",
      symbolSize: 5,
      lineStyle: { width: 2, type: s.dashed ? "dashed" : "solid" },
    })),
  };
}

/** Serie(s) de tiempo con el eje X REALMENTE proporcional al tiempo — a
 * diferencia de `timelineOption` (categoría, espaciado siempre igual entre
 * puntos aunque uno esté a 3 días del anterior y otro a 3 semanas), este
 * usa `type: "time"` con timestamps ISO reales, así que la distancia visual
 * entre dos puntos refleja cuánto tiempo pasó de verdad entre ellos.
 * 2026-08-12, pedido explícito para Espíritu/Confianza y Socios: esas
 * lecturas llegan un punto por CAMBIO real de valor (ver `changes_only` en
 * el backend), no una por semana, así que el espaciado desigual es el
 * dato — apiñar todo en un eje de categoría lo escondería. */
export function proportionalTimelineOption(
  timestamps: string[],
  series: { name: string; values: (number | null)[] }[],
): EChartsOption {
  return {
    legend: { bottom: 0, type: "scroll" },
    grid: { left: 48, right: 16, top: 24, bottom: 40, containLabel: true },
    xAxis: { type: "time" },
    yAxis: { type: "value", splitLine: { lineStyle: { opacity: 0.15 } } },
    dataZoom: [{ type: "inside" }],
    tooltip: { trigger: "axis" },
    series: series.map((s) => ({
      name: s.name,
      type: "line",
      data: timestamps.map((t, i) => [t, s.values[i]]),
      smooth: false,
      symbol: "circle",
      symbolSize: 6,
      lineStyle: { width: 2 },
    })),
  };
}

// Marca invisible para desambiguar un nodo del lado de gastos que se llama
// igual que uno del lado de ingresos (p.ej. "Otros" existe en ambos, tal como
// lo llama Hattrick). El sankey necesita nombres de nodo únicos; el
// formatter de abajo la retira antes de pintar la etiqueta, así que el
// rótulo visible queda idéntico al nombre real de Hattrick, sin prefijos
// inventados como "Gasto · ".
const NODE_DEDUP_MARK = "​";

/** Flujo de una lectura observada: ingresos → resultado semanal → gastos.
 * No recibe ni representa datos de forecast. */
export function economySankeyOption(
  income: { label: string; amount: number | null }[],
  costs: { label: string; amount: number | null }[],
): EChartsOption {
  const hasPositiveAmount = (item: {
    label: string;
    amount: number | null;
  }): item is { label: string; amount: number } =>
    item.amount != null && item.amount > 0;
  const positiveIncome = income.filter(hasPositiveAmount);
  const positiveCosts = costs.filter(hasPositiveAmount);
  const incomeTotal = positiveIncome.reduce(
    (sum, item) => sum + item.amount,
    0,
  );
  const costsTotal = positiveCosts.reduce((sum, item) => sum + item.amount, 0);
  const balance = incomeTotal - costsTotal;
  // El nodo central ES el saldo: todo ingreso entra por la izquierda, todo
  // gasto sale por la derecha, y lo que sobra o falta en el medio es
  // exactamente el resultado de la semana — con nombre propio, no un "hub"
  // técnico sin significado.
  const hub = "Saldo de la semana";
  const incomeLabels = new Set(positiveIncome.map((item) => item.label));
  const costNode = (label: string) =>
    incomeLabels.has(label) ? `${label}${NODE_DEDUP_MARK}` : label;

  // La Caja no es un gasto ni un ingreso más: es la reserva del club
  // recibiendo el sobrante o cubriendo el déficit. Color propio y sólido, no
  // el degradado por defecto que comparte con los nodos de gasto.
  const CAJA_COLOR = "#f5a524";
  const cajaLinkStyle = { color: CAJA_COLOR, opacity: 0.55 };

  const links = [
    ...positiveIncome.map((item) => ({
      source: item.label,
      target: hub,
      value: item.amount,
    })),
    ...positiveCosts.map((item) => ({
      source: hub,
      target: costNode(item.label),
      value: item.amount,
    })),
    ...(balance > 0
      ? [{ source: hub, target: "Caja", value: balance, lineStyle: cajaLinkStyle }]
      : balance < 0
        ? [{ source: "Caja", target: hub, value: Math.abs(balance), lineStyle: cajaLinkStyle }]
        : []),
  ];

  return {
    tooltip: {
      trigger: "item",
      valueFormatter: (value) => Number(value).toLocaleString("es-CO"),
    },
    series: [
      {
        type: "sankey",
        data: [
          ...positiveIncome.map((item) => ({ name: item.label })),
          { name: hub },
          ...positiveCosts.map((item) => ({ name: costNode(item.label) })),
          ...(balance !== 0 ? [{ name: "Caja", itemStyle: { color: CAJA_COLOR } }] : []),
        ],
        links,
        left: 12,
        right: 130,
        top: 18,
        bottom: 18,
        nodeWidth: 14,
        nodeGap: 10,
        draggable: false,
        lineStyle: { color: "gradient", curveness: 0.45, opacity: 0.45 },
        label: {
          color: "inherit",
          fontSize: 11,
          formatter: (params) => String(params.name).replace(NODE_DEDUP_MARK, ""),
        },
        emphasis: { focus: "adjacency" },
      },
    ],
  };
}

/** Dona de resultados (Ganados/Empatados/Perdidos). Colores fijos por
 * estado, no por orden de categoría — igual que en el resto de la app
 * (verde=positivo, ámbar=neutro, rojo=negativo). */
export function resultsPieOption(won: number, drawn: number, lost: number): EChartsOption {
  return {
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    legend: { bottom: 0 },
    series: [
      {
        type: "pie",
        radius: ["45%", "70%"],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: "transparent", borderWidth: 2 },
        label: { formatter: "{b}\n{c}" },
        data: [
          { name: "Ganados", value: won, itemStyle: { color: "#2fbf71" } },
          { name: "Empatados", value: drawn, itemStyle: { color: "#f5a524" } },
          { name: "Perdidos", value: lost, itemStyle: { color: "#e5484d" } },
        ],
      },
    ],
  };
}

/** Dispersión x/y con un punto propio resaltado. Cada punto viaja como
 * [x, y, nombre] — `nombre` solo se usa en el tooltip. */
export function highlightedScatterOption(
  points: { x: number; y: number; label: string }[],
  own: { x: number; y: number; label: string },
  xName: string,
  yName: string,
): EChartsOption {
  const others = points.filter((p) => p.label !== own.label);
  return {
    grid: { left: 56, right: 16, top: 20, bottom: 44, containLabel: true },
    xAxis: { type: "value", name: xName, nameLocation: "middle", nameGap: 28 },
    yAxis: { type: "value", name: yName, nameLocation: "middle", nameGap: 44 },
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const item = p as { value: [number, number, string] };
        const [x, y, name] = item.value;
        return `${name}<br/>${xName}: ${number(x)}<br/>${yName}: ${number(y)}`;
      },
    },
    series: [
      {
        name: "Plantilla",
        type: "scatter",
        data: others.map((p) => [p.x, p.y, p.label]),
        symbolSize: 9,
        itemStyle: { opacity: 0.55 },
        z: 1,
      },
      {
        name: own.label,
        type: "scatter",
        data: [[own.x, own.y, own.label]],
        symbolSize: 16,
        itemStyle: { color: "#e5484d", borderColor: "#fff", borderWidth: 1.5 },
        z: 2,
      },
    ],
  };
}
