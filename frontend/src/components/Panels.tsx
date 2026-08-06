import clsx from "clsx";

export function Kpi({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "positive" | "danger";
}) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
      <div className="text-xs text-[var(--muted)]">{label}</div>
      <div
        className={clsx(
          "mt-2 text-2xl font-semibold tabular-nums",
          tone === "positive" && "text-[var(--positive)]",
          tone === "danger" && "text-[var(--danger)]",
        )}
      >
        {value}
      </div>
      {hint && <div className="mt-1 text-xs text-[var(--muted)]">{hint}</div>}
    </div>
  );
}

export function Panel({
  title,
  meta,
  children,
}: {
  title: string;
  meta?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)]">
      <header className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
        <h2 className="text-sm font-semibold">{title}</h2>
        {meta && <span className="text-xs text-[var(--muted)]">{meta}</span>}
      </header>
      {children}
    </section>
  );
}

/**
 * Para proyecciones/estimaciones — nunca hechos. Borde punteado + rótulo
 * "PROYECCIÓN" para que sea imposible confundirlo con un `Panel` de datos
 * reales, incluso pasando rápido por la pantalla (HL-140: no mezclar hechos
 * con predicciones sin avisar).
 */
export function ProjectionPanel({
  title,
  meta,
  children,
}: {
  title: string;
  meta?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-dashed border-[var(--accent)] bg-[var(--surface)]">
      <header className="flex items-center justify-between border-b border-dashed border-[var(--accent)] px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="rounded bg-[var(--accent)] px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--surface)]">
            Proyección
          </span>
          <h2 className="text-sm font-semibold">{title}</h2>
        </div>
        {meta && <span className="text-xs text-[var(--muted)]">{meta}</span>}
      </header>
      {children}
    </section>
  );
}

/** Barra simple 0-max, para valores reales de un solo número (fidelidad,
 * forma, resistencia) — no un chart, para que se lea de un vistazo. */
export function GaugeBar({
  label,
  value,
  max,
}: {
  label: string;
  value: number;
  max: number;
}) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
      <div className="flex items-baseline justify-between">
        <span className="text-xs text-[var(--muted)]">{label}</span>
        <span className="tabular-nums text-sm font-semibold">
          {value}
          <span className="text-[var(--muted)]"> / {max}</span>
        </span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-[var(--surface-2)]">
        <div className="h-full bg-[var(--accent)]" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function Note({ children }: { children: React.ReactNode }) {
  return <p className="px-4 py-3 text-xs leading-relaxed text-[var(--muted)]">{children}</p>;
}

export function Loading() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="h-24 animate-pulse rounded-lg bg-[var(--surface)]" />
      ))}
    </div>
  );
}

export function ErrorState({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div className="rounded-lg border border-[var(--danger)] bg-[var(--surface)] p-6">
      <h2 className="font-semibold">No pudimos cargar estos datos</h2>
      <p className="mt-1 text-sm text-[var(--muted)]">{message}</p>
      <p className="mt-3 text-sm text-[var(--muted)]">
        Comprueba que el backend está levantado en el puerto 8000.
      </p>
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="p-10 text-center text-sm text-[var(--muted)]">{children}</div>;
}
