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
 * Antes había botones de sincronizar repartidos por la app (barra superior,
 * Partidos, Estadio, Transferencias, la propia pantalla de Cambios), cada
 * uno trayendo un subconjunto distinto de ficheros CHPP. El resultado era que
 * nunca sabías qué estaba actualizado: dependía de en qué pantalla habías
 * pulsado por última vez. Aquí se ve todo junto y se decide una sola vez.
 *
 * Al terminar la sincronización completa se navega a Cambios, que es donde
 * está la respuesta a "¿y qué pasó?" — el mismo gesto de Hattrick Control.
 */

type Extra = "playerDetails" | "matchDetails" | "transfers";

const EXTRA_LABELS: Record<Extra, { title: string; detail: string }> = {
  playerDetails: {
    title: "Fichas de jugador",
    detail:
      "playerdetails.xml, uno por jugador: club de origen, carácter, especialidad y último " +
      "partido. Es lo más lento del sync, por eso va aparte.",
  },
  matchDetails: {
    title: "Detalles de partido",
    detail:
      "matchdetails.xml y las calificaciones individuales. Sin esto, Partidos y Estadio no " +
      "pueden mostrar ratings, asistencia ni ocupación.",
  },
  transfers: {
    title: "Historial de transferencias",
    detail:
      "transfersteam.xml paginado: precios reales de compra y venta. Sólo hace falta cuando " +
      "faltan precios antiguos, el sync normal ya detecta las operaciones nuevas.",
  },
};

export function SyncPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: dashboard } = useDashboard();
  const [progressLog, setProgressLog] = useState<string[] | null>(null);
  const [result, setResult] = useState<SyncResult | null>(null);

  // Sync completo: es el que importa y el único que redirige. Va por streaming
  // para que se vea qué fichero está bajando, en vez de una espera muda de 15-20s.
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

  const extras = useMutation({
    mutationFn: async (which: Extra) => {
      if (which === "playerDetails") return api.syncPlayerDetails(TEAM_ID);
      if (which === "matchDetails") return api.syncMatchDetails(TEAM_ID);
      return api.syncTransfersHistory(TEAM_ID);
    },
    onSuccess: () => qc.invalidateQueries(),
  });

  const running = fullSync.isPending || extras.isPending;

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
            Trae plantilla, entrenamiento, economía, calendario, clasificación, club y cuerpo
            técnico, y compara todo contra el snapshot anterior.
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

      <Panel title="Cargas pesadas, sólo cuando hagan falta">
        <div className="divide-y divide-[var(--border)]">
          {(Object.keys(EXTRA_LABELS) as Extra[]).map((key) => (
            <div
              key={key}
              className="flex flex-wrap items-start justify-between gap-3 p-4"
            >
              <div className="max-w-xl">
                <div className="text-sm font-medium">{EXTRA_LABELS[key].title}</div>
                <p className="mt-1 text-xs text-[var(--muted)]">{EXTRA_LABELS[key].detail}</p>
              </div>
              <button
                onClick={() => extras.mutate(key)}
                disabled={running}
                className="shrink-0 rounded-md border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--text)] hover:border-[var(--accent)] disabled:opacity-60"
              >
                {extras.isPending && extras.variables === key ? "Cargando…" : "Cargar"}
              </button>
            </div>
          ))}
        </div>
      </Panel>

      {extras.isError && (
        <Note>No se pudo completar la carga: {errorMessage(extras.error)}</Note>
      )}
      {extras.isSuccess && <Note>Carga completada. Los datos ya están disponibles.</Note>}

      <Note>
        Son cargas pesadas y opcionales: la sincronización normal ya trae el resto.
      </Note>
    </div>
  );
}
