import type { EChartsOption } from "echarts";
import { metric, number } from "../hooks/useFormat";
import { tx } from "../i18n/tx";

/** Horizontal bars, the most common shape in this product. */
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
 * sin símbolos) en vez de dato real, p.ej. la previsión de Resistencia
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

/** Marca de las dos series auxiliares que dibujan una zona sombreada. No son
 * datos: van fuera de la leyenda y fuera del tooltip. */
const BAND_PREFIX = "__banda";

/** Los colores del comparador de transferencias, compartidos por sus DOS
 *  graficas (2026-10-09).
 *
 *  Van explicitos porque antes no lo estaban: ECharts reparte su paleta por
 *  ORDEN DE SERIE, y la tira tiene dos series mientras la serie en el tiempo
 *  tiene tres --la media va primero--. El resultado era que, en dos graficas
 *  pegadas una encima de otra, el verde significaba «venta cerrada» arriba y
 *  «subasta abierta» abajo. Nadie lo escribio: lo decidio un indice.
 *
 *  Azul para lo provisional y verde para lo firme, que es el orden en que se
 *  leen: una puja todavia puede moverse, un precio pagado ya no. La media va
 *  en gris a proposito, para no competir con los datos que resume. */
/** Un punto pintado segun cuanto se parece esa venta (2026-10-09, pedido del
 *  usuario: «algun indicador de Se parece en la grafica, puede ser puntos mas
 *  pequeños, colores mas suaves»).
 *
 *  Dos canales a la vez, tamaño y opacidad, porque uno solo no se lee: entre
 *  un 85 % y un 100 % --el rango real que da el motor-- la diferencia de
 *  tamaño sola es de tres pixeles. Juntos, un gemelo pesa en el ojo lo que
 *  tiene que pesar y un primo lejano se queda de fondo.
 *
 *  El suelo es 75 porque por debajo el motor ya no acepta la venta; una
 *  lectura vieja sin peso guardado llega como 100 y se pinta entera. */
function segunElParecido(peso: number, base: number) {
  const cuanto = Math.min(Math.max((peso - 75) / 25, 0), 1);
  return { symbolSize: base - 4 + cuanto * 4, opacity: 0.45 + cuanto * 0.55 };
}

const SUBASTA_ABIERTA = "#4f7cff";
const VENTA_CERRADA = "#2fbf71";
const LINEA_DE_LA_MEDIA = "#94a3b8";

/** Sombrea el hueco entre dos líneas de la MISMA magnitud.
 *
 * ECharts no tiene una serie "banda", así que se apilan dos: una base
 * invisible a la altura de la línea de abajo y encima la diferencia, que es
 * la única con relleno. Por eso la base se calcula punto a punto con
 * `Math.min` en vez de fijar cuál de las dos va debajo, si se cruzaran, la
 * banda seguiría cubriendo el hueco real en lugar de invertirse.
 *
 * Una semana sin lectura en cualquiera de las dos deja hueco en la banda
 * también: sombrear ahí inventaría una diferencia que no se midió.
 */
export function bandBetween(
  a: (number | null)[],
  b: (number | null)[],
): Record<string, unknown>[] {
  const base: (number | null)[] = [];
  const gap: (number | null)[] = [];
  a.forEach((low, i) => {
    const high = b[i];
    if (low == null || high == null) {
      base.push(null);
      gap.push(null);
      return;
    }
    base.push(Math.min(low, high));
    gap.push(Math.abs(high - low));
  });
  const invisible = {
    type: "line" as const,
    stack: BAND_PREFIX,
    // Sin esto la banda se rompe en cuanto la base es negativa: ECharts apila
    // los valores positivos y los negativos por separado, así que el relleno
    // dejaba de arrancar en la base y arrancaba en el cero del eje. Se ve con
    // una proyección de caja que se va a números rojos, reportado el
    // 2026-08-19 sobre la gráfica de Economía.
    stackStrategy: "all" as const,
    symbol: "none" as const,
    silent: true,
    z: 1,
    lineStyle: { opacity: 0 },
    emphasis: { disabled: true },
    tooltip: { show: false },
  };
  return [
    { ...invisible, name: `${BAND_PREFIX}-base`, data: base },
    {
      ...invisible,
      name: `${BAND_PREFIX}-hueco`,
      data: gap,
      // Gris neutro y translúcido: funciona sobre el fondo claro y el oscuro,
      // y no compite con el color de ninguna de las dos líneas.
      areaStyle: { color: "rgba(148, 163, 184, 0.28)" },
    },
  ];
}

