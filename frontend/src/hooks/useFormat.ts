// Separador de miles único para toda la aplicación. No dependemos del locale
// disponible en el navegador: el formato visible siempre es 1.234.567.
export const number = (v: number) =>
  Math.round(v)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, ".");

export const money = (v: number, currency = "") =>
  `${number(v)}${currency ? ` ${currency}` : ""}`;

export const htAge = (years: number, days: number) => `${years}.${days}`;

// Formato de fecha único para TODA la herramienta, pedido explícitamente
// 2026-08-05: dd/mm/yyyy con ceros a la izquierda — Intl.toLocaleDateString
// con locale "es-CO" da d/m/yyyy (sin ceros), que no es lo pedido.
export const date = (iso: string | null | undefined) => {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  return `${dd}/${mm}/${d.getFullYear()}`;
};

export const relative = (iso: string | null) => {
  if (!iso) return "nunca";
  const hasTimezone = /(?:Z|[+-]\d{2}:\d{2})$/i.test(iso);
  const then = new Date(hasTimezone ? iso : `${iso}Z`).getTime();
  const mins = Math.round((Date.now() - then) / 60000);
  if (mins < 1) return "ahora";
  if (mins < 60) return `hace ${mins} min`;
  const h = Math.round(mins / 60);
  return h < 24 ? `hace ${h} h` : `hace ${Math.round(h / 24)} d`;
};
