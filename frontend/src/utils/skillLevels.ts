import i18n from "../i18n";

/** Nivel más alto con palabra propia en Hattrick («divino»). */
const NIVEL_MAXIMO = 20;

/** La palabra oficial de Hattrick para un nivel, en el idioma de la app.
 *
 *  2026-09-15: antes eran 21 palabras escritas a mano en español; ahora
 *  salen del glosario oficial (`translations.xml`), que en español dice
 *  exactamente lo mismo. Por encima de 20 se sigue escribiendo «divino+N». */
export function skillLevelLabel(level: number, capitalize = false): string {
  const label =
    Number.isInteger(level) && level >= 0 && level <= NIVEL_MAXIMO
      ? i18n.t(`niveles.${level}`, { ns: "glosario" })
      : `${i18n.t(`niveles.${NIVEL_MAXIMO}`, { ns: "glosario" })}+${level - NIVEL_MAXIMO}`;
  return capitalize ? label.charAt(0).toUpperCase() + label.slice(1) : label;
}

/** La escala de una habilidad juvenil, para medir la barra. */
export const YOUTH_SKILL_SCALE = 8;

/** Cómo se lee UNA habilidad: la palabra, los números y la barra.
 *
 * Vive aquí porque se pinta en cuatro sitios --la tabla de plantilla, la cola
 * de «a quién entrenar», los techos y las tarjetas de la cancha-- y cuando
 * cada uno llevaba su copia, los cuatro no decían lo mismo en los casos
 * raros. La regla es una sola:
 *
 *   - la barra mide el NIVEL sobre la escala, nunca lo lleno que está
 *     respecto a su propio techo: un 4 que ya no sube es un 4;
 *   - el color dice si puede crecer, no la longitud;
 *   - saber que una habilidad tocó techo NO es saber en qué número se paró.
 *     CHPP publica `IsMaxReached` aunque el nivel siga oculto, y entonces lo
 *     honesto es el candado y «desconocido», no un cero.
 */
export function lecturaDeNivel(
  current: number | null,
  maximum: number | null,
  maxReached: boolean,
): { palabra: string; numeros: string; ancho: number; crece: boolean } {
  const sabeAlgo = current != null || maximum != null;
  if (!sabeAlgo) {
    return {
      palabra: i18n.t("juveniles.desconocidoMin", "desconocido"),
      numeros: maxReached ? "" : "",
      ancho: 0,
      crece: !maxReached,
    };
  }
  const nivel = current ?? maximum ?? 0;
  // Con el techo sin revelar, el nivel de hoy es un SUELO: un techo no puede
  // estar por debajo de donde el chico ya juega, así que un «6/?» es en
  // realidad «6/≥6». Se dice porque es lo que hace que ese canterano cuente
  // como aceptable en la selección de entrenamiento, y con el interrogante
  // esa promoción parecía salir de la nada (2026-09-19, pedido del usuario).
  const numeros = maxReached
    ? `${current ?? maximum}/${maximum ?? current}`
    : maximum == null && current != null
      ? `${current}/≥${current}`
      : `${current ?? "?"}/${maximum ?? "?"}`;
  return {
    palabra: skillLevelLabel(nivel),
    numeros,
    ancho: Math.min(100, Math.max(0, (nivel / YOUTH_SKILL_SCALE) * 100)),
    crece: !maxReached,
  };
}
