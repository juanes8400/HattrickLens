import i18n from "../i18n";

/** Las pestañas de los módulos que juntan varias pantallas (8.0.0,
 *  2026-11-26): su dirección y su nombre.
 *
 *  Vive aparte, como `NAV`, porque lo leen dos sitios: la barra del módulo y
 *  la Wiki, que rotula cada sección con la pestaña que documenta. Una sola
 *  lista hace que no puedan llamarla de dos formas.
 *
 *  Cada nombre se traduce en `modulos.<módulo>.<pestaña>`; el texto de aquí es
 *  el español y el valor por defecto. Con clave propia, y no con `tx()`,
 *  porque «Clasificación» a secas ya está traducida como la tabla de una liga
 *  («Table»), y aquí es la de los jugadores. */
export const PESTANAS = {
  jugadores: [
    { key: "tabla", to: "/team", texto: "Tabla" },
    { key: "clasificacion", to: "/team/classes", texto: "Clasificación" },
    { key: "salario", to: "/team/salary", texto: "Salario por grupo" },
    { key: "evolucion", to: "/team/evolution", texto: "Evolución" },
  ],
} as const;

export type Modulo = keyof typeof PESTANAS;
export type PestanaDe<M extends Modulo> = (typeof PESTANAS)[M][number]["key"];

/** El nombre de una pestaña en el idioma de la app. */
export function nombreDePestana(modulo: string, key: string): string {
  const lista: readonly { key: string; texto: string }[] =
    PESTANAS[modulo as Modulo] ?? [];
  const pestana = lista.find((p) => p.key === key);
  return i18n.t(`modulos.${modulo}.${key}`, pestana?.texto ?? key);
}
