/** Constantes que Vite sustituye al compilar (ver `define` en vite.config.ts).
 *
 *  Se declaran aquí porque no existen en tiempo de escritura: son un reemplazo
 *  de texto que hace el empaquetador, así que TypeScript necesita que alguien
 *  le diga de qué tipo son.
 */
declare const __VERSION__: string;
/** Commit corto del build, o cadena vacía si se compiló sin historial de git. */
declare const __COMMIT__: string;
