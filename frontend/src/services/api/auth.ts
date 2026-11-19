/** Entrar, salir y saber quien es.
 *
 *  Sale de partir `services/api.ts`, que tenia 4147 lineas y se leia entero
 *  en cada cambio del frontend. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../services/api"` sigue valiendo igual.
 */
import { request } from "./nucleo";

export interface SessionTeam {
  id: number;
  htTeamId: number;
  name: string;
  leagueName: string | null;
  seriesName: string | null;
  syncedAt: string | null;
  hasImportedData: boolean;
  /** El club PRINCIPAL del manager, dicho por Hattrick (`IsPrimaryClub`). Los
   *  clubes llegan con él delante, así que es también el «1º» del mando que
   *  cambia de club. `null` = Hattrick todavía no lo ha dicho. */
  isPrimaryClub: boolean | null;
}

export interface SessionProfile {
  user: {
    id: number;
    htUserId: number | null;
    loginName: string | null;
    /** Si puede abrir la pantalla de uso. La comprobación de verdad está en el
     *  servidor; esto sólo decide si se enseña el enlace. */
    isAdmin: boolean;
  };
  connectionStatus: "active" | "revoked" | "missing";
  teams: SessionTeam[];
}

/** Los permisos que Hattrick dice que tiene tu acceso (2026-11-19). `null`
 *  donde Hattrick no contestó: no saberlo no es no tenerlo. */
export interface PermisosDeHattrick {
  permisos: string[] | null;
  pedidos: string[];
  faltan: string[] | null;
  puedeEnviarAlineacion: boolean | null;
}

export const apiAuth = {
  sessionProfile: () => request<SessionProfile>(`/auth/chpp/session`),
  permisosDeHattrick: () => request<PermisosDeHattrick>(`/auth/chpp/permisos`),
  connectChpp: () => request<{ authorizeUrl: string }>(`/auth/chpp/connect`),
};
