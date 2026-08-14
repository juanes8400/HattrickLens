import type { ReactNode } from "react";

/**
 * Fondo de cancha reutilizable — dimensiones tomadas literalmente de "Mejor
 * alineación" (LeaguePage.tsx, Comparativa), pedido explícito 2026-08-14
 * para replicar la misma figura donde haga falta una cancha en la app en
 * vez de copiar el markup a mano en cada sitio.
 *
 * Círculo central: 5rem (80px) de diámetro, centrado.
 * Borde de cancha: separado 1rem de cada lado, esquinas 1.5rem, borde 2px
 * blanco al 25%.
 * Línea de medio campo: borde superior 2px blanco al 20%, separada 1rem de
 * los lados.
 *
 * No fija alto/ancho: el contenido (`children`) decide el tamaño, igual que
 * en el panel original. `children` va DIRECTO dentro del contenedor
 * posicionado (sin un `<div>` envoltorio intermedio): un envoltorio extra
 * rompe a cualquier consumidor que posicione sus tarjetas con `top/left` en
 * porcentaje, porque ese porcentaje se resuelve contra la altura del
 * contenedor MÁS CERCANO, y un envoltorio sin contenido de flujo normal
 * colapsa a alto 0.
 */
export function PitchField({
  children,
  ariaLabel,
  className = "",
}: {
  children: ReactNode;
  ariaLabel?: string;
  className?: string;
}) {
  return (
    <div className={`relative overflow-hidden ${className}`} aria-label={ariaLabel}>
      <div className="absolute inset-0 bg-gradient-to-b from-emerald-950 via-emerald-900 to-emerald-950" />
      <div className="absolute inset-4 rounded-[1.5rem] border-2 border-white/25" />
      <div className="absolute left-1/2 top-1/2 h-20 w-20 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white/20" />
      <div className="absolute left-4 right-4 top-1/2 border-t-2 border-white/20" />
      {children}
    </div>
  );
}

/** Tarjeta de jugador con las mismas proporciones que "Mejor alineación":
 * 9rem de ancho, vidrio esmerilado sobre el verde de la cancha. */
export const PITCH_CARD_WIDTH = "w-36";
export const PITCH_CARD_CLASS =
  `${PITCH_CARD_WIDTH} shrink-0 rounded-lg border border-white/20 bg-black/40 p-1.5 text-center shadow-xl backdrop-blur`;
