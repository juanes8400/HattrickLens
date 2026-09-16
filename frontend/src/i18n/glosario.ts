import i18n from ".";

/**
 * El vocabulario del juego, por número de nivel (2026-09-15).
 *
 * Un diccionario de textos no puede con estas familias: «Encantados» es el 7
 * del Espíritu y también el 9 del Ánimo de la afición, y en inglés cada uno
 * se llama distinto. Lo único que los distingue es el número, así que aquí se
 * lee del glosario oficial (`translations.xml`) y no de la traducción.
 *
 * En español devuelve `null` a propósito: manda el texto que ya manda el
 * servidor, para no mover palabras que el usuario lleva viendo desde siempre.
 */
export type FamiliaDelGlosario =
  | "espiritu"
  | "confianza"
  | "aficion"
  | "patrocinadores"
  | "simpatia"
  | "agresividad"
  | "honradez"
  | "actitud"
  | "tacticas"
  | "entrenamientos"
  | "niveles"
  | "especialidades";

export function nivelOficial(
  familia: FamiliaDelGlosario,
  nivel: number | null | undefined,
): string | null {
  if (nivel == null || !Number.isFinite(nivel)) return null;
  if (i18n.language === "es") return null;
  const termino = i18n.t(`${familia}.${nivel}`, {
    ns: "glosario",
    defaultValue: "",
  });
  return termino || null;
}

/** La escala entera de una familia, con el nombre oficial en cada peldaño. */
export function escalaOficial<T extends { level: number; label: string }>(
  familia: FamiliaDelGlosario,
  escala: T[],
): T[] {
  return escala.map((p) => ({ ...p, label: nivelOficial(familia, p.level) ?? p.label }));
}

/** Un término del glosario por su clave, no por nivel: habilidades, sectores,
 *  puestos... El respaldo es el texto en español, que es lo que se ve si el
 *  glosario no trae esa clave. */
export function terminoOficial(
  familia: string,
  clave: string,
  respaldo: string,
): string {
  if (!clave || i18n.language === "es") return respaldo;
  return i18n.t(`${familia}.${clave}`, { ns: "glosario", defaultValue: respaldo });
}
