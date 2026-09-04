import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BotonDeBorrado } from "../components/BotonDeBorrado";
import { Link } from "react-router-dom";
import {
  ClubMoraleSection,
  EconomySection,
  NationalTeamSection,
  TrainingSection,
} from "../components/SyncComparisonReport";
import { YouthChanges } from "../components/YouthChanges";
import { SyncChangesFeed } from "../components/SyncChangesFeed";
import {
  GroupedPlayerChanges,
  type AggregateMetric,
  type NormalizedChange,
  type PlayerChangeGroup,
} from "../components/GroupedPlayerChanges";
import { ErrorState, Loading, Panel } from "../components/Panels";
import { Tabs } from "../components/Tabs";
import {
  TEAM_ID,
  useChangesHistory,
  useSquad,
  useSyncChanges,
} from "../hooks/useTeam";
import { date, relative } from "../hooks/useFormat";
import {
  api,
  type ChangesHistory,
  type HistoricalPlayerChange,
  type LastSyncChanges,
  type SyncResult,
} from "../services/api";

function countPlayerPops(changes: SyncResult["changes"]): number {
  return changes.filter((c) => {
    const s = c.summary.toLowerCase();
    return (
      c.category === "jugadores" && (s.includes("subio") || s.includes("subió"))
    );
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

function actionItems(changes: SyncResult["changes"]): {
  title: string;
  detail: string;
  tone: "positive" | "danger" | undefined;
}[] {
  const items: {
    title: string;
    detail: string;
    tone: "positive" | "danger" | undefined;
  }[] = [];
  const lower = changes.map((c) => ({ ...c, text: c.summary.toLowerCase() }));
  const pops = lower.filter(
    (c) =>
      c.category === "jugadores" &&
      (c.text.includes("subio") || c.text.includes("subió")),
  );
  const injuries = lower.filter(
    (c) => c.text.includes("lesion") || c.text.includes("lesión"),
  );
  const market = lower.filter((c) => c.text.includes("mercado"));
  const salary = lower.filter((c) => c.text.includes("salario"));
  const finishedMatches = lower.filter((c) => c.category === "partidos");
  const training = lower.filter((c) => c.category === "entrenamiento");

  if (pops.length > 0) {
    items.push({
      title: `${pops.length} subida(s) de habilidad`,
      detail:
        "Revisa valor, ventana de venta y si conviene cambiar el plan de entrenamiento.",
      tone: "positive",
    });
  }
  if (injuries.length > 0) {
    items.push({
      title: `${injuries.length} cambio(s) de lesión`,
      detail:
        "Vuelve a calcular alineación y banquillo antes del próximo partido.",
      tone: "danger",
    });
  }
  if (market.length > 0) {
    items.push({
      title: `${market.length} movimiento(s) de mercado`,
      detail:
        "Confirma si el jugador listado sigue encajando con tu economía y plan deportivo.",
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
      detail:
        "Revisa Novedades y Entrenamiento para validar si el nuevo plan aprovecha los minutos jugados.",
      tone: undefined,
    });
  }
  if (items.length === 0 && changes.length === 0) {
    items.push({
      title: "Todo está al día",
      detail:
        "La sincronización no encontró diferencias reales contra el snapshot anterior.",
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
  data,
  changes,
}: {
  data: LastSyncChanges | undefined;
  changes: SyncResult["changes"];
}) {
  const skillPops = data
    ? countReportSkillPops(data)
    : countPlayerPops(changes);
  return (
    <div className="rounded-lg border border-dashed border-[var(--border)] px-4 py-2 text-xs text-[var(--muted)]">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <span className="font-medium uppercase tracking-wide text-[var(--muted)]">
          Mecánica de la sincronización
        </span>
        <span>última: {relative(data?.syncedAt ?? null)}</span>
        <span>cambios nuevos: {changes.length}</span>
        <span>jugadores comparados: {data?.playerRows.length ?? 0}</span>
        <span>subidas de habilidad: {skillPops}</span>
      </div>
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
  // `downTotal` llega del backend en negativo, porque allí es la suma de los
  // deltas tal cual. La tarjeta lo escribe en positivo y deja el signo al
  // color, así que se voltea aquí, en el borde.
  return data.summary.map((metric) => ({
    key: metric.key,
    label: metric.label,
    upTotal: metric.upTotal,
    downTotal: Math.abs(metric.downTotal),
  }));
}

function mergedHistoryEvents(data: ChangesHistory): HistoricalPlayerChange[] {
  return [
    ...data.skillChanges,
    ...data.experienceChanges,
    ...data.loyaltyChanges,
    ...data.formChanges,
    ...data.marketChanges,
  ];
}

function historyGroups(data: ChangesHistory): PlayerChangeGroup[] {
  const byPlayer = new Map<number, PlayerChangeGroup>();
  for (const event of mergedHistoryEvents(data)) {
    const group = byPlayer.get(event.htPlayerId) ?? {
      htPlayerId: event.htPlayerId,
      name: event.name,
      changes: [],
    };
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
    const metric = byKey.get(event.key) ?? {
      key: event.key,
      label: event.label,
      upTotal: 0,
      downTotal: 0,
    };
    if (event.delta > 0) metric.upTotal += event.delta;
    else if (event.delta < 0) metric.downTotal += Math.abs(event.delta);
    byKey.set(event.key, metric);
  }
  return [...byKey.values()];
}

/** Las ventanas de comparación del histórico. `weeks` es lo que se le pide al
 *  backend, que devuelve el cambio NETO contra el cierre semanal de entonces
 *  — no la lista de cada paso intermedio. A 16 semanas eso es la diferencia
 *  entre leer "Pases 8 → 11" y tener que sumar tres subidas sueltas.
 *
 *  2026-08-17, pedido explícito. La de una semana sigue siendo la que se abre
 *  por defecto: la vista de Cambios se pensó efímera, y las ventanas anchas
 *  hay que ir a buscarlas. */
const HISTORY_WINDOWS = [
  { key: "1", weeks: 1, label: "Última semana" },
  { key: "2", weeks: 2, label: "Hace 2 semanas" },
  { key: "4", weeks: 4, label: "Hace 4 semanas" },
  { key: "8", weeks: 8, label: "Hace 8 semanas" },
  { key: "16", weeks: 16, label: "Hace 16 semanas" },
] as const;

type ChangesTab = "latest" | (typeof HISTORY_WINDOWS)[number]["key"];

/** Pregunta por las visitas de una puja que acaba de cerrarse.
 *
 * 2026-08-22, pedido por el usuario. Cuando termina un intento de venta,
 * Hattrick cuenta en el texto de la noticia cuántas veces miraron al jugador
 * ("fue visto 8 veces mientras estaba en la lista de transferibles"). Ese dato
 * no viaja por CHPP por ningún lado, así que si no se anota en ese momento se
 * pierde para siempre.
 *
 * Se puede ignorar, y entonces no vuelve a preguntar por ese intento: un aviso
 * que reaparece cada vez deja de leerse a la tercera.
 */
function PreguntaDeVisitas() {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["transfer-attempts", TEAM_ID],
    queryFn: () => api.transferAttempts(TEAM_ID),
  });
  const [valores, setValores] = useState<Record<number, string>>({});
  // El precio pedido sale del mismo mensaje que las visitas.
  const [precios, setPrecios] = useState<Record<number, string>>({});

  // "No tener en cuenta" borra el intento: como si nunca hubiera llegado a la
  // lista. No hay estado intermedio a proposito.
  const borrar = useMutation({
    mutationFn: (id: number) => api.deleteTransferAttempt(TEAM_ID, id),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["transfer-attempts", TEAM_ID] }),
  });

  const responder = useMutation({
    mutationFn: ({
      id,
      veces,
      precio,
    }: {
      id: number;
      veces?: number;
      precio?: number;
    }) =>
      api.setTimesSeen(
        TEAM_ID,
        id,
        veces != null || precio != null
          ? {
              ...(veces != null ? { times_seen: veces } : {}),
              ...(precio != null ? { asking_price: precio } : {}),
            }
          : // "No se": la fila se queda, con "?" en lo que se preguntaba.
            { dismissed: true },
      ),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["transfer-attempts", TEAM_ID] }),
  });

  const pendientes = data?.pendingQuestion ?? [];
  if (pendientes.length === 0) return null;

  return (
    <Panel
      title="¿Cuántas veces lo vieron?"
      meta="Hattrick solo lo dice al cerrarse la puja"
    >
      <div className="space-y-3 p-4">
        <p className="text-sm text-[var(--muted)]">
          Se acaba de cerrar una puja. En la noticia de Hattrick aparece cuántas
          veces miraron al jugador y a qué precio lo pedías. Ninguno de los dos
          llega en la sincronización, así que si no los anotas ahora se pierden.
        </p>
        {pendientes.map((p) => (
          <div
            key={p.id}
            className="flex flex-wrap items-center gap-3 rounded-md border border-[var(--border)] p-3"
          >
            <span className="text-sm font-medium">{p.name}</span>
            <span className="text-xs text-[var(--muted)]">
              cerró el {p.closedAt ? date(p.closedAt) : "?"}
            </span>
            <input
              type="number"
              min={0}
              placeholder="precio pedido"
              value={precios[p.id] ?? ""}
              onChange={(e) =>
                setPrecios((v) => ({ ...v, [p.id]: e.target.value }))
              }
              className="w-36 rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-sm"
            />
            <input
              type="number"
              min={0}
              placeholder="veces visto"
              value={valores[p.id] ?? ""}
              onChange={(e) =>
                setValores((v) => ({ ...v, [p.id]: e.target.value }))
              }
              className="w-28 rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-sm"
            />
            <button
              onClick={() =>
                responder.mutate({
                  id: p.id,
                  veces: valores[p.id] ? Number(valores[p.id]) : undefined,
                  precio: precios[p.id] ? Number(precios[p.id]) : undefined,
                })
              }
              disabled={!valores[p.id] && !precios[p.id]}
              className="rounded-md bg-[var(--accent)] px-3 py-1 text-xs font-medium text-white disabled:opacity-50"
            >
              Guardar
            </button>
            <button
              onClick={() => responder.mutate({ id: p.id })}
              title="No lo apunto ahora, pero el intento sigue contando"
              className="rounded-md border border-[var(--border)] px-3 py-1 text-xs text-[var(--muted)]"
            >
              No sé
            </button>
            <BotonDeBorrado
              onConfirmar={() => borrar.mutate(p.id)}
              title="Borrarlo: como si nunca hubiera llegado a la lista"
              confirmacion="¿Seguro? No hay vuelta atrás"
              className="min-h-6 rounded-md border border-[var(--border)] px-3 py-1 text-xs text-[var(--muted)]"
            >
              No tener en cuenta
            </BotonDeBorrado>
          </div>
        ))}
      </div>
    </Panel>
  );
}

