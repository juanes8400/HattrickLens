import clsx from "clsx";
import { PlayerLink } from "./PlayerLink";
import type { SyncChange } from "../services/api";

const CATEGORY_LABELS: Record<string, string> = {
  jugadores: "Jugadores",
  entrenamiento: "Entrenamiento",
  partidos: "Partidos",
  liga: "Liga",
  economia: "Economia",
  "economía": "Economia",
};

const CATEGORY_TONE: Record<string, string> = {
  jugadores: "bg-[var(--accent-soft)] text-[var(--accent)]",
  entrenamiento: "bg-[var(--positive)]/15 text-[var(--positive)]",
  partidos: "bg-[var(--warning)]/15 text-[var(--warning)]",
  liga: "bg-[var(--warning)]/15 text-[var(--warning)]",
  economia: "bg-[var(--surface-2)] text-[var(--muted)]",
  "economía": "bg-[var(--surface-2)] text-[var(--muted)]",
};

function classify(summary: string): { kind: string; tone: string } {
  const lower = summary.toLowerCase();
  if (lower.includes("subio") || lower.includes("subió")) {
    return { kind: "Subida", tone: "text-[var(--positive)]" };
  }
  if (lower.includes("bajo") || lower.includes("bajó")) {
    return { kind: "Bajada", tone: "text-[var(--danger)]" };
  }
  if (lower.includes("tsi")) {
    return { kind: "TSI", tone: "text-[var(--accent)]" };
  }
  if (lower.includes("salario")) {
    return { kind: "Salario", tone: "text-[var(--warning)]" };
  }
  if (lower.includes("forma")) {
    return { kind: "Forma", tone: "text-[var(--accent)]" };
  }
  if (lower.includes("resistencia")) {
    return { kind: "Resistencia", tone: "text-[var(--accent)]" };
  }
  if (lower.includes("experiencia")) {
    return { kind: "Experiencia", tone: "text-[var(--positive)]" };
  }
  if (lower.includes("lesion")) {
    return { kind: "Lesion", tone: "text-[var(--danger)]" };
  }
  if (lower.includes("mercado")) {
    return { kind: "Mercado", tone: "text-[var(--warning)]" };
  }
  if (lower.includes("se unio") || lower.includes("se unió")) {
    return { kind: "Alta", tone: "text-[var(--positive)]" };
  }
  return { kind: "Cambio", tone: "text-[var(--muted)]" };
}

function splitPlayerSummary(summary: string): { title: string; detail: string } {
  const idx = summary.indexOf(":");
  if (idx === -1) return { title: summary, detail: "" };
  return { title: summary.slice(0, idx), detail: summary.slice(idx + 1).trim() };
}

function groupByCategory(changes: SyncChange[]): [string, SyncChange[]][] {
  const byCategory = new Map<string, SyncChange[]>();
  for (const change of changes) {
    const list = byCategory.get(change.category) ?? [];
    list.push(change);
    byCategory.set(change.category, list);
  }
  const order = ["jugadores", "entrenamiento", "partidos", "liga", "economía", "economia"];
  const known = order.filter((cat) => byCategory.has(cat));
  const rest = [...byCategory.keys()].filter((cat) => !order.includes(cat));
  return [...known, ...rest].map((cat) => [cat, byCategory.get(cat) ?? []]);
}

export function SyncChangesFeed({
  changes,
  onDismiss,
  playerLinks,
}: {
  changes: SyncChange[];
  onDismiss: () => void;
  playerLinks?: Record<string, number>;
}) {
  const playerChanges = changes.filter((c) => c.category === "jugadores");
  const skillPops = playerChanges.filter((c) => {
    const lower = c.summary.toLowerCase();
    return lower.includes("subio") || lower.includes("subió");
  }).length;

  return (
    <div className="border-b border-[var(--border)] bg-[var(--surface)] px-6 py-4">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">
            Que cambio desde la ultima sincronizacion · {changes.length}
          </h2>
          <p className="mt-1 text-xs text-[var(--muted)]">
            Como Hattrick Control: solo se muestran diferencias reales contra el snapshot anterior.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {playerChanges.length > 0 && (
            <span className="rounded-full bg-[var(--accent-soft)] px-2 py-1 text-xs text-[var(--accent)]">
              {playerChanges.length} cambios de jugadores
            </span>
          )}
          {skillPops > 0 && (
            <span className="rounded-full bg-[var(--positive)]/15 px-2 py-1 text-xs text-[var(--positive)]">
              {skillPops} subida(s)
            </span>
          )}
          <button
            onClick={onDismiss}
            aria-label="Descartar novedades"
            className="text-xs text-[var(--muted)] hover:text-[var(--text)]"
          >
            Cerrar
          </button>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
        <div className="rounded-lg border border-[var(--border)] bg-[var(--bg)]">
          <div className="border-b border-[var(--border)] px-3 py-2 text-xs font-medium text-[var(--muted)]">
            Jugadores
          </div>
          {playerChanges.length === 0 ? (
            <p className="p-3 text-sm text-[var(--muted)]">Sin cambios de jugadores en este sync.</p>
          ) : (
            <ul className="divide-y divide-[var(--border)]">
              {playerChanges.slice(0, 12).map((change, index) => {
                const parsed = splitPlayerSummary(change.summary);
                const kind = classify(change.summary);
                const htPlayerId = playerLinks?.[parsed.title];
                return (
                  <li key={`${change.summary}-${index}`} className="grid gap-1 px-3 py-2 sm:grid-cols-[11rem_5rem_1fr]">
                    <span className="font-medium">
                      {htPlayerId ? (
                        <PlayerLink htPlayerId={htPlayerId} name={parsed.title} />
                      ) : (
                        parsed.title
                      )}
                    </span>
                    <span className={clsx("text-xs font-semibold", kind.tone)}>{kind.kind}</span>
                    <span className="text-sm text-[var(--muted)]">{parsed.detail}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="space-y-3">
          {groupByCategory(changes.filter((c) => c.category !== "jugadores")).map(([category, items]) => (
            <section key={category} className="rounded-lg border border-[var(--border)] bg-[var(--bg)] p-3">
              <div className="mb-2 flex items-center justify-between">
                <span
                  className={clsx(
                    "rounded-full px-2 py-1 text-[11px] font-semibold",
                    CATEGORY_TONE[category] ?? "bg-[var(--surface-2)] text-[var(--muted)]",
                  )}
                >
                  {CATEGORY_LABELS[category] ?? category}
                </span>
                <span className="text-xs text-[var(--muted)]">{items.length}</span>
              </div>
              <ul className="space-y-1 text-sm">
                {items.map((item, index) => (
                  <li key={`${item.summary}-${index}`}>{item.summary}</li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
