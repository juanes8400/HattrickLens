import { useEffect, useState } from "react";

/**
 * El valor una vez deja de moverse (2026-09-19).
 *
 * Los mandos de Juveniles piden al servidor con lo que marcan, y arrastrar una
 * barra dispara un cambio por píxel: ocho peticiones en un par de segundos,
 * cada una rehaciendo la tabla entera. Con la respuesta lenta, eso se siente
 * como un mando que no responde.
 *
 * Aquí se separan las dos cosas: la barra se mueve al instante contra su
 * estado, y la pregunta al servidor espera a que sueltes. `ms` es cuánto
 * silencio hace falta para considerar que ya paraste.
 *
 * OJO: compara por identidad, así que un objeto nuevo en cada renderizado
 * nunca llegaría a asentarse. Pásale estado, no objetos recién construidos.
 */
export function useAsentado<T>(valor: T, ms = 250): T {
  const [asentado, setAsentado] = useState<T>(valor);
  useEffect(() => {
    const id = window.setTimeout(() => setAsentado(valor), ms);
    return () => window.clearTimeout(id);
  }, [valor, ms]);
  return asentado;
}
