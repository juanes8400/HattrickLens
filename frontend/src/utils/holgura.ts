import { tx } from "../i18n/tx";

/**
 * La holgura para vender (2026-11-23, pedido del usuario).
 *
 * Hattrick no deja poner en venta a un jugador más veces que partidos ha
 * jugado. Las dos cuentas van desde que llegó al club: los partidos los da
 * Hattrick y las veces en venta las cuenta HT Lens al sincronizar. Jugadores
 * y la ficha enseñan los dos números y la diferencia, para saber quién tiene
 * más margen y es quien conviene vender cuando se pueda.
 */
export function holgura(
  partidos: number | null | undefined,
  vecesEnVenta: number,
): number | null {
  return partidos == null ? null : partidos - vecesEnVenta;
}

/** Las tres explicaciones, en una función para que salgan en el idioma de
 *  la aplicación en el momento de pintarlas. */
export function explicacionesDeLaHolgura() {
  return {
    partidos: tx(
      "Partidos que ha jugado con tu club desde que llegó, según Hattrick. Hattrick no deja ponerlo en venta más veces que este número.",
    ),
    vecesEnVenta: tx(
      "Veces que HT Lens lo vio en venta desde que llegó a tu club. Depende de lo seguido que sincronices: si estuvo en venta y no sincronizaste mientras tanto, ese intento no se cuenta.",
    ),
    holgura: tx(
      "Partidos con el club menos veces en venta: cuántas veces más puedes ponerlo en venta. Con 0 no puedes volver a ponerlo hasta que juegue otro partido.",
    ),
  };
}
