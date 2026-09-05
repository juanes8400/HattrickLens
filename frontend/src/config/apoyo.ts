/** El botón de apoyo voluntario: dónde lleva y si se enseña.
 *
 *  Vive aquí y no dentro de una pantalla porque lo leen DOS sitios --el menú
 *  lateral y la página de Autor-- y porque encenderlo es una decisión de
 *  producto que se toma en un solo interruptor, igual que
 *  `INTENTOS_DE_TRANSFERENCIA_VISIBLES`.
 */

/** La URL de cobro, del tipo `https://buymeacoffee.com/<usuario>`.
 *
 *  Se fue por Buy Me a Coffee y no por Stripe por un motivo que no es de
 *  gusto: Stripe no admite cuentas de Colombia (comprobado 2026-09-05), así
 *  que la integración mejor no servía de nada.
 *
 *  Es una URL PÚBLICA --está hecha para repartirla-- así que no es un secreto
 *  y no tiene que vivir en el entorno. Aquí no hay ninguna clave de cobro, ni
 *  hace falta: se enlaza, no se procesa.
 *
 *  Se enlaza en vez de incrustar el widget de Buy Me a Coffee a propósito: su
 *  widget es un script de terceros que se carga en cada pantalla, y no
 *  merece la pena cargar código ajeno --ni lo que pueda mirar-- para pintar
 *  un botón que sabemos pintar.
 *
 *  Vacía mientras no exista el enlace. Con la cadena vacía no se enseña nada
 *  aunque la bandera esté encendida: un botón de apoyo que lleva a ningún
 *  sitio es peor que no tener botón.
 */
export const ENLACE_DE_APOYO = "https://buymeacoffee.com/juanes8400";

/** Si se enseña. Encendido el 2026-09-05 por decisión del usuario.
 *
 *  Encender esto SIN `ENLACE_DE_APOYO` no hace nada, a propósito: apagar el
 *  botón es quitar el enlace o bajar esta bandera, cualquiera de las dos.
 */
export const APOYO_VISIBLE = true;

/** Si de verdad hay algo que enseñar. Las dos condiciones en un solo sitio
 *  para que las dos pantallas no puedan discrepar. */
export const hayApoyo = () => APOYO_VISIBLE && ENLACE_DE_APOYO.length > 0;
