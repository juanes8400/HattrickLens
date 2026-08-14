import clsx from "clsx";
import { PlayerLink } from "./PlayerLink";
import { number } from "../hooks/useFormat";
import type { SyncChange } from "../services/api";

const CATEGORY_LABELS: Record<string, string> = {
  jugadores: "Jugadores",
  entrenamiento: "Entrenamiento",
  partidos: "Partidos",
  liga: "Liga",
  economia: "Economía",
  "economía": "Economía",
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
  if (lower.includes("fidelidad")) {
    return { kind: "Fidelidad", tone: "text-[var(--positive)]" };
  }
  if (lower.includes("liderazgo")) {
    return { kind: "Liderazgo", tone: "text-[var(--positive)]" };
  }
  if (lower.includes("lesion") || lower.includes("lesión")) {
    return { kind: "Lesión", tone: "text-[var(--danger)]" };
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

// Los textos vienen del backend como frases ("TSI 223,870 -> 208,360",
// "Pases subió de 12 a 13", "lesión de nivel 0 a 1") — pedido explícito
// 2026-08-13: los números deben verse con el mismo formato bonito que ya usa
// Economía (valor, triángulo verde/rojo según si el cambio es bueno o malo,
// delta con signo), no como texto plano con una flecha "->".
type NumericDelta = { label: string; before: number; after: number; good: boolean | null };

const NEUTRAL_LABELS = new Set(["salario", "nivel de entrenamiento", "tipo"]);

function stripLabel(raw: string): string {
  return raw.trim().replace(/:\s*$/, "");
}

function parseNumericDelta(detail: string): NumericDelta | null {
  const toNum = (raw: string) => Number(raw.replace(/,/g, ""));

  let m = detail.match(/^(.+?)\s+(subió|bajó)\s+de\s+([\d,.]+)\s+a\s+([\d,.]+)\s*$/i);
  if (m) {
    const label = m[1] ?? "";
    const verb = m[2] ?? "";
    const before = toNum(m[3] ?? "0");
    const after = toNum(m[4] ?? "0");
    return { label: stripLabel(label), before, after, good: verb.toLowerCase() === "subió" };
  }

  m = detail.match(/^lesión de nivel (\d+) a (\d+)\s*$/i);
  if (m) {
    const before = toNum(m[1] ?? "0");
    const after = toNum(m[2] ?? "0");
    return { label: "Lesión", before, after, good: after < before };
  }

  m = detail.match(/^(.+?)\s+([\d,.]+)\s*->\s*([\d,.]+)\s*$/);
  if (m) {
    const label = m[1] ?? "";
    const before = toNum(m[2] ?? "0");
    const after = toNum(m[3] ?? "0");
    const key = stripLabel(label).toLowerCase();
    const good = NEUTRAL_LABELS.has(key) ? null : after > before;
    return { label: stripLabel(label), before, after, good };
  }

  return null;
}

function NumberDelta({ parsed }: { parsed: NumericDelta }) {
  const delta = parsed.after - parsed.before;
  const tone =
    parsed.good === true ? "text-[var(--positive)]" : parsed.good === false ? "text-[var(--danger)]" : "text-[var(--muted)]";
  return (
    <span className="inline-flex items-center gap-1.5 tabular-nums">
      <span className="font-medium text-[var(--text)]">{parsed.label}</span>
      <span className="font-semibold text-[var(--text)]">{number(parsed.after)}</span>
      <span className={clsx("font-semibold", tone)}>
        {parsed.good === true && "▲ "}
        {parsed.good === false && "▼ "}
        {delta > 0 ? "+" : ""}
        {number(delta)}
      </span>
    </span>
  );
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
            Qué cambió desde la última sincronización · {changes.length}
          </h2>
          <p className="mt-1 text-xs text-[var(--muted)]">
            Como Hattrick Control: sólo se muestran diferencias reales contra el snapshot anterior.
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
            <p className="p-3 text-sm text-[var(--muted)]">Sin cambios de jugadores en esta sincronización.</p>
          ) : (
            <ul className="divide-y divide-[var(--border)]">
              {playerChanges.slice(0, 12).map((change, index) => {
                const parsed = splitPlayerSummary(change.summary);
                const kind = classify(change.summary);
                const htPlayerId = playerLinks?.[parsed.title];
                const numeric = parseNumericDelta(parsed.detail);
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
                    {numeric ? (
                      <NumberDelta parsed={numeric} />
                    ) : (
                      <span className="text-sm text-[var(--muted)]">{parsed.detail}</span>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="space-y-3">
          {groupByCategory(
            changes.filter((c) => c.category !== "jugadores" && c.category !== "economía" && c.category !== "economia"),
          ).map(([category, items]) => (
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
                {items.map((item, index) => {
                  const numeric = parseNumericDelta(item.summary);
                  return (
                    <li key={`${item.summary}-${index}`}>
                      {numeric ? <NumberDelta parsed={numeric} /> : item.summary}
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
