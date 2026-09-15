/**
 * Lo que encontró el barrido de comisiones, encima de Cambios.
 *
 * 2026-09-10, pedido del usuario: «debe haber un intermedio entre dejarme en
 * Sincronizar y mandarme para Cambios que me permita ver si se encontró
 * historia de jugadores. Algo como que me mande para Cambios, pero que salga
 * un pop-up que se cierra fácil».
 *
 * LAS DOS COSAS QUE ARREGLA. Quedarse en Sincronizar deja el hallazgo lejos
 * del sitio donde se mira el detalle; saltar sin más se lleva por delante el
 * informe que el barrido acababa de escribir. El aviso viaja con la
 * navegación, así que se salta Y se lee.
 *
 * «QUE SE CIERRA FÁCIL», literal: Escape, clic fuera, la X, el botón, y el
 * foco entra en el diálogo al abrirse para que Escape funcione sin tocar
 * nada. Un aviso que estorba se cierra solo una vez; uno que cuesta cerrar
 * enseña a la gente a no leerlo.
 */
import { useEffect, useRef } from "react";
import type { AvisoDelBarrido as Datos } from "../services/api";

import { tx } from "../i18n/tx";
const jugadores = (n: number) => `${n} jugador${n === 1 ? "" : "es"}`;

/** «1 comisión», «3 comisiones». La tilde SE CAE en el plural: pegarle «es»
 *  al singular daba «3 comisiónes», que es una falta de ortografía. */
const comisiones = (n: number) => `${n} ${n === 1 ? "comisión" : "comisiones"}`;

export function AvisoDelBarrido({
  datos,
  onClose,
}: {
  datos: Datos;
  onClose: () => void;
}) {
  const caja = useRef<HTMLDivElement>(null);

  useEffect(() => {
    caja.current?.focus();
    const alPulsar = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", alPulsar);
    return () => document.removeEventListener("keydown", alPulsar);
  }, [onClose]);

  const lineas: string[] = [];
  if (datos.commissions > 0) {
    lineas.push(
      `${comisiones(datos.commissions)} de club anterior o de origen`,
    );
  }
  if (datos.histories > 0) {
    lineas.push(
      `historial de partidos reconstruido a ${jugadores(datos.histories)}`,
    );
  }

  return (
    // El fondo cierra al hacer clic, pero sólo si el clic fue EN él: sin la
    // comprobación, arrastrar una selección desde dentro del diálogo hasta
    // fuera lo cerraba a mitad de leerlo.
    <div
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
    >
      <div
        ref={caja}
        role="dialog"
        aria-modal="true"
        aria-labelledby="aviso-barrido-titulo"
        tabIndex={-1}
        className="w-full max-w-md rounded-lg border border-[var(--border)] bg-[var(--surface)] shadow-xl outline-none"
      >
        <div className="flex items-start justify-between gap-3 border-b border-[var(--border)] px-4 py-3">
          <h2 id="aviso-barrido-titulo" className="text-sm font-semibold">
            {datos.stopped
              ? tx("Lo que alcanzó a encontrar")
              : tx("Esto encontró el barrido")}
          </h2>
          <button
            onClick={onClose}
            aria-label={tx("Cerrar")}
            className="-mr-1 -mt-1 rounded px-2 py-0.5 text-lg leading-none text-[var(--muted)] hover:text-[var(--text)]"
          >
            ×
          </button>
        </div>

        <div className="space-y-3 px-4 py-4">
          <ul className="space-y-1.5 text-sm">
            {lineas.map((linea) => (
              <li key={linea} className="flex gap-2">
                <span className="text-[var(--positive)]">✓</span>
                <span>{linea}</span>
              </li>
            ))}
          </ul>
          <p className="prosa text-xs leading-relaxed text-[var(--muted)]">
            {datos.commissions > 0
              ? tx(
                  "Las comisiones ya están en Transferencias y en el saldo de cada jugador.",
                )
              : tx(
                  "Reconstruir el historial no da dinero por sí solo: es lo que hace falta para poder calcular una comisión el día que a uno de ellos lo revendan.",
                )}{" "}
            {tx("Siguen vivos")} {jugadores(datos.open)}{" "}
            {tx("que pueden dar comisión algún día")}
            {datos.closedTotal > 0
              ? tx(", y {{v0}} quedaron zanjados en esta pasada", {
                  v0: jugadores(datos.closedTotal),
                })
              : ""}
            .
          </p>
          <button
            onClick={onClose}
            className="w-full rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white"
          >
            {tx("Ver los cambios")}
          </button>
        </div>
      </div>
    </div>
  );
}
