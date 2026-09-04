// Separador de miles único para toda la aplicación. No dependemos del locale
// disponible en el navegador: el formato visible siempre es 1.234.567.
export const number = (v: number) =>
  Math.round(v)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, ".");

// Una cifra que puede llegar como número o como texto: un TSI es 207890 y un
// nivel de confianza es «Excelente». Los enteros se formatean; el texto pasa
// tal cual. Existe porque los feeds de cambios pintaban `String(valor)` y se
// veía «207890 ▼ 177190 (-30.700)»: el delta con separador y los extremos sin
// él, en el mismo renglón (2026-09-04).
export const cifra = (v: string | number | boolean | null | undefined) =>
  typeof v === "number" && Number.isInteger(v) ? number(v) : String(v ?? "");

export const money = (v: number, currency = "") =>
  `${number(v)}${currency ? ` ${currency}` : ""}`;

// Política numérica de HT Lens (2026-08-14): los valores decimales usan
// punto, nunca la coma dependiente del locale del navegador. La cantidad de
// decimales la decide cada métrica; por ejemplo 3.5 semanas o 10.99 puntos.
export const decimal = (v: number, digits = 1) => Number(v).toFixed(digits);

// Para tooltips y métricas cuya precisión es variable: conserva como máximo
// ``digits`` decimales, elimina ceros finales y jamás introduce coma decimal.
export const metric = (v: number, digits = 3) => {
  const value = Number(v);
  if (Number.isInteger(value)) return number(value);
  return value
    .toFixed(digits)
    .replace(/(\.\d*?)0+$/, "$1")
    .replace(/\.$/, "");
};

export const htAge = (years: number, days: number) => `${years}.${days}`;

// Formato de fecha único para TODA la herramienta, pedido explícitamente
// 2026-08-05: dd/mm/yyyy con ceros a la izquierda — Intl.toLocaleDateString
// con locale "es-CO" da d/m/yyyy (sin ceros), que no es lo pedido.
/**
 * Toda fecha que sale del backend está en UTC. Las que llegan sin marca de
 * zona ("2026-08-19T22:10:00") las interpretaría el navegador como hora
 * local, que es justo el error que hacía ver un partido de Copa siete horas
 * más tarde de lo real. Añadir la Z que falta lo convierte a la hora del
 * usuario correctamente.
 */
export const parseUtc = (iso: string) =>
  new Date(/(?:Z|[+-]\d{2}:\d{2})$/i.test(iso) ? iso : `${iso}Z`);

export const date = (iso: string | null | undefined) => {
  // Una fecha que falta es una raya. Aquí había una coma, y como este
  // formateador lo usa media aplicación, era la FUENTE de las comas sueltas
  // que se fueron arreglando una a una en las celdas (2026-08-30 y 08-31):
  // se estaban tapando los síntomas mientras el origen seguía en pie.
  if (!iso) return "—";
  const d = parseUtc(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  return `${dd}/${mm}/${d.getFullYear()}`;
};

export const relative = (iso: string | null) => {
  if (!iso) return "nunca";
  const then = parseUtc(iso).getTime();
  const mins = Math.round((Date.now() - then) / 60000);
  if (mins < 1) return "ahora";
  if (mins < 60) return `hace ${mins} min`;
  const h = Math.round(mins / 60);
  return h < 24 ? `hace ${h} h` : `hace ${Math.round(h / 24)} d`;
};

/** Un porcentaje con la politica de la casa: decimales con PUNTO.
 *
 *  Existia disperso como `toLocaleString("es", {...})`, que da coma decimal
 *  --exactamente lo que la politica de arriba prohibe-- y ademas mezclaba
 *  tres criterios de idioma distintos por la aplicacion (2026-08-31). */
export const percent = (v: number, digits = 1) => `${decimal(v, digits)}%`;

/** Cifras grandes abreviadas para los ejes: «2.4 M» en vez de «2400000».
 *  Sin `Intl`, que en espanol devuelve coma decimal. */
export const compact = (v: number) => {
  const abs = Math.abs(v);
  if (abs >= 1_000_000) return `${decimal(v / 1_000_000)} M`;
  if (abs >= 1_000) return `${decimal(v / 1_000)} mil`;
  return number(v);
};

/** Fecha y hora en el formato de la casa. La unica del codigo que se
 *  formateaba con `toLocaleString()` SIN idioma usaba el del navegador de
 *  quien mira: en un navegador en ingles la pantalla de Uso mostraba
 *  «8/31/2026, 4:12:00 PM» mientras el resto de la app iba en espanol. */
export const dateTime = (iso: string | null | undefined) => {
  if (!iso) return "—";
  const d = parseUtc(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${date(iso)} ${hh}:${mm}`;
};
