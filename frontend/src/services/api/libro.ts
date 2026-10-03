/** Libro de visitas.
 *
 *  Sale de partir `services/api.ts`, que tenia 4147 lineas y se leia entero
 *  en cada cambio del frontend. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../services/api"` sigue valiendo igual.
 */
import { request } from "./nucleo";

/** Una firma del libro de visitas.
 *
 *  Sale el nombre del CLUB y su liga, nunca el de la cuenta: en Hattrick uno
 *  se conoce por su equipo, y publicar el login de alguien sería dar un dato
 *  que no hace falta. `teamName` puede venir vacío si quien firma todavía no
 *  ha sincronizado ningún club.
 */
export type GuestbookEntry = {
  id: number;
  teamName: string;
  country: string;
  message: string;
  createdAt: string;
};

export const apiLibro = {
  guestbook: () => request<{ entries: GuestbookEntry[] }>(`/guestbook`),
  /** Dejar una firma. Pide sesión: por eso no se puede firmar en anónimo. */
  signGuestbook: (message: string) =>
    request<GuestbookEntry>(`/guestbook`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    }),
  /** El resumen de uso. Sólo lo abre el administrador.
   *  `dias = 0` es «Siempre», que es lo que la pantalla pide al entrar. */
};
