/** Un hueco de publicidad.
 *
 *  LA PUERTA ESTÁ EN LA CARGA, NO EN EL PINTADO. El script de AdSense pone
 *  cookies en cuanto entra en la página, así que traerlo y no enseñar nada
 *  ya sería rastrear sin permiso. Por eso aquí no se carga nada hasta que se
 *  cumplen TRES cosas: hay cliente configurado, el hueco tiene su
 *  identificador, y el visitante ha consentido.
 *
 *  SI FALTA CUALQUIERA, ESTO NO PINTA NADA --ni un marco, ni un hueco
 *  reservado--. Un recuadro vacío con la palabra «publicidad» en un sitio
 *  que no la sirve es peor que nada.
 *
 *  NO SE PONE EN PANTALLAS SIN CONTENIDO PROPIO. Es política de Google y es
 *  de sentido común: un anuncio en una pantalla de carga o en un error no
 *  acompaña a nada. Los huecos se declaran en `config/anuncios.ts` para que
 *  la lista pueda revisarse de un vistazo.
 */
import { useEffect, useRef } from "react";

import {
  CLIENTE_ADSENSE,
  hayAnuncios,
  huecoPorId,
  preguntaGoogle,
} from "../config/anuncios";
import { useConsentimiento } from "./Consentimiento";

const URL_ADSENSE =
  "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js";

/** Trae el script una sola vez por sesión de página.
 *
 *  Se marca con un atributo propio en vez de con una variable del módulo:
 *  así sigue siendo cierto aunque el módulo se recargue en caliente durante
 *  el desarrollo, que es cuando se duplicaba.
 */
function cargarAdSenseUnaVez(cliente: string): void {
  if (document.querySelector("script[data-htlens-adsense]")) return;
  const s = document.createElement("script");
  s.async = true;
  s.src = `${URL_ADSENSE}?client=${encodeURIComponent(cliente)}`;
  s.crossOrigin = "anonymous";
  s.setAttribute("data-htlens-adsense", "1");
  document.head.appendChild(s);
}

type Props = {
  /** El `id` de un hueco de `config/anuncios.ts`. */
  hueco: string;
  /** Para separarlo de lo que tiene alrededor. */
  className?: string;
};

export function Anuncio({ hueco, className }: Props) {
  const decision = useConsentimiento();
  const declarado = huecoPorId(hueco);
  const puesto = useRef<HTMLModElement | null>(null);
  const empujado = useRef(false);

  // CON LA PLATAFORMA DE GOOGLE no se espera a nuestra decision: la suya
  // viaja dentro del script, asi que hay que cargarlo para que pueda
  // preguntar. Lo que impide la fuga son los `denied` por defecto del Modo
  // de consentimiento, puestos en `index.html` antes que nada.
  const activo =
    hayAnuncios() &&
    !!declarado?.slot &&
    (preguntaGoogle() || decision === "concedido");

  useEffect(() => {
    if (!activo || empujado.current) return;
    cargarAdSenseUnaVez(CLIENTE_ADSENSE);
    try {
      const w = window as unknown as { adsbygoogle?: unknown[] };
      w.adsbygoogle = w.adsbygoogle || [];
      w.adsbygoogle.push({});
      // UNA VEZ POR HUECO. React vuelve a montar en desarrollo (StrictMode) y
      // un segundo `push` sobre el mismo `<ins>` hace que AdSense se queje de
      // «slot ya rellenado» y no pinte ninguno de los dos.
      empujado.current = true;
    } catch {
      /* Un bloqueador de anuncios hace fallar esto. No es un error de la
         aplicación y no debe romper la pantalla que lo contiene. */
    }
  }, [activo]);

  if (!activo) return null;

  return (
    <div className={className}>
      <ins
        ref={puesto}
        className="adsbygoogle block"
        style={{ display: "block" }}
        data-ad-client={CLIENTE_ADSENSE}
        data-ad-slot={declarado.slot}
        data-ad-format="auto"
        data-full-width-responsive="true"
      />
    </div>
  );
}
