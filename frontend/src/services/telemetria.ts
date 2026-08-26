/** Qué usa la gente: páginas, clics y tiempo dentro de cada pantalla.
 *
 * 2026-08-26, pedido por el usuario. Vive aquí y no en un servicio de fuera:
 * los datos no salen de su servidor, ningún bloqueador lo tumba y no hay
 * cookie que consentir —la sesión de la aplicación ya existía—.
 *
 * Lo que NUNCA se manda: nada que el usuario escriba. Ni el contenido de un
 * campo, ni una búsqueda. De un clic sólo viaja la etiqueta visible del
 * control, recortada.
 */

/** El módulo al que pertenece una ruta. Se traduce aquí, con nombres que el
 *  usuario reconoce, en vez de guardar rutas crudas que luego nadie sabe leer. */
const MODULOS: [RegExp, string][] = [
  [/^\/academy/, "Juveniles"],
  [/^\/team$|^\/players\//, "Jugadores"],
  [/^\/transfers/, "Transferencias"],
  [/^\/sync/, "Sincronización"],
  [/^\/economy/, "Economía"],
  [/^\/matches/, "Partidos"],
  [/^\/league/, "Liga"],
  [/^\/cup/, "Copa"],
  [/^\/rivals/, "Rivales"],
  [/^\/training/, "Entrenamiento"],
  [/^\/lineup/, "Alineación"],
  [/^\/positions/, "Posiciones"],
  [/^\/arena/, "Estadio"],
  [/^\/club/, "Club y staff"],
  [/^\/overview/, "Equipo"],
  [/^\/insights/, "Avisos"],
  [/^\/news/, "Cambios"],
  [/^\/dashboard/, "Dashboard"],
  [/^\/engine/, "Motor"],
  [/^\/uso/, "Uso"],
];

export function moduloDe(ruta: string): string {
  for (const [patron, nombre] of MODULOS) if (patron.test(ruta)) return nombre;
  return "Otros";
}

type Evento = {
  sessionId: string;
  kind: "page" | "click";
  module: string;
  label: string | null;
  at: string;
  visibleMs: number;
};

const CLAVE_SESION = "htlens.sesion";
/** Media hora de silencio y se considera otra visita. Cerrar el navegador no
 *  siempre avisa —se pierde la conexión, el móvil mata la pestaña—, así que
 *  esperar ese aviso dejaría sesiones abiertas para siempre. */
const CORTE_POR_SILENCIO_MS = 30 * 60 * 1000;
const CLAVE_ULTIMO = "htlens.ultimo";

function sesionActual(): string {
  try {
    const ahora = Date.now();
    const ultimo = Number(sessionStorage.getItem(CLAVE_ULTIMO) ?? 0);
    let id = sessionStorage.getItem(CLAVE_SESION);
    if (!id || ahora - ultimo > CORTE_POR_SILENCIO_MS) {
      id = crypto.randomUUID();
      sessionStorage.setItem(CLAVE_SESION, id);
    }
    sessionStorage.setItem(CLAVE_ULTIMO, String(ahora));
    return id;
  } catch {
    // Modo privado, almacenamiento bloqueado: se sigue midiendo, sin agrupar.
    return "sin-sesion";
  }
}

const cola: Evento[] = [];
let temporizador: number | null = null;

/** La cola se guarda también en disco.
 *
 *  2026-08-26, encontrado probándolo: navegando rápido se perdía algún evento.
 *  La cola vivía sólo en memoria y una recarga completa se la llevaba, así que
 *  lo que estuviera esperando su turno moría con la página. Se pierde poco y en
 *  silencio, que es la peor forma de perder datos: los números salen bajos y
 *  parece que la gente usa la aplicación menos de lo que la usa.
 *
 *  Con el respaldo en disco, lo que no llegó a salir se manda en la siguiente
 *  visita. */
const CLAVE_PENDIENTES = "htlens.pendientes";

function guardarPendientes() {
  try {
    if (cola.length === 0) localStorage.removeItem(CLAVE_PENDIENTES);
    else localStorage.setItem(CLAVE_PENDIENTES, JSON.stringify(cola));
  } catch {
    // Almacenamiento bloqueado: se sigue midiendo, sin red de seguridad.
  }
}

function recuperarPendientes() {
  try {
    const guardado = localStorage.getItem(CLAVE_PENDIENTES);
    if (!guardado) return;
    localStorage.removeItem(CLAVE_PENDIENTES);
    const viejos = JSON.parse(guardado) as Evento[];
    // Tope por si una pestaña con un fallo dejó ahí miles: el servidor los
    // rechazaría en bloque y se perdería todo, incluido lo bueno.
    if (Array.isArray(viejos)) cola.push(...viejos.slice(-100));
  } catch {
    // Guardado ilegible: no vale la pena que un dato de medición rompa nada.
  }
}

function encolar(e: Evento) {
  cola.push(e);
  guardarPendientes();
  // Se manda en tandas: una petición por clic multiplicaría el tráfico de la
  // aplicación por diez sin necesidad.
  if (cola.length >= 20) enviar();
  else if (temporizador === null) {
    temporizador = window.setTimeout(enviar, 15_000);
  }
}

function enviar(conBeacon = false) {
  if (temporizador !== null) {
    clearTimeout(temporizador);
    temporizador = null;
  }
  if (cola.length === 0) return;
  const cuerpo = JSON.stringify({ events: cola.splice(0, 50) });
  guardarPendientes();
  const url = "/api/v1/usage/events";
  // Al cerrar la pestaña, `fetch` normal se cancela a media petición y se
  // pierde justo el evento que dice cuánto duró la última pantalla.
  if (conBeacon && navigator.sendBeacon) {
    navigator.sendBeacon(url, new Blob([cuerpo], { type: "application/json" }));
    return;
  }
  void fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: cuerpo,
    keepalive: true,
  }).catch(() => {
    // Medir nunca puede romper la aplicación: si falla, se pierde el dato.
  });
}

