import clsx from "clsx";

/**
 * El «?» que explica un control o un gráfico sin ocupar sitio en la pantalla.
 *
 * 2026-09-13, pedido del usuario para Transferencias: «llena de esos íconos que
 * son un círculo con un "?" adentro, que sacan un tooltip, todos los botones y
 * gráficos». Se abre al pasar el ratón y también con el teclado (foco), porque
 * un `title` nativo no llega a quien no usa ratón ni a un móvil.
 */
export function Ayuda({
  texto,
  enLaFila = false,
}: {
  texto: string;
  /** La explicación arranca donde empieza la fila, no centrada sobre el «?».
   *  Para un «?» pegado a una etiqueta corta a la izquierda, donde centrada
   *  se salía de la pantalla del móvil (2026-11-23). La fila tiene que llevar
   *  `relative`. */
  enLaFila?: boolean;
}) {
  return (
    <span
      className={clsx(
        "group inline-flex align-middle",
        !enLaFila && "relative",
      )}
    >
      <button
        type="button"
        aria-label={texto}
        className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-[var(--border)] text-[10px] font-semibold leading-none text-[var(--muted)] hover:border-[var(--accent)] hover:text-[var(--accent)] focus-visible:border-[var(--accent)] focus-visible:text-[var(--accent)] focus-visible:outline-none"
      >
        ?
      </button>
      <span
        role="tooltip"
        className={clsx(
          "pointer-events-none absolute top-full z-30 mt-1.5 hidden w-64 rounded-md border border-[var(--border)] bg-[var(--surface)] p-2.5 text-left text-xs font-normal normal-case leading-relaxed tracking-normal text-[var(--text)] shadow-lg whitespace-pre-line group-focus-within:block group-hover:block",
          enLaFila ? "left-0" : "left-1/2 -translate-x-1/2",
        )}
      >
        {texto}
      </span>
    </span>
  );
}
