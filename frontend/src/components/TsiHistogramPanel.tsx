import { Chart } from "../charts/Chart";
import { Empty, Note, Panel } from "./Panels";

const OWN_COLOR = "#4f7cff";
const RIVAL_COLOR = "#e5484d";

export interface TsiHistogramData {
  grid: number[];
  ownDensity: number[];
  rivalDensity: number[];
  ownValues: number[];
  rivalValues: number[];
}

/**
 * Histograma KDE superpuesto (propia plantilla vs. otra) con los controles
 * de TSI/log, excluir arquero y once titular / plantilla completa. Compartido
 * entre la ficha de un rival puntual y la comparativa de toda la liga: es el
 * mismo motor (`tsi_kde_comparison`) mirando a un solo equipo o a varios.
 */
export function TsiHistogramPanel({
  title,
  meta = "estimación de densidad (KDE), no barras",
  rivalLabel,
  histogram: h,
  logTsi,
  onLogTsiChange,
  excludeKeeper,
  onExcludeKeeperChange,
  top11,
  onTop11Change,
  noteSuffix,
}: {
  title: string;
  meta?: string;
  rivalLabel: string;
  histogram: TsiHistogramData;
  logTsi: boolean;
  onLogTsiChange: (v: boolean) => void;
  excludeKeeper: boolean;
  onExcludeKeeperChange: (v: boolean) => void;
  top11: boolean;
  onTop11Change: (v: boolean) => void;
  noteSuffix: string;
}) {
  const maxDensity = Math.max(1e-9, ...h.ownDensity, ...h.rivalDensity);
  const rugY = -maxDensity * 0.06;

  return (
    <Panel title={title} meta={meta}>
      <div className="flex flex-wrap items-center gap-3 border-b border-[var(--border)] px-4 py-3">
        <div className="flex overflow-hidden rounded border border-[var(--border)] text-xs">
          <button
            className={`px-3 py-1 ${!logTsi ? "bg-[var(--accent)] text-white" : "bg-[var(--surface)]"}`}
            onClick={() => onLogTsiChange(false)}
          >
            TSI
          </button>
          <button
            className={`px-3 py-1 ${logTsi ? "bg-[var(--accent)] text-white" : "bg-[var(--surface)]"}`}
            onClick={() => onLogTsiChange(true)}
          >
            Log(TSI+1)
          </button>
        </div>
        <label className="flex items-center gap-2 text-xs text-[var(--muted)]">
          <input
            type="checkbox"
            checked={excludeKeeper}
            onChange={(e) => onExcludeKeeperChange(e.target.checked)}
          />
          Excluir nuestro arquero
        </label>
        <div className="flex overflow-hidden rounded border border-[var(--border)] text-xs">
          <button
            className={`px-3 py-1 ${!top11 ? "bg-[var(--accent)] text-white" : "bg-[var(--surface)]"}`}
            onClick={() => onTop11Change(false)}
          >
            Plantilla completa
          </button>
          <button
            className={`px-3 py-1 ${top11 ? "bg-[var(--accent)] text-white" : "bg-[var(--surface)]"}`}
            onClick={() => onTop11Change(true)}
          >
            Los 11 mejores
          </button>
        </div>
      </div>
      {h.ownValues.length === 0 && h.rivalValues.length === 0 ? (
        <Empty>Sin jugadores para comparar.</Empty>
      ) : (
        <Chart
          ariaLabel="Distribución de TSI, propia vs. otra, superpuestas"
          height={300}
          option={{
            legend: { data: ["Tu plantilla", rivalLabel], bottom: 0 },
            grid: { left: 48, right: 16, top: 28, bottom: 56, containLabel: true },
            xAxis: {
              type: "value",
              name: logTsi ? "log(TSI + 1)" : "TSI",
              nameLocation: "middle",
              nameGap: 28,
            },
            yAxis: { type: "value", show: false },
            tooltip: {
              trigger: "item",
              formatter: (p: unknown) => {
                const item = p as { seriesName: string; value: [number, number] };
                return `${item.seriesName}<br/>${item.value[0].toFixed(1)}`;
              },
            },
            series: [
              {
                name: "Tu plantilla",
                type: "line",
                data: h.grid.map((x, i) => [x, h.ownDensity[i]]),
                smooth: true,
                symbol: "none",
                lineStyle: { width: 2, color: OWN_COLOR },
                areaStyle: { color: OWN_COLOR, opacity: 0.32 },
                z: 2,
              },
              {
                name: rivalLabel,
                type: "line",
                data: h.grid.map((x, i) => [x, h.rivalDensity[i]]),
                smooth: true,
                symbol: "none",
                lineStyle: { width: 2, color: RIVAL_COLOR },
                areaStyle: { color: RIVAL_COLOR, opacity: 0.32 },
                z: 1,
              },
              {
                name: "Tu plantilla",
                type: "scatter",
                data: h.ownValues.map((v) => [v, rugY]),
                symbolSize: 6,
                itemStyle: { color: OWN_COLOR, opacity: 0.7 },
                tooltip: { formatter: () => "" },
                z: 3,
              },
              {
                name: rivalLabel,
                type: "scatter",
                data: h.rivalValues.map((v) => [v, rugY]),
                symbolSize: 6,
                itemStyle: { color: RIVAL_COLOR, opacity: 0.7 },
                tooltip: { formatter: () => "" },
                z: 3,
              },
            ],
          }}
        />
      )}
      <Note>
        Cada curva es una estimación de densidad (kernel gaussiano, ancho de banda de
        Silverman) sobre {h.ownValues.length} jugador(es) propios y {h.rivalValues.length}{" "}
        {noteSuffix}. Los puntos en la base son cada jugador real.
      </Note>
    </Panel>
  );
}