// ── El reloj de la página ───────────────────────────────────────────────────
//
// Sólo corre con la pestaña VISIBLE. Sin esto, una pestaña olvidada toda la
// noche diría "ocho horas en Juveniles" y el número dejaría de servir.
let rutaActual: string | null = null;
let etiquetaActual: string | null = null;
let visibleDesde: number | null = null;
let acumulado = 0;

function pausar() {
  if (visibleDesde !== null) {
    acumulado += Date.now() - visibleDesde;
    visibleDesde = null;
  }
}

function reanudar() {
  if (visibleDesde === null) visibleDesde = Date.now();
}

function cerrarPagina() {
  if (rutaActual === null) return;
  pausar();
  encolar({
    sessionId: sesionActual(),
    kind: "page",
    module: moduloDe(rutaActual),
    label: etiquetaActual,
    at: new Date().toISOString(),
    visibleMs: acumulado,
  });
  acumulado = 0;
}

/** Se llama en cada cambio de ruta. Cierra la anterior y abre la nueva. */
export function verPagina(ruta: string, etiqueta: string | null = null) {
  if (ruta === rutaActual && etiqueta === etiquetaActual) return;
  cerrarPagina();
  rutaActual = ruta;
  etiquetaActual = etiqueta;
  reanudar();
}

/** Un clic en algo con nombre. La etiqueta la elige quien llama, no un volcado
 *  del DOM: así nunca se cuela lo que alguien escribió. */
export function pulsado(etiqueta: string, ruta?: string) {
  encolar({
    sessionId: sesionActual(),
    kind: "click",
    module: moduloDe(ruta ?? rutaActual ?? "/"),
    label: etiqueta.slice(0, 120),
    at: new Date().toISOString(),
    visibleMs: 0,
  });
}

let arrancado = false;

/** Engancha los avisos del navegador. Idempotente. */
export function arrancarTelemetria() {
  if (arrancado) return;
  arrancado = true;

  // Lo que no llegó a salir en la visita anterior.
  recuperarPendientes();
  if (cola.length > 0) enviar();

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") {
      pausar();
      enviar(true);
    } else {
      reanudar();
    }
  });

  // `pagehide` y no `unload`: es el único que los navegadores móviles
  // disparan de verdad cuando el sistema se lleva la pestaña.
  window.addEventListener("pagehide", () => {
    cerrarPagina();
    enviar(true);
  });

  // Un solo escuchador para toda la aplicación, en vez de tocar cada botón.
  // Sólo mira controles: nunca campos de texto.
  document.addEventListener("click", (ev) => {
    const destino = (ev.target as HTMLElement | null)?.closest(
      "button, a, [role='tab'], [role='button']",
    );
    if (!destino) return;
    if (destino.closest("input, textarea, select")) return;
    const nombre =
      destino.getAttribute("data-track") ||
      destino.getAttribute("aria-label") ||
      (destino.textContent ?? "").trim();
    if (nombre) pulsado(nombre);
  });
}
