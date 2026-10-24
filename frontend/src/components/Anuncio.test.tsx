/** Que un despliegue sin publicidad no traiga NI UN BYTE ajeno.
 *
 *  Es el estado en el que está el sitio hoy y en el que seguirá mientras no
 *  haya cuenta de AdSense, así que es el que más veces se va a dar. Y es el
 *  más fácil de romper sin darse cuenta: basta con que alguien mueva la
 *  condición de sitio al añadir un hueco nuevo.
 *
 *  Se renderiza en el servidor, como el resto de pruebas de componentes de
 *  este proyecto: sin `useEffect`, que es justo donde vive la carga del
 *  script. Lo que se comprueba aquí es que no llega ni a pintarse el hueco,
 *  que es la puerta de antes.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Anuncio } from "./Anuncio";
import { BarraDeConsentimiento } from "./Consentimiento";
import { HUECOS, hayAnuncios } from "../config/anuncios";

describe("sin publicidad configurada", () => {
  it("el entorno de las pruebas no lleva editor, que es el caso por defecto", () => {
    expect(hayAnuncios()).toBe(false);
  });

  it("el hueco no pinta absolutamente nada", () => {
    // Ni un marco, ni un hueco reservado, ni la palabra «publicidad». Un
    // recuadro vacío en un sitio que no sirve anuncios es peor que nada.
    expect(renderToStaticMarkup(<Anuncio hueco="bienvenida" />)).toBe("");
    expect(renderToStaticMarkup(<Anuncio hueco="guia" />)).toBe("");
  });

  it("tampoco pinta nada un hueco que no existe", () => {
    expect(renderToStaticMarkup(<Anuncio hueco="inventado" />)).toBe("");
  });

  it("no se pregunta por cookies que nadie va a poner", () => {
    // El fallo más común de estas barras: salir en sitios que no rastrean.
    expect(renderToStaticMarkup(<BarraDeConsentimiento />)).toBe("");
  });
});

describe("los huecos declarados", () => {
  it("tienen identificadores únicos", () => {
    const ids = HUECOS.map((h) => h.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("dicen dónde van, para que la lista se pueda revisar de un vistazo", () => {
    // La política de Google prohíbe anuncios en páginas sin contenido propio,
    // así que cada hueco tiene que poder justificarse leyendo la lista.
    for (const h of HUECOS) {
      expect(h.donde.length, h.id).toBeGreaterThan(20);
    }
  });
});
