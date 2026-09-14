/**
 * El «?» que explica un control o un gráfico sin ocupar sitio en la pantalla.
 *
 * 2026-09-13, pedido del usuario para Transferencias: «llena de esos íconos que
 * son un círculo con un "?" adentro, que sacan un tooltip, todos los botones y
 * gráficos». Se abre al pasar el ratón y también con el teclado (foco), porque
 * un `title` nativo no llega a quien no usa ratón ni a un móvil.
 */
export function Ayuda({ texto }: { texto: string }) {
  return (
    <span className="group relative inline-flex align-middle">
      <button
        type="button"
        aria-label={texto}
        className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-[var(--border)] text-[10px] font-semibold leading-none text-[var(--muted)] hover:border-[var(--accent)] hover:text-[var(--accent)] focus-visible:border-[var(--accent)] focus-visible:text-[var(--accent)] focus-visible:outline-none"
      >
        ?
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute left-1/2 top-full z-30 mt-1.5 hidden w-64 -translate-x-1/2 rounded-md border border-[var(--border)] bg-[var(--surface)] p-2.5 text-left text-xs font-normal normal-case leading-relaxed tracking-normal text-[var(--text)] shadow-lg group-focus-within:block group-hover:block"
      >
        {texto}
      </span>
    </span>
  );
}
