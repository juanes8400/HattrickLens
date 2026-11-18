/** El filtro «clasificación → grupo» (2026-11-18): el mismo en Jugadores y
 *  en Transferencias → Plantilla actual. Va aparte del componente para que
 *  la recarga en caliente siga funcionando y para poder probarlo sin DOM. */
import type { ClasesDeJugador } from "../../services/api";
import { clasificaciones, type Clasificacion } from "./clasificaciones";

/** Qué se mira. Vacío = todo; con clasificación y sin grupo, también todo. */
export interface ValorDelFiltro {
  clasificacion: string;
  grupo: string;
}

export const SIN_FILTRO: ValorDelFiltro = { clasificacion: "", grupo: "" };

/** Las clasificaciones que se pueden elegir: Mis grupos sólo si hay alguno. */
export function clasificacionesElegibles(
  datos: ClasesDeJugador,
): Clasificacion[] {
  return clasificaciones(datos).filter((c) => c.grupos.length > 0);
}

/** Los jugadores que deja pasar el filtro, o `null` si no filtra nada.
 *
 *  Un valor guardado que ya no existe --un grupo propio borrado, una etapa
 *  que hoy no tiene a nadie-- no filtra: vaciar la tabla por una elección
 *  vieja parecería un fallo. */
export function idsDelFiltro(
  datos: ClasesDeJugador,
  valor: ValorDelFiltro,
): Set<number> | null {
  if (!valor.clasificacion || !valor.grupo) return null;
  const c = clasificacionesElegibles(datos).find(
    (x) => x.clave === valor.clasificacion,
  );
  const g = c?.grupos.find((x) => x.clave === valor.grupo);
  if (!g) return null;
  return new Set(g.jugadores.map((j) => j.htPlayerId));
}
