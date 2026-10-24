/** Los destellos del mapa en vivo: qué país está encendido ahora mismo.
 *
 *  POR QUÉ ES UN ALMACÉN DE FUERA Y NO `useState`. Esto no es estado que se
 *  derive de lo que se pinta: es un flujo de sucesos con reloj propio --llega
 *  un clic, se enciende un país, y un segundo después se apaga él solo--. Con
 *  `useState` el encendido tenía que dispararse DENTRO del efecto que mira si
 *  llegaron clics nuevos, y eso es `setState` síncrono en un efecto: cascada
 *  de renders, y el linter lo rechaza con razón.
 *
 *  Puesto fuera, el efecto sólo empuja el suceso --`encender`-- y quien pinta
 *  se suscribe con `useSyncExternalStore`, que es justo el caso que esa API
 *  existe para cubrir. Es el mismo patrón que `config/consentimiento.ts`.
 *
 *  Y DE PASO SE PUEDE PROBAR. La parte con filo de todo esto --que dos clics
 *  casi juntos del mismo país no se apaguen antes de tiempo-- no se ve en una
 *  captura de pantalla, y aquí se comprueba con un reloj falso.
 */

export interface Destello {
  code: string;
  /** Cuándo pasó el clic, en ISO, tal como lo manda el registro. */
  cuando: string;
}

export interface EstadoDeDestellos {
  /** Cuántos destellos tiene encendidos cada país AHORA.
   *
   *  Una CUENTA y no un `true`: dos clics casi juntos del mismo país se
   *  solapan, y con un booleano el primero en cumplir su segundo apagaría
   *  también al segundo, que acababa de empezar. El país se apaga cuando se
   *  apaga el último.
   */
  encendidos: Record<string, number>;
  /** Cuántos destellos van desde que se encendió el mapa. */
  vistos: number;
  /** El último, para la fila de estado: un mapa en negro tiene que poder
   *  distinguirse de un mapa roto. */
  ultimo: Destello | null;
}

const VACIO: EstadoDeDestellos = { encendidos: {}, vistos: 0, ultimo: null };

export interface AlmacenDeDestellos {
  subscribe: (oyente: () => void) => () => void;
  /** Tiene que devolver LA MISMA referencia mientras nada cambie, o
   *  `useSyncExternalStore` entra en un bucle de renders. */
  getSnapshot: () => EstadoDeDestellos;
  encender: (code: string, cuando: string) => void;
  /** Apaga todo, suelta los relojes y pone la cuenta a cero. */
  apagarTodo: () => void;
  /** Sólo suelta los relojes, sin avisar a nadie. Es lo que hay que llamar al
   *  desmontar: un `setTimeout` pendiente que toca el almacén de un componente
   *  que ya no está es la fuga clásica de este patrón. */
  soltarRelojes: () => void;
}

export function creaDestellos(duracionMs: number): AlmacenDeDestellos {
  let estado: EstadoDeDestellos = VACIO;
  const oyentes = new Set<() => void>();
  const relojes = new Set<ReturnType<typeof setTimeout>>();

  const cambia = (nuevo: EstadoDeDestellos) => {
    estado = nuevo;
    for (const avisar of [...oyentes]) avisar();
  };

  const soltarRelojes = () => {
    for (const reloj of relojes) clearTimeout(reloj);
    relojes.clear();
  };

  return {
    subscribe(oyente) {
      oyentes.add(oyente);
      return () => {
        oyentes.delete(oyente);
      };
    },

    getSnapshot: () => estado,

    encender(code, cuando) {
      cambia({
        encendidos: {
          ...estado.encendidos,
          [code]: (estado.encendidos[code] ?? 0) + 1,
        },
        vistos: estado.vistos + 1,
        ultimo: { code, cuando },
      });

      const reloj = setTimeout(() => {
        relojes.delete(reloj);
        const quedan = (estado.encendidos[code] ?? 0) - 1;
        const encendidos = { ...estado.encendidos };
        if (quedan <= 0) delete encendidos[code];
        else encendidos[code] = quedan;
        cambia({ ...estado, encendidos });
      }, duracionMs);
      relojes.add(reloj);
    },

    apagarTodo() {
      soltarRelojes();
      cambia(VACIO);
    },

    soltarRelojes,
  };
}
