/** Uso de la aplicacion.
 *
 *  Sale de partir `services/api.ts`, que tenia 4147 lineas y se leia entero
 *  en cada cambio del frontend. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../services/api"` sigue valiendo igual.
 */
import { request } from "./nucleo";

/** El resumen de uso de la aplicación. */
export interface UsageSummary {
  days: number;
  totals: {
    sessions: number;
    pages: number;
    clicks: number;
    minutes: number;
    medianSessionSeconds: number;
    clicksPerSession: number;
  };
  modules: {
    module: string;
    visits: number;
    clicks: number;
    minutes: number;
    avgSecondsPerVisit: number;
    lastSeen: string | null;
  }[];
  topControls: { label: string; clicks: number }[];
  byHour: Record<string, number>;
  /** Cuanta gente DISTINTA hubo en cada tramo, en los tres granos.
   *
   *  Los tres viajan juntos porque LA GENTE NO SE SUMA: quien entra lunes y
   *  martes son dos dias y UNA persona en la semana, asi que esta pantalla no
   *  puede agrupar por su cuenta sin inflar el numero. Cambiar el grano no
   *  vuelve al servidor.
   */
  overTime: Record<Grano, TramoDeUso[]>;
  recentSessions: {
    id: string;
    startedAt: string;
    seconds: number;
    pages: number;
    clicks: number;
    modules: string[];
  }[];
  /** Cuánta gente distinta apareció en el plazo, y cuánta hay registrada.
   *  Los dos hacen falta: «tres pantallas usadas por dos personas» sólo se
   *  entiende sabiendo cuántas podrían haberlas usado. */
  activeUsers: number;
  registeredUsers: number;
  /** Una fila por persona, con su propio desglose por pantalla dentro. */
  byUser: UsageUser[];
  /** Volumen y arraigo, separados a propósito. */
  adoption: {
    module: string;
    users: number;
    /** Porcentaje de los activos que la abrieron. */
    reach: number;
    days: number;
    visits: number;
    clicks: number;
    minutes: number;
    visitsPerUser: number;
    clicksPerVisit: number;
  }[];
  /** Lo más pulsado DENTRO de cada pantalla, no en el ranking global. */
  insideEach: {
    module: string;
    controls: { label: string; clicks: number }[];
  }[];
  /** Pantallas que nadie abrió en el plazo. */
  untouched: string[];
  /** De dónde es la gente, para el mapa. `code` vacío es «no consta»: quien
   *  no tiene club sincronizado, o lo tiene en una liga internacional. */
  byCountry: {
    code: string;
    name: string;
    users: number;
    sessions: number;
    pages: number;
    clicks: number;
    minutes: number;
  }[];
}

/** Los tres granos de la serie. */
export type Grano = "day" | "week" | "month";

export interface TramoDeUso {
  /** La fecha de comienzo del tramo, en ISO. */
  from: string;
  /** Personas distintas con actividad. */
  users: number;
  /** De esas, las que aparecen por PRIMERA VEZ DE SIEMPRE, no la primera vez
   *  dentro del plazo elegido. Por eso no cambia al acortar el plazo. */
  newUsers: number;
  sessions: number;
  pages: number;
  clicks: number;
  minutes: number;
}

export interface UsageUserModule {
  module: string;
  visits: number;
  clicks: number;
  minutes: number;
  avgSecondsPerVisit: number;
  lastSeen: string | null;
}

export interface UsageUser {
  userId: number;
  name: string;
  /** Su pais, para la bandera. Sale de la liga del club, igual que el del
   *  mapa; vacio es «no consta», que es lo de quien no ha sincronizado. */
  countryCode: string;
  countryName: string;
  sessions: number;
  pages: number;
  clicks: number;
  minutes: number;
  /** Días DISTINTOS con actividad. Volver otro día dice más que diez visitas
   *  en una tarde. */
  activeDays: number;
  clicksPerPage: number;
  favouriteModule: string;
  firstSeen: string | null;
  lastSeen: string | null;
  modules: UsageUserModule[];
}

/** Una página del registro crudo. */
export interface UsageLog {
  total: number;
  from: number;
  rows: {
    id: number;
    at: string;
    userId: number;
    name: string;
    session: string;
    kind: "page" | "click";
    module: string;
    label: string | null;
    visibleMs: number;
  }[];
  /** Quién aparece, para el desplegable del filtro Y para la bandera de cada
   *  fila: el registro trae el id y el nombre, y un nombre de Hattrick no dice
   *  de dónde es nadie. También sitúa los destellos del mapa en vivo. */
  users: {
    userId: number;
    name: string;
    countryCode: string;
    countryName: string;
  }[];
  modules: string[];
}

