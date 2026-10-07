/** La fontaneria: una sola puerta al backend, con el refresco de sesion.
 *
 *  Sale de partir `services/api.ts`, que tenia 4147 lineas y se leia entero
 *  en cada cambio del frontend. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../services/api"` sigue valiendo igual.
 */
import i18n from "../../i18n";

export const BASE = import.meta.env.VITE_API_URL ?? "/api/v1";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly detail?: unknown,
  ) {
    super(message);
  }
}

/**
 * Mensaje legible de cualquier error: desenvuelve el `detail` de FastAPI, que
 * a veces llega como string y a veces como `{detail: "..."}`. Vive aquí (y no
 * en una pantalla) porque lo necesitan todas las que disparan mutaciones.
 */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const detail = error.detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "detail" in detail) {
      const inner = (detail as { detail: unknown }).detail;
      if (typeof inner === "string") return inner;
    }
    return error.message;
  }
  return error instanceof Error ? error.message : "Error desconocido.";
}

// La cookie de acceso dura pocos minutos (`jwt_access_ttl_minutes`) a
// propósito. La de refresco (días) la renueva en silencio: un 401 dispara
// como mucho UN intento de /auth/refresh, compartido entre requests
// simultáneos (varias queries pueden expirar a la vez), antes de reintentar
// la petición original. Si el refresco también falla (sesión realmente
// muerta), se deja pasar el 401 tal cual, la UI ya sabe pedir reconectar.
//: Lo que contesta un intento de renovar la sesion. Son TRES cosas, y la
//: tercera es la que faltaba: que el servidor no conteste no significa que la
//: sesion haya muerto. Reportado por el usuario: «se desconecta y se va para
//: render a veces» (2026-09-19). El servidor se reinicia --un despliegue, un
//: reinicio del proveedor--, la renovacion se va con el, y la aplicacion lo
//: leia como «sesion muerta»: te echaba a /welcome, con recarga de pagina
//: entera, justo en el peor momento para pedirle una pagina al servidor. De
//: ahi la pantalla del proveedor. Se echa solo cuando el servidor DICE que no.
type Renovacion = "viva" | "muerta" | "sin-respuesta";

let refreshing: Promise<Renovacion> | null = null;

/** Que significa el codigo con el que contesto la renovacion.
 *
 *  401 y 403 son el servidor negandose: la sesion esta muerta de verdad.
 *  Cualquier otro fallo --un 502 del proveedor mientras reinicia, un 500, una
 *  pagina de error que no es nuestra-- dice otra cosa: que ahora mismo no hay
 *  con quien hablar. `null` es "ni siquiera hubo respuesta". */
export function leerRenovacion(estado: number | null): Renovacion {
  if (estado === null) return "sin-respuesta";
  if (estado >= 200 && estado < 300) return "viva";
  return estado === 401 || estado === 403 ? "muerta" : "sin-respuesta";
}

export function expireLocalSession(): void {
  localStorage.removeItem("htlens_team_id");
  if (!window.location.pathname.startsWith("/welcome")) {
    window.location.assign("/welcome?reason=session_expired");
  }
}

export function refreshSession(): Promise<Renovacion> {
  if (!refreshing) {
    refreshing = fetch(`${BASE}/auth/chpp/refresh`, {
      method: "POST",
      credentials: "include",
    })
      .then((res): Renovacion => leerRenovacion(res.status))
      // Sin red, servidor cayendose o peticion cortada. Tampoco es una sesion
      // muerta; se reintentara sola en la siguiente peticion.
      .catch((): Renovacion => "sin-respuesta")
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

/** El idioma de la app viaja en cada petición: el servidor escribe sus
 *  textos (alertas, rótulos, notas) en ese idioma, y en español si no sabe. */
export const idioma = () => ({ "Accept-Language": i18n.language || "es" });

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const doFetch = () =>
    fetch(`${BASE}${path}`, {
      credentials: "include",
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...idioma(),
        ...init?.headers,
      },
    });

  let res = await doFetch();
  const mayRefresh =
    path !== "/auth/chpp/refresh" && path !== "/auth/chpp/connect";
  // Se echa al usuario SÓLO si el refresco falló, o sea si la sesión con HT
  // Lens está de verdad muerta. Antes bastaba con que la petición reintentada
  // volviera a dar 401 para mandarlo a /welcome, y un 401 puede venir de que
  // Hattrick rechazó NUESTRO token, que es otro problema y no se arregla
  // volviendo a entrar. Un hipo pasajero de Hattrick expulsaba de la
  // aplicación (2026-09-04, reportado en producción).
  let renovacion: Renovacion = "viva";
  if (res.status === 401 && mayRefresh) {
    renovacion = await refreshSession();
    if (renovacion === "viva") res = await doFetch();
  }

  // Solo «muerta» echa de la aplicacion. Con «sin-respuesta» el error sube a
  // la pantalla, que lo enseña y lo reintenta, y la sesion se queda donde
  // estaba: un servidor reiniciandose no es una sesion caducada.
  if (res.status === 401 && mayRefresh && renovacion === "muerta") {
    expireLocalSession();
  }

  if (!res.ok) {
    // El cuerpo se lee UNA vez, como texto, y se intenta interpretar después.
    //
    // 2026-09-05. Antes esto era `res.json()` y, si fallaba, `res.text()` en
    // el `catch`. Pero un `json()` fallido ya ha consumido el flujo, así que
    // el `text()` de rescate lanzaba «body stream already read» --una frase
    // interna que sustituía al error de verdad y aparecía en pantalla--.
    // Pasaba siempre que la respuesta no era JSON, que es justo lo que
    // contesta el proxy cuando el backend local está caído: el usuario veía
    // un fallo del navegador donde tenía que ver «no hay conexión».
    const cuerpo = await res.text().catch(() => "");
    let detail: unknown = cuerpo;
    try {
      detail = JSON.parse(cuerpo);
    } catch {
      // No era JSON: se queda el texto tal cual, que ya es mejor pista.
    }
    throw new ApiError(`${res.status} ${res.statusText}`, res.status, detail);
  }
  return res.json() as Promise<T>;
}
