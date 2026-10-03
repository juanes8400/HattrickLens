/**
 * Traducción de HT Lens (2026-09-15).
 *
 * La regla que protege lo ya montado: el español es el idioma por defecto y
 * el de respaldo. Cada texto se busca por clave; si falta en el idioma
 * elegido se enseña en español, nunca vacío.
 *
 * Dos espacios de nombres:
 *   · `app`: los textos propios de HT Lens (`es.json`, `en.json`).
 *   · `glosario`: el vocabulario oficial de Hattrick, generado desde
 *     `translations.xml` con `backend/scripts/generar_glosario.py`. No se
 *     edita a mano.
 *
 * Qué idioma sale al entrar (2026-09-16): manda lo que el usuario haya
 * elegido en este navegador; si no ha elegido nunca, el idioma del navegador,
 * y si ése no es español, inglés. Un club de Hattrick puede estar en
 * cualquier país, así que el español no puede ser el defecto de todos.
 */
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import appEs from "./es.json";
import appEn from "./en.json";
import appIt from "./it.json";
import appDe from "./de.json";
import appPl from "./pl.json";
import glosarioEs from "./glosario/es.json";
import glosarioEn from "./glosario/en.json";
import glosarioIt from "./glosario/it.json";
import glosarioDe from "./glosario/de.json";
import glosarioPl from "./glosario/pl.json";
import textosEn from "./textos/en.json";
import textosIt from "./textos/it.json";
import textosDe from "./textos/de.json";
import textosPl from "./textos/pl.json";

/** Los idiomas que tienen diccionario en el paquete. NO son los que se
 *  ofrecen: ver `OFRECIDOS`. */
export const IDIOMAS = ["es", "en", "it", "de", "pl"] as const;
export type Idioma = (typeof IDIOMAS)[number];

/** Los idiomas TERMINADOS, que son los únicos que se le enseñan a nadie.
 *
 *  Vive aquí y no en el selector porque no basta con esconderlo de la lista:
 *  mientras el italiano estuvo a medias, un navegador puesto en italiano se lo
 *  encontraba igual por la detección automática, que miraba `IDIOMAS`. Una
 *  pantalla mitad en italiano y mitad en español es peor que una entera en
 *  inglés.
 *
 *  2026-09-28: el italiano entra. Las 3.616 cadenas están traducidas, y el
 *  vocabulario del juego --niveles de habilidad, especialidades, carácter,
 *  tácticas, puestos-- no se tradujo a ojo: sale del glosario oficial que
 *  publica Hattrick, el mismo que usa el propio juego en italiano.
 *
 *  2026-09-29: el alemán entra igual, y con él se tapó un agujero que el
 *  italiano tenía desde el primer día: 226 claves nombradas que ningún
 *  guardián miraba porque no se escriben enteras en el código, se arman al
 *  vuelo con una plantilla. Lo impide ahora `idioma.test.ts`, que le exige a
 *  cada idioma OFRECIDO las mismas claves que al inglés.
 *
 *  2026-10-03: el polaco. 1.044 claves nombradas y los 3.624 textos, y el
 *  vocabulario del juego --niveles, especialidades, carácter, agresividad,
 *  honestidad, tácticas, puestos, sectores, entrenamientos, moral, confianza,
 *  afición y expectativas-- sale del glosario oficial de Hattrick, no de
 *  traducirlo a ojo. Dos cosas le pidió el idioma al código, y las dos están:
 *  separa los miles con un espacio duro (`MILES` en `useFormat.ts` y en
 *  `formatting.py`, que ya no sabía escribir otra cosa que punto o coma) y
 *  escribe el ordinal con punto, «3.», como el alemán.
 *
 *  Lo que el polaco NO tiene todavía, y no es cosa de traducir: sus TRES
 *  formas de plural --1, 2-4, 5 o más-- no caben en las claves de ahora, que
 *  son dos («{n} jugador» y «{n} jugadores»). Donde la cifra manda sale la
 *  forma de 2-4, que es la correcta en la mayoría de los casos y la menos
 *  violenta en los demás. */
