import clsx from "clsx";
import { Link } from "react-router-dom";
import type { Insight } from "../services/api";

/**
 * Piezas compartidas de alertas — 2026-08-15, pedido explícito: "las alertas
 * están como muy sueltas, no se les ve importantes".
 *
 * Antes el Dashboard pintaba su propia versión reducida (título + detalle en
 * gris, sin color de severidad, sin la acción sugerida y sin enlace), así que
 * la misma alerta se veía urgente en /insights e irrelevante en el Dashboard.
 * Ahora las dos pantallas usan estas piezas: una alerta se ve igual de seria
 * esté donde esté.
 */

export const INSIGHT_TONE = {
  danger: "var(--danger)",
  warning: "var(--warning)",
  opportunity: "var(--positive)",
  info: "var(--muted)",
} as const;

export const SEVERITY_LABEL: Record<Insight["severity"], string> = {
  danger: "Peligro",
  warning: "Aviso",
  opportunity: "Oportunidad",
  info: "Info",
};

export const SEVERITIES: Insight["severity"][] = [
  "danger",
  "warning",
  "opportunity",
  "info",
];

/** Cada alerta trae el módulo que la generó; llevar al usuario ahí es la
 *  diferencia entre "te aviso" y "te ayudo". `general` no tiene una pantalla
 *  propia — nace del estado del sync. */
const MODULE_ROUTES: Record<string, string> = {
  entrenamiento: "/training",
  economía: "/economy",
  economia: "/economy",
  equipo: "/team",
  liga: "/league",
  copa: "/cup",
  academia: "/academy",
  estadio: "/arena",
  staff: "/club",
  transferencias: "/transfers/balance",
  partidos: "/matches",
  general: "/sync",
};

export function insightRoute(module: string): string | null {
  return MODULE_ROUTES[module] ?? null;
}

/**
 * Una alerta. La X de la esquina superior derecha la manda al buzón — pedido
 * explícito 2026-08-16.
 *
 * Archivar NO silencia la regla: el servidor guarda una huella del contenido,
 * así que si la misma alerta se vuelve a generar con otra cifra u otra
 * severidad, reaparece sola en la lista activa. Descartar "pierdes dinero cada
 * semana" no puede esconder que la semana siguiente pierdas el doble.
 */
export function InsightRow({
  insight,
  onArchive,
  onRestore,
  meta,
  busy = false,
}: {
  insight: Insight;
  onArchive?: (key: string) => void;
  onRestore?: (key: string) => void;
  meta?: React.ReactNode;
  busy?: boolean;
}) {
  const route = insightRoute(insight.module);
  return (
    <li className="flex gap-3 border-b border-[var(--border)] p-4 last:border-0">
      <span
        aria-hidden
        className="mt-1.5 h-2 w-2 shrink-0 rounded-full"
        style={{ background: INSIGHT_TONE[insight.severity] }}
      />
      <div className="min-w-0 flex-1">
        <div className="text-sm font-medium">{insight.title}</div>
        <p className="prosa mt-0.5 text-xs leading-relaxed text-[var(--muted)]">
          {insight.detail}
        </p>
        {insight.action && (
          <p className="prosa mt-1.5 text-xs text-[var(--accent)]">
            → {insight.action}
          </p>
        )}
        {meta && (
          <div className="mt-1.5 text-[11px] text-[var(--muted)]">{meta}</div>
        )}
      </div>
      <div className="flex shrink-0 items-start gap-2">
        {route ? (
          <Link
            to={route}
            className="text-[11px] text-[var(--muted)] underline-offset-2 hover:text-[var(--accent)] hover:underline"
          >
            {insight.module}
          </Link>
        ) : (
          <span className="text-[11px] text-[var(--muted)]">
            {insight.module}
          </span>
        )}
        {onRestore && (
          <button
            onClick={() => onRestore(insight.key)}
            disabled={busy}
            title="Devolver a las alertas activas"
            className="-mt-1 rounded-md px-1.5 py-0.5 text-[11px] text-[var(--muted)] hover:bg-[var(--surface-2)] hover:text-[var(--accent)] disabled:opacity-40"
          >
            Restaurar
          </button>
        )}
        {onArchive && (
          <button
            onClick={() => onArchive(insight.key)}
            disabled={busy}
            aria-label="Archivar alerta"
            title="Archivar en el buzón"
            className="-mr-1.5 -mt-1.5 rounded-md px-2 py-1 text-sm leading-none text-[var(--muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text)] disabled:opacity-40"
          >
            ×
          </button>
        )}
      </div>
    </li>
  );
}

/**
 * Recuento por severidad. En el Dashboard es lo primero que se ve: "2 peligros
 * y 5 avisos" responde antes que cualquier gráfica a la pregunta de por dónde
 * empezar hoy. Las severidades sin ninguna alerta no se pintan — un cero no es
 * información, es ruido.
 */
export function SeverityTally({
  insights,
  onSelect,
  active,
}: {
  insights: Insight[];
  onSelect?: (severity: Insight["severity"]) => void;
  active?: Set<Insight["severity"]>;
}) {
  const counts = insights.reduce<Record<string, number>>((acc, i) => {
    acc[i.severity] = (acc[i.severity] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="flex flex-wrap items-center gap-2">
      {SEVERITIES.map((severity) => {
        const n = counts[severity] ?? 0;
        if (n === 0 && !onSelect) return null;
        const on = active ? active.has(severity) : true;
        const content = (
          <>
            <span
              aria-hidden
              className="h-2 w-2 shrink-0 rounded-full"
              style={{ background: INSIGHT_TONE[severity] }}
            />
            {SEVERITY_LABEL[severity]}
            {/* El contador iba pegado a la palabra y el nombre accesible del
                botón salía «Peligro0». Se lee del `aria-label` de abajo. */}
            <span aria-hidden className="tabular-nums text-[var(--muted)]">
              {n}
            </span>
          </>
        );
        const className = clsx(
          // `min-h-6` son los 24px minimos de diana tactil: con `py-1` la
          // pastilla medía 21 y quedaba por debajo (medido el 2026-08-31).
          "flex min-h-6 items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition",
          on
            ? "border-[var(--border)] bg-[var(--surface-2)]"
            : "border-[var(--border)] text-[var(--muted)] opacity-50",
          n === 0 && "cursor-not-allowed opacity-30",
        );
        return onSelect ? (
          <button
            key={severity}
            onClick={() => onSelect(severity)}
            disabled={n === 0}
            // Es un conmutador: sin `aria-pressed` el que esté puesto o
            // quitado se transmite SÓLO por color y opacidad.
            aria-pressed={on}
            aria-label={`${SEVERITY_LABEL[severity]}: ${n} ${n === 1 ? "alerta" : "alertas"}`}
            className={className}
          >
            {content}
          </button>
        ) : (
          <span key={severity} className={className}>
            {content}
          </span>
        );
      })}
    </div>
  );
}
