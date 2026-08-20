import countries from "flag-icons/country.json";

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
const displayNames = typeof Intl.DisplayNames === "function"
  ? new Intl.DisplayNames(["es"], { type: "region" })
  : null;

for (const country of countries as CountryEntry[]) {
  if (!country.iso || !/^[a-z]{2}$/.test(country.code)) continue;
  const code = country.code.toLowerCase();
  nameToCode.set(normalizeCountryName(country.name), code);
  const spanishName = displayNames?.of(code.toUpperCase());
  if (spanishName) nameToCode.set(normalizeCountryName(spanishName), code);
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

export function countryCodeFromName(country: string | null | undefined): string | null {
  if (!country || country === "?") return null;
  return nameToCode.get(normalizeCountryName(country)) ?? null;
}
