import { Link } from "react-router-dom";

/**
 * «¿De dónde sale este número?», resuelto en un clic.
 *
 * 2026-09-01, pedido del usuario: en cada pantalla que calcule algo debe haber
 * un enlace discreto al cálculo que lo explica en Transparencia.
 *
 * La pantalla ya existía y ya sabía recibir enlaces --su selección vive en la
 * URL justamente para esto-- pero no había ni uno solo en toda la aplicación:
 * para leer cómo se calcula el puntaje de un canterano había que salir de
 * Juveniles, abrir Transparencia, encontrar la sección y luego el cálculo.
 * Tres pasos y saber de antemano que la explicación existe.
 *
 * DISCRETO es parte del encargo, no un adorno. Estos enlaces se repiten por
 * toda la aplicación y compiten con el dato que acompañan: si pesaran como un
 * botón, cada panel tendría una llamada a la acción que nadie pidió. De ahí el
 * tamaño pequeño, el color apagado y el subrayado punteado --que lo distingue
 * de un enlace de navegación normal-- y el color sólo al pasar por encima.
 *
 * El texto por omisión es «cómo se calcula» porque es la pregunta, no el
 * destino: «Transparencia» sería el nombre de una pantalla que quien lee
 * todavía no sabe que le sirve. El nombre del sitio al que va sí viaja en el
 * `title` y en el nombre accesible, que es donde no estorba.
 */
export function EnlaceATransparencia({
  seccion,
  calculo,
  children = "cómo se calcula",
  className = "",
}: {
  /** `id` de la sección en el catálogo de Transparencia. */
  seccion: string;
  /** `id` del cálculo dentro de esa sección. */
  calculo: string;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <Link
      to={`/transparency?s=${seccion}&c=${calculo}`}
      // La etiqueta que se registra dice DE DÓNDE se salió, no a dónde se va:
      // el destino es siempre el mismo y saberlo no enseña nada; lo que hay
      // que poder contar es qué cálculos generan la pregunta.
      data-track={`Transparencia desde ${seccion}/${calculo}`}
      title="Ver en Transparencia cómo se calcula"
      className={`whitespace-nowrap text-xs font-normal text-[var(--muted)] underline decoration-dotted underline-offset-2 hover:text-[var(--accent)] ${className}`}
    >
      {children}
    </Link>
  );
}
