import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BotonDeBorrado } from "../components/BotonDeBorrado";
import { Link, useLocation } from "react-router-dom";
import {
  ClubMoraleSection,
  EconomySection,
  NationalTeamSection,
  TrainingSection,
} from "../components/SyncComparisonReport";
import { YouthChanges } from "../components/YouthChanges";
import { AvisoDelBarrido } from "../components/AvisoDelBarrido";
import { SyncChangesFeed } from "../components/SyncChangesFeed";
import { INTENTOS_DE_TRANSFERENCIA_VISIBLES } from "../config/flags";
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
  type AvisoDelBarrido as AvisoDatos,
} from "../services/api";

import { tx } from "../i18n/tx";
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
      title: tx("{{v0}} subida(s) de habilidad", { v0: pops.length }),
      detail: tx(
        "Revisa valor, ventana de venta y si conviene cambiar el plan de entrenamiento.",
      ),
      tone: "positive",
    });
  }
  if (injuries.length > 0) {
    items.push({
      title: tx("{{v0}} cambio(s) de lesión", { v0: injuries.length }),
      detail: tx(
        "Vuelve a calcular alineación y banquillo antes del próximo partido.",
      ),
      tone: "danger",
    });
  }
  if (market.length > 0) {
    items.push({
      title: tx("{{v0}} movimiento(s) de mercado", { v0: market.length }),
      detail: tx(
        "Confirma si el jugador listado sigue encajando con tu economía y plan deportivo.",
      ),
      tone: undefined,
    });
  }
  if (salary.length > 0) {
    items.push({
      title: tx("{{v0}} cambio(s) de salario", { v0: salary.length }),
      detail: tx("Mira impacto en balance estructural y presión de caja."),
      tone: undefined,
    });
  }
  if (finishedMatches.length > 0) {
    items.push({
      title: tx("{{v0}} resultado(s) nuevo(s)", { v0: finishedMatches.length }),
      detail: tx("Abre Partidos para ver sectores, posesión y conversión."),
      tone: undefined,
    });
  }
  if (training.length > 0) {
    items.push({
      title: tx("Cambio de entrenamiento detectado"),
      detail: tx(
        "Revisa Novedades y Entrenamiento para validar si el nuevo plan aprovecha los minutos jugados.",
      ),
      tone: undefined,
    });
  }
  if (items.length === 0 && changes.length === 0) {
    items.push({
      title: tx("Todo está al día"),
      detail: tx(
        "La sincronización no encontró diferencias reales contra el snapshot anterior.",
      ),
      tone: "positive",
    });
  }
  return items;
}

/** Punto 4 pedido 2026-08-10: esta mecánica de sync es una adenda, no debe
 * competir en importancia con los cambios reales, mismo tratamiento
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
          {tx("Mecánica de la sincronización")}
        </span>
        <span>
          {tx("última:")} {relative(data?.syncedAt ?? null)}
        </span>
        <span>
          {tx("cambios nuevos:")} {changes.length}
        </span>
        <span>
          {tx("jugadores comparados:")} {data?.playerRows.length ?? 0}
        </span>
        <span>
          {tx("subidas de habilidad:")} {skillPops}
        </span>
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
          label: tx("Salario"),
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
      // Un descubrimiento no sube ni baja: se sabe. Va en «up» porque salir de
      // la niebla siempre es ganar información, pero sin delta que pintar.
      direction:
        event.delta == null || event.delta > 0
          ? "up"
          : event.delta < 0
            ? "down"
            : "neutral",
    });
    byPlayer.set(event.htPlayerId, group);
  }
  return [...byPlayer.values()].sort((a, b) => a.name.localeCompare(b.name));
}

/** Los canteranos de la ventana, agrupados por chico.
 *
 *  Van a SU panel y no a la lista de arriba. 2026-09-09: primero se mezclaron
 *  con la plantilla y el usuario lo paró en seco --«no quiero ver juveniles
 *  mezclados con los demás, para eso tienes la sección Academia»--. Lo que
 *  sigue a la ventana es el panel entero, no la lista común. */
