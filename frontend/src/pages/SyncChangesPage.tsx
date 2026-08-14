import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ClubMoraleSection, EconomySection } from "../components/SyncComparisonReport";
import { SyncChangesFeed } from "../components/SyncChangesFeed";
import {
  GroupedPlayerChanges,
  type AggregateMetric,
  type NormalizedChange,
  type PlayerChangeGroup,
} from "../components/GroupedPlayerChanges";
import { ErrorState, Loading, Note, Panel } from "../components/Panels";
import { Tabs } from "../components/Tabs";
import { TEAM_ID, useChangesHistory, useSquad, useSyncChanges } from "../hooks/useTeam";
import { relative } from "../hooks/useFormat";
import {
  api,
  type ChangesHistory,
  type HistoricalPlayerChange,
  type LastSyncChanges,
  type MatchDetailsSyncResult,
  type PlayerDetailsSyncResult,
  type SyncResult,
} from "../services/api";

type FullSyncData = { sync: SyncResult; playerDetails: PlayerDetailsSyncResult; matchDetails: MatchDetailsSyncResult };

function countPlayerPops(changes: SyncResult["changes"]): number {
  return changes.filter((c) => {
    const s = c.summary.toLowerCase();
    return c.category === "jugadores" && (s.includes("subio") || s.includes("subió"));
  }).length;
}

function countReportSkillPops(data: LastSyncChanges): number {
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
  const injuries = lower.filter((c) => c.text.includes("lesion") || c.text.includes("lesión"));
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
      title: `${injuries.length} cambio(s) de lesión`,
      detail: "Vuelve a calcular alineación y banquillo antes del próximo partido.",
      tone: "danger",
    });
  }
  if (market.length > 0) {
    items.push({
      title: `${market.length} movimiento(s) de mercado`,
      detail: "Confirma si el jugador listado sigue encajando con tu economía y plan deportivo.",
      tone: undefined,
    });
  }
  if (salary.length > 0) {
    items.push({
      title: `${salary.length} cambio(s) de salario`,
      detail: "Mira impacto en balance estructural y presión de caja.",
      tone: undefined,
    });
  }
  if (finishedMatches.length > 0) {
    items.push({
      title: `${finishedMatches.length} resultado(s) nuevo(s)`,
      detail: "Abre Partidos para ver sectores, posesión y conversión.",
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
      title: "Todo está al día",
      detail: "La sincronización no encontró diferencias reales contra el snapshot anterior.",
      tone: "positive",
    });
  }
  return items;
}

/** Punto 4 pedido 2026-08-10: esta mecánica de sync es una adenda, no debe
 * competir en importancia con los cambios reales — mismo tratamiento
 * "dashed border, una línea, texto chico" que ya tiene el panel de
 * habilidades susceptibles a mejorar en la ficha del jugador. */
function SyncMetaSummary({
  fullSync,
  data,
  changes,
}: {
  fullSync: FullSyncData | undefined;
  data: LastSyncChanges | undefined;
  changes: SyncResult["changes"];
}) {
  const skillPops = data ? countReportSkillPops(data) : countPlayerPops(changes);
  const errors = fullSync
    ? [...fullSync.sync.errors, ...fullSync.playerDetails.errors, ...fullSync.matchDetails.errors]
    : [];
  return (
    <div className="rounded-lg border border-dashed border-[var(--border)] px-4 py-2 text-xs text-[var(--muted)]">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <span className="font-medium uppercase tracking-wide text-[var(--muted)]">Mecánica de sync</span>
        <span>última: {relative(data?.syncedAt ?? null)}</span>
        <span>cambios nuevos: {changes.length}</span>
        <span>jugadores comparados: {data?.playerRows.length ?? 0}</span>
        <span>subidas de habilidad: {skillPops}</span>
        {fullSync && (
          <>
            <span>
              normal: {fullSync.sync.status} ({fullSync.sync.snapshotsWritten} escritos · {fullSync.sync.unchanged} sin cambios)
            </span>
            <span>playerdetails: {fullSync.playerDetails.playersProcessed} jugadores</span>
            <span>matchdetails: {fullSync.matchDetails.matchesProcessed} partidos</span>
          </>
        )}
      </div>
      {errors.length > 0 && <div className="mt-1 text-[var(--danger)]">Errores: {errors.join(" · ")}</div>}
    </div>
  );
}

function lastSyncGroups(data: LastSyncChanges): PlayerChangeGroup[] {
  return data.playerRows
    .map((row) => {
      const changes: NormalizedChange[] = [];
      if (row.tsiDelta) {
        changes.push({
          key: "tsi",
          label: "TSI",
          before: row.tsi - row.tsiDelta,
          current: row.tsi,
          delta: row.tsiDelta,
          direction: row.tsiDelta > 0 ? "up" : "down",
        });
      }
      if (row.salaryDelta) {
        changes.push({
          key: "salary",
          label: "Salario",
          before: row.salary - row.salaryDelta,
          current: row.salary,
          delta: row.salaryDelta,
          direction: row.salaryDelta > 0 ? "up" : "down",
        });
      }
      for (const change of row.changes) {
        changes.push({
          key: change.key,
          label: change.label,
          before: change.before,
          current: change.current,
          delta: change.delta,
          direction: change.direction,
        });
      }
      return { htPlayerId: row.htPlayerId, name: row.name, changes };
    })
    .filter((group) => group.changes.length > 0);
}

