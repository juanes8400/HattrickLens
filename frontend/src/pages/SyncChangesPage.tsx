import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { SyncComparisonReport } from "../components/SyncComparisonReport";
import { SyncChangesFeed } from "../components/SyncChangesFeed";
import { ErrorState, Kpi, Loading, Note, Panel } from "../components/Panels";
import { Chart } from "../charts/Chart";
import { PlayerLink } from "../components/PlayerLink";
import { TEAM_ID, useChangesHistory, useSquad, useSyncChanges } from "../hooks/useTeam";
import { date, relative } from "../hooks/useFormat";
import { api, type HistoricalPlayerChange, type SyncResult } from "../services/api";

function countPlayerPops(changes: SyncResult["changes"]): number {
  return changes.filter((c) => {
    const s = c.summary.toLowerCase();
    return c.category === "jugadores" && (s.includes("subio") || s.includes("subió"));
  }).length;
}

function countReportSkillPops(data: NonNullable<ReturnType<typeof useSyncChanges>["data"]>): number {
  const skillKeys = new Set([
    "keeper",
    "defending",
    "playmaking",
    "winger",
    "passing",
    "scoring",
    "set_pieces",
  ]);
  return data.summary
    .filter((metric) => skillKeys.has(metric.key))
    .reduce((total, metric) => total + metric.upCount, 0);
}

function actionItems(changes: SyncResult["changes"]): { title: string; detail: string; tone: "positive" | "danger" | undefined }[] {
  const items: { title: string; detail: string; tone: "positive" | "danger" | undefined }[] = [];
  const lower = changes.map((c) => ({ ...c, text: c.summary.toLowerCase() }));
  const pops = lower.filter((c) => c.category === "jugadores" && (c.text.includes("subio") || c.text.includes("subió")));
  const injuries = lower.filter((c) => c.text.includes("lesion"));
  const market = lower.filter((c) => c.text.includes("mercado"));
  const salary = lower.filter((c) => c.text.includes("salario"));
  const finishedMatches = lower.filter((c) => c.category === "partidos");
  const training = lower.filter((c) => c.category === "entrenamiento");

  if (pops.length > 0) {
    items.push({
      title: `${pops.length} subida(s) de habilidad`,
      detail: "Revisa valor, ventana de venta y si conviene cambiar el plan de entrenamiento.",
      tone: "positive",
    });
  }
  if (injuries.length > 0) {
    items.push({
      title: `${injuries.length} cambio(s) de lesion`,
      detail: "Vuelve a calcular alineacion y banquillo antes del proximo partido.",
      tone: "danger",
    });
  }
  if (market.length > 0) {
    items.push({
      title: `${market.length} movimiento(s) de mercado`,
      detail: "Confirma si el jugador listado sigue encajando con tu economia y plan deportivo.",
      tone: undefined,
    });
  }
  if (salary.length > 0) {
    items.push({
      title: `${salary.length} cambio(s) de salario`,
      detail: "Mira impacto en balance estructural y presion de caja.",
      tone: undefined,
    });
  }
  if (finishedMatches.length > 0) {
    items.push({
      title: `${finishedMatches.length} resultado(s) nuevo(s)`,
      detail: "Abre Partidos para ver sectores, posesion y conversion.",
      tone: undefined,
    });
  }
  if (training.length > 0) {
    items.push({
      title: "Cambio de entrenamiento detectado",
      detail: "Revisa Novedades y Entrenamiento para validar si el nuevo plan aprovecha los minutos jugados.",
      tone: undefined,
    });
  }
  if (items.length === 0 && changes.length === 0) {
    items.push({
      title: "Todo esta al dia",
      detail: "El sync no encontro diferencias reales contra el snapshot anterior.",
      tone: "positive",
    });
  }
  return items;
}

