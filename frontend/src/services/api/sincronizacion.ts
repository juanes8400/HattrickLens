/** Sincronizacion con Hattrick y sus cambios.
 *
 *  Sale de partir `services/api.ts`, que tenia 4147 lineas y se leia entero
 *  en cada cambio del frontend. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../services/api"` sigue valiendo igual.
 */
import {
  ApiError,
  BASE,
  expireLocalSession,
  idioma,
  refreshSession,
  request,
} from "./nucleo";

/** Cómo pintar el par antes/después de un cambio, ver `Change.kind` en
 *  `sync_diff.py`. */
export type SyncChangeKind = "count" | "money" | "skill" | "level" | "event";

/**
 * El mismo cambio como DATO, no como frase. Desde 2026-08-15 el backend lo
 * guarda junto al `summary` para que la UI no tenga que sacar los números del
 * texto con una regex, eso fue lo que rompió al unificar el separador de
 * miles (`Number("202.210")` = 202,21, y se mostró "TSI 202").
 */
export interface SyncChangeDetail {
  metric?: string;
  label?: string;
  subject?: string;
  before?: number;
  after?: number;
  beforeLabel?: string;
  afterLabel?: string;
  kind?: SyncChangeKind;
  good?: boolean;
  currency?: string;
  /** A qué jugador se refiere. Ausente en las filas guardadas antes de
   *  2026-09-09 y en todo lo que no sea de un jugador concreto. */
  htPlayerId?: number;
}

/** Lo que de verdad dejó una venta, de la MISMA fuente que Transferencias.
 *
 *  El precio de venta no es el resultado: falta la comisión del agente, el
 *  sueldo que se le pagó mientras estuvo, lo que costaron los listados y la
 *  comisión de club anterior. Sin eso, una venta buena y una ruinosa se leen
 *  igual. `roiPct` es "?" cuando no hubo gasto contra el que dividir. */
export interface SyncSaleEconomics {
  ingresos: number;
  gastos: number;
  saldo: number | null;
  roiPct: number | string;
  salaryTotal: number;
  purchasePrice: number | null;
  listingCost: number;
  commissionAmount: number | string;
  resaleBonus: number;
  salarySource: string;
}

export interface SyncChange {
  category: string;
  summary: string;
  /** `null` en filas guardadas antes de 2026-08-15: para esas la UI cae al
   *  parser de compatibilidad de SyncChangesFeed.tsx. */
  detail?: SyncChangeDetail | null;
  /** Sólo en las ventas, y sólo cuando se le encuentra el saldo. */
  economia?: SyncSaleEconomics;
}

export interface PlayerComparisonChange {
  key: string;
  label: string;
  abbreviation: string;
  before: number | boolean | null;
  current: number | boolean;
  delta: number | null;
  direction: "up" | "down" | "neutral";
  /** Sólo en `key === "arrival"`: lo que costó el fichaje, ya en la moneda
   *  del club. `null` cuando el libro de transferencias todavía no lo trae,
   *  que no es lo mismo que gratis. */
  arrivalPrice?: number | null;
  /** El otro origen posible: subió de la propia cantera. */
  fromAcademy?: boolean;
  currency?: string;
}

export interface PlayerComparisonRow {
  htPlayerId: number;
  name: string;
  tsi: number;
  tsiDelta: number | null;
  salary: number;
  salaryDelta: number | null;
  isNew: boolean;
  changes: PlayerComparisonChange[];
}

/** Un movimiento en UNA habilidad de UN canterano.
 *
 * Se parece a `PlayerComparisonChange` pero no es lo mismo: en juveniles cada
 * habilidad son dos numeros --nivel y techo-- y los dos se revelan por
 * separado, asi que hay cambios sin `current` (solo se descubrio el techo) y
 * cambios sin `delta` (no subio: ahora lo vemos). */
export interface YouthComparisonChange {
  key: string;
  label: string;
  abbreviation: string;
  before: number | boolean | null;
  current: number | boolean | null;
  delta: number | null;
  direction: "up" | "down" | "neutral";
  /** Hasta donde puede llegar. `null` mientras nadie lo haya revelado, que
   *  no es lo mismo que un techo bajo. */
  max?: number | null;
  maxBefore?: number | null;
  /** El techo se descubrio en ESTA comparacion. */
  maxIsNew?: boolean;
  /** Ya no subira mas, aunque el techo siga oculto. */
  maxReached?: boolean;
  maxJustReached?: boolean;
  /** No crecio: se revelo. */
  isReveal?: boolean;
}

export interface YouthComparisonRow {
  htYouthPlayerId: number;
  name: string;
  /** `16;043`, como en todo el modulo de juveniles. */
  age: string;
  isNew: boolean;
  changes: YouthComparisonChange[];
  /** Que se piensa de el AHORA: crack, promesa, aceptable, vendible,
   *  fontanero. `null` si el ojeador no ha revelado ni un techo. */
  verdict?: string | null;
  /** Solo cuando este sync lo MOVIO. Es la diferencia entre «se revelo un
   *  numero» y «este chico es otra cosa». */
  verdictBefore?: string | null;
}

