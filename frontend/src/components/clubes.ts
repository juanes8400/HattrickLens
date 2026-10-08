/** Lo que se sabe de los clubes de un manager, sin pintar nada.
 *
 *  Vive aparte de `SelectorDeClub.tsx` porque un fichero de componentes que
 *  exporta además funciones sueltas rompe el refresco en caliente de Vite: al
 *  guardar, la pantalla entera se recarga en vez de cambiar el trozo tocado.
 */
import { ordinal } from "../hooks/useFormat";
import { setActiveTeamId } from "../hooks/useTeam";
import type { SessionTeam } from "../services/api";

/** «1º · Pulgas Arrechas», y el que no se ha importado lo dice.
 *
 *  El número es la posición en la lista, y la lista llega con el club
 *  principal delante: el «1º» de un manager es su club principal, no el
 *  primero del alfabeto. El ordinal pasa por `ordinal` porque cada idioma lo
 *  escribe distinto («1º», «1st», «1.»).
 *
 *  Lo de «sin importar» no es decoración: cambiar a un club que nunca se
 *  sincronizó deja la aplicación entera en blanco, y sin avisar eso se lee
 *  como que la aplicación se rompió al cambiar.
 */
export function nombreDelClub(
  club: SessionTeam,
  indice: number,
  t: (clave: string, defecto: string) => string,
): string {
  const numero = ordinal(indice + 1);
  if (club.hasImportedData) return `${numero} · ${club.name}`;
  return `${numero} · ${club.name} (${t("layout.clubSinImportar", "sin importar")})`;
}

/** Guarda el club elegido y recarga de verdad.
 *
 *  `TEAM_ID` se evalúa AL CARGAR EL MÓDULO --es una constante, no un estado--
 *  así que una navegación blanda dejaría media aplicación pidiendo datos del
 *  club anterior. Una recarga de verdad garantiza que todo el árbol, y la
 *  caché de react-query con él, arranque con el club nuevo. Es lo mismo que
 *  hace `ConnectedPage` al volver de la autorización.
 */
export function cambiarDeClub(id: number): void {
  setActiveTeamId(id);
  window.location.assign(destinoTrasCambiarDeClub(window.location.pathname));
}

/** A dónde se cae al cambiar de club.
 *
 *  Se queda en la misma pantalla, que es lo que uno espera: si estabas en
 *  Economía comparando, quieres la Economía del otro club. Pero las rutas que
 *  llevan un identificador dentro --`/players/498724298`, `/rivals/1750123`--
 *  nombran a alguien que en el otro club no existe, y recargarlas da un 404
 *  que parece un fallo del cambio. Ésas vuelven al panel.
 */
export function destinoTrasCambiarDeClub(ruta: string): string {
  return /\/\d+/.test(ruta) ? "/dashboard" : ruta;
}
