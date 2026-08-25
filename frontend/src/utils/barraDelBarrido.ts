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

/** Dónde se pinta una marca, de 0 a 99,5 %. El tope evita que la última
 *  casilla se salga del borde redondeado. */
export function sitioDeLaMarca(posicion: number, total: number): number {
  return Math.min(99.5, (posicion / total) * 100);
}