/** Lo que el descubrimiento de esta semana significa para la academia entera.
 *  Una lista de techos sueltos no dice nada; esto si. */
export interface YouthSummary {
  revelations: number;
  /** Techos conocidos antes y ahora, sobre el total de lecturas posibles. */
  ceilingsBefore: number;
  ceilingsNow: number;
  readings: number;
  verdictChanges: { name: string; from: string | null; to: string }[];
  /** Quien salio de la academia desde el informe anterior. */
  left: { name: string; leftAt: string | null }[];
}

export interface ChangeMetricSummary {
  key: string;
  label: string;
  abbreviation: string;
  upCount: number;
  upTotal: number;
  downCount: number;
  downTotal: number;
  net: number;
}

export interface ClubComparisonChange {
  key: string;
  label: string;
  before: number | null;
  current: number | null;
  beforeDisplay: string | null;
  currentDisplay: string | null;
  delta: number | null;
  changed: boolean;
  isGood: boolean | null;
}

export interface SyncResult {
  syncId: number;
  status: "completed" | "partial";
  snapshotsWritten: number;
  unchanged: number;
  errors: string[];
  changes: SyncChange[];
}

export type SyncStreamEvent =
  | { type: "progress"; message: string }
  | { type: "done"; result: SyncResult }
  | { type: "error"; message: string };

export interface LastSyncChanges {
  syncId: number | null;
  syncedAt: string | null;
  changes: SyncChange[];
  reportSyncId: number | null;
  reportSyncedAt: string | null;
  reportIsLatest: boolean;
  reportChanges: SyncChange[];
  playerRows: PlayerComparisonRow[];
  /** La academia. Puede faltar en respuestas de una version anterior. */
  youthRows?: YouthComparisonRow[];
  /** El nombre de tu equipo juvenil. `null` sin sincronizar. */
  youthTeamName?: string | null;
  youthSummary?: YouthSummary;
  summary: ChangeMetricSummary[];
  clubChanges: ClubComparisonChange[];
  /** Partidos de selección jugados desde el informe anterior. */
  nationalMatches: NationalMatchAppearance[];
  /** Snapshots navegables, sólo los que tuvieron cambios reales, del más
   *  reciente al más antiguo. Elegir uno recalcula toda la comparación. */
  availableReports: { syncId: number; syncedAt: string; changeCount: number }[];
}

export interface NationalMatchAppearance {
  htPlayerId: number;
  name: string;
  minutes: number;
  rating: number | null;
  playedAt: string | null;
  competition: string;
  match: string;
}

export interface BackfillPending {
  /** Jugadores a los que les falta algo por descargar. */
  pending: number;
  batchSize: number;
  detail: {
    profile: number;
    purchasePrice: number;
    destination: number;
    /** A cuantos hay que construirles el historial completo esta primera vez. */
    census: number;
    /** Cuantos siguen pudiendo darnos comision algun dia. */
    resaleWatch: number;
  };
}

/** El recorrido de un barrido de comisiones. El eje se congela al empezar,
 *  así que una posición significa lo mismo de la primera pulsación a la
 *  última. */
export interface QueueMap {
  /** Casillas del eje: el ancho de la barra. */
  total: number;
  /** Posiciones ya atendidas. Se pintan como marcas. */
  done: number[];
  /** Casillas seguidas desde la izquierda: el bloque sólido. */
  front: number;
}

/** Cómo queda la vigilancia cuando el barrido para. */
export interface SweepBalance {
  /** Expedientes vivos: aún pueden dar comisión. */
  open: number;
  /** De este barrido, los que se quedaron sin mirar. */
  toCheck: number;
  /** Zanjados en este barrido, por motivo. */
  closed: Record<string, number>;
  closedTotal: number;
  /** Comisiones atribuidas durante este barrido. */
  commissions: number;
  /** A cuántos ex-jugadores se les reconstruyó el historial de partidos.
   *  Puede faltar en respuestas de una versión anterior del servidor. */
  histories?: number;
}

export interface BackfillBatchResult {
  status: string;
  /** Jugadores atendidos en este lote. */
  done: number;
  /** Los que siguen esperando. */
  pending: number;
  /** Apellidos de los atendidos, para decir por quien va. */
  players: string[];
  /** El mapa del barrido de comisiones, para pintar la barra como un
   *  recorrido por la cola. Llega entero en cada respuesta. */
  queue: QueueMap | null;
  /** El resumen para enseñar al parar. */
  balance: SweepBalance | null;
  errors: string[];
}

export interface HistoricalPlayerChange {
  capturedAt: string;
  htPlayerId: number;
  name: string;
  /** Un canterano, no un jugador del primer equipo. Su id vive en otro
   *  espacio y su ficha no está en /players, así que no se enlaza. */
  isYouth?: boolean;
  key: string;
  label: string;
  /** `null` en un DESCUBRIMIENTO: no se sabía y ahora sí. No hubo un antes,
   *  así que tampoco hay delta. Sólo pasa en la cantera. */
  before: number | null;
  current: number;
  delta: number | null;
  /** El cambio es una revelación del ojeador, no un movimiento. */
  isReveal?: boolean;
  /** El canterano LLEGÓ dentro de la ventana: esto no es un movimiento suyo,
   *  es con lo que entró por la puerta. */
  isArrival?: boolean;
}

