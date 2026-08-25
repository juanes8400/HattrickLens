import type { QueueMap } from "../services/api";

/** Lo que ocupa el bloque sólido de la barra, en porcentaje.
 *
 *  Sale del frente que manda el backend —el tramo seguido desde la izquierda
 *  del barrido congelado—, y sólo cae al porcentaje de siempre mientras no
 *  haya llegado ningún mapa. */
export function anchuraDelFrente(relleno: {
  mapa: QueueMap | null;
  hechos: number;
  total: number;
  quedan: number;
}): number {
  if (relleno.quedan === 0) return 100;
  if (relleno.mapa && relleno.mapa.total > 0) {
    return Math.min(100, (relleno.mapa.front / relleno.mapa.total) * 100);
  }
  return Math.min(100, (relleno.hechos / Math.max(relleno.total, 1)) * 100);
}

/** Dónde empieza una marca, en porcentaje del ancho. */
export function sitioDeLaMarca(posicion: number, total: number): number {
  if (total <= 0) return 0;
  return (posicion / total) * 100;
}

/** Lo que ocupa una marca: UNA casilla, ni más ni menos.
 *
 *  Estaba clavada a 3 px mientras el frente avanzaba en pasos proporcionales
 *  al eje —con 176 en cola, 7,19 px—, así que un salto al azar se veía a
 *  menos de la mitad de tamaño que un paso del frente y la barra mentía sobre
 *  cuánto trabajo representa cada uno. Ahora las dos cosas miden lo mismo
 *  porque salen de la misma cuenta. */
export function anchoDeLaMarca(total: number): number {
  if (total <= 0) return 0;
  return (1 / total) * 100;
}

/** Cómo se llama cada motivo de cierre en la pantalla. Los mismos nombres que
 *  usa el aviso de «Cambios», para que no haya dos vocabularios. */
const MOTIVOS: Record<string, [string, string]> = {
  revendido: ["revendido", "revendidos"],
  despedido: ["despedido", "despedidos"],
  sin_comprador: ["se fue sin comprador", "se fueron sin comprador"],
  entrenador: ["ahora es entrenador", "ahora son entrenadores"],
};

/** "2 revendidos, 1 despedido". Ordenado de más a menos, que es como se lee. */
export function motivosEnPalabras(cerrados: Record<string, number>): string {
  return Object.entries(cerrados)
    .filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([clave, n]) => {
      const [uno, varios] = MOTIVOS[clave] ?? [clave, clave];
      return `${n} ${n === 1 ? uno : varios}`;
    })
    .join(", ");
}
