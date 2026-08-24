const SKILL_LEVELS = [
  "nulo", "desastroso", "horrible", "pobre", "débil", "insuficiente",
  "aceptable", "bueno", "excelente", "formidable", "destacado", "brillante",
  "magnífico", "clase mundial", "sobrenatural", "titánico", "extraterrestre",
  "mítico", "mágico", "utópico", "divino",
];

export function skillLevelLabel(level: number, capitalize = false): string {
  const label = SKILL_LEVELS[level] ?? `divino+${level - 20}`;
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
      palabra: "desconocido",
      numeros: maxReached ? "" : "",
      ancho: 0,
      crece: !maxReached,
    };
  }
  const nivel = current ?? maximum ?? 0;
  const numeros = maxReached
    ? `${current ?? maximum}/${maximum ?? current}`
    : `${current ?? "?"}/${maximum ?? "?"}`;
  return {
    palabra: skillLevelLabel(nivel),
    numeros,
    ancho: Math.min(100, Math.max(0, (nivel / YOUTH_SKILL_SCALE) * 100)),
    crece: !maxReached,
  };
}