export interface ChangesHistory {
  /** Ventana pedida, en semanas. */
  weeks: number;
  /** Fecha del cierre más antiguo con el que se comparó de verdad. Con menos
   *  historia que la ventana pedida, esto es más viejo de lo que sugiere
   *  `weeks`, o `null` si no hay con qué comparar. */
  comparedFrom: string | null;
  /** Los canteranos, con la misma regla de comparación que la plantilla pero
   *  sólo en niveles de habilidad: un juvenil no tiene TSI, salario, forma ni
   *  experiencia, y sus techos son revelaciones, no movimientos. */
  youthChanges?: HistoricalPlayerChange[];
  /** Las cifras de la academia recontadas EN ESTA VENTANA. `revelations` es
   *  un flujo y cambia entera; `ceilingsNow` es un stock --lo que se sabe
   *  hoy-- y lo que se mueve con la ventana es `ceilingsBefore`, con lo que
   *  se sabía al empezarla. */
  youthSummary?: {
    revelations: number;
    ceilingsNow: number;
    ceilingsBefore: number;
    readings: number;
  };
  players: { htPlayerId: number; name: string }[];
  selectedPlayerId: number | null;
  skillChanges: HistoricalPlayerChange[];
  experienceChanges: HistoricalPlayerChange[];
  loyaltyChanges: HistoricalPlayerChange[];
  formChanges: HistoricalPlayerChange[];
  /** TSI y Salario. El salario ya viene en la moneda local del equipo. */
  marketChanges: HistoricalPlayerChange[];
  series: {
    capturedAt: string;
    tsi: number;
    salary: number;
    form: number;
    experience: number;
    stamina: number;
  }[];
}

// ── Economía ────────────────────────────────────────────────────────────────

export const apiSincronizacion = {
  backfillPending: (teamId: number) =>
    request<BackfillPending>(`/teams/${teamId}/backfill`),
  /** Un lote y para. Devuelve cuantos atendio y cuantos quedan.
   *  `since` es el momento en que se pulso: acota la vigilancia de reventas a
   *  una sola pasada, porque esa cola no se agota sola. */
  runBackfillBatch: (teamId: number, since?: string) =>
    request<BackfillBatchResult>(
      `/teams/${teamId}/backfill/run${since ? `?since=${encodeURIComponent(since)}` : ""}`,
      { method: "POST" },
    ),
  /** Cada intento de venta, con su final. */
  sync: (teamId: number) =>
    request<SyncResult>(`/teams/${teamId}/sync`, { method: "POST" }),
  // 2026-08-05, pedido explícitamente: como la ventana "Conexión" de
  // Hattrick Control, una línea por fichero/jugador/partido a medida que
  // se descarga, no una espera muda de 15-20s. NDJSON sobre `fetch`, no
  // `EventSource` (solo hace GET, y este endpoint es un POST): se lee el
  // body como stream y se parte por saltos de línea a mano.
  syncStream: async (
    teamId: number,
    onEvent: (event: SyncStreamEvent) => void,
  ): Promise<void> => {
    const doSync = () =>
      fetch(`${BASE}/teams/${teamId}/sync/stream`, {
        method: "POST",
        credentials: "include",
        headers: idioma(),
      });
    let res = await doSync();
    // Mismo criterio que arriba: sólo se expulsa si el refresco no pudo
    // revivir la sesión.
    if (res.status === 401) {
      const renovacion = await refreshSession();
      if (renovacion === "viva") res = await doSync();
      else if (renovacion === "muerta") expireLocalSession();
    }
    if (!res.ok || !res.body) {
      let detail: unknown;
      try {
        detail = await res.json();
      } catch {
        detail = await res.text();
      }
      throw new ApiError(`${res.status} ${res.statusText}`, res.status, detail);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (line.trim()) onEvent(JSON.parse(line) as SyncStreamEvent);
      }
    }
    if (buffer.trim()) onEvent(JSON.parse(buffer) as SyncStreamEvent);
  },
  syncChanges: (teamId: number, syncId?: number | null) =>
    request<LastSyncChanges>(
      `/teams/${teamId}/sync/changes${syncId == null ? "" : `?sync_id=${syncId}`}`,
    ),
  changesHistory: (
    teamId: number,
    playerId?: number | null,
    weeks?: number,
  ) => {
    const params = new URLSearchParams();
    if (playerId != null) params.set("player_id", String(playerId));
    if (weeks != null) params.set("weeks", String(weeks));
    const query = params.toString();
    return request<ChangesHistory>(
      `/teams/${teamId}/changes/history${query ? `?${query}` : ""}`,
    );
  },
};