/** Quita del tooltip los puntos de las series auxiliares de `bandBetween`. */
export function withoutBandInTooltip(): EChartsOption["tooltip"] {
  return {
    trigger: "axis",
    // El `params` de un tooltip de eje trae un punto por serie, incluidas las
    // dos de la banda; sin este filtro la caja mostraría "__banda-hueco".
    formatter: (params: unknown) => {
      const points = (Array.isArray(params) ? params : [params]) as {
        seriesName?: string;
        marker?: string;
        value?: unknown;
        axisValueLabel?: string;
      }[];
      const real = points.filter((p) => !p.seriesName?.startsWith(BAND_PREFIX));
      if (real.length === 0) return "";
      const head = real[0]?.axisValueLabel ?? "";
      const rows = real.map(
        (p) =>
          `${p.marker ?? ""}${p.seriesName ?? ""}: <b>${
            p.value == null ? "-" : number(Number(p.value))
          }</b>`,
      );
      return [head, ...rows].join("<br/>");
    },
  };
}

/** Serie(s) de tiempo con el eje X REALMENTE proporcional al tiempo, a
 * diferencia de `timelineOption` (categoría, espaciado siempre igual entre
 * puntos aunque uno esté a 3 días del anterior y otro a 3 semanas), este
 * usa `type: "time"` con timestamps ISO reales, así que la distancia visual
 * entre dos puntos refleja cuánto tiempo pasó de verdad entre ellos.
 * 2026-08-12, pedido explícito para Espíritu/Confianza y Socios: esas
 * lecturas llegan un punto por CAMBIO real de valor (ver `changes_only` en
 * el backend), no una por semana, así que el espaciado desigual es el
 * dato, apiñar todo en un eje de categoría lo escondería. */
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
  currency = "",
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
  // exactamente el resultado de la semana, con nombre propio, no un "hub"
  // técnico sin significado.
  const hub = tx("Saldo de la semana");
  const incomeLabels = new Set(positiveIncome.map((item) => item.label));
  const costNode = (label: string) =>
    incomeLabels.has(label) ? `${label}${NODE_DEDUP_MARK}` : label;

  // La Caja no es un gasto ni un ingreso más: es la reserva del club
  // recibiendo el sobrante o cubriendo el déficit. Color propio y sólido, no
  // el degradado por defecto que comparte con los nodos de gasto.
  const CAJA_COLOR = "#f5a524";
  // EL NOMBRE DE LA CAJA, UNA SOLA VEZ (2026-09-26). El nodo se creaba con
  // `tx("Caja")` y los enlaces apuntaban al literal "Caja". En español los
  // dos son la misma palabra y coincidían de casualidad; en inglés el nodo se
  // llamaba «Cash» y el enlace buscaba «Caja», que no existe, así que el
  // diagrama se rompía. Era el fallo que reportó el usuario.
  const caja = tx("Caja");
  const cajaLinkStyle = { color: CAJA_COLOR, opacity: 0.55 };
  // Rojo si la semana pierde, verde si gana, gris si queda en cero.
  const colorDelSaldo =
    balance < 0 ? "#e5484d" : balance > 0 ? "#2fbf71" : "#8b8b93";

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
      ? [
          {
            source: hub,
            target: caja,
            value: balance,
            lineStyle: cajaLinkStyle,
          },
        ]
      : balance < 0
        ? [
            {
              source: caja,
              target: hub,
              value: Math.abs(balance),
              lineStyle: cajaLinkStyle,
            },
          ]
        : []),
  ];

  return {
    tooltip: {
      trigger: "item",
      valueFormatter: (value) => metric(Number(value)),
    },
    series: [
      {
        type: "sankey",
        data: [
          ...positiveIncome.map((item) => ({ name: item.label })),
          // EL SALDO CON SIGNO (2026-09-13, pedido del usuario). Con el nodo
          // sin color y sin cifra no se sabía si la semana ganaba o perdía:
          // ahora es rojo o verde y lleva el resultado encima, que es donde
          // ya mira el ojo.
          {
            name: hub,
            itemStyle: { color: colorDelSaldo },
            label: {
              position: "top",
              color: colorDelSaldo,
              fontSize: 12,
              fontWeight: 600,
              formatter: () =>
                `${tx("Saldo")}: ${balance > 0 ? "+" : balance < 0 ? "−" : ""}${number(Math.abs(balance))}${currency ? ` ${currency}` : ""}`,
            },
          },
          ...positiveCosts.map((item) => ({ name: costNode(item.label) })),
          ...(balance !== 0
            ? [{ name: caja, itemStyle: { color: CAJA_COLOR } }]
            : []),
        ],
        links,
        left: 12,
        right: 130,
        // Sitio para la etiqueta del saldo, que va encima de su nodo.
        top: 32,
        bottom: 18,
        nodeWidth: 14,
        nodeGap: 10,
        draggable: false,
        lineStyle: { color: "gradient", curveness: 0.45, opacity: 0.45 },
        label: {
          color: "inherit",
          fontSize: 11,
          formatter: (params) =>
            String(params.name).replace(NODE_DEDUP_MARK, ""),
        },
        emphasis: { focus: "adjacency" },
      },
    ],
  };
}

