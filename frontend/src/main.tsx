import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { arrancarIdioma } from "./i18n";
import {
  guardarCacheAlCambiar,
  restaurarCache,
} from "./services/cacheGuardada";
import "./index.css";

/** EL IDIOMA, ANTES QUE NADA.
 *
 *  No basta con tenerlo antes de pintar: media aplicación llama a `tx("…")`
 *  al cargar su módulo, para armar constantes, y esas llamadas se quedarían
 *  con el español para siempre. Por eso `App` se importa DESPUÉS de que el
 *  diccionario esté puesto (2026-10-03, al dejar de empaquetar los cinco
 *  idiomas juntos).
 *
 *  Va en una función y no con `await` suelto porque el `await` de primer
 *  nivel no entra en el objetivo de compilación de este proyecto.
 */
async function arrancar(): Promise<void> {
  await arrancarIdioma();
  const { App } = await import("./App");

  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60_000,
        // Un día en memoria: lo restaurado de la última visita no debe
        // tirarse a los cinco minutos si nadie lo está mirando.
        gcTime: 24 * 60 * 60 * 1000,
        retry: 1,
        refetchOnWindowFocus: false,
      },
    },
  });
  restaurarCache(queryClient);
  guardarCacheAlCambiar(queryClient);

  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </React.StrictMode>,
  );
}

void arrancar();
