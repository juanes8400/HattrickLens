import { useState } from "react";
import clsx from "clsx";
import { PlayerLink } from "./PlayerLink";
import { Empty, Panel } from "./Panels";
import type {
  ChangeMetricSummary,
  ClubComparisonChange,
  LastSyncChanges,
  PlayerComparisonChange,
} from "../services/api";

const CORE_METRICS = new Set([
  "tsi",
  "salary",
  "form",
  "playmaking",
  "passing",
  "stamina",
  "set_pieces",
]);

function number(value: number): string {
  return new Intl.NumberFormat("es-CO").format(value);
}

function signed(value: number | null): string {
  if (value == null) return "—";
  if (value === 0) return "0";
  return `${value > 0 ? "+" : ""}${number(value)}`;
}

function changeText(change: PlayerComparisonChange): string {
  if (change.key === "arrival") return "Nuevo jugador";
  if (change.key === "market") return change.current ? "Puesto en venta" : "Retirado del mercado";
  if (change.key === "injury") {
    if (change.current === -1) return "Recuperado";
    if (change.before === -1) return `Lesión ${change.current}`;
  }
  return `${change.abbreviation} ${String(change.before)} → ${String(change.current)} (${signed(change.delta)})`;
}

function ChangePill({ change }: { change: PlayerComparisonChange }) {
  return (
    <span
      title={change.label}
      className={clsx(
        "inline-flex rounded-md px-2 py-1 text-xs font-semibold tabular-nums",
        change.direction === "up" && "bg-[var(--positive)]/15 text-[var(--positive)]",
        change.direction === "down" && "bg-[var(--danger)]/15 text-[var(--danger)]",
        change.direction === "neutral" && "bg-[var(--accent-soft)] text-[var(--accent)]",
      )}
    >
      {changeText(change)}
    </span>
  );
}

function visibleMetrics(summary: ChangeMetricSummary[]): ChangeMetricSummary[] {
  return summary.filter(
    (metric) => CORE_METRICS.has(metric.key) || metric.upCount > 0 || metric.downCount > 0,
  );
}