const CLAVE_VISTAS = "cambios.comparacionesVistas";
//: Suficientes para no volver a ver lo de la semana pasada, y no tantas como
//: para guardar un historial que nadie consulta.
const VISTAS_QUE_SE_RECUERDAN = 20;

export function SyncChangesPage() {
  // `null` = la comparación más reciente con cambios. Al elegir una fecha del
  // archivo se pide esa al backend, que recalcula los +1/-1 de ese snapshot
  // contra el inmediatamente anterior (pedido explícito 2026-08-15).
  const [reportSyncId, setReportSyncId] = useState<number | null>(null);
  // Las comparaciones que ya diste por vistas. El botón «Cerrar» existía
  // desde siempre con un manejador vacío --`() => undefined`--, así que no
  // hacía nada; lo reportó el usuario (2026-09-04).
  //
  // Se recuerda por navegador y por comparación: cerrarla y que reapareciera
  // al volver a la pantalla sería el mismo botón inútil con otra forma. Y no
  // se pierde nada: queda una línea con el recuento para volver a abrirla.
  const [vistas, setVistas] = useState<number[]>(() => {
    try {
      const crudo = localStorage.getItem(CLAVE_VISTAS);
      return crudo ? (JSON.parse(crudo) as number[]) : [];
    } catch {
      return [];
    }
  });
  // Guardar y recordar van SIEMPRE juntos. Separados, «Volver a abrir» sólo
  // cambiaba el estado en memoria y al recargar la comparación aparecía
  // cerrada otra vez: el mismo botón que no hace nada, por el otro lado.
  const recordar = (siguientes: number[]) => {
    // Sólo las últimas: la lista no tiene por qué crecer para siempre.
    const recortadas = siguientes.slice(-VISTAS_QUE_SE_RECUERDAN);
    try {
      localStorage.setItem(CLAVE_VISTAS, JSON.stringify(recortadas));
    } catch {
      // Un navegador sin almacenamiento no puede romper la pantalla: se
      // cierra igual, sólo que no lo recuerda la próxima vez.
    }
    setVistas(recortadas);
  };
  const darPorVista = (id: number | null) => {
    if (id != null && !vistas.includes(id)) recordar([...vistas, id]);
  };
  const volverAAbrir = (id: number | null) =>
    recordar(vistas.filter((x) => x !== id));
  const { data, isLoading, isError, error } = useSyncChanges(reportSyncId);
  const squad = useSquad();
  const [changesTab, setChangesTab] = useState<ChangesTab>("latest");
  const window = HISTORY_WINDOWS.find((w) => w.key === changesTab);
  // Sólo se pide histórico cuando hay una ventana activa: en "Último
  // snapshot" no hace falta y sería una consulta de más en cada visita.
  const history = useChangesHistory(null, window?.weeks, window != null);

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;

  const changes = data?.changes ?? [];
  // La comparación que se está mirando, que es la llave con la que se
  // recuerda si ya la diste por vista.
  const comparacion = data?.reportSyncId ?? null;
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
            Última sincronización y archivo histórico: los cambios se comparan
            contra el cierre semanal anterior.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {(data?.availableReports.length ?? 0) > 0 && (
            <label className="flex items-center gap-2 text-xs text-[var(--muted)]">
              Comparación
              <select
                value={data?.reportSyncId ?? ""}
                onChange={(e) =>
                  setReportSyncId(
                    e.target.value === "" ? null : Number(e.target.value),
                  )
                }
                className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5 text-xs text-[var(--text)]"
              >
                {data?.availableReports.map((report, index) => (
                  <option key={report.syncId} value={report.syncId}>
                    {index === 0 ? "Más reciente · " : ""}
                    {date(report.syncedAt)} ({report.changeCount} cambio
                    {report.changeCount === 1 ? "" : "s"})
                  </option>
                ))}
              </select>
            </label>
          )}
          {/* 2026-08-15: sincronizar dejó de vivir aquí, se hace en una sola
              pantalla y esa pantalla trae de vuelta a ésta. */}
          <Link
            to="/sync"
            className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--muted)] hover:border-[var(--accent)] hover:text-[var(--text)]"
          >
            Ir a Sincronización
          </Link>
        </div>
      </header>

      {/* Un informe se lee una vez. Si el último sync no movió nada, aquí no
          hay nada: no se reenseña lo de antes. El archivo sigue accesible
          eligiendo una fecha, y entonces se avisa de que no es lo último. */}
      {/* Lo primero de la pantalla, por delante incluso de los avisos de
          contexto (pedido del usuario, 2026-09-01). */}
      <PreguntaDeVisitas />

      {data && !data.reportIsLatest && (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-sm text-[var(--muted)]">
          <span className="font-medium text-[var(--text)]">
            Estás viendo el archivo.
          </span>{" "}
          Esto es lo que cambió {relative(data.reportSyncedAt)}, no lo último.
        </div>
      )}

      {data && data.reportIsLatest && data.reportChanges.length === 0 && (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-sm text-[var(--muted)]">
          <span className="font-medium text-[var(--text)]">Nada nuevo.</span> La
          sincronización de {relative(data.syncedAt)} no encontró ningún cambio.
          {data.availableReports.length > 0 &&
            " Lo anterior está en el archivo, eligiendo una fecha."}
        </div>
      )}

      {/* ORDEN. Tres revisiones, las tres del usuario:

          2026-08-30: la página abría con «Mecánica de sync» --telemetría del
          proceso, no del club-- y cerraba con «Qué haría ahora», que es la
          conclusión. Se le dio la vuelta: veredicto, detalle por bloques, y la
          mecánica al final, que es donde va lo que sólo importa si algo huele
          mal.

          2026-09-01: «Qué cambió desde la última sincronización» estaba EL
          ÚLTIMO, a 2442px de scroll (medido), cuando es la lista literal de lo
          que pasó y da nombre a la pantalla. Pasó a abrirla.

          2026-09-01, más tarde: «¿Cuántas veces lo vieron?» pasa por delante
          de todo, incluidos los avisos de contexto. Estaba penúltima, detrás
          de ocho bloques. */}

      {changes.length > 0 &&
        (comparacion != null && vistas.includes(comparacion) ? (
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] bg-[var(--surface)] px-6 py-3">
            <span className="text-xs text-[var(--muted)]">
              {changes.length} cambio(s) desde la última sincronización, ya
              vistos.
            </span>
            <button
              onClick={() => volverAAbrir(comparacion)}
              data-track="Cambios: volver a abrir"
              className="text-xs text-[var(--muted)] underline hover:text-[var(--text)]"
            >
              Volver a abrir
            </button>
          </div>
        ) : (
          <SyncChangesFeed
            changes={changes}
            playerLinks={playerLinks}
            onDismiss={() => darPorVista(comparacion)}
          />
        ))}

      {actions.length > 0 && (
        <Panel
          title="Qué haría ahora"
          meta="lo accionable, ya con los cambios delante"
        >
          <div className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-3">
            {actions.map((item) => (
              <div
                key={item.title}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg)] p-3"
              >
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
                <p className="prosa mt-1 text-xs leading-relaxed text-[var(--muted)]">
                  {item.detail}
                </p>
              </div>
            ))}
          </div>
        </Panel>
      )}

      {/* El detalle, de lo que más cambia una decisión a lo que menos. Los
          jugadores primero: es lo que el usuario vino a ver. */}
      <Panel
        title="Cambios por jugador"
        meta="jugador por jugador, habilidad por habilidad"
      >
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] px-4 py-3">
          {/* Mismo feed, distinto tramo del histórico: es un filtro. */}
          <Tabs
            modo="filtro"
            label="Tramo del histórico"
            tabs={[
              { key: "latest", label: "Última lectura" },
              ...HISTORY_WINDOWS.map((w) => ({ key: w.key, label: w.label })),
            ]}
            active={changesTab}
            onChange={setChangesTab}
          />
          <span className="text-xs text-[var(--muted)]">
            {window == null
              ? "última comparación semanal guardada"
              : history.data?.comparedFrom
                ? `neto contra el cierre del ${date(history.data.comparedFrom)}`
                : `cambio neto en ${window.weeks} semana(s)`}
          </span>
        </div>
        {changesTab === "latest" && data && (
          <GroupedPlayerChanges
            groups={lastSyncGroups(data)}
            aggregate={lastSyncAggregate(data)}
            emptyMessage="No hubo variaciones de jugadores en la última comparación guardada."
          />
        )}
        {window != null && history.isError && (
          <ErrorState error={history.error} />
        )}
        {window != null && history.data && (
          <GroupedPlayerChanges
            groups={historyGroups(history.data)}
            aggregate={historyAggregate(history.data)}
            emptyMessage={
              `Ningún jugador cambió nada en las últimas ${window.weeks} semana(s), ` +
              "o todavía no hay dos cierres semanales distintos que comparar."
            }
          />
        )}
      </Panel>

      {data && (
        <YouthChanges rows={data.youthRows ?? []} summary={data.youthSummary} />
      )}

      {data && <TrainingSection changes={data.clubChanges} />}
      {data && <EconomySection changes={data.clubChanges} />}
      {data && <ClubMoraleSection changes={data.clubChanges} />}
      {data && <NationalTeamSection appearances={data.nationalMatches ?? []} />}

      {/* Al fondo: no describe al club, describe a la herramienta. Solo
          importa cuando algo no cuadra y hay que saber contra qué se comparó. */}
      <SyncMetaSummary data={data} changes={changes} />
    </div>
  );
}
