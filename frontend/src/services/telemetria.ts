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
  [/^\/club/, "Club y cuerpo técnico"],
  [/^\/overview/, "Equipo"],
  [/^\/insights/, "Alertas"],
  [/^\/news/, "Cambios"],
  [/^\/dashboard/, "Dashboard"],
  // «Motor» se llama Transparencia desde el 2026-08-31 y `/engine` redirige.
  // Sin la entrada nueva, todas sus visitas caían en «Otros» y el módulo
  // más consultado del mes no aparecía en la tabla.
  [/^\/transparency/, "Transparencia"],
  [/^\/engine/, "Transparencia"],
  [/^\/uso/, "Uso"],
  // El alta, cada pantalla por separado: es el embudo --cuántos entran, cuántos
  // conectan Hattrick y cuántos llegan a sincronizar-- y agrupadas en "Otros"
  // no se puede ver dónde se cae la gente.
  [/^\/welcome/, "Alta: bienvenida"],
  [/^\/connected/, "Alta: conectado"],
  [/^\/setup/, "Alta: importación"],
];

/** Un «Otros» que dice DE DÓNDE viene.
 *
 *  Antes, una ruta sin entrada en el mapa caía en un «Otros» a secas, y como
 *  lo que se guarda es el nombre del módulo --no la ruta-- después no había
 *  forma de saber qué era. Paso justo eso el 2026-08-31: la pantalla Motor
 *  paso a llamarse Transparencia, cambio de ruta a `/transparency`, el mapa se
 *  quedo sin la entrada nueva unas horas, y 51 eventos --de ellos 23 vistas de
 *  pagina SIN etiqueta, con casi siete horas dentro-- acabaron en un cajon
 *  imposible de desglosar.
 *
 *  Ahora el cajon lleva la ruta puesta: «Otros (/transparency)». Sale feo en
 *  la tabla a proposito -- una fila asi es un aviso de que falta una entrada
 *  en el mapa, no una categoria legitima --.
 *
 *  Los tramos numericos se sustituyen por `:id` para que mil fichas de jugador
 *  no se conviertan en mil modulos distintos. */
export function moduloDe(ruta: string): string {
  for (const [patron, nombre] of MODULOS) if (patron.test(ruta)) return nombre;
  const generica = ruta.replace(/\/\d+/g, "/:id") || "/";
  return `Otros (${generica})`;
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

/** Por debajo de esto no fue una visita, fue un rebote de redirección.
 *
 *  2026-08-26, visto en los datos: la raíz `/` redirige al panel y dejaba una
 *  "visita" de 60 ms. No sólo ensucia el recuento: hunde el tiempo medio por
 *  visita de un módulo que en realidad nadie llegó a ver.
 *
 *  El precio es que una salida instantánea de verdad tampoco se cuenta. Se
 *  asume: desde fuera son indistinguibles, y contarlas como visitas miente más
 *  que perderlas. */
const MINIMO_PARA_SER_VISITA_MS = 300;

function cerrarPagina() {
  if (rutaActual === null) return;
  pausar();
  if (acumulado < MINIMO_PARA_SER_VISITA_MS) {
    acumulado = 0;
    return;
  }
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
