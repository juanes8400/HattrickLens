import type { Club, PsychologySeries } from "../services/api/club";

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

/** Lo más que abarca cualquier gráfica de Club: dieciséis semanas, una
 *  temporada. 2026-11-14, pedido del usuario: «limitar las gráficas de Club y
 *  Cuerpo Técnico a 16 semanas máximo». */
export const SEMANAS_DE_LAS_GRAFICAS = 16;

const SEMANA_MS = 7 * 24 * 60 * 60 * 1000;

/** El instante a partir del cual se dibuja: `semanas` antes del dato más
 *  reciente (no de hoy, para que una cuenta que dejó de sincronizar no se
 *  quede con las gráficas vacías). `null` si no hay ninguna fecha. */
export function corteDeSemanas(
  fechas: (string | null | undefined)[],
  semanas: number = SEMANAS_DE_LAS_GRAFICAS,
): number | null {
  const ms = fechas
    .filter((x): x is string => Boolean(x))
    .map((x) => new Date(x).getTime())
    .filter(Number.isFinite);
  if (ms.length === 0) return null;
  return Math.max(...ms) - semanas * SEMANA_MS;
}

/** Los elementos cuya fecha no es anterior al corte. */
export function desdeElCorte<T>(
  items: T[],
  fecha: (x: T) => string,
  corte: number | null,
): T[] {
  if (corte == null) return items;
  return items.filter((x) => new Date(fecha(x)).getTime() >= corte);
}

const diaAlMediodia = (d: { day: string }) => `${d.day}${MEDIODIA}`;

/** El club con TODAS sus series recortadas a las últimas dieciséis semanas.
 *
 *  Un único corte para la pantalla entera, sacado de todo lo que se dibuja:
 *  así Psicología, Cuerpo técnico y Socios abarcan el mismo tramo, y las
 *  cuentas del pie (PIC, ventas, bajadas del %) hablan del mismo período que
 *  la gráfica que tienen encima. Se recortan los DATOS, no sólo el eje: la
 *  gráfica de Psicología no se sale de su marco, pero lo que quedara fuera
 *  se dibujaría a la izquierda, encima de las etiquetas. */
export function recortarClub(club: Club): Club {
  const psi = club.psychology;
  const corte = corteDeSemanas([
    ...psi.spirit.readings.map((r) => r.at),
    ...psi.confidence.readings.map((r) => r.at),
    ...psi.matches.map((m) => m.playedAt),
    ...[...psi.sellDays, ...psi.buyDays].map(diaAlMediodia),
    ...club.supporterHistory.map((s) => s.capturedAt),
    ...club.staffHistory.map((s) => s.capturedAt),
  ]);
  const serie = (s: PsychologySeries): PsychologySeries => ({
    ...s,
    readings: desdeElCorte(s.readings, (r) => r.at, corte),
    movements: desdeElCorte(s.movements, (m) => m.at, corte),
  });
  return {
    ...club,
    psychology: {
      ...psi,
      spirit: serie(psi.spirit),
      confidence: serie(psi.confidence),
      matches: desdeElCorte(psi.matches, (m) => m.playedAt, corte),
      buyDays: desdeElCorte(psi.buyDays, diaAlMediodia, corte),
      sellDays: desdeElCorte(psi.sellDays, diaAlMediodia, corte),
      intensityDrops: desdeElCorte(psi.intensityDrops, (x) => x, corte),
    },
    moodHistory: desdeElCorte(club.moodHistory, (h) => h.capturedAt, corte),
    supporterHistory: desdeElCorte(
      club.supporterHistory,
      (h) => h.capturedAt,
      corte,
    ),
    staffHistory: desdeElCorte(club.staffHistory, (h) => h.capturedAt, corte),
  };
}
