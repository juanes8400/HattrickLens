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

/** De cualquier traducción, su texto en español.
 *
 *  Un objeto plano y no un `Map`: viaja por la caché de consultas, que se
 *  guarda como JSON. Con un `Map`, al recargar volvía como `{}` sin `.get` y
 *  la pantalla Uso entera se caía (visto al verificar este mismo arreglo). */
export function inversoDe(diccionarios: Textos[]): Textos {
  const inverso: Textos = {};
  for (const d of diccionarios) {
    for (const [espanol, traducido] of Object.entries(d)) {
      // El primero gana: si dos textos españoles se traducen igual, son el
      // mismo botón a efectos de contarlo.
      if (!Object.hasOwn(inverso, traducido)) inverso[traducido] = espanol;
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
  inverso: Textos,
  mostrar: (espanol: string) => string,
): Pulsado[] {
  // «Lo más pulsado» las guarda compuestas, «Pantalla · botón»: cada parte
  // vuelve a su español y se enseña por separado.
  const SEP = " · ";
  const aEspanol = (label: string) =>
    label
      .split(SEP)
      .map((parte) => (Object.hasOwn(inverso, parte) ? inverso[parte]! : parte))
      .join(SEP);
  const enPantalla = (espanol: string) =>
    espanol.split(SEP).map(mostrar).join(SEP);
  const porBoton = new Map<string, number>();
  for (const p of pulsados) {
    const espanol = aEspanol(p.label);
    porBoton.set(espanol, (porBoton.get(espanol) ?? 0) + p.clicks);
  }
  // Dos textos españoles distintos pueden enseñarse igual en este idioma: se
  // suman también, para que la lista no repita una fila.
  const porVisible = new Map<string, number>();
  for (const [espanol, clicks] of porBoton) {
    const visible = enPantalla(espanol);
    porVisible.set(visible, (porVisible.get(visible) ?? 0) + clicks);
  }
  return [...porVisible]
    .map(([label, clicks]) => ({ label, clicks }))
    .sort((a, b) => b.clicks - a.clicks);
}
