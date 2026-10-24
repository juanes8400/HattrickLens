/** La aritmética del mapa de uso: qué tono le toca a cada país, y qué dice la
 *  leyenda.
 *
 *  Vive fuera del componente desde el 2026-10-23 para poder probarla sin
 *  montar un mapa del mundo. No es una separación por gusto: aquí está el
 *  único trozo del panel donde se puede mentir sin que se note --un color que
 *  no corresponde al número, o una leyenda que no corresponde al color-- y es
 *  justo lo que una prueba de render no comprueba.
 */

export interface UsoPorPais {
  code: string;
  name: string;
  users: number;
  sessions: number;
  pages: number;
  clicks: number;
  minutes: number;
}

/** Qué colorea el mapa. PERSONAS por defecto, desde el 2026-10-23.
 *
 *  Las dos lecturas contestan preguntas distintas y ninguna sobra: «personas»
 *  dice a cuántos países llegó esto, y «clics» cuáles trabajan dentro. Lo que
 *  no se puede es pintarlas a la vez.
 */
export type Magnitud = "users" | "clicks";

export const valorDe = (p: UsoPorPais, cual: Magnitud): number =>
  cual === "users" ? p.users : p.clicks;

/** Los cinco tonos del mapa: UN solo color, de claro a oscuro.
 *
 *  Una escala de magnitud no se pinta con colores distintos --eso dice
 *  «categorías», no «más y menos»--, así que son cinco mezclas del acento de
 *  la aplicación sobre el fondo. Se escriben con `color-mix` para que el tema
 *  oscuro salga solo: el acento y el fondo ya cambian con él.
 */
export const TONOS = [20, 38, 56, 74, 92] as const;

export const tono = (paso: number) =>
  `color-mix(in srgb, var(--accent) ${TONOS[paso]}%, var(--surface-2))`;

/** En qué tono cae un valor.
 *
 *  Sobre la RAÍZ del valor, no sobre el valor. El reparto está siempre muy
 *  torcido --el país del autor multiplica por diez al segundo-- y en escala
 *  lineal todo lo demás cae en el primer tono y el mapa queda en blanco y
 *  negro, que es no decir nada.
 */
export function pasoDeColor(valor: number, maximo: number): number {
  if (maximo <= 0 || valor <= 0) return 0;
  const parte = Math.sqrt(valor) / Math.sqrt(maximo);
  return Math.min(TONOS.length - 1, Math.floor(parte * TONOS.length));
}

/** La leyenda, construida DESDE LOS DATOS: un renglón por tono que de verdad
 *  sale en el mapa, rotulado con el valor más bajo que cae en él.
 *
 *  Antes se invertía la fórmula del color para sacar el corte de cada tono, y
 *  eso se rompía en cuanto el máximo era pequeño --que es justo lo que pasa al
 *  colorear por PERSONAS--. Con cinco países y cinco tonos salían dos
 *  etiquetas «1+» iguales y dos tonos que no aparecían en ningún sitio: una
 *  leyenda que explica colores que no están y no distingue los que sí.
 *
 *  Leyéndola de los datos no hay forma de que discrepe del dibujo.
 */
export function leyendaDe(
  paises: UsoPorPais[],
  cual: Magnitud,
  maximo: number,
): [paso: number, desde: number][] {
  const minimoDel = new Map<number, number>();
  for (const p of paises) {
    const v = valorDe(p, cual);
    const paso = pasoDeColor(v, maximo);
    const ya = minimoDel.get(paso);
    if (ya === undefined || v < ya) minimoDel.set(paso, v);
  }
  return [...minimoDel.entries()].sort((a, b) => a[0] - b[0]);
}
