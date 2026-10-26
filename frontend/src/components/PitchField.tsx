import type { ReactNode } from "react";

import { usePersistido } from "../hooks/usePersistido";
import { tx } from "../i18n/tx";

/** Dónde se guarda la orientación. Una sola para toda la aplicación: quien la
 *  pone de una manera la quiere igual en Equipo, en Liga y en Alineación. */
const CLAVE_DE_ORIENTACION = "cancha.porteroArriba";

/**
 * Si la cancha se dibuja con el portero arriba. Persistido, como el resto de
 * formas de mirar.
 *
 * ESTO ES UN HOOK Y NO UN PROP a propósito: el que DIBUJA la cancha
 * (`PitchGrid`) y el que la ELIGE (`OrientacionDeLaCancha`) están en sitios
 * distintos de la pantalla --uno dentro del verde y otro fuera-- y pasarlo de
 * mano en mano obligaría a cada página a llevar un estado que no es suyo.
 */
export function useOrientacionDeLaCancha() {
  return usePersistido(CLAVE_DE_ORIENTACION, true);
}

/**
 * El selector de orientación: «portero arriba» o «portero abajo».
 *
 * FUERA DE LA CANCHA, y eso es lo único que lo hace servir (2026-10-26). Vivió
 * dos días dentro del verde, arriba a la derecha y en letra de once píxeles, y
 * el usuario preguntó tres veces dónde estaba. Un ajuste que no se encuentra es
 * un ajuste que no existe, por mucho que esté.
 *
 * Las DOS opciones siempre a la vista. Un botón que enseña el estado actual se
 * lee como etiqueta: no se ve que haya nada que elegir hasta que lo pulsas.
 */
export function OrientacionDeLaCancha({
  className = "",
}: {
  className?: string;
}) {
  const [porteroArriba, setPorteroArriba] = useOrientacionDeLaCancha();
  return (
    <div className={`flex flex-wrap items-center gap-2 ${className}`}>
      {/* CON ROTULO, y no sólo los dos botones. Sin él hay que deducir para
          qué sirven, y lo que se pidió fue poder ELEGIR cómo se mira la
          cancha: el rótulo es la mitad que dice que hay una elección. */}
      <span className="text-xs font-medium text-slate-600 dark:text-slate-300">
        {tx("Ver la cancha")}
      </span>
      <div
        role="group"
        aria-label={tx("Cómo se mira la cancha")}
        title={tx("Cambia si el portero sale arriba o abajo")}
        className="inline-flex gap-0.5 rounded-md bg-slate-200/70 p-0.5 dark:bg-slate-700/60"
      >
        {([true, false] as const).map((arriba) => (
          <button
            key={String(arriba)}
            onClick={() => setPorteroArriba(arriba)}
            aria-pressed={porteroArriba === arriba}
            data-track="Cancha: dar la vuelta"
            className={
              porteroArriba === arriba
                ? "rounded bg-white px-3 py-1 text-xs font-semibold text-slate-900 shadow-sm dark:bg-slate-900 dark:text-slate-100"
                : "rounded px-3 py-1 text-xs text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white"
            }
          >
            {arriba
              ? `↑ ${tx("Portero arriba")}`
              : `↓ ${tx("Portero abajo")}`}
          </button>
        ))}
      </div>
    </div>
  );
}

/**
 * Fondo de cancha reutilizable, dimensiones tomadas literalmente de "Mejor
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
      {/* LAS LINEAS DE LA CANCHA NO RECIBEN CLICS (2026-10-25). Son `absolute`
          y los hijos no, asi que pintan ENCIMA aunque vayan antes en el
          marcado, y sin esto se comen lo que tapan: el borde cubria casi todo
          el selector de orientacion --por eso no se podia cambiar-- y el
          circulo central y la linea de medio campo caen sobre las fichas.
          Son adorno: no tienen nada que atender. */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-emerald-950 via-emerald-900 to-emerald-950" />
      <div className="pointer-events-none absolute inset-4 rounded-[1.5rem] border-2 border-white/25" />
      <div className="pointer-events-none absolute left-1/2 top-1/2 h-20 w-20 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white/20" />
      <div className="pointer-events-none absolute left-4 right-4 top-1/2 border-t-2 border-white/20" />
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
 *
 * EL PORTERO, ARRIBA O ABAJO (2026-10-25, reporte de un usuario): «In my HT
 * match screens, my keeper is at the top, Lens Lineup shows him at the bottom».
 *
 * POR DEFECTO ARRIBA, COMO EL JUEGO. Es un cambio para todo el mundo y se toma
 * a conciencia: quien mira las dos pantallas a la vez --que es lo que hace
 * cualquiera al preparar un partido-- las tiene espejadas, y el error de leer
 * la defensa como la delantera no avisa de que es un error.
 *
 * LA VUELTA VIVE AQUÍ Y NO EN LAS CUATRO PANTALLAS que dibujan canchas. Cada
 * una arma sus filas por su cuenta --`[delanteros, medio, defensa, portero]`--
 * y repetir la vuelta en todas sería garantizar que un día discrepen. Con el
 * interruptor dentro, el ajuste y lo que ajusta no se pueden separar.
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
  const [porteroArriba] = useOrientacionDeLaCancha();
  // Las filas llegan SIEMPRE con el portero al final --asi las arman las
  // cuatro pantallas-- y se dan la vuelta aqui. Copia y no `reverse()` a
  // secas: `reverse` muta el array que le pasaron, y ese array es de quien
  // lo paso.
  const filas = porteroArriba ? [...rows].reverse() : rows;
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
    <div className="cancha overflow-x-auto">
      <div className="mx-auto flex w-max flex-col gap-2 px-2 pb-4 pt-2 sm:gap-3 sm:px-4 sm:pb-6">
        {filas.map((fila, i) => {
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
 * pantalla, había que arrastrarla de lado para ver al extremo derecho, y el
 * verde terminaba antes que la formación. Ahora el ancho es una variable
 * (`--pitch-card`, en index.css) que vale 9rem cuando cabe y se encoge para
 * llenar exactamente el ancho disponible cuando no. La geometría no cambia:
 * siguen siendo cinco columnas y un extremo sigue cayendo sobre su lateral.
 */
export const PITCH_CARD_WIDTH = "w-[var(--pitch-card)]";
export const PITCH_CARD_CLASS =
  `${PITCH_CARD_WIDTH} shrink-0 rounded-lg border border-white/20 bg-black/40 p-1.5 ` +
  "text-center text-[length:var(--pitch-card-font)] shadow-xl backdrop-blur";
