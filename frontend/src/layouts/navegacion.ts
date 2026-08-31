/** La lista de pantallas del menú, y lo que se deriva de ella.
 *
 *  Vive fuera del componente a propósito: es dato y lógica pura, sin DOM ni
 *  React, así que se puede probar sin montar la aplicación. `AppLayout` toca
 *  `localStorage` al cargarse, y con él dentro no había forma de probar la
 *  agrupación (2026-08-31).
 */
export const NAV = [
  { section: "Club" },
  { to: "/dashboard", label: "Dashboard" },
  { to: "/club", label: "Club y cuerpo técnico" },
  { to: "/overview", label: "Equipo" },
  { to: "/team", label: "Jugadores" },
  { to: "/positions", label: "Posiciones" },
  { to: "/lineup", label: "Alineación" },
  { section: "Desarrollo" },
  { to: "/training", label: "Entrenamiento" },
  { to: "/academy", label: "Juveniles" },
  { to: "/transfers/balance", label: "Transferencias" },
  { section: "Competición" },
  { to: "/matches", label: "Partidos" },
  { to: "/league", label: "Liga" },
  { to: "/cup", label: "Copa" },
  { to: "/rivals", label: "Rivales" },
  { section: "Negocio" },
  { to: "/economy", label: "Economía" },
  { to: "/arena", label: "Estadio" },
  { section: "Inteligencia" },
  // Sincronización va justo antes de Cambios: es el orden en que se usan
  // (sincronizas y de inmediato miras qué cambió).
  { to: "/sync", label: "Sincronización" },
  { to: "/news", label: "Cambios" },
  { to: "/insights", label: "Alertas" },
  { to: "/transparency", label: "Transparencia" },
];

/** Cómo se llama la página que hay en esa ruta.
 *
 *  Vive pegado a `NAV` a propósito: es la misma lista que ya nombra cada
 *  pantalla en la barra lateral, así que una página nueva se titula sola y
 *  nadie tiene que acordarse de tocar dos sitios --el mismo trato que ya
 *  tiene la telemetría--.
 *
 *  Hasta el 2026-08-30 las veinticinco pantallas compartían el título «HT
 *  Lens»: dos pestañas abiertas eran indistinguibles, el historial del
 *  navegador era una columna del mismo texto repetido y un marcador no decía
 *  a qué apuntaba. */
const RUTAS_CON_DETALLE: { prefijo: string; label: string }[] = [
  { prefijo: "/players/", label: "Jugador" },
  { prefijo: "/rivals/", label: "Rival" },
];

export function tituloDeRuta(pathname: string): string {
  const detalle = RUTAS_CON_DETALLE.find((r) => pathname.startsWith(r.prefijo));
  if (detalle) return `${detalle.label} · HT Lens`;

  // La coincidencia más larga gana: `/transfers/balance` antes que nada que
  // empiece por `/transfers`.
  const enlaces = [...NAV, { to: "/uso", label: "Uso" }].filter(
    (item): item is { to: string; label: string } => "to" in item,
  );
  let mejor: { to: string; label: string } | undefined;
  for (const item of enlaces) {
    if (pathname === item.to || pathname.startsWith(`${item.to}/`)) {
      if (!mejor || item.to.length > mejor.to.length) mejor = item;
    }
  }
  return mejor ? `${mejor.label} · HT Lens` : "HT Lens";
}

type Enlace = { to: string; label: string };
type Grupo = { titulo: string; enlaces: Enlace[] };

/** Convierte la lista plana de `NAV` --rótulos y enlaces mezclados como
 *  hermanos-- en los grupos que ya se veían pintados.
 *
 *  Se agrupa aquí y no en `NAV` para que la lista siga siendo cómoda de
 *  editar: se añade un enlace debajo de su rótulo y ya. */
export function agrupar(
  items: readonly ({ section: string } | Enlace)[],
): Grupo[] {
  const grupos: Grupo[] = [];
  for (const item of items) {
    if ("section" in item) {
      grupos.push({ titulo: item.section, enlaces: [] });
      continue;
    }
    const actual = grupos[grupos.length - 1];
    if (actual) actual.enlaces.push(item);
    // Un enlace antes del primer rótulo se quedaría sin grupo; hoy no pasa
    // --NAV empieza por «Club»-- y si pasara, se vería al instante.
  }
  return grupos.filter((g) => g.enlaces.length > 0);
}
