import { useEffect, useRef } from "react";

/** Lo que se puede enfocar dentro de un diálogo. */
const ENFOCABLES = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

/**
 * Las cuatro cosas que hacen que un modal se pueda usar sin ratón.
 *
 * El único diálogo de la aplicación no tenía ninguna (2026-08-31): se cerraba
 * pinchando fuera y con teclado no había salida, tabulando se salía hacia la
 * tabla de detrás --tapada por el velo, pero enfocable-- y al cerrarse el
 * foco se perdía y volvía al principio del documento.
 *
 * Va en un hook y no suelto dentro del diálogo porque lo que hay que arreglar
 * no es ese modal: es que el siguiente nazca ya correcto.
 *
 *   1. Escape cierra.
 *   2. El foco entra al abrirse.
 *   3. Tab da la vuelta dentro y no se escapa.
 *   4. Al cerrarse, el foco vuelve a donde estaba.
 *
 * Falta `aria-modal="true"` en el elemento, que se pone en el JSX: sin él el
 * lector de pantalla sigue ofreciendo la página de detrás como disponible.
 */
export function useDialogoModal<T extends HTMLElement>(onCerrar: () => void) {
  const ref = useRef<T>(null);

  useEffect(() => {
    const caja = ref.current;
    if (!caja) return;

    // Quién tenía el foco antes de abrir, para devolvérselo al cerrar.
    const previo = document.activeElement as HTMLElement | null;

    const dentro = () =>
      Array.from(caja.querySelectorAll<HTMLElement>(ENFOCABLES));

    // El foco entra al primer control; si no hay ninguno, al propio diálogo,
    // que para eso lleva tabIndex -1.
    const primeros = dentro();
    (primeros[0] ?? caja).focus();

    const alTeclear = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onCerrar();
        return;
      }
      if (e.key !== "Tab") return;

      const focos = dentro();
      if (focos.length === 0) {
        e.preventDefault();
        return;
      }
      const primero = focos[0]!;
      const ultimo = focos[focos.length - 1]!;
      const actual = document.activeElement;

      // Dar la vuelta en los dos extremos. Sin esto, un Tab en el último
      // control se va a la página de detrás y no hay forma evidente de volver.
      if (!e.shiftKey && actual === ultimo) {
        e.preventDefault();
        primero.focus();
      } else if (e.shiftKey && (actual === primero || actual === caja)) {
        e.preventDefault();
        ultimo.focus();
      }
    };

    document.addEventListener("keydown", alTeclear, true);
    return () => {
      document.removeEventListener("keydown", alTeclear, true);
      // `isConnected`: si el elemento que tenía el foco desapareció con el
      // diálogo, devolvérselo no haría nada y el foco caería al `body`.
      if (previo?.isConnected) previo.focus();
    };
  }, [onCerrar]);

  return ref;
}
