/**
 * Los colores de marca, en hexadecimal, para usarlos DENTRO de una gráfica.
 *
 * Las gráficas se pintan sobre canvas y canvas no sabe leer variables de CSS:
 * un `color: "var(--accent)"` ahí no falla ni avisa, se queda en el color por
 * defecto del canvas y la barra sale de un gris que no dice nada. Pasó en los
 * desgloses de ROI y en la ocupación del estadio, y las dos veces costó
 * encontrarlo porque el código se leía perfectamente bien.
 *
 * Así que fuera de una gráfica, `var(--positive)` como siempre; dentro,
 * `colores(isDark).positive`. Los valores son los mismos de index.css: si
 * cambian allí, cambian aquí.
 */
const CHART_COLORS = {
  dark: {
    accent: "#4f7cff",
    positive: "#2fbf71",
    warning: "#f5a524",
    danger: "#e5484d",
    text: "#ededef",
    muted: "#8b8b93",
    border: "#26262b",
  },
  light: {
    accent: "#3b63e0",
    positive: "#1a9e5c",
    warning: "#c98a10",
    danger: "#d1383d",
    text: "#18181b",
    muted: "#71717a",
    border: "#e4e4e7",
  },
} as const;

export type ChartColors = Record<keyof (typeof CHART_COLORS)["dark"], string>;

export function colores(isDark: boolean): ChartColors {
  return isDark ? CHART_COLORS.dark : CHART_COLORS.light;
}
