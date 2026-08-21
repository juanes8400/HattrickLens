import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { ErrorState, Note, Panel } from "../components/Panels";
import { SyncProgressPanel } from "../components/SyncProgressPanel";
import { TEAM_ID, useDashboard } from "../hooks/useTeam";
import { relative } from "../hooks/useFormat";
import { api, errorMessage, type SyncResult } from "../services/api";

/**
 * Sincronización — pantalla única, pedida explícitamente 2026-08-15:
 * "en una única pantalla, no se debe sincronizar en cualquier lado de la
 * herramienta sino solo en la pantalla sincronización y de inmediato me debe
 * llevar a Cambios".
 *
 * 2026-08-21, por reportes de usuarios: antes había tres cargas sueltas
 * (fichas de jugador, detalles de partido, historial de transferencias) que
 * obligaban a decidir cuál hacía falta. Nadie puede saber eso sin conocer por
 * dentro qué fichero alimenta qué pantalla, así que las dos primeras entran
 * ahora en el botón normal: se trae todo, y lo que ya está guardado no se
 * vuelve a pedir.
 *
 * El historial de transferencias sigue aparte a propósito: es la única carga
 * que recorre el pasado entero página a página, y solo hace falta una vez.
 * También es incremental — se para en cuanto llega a lo que ya tenía.
 */

export function SyncPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: dashboard } = useDashboard();
  const [progressLog, setProgressLog] = useState<string[] | null>(null);
  const [result, setResult] = useState<SyncResult | null>(null);

  // Sync completo: es el que importa y el único que redirige. Va por streaming
  // para que se vea qué fichero está bajando, en vez de una espera muda.
  const fullSync = useMutation({
    mutationFn: () =>
      new Promise<SyncResult>((resolve, reject) => {
        setProgressLog([]);
        setResult(null);
        api
          .syncStream(TEAM_ID, (event) => {
            if (event.type === "progress") {
              setProgressLog((current) => [...(current ?? []), event.message]);
            } else if (event.type === "done") {
              resolve(event.result);
            } else {
              reject(new Error(event.message));
            }
          })
          .catch(reject);
      }),
    onSuccess: (syncResult) => {
      setProgressLog(null);
      setResult(syncResult);
      qc.invalidateQueries();
      // "de inmediato me debe llevar a Cambios".
      navigate("/news");
    },
    onError: () => setProgressLog(null),
  });

  const transfers = useMutation({
    mutationFn: () => api.syncTransfersHistory(TEAM_ID),
    onSuccess: () => qc.invalidateQueries(),
  });

  const running = fullSync.isPending || transfers.isPending;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Sincronización</h1>
        <p className="text-sm text-[var(--muted)]">
          El único lugar desde donde se traen datos de Hattrick. Al terminar te lleva a Cambios.
        </p>
      </header>

      <Panel
        title="Sincronizar con Hattrick"
        meta={`última: ${relative(dashboard?.syncedAt ?? null)}`}
      >
        <div className="space-y-3 p-4">
          <p className="text-sm text-[var(--muted)]">
            Trae todo: plantilla, fichas de cada jugador, entrenamiento, economía, calendario,
            detalles y calificaciones de los partidos, clasificación, club y cuerpo técnico. Lo
            que ya está guardado no se vuelve a pedir, así que la primera vez tarda bastante más
            que las siguientes.
          </p>
          <button
            onClick={() => fullSync.mutate()}
            disabled={running}
            className="rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {fullSync.isPending ? "Sincronizando CHPP…" : "Sincronizar ahora"}
          </button>
          {dashboard?.stale && !fullSync.isPending && (
            <p className="text-xs text-[var(--warning)]">
              Tus datos tienen más de un día.
            </p>
          )}
        </div>
      </Panel>

      {progressLog && <SyncProgressPanel lines={progressLog} />}

      {fullSync.isError && <ErrorState error={fullSync.error} />}

      {result?.status === "partial" && (
        <Note>Sincronización parcial: {result.errors.join(" · ")}</Note>
      )}

      <Panel title="Historial de transferencias">
        <div className="flex flex-wrap items-start justify-between gap-3 p-4">
          <div className="max-w-xl">
            <p className="text-sm text-[var(--muted)]">
              Recorre hacia atrás todas tus compras y ventas para recuperar los precios reales,
              incluidos los de temporadas pasadas. Va aparte porque es un recorrido largo por el
              pasado y normalmente solo hace falta una vez: al repetirlo se detiene en cuanto
              llega a lo que ya tenía guardado.
            </p>
          </div>
          <button
            onClick={() => transfers.mutate()}
            disabled={running}
            className="shrink-0 rounded-md border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--text)] hover:border-[var(--accent)] disabled:opacity-60"
          >
            {transfers.isPending ? "Cargando…" : "Traer historial"}
          </button>
        </div>
      </Panel>

      {transfers.isError && (
        <Note>No se pudo completar la carga: {errorMessage(transfers.error)}</Note>
      )}
      {transfers.isSuccess && (
        <Note>
          Historial al día: {transfers.data.transfersNew} operación(es) nueva(s) de{" "}
          {transfers.data.transfersSeen} revisada(s).
        </Note>
      )}
    </div>
  );
}
