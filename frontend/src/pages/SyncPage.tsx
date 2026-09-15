import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ErrorState, Note, Panel } from "../components/Panels";
import { SyncProgressPanel } from "../components/SyncProgressPanel";
import { TEAM_ID, useDashboard } from "../hooks/useTeam";
import { relative } from "../hooks/useFormat";
import { api, type SyncResult } from "../services/api";

import { tx } from "../i18n/tx";
/**
 * Sincronización, pantalla única, pedida explícitamente 2026-08-15:
 * "en una única pantalla, no se debe sincronizar en cualquier lado de la
 * herramienta sino solo en la pantalla sincronización".
 *
 * LO DE «Y DE INMEDIATO ME DEBE LLEVAR A CAMBIOS» SE RETIRÓ el 2026-09-09, a
 * petición del mismo usuario y por lo que el salto provocaba: «de una me
 * lleva a la pantalla Cambios y es imposible ver qué es lo que me está
 * reportando que encontró». La sincronización termina, se lleva la pantalla
 * por delante, y el informe que acababa de producir no lo ve nadie.
 *
 * Ahora se queda donde está, cuenta lo que encontró, y ofrece el enlace. Ir a
 * Cambios sigue siendo un clic; no ir también.
 *
 * 2026-08-21, por reportes de usuarios: antes había tres cargas sueltas
 * (fichas de jugador, detalles de partido, historial de transferencias) que
 * obligaban a decidir cuál hacía falta. Nadie puede saber eso sin conocer por
 * dentro qué fichero alimenta qué pantalla, así que las dos primeras entran
 * ahora en el botón normal: se trae todo, y lo que ya está guardado no se
 * vuelve a pedir.
 *
 * 2026-09-13: el barrido de comisiones de reventa también dejó de tener botón.
 * El servidor revisa un lote pequeño al final de cada sincronización.
 */

export function SyncPage() {
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
    onSuccess: async (syncResult) => {
      setResult(syncResult);
      qc.invalidateQueries();
      // Las comisiones ya no tienen botón (2026-09-13, pedido del usuario):
      // el servidor revisa un lote pequeño al final de cada sincronización y
      // lo que encuentra llega en este mismo informe.
      setProgressLog(null);
    },
    onError: () => setProgressLog(null),
  });

  const running = fullSync.isPending;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">{tx("Sincronización")}</h1>
        <p className="prosa text-sm text-[var(--muted)]">
          {tx(
            "El único lugar desde donde se traen datos de Hattrick. Al terminar se queda aquí y te dice qué encontró.",
          )}
        </p>
      </header>

      <Panel
        title={tx("Sincronizar con Hattrick")}
        meta={tx("última: {{v0}}", {
          v0: relative(dashboard?.syncedAt ?? null),
        })}
      >
        <div className="space-y-3 p-4">
          <p className="prosa text-sm text-[var(--muted)]">
            {tx(
              "Trae todo: plantilla, fichas de cada jugador, entrenamiento, economía, calendario, detalles y calificaciones de los partidos, clasificación, club y cuerpo técnico. Lo que ya está guardado no se vuelve a pedir, así que la primera vez tarda bastante más que las siguientes.",
            )}
          </p>
          <p className="prosa text-sm text-[var(--muted)]">
            <b className="text-[var(--text)]">
              {tx("Tus compras y tus ventas se traen aquí.")}
            </b>{" "}
            {tx(
              "Cada vez que sincronizas se revisa tu libro de transferencias desde lo último que ya tenías, así que cuesta una página cuando no hay nada nuevo. También busca, poco a poco, las comisiones que te dejan tus ex-jugadores cuando los revenden.",
            )}
          </p>
          <button
            onClick={() => fullSync.mutate()}
            disabled={running}
            className="rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {fullSync.isPending
              ? tx("Sincronizando…")
              : tx("Sincronizar ahora")}
          </button>
          {dashboard?.stale && !fullSync.isPending && (
            <p className="text-xs text-[var(--warning)]">
              {tx("Tus datos tienen más de un día.")}
            </p>
          )}
        </div>
      </Panel>

      {progressLog && <SyncProgressPanel lines={progressLog} />}

      {fullSync.isError && <ErrorState error={fullSync.error} />}

      {result?.status === "partial" && (
        <Note>
          {tx("Sincronización parcial:")} {result.errors.join(" · ")}
        </Note>
      )}

      {result && !fullSync.isPending && (
        <ResumenDeLaSincronizacion result={result} />
      )}
    </div>
  );
}

/** Qué encontró la sincronización que acaba de terminar.
 *
 *  Existe porque el salto automático a Cambios se llevaba por delante el
 *  informe (2026-09-09, el usuario: «es imposible ver qué es lo que me está
 *  reportando que encontró»). No repite Cambios --allí está el detalle, con
 *  sus ventanas de tiempo y su comparación por jugador--: aquí sólo se dice
 *  cuántos y de qué, que es lo que se quiere saber en el segundo siguiente a
 *  pulsar el botón.
 */
function ResumenDeLaSincronizacion({ result }: { result: SyncResult }) {
  const porCategoria = new Map<string, number>();
  for (const cambio of result.changes) {
    porCategoria.set(
      cambio.category,
      (porCategoria.get(cambio.category) ?? 0) + 1,
    );
  }
  const lineas = [...porCategoria.entries()].sort((a, b) => b[1] - a[1]);

  return (
    <Panel
      title={tx("Lo que encontró")}
      meta={tx("{{v0}} ficha(s) guardada(s) · {{v1}} sin cambios", {
        v0: result.snapshotsWritten,
        v1: result.unchanged,
      })}
    >
      <div className="space-y-3 p-4">
        {lineas.length === 0 ? (
          <p className="prosa text-sm text-[var(--muted)]">
            {tx(
              "Nada nuevo desde la última vez. No es un fallo: quiere decir que lo que hay guardado ya estaba al día.",
            )}
          </p>
        ) : (
          <>
            <div className="flex flex-wrap gap-2">
              {lineas.map(([categoria, cuantos]) => (
                <span
                  key={categoria}
                  className="rounded-full bg-[var(--surface-2)] px-3 py-1 text-xs"
                >
                  <b className="tabular-nums">{cuantos}</b>{" "}
                  <span className="text-[var(--muted)]">{categoria}</span>
                </span>
              ))}
            </div>
            <p className="prosa text-sm text-[var(--muted)]">
              {tx(
                "El detalle --qué jugador, cuánto subió, qué dejó cada venta-- está en Cambios, con sus ventanas de tiempo.",
              )}
            </p>
          </>
        )}
        <Link
          to="/news"
          className="inline-flex rounded-md border border-[var(--border)] px-3 py-1.5 text-sm hover:border-[var(--accent)] hover:text-[var(--accent)]"
        >
          {tx("Ver los cambios")}
        </Link>
      </div>
    </Panel>
  );
}
