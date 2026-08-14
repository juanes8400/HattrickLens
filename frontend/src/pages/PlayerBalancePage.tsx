import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { CustomSeriesRenderItem, EChartsOption } from "echarts";
import { Chart } from "../charts/Chart";
import { Column, DataTable } from "../components/DataTable";
import { ErrorState, Kpi, Loading, Note, Panel } from "../components/Panels";
import { PlayerLink } from "../components/PlayerLink";
import { Tabs } from "../components/Tabs";
import { date, money } from "../hooks/useFormat";
import { useIsDarkTheme } from "../hooks/useTheme";
import { TEAM_ID, usePlayerBalance } from "../hooks/useTeam";
import { api } from "../services/api";
import type { PlayerBalanceRow } from "../services/api";

const UNKNOWN_TRAINING = "Entrenamiento desconocido";
const UNKNOWN_SEASON = "Temporada desconocida";
const UNKNOWN_AGE = "Edad desconocida";
const UNKNOWN_TOP_SKILL = "?";
const UNKNOWN_BID_HOUR = "Hora desconocida";

// Mismos cubos que `_age_bucket` en el backend (player_balance.py) — pedido
// explícitamente 2026-08-04 en el filtro general de temporadas: al filtrar
// por temporada, los desgloses "por Entrenamiento/Edad/Habilidad/Hora" se
// recalculan aquí, en el cliente, sobre el subconjunto filtrado (mismos
// cubos, mismo criterio, nunca un número inventado).
const AGE_BUCKETS: [number, string][] = [
  [18, "17–18"],
  [21, "19–21"],
  [24, "22–24"],
  [28, "25–28"],
  [31, "29–31"],
];
const AGE_BUCKET_OVERFLOW = "32+";
const AGE_LABELS_ORDER = [
  ...AGE_BUCKETS.map(([, label]) => label),
  AGE_BUCKET_OVERFLOW,
  UNKNOWN_AGE,
];
function ageBucket(ageYears: number): string {
  for (const [max, label] of AGE_BUCKETS) {
    if (ageYears <= max) return label;
  }
  return AGE_BUCKET_OVERFLOW;
}
function ageSortKey(label: string): number {
  const i = AGE_LABELS_ORDER.indexOf(label);
  return i === -1 ? AGE_LABELS_ORDER.length : i;
}

// Orden numérico de "Temporada N" — "Temporada desconocida" siempre al final.
function seasonSortKey(label: string): [number, number] {
  if (label === UNKNOWN_SEASON) return [1, 0];
  return [0, Number(label.replace("Temporada ", "")) || 0];
}

// Mismo formato de 12 horas que `_format_hour_range` en el backend
// (player_balance.py) — necesario para poder ordenar cronológicamente los
// bloques de 2 horas que llegan como texto ("2:00 a 4:00 p.m."), ya que el
// desglose por hora se recalcula aquí, en el cliente, sobre las filas
// filtradas.
function splitHour12(hour: number): [number, string] {
  const period = hour < 12 ? "a.m." : "p.m.";
  return [hour % 12 || 12, period];
}
function formatHourRange(start: number, end: number): string {
  const [startH12, startPeriod] = splitHour12(start);
  const [endH12, endPeriod] = splitHour12(end % 24);
  if (startPeriod === endPeriod) return `${startH12}:00 a ${endH12}:00 ${endPeriod}`;
  return `${startH12}:00 ${startPeriod} a ${endH12}:00 ${endPeriod}`;
}
const BID_HOUR_LABELS_ORDER = Array.from({ length: 12 }, (_, i) =>
  formatHourRange(i * 2, i * 2 + 2),
);
function bidHourSortKey(label: string): number {
  const i = BID_HOUR_LABELS_ORDER.indexOf(label);
  return i === -1 ? BID_HOUR_LABELS_ORDER.length : i;
}

