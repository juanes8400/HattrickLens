import { useRef } from "react";
import type { ReactNode } from "react";
import clsx from "clsx";

/**
 * Control segmentado tipo píldora (referencia visual del usuario 2026-08-03:
 * "🏠 Inicio" / "</> Code") — patrón general para partir pantallas largas en
 * secciones, en vez de obligar a hacer scroll por todo para llegar a la
 * última parte.
 *
 * Con teclado se comporta como manda el patrón de pestañas, y hasta el
 * 2026-08-31 no lo hacía:
 *
 *   - **Una sola parada de tabulador**, la pestaña activa. Antes todas eran
 *     parada: en Transparencia había que pulsar el tabulador DOCE veces para
 *     pasar de las pestañas al contenido, y eso en cada visita.
 *   - **Las flechas mueven entre pestañas**, con vuelta al principio al
 *     llegar al final. Antes no hacían nada, y era la primera tecla que
 *     alguien prueba en un control segmentado.
 *   - `Inicio` y `Fin` saltan a la primera y a la última.
 */
export function Tabs<T extends string>({
  tabs,
  active,
  onChange,
  label,
}: {
  tabs: { key: T; label: string; icon?: ReactNode }[];
  active: T;
  onChange: (key: T) => void;
  /** Qué distingue a ESTE grupo cuando hay varios en la misma pantalla. */
  label?: string;
}) {
  const zona = useRef<HTMLDivElement>(null);

  const mover = (indice: number) => {
    const destino = tabs[indice];
    if (!destino) return;
    onChange(destino.key);
    // El foco viaja con la selección: si se queda atrás, la siguiente flecha
    // se mueve desde donde estaba el foco y no desde lo que se ve marcado.
    zona.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[indice]?.focus();
  };

  const alPulsar = (e: React.KeyboardEvent, actual: number) => {
    const ultimo = tabs.length - 1;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      e.preventDefault();
      mover(actual === ultimo ? 0 : actual + 1);
    } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      e.preventDefault();
      mover(actual === 0 ? ultimo : actual - 1);
    } else if (e.key === "Home") {
      e.preventDefault();
      mover(0);
    } else if (e.key === "End") {
      e.preventDefault();
      mover(ultimo);
    }
  };

  return (
    // El carril que se desplaza es ESTE, no la página. Con la barra de
    // píldoras suelta, en un móvil las siete secciones de Transparencia
    // sobresalían 327 px y arrastraban el documento entero: la cabecera y el
    // contenido se movían de lado al deslizar (2026-08-31).
    <div className="-mx-1 overflow-x-auto px-1">
      <div
        ref={zona}
        role="tablist"
        aria-label={label}
        className="inline-flex w-max gap-1 rounded-full border border-[var(--border)] bg-[var(--surface-2)] p-1"
      >
        {tabs.map((t, i) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={active === t.key}
          // Sólo la activa está en el orden de tabulación; entre ellas se
          // navega con las flechas. Es lo que espera quien usa teclado y lo
          // que evita convertir cada grupo de pestañas en un peaje.
            tabIndex={active === t.key ? 0 : -1}
            onClick={() => onChange(t.key)}
            onKeyDown={(e) => alPulsar(e, i)}
            className={clsx(
              "flex items-center gap-1.5 whitespace-nowrap rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors",
              active === t.key
                ? "bg-[var(--surface)] text-[var(--text)] shadow-sm"
                : "text-[var(--muted)] hover:text-[var(--text)]",
            )}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
      </div>
    </div>
  );
}
