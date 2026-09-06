import { useEffect, useState } from "react";

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
 * OJO con lo que NO hace: esto vive en el navegador. Un navegador configurado
 * para borrar los datos del sitio al cerrarse se lleva por delante todos estos
 * ajustes, igual que se llevó la sesión en su día. Para algo que deba seguir
 * al usuario entre navegadores hace falta guardarlo en el servidor.
 */
export function usePersistido<T>(clave: string, porDefecto: T) {
  const [valor, setValor] = useState<T>(() => recordado(clave, porDefecto));
  useEffect(() => {
    localStorage.setItem(clave, JSON.stringify(valor));
  }, [clave, valor]);
  return [valor, setValor] as const;
}

/** Lo guardado, o el valor por defecto si no hay nada o no se puede leer.
 *
 *  El `catch` no es paranoia: basta con que alguien haya guardado texto plano
 *  bajo esa clave en una versión anterior para que `JSON.parse` reviente, y
 *  reventar al arrancar por un ajuste es peor que ignorarlo.
 */
export function recordado<T>(clave: string, porDefecto: T): T {
  const guardado = localStorage.getItem(clave);
  if (guardado === null) return porDefecto;
  try {
    return JSON.parse(guardado) as T;
  } catch {
    return porDefecto;
  }
}
