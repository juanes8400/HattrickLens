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

/** Habilidades con «Mirar a»: una gráfica pequeña por dato, en rejilla, y una
 *  línea por cada cosa marcada en todas (2026-11-18, opción B del usuario).
 *
 *  Antes la forma dependía de cuántos grupos se marcaban: con uno, las
 *  gráficas de siempre con varias habilidades; con dos o más, una sola
 *  gráfica y el selector «Dato». Funcionaba, pero marcar una casilla más
 *  cambiaba la gráfica entera en vez de añadir una línea.
 *
 *  El usuario pidió estar listo para volver: `false` devuelve la forma
 *  anterior tal cual, cuyo código sigue entero. Sólo con la plantilla entera
 *  marcada no cambia nada: siguen las gráficas de siempre, con la línea de
 *  los 11 de más TSI. */
export const HABILIDADES_EN_REJILLA = true;
