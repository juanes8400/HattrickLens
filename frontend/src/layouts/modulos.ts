import i18n from "../i18n";

/** Los módulos del menú que juntan varias pantallas (8.0.0 y 8.1.0,
 *  2026-11-26): su nombre, y el de cada pestaña con su dirección.
 *
 *  Vive aparte, como `NAV`, porque lo leen dos sitios: la barra del módulo y
 *  la Wiki, que rotula cada sección con la pestaña que documenta. Una sola
 *  lista hace que no puedan llamarla de dos formas.
 *
 *  Cada pestaña se traduce en `modulos.<módulo>.<pestaña>`; el texto de aquí
 *  es el español y el valor por defecto. Con clave propia, y no con `tx()`,
 *  porque «Clasificación» a secas ya está traducida como la tabla de una liga
 *  («Table»), y aquí es la de los jugadores. */
export const MODULOS = {
  // Quién es cada uno, en qué grupo cae y cómo cambia la plantilla.
  jugadores: {
    nombre: "Jugadores",
    clave: "jugadores",
    pestanas: [
      { key: "tabla", to: "/team", texto: "Tabla" },
      { key: "clasificacion", to: "/team/classes", texto: "Clasificación" },
      { key: "salario", to: "/team/salary", texto: "Salario por grupo" },
      { key: "evolucion", to: "/team/evolution", texto: "Evolución" },
    ],
  },
  // Dónde rinde cada uno en la cancha y dónde falta gente.
  puestos: {
    nombre: "Puestos",
    clave: "puestos",
    pestanas: [
      // Posiciones primero y en la raíz, para que la entrada del menú abra
      // en ella (8.2.0, 2026-11-26, pedido del usuario).
      { key: "posiciones", to: "/skills", texto: "Posiciones" },
      { key: "profundidad", to: "/skills/depth", texto: "Profundidad" },
      { key: "cuello", to: "/skills/bottleneck", texto: "Cuello de botella" },
      { key: "mejor", to: "/skills/best", texto: "Mejor posición" },
    ],
  },
} as const;

export type Modulo = keyof typeof MODULOS;
export type PestanaDe<M extends Modulo> =
  (typeof MODULOS)[M]["pestanas"][number]["key"];

/** El nombre de una pestaña en el idioma de la app. */
export function nombreDePestana(modulo: string, key: string): string {
  const lista: readonly { key: string; texto: string }[] =
    MODULOS[modulo as Modulo]?.pestanas ?? [];
  const pestana = lista.find((p) => p.key === key);
  return i18n.t(`modulos.${modulo}.${key}`, pestana?.texto ?? key);
}

/** El nombre de un módulo en el idioma de la app, el mismo del menú; `null`
 *  si `id` no es un módulo.
 *
 *  La Wiki titula con esto su artículo de cada módulo, y no con `tx()`: en
 *  inglés, alemán, italiano y polaco «Puestos» se llamaba igual que su
 *  pestaña «Posiciones» (Positions, Positionen…), así que el módulo tiene
 *  nombre propio en el menú (Roles, Rollen…), mientras que «Puestos» en el
 *  glosario sigue siendo «Positions» (8.2.0, 2026-11-26, pedido del
 *  usuario). */
export function nombreDeModulo(id: string): string | null {
  const modulo = MODULOS[id as Modulo];
  return modulo ? i18n.t(`nav.${modulo.clave}`, modulo.nombre) : null;
}
