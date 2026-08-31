import { useMemo, useState } from "react";
import {
  useArchiveInsight,
  useArchivedInsights,
  useInsights,
  useRestoreInsight,
} from "../hooks/useTeam";
import { Empty, ErrorState, Loading, Panel } from "../components/Panels";
import { InsightRow, SEVERITIES, SeverityTally } from "../components/Insights";
import { relative } from "../hooks/useFormat";
import type { Insight } from "../services/api";

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
  const archived = useArchivedInsights();
  const archive = useArchiveInsight();
  const restore = useRestoreInsight();
  const [activeSeverities, setActiveSeverities] = useState<Set<Insight["severity"]>>(
    new Set(SEVERITIES),
  );
  const [activeModule, setActiveModule] = useState<string>("__all__");

  const byModule = useMemo(() => {
    const acc: Record<string, number> = {};
    for (const i of data ?? []) acc[i.module] = (acc[i.module] ?? 0) + 1;
    return acc;
  }, [data]);

  const modules = useMemo(
    () => Object.keys(byModule).sort((a, b) => a.localeCompare(b)),
    [byModule],
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
          academia y tu cuerpo técnico, ordenadas por urgencia
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-2">
        <SeverityTally
          insights={data ?? []}
          onSelect={toggleSeverity}
          active={activeSeverities}
        />

        {modules.length > 1 && (
          <select
            aria-label="Filtrar las alertas por módulo"
            value={activeModule}
            onChange={(e) => setActiveModule(e.target.value)}
            className="ml-auto rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-xs"
          >
            <option value="__all__">Todos los módulos ({data?.length ?? 0})</option>
            {modules.map((mod) => (
              <option key={mod} value={mod}>
                {mod} ({byModule[mod]})
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
                <InsightRow
                  key={i.key}
                  insight={i}
                  onArchive={archive.mutate}
                  busy={archive.isPending}
                />
              ))}
            </ul>
          ) : (
            <Empty>Ninguna alerta activa coincide con el filtro.</Empty>
          )
        ) : (
          <Empty>Nada requiere tu atención ahora mismo.</Empty>
        )}
      </Panel>

      {/* El buzón solo aparece cuando hay algo dentro: un panel vacío
          permanente sería ruido en una pantalla que ya tiene filtros. */}
      {archived.data?.length ? (
        <Panel title="Buzón" meta={`${archived.data.length} archivada${archived.data.length === 1 ? "" : "s"}`}>
          <ul>
            {archived.data.map((i) => (
              <InsightRow
                key={i.key}
                insight={i}
                onRestore={restore.mutate}
                busy={restore.isPending}
                meta={
                  i.stillActive
                    ? `Archivada ${relative(i.dismissedAt)} · la condición sigue vigente`
                    : `Archivada ${relative(i.dismissedAt)} · ya no se cumple`
                }
              />
            ))}
          </ul>
          <p className="border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
            Archivar no apaga la regla: si la misma alerta se vuelve a generar con otra cifra
            u otra severidad, vuelve sola a la lista de arriba.
          </p>
        </Panel>
      ) : null}
    </div>
  );
}
