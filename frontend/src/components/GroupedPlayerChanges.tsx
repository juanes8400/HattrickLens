import clsx from "clsx";
import { PlayerLink } from "./PlayerLink";
import { Empty } from "./Panels";

/**
 * Formato "Hattrick Control" pedido 2026-08-10: jugador por jugador,
 * habilidad por habilidad, y luego un agregado del equipo desglosado POR
 * habilidad (no un total único) — usado tanto por el snapshot más reciente
 * como por el histórico de la semana, para que ambas vistas se lean igual.
 */
export interface NormalizedChange {
  key: string;
  label: string;
  before: number | boolean | null;
  current: number | boolean | null;
  delta: number | null;
  direction: "up" | "down" | "neutral";
}

export interface PlayerChangeGroup {
  htPlayerId: number;
  name: string;
  changes: NormalizedChange[];
}

export interface AggregateMetric {
  key: string;
  label: string;
  upCount: number;
  downCount: number;
  net: number;
}

function signed(value: number): string {
  if (value === 0) return "0";
  return `${value > 0 ? "+" : ""}${value}`;
}

/** Casos sin un par before/current numérico limpio — se muestran como una
 * sola frase coloreada, sin el formato "antes ▲ ahora (delta)". */
function specialChangeLine(change: NormalizedChange): string | null {
  if (change.key === "arrival") return "Nuevo jugador";
  if (change.key === "market") return change.current ? "Puesto en venta" : "Retirado del mercado";
  if (change.key === "injury") {
    if (change.current === -1) return "Recuperado";
    if (change.before === -1) return `Lesión (nivel ${change.current})`;
    return `Lesión ${change.before} → ${change.current}`;
  }
  return null;
}

/** Formato pedido 2026-08-11: "antes ▲ ahora (delta)" — sólo el valor
 * nuevo, la flecha y el delta llevan color; "antes" queda en tono neutro
 * para que el ojo vaya directo a lo que cambió. */
function ChangeValue({ change }: { change: NormalizedChange }) {
  const toneClass = clsx(
    "font-semibold tabular-nums",
    change.direction === "up" && "text-[var(--positive)]",
    change.direction === "down" && "text-[var(--danger)]",
    change.direction === "neutral" && "text-[var(--muted)]",
  );
  const special = specialChangeLine(change);
  if (special != null) {
    return <span className={toneClass}>{special}</span>;
  }
  return (
    <span className="tabular-nums">
      <span className="text-[var(--text)]">{String(change.before)}</span>{" "}
      <span className={toneClass}>
        {change.direction === "up" && "▲ "}
        {change.direction === "down" && "▼ "}
        {String(change.current)} ({signed(change.delta ?? 0)})
      </span>
    </span>
  );
}

function PlayerChangeCard({ group }: { group: PlayerChangeGroup }) {
  return (
    <section className="rounded-lg border border-[var(--border)] bg-[var(--bg)] p-3">
      <header className="mb-2 border-b border-[var(--border)] pb-2 text-sm font-semibold">
        <PlayerLink htPlayerId={group.htPlayerId} name={group.name} />
      </header>
      <ul className="space-y-1.5 text-xs">
        {group.changes.map((change, index) => (
          <li key={`${change.key}-${index}`} className="flex items-center justify-between gap-3">
            <span className="text-[var(--muted)]">{change.label}</span>
            <ChangeValue change={change} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function AggregateCard({ metric }: { metric: AggregateMetric }) {
  return (
    <section className="rounded-lg border border-[var(--border)] bg-[var(--bg)] p-3">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">{metric.label}</div>
      <dl className="space-y-1 text-sm">
        {metric.upCount > 0 && (
          <div className="flex items-center justify-between">
            <dt className="text-[var(--muted)]">Subidas</dt>
            <dd className="font-semibold tabular-nums text-[var(--positive)]">{metric.upCount} caso(s)</dd>
          </div>
        )}
        {metric.downCount > 0 && (
          <div className="flex items-center justify-between">
            <dt className="text-[var(--muted)]">Bajadas</dt>
            <dd className="font-semibold tabular-nums text-[var(--danger)]">{metric.downCount} caso(s)</dd>
          </div>
        )}
        <div className="flex items-center justify-between">
          <dt className="text-[var(--muted)]">Balance</dt>
          <dd
            className={clsx(
              "font-semibold tabular-nums",
              metric.net > 0 && "text-[var(--positive)]",
              metric.net < 0 && "text-[var(--danger)]",
            )}
          >
            {signed(metric.net)}
          </dd>
        </div>
      </dl>
    </section>
  );
}

export function GroupedPlayerChanges({
  groups,
  aggregate,
  emptyMessage,
}: {
  groups: PlayerChangeGroup[];
  aggregate: AggregateMetric[];
  emptyMessage: string;
}) {
  const visibleAggregate = aggregate.filter((metric) => metric.upCount > 0 || metric.downCount > 0);

  if (groups.length === 0) {
    return <Empty>{emptyMessage}</Empty>;
  }

  return (
    <div className="space-y-5 p-4">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {groups.map((group) => (
          <PlayerChangeCard key={group.htPlayerId} group={group} />
        ))}
      </div>

      {visibleAggregate.length > 0 && (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
            Total equipo
          </h3>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {visibleAggregate.map((metric) => (
              <AggregateCard key={metric.key} metric={metric} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