/** Dona de resultados (Ganados/Empatados/Perdidos). Colores fijos por
 * estado, no por orden de categoría, igual que en el resto de la app
 * (verde=positivo, ámbar=neutro, rojo=negativo). */
export function resultsPieOption(
  won: number,
  drawn: number,
  lost: number,
): EChartsOption {
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
          { name: tx("Ganados"), value: won, itemStyle: { color: "#2fbf71" } },
          {
            name: tx("Empatados"),
            value: drawn,
            itemStyle: { color: "#f5a524" },
          },
          {
            name: tx("Perdidos"),
            value: lost,
            itemStyle: { color: "#e5484d" },
          },
        ],
      },
    ],
  };
}

/**
 * Barras enfrentadas desde un eje central: lo propio crece hacia la izquierda
 * y lo del rival hacia la derecha, una fila por categoría.
 *
 * Es la forma honesta de comparar dos recuentos sobre las mismas categorías:
 * con dos barras independientes el ojo tiene que medir dos longitudes y
 * restarlas, mientras que aquí la diferencia ES el desequilibrio de la fila.
 * Los valores propios viajan negados para que ECharts los dibuje a la
 * izquierda; las etiquetas y el tooltip muestran el número real.
 */
export function facingBarsOption(
  categories: string[],
  own: number[],
  opponent: number[],
  ownLabel: string,
  opponentLabel: string,
): EChartsOption {
  const OWN = "#4f7cff";
  const RIVAL = "#e5484d";
  return {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params: unknown) => {
        const items = (Array.isArray(params) ? params : [params]) as {
          name: string;
          seriesName: string;
          value: number;
        }[];
        if (items.length === 0) return "";
        const cabecera = items[0]?.name ?? "";
        const filas = items.map(
          (p) => `${p.seriesName}: <b>${Math.abs(Number(p.value))}</b>`,
        );
        return [`<b>${cabecera}</b>`, ...filas].join("<br/>");
      },
    },
    legend: { bottom: 0, data: [ownLabel, opponentLabel] },
    grid: { left: 8, right: 8, top: 8, bottom: 32, containLabel: true },
    xAxis: {
      type: "value",
      axisLabel: { formatter: (v: number) => String(Math.abs(v)) },
      splitLine: { lineStyle: { opacity: 0.15 } },
    },
    yAxis: { type: "category", data: categories, axisTick: { show: false } },
    series: [
      {
        name: ownLabel,
        type: "bar" as const,
        stack: "ocasiones",
        data: own.map((v) => -v),
        itemStyle: { color: OWN, borderRadius: [4, 0, 0, 4] as const },
        label: {
          show: true,
          position: "left" as const,
          // El valor viaja negado para dibujarse a la izquierda; la etiqueta
          // enseña el número real.
          formatter: (p: { value: unknown }) =>
            String(Math.abs(Number(p.value))),
          fontSize: 10,
        },
      },
      {
        name: opponentLabel,
        type: "bar" as const,
        stack: "ocasiones",
        data: opponent,
        itemStyle: { color: RIVAL, borderRadius: [0, 4, 4, 0] as const },
        label: { show: true, position: "right" as const, fontSize: 10 },
      },
    ],
  };
}

