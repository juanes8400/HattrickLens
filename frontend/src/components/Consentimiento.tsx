/** La barra que pregunta por las cookies de publicidad.
 *
 *  SÓLO APARECE SI HAY PUBLICIDAD CONFIGURADA. Sin `VITE_ADSENSE_CLIENT` no
 *  hay nada que consentir --no se carga un solo script ajeno-- y preguntar
 *  sería pedir permiso para algo que no se hace. Es el fallo más común de
 *  estas barras: salen en sitios que no rastrean nada.
 *
 *  DENEGAR ES TAN FÁCIL COMO ACEPTAR. Dos botones del mismo tamaño y el
 *  mismo peso visual. No es estética: una barra donde «aceptar» es un botón
 *  grande y «rechazar» un enlace gris no recoge un consentimiento válido.
 */
import { useSyncExternalStore } from "react";
import { Link } from "react-router-dom";

import {
  alCambiarElConsentimiento,
  decidir,
  decisionGuardada,
  type Decision,
} from "../config/consentimiento";
import { hayAnuncios } from "../config/anuncios";
import { tx } from "../i18n/tx";

/** La decisión actual, viva: si se cambia en otra pantalla, ésta se entera. */
export function useConsentimiento(): Decision {
  return useSyncExternalStore(
    (fn) => alCambiarElConsentimiento(fn),
    decisionGuardada,
    // En el render del servidor no hay navegador ni decisión que leer.
    () => "sin-decidir" as Decision,
  );
}

export function BarraDeConsentimiento() {
  const decision = useConsentimiento();
  if (!hayAnuncios() || decision !== "sin-decidir") return null;

  return (
    <div
      role="dialog"
      aria-label={tx("Cookies de publicidad")}
      className="fixed inset-x-0 bottom-0 z-50 border-t border-[var(--border)] bg-[var(--surface)] px-4 py-3 shadow-lg"
    >
      <div className="mx-auto flex max-w-4xl flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="prosa text-sm text-[var(--text)]">
          {tx(
            "Este sitio enseña anuncios para pagarse el alojamiento. Para que sean personalizados, Google necesita usar cookies. Puedes decir que no y seguir usando HT Lens igual.",
          )}{" "}
          <Link to="/cookies" className="underline">
            {tx("Qué se guarda y por qué")}
          </Link>
        </p>
        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            onClick={() => decidir("denegado")}
            className="rounded border border-[var(--border)] px-4 py-2 text-sm"
          >
            {tx("Rechazar")}
          </button>
          <button
            type="button"
            onClick={() => decidir("concedido")}
            className="rounded border border-[var(--border)] bg-[var(--accent-soft)] px-4 py-2 text-sm"
          >
            {tx("Aceptar")}
          </button>
        </div>
      </div>
    </div>
  );
}