// Abrevia cifras grandes de moneda en los ejes de las gráficas ("2,4 M" en
// vez de "2400000") — pedido explícitamente 2026-08-11, se veían feas.
function compactNumber(value: number): string {
  return new Intl.NumberFormat("es-CO", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

// Rojo/gris/verde de las cascadas y el mapa de calor de ROI — deben coincidir
// EXACTAMENTE con --danger/--muted/--positive de index.css en el tema activo
// (pedido explícitamente: los colores de las gráficas se veían distintos a
// los de las etiquetas de texto — antes los gráficos usaban siempre el hex
// del tema oscuro sin importar el tema real).
const CHART_COLORS = {
  dark: { positive: "#2fbf71", danger: "#e5484d", muted: "#8b8b93" },
  light: { positive: "#1a9e5c", danger: "#d1383d", muted: "#71717a" },
};

// Icono de corazón (Material Design), viewBox 0 0 24 24 — ECharts acepta
// una ruta SVG como símbolo de un scatter vía `path://`.
const HEART_SYMBOL =
  "path://M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z";

// Diagrama de puntos — cada transferencia es una bolita, pedido
// explícitamente 2026-08-04. A diferencia del scatter (Δ TSI vs. ROI), la
// posición es un RANGO (1º, 2º, 3º...), no un valor numérico en un eje —
// así un outlier de ROI extremo no aplasta la escala de todos los demás,
// solo queda en un extremo de la fila.
type DotSortKey =
  "date" | "roi" | "value" | "tsiPurchase" | "tsiSale" | "deltaTsi" | "age";

const DOT_SORT_OPTIONS: [DotSortKey, string][] = [
  ["date", "Fecha"],
  ["roi", "ROI"],
  ["value", "Valor de la transacción"],
  ["tsiPurchase", "TSI inicial"],
  ["tsiSale", "TSI final"],
  ["deltaTsi", "Δ TSI"],
  ["age", "Edad"],
];

type DotRow = PlayerBalanceRow & { roiPct: number; salePrice: number };

function dotSortValue(r: DotRow, key: DotSortKey): number {
  switch (key) {
    case "date":
      return r.soldAt ? new Date(r.soldAt).getTime() : -Infinity;
    case "roi":
      return r.roiPct;
    case "value":
      return r.salePrice;
    case "tsiPurchase":
      return typeof r.tsiAtPurchase === "number" ? r.tsiAtPurchase : -Infinity;
    case "tsiSale":
      return typeof r.tsiAtSale === "number" ? r.tsiAtSale : -Infinity;
    case "deltaTsi":
      return typeof r.deltaTsi === "number" ? r.deltaTsi : -Infinity;
    case "age":
      return typeof r.ageAtSale === "number" ? r.ageAtSale : -Infinity;
  }
}

// Color divergente por ROI (pedido explícitamente 2026-08-04, en vez de
// edad — "es la señal de negocio que más importa, no cubierta por nada más
// en esta gráfica"). Recortado a ±300%: sin esto, dos o tres ventas con
// ROI de decenas de miles por ciento (compras muy baratas con una
// revalorización real modesta) dejarían a todas las demás en el mismo tono
// apagado — el tooltip siempre muestra el ROI real, sin recortar.
const DOT_ROI_CAP = 300;
// Suavizado con raíz cuadrada (pedido explícitamente 2026-08-05, "-sqrt()"
// para los negativos): antes de mapear a color, se aplica sqrt con signo
// al ROI ya recortado — una escala lineal deja casi todo en el gris del
// medio salvo los pocos extremos; sqrt es cóncava (crece rápido cerca de
// 0 y se aplana después), así que ventas con ROI modesto ya se ven bien
// diferenciadas en color, no solo las de ROI enorme.
function signedSqrt(x: number): number {
  return Math.sign(x) * Math.sqrt(Math.abs(x));
}
const DOT_ROI_COLOR_BOUND = Math.sqrt(DOT_ROI_CAP);
function clampRoiForColor(roiPct: number): number {
  return signedSqrt(Math.max(-DOT_ROI_CAP, Math.min(DOT_ROI_CAP, roiPct)));
}

// Icono de refresco/actualizar (Material Design), viewBox 0 0 24 24 — pedido
// explícitamente 2026-08-04 para el botón "Actualizar transferencias".
function RefreshIcon({ spinning }: { spinning: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="14"
      height="14"
      fill="currentColor"
      className={spinning ? "animate-spin" : undefined}
      aria-hidden="true"
    >
      <path d="M17.65 6.35A7.95 7.95 0 0012 4a8 8 0 108 8h-2a6 6 0 11-1.76-4.24L13 11h7V4l-2.35 2.35z" />
    </svg>
  );
}

type SectionKey = "resumen" | "desgloses" | "detalle";

// Interruptor coqueto reutilizado por los 2 toggles compartidos (pedido
// explícitamente 2026-08-04/05) — antes duplicado inline en cada sección.
function ToggleSwitch({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={onChange}
      className="flex items-center gap-2 text-xs text-[var(--muted)]"
    >
      {label}
      <span
        className={
          "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors " +
          (checked
            ? "bg-[var(--accent)]"
            : "bg-[var(--surface-2)] border border-[var(--border)]")
        }
      >
        <span
          className={
            "inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform " +
            (checked ? "translate-x-[18px]" : "translate-x-1")
          }
        />
      </span>
    </button>
  );
}

/**
 * Cascada (waterfall): cada categoría flota desde el total acumulado hasta
 * ahora, verde si suma y rojo si resta, terminando en un "Subtotal" gris que
 * cierra en el total real — mismo total en las cuatro cascadas de esta
 * pantalla, solo repartido de una forma distinta cada vez. Un gauge/tanque
 * no sirve aquí: representa un solo ratio contra un límite, no una
 * comparación de varias categorías con signo.
 */
type WaterfallDatum = [
  category: number,
  start: number,
  end: number,
  value: number,
];

function waterfallBarRenderer(color: string): CustomSeriesRenderItem {
  return (_params, api) => {
    const category = Number(api.value(0));
    const start = Number(api.value(1));
    const end = Number(api.value(2));
    const startPoint = api.coord([category, start]);
    const endPoint = api.coord([category, end]);
    const categorySize = api.size?.([1, 0]);
    const categoryWidth = Array.isArray(categorySize)
      ? (categorySize[0] ?? 40)
      : 40;
    const startX = startPoint[0] ?? 0;
    const startY = startPoint[1] ?? 0;
    const endY = endPoint[1] ?? 0;
    const width = Math.max(4, categoryWidth * 0.58);
    const height = Math.max(1, Math.abs(startY - endY));

    return {
      type: "rect",
      shape: {
        x: startX - width / 2,
        y: Math.min(startY, endY),
        width,
        height,
      },
      style: { fill: color },
      emphasis: { style: { opacity: 0.82 } },
      transition: ["shape"],
    };
  };
}

function buildWaterfallOption(
  entries: [string, number][],
  currency: string,
  isDark: boolean,
  forceAllLabels = false,
): EChartsOption {
  const colors = CHART_COLORS[isDark ? "dark" : "light"];
  const labels: string[] = [];
  const gains: WaterfallDatum[] = [];
  const losses: WaterfallDatum[] = [];
  const subtotals: WaterfallDatum[] = [];

  let running = 0;
  for (const [label, value] of entries) {
    const category = labels.length;
    const next = running + value;
    labels.push(label);
    if (value >= 0) {
      gains.push([category, running, next, value]);
    } else {
      losses.push([category, running, next, value]);
    }
    running = next;
  }
  labels.push("Subtotal");
  subtotals.push([labels.length - 1, 0, running, running]);

  return {
    // Pedido explícitamente 2026-08-04: ningún eje de las cascadas va en
    // diagonal, aunque las etiquetas sean largas ("Temporada 83", "2:00 a
    // 4:00 p.m."). `forceAllLabels` fuerza `interval: 0` SOLO donde hace
    // falta (pocas categorías fijas, como "De la compra a la venta" — ahí
    // ECharts se comía "Sueldos" al decidir que no cabía); con muchas
    // categorías (temporadas, horas) `interval: 0` las amontona ilegibles,
    // así que esas dejan el auto-hide de ECharts tal cual.
    xAxis: {
      type: "category", data: labels,
      axisLabel: { rotate: 0, interval: forceAllLabels ? 0 : "auto", fontSize: 11 },
    },
    yAxis: { type: "value", name: currency },
    legend: { data: ["Ganancia", "Pérdida", "Subtotal"], bottom: 0 },
    tooltip: {
      trigger: "axis",
      formatter: (params) => {
        const p = Array.isArray(params) ? params[0] : params;
        const values = p?.value as WaterfallDatum | undefined;
        const category = values?.[0] ?? 0;
        const value = values?.[3] ?? 0;
        return `${labels[category] ?? ""}<br/>${money(value, currency)}`;
      },
    },
    series: [
      {
        name: "Ganancia",
        type: "custom",
        // Un series `custom` dibuja sus barras a mano en `renderItem`, así
        // que ECharts no tiene de dónde sacar el color del ícono de la
        // leyenda — sin `itemStyle.color` aquí, cae al azul/verde/naranja
        // de su paleta por defecto, distinto del rojo/verde/gris real de
        // las barras (justo el bug reportado: "los colores están
        // diferentes a los de los labels").
        itemStyle: { color: colors.positive },
        renderItem: waterfallBarRenderer(colors.positive),
        data: gains,
      },
      {
        name: "Pérdida",
        type: "custom",
        itemStyle: { color: colors.danger },
        renderItem: waterfallBarRenderer(colors.danger),
        data: losses,
      },
      {
        name: "Subtotal",
        type: "custom",
        itemStyle: { color: colors.muted },
        renderItem: waterfallBarRenderer(colors.muted),
        data: subtotals,
      },
    ],
  };
}

function WaterfallPanel({
  title,
  meta,
  ariaLabel,
  entries,
  currency,
  isDark,
  forceAllLabels = false,
}: {
  title: string;
  meta: string;
  ariaLabel: string;
  entries: [string, number][];
  currency: string;
  isDark: boolean;
  forceAllLabels?: boolean;
}) {
  if (entries.length === 0) return null;
  return (
    <Panel title={title} meta={meta}>
      <Chart
        ariaLabel={ariaLabel}
        option={buildWaterfallOption(entries, currency, isDark, forceAllLabels)}
        height={280}
      />
    </Panel>
  );
}

/**
 * Barras horizontales — mismo lenguaje visual que la cascada (verde/rojo por
 * signo, mismo tooltip, mismo eje de moneda) pero sin el efecto de flotar
 * desde un acumulado: para "Entrenamiento" y "Habilidad más alta" el orden
 * de las categorías no tiene un antes/después real, así que apilarlas en
 * cascada sugería una secuencia que no existe. Pedido explícitamente.
 */
function buildHorizontalBarOption(
  entries: [string, number][],
  currency: string,
  isDark: boolean,
): EChartsOption {
  const colors = CHART_COLORS[isDark ? "dark" : "light"];
  const sorted = [...entries].sort((a, b) => a[1] - b[1]);
  const labels = sorted.map(([label]) => label);
  const values = sorted.map(([, value]) => value);
  return {
    xAxis: {
      type: "value", name: currency,
      axisLabel: { formatter: (value: number) => compactNumber(value) },
    },
    yAxis: { type: "category", data: labels, axisLabel: { fontSize: 11 } },
    grid: { left: 140, right: 24, top: 12, bottom: 24 },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params) => {
        const p = Array.isArray(params) ? params[0] : params;
        const idx = p?.dataIndex ?? 0;
        return `${labels[idx] ?? ""}<br/>${money(values[idx] ?? 0, currency)}`;
      },
    },
    series: [
      {
        type: "bar",
        data: values,
        itemStyle: {
          color: (params) =>
            (params.value as number) >= 0 ? colors.positive : colors.danger,
        },
      },
    ],
  };
}

