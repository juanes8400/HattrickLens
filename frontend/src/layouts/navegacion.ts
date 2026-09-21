import i18n from "../i18n";

/** La lista de pantallas del menú, y lo que se deriva de ella.
 *
 *  Vive fuera del componente a propósito: es dato y lógica pura, sin DOM ni
 *  React, así que se puede probar sin montar la aplicación. `AppLayout` toca
 *  `localStorage` al cargarse, y con él dentro no había forma de probar la
 *  agrupación (2026-08-31).
 *
 *  Traducción (2026-09-15): cada entrada lleva `clave`, y su nombre se busca
 *  en `nav.<clave>`. El texto en español se queda aquí como valor por defecto,
 *  así que en español no cambia nada aunque falte la traducción.
 */
export const NAV = [
  { section: "Club", clave: "seccion.club" },
  { to: "/dashboard", label: "Dashboard", clave: "dashboard" },
  { to: "/club", label: "Club y cuerpo técnico", clave: "club" },
  { to: "/overview", label: "Habilidades", clave: "equipo" },
  { to: "/team", label: "Jugadores", clave: "jugadores" },
  { to: "/skills", label: "Equipo", clave: "habilidades" },
  { to: "/positions", label: "Posiciones", clave: "posiciones" },
  { to: "/lineup", label: "Alineación", clave: "alineacion" },
  { section: "Desarrollo", clave: "seccion.desarrollo" },
  { to: "/training", label: "Entrenamiento", clave: "entrenamiento" },
  { to: "/academy", label: "Juveniles", clave: "juveniles" },
  { section: "Competición", clave: "seccion.competicion" },
  { to: "/matches", label: "Partidos", clave: "partidos" },
  { to: "/league", label: "Liga", clave: "liga" },
  { to: "/cup", label: "Copa", clave: "copa" },
  { to: "/rivals", label: "Rivales", clave: "rivales" },
  { section: "Negocio", clave: "seccion.negocio" },
  { to: "/economy", label: "Economía", clave: "economia" },
  // Transferencias baja aquí desde Desarrollo (2026-09-20, pedido del
  // usuario): lo que enseña es dinero --coste de compra, sueldos acumulados,
  // comisiones, beneficio y ROI-- y no el crecimiento de un jugador, así que
  // vive entre las cuentas y el estadio, no junto a Entrenamiento.
  {
    to: "/transfers/balance",
    label: "Transferencias",
    clave: "transferencias",
  },
  { to: "/arena", label: "Estadio", clave: "estadio" },
  { section: "Inteligencia", clave: "seccion.inteligencia" },
  // Sincronización va justo antes de Cambios: es el orden en que se usan
  // (sincronizas y de inmediato miras qué cambió).
  { to: "/sync", label: "Sincronización", clave: "sincronizacion" },
  { to: "/news", label: "Cambios", clave: "cambios" },
  { to: "/insights", label: "Alertas", clave: "alertas" },
  { to: "/transparency", label: "Transparencia", clave: "transparencia" },
  // Junto a Transparencia: una explica cada número, la otra cada pantalla.
  { to: "/wiki", label: "Wiki", clave: "wiki" },
  // Última, y en su propia sección: es lo único de la aplicación que no
  // depende de haber sincronizado nada, así que no pertenece a ninguna de
  // las otras (2026-09-02).
  { section: "Acerca de", clave: "seccion.acerca" },
  { to: "/autor", label: "Autor", clave: "autor" },
  // Debajo de Autor: quien quiere escribirle a alguien primero mira quién es.
  { to: "/libro", label: "Libro de visitas", clave: "libro" },
  // El botón del café del menú lleva aquí, pero también tiene su entrada:
  // quien ya la cerró una vez debe poder volver sin buscarla.
  { to: "/apoyar", label: "Apoyar el proyecto", clave: "apoyar" },
];

/** La entrada de «Uso», que sólo ve el administrador. */
export const USO = { to: "/uso", label: "Uso", clave: "uso" };

/** El nombre de una entrada del menú en el idioma de la app; sin clave, tal cual. */
export function nombreNav(texto: string, clave?: string): string {
  return clave ? i18n.t(`nav.${clave}`, texto) : texto;
}

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
const RUTAS_CON_DETALLE: { prefijo: string; label: string; clave: string }[] = [
  { prefijo: "/players/", label: "Jugador", clave: "jugador" },
  { prefijo: "/rivals/", label: "Rival", clave: "rival" },
];

/** Las pantallas de entrada, que no están en el menú.
 *
 *  Caían al valor de reserva y su pestaña decía «HT Lens» a secas: eran las
 *  dos únicas indistinguibles en el historial y entre pestañas abiertas, y
 *  justo son por las que se pasa al empezar (2026-08-31). */
const FUERA_DEL_MENU: Record<string, { label: string; clave: string }> = {
  "/welcome": { label: "Conectar tu club", clave: "conectar" },
  "/setup": { label: "Configuración de tu club", clave: "configuracion" },
  "/connected": { label: "Club conectado", clave: "conectado" },
};

export function tituloDeRuta(pathname: string): string {
  const detalle = RUTAS_CON_DETALLE.find((r) => pathname.startsWith(r.prefijo));
  if (detalle) return `${nombreNav(detalle.label, detalle.clave)} · HT Lens`;

  const entrada = FUERA_DEL_MENU[pathname];
  if (entrada) return `${nombreNav(entrada.label, entrada.clave)} · HT Lens`;

  // La coincidencia más larga gana: `/transfers/balance` antes que nada que
  // empiece por `/transfers`.
  const enlaces = [...NAV, USO].filter(
    (item): item is { to: string; label: string; clave: string } =>
      "to" in item,
  );
  let mejor: { to: string; label: string; clave: string } | undefined;
  for (const item of enlaces) {
    if (pathname === item.to || pathname.startsWith(`${item.to}/`)) {
      if (!mejor || item.to.length > mejor.to.length) mejor = item;
    }
  }
  return mejor ? `${nombreNav(mejor.label, mejor.clave)} · HT Lens` : "HT Lens";
}

type Enlace = { to: string; label: string; clave?: string };
type Grupo = { titulo: string; clave?: string; enlaces: Enlace[] };

/** Convierte la lista plana de `NAV` --rótulos y enlaces mezclados como
 *  hermanos-- en los grupos que ya se veían pintados.
 *
 *  Se agrupa aquí y no en `NAV` para que la lista siga siendo cómoda de
 *  editar: se añade un enlace debajo de su rótulo y ya. */
export function agrupar(
  items: readonly ({ section: string; clave?: string } | Enlace)[],
): Grupo[] {
  const grupos: Grupo[] = [];
  for (const item of items) {
    if ("section" in item) {
      grupos.push({ titulo: item.section, clave: item.clave, enlaces: [] });
      continue;
    }
    const actual = grupos[grupos.length - 1];
    if (actual) actual.enlaces.push(item);
    // Un enlace antes del primer rótulo se quedaría sin grupo; hoy no pasa
    // --NAV empieza por «Club»-- y si pasara, se vería al instante.
  }
  return grupos.filter((g) => g.enlaces.length > 0);
}
