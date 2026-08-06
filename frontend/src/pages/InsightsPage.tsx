import { useMemo, useState } from "react";
import clsx from "clsx";
import { useInsights } from "../hooks/useTeam";
import { Empty, ErrorState, Loading, Panel } from "../components/Panels";
import type { Insight } from "../services/api";

const TONE = {
  danger: "var(--danger)",
  warning: "var(--warning)",
  opportunity: "var(--positive)",
  info: "var(--muted)",
} as const;

const SEVERITY_LABEL: Record<Insight["severity"], string> = {
  danger: "Peligro",
  warning: "Aviso",
  opportunity: "Oportunidad",
  info: "Info",
};

const SEVERITIES: Insight["severity"][] = ["danger", "warning", "opportunity", "info"];

/**
 * Centro de alertas. HL-130.
 *
 * El catálogo de reglas es mucho más grande que lo que cabe en una lista
 * plana cómoda de leer: son decenas de plantillas evaluadas contra cada
 * jugador, cada juvenil, la liga, la copa, el estadio y el cuerpo técnico.
 * Solo se muestran las que realmente disparan con el estado de hoy — pero
 * incluso así, con una plantilla completa puede haber muchas a la vez, así
 * que hacen falta filtros por severidad y por módulo para que siga siendo
 * legible. El orden de urgencia (peligro → aviso → oportunidad → info) lo
 * decide el backend y aquí nunca se reordena, solo se filtra.
 */
export function InsightsPage() {
  const { data, isLoading, isError, error } = useInsights();
  const [activeSeverities, setActiveSeverities] = useState<Set<Insight["severity"]>>(
    new Set(SEVERITIES),
  );
  const [activeModule, setActiveModule] = useState<string>("__all__");

  const counts = useMemo(() => {
    const bySeverity: Record<string, number> = {};
    const byModule: Record<string, number> = {};
    for (const i of data ?? []) {
      bySeverity[i.severity] = (bySeverity[i.severity] ?? 0) + 1;
      byModule[i.module] = (byModule[i.module] ?? 0) + 1;
    }
    return { bySeverity, byModule };
  }, [data]);

  const modules = useMemo(
    () => Object.keys(counts.byModule).sort((a, b) => a.localeCompare(b)),
    [counts.byModule],
  );

  const filtered = useMemo(
    () =>
      (data ?? []).filter(
        (i) =>
          activeSeverities.has(i.severity) &&
          (activeModule === "__all__" || i.module === activeModule),
      ),
    [data, activeSeverities, activeModule],
  );

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;

  function toggleSeverity(s: Insight["severity"]) {
    setActiveSeverities((prev) => {
      const next = new Set(prev);
      if (next.has(s)) next.delete(s);
      else next.add(s);
      // Nunca dejar el filtro vacío: equivale a "todas".
      return next.size === 0 ? new Set(SEVERITIES) : next;
    });
  }

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Alertas</h1>
        <p className="text-sm text-[var(--muted)]">
          Reglas de negocio evaluadas contra tu plantilla, tu liga, tu copa, tu estadio, tu
          academia y tu cuerpo técnico — ordenadas por urgencia
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-2">
        {SEVERITIES.map((s) => {
          const n = counts.bySeverity[s] ?? 0;
          const on = activeSeverities.has(s);
          return (
            <button
              key={s}
              onClick={() => toggleSeverity(s)}
              disabled={n === 0}
              className={clsx(
                "flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs transition",
                on
                  ? "border-[var(--border)] bg-[var(--surface-2)]"
                  : "border-[var(--border)] text-[var(--muted)] opacity-50",
                n === 0 && "cursor-not-allowed opacity-30",
              )}
            >
              <span
                aria-hidden
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ background: TONE[s] }}
              />
              {SEVERITY_LABEL[s]}
              <span className="tabular-nums text-[var(--muted)]">{n}</span>
            </button>
          );
        })}

        {modules.length > 1 && (
          <select
            value={activeModule}
            onChange={(e) => setActiveModule(e.target.value)}
            className="ml-auto rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-xs"
          >
            <option value="__all__">Todos los módulos ({data?.length ?? 0})</option>
            {modules.map((mod) => (
              <option key={mod} value={mod}>
                {mod} ({counts.byModule[mod]})
              </option>
            ))}
          </select>
        )}
      </div>

      <Panel
        title="Centro de alertas"
        meta={
          filtered.length === (data?.length ?? 0)
            ? `${data?.length ?? 0} activas`
            : `${filtered.length} de ${data?.length ?? 0}`
        }
      >
        {data?.length ? (
          filtered.length ? (
            <ul>
              {filtered.map((i) => (
                <li
                  key={i.key}
                  className="flex gap-3 border-b border-[var(--border)] p-4 last:border-0"
                >
                  <span
                    aria-hidden
                    className="mt-1.5 h-2 w-2 shrink-0 rounded-full"
                    style={{ background: TONE[i.severity] }}
                  />
                  <div className="flex-1">
                    <div className="text-sm font-medium">{i.title}</div>
                    <p className="mt-0.5 text-xs leading-relaxed text-[var(--muted)]">
                      {i.detail}
                    </p>
                    {i.action && (
                      <p className={clsx("mt-1.5 text-xs", "text-[var(--accent)]")}>
                        → {i.action}
                      </p>
                    )}
                  </div>
                  <span className="text-[11px] text-[var(--muted)]">{i.module}</span>
                </li>
              ))}
            </ul>
          ) : (
            <Empty>Ninguna alerta activa coincide con el filtro.</Empty>
          )
        ) : (
          <Empty>Nada requiere tu atención ahora mismo.</Empty>
        )}
      </Panel>
    </div>
  );
}
