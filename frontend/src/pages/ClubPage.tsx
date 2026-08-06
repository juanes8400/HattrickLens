import { Chart } from "../charts/Chart";
import { timelineOption } from "../charts/chartOptions";
import { DateRangeFilter, useDateRangeFilter } from "../components/DateRangeFilter";
import { ErrorState, GaugeBar, Kpi, Loading, Note, Panel } from "../components/Panels";
import { useClub } from "../hooks/useTeam";
import { date } from "../hooks/useFormat";

/** Club y staff: las tres subpestañas de Hattrick Control reunidas sin perder
 * la distinción entre dato actual y serie observada. */
export function ClubPage() {
  const { data, isLoading, isError, error } = useClub();

  const moodLabels = (data?.moodHistory ?? []).map((item) => date(item.capturedAt));
  const fanLabels = (data?.supporterHistory ?? []).map((item) => date(item.capturedAt));
  const staffLabels = (data?.staffHistory ?? []).map((item) => date(item.capturedAt));
  const mood = useDateRangeFilter(moodLabels);
  const fan = useDateRangeFilter(fanLabels);
  const staffRange = useDateRangeFilter(staffLabels);

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

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
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
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Ánimo competitivo" meta={`${data.moodHistory.length} lectura(s)`}>
          {hasMoodHistory ? (
            <>
              <div className="border-b border-[var(--border)] px-4 py-2">
                <DateRangeFilter range={mood.range} onChange={mood.setRange} min={mood.min} max={mood.max} />
              </div>
              <Chart
                ariaLabel="Evolución observada de espíritu y confianza"
                option={timelineOption(pick(moodLabels, mood.indices), [
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

        <Panel title="Afición y patrocinadores" meta={`${data.supporterHistory.length} lectura(s)`}>
          {hasFanHistory ? (
            <>
              <div className="border-b border-[var(--border)] px-4 py-2">
                <DateRangeFilter range={fan.range} onChange={fan.setRange} min={fan.min} max={fan.max} />
              </div>
              <Chart
                ariaLabel="Socios y popularidad de aficionados y patrocinadores"
                option={{
                  legend: { bottom: 0 },
                  grid: { left: 48, right: 48, top: 24, bottom: 40, containLabel: true },
                  xAxis: { type: "category", data: pick(fanLabels, fan.indices), boundaryGap: false },
                  yAxis: [
                    { type: "value", name: "Socios", splitLine: { lineStyle: { opacity: 0.15 } } },
                    { type: "value", name: "Popularidad", min: 0, max: 9 },
                  ],
                  dataZoom: [{ type: "inside" }],
                  series: [
                    { name: "Socios", type: "line", data: pick(data.supporterHistory.map((item) => item.fanClubSize), fan.indices), smooth: true },
                    { name: "Afición", type: "line", yAxisIndex: 1, data: pick(data.supporterHistory.map((item) => item.supportersPopularity), fan.indices), smooth: true },
                    { name: "Patrocinadores", type: "line", yAxisIndex: 1, data: pick(data.supporterHistory.map((item) => item.sponsorsPopularity), fan.indices), smooth: true },
                  ],
                }}
                height={240}
              />
            </>
          ) : (
            <Note>
              {current.sponsors ? `Patrocinadores: ${current.sponsors.popularityLabel}. ` : ""}
              El histórico aparecerá al acumular sincronizaciones.
            </Note>
          )}
        </Panel>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(18rem,0.72fr)]">
        <Panel title="Cuerpo técnico" meta={staff ? `lectura ${date(staff.capturedAt)}` : "sin dato"}>
          {staff ? (
            <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3">
              {staff.roles.map((role) => <GaugeBar key={role.key} label={role.label} value={role.level} max={10} />)}
            </div>
          ) : <Note>Sincroniza el club para cargar stafflist y la distribución del cuerpo técnico.</Note>}
        </Panel>

        <Panel title="Entrenador">
          {staff ? (
            <dl className="space-y-3 p-4 text-sm">
              <div className="flex justify-between gap-4"><dt className="text-[var(--muted)]">Tipo</dt><dd>{staff.trainer.typeLabel}</dd></div>
              <div className="flex justify-between gap-4"><dt className="text-[var(--muted)]">Nivel</dt><dd>{staff.trainer.skillLevel}/5</dd></div>
              <div className="flex justify-between gap-4"><dt className="text-[var(--muted)]">Liderazgo</dt><dd>{staff.trainer.leadership}</dd></div>
              <div className="flex justify-between gap-4"><dt className="text-[var(--muted)]">Inversión juvenil</dt><dd>{staff.youthInvestment.toLocaleString("es-CO")}</dd></div>
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
            ariaLabel="Evolución observada de niveles del cuerpo técnico"
            option={timelineOption(
              pick(staffLabels, staffRange.indices),
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