function HorizontalBarPanel({
  title,
  meta,
  ariaLabel,
  entries,
  currency,
  isDark,
}: {
  title: string;
  meta: string;
  ariaLabel: string;
  entries: [string, number][];
  currency: string;
  isDark: boolean;
}) {
  if (entries.length === 0) return null;
  return (
    <Panel title={title} meta={meta}>
      <Chart
        ariaLabel={ariaLabel}
        option={buildHorizontalBarOption(entries, currency, isDark)}
        height={Math.max(180, entries.length * 34 + 60)}
      />
    </Panel>
  );
}

/**
 * Saldo neto por jugador. HL-161.
 *
 * Precio de compra + salario acumulado semana a semana + coste de cada
 * intento de venta, contra el precio real de venta menos la comisión del
 * agente — más la parte que le toca de cualquier reventa futura de origen
 * desconocido. Nunca se usa una valoración de mercado hipotética para un
 * jugador que sigue sin venderse: para eso está la pestaña de Transferencias.
 */
export function PlayerBalancePage() {
  const { data, isLoading, isError, error } = usePlayerBalance();
  const qc = useQueryClient();
  const isDark = useIsDarkTheme();
  const [section, setSection] = useState<SectionKey>("resumen");
  const [seasonFilter, setSeasonFilter] = useState<string>("all");
  const [dotSort, setDotSort] = useState<DotSortKey>("date");
  // Filtros compartidos (pedido explícitamente 2026-08-05: los mismos 4
  // controles — Entrenamiento, Origen, Ignorar entrenamiento desconocido,
  // Ignorar despedidos — en un solo lugar, afectando Resumen, Desgloses y
  // Detalle a la vez, en vez de repetidos/independientes por sección).
  const [trainingFilter, setTrainingFilter] = useState<string>("all");
  const [originFilter, setOriginFilter] = useState<
    "all" | "bought" | "academy"
  >("all");
  const [ignoreUnknownData, setIgnoreUnknownData] = useState(false);
  const [ignoreFired, setIgnoreFired] = useState(false);
  const syncTransfers = useMutation({
    mutationFn: () => api.syncTransfersHistory(TEAM_ID),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["player-balance", TEAM_ID] }),
  });

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return null;

  const soldRows = data.players.filter((r) => r.isSold);
  // Filtro general de temporadas (pedido explícitamente 2026-08-04):
  // "Todas" no toca nada; una temporada real recorta Detalle, el scatter y
  // los desgloses no-temporada a las ventas cerradas esa temporada — mismo
  // criterio que ya usa cada fila (`seasonAtSale`), nunca un cálculo nuevo.
  // "Todas" siempre primero (opción fija, fuera de esta lista) y luego de
  // la temporada más reciente a la más antigua — pedido explícitamente
  // 2026-08-08; "Temporada desconocida" se queda al final igual que antes.
  const seasonOptions = Array.from(
    new Set(soldRows.map((r) => r.seasonAtSale ?? UNKNOWN_SEASON)),
  ).sort((a, b) => {
    const [ka, na] = seasonSortKey(a);
    const [kb, nb] = seasonSortKey(b);
    return ka - kb || nb - na;
  });
  const soldRowsInSeason =
    seasonFilter === "all"
      ? soldRows
      : soldRows.filter(
          (r) => (r.seasonAtSale ?? UNKNOWN_SEASON) === seasonFilter,
        );

  // Filtros compartidos (pedido explícitamente 2026-08-05, confirmado: un
  // solo lugar, no repetidos por sección) — Resumen, Desgloses y Detalle
  // parten TODOS del mismo subconjunto filtrado, para que una fila
  // descartada aquí desaparezca de las tres a la vez.
  const trainingOptions = Array.from(
    new Set(soldRowsInSeason.map((r) => r.trainingAtSale ?? UNKNOWN_TRAINING)),
  ).sort();
  let filteredRows = soldRowsInSeason;
  if (trainingFilter !== "all") {
    filteredRows = filteredRows.filter(
      (r) => (r.trainingAtSale ?? UNKNOWN_TRAINING) === trainingFilter,
    );
  }
  if (ignoreUnknownData) {
    // "etc." = cualquier dimensión usada en los desgloses de Desgloses, no
    // solo entrenamiento — pedido explícitamente al renombrar el toggle.
    filteredRows = filteredRows.filter(
      (r) =>
        r.trainingAtSale != null &&
        typeof r.ageAtSale === "number" &&
        r.topSkillAtSale != null &&
        r.bidHourAtSale != null,
    );
  }
  if (originFilter === "bought")
    filteredRows = filteredRows.filter((r) => !r.isAcademyGraduate);
  if (originFilter === "academy")
    filteredRows = filteredRows.filter((r) => r.isAcademyGraduate);
  if (ignoreFired)
    filteredRows = filteredRows.filter((r) => !r.isDepartureWithoutSale);

  // Detalle: pedido explícitamente 2026-08-05, solo vendidos o despedidos
  // ("Compras (solo vendidos)") — nunca jugadores que siguen en la
  // plantilla, con o sin filtro de temporada.
  const detalleRows = filteredRows;

  // Los 5 desgloses se calculan siempre aquí, en el cliente, sobre las
  // filas ya filtradas — nunca desde data.bySeason/data.byTrainingType/etc
  // (agregados del backend, cada uno calculado por separado sobre TODAS
  // las ventas).
  const desglosesRows = filteredRows;
  const bySeason: Record<string, number> = {};
  const byTraining: Record<string, number> = {};
  const byAge: Record<string, number> = {};
  const byTopSkill: Record<string, number> = {};
  const byBidHour: Record<string, number> = {};
  for (const r of desglosesRows) {
    if (r.saldo == null) continue;
    const season = r.seasonAtSale ?? UNKNOWN_SEASON;
    bySeason[season] = (bySeason[season] ?? 0) + r.saldo;
    const training = r.trainingAtSale ?? UNKNOWN_TRAINING;
    byTraining[training] = (byTraining[training] ?? 0) + r.saldo;
    const age =
      typeof r.ageAtSale === "number"
        ? ageBucket(Math.floor(r.ageAtSale))
        : UNKNOWN_AGE;
    byAge[age] = (byAge[age] ?? 0) + r.saldo;
    const skill = r.topSkillAtSale ?? UNKNOWN_TOP_SKILL;
    byTopSkill[skill] = (byTopSkill[skill] ?? 0) + r.saldo;
    const bidHour = r.bidHourAtSale ?? UNKNOWN_BID_HOUR;
    byBidHour[bidHour] = (byBidHour[bidHour] ?? 0) + r.saldo;
  }
  const seasonEntries = Object.entries(bySeason).sort(
    (a, b) =>
      seasonSortKey(a[0])[0] - seasonSortKey(b[0])[0] ||
      seasonSortKey(a[0])[1] - seasonSortKey(b[0])[1],
  );
  const trainingEntries = Object.entries(byTraining).sort(
    (a, b) => b[1] - a[1],
  );
  const ageEntries = Object.entries(byAge).sort(
    (a, b) => ageSortKey(a[0]) - ageSortKey(b[0]),
  );
  const topSkillEntries = Object.entries(byTopSkill).sort(
    (a, b) => b[1] - a[1],
  );
  const bidHourEntries = Object.entries(byBidHour).sort(
    (a, b) => bidHourSortKey(a[0]) - bidHourSortKey(b[0]),
  );

  // Cascada del ciclo financiero de las operaciones cerradas. Solo entran
  // filas cuyo saldo es calculable y cuya venta/comisión están disponibles:
  // un precio de compra desconocido nunca se trata como cero. La venta se
  // muestra bruta y la comisión como un paso negativo separado, tal como se
  // cobra realmente. La reventa estimada queda fuera de esta cascada porque
  // no pertenece a ninguno de los cinco movimientos solicitados.
  const financialFlowRows = filteredRows.filter(
    (r) =>
      r.saldo !== null && r.salePrice !== null && r.commissionAmount !== "?",
  );
  const financialFlowEntries: [string, number][] =
    financialFlowRows.length > 0
      ? [
          [
            "Compra",
            -financialFlowRows.reduce(
              (total, r) => total + (r.purchasePrice ?? 0),
              0,
            ),
          ],
          [
            "Sueldos",
            -financialFlowRows.reduce((total, r) => total + r.salaryTotal, 0),
          ],
          [
            "Intentos de venta",
            -financialFlowRows.reduce((total, r) => total + r.listingCost, 0),
          ],
          [
            "Venta",
            financialFlowRows.reduce(
              (total, r) => total + (r.salePrice ?? 0),
              0,
            ),
          ],
          [
            "Comisiones",
            -financialFlowRows.reduce(
              (total, r) =>
                total + (r.commissionAmount === "?" ? 0 : r.commissionAmount),
              0,
            ),
          ],
        ]
      : [];
  // Diagrama de puntos: una bolita por transferencia (pedido explícitamente
  // 2026-08-04) — parte de las mismas filas ya filtradas arriba, solo
  // añade el requisito propio del gráfico (ROI/precio numéricos).
  const dotBase = filteredRows.filter(
    (r): r is DotRow =>
      typeof r.roiPct === "number" && typeof r.salePrice === "number",
  );
  const dotRows = [...dotBase].sort(
    (a, b) => dotSortValue(b, dotSort) - dotSortValue(a, dotSort),
  );
  const DOT_COLS = 26;
  const dotRowCount = Math.max(1, Math.ceil(dotRows.length / DOT_COLS));
  const dotPoints = dotRows.map((r, i) => ({
    name: r.name,
    symbol: r.isAcademyGraduate ? HEART_SYMBOL : "circle",
    symbolSize: r.isAcademyGraduate ? 15 : 13,
    value: [
      i % DOT_COLS,
      -Math.floor(i / DOT_COLS),
      clampRoiForColor(r.roiPct),
      r.roiPct,
      r.salePrice,
      r.soldAt,
      r.trainingAtSale ?? UNKNOWN_TRAINING,
    ] as [number, number, number, number, number, string | null, string],
  }));

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Saldo neto por jugador</h1>
          <p className="text-sm text-[var(--muted)]">
            Cálculo del ROI: (Venta neta − (Compra + Salario + Listados) +
            Reventa) ÷ (Compra + Salario + Listados) × 100, donde Venta neta =
            Precio de venta × (1 − % agente)
          </p>
        </div>
        <button
          onClick={() => syncTransfers.mutate()}
          disabled={syncTransfers.isPending}
          className="flex items-center gap-1.5 rounded-md border border-[var(--border)] px-3 py-1.5 text-sm hover:bg-[var(--surface-2)] disabled:opacity-50"
        >
          <RefreshIcon spinning={syncTransfers.isPending} />
          {syncTransfers.isPending
            ? "Actualizando…"
            : "Actualizar transferencias"}
        </button>
      </header>

      {syncTransfers.isSuccess && (
        <Note>
          {syncTransfers.data.transfersNew} transferencia(s) nueva(s) de{" "}
          {syncTransfers.data.transfersSeen} vista(s), en{" "}
          {syncTransfers.data.pagesFetched} página(s).
          {syncTransfers.data.errors.length > 0 &&
            ` ${syncTransfers.data.errors.length} error(es).`}
        </Note>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs
          tabs={[
            { key: "resumen", label: "Resumen" },
            { key: "desgloses", label: "Desgloses" },
            { key: "detalle", label: `Detalle (${detalleRows.length})` },
          ]}
          active={section}
          onChange={setSection}
        />
        {seasonOptions.length > 0 && (
          <div className="flex items-center gap-2">
            <label
              htmlFor="season-filter"
              className="text-xs text-[var(--muted)]"
            >
              Temporada
            </label>
            <select
              id="season-filter"
              value={seasonFilter}
              onChange={(e) => setSeasonFilter(e.target.value)}
              className="rounded border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-xs"
            >
              <option value="all">Todas</option>
              {seasonOptions.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Filtros compartidos (pedido explícitamente 2026-08-05, confirmado:
          un solo lugar, no repetidos en Resumen/Desgloses/Detalle) — los
          mismos 4 controles afectan a las tres secciones a la vez. */}
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-2">
        <label className="flex items-center gap-1.5 text-xs text-[var(--muted)]">
          Entrenamiento
          <select
            value={trainingFilter}
            onChange={(e) => setTrainingFilter(e.target.value)}
            className="rounded border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-xs text-[var(--text)]"
          >
            <option value="all">Todos</option>
            {trainingOptions.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-1.5 text-xs text-[var(--muted)]">
          Origen
          <select
            value={originFilter}
            onChange={(e) =>
              setOriginFilter(e.target.value as "all" | "bought" | "academy")
            }
            className="rounded border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-xs text-[var(--text)]"
          >
            <option value="all">Todos</option>
            <option value="bought">Comprado</option>
            <option value="academy">Canterano</option>
          </select>
        </label>
        <ToggleSwitch
          checked={ignoreUnknownData}
          onChange={() => setIgnoreUnknownData((v) => !v)}
          label="Ignorar datos desconocidos (entrenamiento, edad, etc.)"
        />
        <ToggleSwitch
          checked={ignoreFired}
          onChange={() => setIgnoreFired((v) => !v)}
          label="Ignorar jugadores despedidos"
        />
      </div>

      {section === "resumen" && (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <Kpi
              label="Total de compras"
              value={money(data.transferTotalBuys, data.currency)}
            />
            <Kpi
              label="Total de ventas"
              value={money(data.transferTotalSales, data.currency)}
            />
            <Kpi
              label="Número de compras"
              value={String(data.transferNumberBuys)}
            />
            <Kpi
              label="Número de ventas"
              value={String(data.transferNumberSales)}
            />
            <Kpi
              label="Diferencia"
              value={money(
                data.transferTotalSales - data.transferTotalBuys,
                data.currency,
              )}
              tone={
                data.transferTotalSales - data.transferTotalBuys >= 0
                  ? "positive"
                  : "danger"
              }
            />
          </div>

          {dotBase.length > 0 && (
            <Panel
              title="Cada transferencia"
              meta="color = ROI (rojo = pérdida, verde = ganancia) · ● comprado · ♥ canterano"
            >
              <div className="flex flex-wrap items-center gap-3 border-b border-[var(--border)] px-4 py-2">
                <label className="flex items-center gap-1.5 text-xs text-[var(--muted)]">
                  Ordenar por
                  <select
                    value={dotSort}
                    onChange={(e) => setDotSort(e.target.value as DotSortKey)}
                    className="rounded border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-xs text-[var(--text)]"
                  >
                    {DOT_SORT_OPTIONS.map(([key, label]) => (
                      <option key={key} value={key}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              {dotRows.length === 0 ? (
                <p className="px-4 py-6 text-center text-sm text-[var(--muted)]">
                  Ningún jugador vendido coincide con estos filtros.
                </p>
              ) : (
                <Chart
                  ariaLabel="Diagrama de puntos: una bolita por transferencia vendida, ordenadas según el criterio elegido, coloreadas por ROI de rojo (pérdida) a verde (ganancia), forma por origen (comprado o canterano)"
                  option={{
                    grid: {
                      left: 8,
                      right: 8,
                      top: 8,
                      bottom: 48,
                      containLabel: false,
                    },
                    xAxis: {
                      type: "value",
                      min: -1,
                      max: DOT_COLS,
                      show: false,
                    },
                    yAxis: {
                      type: "value",
                      min: -dotRowCount,
                      max: 1,
                      show: false,
                    },
                    visualMap: {
                      type: "continuous",
                      dimension: 2,
                      min: -DOT_ROI_COLOR_BOUND,
                      max: DOT_ROI_COLOR_BOUND,
                      inRange: {
                        color: isDark
                          ? [CHART_COLORS.dark.danger, CHART_COLORS.dark.muted, CHART_COLORS.dark.positive]
                          : [CHART_COLORS.light.danger, CHART_COLORS.light.muted, CHART_COLORS.light.positive],
                      },
                      text: ["Ganancia", "Pérdida"],
                      textStyle: { color: isDark ? "#ededef" : "#18181b" },
                      orient: "horizontal",
                      left: "center",
                      bottom: 4,
                      itemWidth: 12,
                      itemHeight: 100,
                      calculable: false,
                    },
                    tooltip: {
                      trigger: "item",
                      formatter: (params) => {
                        const p = Array.isArray(params) ? params[0] : params;
                        const v = p?.value as
                          | [
                              number,
                              number,
                              number,
                              number,
                              number,
                              string | null,
                              string,
                            ]
                          | undefined;
                        if (!v) return "";
                        const [, , , roi, salePrice, soldAt, training] = v;
                        return (
                          `${p?.name ?? ""}<br/>Venta: ${money(salePrice, data.currency)}<br/>` +
                          `ROI: ${roi.toFixed(1)}%<br/>Fecha: ${date(soldAt)}<br/>Entrenamiento: ${training}`
                        );
                      },
                    },
                    series: [
                      {
                        type: "scatter",
                        data: dotPoints,
                        itemStyle: { opacity: 0.88 },
                      },
                    ],
                  }}
                  height={Math.max(220, dotRowCount * 20 + 90)}
                />
              )}
            </Panel>
          )}
        </div>
      )}

      {section === "desgloses" && (
        <div className="space-y-3">
          <WaterfallPanel
            title="De la compra a la venta"
            meta={`${financialFlowRows.length} operaciones cerradas con datos completos · subtotal sin reventa estimada`}
            ariaLabel="Cascada del ciclo financiero: gasto de compra, sueldos e intentos de venta como valores negativos; venta como valor positivo; y comisiones como valor negativo"
            entries={financialFlowEntries}
            currency={data.currency}
            isDark={isDark}
            forceAllLabels
          />
          <div className="grid gap-4 lg:grid-cols-2">
            <WaterfallPanel
              title="Saldo por temporada"
              meta="temporada en la que se cerró cada venta"
              ariaLabel="Cascada del saldo neto, repartido por la temporada de Hattrick en la que se vendió cada jugador"
              entries={seasonEntries}
              currency={data.currency}
              isDark={isDark}
            />
            <HorizontalBarPanel
              title="Saldo por entrenamiento en el momento de la venta"
              meta="ventas cerradas"
              ariaLabel="Barras horizontales del saldo neto, repartido por el tipo de entrenamiento activo cuando se vendió cada jugador"
              entries={trainingEntries}
              currency={data.currency}
              isDark={isDark}
            />
            <WaterfallPanel
              title="Saldo por edad en el momento de la venta"
              meta="ventas cerradas"
              ariaLabel="Cascada del saldo neto, repartido por la edad del jugador cuando se vendió"
              entries={ageEntries}
              currency={data.currency}
              isDark={isDark}
            />
            <HorizontalBarPanel
              title="Saldo por habilidad más alta"
              meta="ventas cerradas · sin contar Balón Parado"
              ariaLabel="Barras horizontales del saldo neto, repartido por la habilidad más alta del jugador cuando se vendió, sin contar Balón Parado"
              entries={topSkillEntries}
              currency={data.currency}
              isDark={isDark}
            />
            <WaterfallPanel
              title="Saldo por hora de cierre de la puja"
              meta="bloques de 2 horas (Hora Hattrick)"
              ariaLabel="Cascada del saldo neto, repartido por el bloque de 2 horas, en hora de Hattrick, en el que se cerró cada puja de venta"
              entries={bidHourEntries}
              currency={data.currency}
              isDark={isDark}
            />
          </div>
        </div>
      )}

      {section === "detalle" && (
        <Panel
          title="Detalle por jugador"
          meta={
            seasonFilter === "all"
              ? `${detalleRows.length} vendidos o despedidos`
              : `${detalleRows.length} vendidos o despedidos en ${seasonFilter}`
          }
        >
          <BalanceTable data={detalleRows} currency={data.currency} />
          <p className="border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
            "Reventa" es la parte estimada de un ingreso que Hattrick reporta
            agregado y sin decir de qué jugador viene, repartida proporcional al
            precio de venta entre todo lo que has vendido — es una aproximación,
            no un dato exacto.
          </p>
        </Panel>
      )}
    </div>
  );
}

// "Edad de compra (aa;ddd)" — pedido explícitamente en ese formato exacto
// 2026-08-05: años enteros ";" días (0-111) rellenados a 3 dígitos.
function formatAgeYD(age: number | "?"): string {
  if (age === "?") return "?";
  const years = Math.floor(age);
  const days = Math.round((age - years) * 112);
  return `${years};${String(days).padStart(3, "0")}`;
}

function intCol(
  key: string,
  header: string,
  accessor: (r: PlayerBalanceRow) => number | "?",
): Column<PlayerBalanceRow> {
  return {
    key,
    header,
    align: "right",
    value: (r) => {
      const v = accessor(r);
      return v === "?" ? -Infinity : v;
    },
    render: (r) => <span className="tabular-nums">{String(accessor(r))}</span>,
  };
}

// Habilidad "al entrar" + "al salir" fusionadas en una sola columna
// (pedido explícitamente 2026-08-05: "en vez de Pases al entrar y Pases al
// salir, lo ponemos todo en 'Pases'" — Lander Fripont: "Pases 7 (+1)", el
// (+1) en verde) — y lo mismo para TSI. Se ordena por el valor de entrada;
// el delta solo se muestra cuando AMBOS lados son conocidos (nunca se
// inventa un cambio que no se puede calcular).
function skillCol(
  key: string,
  header: string,
  entryAccessor: (r: PlayerBalanceRow) => number | "?",
  exitAccessor: (r: PlayerBalanceRow) => number | "?",
): Column<PlayerBalanceRow> {
  return {
    key,
    header,
    align: "right",
    value: (r) => {
      const entry = entryAccessor(r);
      return entry === "?" ? -Infinity : entry;
    },
    render: (r) => {
      const entry = entryAccessor(r);
      const exit = exitAccessor(r);
      if (entry === "?") return <span className="tabular-nums">?</span>;
      // Pedido explícitamente 2026-08-05: sin delta que mostrar (exit
      // desconocido, o conocido pero igual al de entrada) es solo el
      // número, nunca un "(0)" que dé a entender un cambio que no hubo.
      if (exit === "?" || exit === entry)
        return <span className="tabular-nums">{entry}</span>;
      const delta = exit - entry;
      const deltaLabel = delta > 0 ? `+${delta}` : `${delta}`;
      const deltaClass =
        delta > 0 ? "text-[var(--positive)]" : "text-[var(--danger)]";
      return (
        <span className="tabular-nums">
          {entry} <span className={deltaClass}>({deltaLabel})</span>
        </span>
      );
    },
  };
}

function BalanceTable({
  data,
  currency,
}: {
  data: PlayerBalanceRow[];
  currency: string;
}) {
  const [editing, setEditing] = useState<number | null>(null);
  const qc = useQueryClient();
  const setManual = useMutation({
    mutationFn: ({
      htPlayerId,
      price,
    }: {
      htPlayerId: number;
      price: number;
    }) => api.setManualPurchasePrice(TEAM_ID, htPlayerId, price),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["player-balance", TEAM_ID] });
      setEditing(null);
    },
  });

  // 43 columnas exactas, en este orden, pedidas explícitamente 2026-08-05
  // tras confirmar la fórmula de ROI. Cambio de opinión, mismo día: "Fecha
  // de venta" pasa a ser la primera columna y el orden por defecto (en vez
  // de "Fecha de compra").
  const columns: Column<PlayerBalanceRow>[] = [
    {
      key: "soldAt",
      header: "Fecha de venta",
      align: "right",
      value: (r) => (r.soldAt ? new Date(r.soldAt).getTime() : -Infinity),
      render: (r) => <span className="tabular-nums">{date(r.soldAt)}</span>,
    },
    {
      key: "htPlayerId",
      header: "ID",
      align: "right",
      value: (r) => r.htPlayerId,
    },
    {
      key: "name",
      header: "Jugador",
      align: "left",
      value: (r) => r.name,
      render: (r) => <PlayerLink htPlayerId={r.htPlayerId} name={r.name} />,
    },
    {
      key: "listingCount",
      header: "Intentos venta",
      align: "right",
      value: (r) => r.listingCount,
    },
    {
      key: "nativeCountry",
      header: "País origen",
      align: "left",
      value: (r) => r.nativeCountry,
    },
    {
      key: "character",
      header: "Carácter",
      align: "left",
      value: (r) => r.character,
    },
    skillCol(
      "experience",
      "Experiencia",
      (r) => r.experienceAtPurchase,
      (r) => r.experienceAtSale,
    ),
    intCol("leadershipAtPurchase", "Liderazgo", (r) => r.leadershipAtPurchase),
    skillCol(
      "form",
      "Forma",
      (r) => r.formAtPurchase,
      (r) => r.formAtSale,
    ),
    skillCol(
      "stamina",
      "Resistencia",
      (r) => r.staminaAtPurchase,
      (r) => r.staminaAtSale,
    ),
    skillCol(
      "keeper",
      "Portería",
      (r) => r.keeperAtPurchase,
      (r) => r.keeperAtSale,
    ),
    skillCol(
      "defending",
      "Defensa",
      (r) => r.defendingAtPurchase,
      (r) => r.defendingAtSale,
    ),
    skillCol(
      "playmaking",
      "Jugadas",
      (r) => r.playmakingAtPurchase,
      (r) => r.playmakingAtSale,
    ),
    skillCol(
      "winger",
      "Lateral",
      (r) => r.wingerAtPurchase,
      (r) => r.wingerAtSale,
    ),
    skillCol(
      "passing",
      "Pases",
      (r) => r.passingAtPurchase,
      (r) => r.passingAtSale,
    ),
    skillCol(
      "scoring",
      "Anotación",
      (r) => r.scoringAtPurchase,
      (r) => r.scoringAtSale,
    ),
    skillCol(
      "setPieces",
      "BP",
      (r) => r.setPiecesAtPurchase,
      (r) => r.setPiecesAtSale,
    ),
    {
      key: "specialty",
      header: "Especialidad",
      align: "left",
      value: (r) => r.specialty,
    },
    skillCol(
      "tsi",
      "TSI",
      (r) => r.tsiAtPurchase,
      (r) => r.tsiAtSale,
    ),
    {
      key: "purchasedAt",
      header: "Fecha de compra",
      align: "right",
      value: (r) =>
        r.purchasedAt ? new Date(r.purchasedAt).getTime() : -Infinity,
      render: (r) => (
        <span className="tabular-nums">{date(r.purchasedAt)}</span>
      ),
    },
    {
      key: "isAcademyGraduate",
      header: "Canterano",
      align: "left",
      value: (r) => (r.isAcademyGraduate ? "Sí" : "No"),
    },
    {
      key: "ageAtPurchase",
      header: "Edad de compra",
      align: "right",
      value: (r) => (r.ageAtPurchase === "?" ? -Infinity : r.ageAtPurchase),
      render: (r) => (
        <span className="tabular-nums">{formatAgeYD(r.ageAtPurchase)}</span>
      ),
    },
    {
      key: "purchasePrice",
      header: "Precio compra",
      align: "right",
      value: (r) => r.purchasePrice ?? -1,
      render: (r) => {
        if (r.purchasePrice != null) {
          return (
            <span className="tabular-nums">
              {money(r.purchasePrice, currency)}
              {r.isPurchasePriceManual && (
                <span className="text-[var(--muted)]"> (manual)</span>
              )}
            </span>
          );
        }
        if (editing === r.htPlayerId) {
          return (
            <ManualPriceForm
              onSave={(price) =>
                setManual.mutate({ htPlayerId: r.htPlayerId, price })
              }
              onCancel={() => setEditing(null)}
              saving={setManual.isPending}
            />
          );
        }
        return (
          <button
            className="text-xs text-[var(--accent)] underline"
            onClick={() => setEditing(r.htPlayerId)}
          >
            Escribir precio
          </button>
        );
      },
    },
    intCol(
      "daysSincePurchase",
      "Días desde la compra",
      (r) => r.daysSincePurchase,
    ),
    {
      key: "agentPct",
      header: "% agente",
      align: "right",
      value: (r) => r.agentPct ?? -1,
      render: (r) => (
        <span className="tabular-nums">
          {r.agentPct != null ? `${(r.agentPct * 100).toFixed(1)}%` : "—"}
        </span>
      ),
    },
    {
      key: "salaryTotal",
      header: "Salario acum.",
      align: "right",
      value: (r) => r.salaryTotal,
      render: (r) => (
        <span className="tabular-nums">{money(r.salaryTotal, currency)}</span>
      ),
    },
    {
      key: "salePrice",
      header: "Precio venta",
      align: "right",
      value: (r) => r.salePrice ?? -1,
      render: (r) => (
        <span className="tabular-nums">
          {r.salePrice != null ? money(r.salePrice, currency) : "—"}
          {r.isDepartureWithoutSale && (
            <span className="text-[var(--muted)]"> (despedido)</span>
          )}
        </span>
      ),
    },
    {
      key: "trainingAtSale",
      header: "Entrenamiento en venta",
      align: "left",
      value: (r) => r.trainingAtSale ?? "",
    },
    {
      key: "commissionAmount",
      header: "Comisiones",
      align: "right",
      value: (r) => (r.commissionAmount === "?" ? -1 : r.commissionAmount),
      render: (r) => (
        <span className="tabular-nums">
          {r.commissionAmount === "?"
            ? "?"
            : money(r.commissionAmount, currency)}
        </span>
      ),
    },
    {
      key: "saldo",
      header: "Ganancia",
      align: "right",
      value: (r) => r.saldo ?? 0,
      render: (r) => (
        <span
          className={
            r.saldo == null
              ? "text-[var(--muted)]"
              : r.saldo >= 0
                ? "font-medium tabular-nums text-[var(--positive)]"
                : "font-medium tabular-nums text-[var(--danger)]"
          }
        >
          {r.saldo != null ? money(r.saldo, currency) : "—"}
        </span>
      ),
    },
    {
      key: "saldoPerDeltaTsi",
      header: "Ganancia / Δ TSI",
      align: "right",
      value: (r) =>
        r.saldoPerDeltaTsi === "?" ? -Infinity : r.saldoPerDeltaTsi,
      render: (r) => (
        <span className="tabular-nums">
          {r.saldoPerDeltaTsi === "?"
            ? "?"
            : money(r.saldoPerDeltaTsi, currency)}
        </span>
      ),
    },
    {
      key: "destinationCountry",
      header: "País destino",
      align: "left",
      value: (r) => r.destinationCountry,
    },
  ];

  return (
    <DataTable
      rows={data}
      columns={columns}
      rowKey={(r) => r.htPlayerId}
      initialSort="soldAt"
      csvName="saldo-por-jugador"
      filterPlaceholder="Filtrar jugadores…"
    />
  );
}

function ManualPriceForm({
  onSave,
  onCancel,
  saving,
}: {
  onSave: (price: number) => void;
  onCancel: () => void;
  saving: boolean;
}) {
  const [value, setValue] = useState("");
  const parsed = Number(value);
  const isValid = value.trim() !== "" && Number.isFinite(parsed) && parsed >= 0;

  return (
    <div className="flex items-center justify-end gap-1">
      <input
        type="number"
        min={0}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="precio"
        className="w-24 rounded border border-[var(--border)] bg-[var(--bg)] px-1.5 py-0.5 text-right text-xs"
        autoFocus
      />
      <button
        className="rounded border border-[var(--border)] px-1.5 py-0.5 text-xs disabled:opacity-50"
        disabled={!isValid || saving}
        onClick={() => onSave(Math.round(parsed))}
      >
        Guardar
      </button>
      <button className="text-xs text-[var(--muted)]" onClick={onCancel}>
        Cancelar
      </button>
    </div>
  );
}
