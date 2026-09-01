/** El ancho del eje de las gráficas de Psicología.
 *
 *  Vive fuera de la pantalla a propósito: es lógica pura, sin DOM ni React,
 *  así que se puede probar sin montar la aplicación. `ClubPage` toca
 *  `localStorage` al cargarse y con la función dentro no había forma de
 *  probarla (mismo motivo que llevó `agrupar` a `navegacion.ts`).
 */

/** Lo mínimo que hace falta de cada serie para saber cuánto abarca. */
export interface FuentesDeLaVentana {
  /** Marcas de tiempo completas (`2026-08-20T15:32:33`). */
  instantes: (string | null | undefined)[];
  /** Días sueltos del pulso de mercado (`2026-07-07`). */
  dias: string[];
}

/** Los días del mercado se dibujan al MEDIODÍA; se cuentan con esa hora para
 *  que el punto no acabe pegado al marco. */
const MEDIODIA = "T12:00:00";

/**
 * De cuándo a cuándo tiene que llegar el eje.
 *
 * La regla de fondo: **una gráfica cubre con su escala todo lo que dibuja**.
 *
 * Antes el eje se calculaba con las lecturas, los partidos y los socios, pero
 * la gráfica pintaba además el pulso de compras y ventas, que el backend saca
 * con su propia ventana de ocho semanas. Cuando la operación más antigua era
 * anterior al primer partido, sus puntos caían a la IZQUIERDA del eje: encima
 * de las etiquetas y fuera del dibujo.
 *
 * En producción eran seis puntos --el mercado empieza el 7 de julio y el
 * primer partido es del 12-- y en la copia local no se veía, porque allí el
 * partido más antiguo es anterior a la primera venta (2026-09-01).
 */
export function ventanaDeGraficas(
  fuentes: FuentesDeLaVentana,
  ahora: () => Date = () => new Date(),
): { from: string; to: string } {
  const fechas = [
    ...fuentes.instantes.filter((x): x is string => Boolean(x)),
    ...fuentes.dias.map((d) => `${d}${MEDIODIA}`),
  ].sort();

  const porDefecto = ahora().toISOString();
  const primera = new Date(fechas[0] ?? porDefecto);
  const ultima = new Date(fechas[fechas.length - 1] ?? porDefecto);

  // Un día de aire a cada lado: sin él, el primer y el último punto quedan
  // pegados al marco y no se distingue el círculo de la lectura.
  primera.setDate(primera.getDate() - 1);
  ultima.setDate(ultima.getDate() + 1);
  return { from: primera.toISOString(), to: ultima.toISOString() };
}
