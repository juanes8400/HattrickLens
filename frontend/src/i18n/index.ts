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
 * El inglés no se ofrece a nadie todavía: sólo se activa guardando el idioma
 * en este navegador, para revisarlo antes de abrirlo.
 */
import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import appEs from "./es.json";
import appEn from "./en.json";
import glosarioEs from "./glosario/es.json";
import glosarioEn from "./glosario/en.json";

export const IDIOMAS = ["es", "en"] as const;
export type Idioma = (typeof IDIOMAS)[number];

const CLAVE_GUARDADA = "htlens.idioma";

function esIdioma(valor: string | null): valor is Idioma {
  return valor != null && (IDIOMAS as readonly string[]).includes(valor);
}

function idiomaGuardado(): Idioma {
  try {
    const valor = localStorage.getItem(CLAVE_GUARDADA);
    return esIdioma(valor) ? valor : "es";
  } catch {
    return "es";
  }
}

void i18n.use(initReactI18next).init({
  resources: {
    es: { app: appEs, glosario: glosarioEs },
    en: { app: appEn, glosario: glosarioEn },
  },
  lng: idiomaGuardado(),
  fallbackLng: "es",
  ns: ["app", "glosario"],
  defaultNS: "app",
  interpolation: { escapeValue: false },
  returnNull: false,
});

/** Cambia el idioma y lo recuerda en este navegador. */
export function cambiarIdioma(idioma: Idioma): void {
  try {
    localStorage.setItem(CLAVE_GUARDADA, idioma);
  } catch {
    // Almacenamiento bloqueado: se cambia igual, sin recordarlo.
  }
  void i18n.changeLanguage(idioma);
}

export default i18n;
