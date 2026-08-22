import { useState } from "react";
import clsx from "clsx";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import type { CustomSeriesRenderItem, EChartsOption } from "echarts";
import { Chart } from "../charts/Chart";
import { CountryCell } from "../components/CountryFlag";
import { Column, DataTable } from "../components/DataTable";
import { Empty, ErrorState, Kpi, Loading, Note, Panel } from "../components/Panels";
import { Specialty } from "../components/Specialty";
import { PlayerLink } from "../components/PlayerLink";
import { Tabs } from "../components/Tabs";
import { date, money, number, parseUtc } from "../hooks/useFormat";
import { useIsDarkTheme } from "../hooks/useTheme";
import { TEAM_ID, usePlayerBalance } from "../hooks/useTeam";
import { api, errorMessage } from "../services/api";
import type { PlayerBalanceRow } from "../services/api";

const UNKNOWN_TRAINING = "Entrenamiento desconocido";
const UNKNOWN_SEASON = "Temporada desconocida";
const UNKNOWN_AGE = "Edad desconocida";
const UNKNOWN_TOP_SKILL = "?";
/** La semana sin temporada: "05", no "83-05". Con dos dígitos para que el eje
 *  ordene y se lea igual de la 01 a la 16. */
const weekLabel = (n: number) => String(n).padStart(2, "0");
const UNKNOWN_WEEK = "sin fecha";
const UNKNOWN_BID_HOUR = "Hora desconocida";

/** El bloque de dos horas en que se cerró la puja, EN TU RELOJ.
 *
 * 2026-08-22, pedido por el usuario. El servidor agrupaba por la hora UTC, que
 * no es la de nadie: una puja cerrada a las 19:00 en Colombia caía en el bloque
 * de medianoche. `worlddetails.xml` no sirve para arreglarlo —de cada país da
 * `ZoneName`, y para Colombia vale "South America", una región, no una zona
 * horaria—, así que se resuelve como se resolvió la hora de los partidos de
 * Copa: la fecha viaja en UTC y el navegador la pone en la hora de quien mira.
 * Así cada usuario ve la suya sin configurar nada.
 */
function bidHourBucket(soldAt: string | null): string {
  if (!soldAt) return UNKNOWN_BID_HOUR;
  const cuando = parseUtc(soldAt);
  if (Number.isNaN(cuando.getTime())) return UNKNOWN_BID_HOUR;
  const inicio = Math.floor(cuando.getHours() / 2) * 2;
  const fin = (inicio + 2) % 24;
  const dosDigitos = (h: number) => String(h).padStart(2, "0");
  return `${dosDigitos(inicio)}:00 - ${dosDigitos(fin)}:00`;
}

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
  }).format(value).replace(",", ".");
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

type SectionKey =
  | "resumen"
  | "totales"
  | "desgloses"
  | "roi"
  | "intentos"
  | "detalle";

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
    yAxis: {
      type: "value",
      name: currency,
      axisLabel: { formatter: (value: number) => number(value) },
    },
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

/** Los siete entrenamientos que Hattrick deja elegir hoy, con su nombre. Los
 *  obsoletos (0 y 1) no se ofrecen: nadie los entrena ya. */
const ENTRENAMIENTOS: [number, string][] = [
  [2, "Balón parado"], [3, "Defensa"], [4, "Anotación"], [5, "Lateral"],
  [6, "Anotación y balón parado"], [7, "Pases"], [8, "Jugadas"], [9, "Portería"],
  [10, "Pases (defensas y centrocampistas)"],
  [11, "Defensa (porteros, defensas y centrocampistas)"],
  [12, "Lateral (extremos y delanteros)"],
];

const HABILIDADES: [string, string][] = [
  ["keeper", "Portería"], ["defending", "Defensa"], ["playmaking", "Jugadas"],
  ["winger", "Lateral"], ["passing", "Pases"], ["scoring", "Anotación"],
  ["set_pieces", "Balón parado"],
];

/** Atribuir a mano lo que Hattrick ya no da de un ex-jugador, o sacar esa
 *  etapa de las cuentas. Solo rellena huecos: si el dato real aparece algún
 *  día, gana el real. */
