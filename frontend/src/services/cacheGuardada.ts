import { dehydrate, hydrate, type QueryClient } from "@tanstack/react-query";

/**
 * La caché de las pantallas, guardada entre recargas (2026-09-14).
 *
 * Al abrir la app se repinta al instante con lo último que se vio, y en segundo
 * plano se pide lo nuevo: los datos guardados llegan viejos (más de un minuto,
 * el `staleTime` de la app), así que React Query los refresca solo.
 *
 * Se tira entera si cambia la versión de la app --una respuesta de otra versión
 * puede no tener la forma que espera la pantalla-- o si tiene más de un día.
 * Nada de sesión ni de autenticación: eso se pregunta siempre.
 */

const CLAVE = "htlens-cache";
const EDAD_MAXIMA_MS = 24 * 60 * 60 * 1000;

function persistible(clave: readonly unknown[]): boolean {
  const nombre = String(clave[0] ?? "");
  return !/session|auth/i.test(nombre);
}

export function restaurarCache(qc: QueryClient): void {
  try {
    const crudo = localStorage.getItem(CLAVE);
    if (!crudo) return;
    const guardado = JSON.parse(crudo) as {
      version: string;
      guardado: number;
      estado: unknown;
    };
    if (
      guardado.version !== __VERSION__ ||
      Date.now() - guardado.guardado > EDAD_MAXIMA_MS
    ) {
      localStorage.removeItem(CLAVE);
      return;
    }
    hydrate(qc, guardado.estado);
  } catch {
    // Sin caché guardada (bloqueada, llena o corrupta): se carga como siempre.
  }
}

export function guardarCacheAlCambiar(qc: QueryClient): void {
  let pendiente: number | undefined;
  qc.getQueryCache().subscribe((evento) => {
    if (evento.type !== "updated") return;
    window.clearTimeout(pendiente);
    // Una sola escritura por ráfaga: el Dashboard termina diez peticiones en
    // pocos segundos.
    pendiente = window.setTimeout(() => {
      try {
        localStorage.setItem(
          CLAVE,
          JSON.stringify({
            version: __VERSION__,
            guardado: Date.now(),
            estado: dehydrate(qc, {
              shouldDehydrateQuery: (q) =>
                q.state.status === "success" && persistible(q.queryKey),
            }),
          }),
        );
      } catch {
        // Sin espacio o sin permiso: la próxima carga será la de siempre.
      }
    }, 2000);
  });
}