export function SyncChangesPage() {
  const { data, isLoading, isError, error } = useSyncChanges();
  const squad = useSquad();
  const qc = useQueryClient();
  const [selectedPlayerId, setSelectedPlayerId] = useState<number | null>(null);
  const history = useChangesHistory(selectedPlayerId);
  const effectiveSelectedPlayerId = selectedPlayerId ?? history.data?.selectedPlayerId ?? null;

  const fullSync = useMutation({
    mutationFn: async () => {
      const sync = await api.sync(TEAM_ID);
      const playerDetails = await api.syncPlayerDetails(TEAM_ID);
      const matchDetails = await api.syncMatchDetails(TEAM_ID);
      return { sync, playerDetails, matchDetails };
    },
    onSuccess: () => qc.invalidateQueries(),
  });

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;

  const changes = fullSync.data?.sync.changes ?? data?.changes ?? [];
  const syncResult = fullSync.data?.sync;
  const actions = actionItems(changes);
  const playerLinks = Object.fromEntries(
    (squad.data?.players ?? []).map((p) => [p.name, p.htPlayerId]),
  );

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Cambios</h1>
          <p className="text-sm text-[var(--muted)]">
            Último sync y archivo histórico: los cambios se comparan contra el cierre semanal anterior.
          </p>
        </div>
        <button
          onClick={() => fullSync.mutate()}
          disabled={fullSync.isPending}
          className="rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white disabled:opacity-60"
        >
          {fullSync.isPending ? "Sincronizando CHPP..." : "Sync completo + recalcular"}
        </button>
      </header>

      {fullSync.isError && <ErrorState error={fullSync.error} />}

      {fullSync.data && (
        <Panel title="Resultado del sync completo" meta="CHPP real, iniciado por usuario">
          <div className="grid gap-4 p-4 sm:grid-cols-3">
            <Kpi
              label="Sync normal"
              value={fullSync.data.sync.status}
              hint={`${fullSync.data.sync.snapshotsWritten} escritos · ${fullSync.data.sync.unchanged} sin cambios`}
              tone={fullSync.data.sync.status === "completed" ? "positive" : "danger"}
            />
            <Kpi
              label="Playerdetails"
              value={String(fullSync.data.playerDetails.playersProcessed)}
              hint={`${fullSync.data.playerDetails.snapshotsWritten} actualizados`}
            />
            <Kpi
              label="Matchdetails"
              value={String(fullSync.data.matchDetails.matchesProcessed)}
              hint={`${fullSync.data.matchDetails.snapshotsWritten} escritos`}
            />
          </div>
          {[
            ...fullSync.data.sync.errors,
            ...fullSync.data.playerDetails.errors,
            ...fullSync.data.matchDetails.errors,
          ].length > 0 && (
            <Note>
              Errores:{" "}
              {[
                ...fullSync.data.sync.errors,
                ...fullSync.data.playerDetails.errors,
                ...fullSync.data.matchDetails.errors,
              ].join(" · ")}
            </Note>
          )}
        </Panel>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi label="Último sync" value={relative(data?.syncedAt ?? null)} />
        <Kpi label="Cambios nuevos" value={String(changes.length)} />
        <Kpi label="Jugadores comparados" value={String(data?.playerRows.length ?? 0)} />
        <Kpi
          label="Subidas de habilidad"
          value={String(data ? countReportSkillPops(data) : countPlayerPops(changes))}
        />
      </div>

      {data && !data.reportIsLatest && (
        <Note>
          El último sync confirmó que todo sigue igual. Para que una sincronización repetida no
          borre información útil, conservamos la última variación real detectada {relative(data.reportSyncedAt)}.
        </Note>
      )}

      {data && <SyncComparisonReport data={data} />}

      {history.isError && <ErrorState error={history.error} />}
      {history.data && (
        <HistoricalChanges
          data={history.data}
          selectedPlayerId={effectiveSelectedPlayerId}
          onSelectPlayer={setSelectedPlayerId}
        />
      )}

      {actions.length > 0 && (
        <Panel title="Que haria ahora" meta="resumen accionable">
          <div className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-3">
            {actions.map((item) => (
              <div key={item.title} className="rounded-lg border border-[var(--border)] bg-[var(--bg)] p-3">
                <div
                  className={
                    item.tone === "positive"
                      ? "text-sm font-semibold text-[var(--positive)]"
                      : item.tone === "danger"
                        ? "text-sm font-semibold text-[var(--danger)]"
                        : "text-sm font-semibold"
                  }
                >
                  {item.title}
                </div>
                <p className="mt-1 text-xs leading-relaxed text-[var(--muted)]">{item.detail}</p>
              </div>
            ))}
          </div>
        </Panel>
      )}

      {changes.length > 0 ? (
        <SyncChangesFeed changes={changes} playerLinks={playerLinks} onDismiss={() => undefined} />
      ) : null}

      {syncResult?.changes.length === 0 && syncResult.status === "completed" && (
        <Note>
          Sync completado sin diferencias: eso es bueno. La base confirmó que ya estaba al día.
        </Note>
      )}
    </div>
  );
}

const dateLabel = date;

function signed(value: number): string {
  return `${value > 0 ? "+" : ""}${value}`;
}

function HistoricalChangeTable({
  title,
  events,
}: {
  title: string;
  events: HistoricalPlayerChange[];
}) {
  return (
    <Panel title={title} meta={`${events.length} registro(s)`}>
      {events.length === 0 ? (
        <Note>Aún no hay dos snapshots distintos para detectar cambios.</Note>
      ) : (
        <div className="max-h-80 overflow-auto">
          <table className="w-full min-w-[420px] text-left text-xs">
            <thead className="sticky top-0 bg-[var(--surface-2)] text-[var(--muted)]">
              <tr>
                <th className="px-3 py-2 font-medium">Fecha</th>
                <th className="px-3 py-2 font-medium">Jugador</th>
                <th className="px-3 py-2 font-medium">Cambio</th>
                <th className="px-3 py-2 text-right font-medium">Antes</th>
                <th className="px-3 py-2 text-right font-medium">Ahora</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {events.map((event, index) => (
                <tr key={`${event.htPlayerId}-${event.capturedAt}-${event.key}-${index}`}>
                  <td className="px-3 py-2 whitespace-nowrap text-[var(--muted)]">{dateLabel(event.capturedAt)}</td>
                  <td className="px-3 py-2"><PlayerLink htPlayerId={event.htPlayerId} name={event.name} /></td>
                  <td className="px-3 py-2 font-medium">{event.label}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{event.before}</td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    <span className={event.delta > 0 ? "text-[var(--positive)]" : "text-[var(--danger)]"}>
                      {event.current} ({signed(event.delta)})
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

function HistoricalChanges({
  data,
  selectedPlayerId,
  onSelectPlayer,
}: {
  data: NonNullable<ReturnType<typeof useChangesHistory>["data"]>;
  selectedPlayerId: number | null;
  onSelectPlayer: (playerId: number) => void;
}) {
  const selected = data.players.find((player) => player.htPlayerId === selectedPlayerId);
  const timeline = data.series;

  return (
    <section className="space-y-4">
      <header>
        <h2 className="text-lg font-semibold">Histórico de cambios</h2>
        <p className="text-sm text-[var(--muted)]">
          Diferencias de la última semana entre cierres semanales CHPP — más antiguo no se muestra
          aquí, pero sigue guardado en el histórico crudo del jugador.
        </p>
      </header>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(20rem,0.75fr)]">
        <div className="grid gap-4 md:grid-cols-2">
          <HistoricalChangeTable title="Habilidades y condición" events={data.skillChanges} />
          <HistoricalChangeTable title="Forma" events={data.formChanges} />
        </div>
        <HistoricalChangeTable title="Experiencia" events={data.experienceChanges} />
      </div>

      <Panel title="Evolución de jugador" meta="TSI, salario y atributos observados">
        <div className="border-b border-[var(--border)] p-4">
          <label className="text-xs text-[var(--muted)]">
            Jugador
            <select
              value={selectedPlayerId ?? ""}
              onChange={(event) => onSelectPlayer(Number(event.target.value))}
              className="ml-2 rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-sm text-[var(--text)]"
            >
              {data.players.map((player) => (
                <option key={player.htPlayerId} value={player.htPlayerId}>{player.name}</option>
              ))}
            </select>
          </label>
          {selected && <span className="ml-3 text-sm text-[var(--muted)]">{selected.name}</span>}
        </div>
        {timeline.length < 2 ? (
          <Note>Falta otra lectura de este jugador para dibujar su evolución.</Note>
        ) : (
          <Chart
            ariaLabel="Evolución de TSI, salario, forma, experiencia y condición del jugador elegido"
            height={300}
            option={{
              tooltip: { trigger: "axis" },
              legend: { bottom: 0 },
              xAxis: { type: "category", data: timeline.map((point) => dateLabel(point.capturedAt)) },
              yAxis: [
                { type: "value", name: "TSI / salario", splitLine: { lineStyle: { opacity: 0.15 } } },
                { type: "value", name: "nivel", min: 0, max: 20 },
              ],
              series: [
                { name: "TSI", type: "line", data: timeline.map((point) => point.tsi), smooth: true },
                { name: "Salario", type: "line", data: timeline.map((point) => point.salary), smooth: true },
                { name: "Forma", type: "line", yAxisIndex: 1, data: timeline.map((point) => point.form) },
                { name: "Experiencia", type: "line", yAxisIndex: 1, data: timeline.map((point) => point.experience) },
                { name: "Condición", type: "line", yAxisIndex: 1, data: timeline.map((point) => point.stamina) },
              ],
            }}
          />
        )}
      </Panel>
    </section>
  );
}
