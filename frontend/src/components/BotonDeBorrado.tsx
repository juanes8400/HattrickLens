import { useEffect, useRef, useState } from "react";
import clsx from "clsx";

/**
 * Un borrado que no se consuma al primer clic.
 *
 * Los dos borrados irreversibles de la aplicación se ejecutaban en un clic,
 * sin confirmar y sin deshacer, con el botón pegado a otros de uso corriente
 * (2026-08-31). Sus propios tooltips lo decían: «como si nunca hubiera
 * llegado a la lista».
 *
 * Lo llamativo es que la casa ya tenía resuelto este problema en otra parte:
 * en Alertas, quitar algo es ARCHIVAR, y hay un «Restaurar» al lado. Existe
 * el patrón reversible; sólo que estas dos pantallas no lo usaban. Deshacer
 * de verdad aquí exige que el servidor sepa resucitar la fila, que hoy no
 * sabe; mientras tanto, confirmar en el sitio da la misma red sin inventarse
 * una API: hasta el segundo clic no se ha perdido nada.
 *
 * Se confirma EN EL PROPIO BOTÓN y no con un diálogo aparte porque la acción
 * es pequeña y local: sacar un modal para borrar una fila de una tabla cuesta
 * más atención de la que la decisión merece.
 */
export function BotonDeBorrado({
  onConfirmar,
  children,
  confirmacion = "¿Seguro?",
  title,
  disabled,
  className,
}: {
  onConfirmar: () => void;
  children: React.ReactNode;
  /** Lo que dice el botón cuando ya está esperando el segundo clic. */
  confirmacion?: string;
  title?: string;
  disabled?: boolean;
  className?: string;
}) {
  const [armado, setArmado] = useState(false);
  const temporizador = useRef<number | undefined>(undefined);

  // Se desarma solo: un botón que se queda «¿Seguro?» para siempre es una
  // trampa para el siguiente clic distraído.
  useEffect(() => {
    if (!armado) return;
    temporizador.current = window.setTimeout(() => setArmado(false), 4000);
    return () => window.clearTimeout(temporizador.current);
  }, [armado]);

  return (
    <button
      type="button"
      disabled={disabled}
      title={armado ? "Pulsa otra vez para borrar. Se desarma solo." : title}
      // El estado no puede vivir sólo en el texto y el color: se anuncia.
      aria-live="polite"
      onClick={() => {
        if (armado) {
          setArmado(false);
          onConfirmar();
        } else {
          setArmado(true);
        }
      }}
      onBlur={() => setArmado(false)}
      className={clsx(
        className,
        armado && "border-[var(--danger)] text-[var(--danger)]",
      )}
    >
      {armado ? confirmacion : children}
    </button>
  );
}
