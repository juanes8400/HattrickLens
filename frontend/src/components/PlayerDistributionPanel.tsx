import { Chart } from "../charts/Chart";
import { Empty, Note, Panel } from "./Panels";

const CURVE_COLOR = "#4f7cff";
const HIGHLIGHT_COLOR = "#e5484d";

export interface PlayerDistribution {
  grid: number[];
  density: number[];
  values: number[];
  ownValue: number;
}

/**
 * Histograma KDE de una variable sobre la plantilla, con el punto de ESTE
 * jugador resaltado — HL-15x #8. Mismo motor (`gaussian_kde`, ancho de banda
 * de Silverman) que ya usa `TsiHistogramPanel` para propio-vs-rival, pero
 * aquí es una sola distribución con un punto propio destacado en vez de dos
 * curvas superpuestas.
 */
export function PlayerDistributionPanel({
  title,
  meta = "estimación de densidad (KDE), no barras",
  xLabel,
  playerName,
  distribution: d,
  formatValue = (v: number) => v.toLocaleString("es-CO", { maximumFractionDigits: 1 }),
}: {
  title: string;
  meta?: string;
  xLabel: string;
  playerName: string;
  distribution: PlayerDistribution;
  formatValue?: (v: number) => string;
}) {
  if (d.values.length === 0) {
    return (
      <Panel title={title} meta={meta}>
        <Empty>Sin jugadores en la plantilla para comparar.</Empty>
      </Panel>
    );
  }

  const maxDensity = Math.max(1e-9, ...d.density);
  const rugY = -maxDensity * 0.06;
  const others = d.values.filter((v) => v !== d.ownValue);

  return (
    <Panel title={title} meta={meta}>
      <Chart
        ariaLabel={`Distribución de ${xLabel} de la plantilla, con ${playerName} resaltado`}
        height={260}
        option={{
          grid: { left: 48, right: 16, top: 20, bottom: 44, containLabel: true },
          xAxis: { type: "value", name: xLabel, nameLocation: "middle", nameGap: 28 },
          yAxis: { type: "value", show: false },
          tooltip: {
            trigger: "item",
            formatter: (p: unknown) => {
              const item = p as { seriesName: string; value: [number, number] };
              if (item.seriesName === playerName) {
                return `${playerName}: ${formatValue(item.value[0])}`;
              }
              return formatValue(item.value[0]);
            },
          },
          series: [
            {
              name: "Plantilla",
              type: "line",
              data: d.grid.map((x, i) => [x, d.density[i]]),
              smooth: true,
              symbol: "none",
              lineStyle: { width: 2, color: CURVE_COLOR },
              areaStyle: { color: CURVE_COLOR, opacity: 0.28 },
              z: 1,
              // HL-15x #100: franja vertical que atraviesa todo el
              // histograma en vez de un solo punto en la base — más fácil
              // de leer contra la curva completa.
              markLine: {
                symbol: "none",
                silent: true,
                animation: false,
                lineStyle: { color: HIGHLIGHT_COLOR, width: 2, type: "solid" },
                label: {
                  formatter: () => playerName,
                  position: "insideEndTop",
                  color: HIGHLIGHT_COLOR,
                  fontWeight: "bold",
                },
                data: [{ xAxis: d.ownValue }],
              },
            },
            {
              name: "Plantilla",
              type: "scatter",
              data: others.map((v) => [v, rugY]),
              symbolSize: 6,
              itemStyle: { color: CURVE_COLOR, opacity: 0.55 },
              tooltip: { formatter: () => "" },
              z: 2,
            },
          ],
        }}
      />
      <Note>
        {d.values.length} jugador(es) de la plantilla actual. {playerName} está en{" "}
        <b>{formatValue(d.ownValue)}</b> (franja vertical roja).
      </Note>
    </Panel>
  );
}