function EditarEtapa({
  fila,
  onCerrar,
  onGuardado,
}: {
  fila: PlayerBalanceRow;
  onCerrar: () => void;
  onGuardado: () => void;
}) {
  const [entrenamiento, setEntrenamiento] = useState<string>("");
  const [habilidad, setHabilidad] = useState<string>("");
  const [anios, setAnios] = useState<string>("");
  const [dias, setDias] = useState<string>("");
  const [excluida, setExcluida] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const guardar = useMutation({
    mutationFn: () =>
      api.editStint(TEAM_ID, fila.stintId as number, {
        ...(entrenamiento ? { training_type: Number(entrenamiento) } : {}),
        ...(habilidad ? { top_skill: habilidad } : {}),
        ...(anios ? { age_years: Number(anios) } : {}),
        ...(dias ? { age_days: Number(dias) } : {}),
        excluded: excluida,
      }),
    onSuccess: () => {
      onGuardado();
      onCerrar();
    },
    onError: (reason) => setError(errorMessage(reason)),
  });

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-black/50 p-4"
      role="dialog"
      aria-label={`Editar ${fila.name}`}
      onClick={onCerrar}
    >
      <div
        className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-base font-semibold">{fila.name}</h2>
        <p className="mt-1 text-xs text-[var(--muted)]">
          Salió el {date(fila.soldAt)}. Lo que escribas aquí solo rellena lo que
          está en «?»; si Hattrick devuelve el dato de verdad, manda el suyo.
        </p>

        <div className="mt-4 space-y-3 text-sm">
          <label className="block">
            <span className="text-xs text-[var(--muted)]">Entrenamiento al salir</span>
            <select
              value={entrenamiento}
              onChange={(e) => setEntrenamiento(e.target.value)}
              className="mt-1 w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5"
            >
              <option value="">Sin atribuir</option>
              {ENTRENAMIENTOS.map(([id, nombre]) => (
                <option key={id} value={id}>{nombre}</option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-xs text-[var(--muted)]">Habilidad más alta</span>
            <select
              value={habilidad}
              onChange={(e) => setHabilidad(e.target.value)}
              className="mt-1 w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5"
            >
              <option value="">Sin atribuir</option>
              {HABILIDADES.map(([clave, nombre]) => (
                <option key={clave} value={clave}>{nombre}</option>
              ))}
            </select>
          </label>

          <div className="flex gap-3">
            <label className="flex-1">
              <span className="text-xs text-[var(--muted)]">Edad (años)</span>
              <input
                type="number" min={15} max={50} value={anios}
                onChange={(e) => setAnios(e.target.value)}
                className="mt-1 w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5"
              />
            </label>
            <label className="flex-1">
              <span className="text-xs text-[var(--muted)]">Días</span>
              <input
                type="number" min={0} max={111} value={dias}
                onChange={(e) => setDias(e.target.value)}
                className="mt-1 w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5"
              />
            </label>
          </div>

          <label className="flex items-start gap-2 rounded-md border border-[var(--border)] p-3">
            <input
              type="checkbox" checked={excluida}
              onChange={(e) => setExcluida(e.target.checked)}
              className="mt-0.5"
            />
            <span className="text-xs">
              <b>Sacar de los cálculos.</b> Esta etapa deja de contar en los totales,
              los desgloses y el ROI. Sigue estando en Hattrick; solo desaparece de
              estas cuentas.
            </span>
          </label>

          {error && <p className="text-xs text-[var(--warning)]">{error}</p>}
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <button
            onClick={onCerrar}
            className="rounded-md border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--muted)]"
          >
            Cancelar
          </button>
          <button
            onClick={() => guardar.mutate()}
            disabled={guardar.isPending}
            className="rounded-md bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60"
          >
            {guardar.isPending ? "Guardando…" : "Guardar"}
          </button>
        </div>
      </div>
    </div>
  );
}

export function PlayerBalancePage() {
  const { data, isLoading, isError, error } = usePlayerBalance();
  const navigate = useNavigate();
  const isDark = useIsDarkTheme();
  const [section, setSection] = useState<SectionKey>("resumen");
  const [seasonFilter, setSeasonFilter] = useState<string>("all");
  const [dotSort, setDotSort] = useState<DotSortKey>("date");
  // Solo para el contador de la pestaña; react-query comparte la respuesta
  // con la sección, así que no cuesta una segunda petición.
  const intentos = useQuery({
    queryKey: ["transfer-attempts", TEAM_ID],
    queryFn: () => api.transferAttempts(TEAM_ID),
  });
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
  // Semana de temporada (1-16), sin la temporada delante: una venta de 83-05
  // y otra de 81-05 caen en la misma columna. La pregunta es en qué semana
  // del calendario conviene comprar o vender, no en qué temporada.
  const bySaleWeek: Record<string, number> = {};
  const byPurchaseWeek: Record<string, number> = {};
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
    // El bloque se calcula aquí y no en el servidor: es el único sitio que
    // sabe en qué huso está quien mira la pantalla. `bidHourAtSale` sigue
    // sirviendo de señal de "hubo puja de verdad": un despido no la tiene.
    const bidHour =
      r.bidHourAtSale != null ? bidHourBucket(r.soldAt) : UNKNOWN_BID_HOUR;
    byBidHour[bidHour] = (byBidHour[bidHour] ?? 0) + r.saldo;
    const semanaVenta = r.weekAtSale != null ? weekLabel(r.weekAtSale) : UNKNOWN_WEEK;
    bySaleWeek[semanaVenta] = (bySaleWeek[semanaVenta] ?? 0) + r.saldo;
    const semanaCompra =
      r.weekAtPurchase != null ? weekLabel(r.weekAtPurchase) : UNKNOWN_WEEK;
    byPurchaseWeek[semanaCompra] = (byPurchaseWeek[semanaCompra] ?? 0) + r.saldo;
  }
  const weekEntries = (bucket: Record<string, number>): [string, number][] =>
    Object.entries(bucket).sort(
      ([a], [b]) =>
        (a === UNKNOWN_WEEK ? 99 : Number(a)) - (b === UNKNOWN_WEEK ? 99 : Number(b)),
    );
  const saleWeekEntries = weekEntries(bySaleWeek);
  const purchaseWeekEntries = weekEntries(byPurchaseWeek);

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
  // ── Desgloses por ROI ──────────────────────────────────────────────────
  //
  // La metodología, pedida así: se suman PRIMERO todos los componentes de
  // cada grupo —lo invertido por un lado, el saldo por otro— y el porcentaje
  // se calcula al final, sobre esos totales. Promediar los ROI individuales
  // daría el mismo peso a un jugador de 10.000 que a uno de cinco millones.
  type Acumulado = { saldo: number; coste: number; ventas: number };
  const acumular = (
    destino: Record<string, Acumulado>,
    clave: string,
    r: PlayerBalanceRow,
  ) => {
    const actual = destino[clave] ?? { saldo: 0, coste: 0, ventas: 0 };
    actual.saldo += r.saldo ?? 0;
    actual.coste += r.totalCost;
    actual.ventas += 1;
    destino[clave] = actual;
  };

  const roiPorSemanaCompra: Record<string, Acumulado> = {};
  const roiPorEntrenamiento: Record<string, Acumulado> = {};
  const roiPorEdad: Record<string, Acumulado> = {};
  const roiPorHabilidad: Record<string, Acumulado> = {};
  const roiPorHora: Record<string, Acumulado> = {};
  for (const r of desglosesRows) {
    if (r.saldo == null || r.totalCost <= 0) continue;
    acumular(
      roiPorSemanaCompra,
      r.weekAtPurchase != null ? weekLabel(r.weekAtPurchase) : UNKNOWN_WEEK,
      r,
    );
    acumular(roiPorEntrenamiento, r.trainingAtSale ?? UNKNOWN_TRAINING, r);
    acumular(
      roiPorEdad,
      typeof r.ageAtSale === "number" ? ageBucket(Math.floor(r.ageAtSale)) : UNKNOWN_AGE,
      r,
    );
    acumular(roiPorHabilidad, r.topSkillAtSale ?? UNKNOWN_TOP_SKILL, r);
    acumular(
      roiPorHora,
      r.bidHourAtSale != null ? bidHourBucket(r.soldAt) : UNKNOWN_BID_HOUR,
      r,
    );
  }

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
  const dotChartHeight = Math.max(220, dotRowCount * 20 + 90);
  const dotPoints = dotRows.map((r, i) => ({
    name: r.name,
    htPlayerId: r.htPlayerId,
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
      r.htPlayerId,
    ] as [
      number,
      number,
      number,
      number,
      number,
      string | null,
      string,
      number,
    ],
  }));
  const openDotPlayer = (...args: unknown[]) => {
    const params = args[0] as
      | { value?: unknown; data?: { htPlayerId?: unknown } }
      | undefined;
    const htPlayerId = Number(
      params?.data?.htPlayerId ??
        (Array.isArray(params?.value) ? params.value[7] : undefined),
    );
    if (Number.isInteger(htPlayerId) && htPlayerId > 0) {
      navigate(`/players/${htPlayerId}`);
    }
  };

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Transferencias</h1>
          <p className="text-sm text-[var(--muted)]">
            Cálculo del ROI: (Venta neta − (Compra + Salario + Listados) +
            Reventa) ÷ (Compra + Salario + Listados) × 100, donde Venta neta =
            Precio de venta × (1 − % agente)
          </p>
        </div>
        {/* 2026-08-15: traer el historial de transferencias se hace desde
            Sincronización, junto al resto de cargas CHPP. */}
        <Link
          to="/sync"
          className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--muted)] hover:border-[var(--accent)] hover:text-[var(--text)]"
        >
          Actualizar transferencias en Sincronización
        </Link>
      </header>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs
          tabs={[
            { key: "resumen", label: "Resumen" },
            { key: "totales", label: "Totales" },
            { key: "desgloses", label: "Desgloses absolutos" },
            { key: "roi", label: "Desgloses ROI" },
            {
              key: "intentos",
              label: `Intentos de transferencias (${intentos.data?.rows.length ?? 0})`,
            },
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
          un solo lugar, no repetidos en Resumen/Desgloses/Detalle), los
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
                <div className="relative">
                  <Chart
                    ariaLabel="Diagrama de puntos: una bolita enlazada a la ficha de cada exjugador vendido, ordenadas según el criterio elegido, coloreadas por ROI de rojo (pérdida) a verde (ganancia), forma por origen (comprado o canterano)"
                    onEvents={{ click: openDotPlayer }}
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
                              number,
                            ]
                          | undefined;
                        if (!v) return "";
                        const [, , , roi, salePrice, soldAt, training] = v;
                        return (
                          `${p?.name ?? ""}<br/>Venta: ${money(salePrice, data.currency)}<br/>` +
                          `ROI: ${roi.toFixed(1)}%<br/>Fecha: ${date(soldAt)}<br/>Entrenamiento: ${training}<br/><b>Haz clic para abrir la ficha</b>`
                        );
                      },
                    },
                    series: [
                      {
                        type: "scatter",
                        data: dotPoints,
                        cursor: "pointer",
                        itemStyle: { opacity: 0.88 },
                      },
                    ],
                    }}
                    height={dotChartHeight}
                  />
                  <div
                    className="pointer-events-none absolute inset-x-2 bottom-12 top-2"
                    style={{
                      display: "grid",
                      gridTemplateColumns: `repeat(${DOT_COLS + 1}, minmax(0, 1fr))`,
                      gridTemplateRows: `repeat(${dotRowCount + 1}, minmax(0, 1fr))`,
                    }}
                  >
                    {dotRows.map((row, index) => (
                      <Link
                        key={`${row.htPlayerId}-${row.soldAt ?? index}`}
                        to={`/players/${row.htPlayerId}`}
                        aria-label={`Abrir ficha de ${row.name}`}
                        title={`${row.name} · Venta: ${money(row.salePrice, data.currency)} · ROI: ${row.roiPct.toFixed(1)}%`}
                        className="pointer-events-auto h-[18px] w-[18px] -translate-x-1/2 -translate-y-1/2 rounded-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[var(--accent)]"
                        style={{
                          gridColumn: (index % DOT_COLS) + 2,
                          gridRow: Math.floor(index / DOT_COLS) + 2,
                          justifySelf: "start",
                          alignSelf: "start",
                        }}
                      />
                    ))}
                  </div>
                </div>
              )}
            </Panel>
          )}
        </div>
      )}

      {section === "totales" && (
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
            value={number(data.transferNumberBuys)}
          />
          <Kpi
            label="Número de ventas"
            value={number(data.transferNumberSales)}
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
            <WaterfallPanel
              title="Saldo por semana de venta"
              meta="la semana de la temporada, sumando todas las temporadas"
              ariaLabel="Cascada del saldo neto agrupado por la semana de temporada en la que se vendió cada jugador"
              entries={saleWeekEntries}
              currency={data.currency}
              isDark={isDark}
              forceAllLabels
            />
            <WaterfallPanel
              title="Saldo por semana de compra"
              meta="la semana de la temporada, sumando todas las temporadas"
              ariaLabel="Cascada del saldo neto agrupado por la semana de temporada en la que se compró cada jugador"
              entries={purchaseWeekEntries}
              currency={data.currency}
              isDark={isDark}
              forceAllLabels
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
              meta="bloques de 2 horas, en tu hora"
              ariaLabel="Cascada del saldo neto, repartido por el bloque de 2 horas, en la hora local de quien mira, en el que se cerró cada puja de venta"
              entries={bidHourEntries}
              currency={data.currency}
              isDark={isDark}
            />
          </div>
        </div>
      )}

      {section === "roi" && (
        <div className="space-y-4">
          <Note>
            Cada grupo suma primero lo invertido y lo ganado de todas sus ventas, y
            el porcentaje sale de esos totales. No es el promedio de los ROI de
            cada jugador: así una venta de cinco millones pesa lo que debe frente a
            una de diez mil.
          </Note>
          <div className="grid gap-4 lg:grid-cols-2">
            <RoiPanel
              title="ROI por semana de compra"
              meta="semana del calendario, no de la temporada"
              entries={Object.entries(roiPorSemanaCompra).sort((a, b) =>
                a[0].localeCompare(b[0], "es", { numeric: true }),
              )}
              isDark={isDark}
            />
            <RoiPanel
              title="ROI por hora de cierre de la puja"
              meta="bloques de 2 horas, en tu hora"
              entries={Object.entries(roiPorHora).sort((a, b) =>
                a[0].localeCompare(b[0], "es", { numeric: true }),
              )}
              isDark={isDark}
            />
            <RoiPanel
              title="ROI por edad al vender"
              meta="por tramos de edad"
              entries={Object.entries(roiPorEdad).sort((a, b) =>
                a[0].localeCompare(b[0], "es", { numeric: true }),
              )}
              isDark={isDark}
            />
            <RoiPanel
              title="ROI por entrenamiento al vender"
              meta="ordenado de mejor a peor"
              entries={Object.entries(roiPorEntrenamiento).sort(
                (a, b) => b[1].saldo / b[1].coste - a[1].saldo / a[1].coste,
              )}
              horizontal
              isDark={isDark}
            />
            <RoiPanel
              title="ROI por habilidad más alta"
              meta="ordenado de mejor a peor"
              entries={Object.entries(roiPorHabilidad).sort(
                (a, b) => b[1].saldo / b[1].coste - a[1].saldo / a[1].coste,
              )}
              horizontal
              isDark={isDark}
            />
          </div>
        </div>
      )}

      {section === "intentos" && <TransferAttemptsSection />}

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
            precio de venta entre todo lo que has vendido, es una aproximación,
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
    render: (r) => {
      const value = accessor(r);
      return (
        <span className="tabular-nums">
          {value === "?" ? "?" : number(value)}
        </span>
      );
    },
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
        return <span className="tabular-nums">{number(entry)}</span>;
      const delta = exit - entry;
      const deltaLabel = `${delta > 0 ? "+" : ""}${number(delta)}`;
      const deltaClass =
        delta > 0 ? "text-[var(--positive)]" : "text-[var(--danger)]";
      return (
        <span className="tabular-nums">
          {number(entry)} <span className={deltaClass}>({deltaLabel})</span>
        </span>
      );
    },
  };
}


