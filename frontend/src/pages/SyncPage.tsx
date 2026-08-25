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

/** "1 jugador", "454 jugadores". Nunca "jugador(es)". */
const jugadores = (n: number) => `${n} jugador${n === 1 ? "" : "es"}`;

/** Hasta dónde llega el frente: el tramo seguido desde la izquierda que ya
 *  se atendió. Una marca suelta a mitad de la barra no lo empuja — eso es
 *  justo lo que distingue al azar del avance. */
function frente(relleno: {
  marcas: number[];
  escala: number;
  hechos: number;
  total: number;
  quedan: number;
}): number {
  if (relleno.quedan === 0) return 100;
  if (relleno.escala <= 0) {
    return Math.min(100, (relleno.hechos / Math.max(relleno.total, 1)) * 100);
  }
  const vistas = new Set(relleno.marcas);
  let seguidas = 0;
  while (vistas.has(seguidas)) seguidas += 1;
  return Math.min(100, (seguidas / relleno.escala) * 100);
}

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
    ultimo: string | null;
    error: string | null;
    /** Dónde cayó en la cola cada uno de los atendidos, y cuántos había en
     *  esa cola cuando empezó el barrido. La escala se CONGELA en la primera
     *  pulsación: cada jugador atendido sale de la cola, así que si se
     *  repintara con la cola de ahora las marcas viejas se irían corriendo y
     *  la barra bailaría. */
    marcas: number[];
    escala: number;
  } | null>(null);
  const pararRef = useRef(false);
  const [rellenando, setRellenando] = useState(false);

  const completarFichas = async () => {
    const inicio = pendientes.data?.pending ?? 0;
    if (inicio === 0) return;
    pararRef.current = false;
    // Una pulsación es UNA pasada. La vigilancia de reventas no se agota sola
    // —un ex-jugador sin vender puede dar dinero mañana—, así que el corte lo
    // marca este instante: quien ya se revisó después de él no vuelve a la
    // cola hasta que pulses otra vez.
    const pulsacion = new Date().toISOString();
    setRellenando(true);
    setRelleno({
      total: inicio, hechos: 0, quedan: inicio, ultimo: null, error: null,
      marcas: [], escala: 0,
    });
    let hechos = 0;
    try {
      // Vuelta a vuelta hasta acabar. Cada lote es una petición corta e
      // independiente: si algo se corta, lo ya descargado se queda guardado y
      // al volver a pulsar se sigue donde iba, nunca desde el principio.
      let quedabanAntes = inicio;
      for (;;) {
        if (pararRef.current) break;
        const lote = await api.runBackfillBatch(TEAM_ID, pulsacion);
        hechos += lote.done;
        setRelleno((previo) => ({
          total: inicio,
          hechos: Math.min(hechos, inicio),
          quedan: lote.pending,
          ultimo: lote.players[lote.players.length - 1] ?? null,
          error: lote.errors[0] ?? null,
          // El backend manda el barrido ENTERO en cada respuesta, asi que
          // aqui no se acumula nada: acumular era lo que dejaba el hueco de
          // la izquierda sin llenar, porque lo atendido en barridos
          // anteriores no aparecia por ningun lado.
          marcas: (lote.queueMarks ?? []).map((x) => x.position),
          // La escala se congela en la primera pulsación: los expedientes
          // que se cierran salen del eje, y repintar con el eje de ahora
          // correría las marcas ya puestas.
          escala: previo?.escala || (lote.queueMarks ?? [])[0]?.total || 0,
        }));
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
          <p className="text-sm text-[var(--muted)]">
            <b className="text-[var(--text)]">Tus compras y tus ventas se traen aquí.</b>{" "}
            Cada vez que sincronizas se revisa tu libro de transferencias desde lo
            último que ya tenías, así que cuesta una página cuando no hay nada nuevo.
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

      <Panel title="Transferencias" meta={pendientes.data ? jugadores(pendientes.data.pending) : ""}>
        <div className="space-y-3 p-4">
          <p className="text-sm text-[var(--muted)]">
            <b className="text-[var(--text)]">Sólo comisiones de reventa.</b> Cuando un
            club revende a alguien que le vendiste —o a un canterano tuyo— te toca un
            porcentaje, y esto es lo que sale a buscarlo. Va de a un jugador, así que
            puedes pararlo y seguir otro día.
          </p>
          <p className="text-sm text-[var(--muted)]">
            Aquí <b className="text-[var(--text)]">no</b> se traen tus compras ni tus
            ventas: ésas vienen con «Sincronizar ahora». De paso completa lo que le
            falte al pasado de cada ex-jugador —de dónde era, por cuánto se fue, cuántos
            partidos jugó contigo—, que es lo que hace falta para calcular la comisión.
          </p>

          {pendientes.data && (
            <dl className="divide-y divide-[var(--border)] rounded-md border border-[var(--border)] text-sm">
              <div className="flex items-baseline justify-between gap-3 px-3 py-2">
                <dt className="text-[var(--muted)]">Con posible comisión futura</dt>
                <dd className="tabular-nums font-semibold">
                  {jugadores(pendientes.data.detail.resaleWatch)}
                </dd>
              </div>
              <div className="flex items-baseline justify-between gap-3 px-3 py-2">
                <dt className="text-[var(--muted)]">Historial por construir</dt>
                <dd className="tabular-nums font-semibold">
                  {jugadores(pendientes.data.detail.census)}
                </dd>
              </div>
            </dl>
          )}

          {relleno && (
            <div>
              <div className="mb-1 flex items-baseline justify-between gap-3 text-xs">
                <span className="truncate text-[var(--muted)]">
                  {relleno.quedan === 0
                    ? "Listo"
                    : `${relleno.hechos} de ${relleno.total}${relleno.ultimo ? ` · ${relleno.ultimo}` : ""}`}
                </span>
                <span className="shrink-0 tabular-nums text-[var(--muted)]">
                  {Math.round(
                    relleno.quedan === 0
                      ? 100
                      : (relleno.hechos / Math.max(relleno.total, 1)) * 100,
                  )}
                  %
                </span>
              </div>
              {/* La barra es un MAPA de la cola, no un porcentaje: de
                  izquierda a derecha van los ex-jugadores del más reciente al
                  más antiguo. El frente avanza por la izquierda con cada
                  turno "reciente", y cada turno al azar enciende una marca
                  allí donde cayó — normalmente lejos, en la cola vieja. */}
              <div className="relative h-2 overflow-hidden rounded-full bg-[var(--surface-2)]">
                <div
                  className="absolute inset-y-0 left-0 rounded-full bg-[var(--accent)] transition-all duration-300"
                  style={{ width: `${frente(relleno)}%` }}
                />
                {relleno.escala > 0 &&
                  relleno.marcas.map((posicion, i) => (
                    <span
                      key={`${posicion}-${i}`}
                      className="absolute inset-y-0 w-[3px] rounded-sm bg-[var(--accent)]"
                      style={{
                        left: `${Math.min(99, (posicion / relleno.escala) * 100)}%`,
                      }}
                    />
                  ))}
              </div>
              {relleno.error && (
                <p className="mt-2 text-xs text-[var(--warning)]">
                  Hattrick falló en una ficha. Lo descargado se guardó; vuelve a pulsar
                  para seguir.
                </p>
              )}
            </div>
          )}

          {!yaSincronizo && (
            <p className="text-xs text-[var(--warning)]">
              Primero pulsa «Sincronizar ahora».
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
                    ? "Todo al día"
                    : `Traer ${jugadores(pendientes.data?.pending ?? 0)}`}
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