function historyYouthGroups(data: ChangesHistory): PlayerChangeGroup[] {
  const byPlayer = new Map<number, PlayerChangeGroup>();
  for (const event of data.youthChanges ?? []) {
    const group = byPlayer.get(event.htPlayerId) ?? {
      htPlayerId: event.htPlayerId,
      name: event.name,
      isYouth: true,
      changes: [],
    };
    group.changes.push({
      key: event.key,
      label: event.label,
      before: event.before,
      current: event.current,
      delta: event.delta,
      direction:
        event.delta == null || event.delta > 0
          ? "up"
          : event.delta < 0
            ? "down"
            : "neutral",
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
    // Los descubrimientos NO entran en el total del equipo. No tienen tamaño
    // --nadie subió ni bajó-- y sumarlos como si fueran +4 diría que la
    // plantilla mejoró cuando lo único que pasó es que ahora se sabe algo.
    if (event.delta != null) {
      if (event.delta > 0) metric.upTotal += event.delta;
      else if (event.delta < 0) metric.downTotal += Math.abs(event.delta);
      byKey.set(event.key, metric);
    }
  }
  return [...byKey.values()];
}

/** Las ventanas de comparación del histórico. `weeks` es lo que se le pide al
 *  backend, que devuelve el cambio NETO contra el cierre semanal de entonces
 *  no la lista de cada paso intermedio. A 16 semanas eso es la diferencia
 *  entre leer "Pases 8 → 11" y tener que sumar tres subidas sueltas.
 *
 *  2026-08-17, pedido explícito. La de una semana sigue siendo la que se abre
 *  por defecto: la vista de Cambios se pensó efímera, y las ventanas anchas
 *  hay que ir a buscarlas. */
const HISTORY_WINDOWS = [
  { key: "1", weeks: 1, label: tx("Última semana") },
  { key: "2", weeks: 2, label: tx("Hace 2 semanas") },
  { key: "4", weeks: 4, label: tx("Hace 4 semanas") },
  { key: "8", weeks: 8, label: tx("Hace 8 semanas") },
  { key: "16", weeks: 16, label: tx("Hace 16 semanas") },
  // «Siempre» va al final y no es una ventana más larga: `weeks: 0` es el
  // centinela que le dice al motor que no ponga corte, y entonces cada
  // jugador se compara contra SU primer cierre guardado en vez de contra una
  // fecha común (2026-09-09, pedido del usuario).
  { key: "siempre", weeks: 0, label: tx("Siempre") },
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
      title={tx("¿Cuántas veces lo vieron?")}
      meta={tx("Hattrick solo lo dice al cerrarse la puja")}
    >
      <div className="space-y-3 p-4">
        <p className="text-sm text-[var(--muted)]">
          {tx(
            "Se acaba de cerrar una puja. En la noticia de Hattrick aparece cuántas veces miraron al jugador y a qué precio lo pedías. Ninguno de los dos llega en la sincronización, así que si no los anotas ahora se pierden.",
          )}
        </p>
        {pendientes.map((p) => (
          <div
            key={p.id}
            className="flex flex-wrap items-center gap-3 rounded-md border border-[var(--border)] p-3"
          >
            <span className="text-sm font-medium">{p.name}</span>
            <span className="text-xs text-[var(--muted)]">
              {tx("cerró el")} {p.closedAt ? date(p.closedAt) : "?"}
            </span>
            <input
              type="number"
              min={0}
              placeholder={tx("precio pedido")}
              value={precios[p.id] ?? ""}
              onChange={(e) =>
                setPrecios((v) => ({ ...v, [p.id]: e.target.value }))
              }
              className="w-36 rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-sm"
            />
            <input
              type="number"
              min={0}
              placeholder={tx("veces visto")}
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
              {tx("Guardar")}
            </button>
            <button
              onClick={() => responder.mutate({ id: p.id })}
              title={tx("No lo apunto ahora, pero el intento sigue contando")}
              className="rounded-md border border-[var(--border)] px-3 py-1 text-xs text-[var(--muted)]"
            >
              {tx("No sé")}
            </button>
            <BotonDeBorrado
              onConfirmar={() => borrar.mutate(p.id)}
              title={tx("Borrarlo: como si nunca hubiera llegado a la lista")}
              confirmacion={tx("¿Seguro? No hay vuelta atrás")}
              className="min-h-6 rounded-md border border-[var(--border)] px-3 py-1 text-xs text-[var(--muted)]"
            >
              {tx("No tener en cuenta")}
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
  // EL AVISO DEL BARRIDO, si es que se llegó aquí desde uno (2026-09-10).
  // Vive en el estado de la navegación y no en la URL: es de este viaje
  // concreto, así que recargar la página no lo resucita y compartir el enlace
  // no se lo enseña a nadie más.
  //
  // Los dos hooks van ARRIBA DEL TODO, antes de cualquier return temprano: un
  // hook detrás de un return se salta en las cargas en las que ese return
  // dispara, y React tumba la pantalla con «Rendered more hooks than during
  // the previous render».
  const location = useLocation();
  const [avisoCerrado, setAvisoCerrado] = useState(false);

  // EL ARCHIVO SE FUE, 2026-09-09, pedido del usuario. Había un desplegable
  // para releer el informe de una sincronización anterior, y llevaba roto
  // desde que existía: al elegir una fecha se movía todo --el aviso, los
  // cambios por jugador, los del club-- menos la lista principal, que seguía
  // enseñando lo último. La pantalla decía «estás viendo el archivo» encima
  // de la lista del presente.
  //
  // Lo que se pierde con esto, y se pierde de verdad: sincronizar dos veces
  // seguidas. La segunda no encuentra nada, dice «Nada nuevo», y lo que
  // encontró la primera ya no se puede volver a leer. Es la consecuencia
  // aceptada de «la vida de las notificaciones es ÚNICA» (2026-08-24) sin un
  // archivo que la matice.
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
  const { data, isLoading, isError, error } = useSyncChanges();
  const squad = useSquad();
  const [changesTab, setChangesTab] = useState<ChangesTab>("latest");
  const window = HISTORY_WINDOWS.find((w) => w.key === changesTab);
  // Sólo se pide histórico cuando hay una ventana activa: en "Último
  // snapshot" no hace falta y sería una consulta de más en cada visita.
  const history = useChangesHistory(null, window?.weeks, window != null);

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;

  const aviso = (location.state as { avisoDelBarrido?: AvisoDatos } | null)
    ?.avisoDelBarrido;

  const todos = data?.changes ?? [];
  // LOS FICHAJES DE TUS RIVALES, APARTE (2026-09-09). El usuario los vio
  // aparecer en el feed tras sincronizar y no supo qué eran: «me muestra unos
  // nuevos eventos que no sé qué son».
  //
  // Y con razón: esta pantalla responde «qué cambió EN MI CLUB», y un fichaje
  // de otro equipo no es eso. Es información útil --por eso no se borra-- pero
  // de otra pregunta, así que baja a su propio cajón, cerrado, al final.
  const changes = todos.filter((c) => c.category !== "rivales");
  const deRivales = todos.filter((c) => c.category === "rivales");
  // La comparación que se está mirando, que es la llave con la que se
  // recuerda si ya la diste por vista.
  const comparacion = data?.reportSyncId ?? null;
  const actions = actionItems(changes);
  const playerLinks = Object.fromEntries(
    (squad.data?.players ?? []).map((p) => [p.name, p.htPlayerId]),
  );

  return (
    <div className="space-y-4">
      {aviso && !avisoCerrado && (
        <AvisoDelBarrido datos={aviso} onClose={() => setAvisoCerrado(true)} />
      )}
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">{tx("Cambios")}</h1>
          <p className="text-sm text-[var(--muted)]">
            {tx(
              "Lo que movió la última sincronización, comparado contra el cierre semanal anterior.",
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* 2026-08-15: sincronizar dejó de vivir aquí, se hace en una sola
              pantalla y esa pantalla trae de vuelta a ésta. */}
          <Link
            to="/sync"
            className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--muted)] hover:border-[var(--accent)] hover:text-[var(--text)]"
          >
            {tx("Ir a Sincronización")}
          </Link>
        </div>
      </header>

      {/* Un informe se lee una vez. Si el último sync no movió nada, aquí no
          hay nada: no se reenseña lo de antes. El archivo sigue accesible
          eligiendo una fecha, y entonces se avisa de que no es lo último. */}
      {/* Lo primero de la pantalla, por delante incluso de los avisos de
          contexto (pedido del usuario, 2026-09-01). */}
      {/* Apagado a petición del usuario (2026-09-04) junto con la pestaña de
          «Intentos de transferencias», que es donde vivían estos datos. Se
          apaga desde la MISMA constante para que no quede la mitad
          encendida: pedirle a alguien que teclee unas visitas que luego no
          puede consultar en ninguna parte sería peor que no pedírselas. */}
      {INTENTOS_DE_TRANSFERENCIA_VISIBLES && <PreguntaDeVisitas />}

      {data && data.reportIsLatest && data.reportChanges.length === 0 && (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-sm text-[var(--muted)]">
          <span className="font-medium text-[var(--text)]">
            {tx("Nada nuevo.")}
          </span>{" "}
          {tx("La sincronización de")} {relative(data.syncedAt)}{" "}
          {tx("no encontró ningún cambio.")}
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
              {changes.length}{" "}
              {tx("cambio(s) desde la última sincronización, ya vistos.")}
            </span>
            <button
              onClick={() => volverAAbrir(comparacion)}
              data-track="Cambios: volver a abrir"
              className="text-xs text-[var(--muted)] underline hover:text-[var(--text)]"
            >
              {tx("Volver a abrir")}
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
          title={tx("Qué haría ahora")}
          meta={tx("lo accionable, ya con los cambios delante")}
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
        title={tx("Cambios por jugador")}
        meta={tx("jugador por jugador, habilidad por habilidad")}
      >
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] px-4 py-3">
          {/* Mismo feed, distinto tramo del histórico: es un filtro. */}
          <Tabs
            modo="filtro"
            label={tx("Tramo del histórico")}
            tabs={[
              { key: "latest", label: tx("Última lectura") },
              ...HISTORY_WINDOWS.map((w) => ({ key: w.key, label: w.label })),
            ]}
            active={changesTab}
            onChange={setChangesTab}
          />
          <span className="text-xs text-[var(--muted)]">
            {window == null
              ? tx("última comparación semanal guardada")
              : window.weeks === 0
                ? // «Siempre» no tiene UNA fecha: cada jugador se compara
                  // contra su propio primer cierre, así que decir «contra el
                  // cierre del 26/07» sería falso para todo el que llegara
                  // después. Y «siempre» es desde que esta aplicación mira,
                  // no desde que el jugador existe: eso también se dice.
                  tx(
                    "contra el primer dato guardado de cada jugador, que es desde cuando esta aplicación lo mira",
                  )
                : history.data?.comparedFrom
                  ? tx("neto contra el cierre del {{v0}}", {
                      v0: date(history.data.comparedFrom),
                    })
                  : tx("cambio neto en {{v0}} semana(s)", { v0: window.weeks })}
          </span>
        </div>
        {changesTab === "latest" && data && (
          <GroupedPlayerChanges
            groups={lastSyncGroups(data)}
            aggregate={lastSyncAggregate(data)}
            emptyMessage={tx(
              "No hubo variaciones de jugadores en la última comparación guardada.",
            )}
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
        <YouthChanges
          rows={data.youthRows ?? []}
          // Las tres cifras siguen a la ventana de arriba (2026-09-09). Sólo
          // se sustituye el recuento de revelaciones, que es lo que depende
          // del periodo: los techos conocidos son lo que se sabe HOY, mire
          // uno la semana pasada o toda la historia.
          summary={
            window && history.data?.youthSummary && data.youthSummary
              ? {
                  ...data.youthSummary,
                  revelations: history.data.youthSummary.revelations,
                }
              : data.youthSummary
          }
          grupos={
            window && history.data
              ? historyYouthGroups(history.data)
              : undefined
          }
          ventana={
            window && history.data?.youthSummary
              ? {
                  etiqueta:
                    window.weeks === 0
                      ? "en total"
                      : window.weeks === 1
                        ? "en la última semana"
                        : `en ${window.weeks} semanas`,
                  ceilingsBefore: history.data.youthSummary.ceilingsBefore,
                }
              : undefined
          }
          teamName={data.youthTeamName}
        />
      )}

      {data && <TrainingSection changes={data.clubChanges} />}
      {data && <EconomySection changes={data.clubChanges} />}
      {data && <ClubMoraleSection changes={data.clubChanges} />}
      {data && <NationalTeamSection appearances={data.nationalMatches ?? []} />}

      {/* Al fondo: no describe al club, describe a la herramienta. Solo
          importa cuando algo no cuadra y hay que saber contra qué se comparó. */}
      {deRivales.length > 0 && (
        <details className="rounded-lg border border-[var(--border)] bg-[var(--surface)]">
          <summary className="cursor-pointer px-4 py-3 text-sm">
            {tx("Movimientos de tus rivales")}{" "}
            <span className="text-[var(--muted)]">
              ({deRivales.length}
              {tx("), no son cambios de tu club")}
            </span>
          </summary>
          <ul className="space-y-1 border-t border-[var(--border)] px-4 py-3">
            {deRivales.map((c, i) => (
              <li
                key={`${c.summary}-${i}`}
                className="prosa text-sm text-[var(--muted)]"
              >
                {c.summary}
              </li>
            ))}
          </ul>
        </details>
      )}

      <SyncMetaSummary data={data} changes={changes} />
    </div>
  );
}
