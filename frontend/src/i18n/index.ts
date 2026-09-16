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
import glosarioEs from "./glosario/es.json";
import glosarioEn from "./glosario/en.json";
import textosEn from "./textos/en.json";

export const IDIOMAS = ["es", "en"] as const;
export type Idioma = (typeof IDIOMAS)[number];

const CLAVE_GUARDADA = "htlens.idioma";

function esIdioma(valor: string | null): valor is Idioma {
  return valor != null && (IDIOMAS as readonly string[]).includes(valor);
}

/** El primero de la lista del navegador que la app hable; inglés si ninguno.
 *
 *  Se exporta para poder probarlo sin navegador. */
export function idiomaPreferido(etiquetas: readonly string[]): Idioma {
  for (const etiqueta of etiquetas) {
    const codigo = (etiqueta ?? "").slice(0, 2).toLowerCase();
    if (esIdioma(codigo)) return codigo;
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
    if (esIdioma(valor)) return valor;
  } catch {
    return idiomaDelNavegador();
  }
  return idiomaDelNavegador();
}

void i18n.use(initReactI18next).init({
  resources: {
    es: { app: appEs, glosario: glosarioEs },
    en: { app: appEn, glosario: glosarioEn, textos: textosEn },
  },
  lng: idiomaGuardado(),
  fallbackLng: "es",
  ns: ["app", "glosario", "textos"],
  defaultNS: "app",
  interpolation: { escapeValue: false },
  returnNull: false,
});

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