/** Dona de reparto: una porción por categoría, con el conteo en la etiqueta.
 *  Misma forma que la de resultados en Partidos, pero con categorías libres
 *  (tácticas de un rival, competiciones de una muestra…). */
export function sharePieOption(
  slices: { name: string; value: number }[],
): EChartsOption {
  return {
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    legend: { bottom: 0, type: "scroll" },
    series: [
      {
        type: "pie",
        radius: ["45%", "70%"],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: "transparent", borderWidth: 2 },
        label: { formatter: "{b}\n{c}" },
        data: slices,
      },
    ],
  };
}

/** Dispersión x/y con un punto propio resaltado. Cada punto viaja como
 * [x, y, nombre], `nombre` solo se usa en el tooltip. */
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
        name: tx("Plantilla"),
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

/** Una cifra de dinero en corto, para que quepa en un eje: «332 k», «1.3 M». */
function corto(v: number): string {
  if (Math.abs(v) >= 1_000_000) return `${metric(v / 1_000_000, 1)} M`;
  if (Math.abs(v) >= 1_000) return `${Math.round(v / 1_000)} k`;
  return number(Math.round(v));
}

/**
 * La serie del precio como COLUMNAS DE PUNTOS, no como una línea sola.
 *
 * Cada lectura dibuja todas sus ventas sobre el eje de precio, y una línea
 * une las medias. La línea sola decía «520.000» y callaba que sus seis
 * ventas iban de 260.000 a 700.000, que es la mitad de lo que hay que
 * juzgar.
 *
 * POR QUÉ PUNTOS Y NO UN VIOLÍN, que fue lo que se consideró: un violín
 * dibuja una curva de densidad estimada, y con siete datos esa curva la
 * decide el suavizado y no los datos. Un punto es una venta que existió.
 * Cuando una lectura traiga veinte o treinta, el violín empezará a tener
 * sentido y la nube a estorbar.
 *
 * Relleno es venta cerrada y hueco es subasta todavía abierta: el estado
 * importa tanto como el número, porque una puja sólo puede subir.
 */
