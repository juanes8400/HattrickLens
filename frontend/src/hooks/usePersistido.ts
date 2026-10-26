import { useCallback, useSyncExternalStore } from "react";

/**
 * Un ajuste del usuario que sobrevive a la recarga.
 *
 * Nació dentro de la pantalla de Juveniles, para los parámetros con los que se
 * puntúa la cantera. El razonamiento de allí vale igual aquí:
 *
 *   Son la opinión del usuario sobre cómo mirar sus datos, no un estado de
 *   pantalla. Tenerlos que volver a poner cada vez convertía un ajuste
 *   deliberado en algo que se perdía al pestañear.
 *
 * Se saca a un módulo propio el 2026-09-05, al necesitarlo la pantalla de Uso:
 * una tercera copia del mismo `useState` + `useEffect` era garantizar que un
 * día diverjan.
 *
 * TODAS LAS VISTAS DEL MISMO AJUSTE VAN JUNTAS (2026-10-26). Era un `useState`
 * por componente, así que dos sitios que leyeran la misma clave tenían cada uno
 * su copia: el que la cambiaba se enteraba y el otro no, hasta recargar.
 *
 * Se vio al sacar el selector de orientación fuera de la cancha. Mientras el
 * botón vivía dentro del mismo componente que dibujaba las filas no había dos
 * copias y el fallo no existía; en cuanto el que ELIGE y el que DIBUJA
 * quedaron separados, pulsar cambiaba el botón y la cancha se quedaba igual.
 *
 * Por eso ahora el valor vive en el módulo y los componentes se suscriben, con
 * `useSyncExternalStore`: el mismo patrón que `config/consentimiento` y
 * `utils/destellos`, que están aquí por la misma razón.
 *
 * OJO con lo que NO hace: esto vive en el navegador. Un navegador configurado
 * para borrar los datos del sitio al cerrarse se lleva por delante todos estos
 * ajustes, igual que se llevó la sesión en su día. Para algo que deba seguir
 * al usuario entre navegadores hace falta guardarlo en el servidor.
 */
export function usePersistido<T>(clave: string, porDefecto: T) {
  const suscribir = useCallback(
    (avisar: () => void) => {
      let oyentes = OYENTES.get(clave);
      if (!oyentes) {
        oyentes = new Set();
        OYENTES.set(clave, oyentes);
      }
      oyentes.add(avisar);
      return () => {
        oyentes.delete(avisar);
      };
    },
    [clave],
  );

  // LA MISMA REFERENCIA MIENTRAS NADIE CAMBIE NADA. `useSyncExternalStore`
  // vuelve a pintar cuando esto devuelve algo distinto de lo anterior, así que
  // un valor recién leído en cada llamada --que con un objeto sería otro
  // objeto-- sería un bucle de renders. De ahí la caché del módulo.
  const leer = useCallback((): T => {
    if (!EN_MEMORIA.has(clave)) EN_MEMORIA.set(clave, recordado(clave, porDefecto));
    return EN_MEMORIA.get(clave) as T;
  }, [clave, porDefecto]);

  const valor = useSyncExternalStore(suscribir, leer, leer);

  const setValor = useCallback(
    (siguiente: T | ((previo: T) => T)) => {
      const previo = (
        EN_MEMORIA.has(clave) ? EN_MEMORIA.get(clave) : recordado(clave, porDefecto)
      ) as T;
      const nuevo =
        typeof siguiente === "function"
          ? (siguiente as (previo: T) => T)(previo)
          : siguiente;
      EN_MEMORIA.set(clave, nuevo);
      try {
        localStorage.setItem(clave, JSON.stringify(nuevo));
      } catch {
        // Sin espacio, en privado o con los datos del sitio bloqueados,
        // guardar lanza. Perder un ajuste al cerrar es molesto; quedarse sin
        // pantalla por él es peor. El valor sigue en memoria, así que la
        // sesión de ahora funciona igual: lo único que se pierde es que
        // sobreviva a la recarga.
      }
      OYENTES.get(clave)?.forEach((avisar) => avisar());
    },
    [clave, porDefecto],
  );

  return [valor, setValor] as const;
}

/** Quién quiere enterarse de que una clave cambió. */
const OYENTES = new Map<string, Set<() => void>>();

/** El valor vigente de cada clave. Es lo que hace que dos componentes vean lo
 *  mismo, y además lo que mantiene estable la referencia que lee React. */
const EN_MEMORIA = new Map<string, unknown>();

/** Lo guardado, o el valor por defecto si no hay nada o no se puede leer.
 *
 *  El `catch` no es paranoia: basta con que alguien haya guardado texto plano
 *  bajo esa clave en una versión anterior para que `JSON.parse` reviente, y
 *  reventar al arrancar por un ajuste es peor que ignorarlo.
 *
 *  2026-10-23: LA LECTURA TAMBIÉN VA DENTRO DEL `try`. Estaba fuera, y era el
 *  mismo fallo que ya se arregló abajo para `setItem` --«en privado o con los
 *  datos del sitio bloqueados, guardar lanza»-- dejado a medias: leer lanza
 *  exactamente igual, y `localStorage` no existe en absoluto fuera del
 *  navegador. Y esta mitad era la peor de las dos: el `setItem` vive en un
 *  efecto, que falla después de pintar, mientras que esto es el valor inicial
 *  del `useState` y se ejecuta ANTES del primer render. Reventaba la pantalla
 *  entera por un ajuste, que es justo lo que el otro `catch` existe para
 *  evitar.
 */
export function recordado<T>(clave: string, porDefecto: T): T {
  try {
    const guardado = localStorage.getItem(clave);
    if (guardado === null) return porDefecto;
    return JSON.parse(guardado) as T;
  } catch {
    return porDefecto;
  }
}
