/** Cómo se llama una habilidad, en el idioma de quien mira.
 *
 *  POR QUÉ EXISTE ESTE FICHERO (2026-11-07). Había TRES mapas de nombres de
 *  habilidad, uno por pantalla: `EN_ESPANOL` en el comparador de precios,
 *  `HABILIDAD` en Transparencia y `SKILL_NAMES` en la Academia. Los tres decían
 *  casi lo mismo, y «casi» era el problema: la Academia llamaba «Portero» a la
 *  habilidad de portería. «Portero» es el PUESTO; la habilidad es «Portería»,
 *  y así la llama Hattrick. Tres copias son tres oportunidades de que una se
 *  desvíe, y una se había desviado.
 *
 *  Y DOS DE LAS TRES ESTABAN EN ESPAÑOL A MANO, lo que significa que un manager
 *  alemán leía «Jugadas» en Transparencia y en la Academia mientras el resto de
 *  la aplicación le decía «Spielaufbau». Desde aquí el nombre sale del GLOSARIO
 *  OFICIAL de Hattrick --el mismo `translations.xml` que usa el juego-- así que
 *  se lee exactamente la palabra que ve en su pantalla de Hattrick.
 *
 *  El respaldo en español sólo entra si el glosario no tuviera la clave, que
 *  hoy no pasa: las once están.
 */
import { terminoOficial } from "./glosario";

/** El respaldo, y nada más que el respaldo.
 *
 *  Son los mismos valores que el glosario oficial da en español, a propósito:
 *  si algún día el glosario perdiera una clave, la pantalla no cambiaría de
 *  palabra sin avisar. Están las once que Hattrick nombra, no sólo las seis que
 *  entran en el parecido de un comparable: quien pida `stamina` o `experience`
 *  también merece una palabra.
 */
export const HABILIDADES_EN_ESPANOL: Record<string, string> = {
  keeper: "Portería",
  stamina: "Resistencia",
  defending: "Defensa",
  playmaking: "Jugadas",
  winger: "Lateral",
  passing: "Pases",
  scoring: "Anotación",
  set_pieces: "Balón parado",
  experience: "Experiencia",
  leadership: "Liderazgo",
  form: "Forma",
};

/** `setpieces` y `set_pieces` son la misma habilidad.
 *
 *  El motor del mercado la guarda sin guion bajo --así la nombra
 *  `transfersearch`-- y el glosario oficial con él. Normalizar aquí evita que
 *  una pantalla acabe enseñando la clave cruda «setpieces» porque la pidió con
 *  la ortografía de la otra mitad de la aplicación.
 */
const ALIAS: Record<string, string> = {
  setpieces: "set_pieces",
  setPieces: "set_pieces",
};

/** El nombre oficial de una habilidad, o la clave si no se conoce.
 *
 *  Devolver la clave cruda es a propósito: una habilidad que no sabemos nombrar
 *  se ve fea y eso es una señal, mientras que inventarle un nombre bonito la
 *  esconde.
 */
export function nombreDeHabilidad(clave: string): string {
  const k = ALIAS[clave] ?? clave;
  return terminoOficial("habilidades", k, HABILIDADES_EN_ESPANOL[k] ?? clave);
}