export const OFRECIDOS: readonly Idioma[] = ["es", "en", "it", "de", "pl"];

const CLAVE_GUARDADA = "htlens.idioma";

function esIdioma(valor: string | null): valor is Idioma {
  return valor != null && (IDIOMAS as readonly string[]).includes(valor);
}

function seOfrece(valor: string | null): valor is Idioma {
  return esIdioma(valor) && OFRECIDOS.includes(valor);
}

/** El primero de la lista del navegador que la app OFREZCA; inglés si ninguno.
 *
 *  Se exporta para poder probarlo sin navegador. */
export function idiomaPreferido(etiquetas: readonly string[]): Idioma {
  for (const etiqueta of etiquetas) {
    const codigo = (etiqueta ?? "").slice(0, 2).toLowerCase();
    if (seOfrece(codigo)) return codigo;
  }
  return "en";
}

function idiomaDelNavegador(): Idioma {
  try {
    const lista = navigator.languages?.length
      ? navigator.languages
      : [navigator.language];
    return idiomaPreferido(lista);
  } catch {
    return "en";
  }
}

/** Lo elegido en este navegador; la primera vez, lo que diga el navegador. */
function idiomaGuardado(): Idioma {
  try {
    const valor = localStorage.getItem(CLAVE_GUARDADA);
    // Contra lo OFRECIDO y no contra lo que hay: un «it» guardado de cuando
    // se probaba dejaria la pantalla a medias para siempre.
    if (seOfrece(valor)) return valor;
  } catch {
    return idiomaDelNavegador();
  }
  return idiomaDelNavegador();
}

void i18n.use(initReactI18next).init({
  resources: {
    es: { app: appEs, glosario: glosarioEs },
    en: { app: appEn, glosario: glosarioEn, textos: textosEn },
    it: { app: appIt, glosario: glosarioIt, textos: textosIt },
    de: { app: appDe, glosario: glosarioDe, textos: textosDe },
    pl: { app: appPl, glosario: glosarioPl, textos: textosPl },
  },
  lng: idiomaGuardado(),
  fallbackLng: "es",
  ns: ["app", "glosario", "textos"],
  defaultNS: "app",
  interpolation: { escapeValue: false },
  returnNull: false,
});

/** El `lang` del `<html>`, que se quedaba en «es» para todo el mundo.
 *
 *  2026-10-03, al entrar el polaco. No es decorativo: un lector de pantalla
 *  lee con la fonética del idioma que declara la página --el polaco con
 *  acento español es ininteligible-- y el navegador ofrece traducir una
 *  página que ya está en el idioma de quien la mira. Va por el evento de
 *  i18next y no en una línea suelta para que valga también cuando el idioma
 *  cambie sin recargar. */
function marcarIdiomaEnElHtml(idioma: string): void {
  try {
    document.documentElement.lang = idioma.slice(0, 2);
  } catch {
    // Sin DOM (una prueba, un render en servidor) no hay nada que marcar.
  }
}

i18n.on("languageChanged", marcarIdiomaEnElHtml);
marcarIdiomaEnElHtml(i18n.language || "es");

/** Cambia el idioma, lo recuerda en este navegador y recarga.
 *
 *  Recarga a propósito: muchas tablas y constantes se arman al cargar el
 *  módulo, y sólo una carga nueva garantiza que TODO salga en el idioma
 *  elegido y no media pantalla en uno y media en otro. */
export function cambiarIdioma(idioma: Idioma): void {
  try {
    localStorage.setItem(CLAVE_GUARDADA, idioma);
  } catch {
    // Almacenamiento bloqueado: se cambia sólo hasta la próxima carga.
    void i18n.changeLanguage(idioma);
    return;
  }
  window.location.reload();
}

export default i18n;
