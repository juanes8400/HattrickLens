/** Los botones de la pantalla Uso, uno por botón y no uno por idioma.
 *
 *  2026-11-15, revisión de QA. Cada clic guarda la etiqueta VISIBLE del botón,
 *  en el idioma que tenía quien lo pulsó (`services/telemetria.ts`), y el
 *  servidor traduce después las que reconoce. Así, «Jugadores» guardado en
 *  español y «Players» guardado en inglés salían como dos filas «Players»
 *  --con la misma clave de React, que era el aviso de la consola-- y el resto
 *  se quedaba en el idioma en que se pulsó.
 *
 *  Aquí cada etiqueta vuelve a su texto en español con los diccionarios de
 *  los cuatro idiomas, se suman los clics de las que son el mismo botón y se
 *  enseña cada uno en el idioma de la app. Lógica pura, sin React: se prueba
 *  sin montar la pantalla.
 */

/** Un diccionario de textos (`textos/xx.json`): español → traducción. */
export type Textos = Record<string, string>;

export interface Pulsado {
  label: string;
  clicks: number;
}

/** De cualquier traducción, su texto en español. */
export function inversoDe(diccionarios: Textos[]): Map<string, string> {
  const inverso = new Map<string, string>();
  for (const d of diccionarios) {
    for (const [espanol, traducido] of Object.entries(d)) {
      // El primero gana: si dos textos españoles se traducen igual, son el
      // mismo botón a efectos de contarlo.
      if (!inverso.has(traducido)) inverso.set(traducido, espanol);
    }
  }
  return inverso;
}

/**
 * Junta las etiquetas que son el mismo botón y las enseña en el idioma de la
 * app. `mostrar` recibe el texto en español (o la etiqueta tal cual, si no
 * está en ningún diccionario) y devuelve lo que se ve.
 */
export function fusionarPulsados(
  pulsados: Pulsado[],
  inverso: Map<string, string>,
  mostrar: (espanol: string) => string,
): Pulsado[] {
  const porBoton = new Map<string, number>();
  for (const p of pulsados) {
    const espanol = inverso.get(p.label) ?? p.label;
    porBoton.set(espanol, (porBoton.get(espanol) ?? 0) + p.clicks);
  }
  // Dos textos españoles distintos pueden enseñarse igual en este idioma: se
  // suman también, para que la lista no repita una fila.
  const porVisible = new Map<string, number>();
  for (const [espanol, clicks] of porBoton) {
    const visible = mostrar(espanol);
    porVisible.set(visible, (porVisible.get(visible) ?? 0) + clicks);
  }
  return [...porVisible]
    .map(([label, clicks]) => ({ label, clicks }))
    .sort((a, b) => b.clicks - a.clicks);
}
