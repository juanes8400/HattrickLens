import clsx from "clsx";
import { ApiError } from "../services/api";

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
      <div className="min-h-[2rem] text-xs leading-4 text-[var(--muted)]">{label}</div>
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

/** Barra compacta para una fila de habilidad — se llena hasta `max` y, si el
 * valor real lo supera, se queda al 100% y muestra el excedente aparte
 * ("+1"/"+2") en vez de desbordar la barra. */
export function SkillBar({
  label,
  value,
  max = 20,
}: {
  label: string;
  value: number;
  max?: number;
}) {
  const overflow = Math.max(0, value - max);
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="text-sm">
      <div className="flex items-baseline justify-between gap-3">
        <span className="font-semibold">{label}</span>
        <span className="tabular-nums text-right font-semibold text-[var(--accent)]">
          {value}
          {overflow > 0 && <span className="ml-1 text-xs text-[var(--positive)]">+{overflow}</span>}
        </span>
      </div>
      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-[var(--surface-2)]">
        <div className="h-full bg-[var(--accent)]" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

/** Barra de progreso azul+rojo — pedida explícitamente 2026-08-10 para
 * unificar habilidad entrenada/Experiencia/Fidelidad/Forma/Resistencia en
 * una sola grilla pareja (antes: paneles separados de distinto tamaño).
 * El azul es siempre el nivel entero conocido; el rojo es la evidencia
 * real de progreso hacia el siguiente nivel, calculada distinto para cada
 * habilidad (ver PlayerPage.tsx) — nunca el mismo número reciclado.
 * `redPlacement="append"` lo pega justo después del azul (progreso hacia
 * arriba); `"eat"` le come al azul su propio tramo final (riesgo de bajar,
 * como en la proyección de Resistencia). `dot` reemplaza la franja roja
 * por un punto junto al valor — para Forma, que no tiene una fracción
 * calculable, solo la señal de "jugó esta semana". */
export function ProgressBar({
  label,
  level,
  max,
  valueLabel,
  redFraction = 0,
  redPlacement = "append",
  dot = false,
  tooltip,
}: {
  label: string;
  level: number;
  max: number;
  valueLabel: string;
  redFraction?: number;
  redPlacement?: "append" | "eat";
  dot?: boolean;
  tooltip: string;
}) {
  const bluePctFull = Math.max(0, Math.min(100, (level / max) * 100));
  const redPctRaw = (Math.max(redFraction, 0) / max) * 100;

  let blueWidth = bluePctFull;
  let redLeft = bluePctFull;
  let redWidth: number;
  if (redPlacement === "eat") {
    redWidth = Math.min(redPctRaw, bluePctFull);
    blueWidth = bluePctFull - redWidth;
    redLeft = blueWidth;
  } else {
    redWidth = Math.min(redPctRaw, Math.max(0, 100 - bluePctFull));
    redLeft = bluePctFull;
  }
  const segmentGap = blueWidth > 0 && redWidth > 0 ? 2 : 0;

  return (
    <div title={tooltip} className="cursor-help">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-sm font-semibold">{label}</span>
        <span className="flex items-center gap-1.5 tabular-nums text-sm font-semibold">
          {dot && <span className="h-1.5 w-1.5 rounded-full bg-[var(--danger)]" />}
          {valueLabel}
        </span>
      </div>
      {/* Cada tramo lleva sus propias esquinas y hay 2px de aire entre ellos.
          Antes ninguno tenía radio propio: se apoyaban en el recorte de la
          pista, así que el rojo salía como un rectángulo de bordes rectos
          pegado a hueso contra el azul, y sólo se redondeaba por la derecha
          si llegaba justo al 100%. El aire sólo aparece cuando hay los dos
          tramos, si no, dejaría un hueco contra el borde de la pista. */}
      <div className="relative mt-1.5 h-2 overflow-hidden rounded-full bg-[var(--surface-2)]">
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-[var(--accent)]"
          style={{ width: `${blueWidth}%` }}
        />
        {redWidth > 0 && (
          <div
            className="absolute inset-y-0 rounded-full bg-[var(--danger)]"
            style={{
              left: `calc(${redLeft}% + ${segmentGap}px)`,
              width: `max(0px, calc(${redWidth}% - ${segmentGap}px))`,
            }}
          />
        )}
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
  if (error instanceof ApiError && error.status === 401) {
    return (
      <div className="max-w-lg rounded-lg border border-[var(--warning)] bg-[var(--surface)] p-6">
        <h2 className="font-semibold">Tu sesión de Hattrick venció</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Reconecta para continuar. Los datos ya importados se conservan.
        </p>
        <a
          href="/welcome?reason=session_expired"
          className="mt-4 inline-flex rounded-md bg-[var(--accent)] px-3 py-2 text-sm font-semibold text-white"
        >
          Reconectar con Hattrick
        </a>
      </div>
    );
  }
  const message = error instanceof Error ? error.message : String(error);
  return (
    <div className="rounded-lg border border-[var(--danger)] bg-[var(--surface)] p-6">
      <h2 className="font-semibold">No pudimos cargar estos datos</h2>
      <p className="mt-1 text-sm text-[var(--muted)]">{message}</p>
      <p className="mt-3 text-sm text-[var(--muted)]">
        Reintenta en unos segundos. Si el problema continúa, revisa la conexión local de HT Lens.
      </p>
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="p-10 text-center text-sm text-[var(--muted)]">{children}</div>;
}