export function serieDePuntosOption(
  lecturas: {
    cuando: string;
    media: number | null;
    precios: [number, boolean, number][];
  }[],
  opciones: {
    etiqueta: (iso: string) => string;
    detalle: (v: number) => string;
    soloCerradas: boolean;
    etiquetaMedia: string;
  },
): EChartsOption {
  // LA LINEA DE TIEMPO SE DIBUJA CON VENTAS CERRADAS (2026-10-09, decision
  // del usuario). Una puja no es un precio: ese mismo dia, en la tabla de
  // Imam Ece, Edu Fuenllana figuraba con 6.000 US$ de puja y se vendio en
  // 1.241.000, un +20.583 %. Una nube con pujas dentro cuenta como «lo que
  // valen estos jugadores» algo que todavia no ha pasado.
  //
  // La excepcion, y por lectura, no para la serie entera: si una lectura NO
  // TIENE ninguna venta cerrada, se enseñan sus pujas. Esconderlas dejaria la
  // columna vacia, y una columna vacia se lee como «aquel dia no habia nada»,
  // que es distinto de «aquel dia todo estaba sin cerrar».
  type Punto = { value: [number, number]; symbolSize: number; itemStyle: { opacity: number } };
  const punto = (i: number, precio: number, peso: number): Punto => {
    const { symbolSize, opacity } = segunElParecido(peso ?? 100, 8);
    return { value: [i, precio], symbolSize, itemStyle: { opacity } };
  };
  const nube: Punto[] = [];
  const cerradas: Punto[] = [];
  const medias: (number | null)[] = [];
  lecturas.forEach((l, i) => {
    const firmes = opciones.soloCerradas
      ? l.precios.filter(([, firme]) => firme)
      : [];
    if (!opciones.soloCerradas) {
      // Con las pujas dentro se enseña todo, cada cosa con su forma, y la
      // linea es la media de todo lo que se ve.
      for (const [precio, firme, peso] of l.precios) {
        (firme ? cerradas : nube).push(punto(i, precio, peso));
      }
      medias.push(
        l.precios.length
          ? l.precios.reduce((s, [precio]) => s + precio, 0) / l.precios.length
          : null,
      );
      return;
    }
    if (firmes.length > 0) {
      for (const [precio, , peso] of firmes) cerradas.push(punto(i, precio, peso));
      // LA LINEA ES LA MEDIA DE LO QUE SE VE (2026-10-09, decision del
      // usuario). Antes era la media ponderada del panel --la cifra grande de
      // arriba-- y al quitar las pujas de los puntos dejaba de describir el
      // dibujo: en la ultima lectura de Imam Ece los tres puntos estaban en
      // 595.000, 792.000 y 1.241.000 y la linea pasaba por 436.144, por debajo
      // de los tres. Una media por debajo de todos los puntos se lee como un
      // error aunque sea correcta.
      medias.push(firmes.reduce((s, [precio]) => s + precio, 0) / firmes.length);
      return;
    }
    for (const [precio, , peso] of l.precios) nube.push(punto(i, precio, peso));
    // Sin ventas cerradas no hay media que dibujar: la linea se corta ahi en
    // vez de inventar un punto con pujas, que es justo lo que se quiso quitar.
    // `connectNulls: false` hace el hueco de verdad.
    medias.push(null);
  });

  return {
    grid: { left: 8, right: 14, top: 18, bottom: 28, containLabel: true },
    xAxis: {
      type: "category",
      data: lecturas.map((l) => opciones.etiqueta(l.cuando)),
      axisLabel: { fontSize: 10, hideOverlap: true },
      axisTick: { show: false },
      boundaryGap: true,
    },
    yAxis: {
      type: "value",
      axisLabel: { fontSize: 10, formatter: (v: number) => corto(v) },
      splitLine: { lineStyle: { opacity: 0.15 } },
    },
    series: [
      {
        type: "line",
        name: opciones.etiquetaMedia,
        data: medias,
        symbol: "none",
        lineStyle: { width: 2, color: LINEA_DE_LA_MEDIA },
        itemStyle: { color: LINEA_DE_LA_MEDIA },
        connectNulls: false,
        z: 1,
      },
      {
        type: "scatter",
        name: tx("Subasta abierta"),
        data: nube,
        symbolSize: 8,
        symbol: "emptyCircle",
        itemStyle: { color: SUBASTA_ABIERTA },
        z: 2,
      },
      {
        type: "scatter",
        name: tx("Venta cerrada"),
        data: cerradas,
        symbolSize: 8,
        itemStyle: { color: VENTA_CERRADA },
        z: 3,
      },
    ],
    legend: { bottom: 0, itemHeight: 8, textStyle: { fontSize: 10 } },
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const d = p as { seriesType?: string; value?: unknown; name?: string };
        if (d.seriesType === "line") {
          return `${d.name}<br/>${opciones.detalle(Number(d.value ?? 0))}`;
        }
        const par = Array.isArray(d.value) ? d.value : [0, 0];
        return opciones.detalle(Number(par[1] ?? 0));
      },
    },
  };
}

/**
 * El reparto de precios como UNA TIRA DE PUNTOS, no como barras.
 *
 * Cada punto es una venta sobre el eje de precio. Relleno es venta cerrada y
 * hueco es subasta todavía abierta.
 *
 * POR QUÉ NO UN HISTOGRAMA, que fue lo primero que se construyó: con siete
 * ventas los cubos salen de cuatro, y los tres precios bajos --1.000, 3.000 y
 * 6.000-- caían los tres en la misma barra, indistinguibles. La tira los
 * separa y además enseña dónde NO hay nada, que es la mitad de la forma.
 * El histograma vuelve a tener sentido con quince o veinte ventas.
 *
 * Los que casi coinciden se APILAN en vez de taparse: sin eso, tres ventas
 * pegadas al cero parecen una.
 */