function lastSyncAggregate(data: LastSyncChanges): AggregateMetric[] {
  return data.summary.map((metric) => ({
    key: metric.key,
    label: metric.label,
    upCount: metric.upCount,
    downCount: metric.downCount,
    net: metric.net,
  }));
}

function mergedHistoryEvents(data: ChangesHistory): HistoricalPlayerChange[] {
  return [
    ...data.skillChanges,
    ...data.experienceChanges,
    ...data.loyaltyChanges,
    ...data.formChanges,
  ];
}

function historyGroups(data: ChangesHistory): PlayerChangeGroup[] {
  const byPlayer = new Map<number, PlayerChangeGroup>();
  for (const event of mergedHistoryEvents(data)) {
    const group = byPlayer.get(event.htPlayerId) ?? { htPlayerId: event.htPlayerId, name: event.name, changes: [] };
    group.changes.push({
      key: event.key,
      label: event.label,
      before: event.before,
      current: event.current,
      delta: event.delta,
      direction: event.delta > 0 ? "up" : event.delta < 0 ? "down" : "neutral",
    });
    byPlayer.set(event.htPlayerId, group);
  }
  return [...byPlayer.values()].sort((a, b) => a.name.localeCompare(b.name));
}

function historyAggregate(data: ChangesHistory): AggregateMetric[] {
  const byKey = new Map<string, AggregateMetric>();
  for (const event of mergedHistoryEvents(data)) {
    const metric = byKey.get(event.key) ?? { key: event.key, label: event.label, upCount: 0, downCount: 0, net: 0 };
    metric.net += event.delta;
    if (event.delta > 0) metric.upCount += 1;
    else if (event.delta < 0) metric.downCount += 1;
    byKey.set(event.key, metric);
  }
  return [...byKey.values()];
}

export function SyncChangesPage() {
  const { data, isLoading, isError, error } = useSyncChanges();
  const squad = useSquad();
  const qc = useQueryClient();
  const history = useChangesHistory();
  const [changesTab, setChangesTab] = useState<"latest" | "history">("latest");

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
            Última sincronización y archivo histórico: los cambios se comparan contra el cierre semanal anterior.
          </p>
        </div>
        <button
          onClick={() => fullSync.mutate()}
          disabled={fullSync.isPending}
          className="rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white disabled:opacity-60"
        >
          {fullSync.isPending ? "Sincronizando CHPP…" : "Sincronizar todo + recalcular"}
        </button>
      </header>

      {fullSync.isError && <ErrorState error={fullSync.error} />}

      <SyncMetaSummary fullSync={fullSync.data} data={data} changes={changes} />

      {data && <EconomySection changes={data.clubChanges} />}

      {data && !data.reportIsLatest && (
        <Note>
          La última sincronización confirmó que todo sigue igual. Para que una sincronización repetida no
          borre información útil, conservamos la última variación real detectada {relative(data.reportSyncedAt)}.
        </Note>
      )}

      <Panel title="Cambios por jugador" meta="jugador por jugador, habilidad por habilidad">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] px-4 py-3">
          <Tabs
            tabs={[
              { key: "latest", label: "Último snapshot" },
              { key: "history", label: "Última semana" },
            ]}
            active={changesTab}
            onChange={setChangesTab}
          />
          <span className="text-xs text-[var(--muted)]">
            {changesTab === "latest"
              ? "última comparación semanal guardada"
              : "últimos 7 días de cierres semanales"}
          </span>
        </div>
        {changesTab === "latest" && data && (
          <GroupedPlayerChanges
            groups={lastSyncGroups(data)}
            aggregate={lastSyncAggregate(data)}
            emptyMessage="No hubo variaciones de jugadores en la última comparación guardada."
          />
        )}
        {changesTab === "history" && history.isError && <ErrorState error={history.error} />}
        {changesTab === "history" && history.data && (
          <GroupedPlayerChanges
            groups={historyGroups(history.data)}
            aggregate={historyAggregate(history.data)}
            emptyMessage="Aún no hay dos cierres semanales distintos para detectar cambios."
          />
        )}
      </Panel>

      {data && <ClubMoraleSection changes={data.clubChanges} />}

      {actions.length > 0 && (
        <Panel title="Qué haría ahora" meta="resumen accionable">
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
          Sincronización completada sin diferencias: eso es bueno. La base confirmó que ya estaba al día.
        </Note>
      )}
    </div>
  );
}