/** Barras de ROI por grupo, con la línea de cero a la vista.
 *
 * Un grupo con dos ventas da un porcentaje que parece dato y es anécdota, así
 * que se dibuja apagado y el número de ventas va siempre al lado. Nada se
 * esconde: el usuario juzga.
 */
const VENTAS_PARA_FIARSE = 5;

function RoiPanel({
  title,
  meta,
  entries,
  horizontal = false,
  isDark,
}: {
  title: string;
  meta: string;
  entries: [string, { saldo: number; coste: number; ventas: number }][];
  /** Para etiquetas largas: nombres de entrenamiento y de habilidad. */
  horizontal?: boolean;
  isDark: boolean;
}) {
  if (entries.length === 0) {
    return (
      <Panel title={title} meta="sin ventas que repartir">
        <Empty>Todavía no hay ventas con estos datos.</Empty>
      </Panel>
    );
  }

  const puntos = entries.map(([clave, a]) => ({
    clave,
    roi: (a.saldo / a.coste) * 100,
    ventas: a.ventas,
  }));
  const ejeTexto = isDark ? "#8b8b93" : "#6b7280";
  const rejilla = isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.08)";

  const option: EChartsOption = {
    grid: { left: horizontal ? 180 : 48, right: 24, top: 16, bottom: 48 },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params: unknown) => {
        const lista = params as { dataIndex: number }[];
        const p = puntos[lista[0]?.dataIndex ?? 0];
        if (!p) return "";
        return `${p.clave}<br/>ROI ${p.roi.toFixed(1)}%<br/>${p.ventas} venta(s)`;
      },
    },
    xAxis: horizontal
      ? { type: "value", axisLabel: { color: ejeTexto, formatter: "{value}%" },
          splitLine: { lineStyle: { color: rejilla } } }
      : { type: "category", data: puntos.map((p) => p.clave),
          axisLabel: { color: ejeTexto, rotate: puntos.length > 8 ? 45 : 0 } },
    yAxis: horizontal
      ? { type: "category", data: puntos.map((p) => p.clave),
          axisLabel: { color: ejeTexto } }
      : { type: "value", axisLabel: { color: ejeTexto, formatter: "{value}%" },
          splitLine: { lineStyle: { color: rejilla } } },
    series: [
      {
        type: "bar",
        data: puntos.map((p) => ({
          value: horizontal ? [p.roi, p.clave] : p.roi,
          itemStyle: {
            // Apagado cuando el grupo tiene pocas ventas: el número está,
            // pero no invita a sacar conclusiones.
            opacity: p.ventas < VENTAS_PARA_FIARSE ? 0.35 : 1,
            color: p.roi >= 0 ? "var(--accent)" : "#dc2626",
          },
        })),
        // La línea de cero, visible: un ROI negativo tiene que verse cayendo.
        markLine: {
          silent: true,
          symbol: "none",
          lineStyle: { color: ejeTexto, type: "solid", width: 1 },
          data: [horizontal ? { xAxis: 0 } : { yAxis: 0 }],
          label: { show: false },
        },
      },
    ],
  };

  return (
    <Panel title={title} meta={meta}>
      <div className="p-4">
        <Chart ariaLabel={title} height={horizontal ? 320 : 260} option={option} />
        <p className="mt-2 text-xs text-[var(--muted)]">
          Los grupos con menos de {VENTAS_PARA_FIARSE} ventas salen apagados: su
          porcentaje se mueve entero con una sola operación.
        </p>
      </div>
    </Panel>
  );
}


