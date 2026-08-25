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
