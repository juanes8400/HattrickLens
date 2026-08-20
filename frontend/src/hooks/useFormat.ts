// Separador de miles único para toda la aplicación. No dependemos del locale
// disponible en el navegador: el formato visible siempre es 1.234.567.
export const number = (v: number) =>
  Math.round(v)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, ".");

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
  if (!iso) return ", ";
  const d = parseUtc(iso);
  if (Number.isNaN(d.getTime())) return ", ";
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
