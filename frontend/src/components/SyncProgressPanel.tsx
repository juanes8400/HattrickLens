import { useEffect, useRef } from "react";

/**
 * 2026-08-05, pedido explícitamente: "mira cómo lo hace Hattrick Control" —
 * su ventana "Conexión" muestra en vivo qué fichero/jugador/partido está
 * bajando. Esta es la versión HT Lens: una caja con scroll automático,
 * alimentada por `api.syncStream` línea a línea.
 */
export function SyncProgressPanel({ lines }: { lines: string[] }) {
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    boxRef.current?.scrollTo({ top: boxRef.current.scrollHeight });
  }, [lines]);

  return (
    <div className="border-b border-[var(--border)] bg-[var(--surface)] px-6 py-3">
      <div className="mb-2 text-xs font-medium text-[var(--muted)]">
        Sincronizando con Hattrick…
      </div>
      <div
        ref={boxRef}
        className="max-h-40 overflow-y-auto rounded-md border border-[var(--border)] bg-[var(--bg)] p-2 font-mono text-xs leading-relaxed text-[var(--muted)]"
      >
        {lines.length === 0 ? (
          <div>Conectando…</div>
        ) : (
          lines.map((line, index) => <div key={index}>{line}</div>)
        )}
      </div>
    </div>
  );
}
