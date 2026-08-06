import type { EChartsOption } from "echarts";

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

/** Serie(s) de tiempo, categoría en el eje X (fechas ya formateadas). */
export function timelineOption(
  dates: string[],
  series: { name: string; values: number[] }[],
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
      symbol: "circle",
      symbolSize: 5,
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
        return `${name}<br/>${xName}: ${x}<br/>${yName}: ${y.toLocaleString()}`;
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
