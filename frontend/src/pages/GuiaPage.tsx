/** La Wiki, en abierto.
 *
 *  POR QUÉ EXISTE UNA SEGUNDA PUERTA A LO MISMO. La Wiki son mil ochocientas
 *  líneas que explican cómo funciona Hattrick y cómo calcula HT Lens, y hasta
 *  hoy vivían ENTERAS detrás del OAuth. Eso dejaba el sitio público reducido a
 *  una pantalla de «conecta tu club» y dos páginas legales: nada que leer para
 *  quien llega de un buscador, y nada que revisar para el rastreador de
 *  anuncios, que nunca inicia sesión. La falta de contenido propio es la causa
 *  más común de que AdSense rechace un sitio, y era la nuestra.
 *
 *  NO ES CONTENIDO DUPLICADO NI UN APAÑO. Es el mismo material servido a dos
 *  públicos distintos: `/wiki` va dentro de la aplicación, con su barra
 *  lateral y para quien ya entró; `/guia` es la versión de la calle, sin
 *  sesión y sin pedir nada.
 *
 *  NO SE TOCÓ `/wiki`. Moverla fuera del guardián habría dejado a quien ya ha
 *  entrado sin barra lateral al abrir la Wiki, que es una regresión a cambio
 *  de nada. Dos rutas, un solo contenido, cero riesgo para lo que ya
 *  funcionaba.
 *
 *  Y AQUÍ SÍ VA UN ANUNCIO, cuando lo haya: es la única pantalla pública con
 *  contenido de verdad, que es justo lo que la política de Google exige para
 *  poder enseñar publicidad.
 */
import { WikiPage } from "./WikiPage";
import { Anuncio } from "../components/Anuncio";
import { tx } from "../i18n/tx";

export function GuiaPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-4 p-4 sm:p-6">
      {/* `a` y no `Link` para ser coherentes con la bienvenida, que es de
          donde se llega. */}
      <a
        href="/welcome"
        className="inline-block text-sm text-[var(--muted)] hover:text-[var(--text)]"
      >
        ← {tx("Volver")}
      </a>

      <WikiPage />

      <Anuncio hueco="guia" className="mt-6" />

      <div className="flex justify-center gap-4 pt-2 text-xs text-[var(--muted)]">
        <a href="/privacidad" className="hover:text-[var(--text)]">
          {tx("Privacidad y cookies")}
        </a>
      </div>
    </div>
  );
}
