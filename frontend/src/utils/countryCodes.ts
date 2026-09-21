import countries from "flag-icons/country.json";
import i18n from "../i18n";
import { tx } from "../i18n/tx";

type CountryEntry = {
  code: string;
  iso: boolean;
  name: string;
};

function normalizeCountryName(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("es")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

const nameToCode = new Map<string, string>();

const nombres = (idioma: string) =>
  typeof Intl.DisplayNames === "function"
    ? new Intl.DisplayNames([idioma], { type: "region" })
    : null;

/** Los nombres que SE ESCRIBEN, en el idioma de la aplicación (2026-09-21).
 *
 *  Estaba fijo en español y por eso la columna Origen decía «Alemania» con
 *  la aplicación en inglés. El idioma se lee al cargar el módulo y no hace
 *  falta más: cambiarlo recarga la página entera (ver `cambiarIdioma`). */
const displayNames = nombres(i18n.language || "es");

/** Los nombres que SE LEEN. El texto que guarda la aplicación viene de
 *  Hattrick en español --«Alemania», «Madagasikara»--, así que reconocerlo
 *  hay que hacerlo en español pase lo que pase con el idioma de pantalla. */
const nombresLeidos = nombres("es");

for (const country of countries as CountryEntry[]) {
  if (!country.iso || !/^[a-z]{2}$/.test(country.code)) continue;
  const code = country.code.toLowerCase();
  nameToCode.set(normalizeCountryName(country.name), code);
  for (const fuente of new Set([nombresLeidos, displayNames])) {
    const nombre = fuente?.of(code.toUpperCase());
    if (nombre) nameToCode.set(normalizeCountryName(nombre), code);
  }
}

// Nombres de ligas Hattrick que no son el nombre ISO mostrado por el
// navegador. Solo se usa para registros históricos que guardaron el texto
// de teamdetails.xml antes de que HT Lens conservara CountryCode.
const HATTRICK_COUNTRY_ALIASES: Record<string, string> = {
  inglaterra: "gb",
  madagasikara: "mg",
  oceania: "au",
  tahiti: "pf",
};

for (const [name, code] of Object.entries(HATTRICK_COUNTRY_ALIASES)) {
  nameToCode.set(normalizeCountryName(name), code);
}

/** Ligas de Hattrick cuyo nombre NO es el del país ISO de su bandera:
 *  «Inglaterra» lleva la bandera británica, pero no se llama Reino Unido.
 *
 *  Su nombre no se puede sacar del código, así que se traduce como cualquier
 *  otro texto de la aplicación en vez de dejarlo en español (2026-09-21). */
const CONSERVAR_NOMBRE = new Set(["inglaterra", "oceania", "tahiti"]);

/** El nombre del país, sacado siempre del código y en el idioma de la
 *  aplicación (2026-09-13; el idioma, 2026-09-21).
 *
 *  Cada tabla lo tomaba de una fuente distinta y salía «Madagasikara» en
 *  Jugadores --el nombre de la liga en Hattrick-- y «Madagascar» en
 *  Entrenamiento. Si el texto recibido es de OTRO país que el código, o una
 *  liga que no se llama como su bandera, se respeta el texto. */
export function nombreDePais(
  code: string | null | undefined,
  country: string | null | undefined,
): string | null {
  const c = code?.trim().toLowerCase() || countryCodeFromName(country);
  if (!c || !/^[a-z]{2}$/.test(c) || !displayNames) return country ?? null;
  if (country) {
    const n = normalizeCountryName(country);
    if (CONSERVAR_NOMBRE.has(n)) return tx(country);
    const suyo = nameToCode.get(n);
    if (suyo != null && suyo !== c) return country;
  }
  return displayNames.of(c.toUpperCase()) ?? country ?? null;
}

export function countryCodeFromName(
  country: string | null | undefined,
): string | null {
  if (!country || country === "?") return null;
  return nameToCode.get(normalizeCountryName(country)) ?? null;
}