function MovementCard({
  title,
  tone,
  metrics,
}: {
  title: string;
  tone: "positive" | "danger" | "neutral";
  metrics: ChangeMetricSummary[];
}) {
  return (
    <section className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg)]">
      <header
        className={clsx(
          "flex items-center justify-between border-b border-[var(--border)] px-3 py-2 text-xs font-semibold uppercase tracking-wide",
          tone === "positive" && "text-[var(--positive)]",
          tone === "danger" && "text-[var(--danger)]",
          tone === "neutral" && "text-[var(--accent)]",
        )}
      >
        <span>{title}</span>
        {tone !== "neutral" && <span>Casos · Total</span>}
      </header>
      <div className="divide-y divide-[var(--border)]">
        {metrics.map((metric) => {
          const count = tone === "positive" ? metric.upCount : metric.downCount;
          const total = tone === "positive" ? metric.upTotal : metric.downTotal;
          return (
            <div
              key={`${title}-${metric.key}`}
              className="grid grid-cols-[1fr_auto_auto] items-center gap-3 px-3 py-2 text-xs"
            >
              <span title={metric.label} className="font-semibold">
                {metric.abbreviation}
              </span>
              {tone === "neutral" ? (
                <span
                  className={clsx(
                    "col-span-2 min-w-20 text-right font-semibold tabular-nums",
                    metric.net > 0 && "text-[var(--positive)]",
                    metric.net < 0 && "text-[var(--danger)]",
                  )}
                >
                  {signed(metric.net)}
                </span>
              ) : (
                <>
                  <span className="min-w-6 text-right tabular-nums text-[var(--muted)]">{count}</span>
                  <span className="min-w-20 text-right font-semibold tabular-nums">{signed(total)}</span>
                </>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function PlayersComparison({ data }: { data: LastSyncChanges }) {
  const metrics = visibleMetrics(data.summary);
  return (
    <div className="grid gap-4 p-4 xl:grid-cols-[minmax(0,1.7fr)_minmax(22rem,1fr)]">
      <div className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--bg)]">
        {data.playerRows.length === 0 ? (
          <Empty>No hubo variaciones de jugadores en esta comparación guardada.</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="border-b border-[var(--border)] bg-[var(--surface-2)] text-xs text-[var(--muted)]">
                <tr>
                  <th className="px-3 py-2 font-medium">PlayerID</th>
                  <th className="px-3 py-2 font-medium">Jugador</th>
                  <th className="px-3 py-2 text-right font-medium">TSI</th>
                  <th className="px-3 py-2 text-right font-medium">Salario</th>
                  <th className="px-3 py-2 font-medium">Cambios</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {data.playerRows.map((row) => (
                  <tr key={row.htPlayerId} className="align-top hover:bg-[var(--surface-2)]/50">
                    <td className="px-3 py-3 font-mono text-xs text-[var(--muted)]">{row.htPlayerId}</td>
                    <td className="px-3 py-3 font-medium">
                      <PlayerLink htPlayerId={row.htPlayerId} name={row.name} />
                    </td>
                    <td className="px-3 py-3 text-right tabular-nums">
                      <div>{number(row.tsi)}</div>
                      <div
                        className={clsx(
                          "text-xs font-semibold",
                          (row.tsiDelta ?? 0) > 0 && "text-[var(--positive)]",
                          (row.tsiDelta ?? 0) < 0 && "text-[var(--danger)]",
                          (row.tsiDelta ?? 0) === 0 && "text-[var(--muted)]",
                        )}
                      >
                        {signed(row.tsiDelta)}
                      </div>
                    </td>
                    <td className="px-3 py-3 text-right tabular-nums">
                      <div>{number(row.salary)}</div>
                      <div
                        className={clsx(
                          "text-xs font-semibold",
                          (row.salaryDelta ?? 0) > 0 && "text-[var(--positive)]",
                          (row.salaryDelta ?? 0) < 0 && "text-[var(--danger)]",
                          (row.salaryDelta ?? 0) === 0 && "text-[var(--muted)]",
                        )}
                      >
                        {signed(row.salaryDelta)}
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex flex-wrap gap-1.5">
                        {row.changes.map((change) => (
                          <ChangePill key={`${row.htPlayerId}-${change.key}`} change={change} />
                        ))}
                        {row.changes.length === 0 && (
                          <span className="text-xs text-[var(--muted)]">Sólo varió TSI o salario</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
        <MovementCard title="Subidas" tone="positive" metrics={metrics} />
        <MovementCard title="Bajadas" tone="danger" metrics={metrics} />
        <MovementCard title="Balance neto" tone="neutral" metrics={metrics} />
      </div>
    </div>
  );
}

function ClubComparison({ changes }: { changes: ClubComparisonChange[] }) {
  if (changes.length === 0) {
    return <Empty>Aún no hay dos estados del club que se puedan comparar.</Empty>;
  }
  return (
    <div className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-3">
      {changes.map((change) => (
        <section
          key={change.key}
          className={clsx(
            "rounded-lg border p-4",
            change.changed
              ? "border-[var(--accent)] bg-[var(--accent-soft)]"
              : "border-[var(--border)] bg-[var(--bg)]",
          )}
        >
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs text-[var(--muted)]">{change.label}</span>
            <span
              className={clsx(
                "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                change.changed
                  ? "bg-[var(--accent)] text-white"
                  : "bg-[var(--surface-2)] text-[var(--muted)]",
              )}
            >
              {change.changed ? "Cambió" : "Igual"}
            </span>
          </div>
          <div className="mt-4 grid grid-cols-[1fr_auto_1fr] items-center gap-3">
            <div>
              <div className="text-[10px] uppercase tracking-wide text-[var(--muted)]">Antes</div>
              <div className="mt-1 text-sm font-medium">{change.beforeDisplay ?? "—"}</div>
            </div>
            <span aria-hidden className="text-[var(--muted)]">→</span>
            <div className="text-right">
              <div className="text-[10px] uppercase tracking-wide text-[var(--muted)]">Ahora</div>
              <div className="mt-1 text-sm font-semibold">{change.currentDisplay ?? "—"}</div>
            </div>
          </div>
          {change.changed && change.delta != null && (
            <div
              className={clsx(
                "mt-3 text-right text-xs font-semibold tabular-nums",
                change.delta > 0 ? "text-[var(--positive)]" : "text-[var(--danger)]",
              )}
            >
              {signed(change.delta)}
            </div>
          )}
        </section>
      ))}
    </div>
  );
}

export function SyncComparisonReport({ data }: { data: LastSyncChanges }) {
  const [tab, setTab] = useState<"players" | "club">("players");
  return (
    <Panel
      title="Comparación semanal"
      meta={data.reportIsLatest ? "último cierre semanal" : "última variación semanal"}
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] px-4 py-3">
        <div className="flex rounded-lg bg-[var(--surface-2)] p-1">
          <button
            type="button"
            onClick={() => setTab("players")}
            className={clsx(
              "rounded-md px-3 py-1.5 text-xs font-semibold",
              tab === "players" ? "bg-[var(--surface)] text-[var(--text)] shadow-sm" : "text-[var(--muted)]",
            )}
          >
            Equipo · Jugadores
          </button>
          <button
            type="button"
            onClick={() => setTab("club")}
            className={clsx(
              "rounded-md px-3 py-1.5 text-xs font-semibold",
              tab === "club" ? "bg-[var(--surface)] text-[var(--text)] shadow-sm" : "text-[var(--muted)]",
            )}
          >
            Equipo · Club
          </button>
        </div>
        <span className="text-xs text-[var(--muted)]">
          {data.playerRows.length} jugador(es) con variación · datos CHPP reales
        </span>
      </div>
      {tab === "players" ? <PlayersComparison data={data} /> : <ClubComparison changes={data.clubChanges} />}
    </Panel>
  );
}