export interface UsageLogFiltros {
  dias?: number;
  usuario?: number | null;
  modulo?: string | null;
  tipo?: "page" | "click" | null;
  buscar?: string | null;
  desdeFila?: number;
  cuantas?: number;
  /** Dejar fuera los eventos de quien pregunta. */
  excluirme?: boolean;
}

/** Un fallo reportado desde dentro de la aplicación. */
export interface ReporteDeFallo {
  id: number;
  at: string;
  userId: number;
  name: string;
  /** La pantalla desde la que se escribió, rellenada sola. */
  module: string;
  text: string;
  userAgent: string;
  atendido: boolean;
}

export interface ReportesDeFallos {
  /** Cuántos faltan por atender EN TOTAL, no en esta página. */
  pending: number;
  rows: ReporteDeFallo[];
}

/** Un aviso del autor para todos los que usan la herramienta.
 *
 *  2026-11-03. Sale por las alertas que ya se miran, con la clave
 *  `author.notice.{id}`, así que no hay pantalla nueva del lado del que lo
 *  lee: lo de aquí es sólo el lado del que lo escribe. */
export interface AvisoDelAutor {
  id: number;
  at: string;
  author: string;
  title: string;
  detail: string;
  action: string;
  severity: "info" | "opportunity" | "warning" | "danger";
  /** Nulo = hasta que se retire a mano. */
  until: string | null;
  retiredAt: string | null;
  /** Si ahora mismo se está emitiendo. Lo resuelve el servidor para que la
   *  pantalla no tenga que repetir la regla de `until` + `retiredAt`. */
  vivo: boolean;
}

export interface AvisoNuevo {
  title: string;
  detail: string;
  action?: string;
  severity?: AvisoDelAutor["severity"];
  until?: string | null;
}

export const apiUso = {
  usage: (dias = 0, excluirme = false) =>
    request<UsageSummary>(
      `/usage?dias=${dias}${excluirme ? "&excluirme=true" : ""}`,
    ),
  /** El registro crudo, filtrado y paginado en el servidor. */
  usageLog: (f: UsageLogFiltros = {}) => {
    const q = new URLSearchParams({ dias: String(f.dias ?? 30) });
    if (f.usuario != null) q.set("usuario", String(f.usuario));
    if (f.modulo) q.set("modulo", f.modulo);
    if (f.tipo) q.set("tipo", f.tipo);
    if (f.buscar) q.set("buscar", f.buscar);
    if (f.desdeFila) q.set("desde_fila", String(f.desdeFila));
    if (f.cuantas) q.set("cuantas", String(f.cuantas));
    if (f.excluirme) q.set("excluirme", "true");
    return request<UsageLog>(`/usage/log?${q}`);
  },
  /** Anota cuantas veces vieron al jugador, o ignora la pregunta. */

  /** Cuenta un fallo. LO PUEDE MANDAR CUALQUIERA que haya entrado, no sólo el
   *  administrador: un canal de reportes que sólo usa el dueño no es un canal
   *  de reportes. */
  reportarFallo: (texto: string, pantalla: string) =>
    request<void>(`/feedback`, {
      method: "POST",
      body: JSON.stringify({ text: texto, module: pantalla }),
    }),
  /** Los reportes recibidos. Sólo el administrador. */
  reportes: (soloPendientes = false) =>
    request<ReportesDeFallos>(
      `/feedback${soloPendientes ? "?pendientes=true" : ""}`,
    ),
  atenderReporte: (id: number, atendido: boolean) =>
    request<void>(`/feedback/${id}/atendido?atendido=${atendido}`, {
      method: "POST",
    }),

  /** Publica un aviso para todos. Sólo el administrador. */
  publicarAviso: (aviso: AvisoNuevo) =>
    request<{ id: number }>(`/avisos`, {
      method: "POST",
      body: JSON.stringify(aviso),
    }),
  /** Todos los avisos, vivos y retirados. Los retirados siguen porque son el
   *  único sitio donde queda qué se dijo y cuándo. */
  avisos: () => request<{ avisos: AvisoDelAutor[] }>(`/avisos`),
  retirarAviso: (id: number, retirado: boolean) =>
    request<void>(`/avisos/${id}/retirar?retirado=${retirado}`, {
      method: "POST",
    }),
};
