/** El consentimiento de anuncios: lo que el visitante ha decidido.
 *
 *  QUÉ ES Y QUÉ NO ES. Esto guarda y transmite una decisión; no es una
 *  plataforma de consentimiento certificada. Google exige una certificada
 *  (TCF v2.2) para servir anuncios personalizados en el EEE, el Reino Unido
 *  y Suiza, y cuando se contrate, ella será quien conceda. Hasta entonces
 *  esto hace lo único que siempre hay que hacer bien: **nacer denegado** y
 *  no cargar nada ajeno hasta que alguien diga que sí.
 *
 *  POR QUÉ NO BASTA CON NO PINTAR EL ANUNCIO. El script de AdSense pone
 *  cookies en cuanto se carga, así que «cargarlo y no enseñar nada» ya sería
 *  rastrear sin permiso. Por eso la puerta está en la CARGA, no en el
 *  pintado.
 */

/** Dónde se recuerda la decisión. Con el mismo prefijo que el tema, que es
 *  la convención que ya había en `index.html` (`htlens.tema`). */
const LLAVE = "htlens.consentimiento";

export type Decision = "concedido" | "denegado" | "sin-decidir";

/** Lo que el navegador recuerda.
 *
 *  Cualquier fallo se lee como «sin decidir», que es el estado prudente: en
 *  una ventana privada, o con el almacenamiento bloqueado, se vuelve a
 *  preguntar en vez de dar por hecho un sí que nadie dio.
 */
export function decisionGuardada(): Decision {
  try {
    const v = localStorage.getItem(LLAVE);
    return v === "concedido" || v === "denegado" ? v : "sin-decidir";
  } catch {
    return "sin-decidir";
  }
}

type Gtag = (...args: unknown[]) => void;

/** Le cuenta a Google lo decidido, en su vocabulario (Modo de consentimiento
 *  v2). Las cuatro señales van juntas: conceder sólo algunas dejaría un
 *  estado que ni la norma ni Google saben interpretar. */
function avisarAGoogle(decision: Exclude<Decision, "sin-decidir">): void {
  const estado = decision === "concedido" ? "granted" : "denied";
  const gtag = (window as unknown as { gtag?: Gtag }).gtag;
  if (typeof gtag !== "function") return;
  gtag("consent", "update", {
    ad_storage: estado,
    ad_user_data: estado,
    ad_personalization: estado,
    analytics_storage: estado,
  });
}

const oyentes = new Set<() => void>();

/** Para que las pantallas abiertas reaccionen sin recargar. */
export function alCambiarElConsentimiento(fn: () => void): () => void {
  oyentes.add(fn);
  return () => oyentes.delete(fn);
}

export function decidir(decision: Exclude<Decision, "sin-decidir">): void {
  try {
    localStorage.setItem(LLAVE, decision);
  } catch {
    /* Sin almacenamiento la decisión vale para esta visita y no se recuerda:
       es peor perderla en memoria que no poder escribirla en disco. */
  }
  avisarAGoogle(decision);
  oyentes.forEach((fn) => fn());
}

/** Vuelve a preguntar. Lo pide la página de cookies: una decisión sobre
 *  rastreo tiene que poder deshacerse, y en el EEE eso es obligatorio. */
export function olvidarLaDecision(): void {
  try {
    localStorage.removeItem(LLAVE);
  } catch {
    /* Igual que arriba. */
  }
  avisarAGoogle("denegado");
  oyentes.forEach((fn) => fn());
}
