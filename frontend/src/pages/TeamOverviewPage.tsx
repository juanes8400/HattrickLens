import { useState } from "react";
import { Chart } from "../charts/Chart";
import { PitchField } from "../components/PitchField";
import { bandBetween, timelineOption, withoutBandInTooltip } from "../charts/chartOptions";
import { Empty, ErrorState, Loading, Note, Panel } from "../components/Panels";
import { useTeamOverview } from "../hooks/useTeam";
import { decimal, money, number } from "../hooks/useFormat";
import type {
  TeamOverviewGroup,
  TeamOverviewMetric,
  TeamOverviewPitchSlot,
  TeamOverviewSpecialRole,
} from "../services/api";

/**
 * Equipo — la plantilla promediada, semana a semana.
 *
 * Cuántas gráficas lleva cada grupo lo decide el backend (`charts`), porque
 * depende de si sus series comparten escala. Habilidades lleva dos: lo que se
 * mide de 0 a 20 arriba, y Resistencia y Forma —escalas mucho más cortas—
 * aparte. TSI y Salario también, por ser un índice y dinero. Juntarlas en un
 * eje daría a entender que se comparan.
 */
function formatValue(metric: TeamOverviewMetric, currency: string): string {
  switch (metric.display) {
    case "money":
      return money(Math.round(metric.value), currency);
    case "number":
      return number(Math.round(metric.value));
    case "count":
      return `${Math.round(metric.value)} jugador${metric.value === 1 ? "" : "es"}`;
    case "ratio":
      // Céntimos por punto de índice: con menos decimales todas las semanas
      // se verían iguales.
      return `${decimal(metric.value, 3)} ${currency}`;
    default:
      return `${decimal(metric.value, 1)} / ${Math.round(metric.scaleMax)}`;
  }
}

