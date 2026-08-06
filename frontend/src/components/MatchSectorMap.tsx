import clsx from "clsx";
import type { MatchDetail } from "../services/api";

const SECTOR_LAYOUT: Record<string, { col: number; row: number }> = {
  left_att: { col: 1, row: 1 },
  central_att: { col: 2, row: 1 },
  right_att: { col: 3, row: 1 },
  midfield: { col: 2, row: 2 },
  left_def: { col: 1, row: 3 },
  central_def: { col: 2, row: 3 },
  right_def: { col: 3, row: 3 },
};

function tone(delta: number): string {
  if (delta >= 10) return "border-[var(--positive)] bg-[var(--positive)]/20";
  if (delta <= -10) return "border-[var(--danger)] bg-[var(--danger)]/20";
  return "border-[var(--warning)] bg-[var(--warning)]/15";
}

function verdict(delta: number): string {
  if (delta >= 10) return "dominamos";
  if (delta <= -10) return "nos superan";
  return "parejo";
}

export function MatchSectorMap({ data }: { data: MatchDetail }) {
  const max = Math.max(...data.sectors.flatMap((s) => [s.own, s.opponent, 1]));
  const sectors = data.sectors
    .filter((s) => SECTOR_LAYOUT[s.sector])
    .map((s) => ({ ...s, ...SECTOR_LAYOUT[s.sector] }));

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] p-4">
      <div className="mb-3 flex items-center justify-between gap-2 text-xs text-[var(--muted)]">
        <span>Mapa de sectores</span>
        <span>Nosotros vs rival</span>
      </div>
      <div className="grid grid-cols-3 grid-rows-3 gap-3">
        {sectors.map((s) => (
          <div
            key={s.sector}
            className={clsx("rounded-lg border p-3", tone(s.delta))}
            style={{ gridColumn: s.col, gridRow: s.row }}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="text-xs font-medium">{s.label}</div>
              <div className="text-xs tabular-nums">
                {s.delta > 0 ? "+" : ""}
                {s.delta}
              </div>
            </div>
            <div className="mt-2 grid grid-cols-[1fr_auto] items-center gap-2 text-[11px]">
              <div className="h-2 overflow-hidden rounded bg-black/10">
                <div
                  className="h-full bg-[var(--accent)]"
                  style={{ width: `${Math.max(4, (s.own / max) * 100)}%` }}
                />
              </div>
              <span className="tabular-nums">{s.own}</span>
              <div className="h-2 overflow-hidden rounded bg-black/10">
                <div
                  className="h-full bg-[var(--muted)]"
                  style={{ width: `${Math.max(4, (s.opponent / max) * 100)}%` }}
                />
              </div>
              <span className="tabular-nums">{s.opponent}</span>
            </div>
            <div className="mt-2 text-[10px] uppercase tracking-wide text-[var(--muted)]">
              {verdict(s.delta)}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-3 text-[11px] text-[var(--muted)]">
        <span className="inline-flex items-center gap-1">
          <span className="h-2 w-4 rounded bg-[var(--accent)]" /> Nosotros
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-2 w-4 rounded bg-[var(--muted)]" /> Rival
        </span>
        <span>Umbral de dominio: ±10 puntos.</span>
      </div>
    </div>
  );
}
