import i18n from "./index";

/**
 * Traducción por el propio texto (2026-09-15).
 *
 * Las primeras pantallas se tradujeron con claves con nombre
 * (`t("dashboard.caja", "Caja")`). Para el resto, miles de textos, la clave
 * es el texto en español tal cual: `tx("Caja")`. Lo pone
 * `scripts/extraer-textos.mjs` y el inglés vive en `textos/en.json`, un
 * diccionario español → inglés.
 *
 * Lo que protege lo ya montado es lo mismo: si falta la traducción, se
 * enseña el español, nunca un hueco. Los valores van con `{{v0}}`, `{{v1}}`…
 */
type Valor = string | number | boolean | null | undefined;

export function tx(texto: string, valores?: Record<string, Valor>): string {
  const opciones: Record<string, unknown> = {
    ns: "textos",
    defaultValue: texto,
    // El texto lleva puntos y dos puntos: no son separadores de clave.
    keySeparator: false,
    nsSeparator: false,
    ...valores,
  };
  return i18n.t(texto, opciones) as string;
}
