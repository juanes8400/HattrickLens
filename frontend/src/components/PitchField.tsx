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
    <div
      className={`relative overflow-hidden ${className}`}
      aria-label={ariaLabel}
    >
      <div className="absolute inset-0 bg-gradient-to-b from-emerald-950 via-emerald-900 to-emerald-950" />
      <div className="absolute inset-4 rounded-[1.5rem] border-2 border-white/25" />
      <div className="absolute left-1/2 top-1/2 h-20 w-20 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white/20" />
      <div className="absolute left-4 right-4 top-1/2 border-t-2 border-white/20" />
      {children}
    </div>
  );
}

/**
 * Los máximos por puesto de una alineación de Hattrick. No es una decisión de
 * esta app: el juego no deja poner más, y de aquí sale la geometría de la
 * cancha. Con dos bandas y tres por el centro, ninguna fila pasa de cinco.
 */
export const PITCH_MAX = {
  keeper: 1,
  centralDefenders: 3,
  wingbacks: 2, // uno por banda
  innerMidfielders: 3,
  wingers: 2, // uno por banda
  forwards: 3,
} as const;

/** Columnas de la cancha: dos bandas más tres del centro. Fijas, iguales en
 *  todas las canchas de la app, para que un extremo caiga siempre sobre su
 *  lateral aunque la formación cambie. */
export const PITCH_COLUMNS = PITCH_MAX.wingbacks + PITCH_MAX.centralDefenders;

/**
 * Las filas de un once sobre una rejilla de columnas fijas.
 *
 * 2026-08-19, pedido explícito: un extremo tiene que caer en la misma vertical
 * que su lateral. Con filas centradas cada una por su cuenta eso no pasa
 * nunca: una fila de tres centrada sobre una de cinco deja a los extremos
 * encima de los defensas centrales, que es justo donde no juegan.
 *
 * `isFlank` marca a los jugadores de banda (laterales y extremos). Van a la
 * primera y la última columna; el resto se centra en la franja del medio. Una
 * fila sin gente de banda se centra sobre el ancho completo, así que dos
 * delanteros quedan simétricos respecto al eje del campo y no pegados a un
 * lado.
 */
export function PitchGrid<T>({
  rows,
  isFlank,
  render,
}: {
  rows: T[][];
  /** Si no se pasa, ninguna fila tiene bandas y todas se centran. Es el caso
   *  del once ideal de la liga, que llega agrupado por línea y sin lado. */
  isFlank?: (item: T) => boolean;
  render: (item: T) => ReactNode;
}) {
  const marca = isFlank ?? (() => false);
  const franja = (items: T[], desde: number, hasta: number, clave: string) => (
    <div
      key={clave}
      className="flex justify-center gap-2"
      style={{ gridColumn: `${desde} / ${hasta + 1}` }}
    >
      {items.map(render)}
    </div>
  );

  return (
    // Un solo contenedor con scroll para TODAS las filas: si cada una se
    // desplazara por su cuenta, al mover una se perdería la vertical.
    <div className="overflow-x-auto">
      <div className="mx-auto flex w-max flex-col gap-2 px-2 py-4 sm:gap-3 sm:px-4 sm:py-6">
        {rows.map((fila, i) => {
          if (fila.length === 0) return null;
          const bandas = fila.filter(marca);
          const centro = fila.filter((item) => !marca(item));
          const izquierda = bandas[0];
          // Solo dos bandas por fila, una por lado: si llegara una tercera
          // (dato inesperado), se queda con el grupo del centro en vez de
          // inventar una columna que no existe.
          const derecha =
            bandas.length > 1 ? bandas[bandas.length - 1] : undefined;
          const medio = [
            ...bandas.slice(1, Math.max(1, bandas.length - 1)),
            ...centro,
          ];
          return (
            <div
              key={i}
              className="grid gap-2"
              style={{
                gridTemplateColumns: `repeat(${PITCH_COLUMNS}, var(--pitch-card))`,
              }}
            >
              {bandas.length === 0
                ? franja(medio, 1, PITCH_COLUMNS, "todo")
                : [
                    <div key="izq" style={{ gridColumn: 1 }}>
                      {render(izquierda as T)}
                    </div>,
                    franja(medio, 2, PITCH_COLUMNS - 1, "medio"),
                    derecha ? (
                      <div key="der" style={{ gridColumn: PITCH_COLUMNS }}>
                        {render(derecha)}
                      </div>
                    ) : null,
                  ]}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Tarjeta de jugador con las mismas proporciones que "Mejor alineación":
 * vidrio esmerilado sobre el verde de la cancha.
 *
 * 2026-08-21, por reportes de usuarios: el ancho era 9rem fijo, así que las
 * cinco columnas medían 45rem y en un teléfono la cancha se salía de la
 * pantalla — había que arrastrarla de lado para ver al extremo derecho, y el
 * verde terminaba antes que la formación. Ahora el ancho es una variable
 * (`--pitch-card`, en index.css) que vale 9rem cuando cabe y se encoge para
 * llenar exactamente el ancho disponible cuando no. La geometría no cambia:
 * siguen siendo cinco columnas y un extremo sigue cayendo sobre su lateral.
 */
export const PITCH_CARD_WIDTH = "w-[var(--pitch-card)]";
export const PITCH_CARD_CLASS =
  `${PITCH_CARD_WIDTH} shrink-0 rounded-lg border border-white/20 bg-black/40 p-1.5 ` +
  "text-center text-[length:var(--pitch-card-font)] shadow-xl backdrop-blur";
