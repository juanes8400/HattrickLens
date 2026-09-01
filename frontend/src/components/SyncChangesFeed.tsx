import clsx from "clsx";
import { PlayerLink } from "./PlayerLink";
import { number } from "../hooks/useFormat";
import type { SyncChange, SyncChangeDetail } from "../services/api";

const CATEGORY_LABELS: Record<string, string> = {
  jugadores: "Jugadores",
  entrenamiento: "Entrenamiento",
  partidos: "Partidos",
  liga: "Liga",
  rivales: "Rivales",
  economia: "Economía",
  economía: "Economía",
};

const CATEGORY_TONE: Record<string, string> = {
  // Los fichajes de los clubes contra los que vas a jugar no son un cambio
  // tuyo: llevan su propio color para que no se confundan con tu plantilla.
  rivales: "bg-[var(--warning)]/15 text-[var(--warning)]",
  jugadores: "bg-[var(--accent-soft)] text-[var(--accent)]",
  entrenamiento: "bg-[var(--positive)]/15 text-[var(--positive)]",
  partidos: "bg-[var(--warning)]/15 text-[var(--warning)]",
  liga: "bg-[var(--warning)]/15 text-[var(--warning)]",
  economia: "bg-[var(--surface-2)] text-[var(--muted)]",
  economía: "bg-[var(--surface-2)] text-[var(--muted)]",
};

type NumericDelta = {
  label: string;
  before: number;
  after: number;
  good: boolean | null;
  afterDisplay?: string;
  stateLabel?: string;
};

const TEAM_SPIRIT_LEVELS: Record<string, number> = {
  "como en la guerra fría": 0,
  "muy agresivos": 1,
  tensos: 2,
  susceptibles: 3,
  serenos: 4,
  calmados: 5,
  contentos: 6,
  encantados: 7,
  eufóricos: 8,
  "por las nubes": 9,
  "paraíso en la tierra": 10,
};

const CONFIDENCE_LEVELS: Record<string, number> = {
  inexistente: 0,
  "por los suelos": 1,
  "muy baja": 2,
  baja: 3,
  decente: 4,
  sólida: 5,
  alta: 6,
  "muy alta": 7,
  exagerada: 8,
  desmedida: 9,
};

function metricTone(label: string): string {
  const key = label.toLocaleLowerCase("es");
  if (key === "salario") return "text-[var(--warning)]";
  if (["experiencia", "fidelidad", "liderazgo"].includes(key)) {
    return "text-[var(--positive)]";
  }
  if (key === "lesión") return "text-[var(--danger)]";
  return "text-[var(--accent)]";
}

