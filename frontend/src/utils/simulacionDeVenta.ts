/** Qué dejaría vender a alguien que TODAVÍA está en el club.
 *
 *  2026-10-03, pedido por un usuario: Transferencias sólo miraba hacia atrás,
 *  lo ya comprado y vendido. Esto mira hacia delante con un precio que te
 *  inventas tú, y responde la pregunta de siempre: a este precio, ¿gano o
 *  pierdo con él?
 *
 *  LA FÓRMULA ES LA DE LA CASA, NO UNA NUEVA. Es exactamente la que el libro
 *  de transferencias aplica a una venta de verdad:
 *
 *      venta_neta = precio · (1 − %agente)
 *      saldo      = venta_neta − gastos + reventa
 *      ROI        = saldo ÷ gastos · 100
 *
 *  Los dos números que no se calculan aquí son justo los que no se pueden
 *  adivinar desde el navegador: `agentPct` --que depende de los días que
 *  lleva en el club y de si es canterano-- y `gastos` --compra o ascenso, más
 *  los sueldos que se le han pagado, más los intentos de venta--. Los dos
 *  llegan del servidor, de la misma fila que cuenta la historia real, para
 *  que la simulación de hoy y la venta de mañana no digan cosas distintas.
 */

export interface SimulacionDeVenta {
  /** Lo que entra en caja: el precio menos lo que se lleva la casa. */
  neto: number;
  /** Neto menos lo invertido. Negativo es pérdida. */
  saldo: number;
  /** El saldo como porcentaje de lo invertido; `null` si no se invirtió nada
   *  (no se puede dividir, y un ROI infinito no significa nada). */
  roiPct: number | null;
  /** El precio al que el saldo sería exactamente cero: lo que hay que pedir
   *  para no perder. `null` cuando la casa se lo llevaría todo. */
  precioDeEquilibrio: number | null;
}

/** Redondeo al par, como el `round` de Python.
 *
 *  Importa aquí y en ningún otro sitio: el saldo lo escribe el servidor para
 *  las ventas reales y el navegador para las simuladas, y con `Math.round`
 *  --que sube siempre-- un precio que cae justo en medio daba una unidad de
 *  diferencia entre lo que la simulación prometió y lo que el libro apuntó.
 */
function redondeoAlPar(valor: number): number {
  const entero = Math.floor(valor);
  const resto = valor - entero;
  if (resto > 0.5) return entero + 1;
  if (resto < 0.5) return entero;
  return entero % 2 === 0 ? entero : entero + 1;
}

export function simularVenta({
  precio,
  agentPct,
  gastos,
  resaleBonusShare = 0,
}: {
  precio: number;
  /** Fracción, no porcentaje: 0,1327 es el 13,27 %. */
  agentPct: number;
  gastos: number;
  resaleBonusShare?: number;
}): SimulacionDeVenta {
  const neto = redondeoAlPar(precio * (1 - agentPct));
  const saldo = neto - gastos + resaleBonusShare;
  const roiPct = gastos > 0 ? Math.round((saldo / gastos) * 10000) / 100 : null;
  const precioDeEquilibrio =
    agentPct < 1
      ? Math.ceil((gastos - resaleBonusShare) / (1 - agentPct))
      : null;
  return { neto, saldo, roiPct, precioDeEquilibrio };
}