function MetricBars({ group, currency }: { group: TeamOverviewGroup; currency: string }) {
  return (
    <div className="space-y-3 p-4">
      {group.metrics.map((metric) => {
        const pct = metric.scaleMax > 0
          ? Math.max(0, Math.min(100, (metric.value / metric.scaleMax) * 100))
          : 0;
        return (
          <div key={metric.key}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span>{metric.label}</span>
              <span className="tabular-nums font-semibold">
                {formatValue(metric, currency)}
              </span>
            </div>
            <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-[var(--surface-2)]">
              <div
                className="h-full rounded-full bg-[var(--accent)]"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function GroupLines({ group }: { group: TeamOverviewGroup }) {
  if (group.weeks.length === 0) {
    return <Empty>Hace falta más de un cierre semanal para dibujar la evolución.</Empty>;
  }

  return (
    <div className="space-y-4 p-4">
      {group.charts.map((chart) => {
        const base = timelineOption(
          group.weeks,
          chart.series.map((s) => ({ name: s.label, values: s.values })),
        );
        // El backend marca con `band` las gráficas cuyas dos líneas miden lo
        // mismo sobre poblaciones distintas: ahí el hueco entre ellas es una
        // cantidad y se sombrea. Las auxiliares se quedan fuera de la leyenda
        // (`data`) y del tooltip.
        const [first, second] = chart.series;
        const banded =
          chart.band && first && second
            ? {
                series: [
                  ...bandBetween(first.values, second.values),
                  ...(base.series as Record<string, unknown>[]),
                ],
                legend: {
                  bottom: 0,
                  type: "scroll" as const,
                  data: chart.series.map((s) => s.label),
                },
                tooltip: withoutBandInTooltip(),
              }
            : {};
        return (
          <div key={chart.key}>
            {chart.title && (
              <div className="mb-1 text-xs font-medium text-[var(--muted)]">{chart.title}</div>
            )}
            <Chart
              ariaLabel={`${chart.title || group.label}, media de la plantilla por semana`}
              height={group.charts.length > 1 ? 260 : 340}
              option={{
                ...base,
                ...banded,
                ...(chart.scaleMax != null
                  ? {
                      yAxis: {
                        type: "value" as const,
                        min: chart.scaleMin ?? 0,
                        max: chart.scaleMax,
                        splitLine: { lineStyle: { opacity: 0.15 } },
                      },
                    }
                  : {}),
              }}
            />
          </div>
        );
      })}
    </div>
  );
}

function PitchSlotCard({ slot }: { slot: TeamOverviewPitchSlot }) {
  const best = slot.bestRating;
  return (
    <div className="w-44 shrink-0 rounded-lg border border-white/20 bg-black/45 p-2 text-center shadow-xl backdrop-blur">
      <div className="text-[11px] text-white/70">{slot.label}</div>

      {/* El número grande es CUÁNTOS tienen esta línea como su mejor puesto
          la lectura que se busca de un vistazo al mirar la cancha. */}
      <div className="mt-0.5 text-3xl font-semibold leading-none tabular-nums text-white">
        {slot.count}
      </div>
      <div className="text-[10px] text-white/50">
        {slot.count === 1 ? "lo tiene como mejor" : "lo tienen como mejor"}
      </div>

      {/* Debajo y en pequeño, el mejor de la línea medido sobre TODA la
          plantilla. Es otra población que el conteo de arriba, por eso la
          línea divisoria. */}
      <div className="mt-1.5 space-y-0.5 border-t border-white/15 pt-1">
        {best == null ? (
          <div className="text-[10px] text-white/40">sin rating</div>
        ) : (
          <>
            {slot.topPlayer && (
              <div className="truncate text-[10px] text-white/80" title={slot.topPlayer}>
                {slot.topPlayer}
              </div>
            )}
            <div className="text-[10px] tabular-nums text-white/70">
              máx {decimal(best, 2)}
              {slot.averageRating != null && ` · media ${decimal(slot.averageRating, 2)}`}
            </div>
            {slot.bestVariantLabel && (
              <div className="truncate text-[10px] text-white/45" title={slot.bestVariantLabel}>
                {slot.bestVariantLabel}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

/** Capitán y lanzador de faltas viven FUERA del campo, en una columna al
 *  lado y con otro aspecto: son recomendaciones de rol, no puestos, y su
 *  puntuación usa otra fórmula — nada de la barra 0-20 de las posiciones. */
function SpecialRoles({ roles }: { roles: TeamOverviewSpecialRole[] }) {
  if (roles.length === 0) return null;
  return (
    <div className="flex shrink-0 flex-col gap-2 sm:w-48">
      <div className="text-[11px] uppercase tracking-wide text-[var(--muted)]">
        Roles del equipo
      </div>
      {roles.map((role) => (
        <div
          key={role.key}
          className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-2"
        >
          <div className="text-[11px] text-[var(--muted)]">{role.label}</div>
          <div className="mt-0.5 truncate text-sm font-medium" title={role.topPlayer ?? ""}>
            {role.topPlayer ?? "-"}
          </div>
          {role.rating != null && (
            <div className="text-[10px] tabular-nums text-[var(--muted)]">
              índice {decimal(role.rating, 1)}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

/** Cancha de portería (abajo) a delantera (arriba), como se lee un campo al
 *  atacar. Extremo y Medio comparten fila, y Lateral con Defensa central,
 *  porque en el campo real ocupan la misma altura. */
function PitchLayout({ group }: { group: TeamOverviewGroup }) {
  const byKey = new Map(group.pitch.map((slot) => [slot.key, slot]));
  const rows: string[][] = [
    ["forward"],
    ["winger", "inner_midfield"],
    ["wingback", "central_defender"],
    ["keeper"],
  ];
  return (
    <div className="flex flex-col gap-4 p-4 lg:flex-row lg:items-start">
      <PitchField
        ariaLabel="Mejor posición de cada jugador sobre la cancha"
        className="min-w-0 flex-1 rounded-xl"
      >
        <div className="relative flex flex-col gap-3 px-4 py-6">
          {rows.map((row) => (
            <div key={row.join("-")} className="flex flex-wrap justify-center gap-3">
              {row.map((key) => {
                const slot = byKey.get(key);
                return slot ? <PitchSlotCard key={key} slot={slot} /> : null;
              })}
            </div>
          ))}
        </div>
      </PitchField>
      <SpecialRoles roles={group.specialRoles} />
    </div>
  );
}

export function TeamOverviewPage() {
  const { data, isLoading, isError, error } = useTeamOverview();
  const [activeKey, setActiveKey] = useState<string | null>(null);

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return null;

  const active = data.groups.find((g) => g.key === activeKey) ?? data.groups[0];
  if (!active) return <Empty>Sincroniza para calcular las medias de la plantilla.</Empty>;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Equipo</h1>
        <p className="text-sm text-[var(--muted)]">
          Media de los {data.playerCount} jugadores de {data.teamName}, semana a semana.
        </p>
      </header>

      <div className="flex flex-wrap gap-1 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-1">
        {data.groups.map((group) => (
          <button
            key={group.key}
            onClick={() => setActiveKey(group.key)}
            className={
              group.key === active.key
                ? "rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white"
                : "rounded-md px-3 py-1.5 text-sm text-[var(--muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text)]"
            }
          >
            {group.label}
          </button>
        ))}
      </div>

      <Panel
        title={active.label}
        meta={
          active.chart === "pending"
            ? "por definir"
            : active.chart === "line"
              ? `${active.weeks.length} semana(s) · ${data.playerCount} jugadores`
              : `${data.playerCount} jugadores`
        }
      >
        {active.chart === "pending" ? (
          <Empty>Esta pestaña todavía no tiene contenido.</Empty>
        ) : active.chart === "line" ? (
          <GroupLines group={active} />
        ) : active.chart === "pitch" ? (
          <PitchLayout group={active} />
        ) : active.metrics.length === 0 ? (
          <Empty>Sincroniza para calcular las medias de la plantilla.</Empty>
        ) : (
          <MetricBars group={active} currency={data.currency} />
        )}
        {active.note && <Note>{active.note}</Note>}
      </Panel>
    </div>
  );
}