function classify(
  summary: string,
  numeric: NumericDelta | null,
): { kind: string; tone: string } {
  // La segunda columna nombra QUÉ cambió. La dirección ya vive en el
  // triángulo, el color y el delta de la tercera columna; decir "Subida" o
  // "Bajada" aquí duplicaba esa señal y ocultaba rubros como "Pases".
  if (numeric) return { kind: numeric.label, tone: metricTone(numeric.label) };

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

function splitPlayerSummary(summary: string): {
  title: string;
  detail: string;
} {
  const idx = summary.indexOf(":");
  if (idx === -1) return { title: summary, detail: "" };
  return {
    title: summary.slice(0, idx),
    detail: summary.slice(idx + 1).trim(),
  };
}

// Los textos vienen del backend como frases ("TSI 223,870 -> 208,360",
// "Pases subió de 12 a 13", "lesión de nivel 0 a 1") — pedido explícito
// 2026-08-13: los números deben verse con el mismo formato bonito que ya usa
// Economía (valor, triángulo verde/rojo según si el cambio es bueno o malo,
// delta con signo), no como texto plano con una flecha "->".
const NEUTRAL_LABELS = new Set(["salario", "nivel de entrenamiento", "tipo"]);

function stripLabel(raw: string): string {
  return raw.trim().replace(/:\s*$/, "");
}

/**
 * Camino principal desde 2026-08-15: el backend manda el cambio como dato
 * (`detail`), así que aquí no se parsea nada — sólo se decide cómo pintarlo.
 * Devuelve `null` para eventos sin par numérico (llegó, se vendió, mercado),
 * que se muestran como frase.
 */
function numericFromDetail(
  detail: SyncChangeDetail | null | undefined,
): NumericDelta | null {
  if (!detail || detail.before == null || detail.after == null) return null;
  if (detail.kind === "event") return null;
  return {
    label: detail.label ?? "",
    before: detail.before,
    after: detail.after,
    good: detail.good ?? null,
    // Un nivel con nombre propio (espíritu, confianza) muestra la etiqueta
    // además del número, igual que hacía el parser con `stateLabel`.
    stateLabel: detail.kind === "level" ? detail.afterLabel : undefined,
  };
}

/**
 * Compatibilidad para las filas guardadas ANTES de que existiera `detail`.
 * No se usa para cambios nuevos — ver `numericFromDetail`.
 */
export function parseNumericDelta(detail: string): NumericDelta | null {
  // Los números llegan dentro de la frase ya formateados. Hasta 2026-08-15 el
  // backend usaba coma de miles ("202,210"); desde ese día usa punto, como el
  // resto de la app ("202.210"). Hay frases de las dos épocas guardadas en
  // `sync_changes`, así que aquí se aceptan ambas: un separador solo cuenta
  // como de miles si lo siguen EXACTAMENTE tres dígitos — si no, es decimal.
  // Sin ese matiz, `Number("202.210")` daba 202,21 y la UI mostraba "202".
  const toNum = (raw: string) =>
    Number(raw.replace(/[.,](?=\d{3}(?:\D|$))/g, "").replace(",", "."));

  const state = detail.match(
    /^(Espíritu del equipo|Confianza):\s*(.+?)\s*->\s*(.+?)\s*$/i,
  );
  if (state) {
    const label = state[1] ?? "";
    const beforeRaw = state[2] ?? "";
    const afterRaw = state[3] ?? "";
    const levels = label.toLocaleLowerCase("es").startsWith("espíritu")
      ? TEAM_SPIRIT_LEVELS
      : CONFIDENCE_LEVELS;
    const levelOf = (raw: string): number | null => {
      const numeric = Number(raw);
      if (Number.isFinite(numeric)) return numeric;
      return levels[raw.toLocaleLowerCase("es")] ?? null;
    };
    const before = levelOf(beforeRaw);
    const after = levelOf(afterRaw);
    if (before != null && after != null) {
      return {
        label,
        before,
        after,
        good: after > before,
        stateLabel: afterRaw,
      };
    }
  }

  let m = detail.match(
    /^(.+?)\s+(subió|bajó)\s+de\s+([\d,.]+)\s+a\s+([\d,.]+)\s*$/i,
  );
  if (m) {
    const label = m[1] ?? "";
    const verb = m[2] ?? "";
    const before = toNum(m[3] ?? "0");
    const after = toNum(m[4] ?? "0");
    return {
      label: stripLabel(label),
      before,
      after,
      good: verb.toLowerCase() === "subió",
    };
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

function NumberDelta({
  parsed,
  showLabel = true,
}: {
  parsed: NumericDelta;
  showLabel?: boolean;
}) {
  const delta = parsed.after - parsed.before;
  const tone =
    parsed.good === true
      ? "text-[var(--positive)]"
      : parsed.good === false
        ? "text-[var(--danger)]"
        : "text-[var(--muted)]";
  if (parsed.stateLabel) {
    return (
      <span className="inline-flex flex-wrap items-center gap-1.5 tabular-nums">
        <span className="font-semibold text-[var(--text)]">
          {parsed.label} {parsed.stateLabel}
        </span>
        <span className="text-[var(--muted)]">{number(parsed.before)}</span>
        <span className={clsx("font-semibold", tone)}>
          {parsed.good === true ? "▲" : parsed.good === false ? "▼" : "→"}
        </span>
        <span className="font-semibold text-[var(--text)]">
          {number(parsed.after)}
        </span>
        <span className={clsx("font-semibold", tone)}>
          ({delta > 0 ? "+" : ""}
          {number(delta)})
        </span>
      </span>
    );
  }
  return (
    <span className="inline-flex items-baseline justify-end gap-1.5 whitespace-nowrap tabular-nums">
      {showLabel && (
        <span className="font-medium text-[var(--text)]">{parsed.label}</span>
      )}
      <span className="font-semibold text-[var(--text)]">
        {parsed.afterDisplay ?? number(parsed.after)}
      </span>
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
  const order = [
    "jugadores",
    "entrenamiento",
    "partidos",
    "liga",
    "economía",
    "economia",
  ];
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
            Sólo se muestran diferencias reales contra la lectura anterior.
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

      <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr] [&>*]:min-w-0">
        <div className="rounded-lg border border-[var(--border)] bg-[var(--bg)]">
          <div className="border-b border-[var(--border)] px-3 py-2 text-xs font-medium text-[var(--muted)]">
            Jugadores
          </div>
          {playerChanges.length === 0 ? (
            <p className="p-3 text-sm text-[var(--muted)]">
              Sin cambios de jugadores en esta sincronización.
            </p>
          ) : (
            <ul className="max-h-[32rem] divide-y divide-[var(--border)] overflow-y-auto overscroll-contain">
              {playerChanges.map((change, index) => {
                const parsed = splitPlayerSummary(change.summary);
                // El nombre del jugador viene en `detail.subject` cuando el
                // cambio es nuevo; en las filas viejas hay que sacarlo de la
                // frase, que es de donde salía siempre.
                const title = change.detail?.subject ?? parsed.title;
                const htPlayerId = playerLinks?.[title];
                const numeric =
                  numericFromDetail(change.detail) ??
                  parseNumericDelta(parsed.detail);
                const kind = classify(change.summary, numeric);
                return (
                  // Tres columnas de ancho fijo y el valor a la derecha: con
                  // `1fr` al final cada fila empezaba su número donde
                  // terminara el texto de al lado, así que la columna de
                  // cifras salía en diente de sierra.
                  <li
                    key={`${change.summary}-${index}`}
                    className="grid grid-cols-[1fr_5.5rem] items-baseline gap-x-3 gap-y-0.5 px-3 py-2 sm:grid-cols-[1fr_6rem_9rem]"
                  >
                    <span className="truncate font-medium">
                      {htPlayerId ? (
                        <PlayerLink htPlayerId={htPlayerId} name={title} />
                      ) : (
                        title
                      )}
                    </span>
                    <span
                      className={clsx(
                        "truncate text-xs font-semibold",
                        kind.tone,
                      )}
                    >
                      {kind.kind}
                    </span>
                    <span className="col-span-2 justify-self-end text-right sm:col-span-1">
                      {numeric ? (
                        <NumberDelta parsed={numeric} showLabel={false} />
                      ) : (
                        <span className="text-sm text-[var(--muted)]">
                          {parsed.detail}
                        </span>
                      )}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="space-y-3">
          {groupByCategory(
            changes.filter(
              (c) =>
                c.category !== "jugadores" &&
                c.category !== "economía" &&
                c.category !== "economia",
            ),
          ).map(([category, items]) => (
            <section
              key={category}
              className="rounded-lg border border-[var(--border)] bg-[var(--bg)] p-3"
            >
              <div className="mb-2 flex items-center justify-between">
                <span
                  className={clsx(
                    "rounded-full px-2 py-1 text-[11px] font-semibold",
                    CATEGORY_TONE[category] ??
                      "bg-[var(--surface-2)] text-[var(--muted)]",
                  )}
                >
                  {CATEGORY_LABELS[category] ?? category}
                </span>
                <span className="text-xs text-[var(--muted)]">
                  {items.length}
                </span>
              </div>
              <ul className="space-y-1 text-sm">
                {items.map((item, index) => {
                  const numeric =
                    numericFromDetail(item.detail) ??
                    parseNumericDelta(item.summary);
                  return (
                    <li key={`${item.summary}-${index}`}>
                      {numeric ? (
                        <NumberDelta parsed={numeric} />
                      ) : (
                        item.summary
                      )}
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
