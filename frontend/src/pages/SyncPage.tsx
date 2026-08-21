import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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

  // Relleno del pasado: la ficha completa de cada ex-jugador (nacionalidad,
  // carácter, precio de compra antiguo, país al que se fue). Es una llamada a
  // Hattrick por jugador, así que va por lotes: cada vuelta termina lo que
  // empieza y la barra dice cuánto falta.
  const pendientes = useQuery({
    queryKey: ["backfill-pending", TEAM_ID],
    queryFn: () => api.backfillPending(TEAM_ID),
  });
  const [relleno, setRelleno] = useState<{
    total: number;
    hechos: number;
    quedan: number;
    error: string | null;
  } | null>(null);
  const pararRef = useRef(false);
  const [rellenando, setRellenando] = useState(false);

  const completarFichas = async () => {
    const inicio = pendientes.data?.pending ?? 0;
    if (inicio === 0) return;
    pararRef.current = false;
    setRellenando(true);
    setRelleno({ total: inicio, hechos: 0, quedan: inicio, error: null });
    let hechos = 0;
    try {
      // Vuelta a vuelta hasta acabar. Cada lote es una petición corta e
      // independiente: si algo se corta, lo ya descargado se queda guardado y
      // al volver a pulsar se sigue donde iba, nunca desde el principio.
      let quedabanAntes = inicio;
      for (;;) {
        if (pararRef.current) break;
        const lote = await api.runBackfillBatch(TEAM_ID);
        hechos += lote.done;
        setRelleno({
          total: inicio,
          hechos: Math.min(hechos, inicio),
          quedan: lote.pending,
          error: lote.errors[0] ?? null,
        });
        if (lote.pending === 0 || lote.done === 0) break;
        // Freno de mano: si una vuelta no reduce lo que queda, es que algo no
        // se puede resolver y volvería a salir en la siguiente. Sin esto el
        // bucle no terminaría nunca — pasó de verdad, con la barra marcando
        // "55 de 11".
        if (lote.pending >= quedabanAntes) break;
        quedabanAntes = lote.pending;
      }
    } catch (reason) {
      setRelleno((previo) =>
        previo ? { ...previo, error: errorMessage(reason) } : previo,
      );
    } finally {
      setRellenando(false);
      await pendientes.refetch();
      qc.invalidateQueries();
    }
  };

  // Transferencias solo se habilita despues de la primera sincronizacion:
  // el recorrido del pasado necesita saber cual es tu equipo, y eso lo
  // establece la sincronizacion normal.
  const yaSincronizo = Boolean(dashboard?.syncedAt);
  const running = fullSync.isPending || rellenando;

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

      <Panel
        title="Transferencias"
        meta={
          pendientes.data
            ? pendientes.data.pending === 0
              ? "todo al día"
              : `faltan ${pendientes.data.pending} jugador(es)`
            : "contando…"
        }
      >
        <div className="space-y-3 p-4">
          <p className="text-sm text-[var(--muted)]">
            Todo tu pasado en un botón: primero el libro de compras y ventas —de donde
            salen los jugadores que esta aplicación nunca vio— y después, de cada uno, su
            ficha completa:
            nacionalidad (de ahí salen las banderas), carácter, precio de compra antiguo
            y a qué club se fue. Es una consulta a Hattrick por jugador, así que va por
            tandas y se puede parar cuando quieras.
          </p>
          <p className="text-sm text-[var(--muted)]">
            <b>Con posible comisión futura</b> son los ex-jugadores que todavía pueden
            darte dinero: a los normales les toca cobrar en la próxima venta del club que
            te los compró, y a los de tu cantera en todas las que vengan. Se revisan cada
            vez que pulses, y en cuanto uno cobra —o lo despiden— desaparece de esa
            cuenta para siempre. <b>Historial por construir</b> es el recorrido pesado:
            partido a partido, en cuáles jugó al menos un minuto contigo. Es lo que fija
            la comisión que te correspondería, y se hace una sola vez en la vida de cada
            jugador.
          </p>

          {pendientes.data && (
            <dl className="grid gap-2 rounded-md border border-[var(--border)] bg-[var(--bg)] p-3 text-xs sm:grid-cols-2">
              <div className="flex items-baseline justify-between gap-3">
                <dt className="text-[var(--muted)]">Con posible comisión futura</dt>
                <dd className="tabular-nums font-semibold">
                  {pendientes.data.detail.resaleWatch} jugador(es)
                </dd>
              </div>
              <div className="flex items-baseline justify-between gap-3">
                <dt className="text-[var(--muted)]">Historial por construir</dt>
                <dd className="tabular-nums font-semibold">
                  {pendientes.data.detail.census} jugador(es)
                </dd>
              </div>
            </dl>
          )}

          {relleno && (
            <div>
              <div className="mb-1 flex items-baseline justify-between text-xs">
                <span className="text-[var(--muted)]">
                  {relleno.quedan === 0
                    ? "Listo, no queda ninguna"
                    : `${relleno.hechos} de ${relleno.total}`}
                </span>
                <span className="tabular-nums text-[var(--muted)]">
                  {relleno.quedan === 0
                    ? "100%"
                    : `${Math.round((relleno.hechos / Math.max(relleno.total, 1)) * 100)}%`}
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-[var(--surface-2)]">
                <div
                  className="h-full rounded-full bg-[var(--accent)] transition-all duration-300"
                  style={{
                    width: `${
                      relleno.quedan === 0
                        ? 100
                        : Math.min(100, (relleno.hechos / Math.max(relleno.total, 1)) * 100)
                    }%`,
                  }}
                />
              </div>
              {relleno.error && (
                <p className="mt-2 text-xs text-[var(--warning)]">
                  Hattrick falló en alguna ficha: {relleno.error}. Lo descargado se guardó;
                  vuelve a pulsar para seguir.
                </p>
              )}
            </div>
          )}

          {!yaSincronizo && (
            <p className="text-xs text-[var(--warning)]">
              Primero pulsa «Sincronizar ahora»: hasta que la aplicación no sepa cuál es
              tu equipo y quién está hoy en la plantilla, no hay pasado que recorrer.
            </p>
          )}

          <div className="flex flex-wrap gap-2">
            <button
              onClick={completarFichas}
              disabled={
                running || !yaSincronizo || (pendientes.data?.pending ?? 0) === 0
              }
              className="rounded-md border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--text)] hover:border-[var(--accent)] disabled:opacity-60"
            >
              {rellenando
                ? "Descargando…"
                : !yaSincronizo
                  ? "Sincroniza primero"
                  : (pendientes.data?.pending ?? 0) === 0
                    ? "No queda nada por descargar"
                    : `Traer ${pendientes.data?.pending ?? 0} jugador(es)`}
            </button>
            {rellenando && (
              <button
                onClick={() => {
                  pararRef.current = true;
                }}
                className="rounded-md border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--muted)] hover:border-[var(--accent)]"
              >
                Parar
              </button>
            )}
          </div>
        </div>
      </Panel>

    </div>
  );
}