export function tiraDePuntosOption(
  precios: [number, boolean, number][],
  opciones: {
    media: number | null;
    mediana: number | null;
    detalle: (v: number) => string;
    etiquetaMedia: string;
    etiquetaMediana: string;
  },
): EChartsOption {
  const orden = [...precios].sort((a, b) => a[0] - b[0]);
  const minimo = orden.length ? orden[0]![0] : 0;
  const maximo = orden.length ? orden[orden.length - 1]![0] : 1;
  // Dos puntos a menos de un 2,5 % del rango se pisan a este tamaño. La
  // cuenta tiene que hacerse EN EL EJE QUE SE DIBUJA: hubo un rato, el
  // 2026-10-09, en que el eje era logarítmico y esta cuenta seguía siendo
  // lineal, y entonces 1.000 y 3.000 se apilaban uno encima de otro aunque en
  // pantalla quedaran a medio dedo. Hoy el eje es lineal y coinciden; si
  // alguna vez vuelve a cambiar, esto cambia con él.
  const juntos = Math.max((maximo - minimo) * 0.025, 1);

  type Punto = { value: [number, number]; symbolSize: number; itemStyle: { opacity: number } };
  const abiertas: Punto[] = [];
  const cerradas: Punto[] = [];
  let anterior = -Infinity;
  let piso = 0;
  for (const [precio, firme, peso] of orden) {
    piso = precio - anterior <= juntos ? piso + 1 : 0;
    anterior = precio;
    const { symbolSize, opacity } = segunElParecido(peso ?? 100, 11);
    (firme ? cerradas : abiertas).push({
      value: [precio, piso],
      symbolSize,
      itemStyle: { opacity },
    });
  }
  const alto = Math.max(piso, 2);

  const marcas = [
    opciones.media != null
      ? { xAxis: opciones.media, name: opciones.etiquetaMedia }
      : null,
    opciones.mediana != null
      ? { xAxis: opciones.mediana, name: opciones.etiquetaMediana }
      : null,
  ].filter(Boolean) as { xAxis: number; name: string }[];

  return {
    grid: { left: 8, right: 16, top: 26, bottom: 28, containLabel: true },
    xAxis: {
      type: "value",
      min: minimo,
      max: maximo,
      axisLabel: { fontSize: 10, formatter: (v: number) => corto(v) },
      splitLine: { lineStyle: { opacity: 0.12 } },
    },
    yAxis: {
      type: "value",
      min: -0.6,
      max: alto + 0.6,
      show: false,
    },
    series: [
      {
        type: "scatter",
        name: tx("Subasta abierta"),
        data: abiertas,
        symbolSize: 11,
        itemStyle: { color: SUBASTA_ABIERTA },
        // Hueco de verdad: `emptyCircle` pinta el borde con el color de la
        // serie. Con `color: transparent` y sin `borderColor` el punto
        // salia INVISIBLE, y la grafica enseñaba ejes y marcas sin datos.
        symbol: "emptyCircle",
        markLine: {
          symbol: "none",
          silent: true,
          lineStyle: { type: "dashed", opacity: 0.55 },
          // `rotate: 0` porque ECharts gira la etiqueta de una linea
          // VERTICAL por defecto, y «media» salia escrito de arriba
          // abajo (2026-10-08).
          label: {
            fontSize: 10,
            formatter: "{b}",
            position: "insideEndTop",
            rotate: 0,
          },
          data: marcas,
        },
      },
      {
        type: "scatter",
        name: tx("Venta cerrada"),
        data: cerradas,
        symbolSize: 11,
        itemStyle: { color: VENTA_CERRADA },
      },
    ],
    legend: { bottom: 0, itemHeight: 8, textStyle: { fontSize: 10 } },
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const d = p as { value?: unknown };
        const par = Array.isArray(d.value) ? d.value : [0, 0];
        return opciones.detalle(Number(par[0] ?? 0));
      },
    },
  };
}
