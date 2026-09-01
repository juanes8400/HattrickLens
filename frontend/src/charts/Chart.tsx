import * as echarts from "echarts";
import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import { useIsDarkTheme } from "../hooks/useTheme";
import { number } from "../hooks/useFormat";

/**
 * Single ECharts wrapper. UI_GUIDELINES.md requires zoom, tooltips, PNG export
 * and theme compatibility from every chart, so those defaults live here rather
 * than being repeated at each call site.
 *
 * ECharts renders to <canvas>, which cannot resolve CSS custom properties —
 * `color: "var(--text)"` silently falls back to canvas's own default (~#333),
 * which reads as near-invisible dark-on-dark text once merged with our dark
 * theme's backgrounds. Individual chart options across the app mostly avoid
 * setting text colors at all (relying on ECharts' own defaults), so the fix
 * belongs in ONE place: two registered ECharts themes with the same literal
 * hex values as index.css's --text/--muted/--border, applied globally via
 * the `theme` prop below. A chart that explicitly sets its own color (e.g. a
 * literal hex for a positive/negative line) still wins — themes only fill in
 * what nothing else specified.
 */
/**
 * La paleta de series, UNA POR TEMA.
 *
 * Era una sola lista para los dos, y sus valores eran los del tema oscuro:
 * en modo claro el verde medía 2,38 de contraste, el ámbar 2,04 y el cian
 * 2,43, todos por debajo del mínimo de 3:1 para elementos gráficos (medido el
 * 2026-08-31). Es decir, la mitad de las series de cualquier gráfica con
 * varias líneas se leían mal en el tema por defecto.
 *
 * Los cuatro primeros son los mismos tokens de `colors.ts`; el violeta y el
 * cian son series extra y llevan su propia versión oscurecida para claro.
 */
const PALETTE_POR_TEMA: Record<"dark" | "light", string[]> = {
  dark: ["#4f7cff", "#2fbf71", "#f5a524", "#e5484d", "#8b5cf6", "#06b6d4"],
  light: ["#3b63e0", "#1a9e5c", "#bd8109", "#d1383d", "#7c4ddb", "#0e7490"],
};

const AXIS_THEME = {
  dark: { text: "#ededef", muted: "#8b8b93", line: "#26262b" },
  light: { text: "#18181b", muted: "#71717a", line: "#e4e4e7" },
} as const;

for (const [name, c] of Object.entries(AXIS_THEME)) {
  echarts.registerTheme(`ht-${name}`, {
    color: PALETTE_POR_TEMA[name as "dark" | "light"],
    backgroundColor: "transparent",
    textStyle: { color: c.text },
    title: { textStyle: { color: c.text }, subtextStyle: { color: c.muted } },
    legend: { textStyle: { color: c.text } },
    categoryAxis: {
      axisLine: { lineStyle: { color: c.line } },
      axisTick: { lineStyle: { color: c.line } },
      axisLabel: { color: c.muted },
      splitLine: { lineStyle: { color: c.line } },
    },
    valueAxis: {
      axisLine: { lineStyle: { color: c.line } },
      axisTick: { lineStyle: { color: c.line } },
      axisLabel: {
        color: c.muted,
        formatter: (value: number) => number(value),
      },
      splitLine: { lineStyle: { color: c.line } },
    },
  });
}
function baseOption(dark: boolean): EChartsOption {
  return {
    color: PALETTE_POR_TEMA[dark ? "dark" : "light"],
    textStyle: { fontFamily: "Inter, system-ui, sans-serif", fontSize: 12 },
    tooltip: { trigger: "axis", confine: true },
    grid: { left: 48, right: 16, top: 28, bottom: 32, containLabel: true },
    toolbox: {
      right: 8,
      feature: {
        saveAsImage: { title: "PNG", pixelRatio: 2 },
        dataZoom: { title: { zoom: "Zoom", back: "Reset" } },
      },
      iconStyle: {
        borderColor: dark ? AXIS_THEME.dark.muted : AXIS_THEME.light.muted,
      },
    },
    backgroundColor: "transparent",
  };
}

export function Chart({
  option,
  height = 280,
  dark,
  ariaLabel,
  onEvents,
}: {
  option: EChartsOption;
  height?: number;
  /** Overrides theme auto-detection; normally left unset. */
  dark?: boolean;
  ariaLabel: string;
  /** Event handlers passed to ECharts (for example, clickable data points). */
  onEvents?: Record<string, (...args: unknown[]) => void>;
}) {
  const isDarkTheme = useIsDarkTheme();
  const resolvedDark = dark ?? isDarkTheme;
  const merged: EChartsOption = { ...baseOption(resolvedDark), ...option };
  return (
    <div role="img" aria-label={ariaLabel}>
      <ReactECharts
        option={merged}
        theme={resolvedDark ? "ht-dark" : "ht-light"}
        style={{ height }}
        opts={{ renderer: "canvas" }}
        onEvents={onEvents}
        notMerge
      />
    </div>
  );
}
