/** Interruptores de producto: qué se enseña y qué no.
 *
 *  Viven aparte de las pantallas a propósito. Apagar una función suele tocar
 *  dos o tres sitios --una pestaña aquí, el formulario que la alimenta allá--
 *  y con la bandera dentro de una de esas pantallas la otra tendría que
 *  importar una página entera para leer un booleano.
 */

/** «Intentos de transferencias», apagado a petición del usuario
 *  (2026-09-04): ni la pestaña de Transferencias ni el formulario de la
 *  pantalla de Cambios que la alimentaba.
 *
 *  Se apagan JUNTOS desde aquí: pedirle a alguien que teclee unas visitas que
 *  luego no puede consultar en ninguna parte sería peor que no pedírselas.
 *
 *  El código se queda entero --la tabla, el endpoint y lo que ya está
 *  guardado-- porque apagarlo es una decisión de producto y puede volver;
 *  borrarlo sería tirar el trabajo y los datos. Poner `true` lo devuelve.
 */
export const INTENTOS_DE_TRANSFERENCIA_VISIBLES = false;
