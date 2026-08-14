import { Chart } from "../charts/Chart";
import { proportionalTimelineOption, timelineOption } from "../charts/chartOptions";
import { DateRangeFilter, useDateRangeFilter } from "../components/DateRangeFilter";
import { ErrorState, Kpi, Loading, Note, Panel } from "../components/Panels";
import { StaffRoleCard } from "../components/StaffRoleCard";
import { useClub } from "../hooks/useTeam";
import { date, number } from "../hooks/useFormat";
import { trainerTrainingSpeedPct, trainingStaffLevelColor } from "../utils/staffEffects";
import { skillLevelLabel } from "../utils/skillLevels";

/** Club y staff: las tres subpestañas de Hattrick Control reunidas sin perder
 * la distinción entre dato actual y serie observada. */
export function ClubPage() {
  const { data, isLoading, isError, error } = useClub();

  // Timestamps ISO reales (no el "dd/mm/yyyy" de `date()`) para que el
  // filtro de rango compare fechas correctamente — comparar cadenas
  // "dd/mm/yyyy" como si fueran ISO da resultados sin sentido, mismo
  // patrón ya usado en EconomyPage/PlayerPage.
  const moodTimestamps = (data?.moodHistory ?? []).map((item) => item.capturedAt);
  const fanTimestamps = (data?.supporterHistory ?? []).map((item) => item.capturedAt);
  const staffTimestamps = (data?.staffHistory ?? []).map((item) => item.capturedAt);
  const mood = useDateRangeFilter(moodTimestamps);
  const fan = useDateRangeFilter(fanTimestamps);
  const staffRange = useDateRangeFilter(staffTimestamps);

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return null;

  const { current, staff } = data;
  const hasMoodHistory = data.moodHistory.length > 1;
  const hasFanHistory = data.supporterHistory.length > 1;
  const hasStaffHistory = data.staffHistory.length > 1;
  // Los índices siempre vienen de un arreglo de fechas del mismo largo que
  // `items` (ambos derivados de la misma historia), así que la posición
  // siempre existe.
  const pick = <T,>(items: T[], indices: number[]) => indices.map((i) => items[i] as T);

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Club y cuerpo técnico</h1>
        <p className="text-sm text-[var(--muted)]">
          Estado actual e histórico real de {data.teamName}.
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Kpi
          label="Espíritu del equipo"
          value={current.spirit ? `${current.spirit.label} (${current.spirit.level})` : "Sin dato"}
        />
        <Kpi
          label="Confianza"
          value={current.confidence ? `${current.confidence.label} (${current.confidence.level})` : "Sin dato"}
        />
        <Kpi
          label="Socios"
          value={current.supporters?.fanClubSize.toLocaleString("es-CO") ?? "Sin dato"}
          hint={current.supporters ? `afición: ${current.supporters.popularityLabel}` : undefined}
        />
        <Kpi
          label="Niveles de staff"
          value={staff ? String(staff.totalLevels) : "Sin dato"}
          hint={staff ? `entrenador ${staff.trainer.typeLabel.toLowerCase()} · nivel ${staff.trainer.skillLevel}` : undefined}
        />
        <Kpi
          label="Inversión juvenil"
          value={staff ? number(staff.youthInvestment) : "Sin dato"}
          hint={staff ? `nivel juvenil ${staff.youthLevel}` : undefined}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Ánimo competitivo" meta={`${data.moodHistory.length} lectura(s)`}>
          {hasMoodHistory ? (
            <>
              <div className="border-b border-[var(--border)] px-4 py-2">
                <DateRangeFilter range={mood.range} onChange={mood.setRange} min={mood.min} max={mood.max} />
              </div>
              <Chart
                ariaLabel="Evolución observada de espíritu y confianza, un punto por cada cambio real"
                option={proportionalTimelineOption(pick(moodTimestamps, mood.indices), [
                  { name: "Espíritu", values: pick(data.moodHistory.map((item) => item.spirit), mood.indices) },
                  { name: "Confianza", values: pick(data.moodHistory.map((item) => item.confidence), mood.indices) },
                ])}
                height={240}
              />
            </>
          ) : (
            <Note>Habrá gráfica después de una segunda lectura distinta. La pantalla no inventa un histórico antes de que Lens exista.</Note>
          )}
        </Panel>

        <Panel title="Socios y afición" meta={`${data.supporterHistory.length} lectura(s)`}>
          {hasFanHistory ? (
            <>
              <div className="border-b border-[var(--border)] px-4 py-2">
                <DateRangeFilter range={fan.range} onChange={fan.setRange} min={fan.min} max={fan.max} />
              </div>
              <Chart
                ariaLabel="Evolución observada de socios y popularidad de aficionados, un punto por cada cambio real"
                option={{
                  legend: { bottom: 0, type: "scroll" },
                  grid: { left: 48, right: 48, top: 24, bottom: 40, containLabel: true },
                  xAxis: { type: "time" },
                  yAxis: [
                    { type: "value", name: "Socios", splitLine: { lineStyle: { opacity: 0.15 } } },
                    { type: "value", name: "Popularidad", min: 0, max: 9 },
                  ],
                  dataZoom: [{ type: "inside" }],
                  tooltip: { trigger: "axis" },
                  series: [
                    {
                      name: "Socios", type: "line", symbol: "circle", symbolSize: 6,
                      data: pick(fanTimestamps, fan.indices).map((t, i) => [
                        t, pick(data.supporterHistory.map((item) => item.fanClubSize), fan.indices)[i],
                      ]),
                    },
                    {
                      name: "Afición", type: "line", yAxisIndex: 1, symbol: "circle", symbolSize: 6,
                      data: pick(fanTimestamps, fan.indices).map((t, i) => [
                        t, pick(data.supporterHistory.map((item) => item.supportersPopularity), fan.indices)[i],
                      ]),
                    },
                  ],
                }}
                height={240}
              />
            </>
          ) : (
            <Note>El histórico aparecerá al acumular sincronizaciones con un valor distinto.</Note>
          )}
        </Panel>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(18rem,0.72fr)]">
        <Panel title="Cuerpo técnico" meta={staff ? `lectura ${date(staff.capturedAt)}` : "sin dato"}>
          {staff ? (
            <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3">
              {staff.roles.map((role) => <StaffRoleCard key={role.key} role={role} />)}
            </div>
          ) : <Note>Sincroniza el club para cargar stafflist y la distribución del cuerpo técnico.</Note>}
        </Panel>

        <Panel title="Entrenador">
          {staff ? (
            <dl className="space-y-3 p-4 text-sm">
              <div className="flex justify-between gap-4"><dt className="text-[var(--muted)]">Tipo</dt><dd>{staff.trainer.typeLabel}</dd></div>
              <div className="flex justify-between gap-4">
                <dt className="text-[var(--muted)]">Nivel</dt>
                <dd className={`font-semibold ${trainingStaffLevelColor(staff.trainer.skillLevel)}`}>
                  {staff.trainer.skillLevel}/5
                </dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-[var(--muted)]">Liderazgo</dt>
                <dd>{skillLevelLabel(staff.trainer.leadership, true)} ({staff.trainer.leadership})</dd>
              </div>
              <div className="flex justify-between gap-4 border-t border-[var(--border)] pt-3">
                <dt className="text-[var(--muted)]">Velocidad de entrenamiento</dt>
                <dd className="font-medium text-[var(--positive)]">
                  {trainerTrainingSpeedPct(staff.trainer.skillLevel)}%
                </dd>
              </div>
            </dl>
          ) : <Note>Sin datos de entrenador todavía.</Note>}
        </Panel>
      </div>

      {hasStaffHistory && staff && (
        <Panel title="Evolución del staff" meta={`${data.staffHistory.length} lecturas`}>
          <div className="border-b border-[var(--border)] px-4 py-2">
            <DateRangeFilter
              range={staffRange.range} onChange={staffRange.setRange}
              min={staffRange.min} max={staffRange.max}
            />
          </div>
          <Chart
            ariaLabel="Evolución observada de niveles del cuerpo técnico, eje temporada-semana"
            option={timelineOption(
              pick(
                data.staffHistory.map((item) => item.seasonWeek ?? date(item.capturedAt)),
                staffRange.indices,
              ),
              staff.roles.map((role) => ({
                name: role.label,
                values: pick(
                  data.staffHistory.map((item) =>
                    item.roles.find((historyRole) => historyRole.key === role.key)?.level ?? 0,
                  ),
                  staffRange.indices,
                ),
              })),
            )}
            height={280}
          />
        </Panel>
      )}

      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)]">
        {data.notes.map((note) => <Note key={note}>{note}</Note>)}
      </div>
    </div>
  );
}