/** Cada intento de venta, uno por fila.
 *
 * 2026-08-22, pedido por el usuario. La aplicación ya contaba cuántas veces se
 * había listado a alguien, pero no podía enseñar CADA intento con su final. Y
 * las visitas —"este jugador fue visto 8 veces mientras estaba en la lista de
 * transferibles"— son el único dato de toda la app que Hattrick no entrega por
 * CHPP: solo lo dice en el texto de la noticia, así que lo teclea el usuario.
 *
 * No hay relleno hacia atrás, por decisión suya: empieza desde el primer
 * intento que se detecte.
 */
/** Las siete, con el mismo codigo corto que usa la tabla de Jugadores. */
const SKILL_HEADERS: [string, [string, string]][] = [
  ["keeper", ["PO", "Portería"]],
  ["defending", ["DE", "Defensa"]],
  ["playmaking", ["JU", "Jugadas"]],
  ["winger", ["LA", "Lateral"]],
  ["passing", ["PA", "Pases"]],
  ["scoring", ["AN", "Anotación"]],
  ["setPieces", ["BP", "Balón parado"]],
];

function TransferAttemptsSection() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["transfer-attempts", TEAM_ID],
    queryFn: () => api.transferAttempts(TEAM_ID),
  });

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data || data.rows.length === 0) {
    return (
      <Panel title="Intentos de transferencias" meta="empieza a contar desde hoy">
        <Empty>
          Todavía no se ha detectado ningún intento de venta. El primero que
          pongas en el mercado aparecerá aquí, con su plazo y su final.
        </Empty>
      </Panel>
    );
  }

  return (
    <Panel
      title="Intentos de transferencias"
      meta={`${data.rows.length} intento(s) desde que se empezó a contar`}
    >
      <div className="overflow-x-auto">
        <table className="w-full whitespace-nowrap text-sm">
          <thead className="border-b border-[var(--border)] text-left text-xs text-[var(--muted)]">
            <tr>
              <th className="px-3 py-2">Identificador</th>
              <th className="px-3 py-2">Jugador</th>
              <th className="px-3 py-2 text-right">Intento</th>
              <th className="px-3 py-2">Cierre de la puja</th>
              <th className="px-3 py-2">Resultado</th>
              <th className="px-3 py-2 text-right">Precio pedido</th>
              <th className="px-3 py-2 text-right">Última puja</th>
              <th className="px-3 py-2 text-right">Precio de venta</th>
              <th className="px-3 py-2 text-right">% agente</th>
              <th className="px-3 py-2 text-right">Visitas</th>
              <th className="px-3 py-2">País</th>
              <th className="px-3 py-2">Especialidad</th>
              <th className="px-3 py-2">Carácter</th>
              <th className="px-3 py-2 text-right">TSI</th>
              <th className="px-3 py-2 text-right">Edad</th>
              {SKILL_HEADERS.map(([clave, corto]) => (
                <th key={clave} className="px-2 py-2 text-right" title={corto[1]}>
                  {corto[0]}
                </th>
              ))}
              <th className="px-3 py-2">Canterano</th>
              <th className="px-3 py-2">Fecha de compra</th>
              <th className="px-3 py-2 text-right">Edad de compra</th>
              <th className="px-3 py-2 text-right">Precio compra</th>
              <th className="px-3 py-2 text-right">Días desde la compra</th>
              <th className="px-3 py-2 text-right">Partidos con nosotros</th>
              <th className="px-3 py-2 text-right">Salario acumulado</th>
              <th className="px-3 py-2">Entrenamiento</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <tr key={r.key} className="border-b border-[var(--border)]">
                <td className="px-3 py-2 font-mono text-xs text-[var(--muted)]">
                  {r.key}
                </td>
                <td className="px-3 py-2">
                  {r.htPlayerId ? (
                    <Link
                      to={`/players/${r.htPlayerId}`}
                      className="text-[var(--accent)] hover:underline"
                    >
                      {r.name}
                    </Link>
                  ) : (
                    r.name
                  )}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{r.attemptNumber}</td>
                <td className="px-3 py-2 tabular-nums">
                  {r.closedAt ? date(r.closedAt) : "-"}
                </td>
                <td className="px-3 py-2">
                  {r.open ? (
                    <span className="text-[var(--muted)]">en el mercado</span>
                  ) : r.sold ? (
                    <span className="font-medium text-[var(--positive)]">Vendido</span>
                  ) : (
                    <span className="text-[var(--muted)]">Se quedó</span>
                  )}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {r.askingPrice != null ? money(r.askingPrice, data.currency) : "?"}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {r.highestBid ? money(r.highestBid, data.currency) : "-"}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {r.salePrice != null ? money(r.salePrice, data.currency) : "-"}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {r.agentPct === "?" ? "-" : `${(r.agentPct * 100).toFixed(1)}%`}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {r.timesSeen ?? "?"}
                </td>
                <td className="px-3 py-2">{r.nativeCountry}</td>
                <td className="px-3 py-2">{r.specialty}</td>
                <td className="px-3 py-2">{r.character}</td>
                <td
                  className={clsx(
                    "px-3 py-2 text-right tabular-nums",
                    r.stale && "text-[var(--muted)]",
                  )}
                  title={
                    r.stale
                      ? "La foto más cercana al cierre es de varios días antes: no la leas como exacta."
                      : undefined
                  }
                >
                  {r.tsi === "?" ? "?" : number(r.tsi)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{r.age}</td>
                {SKILL_HEADERS.map(([clave]) => (
                  <td
                    key={clave}
                    className={clsx(
                      "px-2 py-2 text-right tabular-nums",
                      r.stale && "text-[var(--muted)]",
                    )}
                  >
                    {r.skills[clave] ?? "?"}
                  </td>
                ))}
                <td className="px-3 py-2">{r.fromAcademy ? "Sí" : "No"}</td>
                <td className="px-3 py-2 tabular-nums">
                  {r.purchasedAt ? date(r.purchasedAt) : "?"}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{r.ageAtPurchase}</td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {r.purchasePrice === "?"
                    ? "?"
                    : money(r.purchasePrice, data.currency)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {r.daysSincePurchase}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{r.gamesWithUs}</td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {r.salaryToDate === "?"
                    ? "?"
                    : money(r.salaryToDate, data.currency)}
                </td>
                <td className="px-3 py-2">{r.trainingThatWeek}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function BalanceTable({
  data,
  currency,
}: {
  data: PlayerBalanceRow[];
  currency: string;
}) {
  const [editing, setEditing] = useState<number | null>(null);
  // Etapa que se está atribuyendo a mano, si alguna. Solo se abre para etapas
  // cerradas: de la plantilla de hoy los datos vienen de Hattrick.
  const [editando, setEditando] = useState<PlayerBalanceRow | null>(null);
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
      render: (r) => (
        <CountryCell code={r.nativeCountryCode} country={r.nativeCountry} compact />
      ),
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
      render: (r) => <Specialty specialty={r.specialty} />,
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
              {/* Un canterano no se compró: lo que se ve es lo que costó
                  subirlo al primer equipo. Decirlo evita leer esa cifra como
                  un fichaje que nunca hubo. */}
              {r.isAcademyGraduate && r.promotionCost > 0 && (
                <span className="text-[var(--muted)]"> (ascenso)</span>
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
          {r.agentPct != null ? `${(r.agentPct * 100).toFixed(1)}%` : "-"}
        </span>
      ),
    },
    {
      key: "editar",
      header: "",
      align: "left",
      value: () => 0,
      // Solo para etapas cerradas: de quien sigue en la plantilla los datos
      // vienen de Hattrick y no se teclean.
      render: (r) =>
        r.stintId != null && r.soldAt ? (
          <button
            onClick={(e) => {
              e.stopPropagation();
              setEditando(r);
            }}
            className="rounded border border-[var(--border)] px-2 py-0.5 text-[10px] text-[var(--muted)] hover:border-[var(--accent)]"
            title="Atribuir a mano lo que falta, o sacar esta etapa de los cálculos"
          >
            Editar
          </button>
        ) : null,
    },
    {
      key: "gamesWithUs",
      header: "Partidos con nosotros",
      align: "right",
      // Fija la comisión que nos toca si alguien lo revende. "?" mientras el
      // censo no haya pasado por él: contarlo exige leer la alineación de
      // cada partido de su etapa.
      value: (r) => (typeof r.gamesWithUs === "number" ? r.gamesWithUs : -1),
      render: (r) =>
        typeof r.gamesWithUs === "number" ? (
          <span className="tabular-nums">{r.gamesWithUs}</span>
        ) : (
          <span
            className="text-[var(--muted)]"
            title="Sin contar todavía. Se cuenta desde Sincronización › Transferencias, una sola vez por jugador."
          >
            ?
          </span>
        ),
    },
    {
      key: "salaryTotal",
      header: "Salario acum.",
      align: "right",
      value: (r) => r.salaryTotal,
      // O se conoce el salario o no se conoce; nunca se estima. Lo normal es
      // tenerlo medido semana a semana en los snapshots. Para quien entró y
      // salió entre dos sincronizaciones no hay snapshots, pero Hattrick sigue
      // reportando su salario en playerdetails.xml, así que ese dato también
      // es conocido. Sin ninguna de las dos cosas, la casilla queda en "?":
      // un 0 se leía como "no costó nada" e inflaba el saldo.
      render: (r) =>
        r.salaryKnown ? (
          <span className="tabular-nums">{money(r.salaryTotal, currency)}</span>
        ) : (
          <span
            className="text-[var(--muted)]"
            title="De este jugador no se guardó ningún salario y Hattrick tampoco lo reporta, así que su coste no se puede calcular. El saldo sale mejor de lo que fue."
          >
            ?
          </span>
        ),
    },
    {
      key: "salePrice",
      header: "Precio venta",
      align: "right",
      value: (r) => r.salePrice ?? -1,
      render: (r) => (
        <span className="tabular-nums">
          {r.salePrice != null ? money(r.salePrice, currency) : "-"}
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
          {r.saldo != null ? money(r.saldo, currency) : "-"}
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
      value: (r) => r.isSold ? r.destinationCountry : "Sin destino",
      render: (r) => r.isSold ? (
        <CountryCell code={r.destinationCountryCode} country={r.destinationCountry} compact />
      ) : (
        <span className="whitespace-nowrap text-xs text-[var(--muted)]">
          Sin destino · despedido
        </span>
      ),
    },
  ];

  return (
    <>
    <DataTable
      rows={data}
      columns={columns}
      // Por ETAPA, no por jugador: quien paso dos veces por el club tiene
      // dos filas y compartirian identificador.
      rowKey={(r) => r.stintId ?? r.htPlayerId}
      initialSort="soldAt"
      csvName="saldo-por-jugador"
      filterPlaceholder="Filtrar jugadores…"
    />
      {editando && (
        <EditarEtapa
          fila={editando}
          onCerrar={() => setEditando(null)}
          onGuardado={() => qc.invalidateQueries({ queryKey: ["player-balance"] })}
        />
      )}
    </>
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
