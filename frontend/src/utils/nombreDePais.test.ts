import { beforeEach, describe, expect, it, vi } from "vitest";

/**
 * El nombre del país sigue al idioma de la aplicación (2026-09-21).
 *
 * Lo que guarda HT Lens es el nombre de la liga tal y como lo manda
 * Hattrick, que para esta cuenta viene en español. La columna Origen decía
 * «Alemania» con la aplicación en inglés porque el traductor de nombres
 * estaba fijo en español.
 *
 * La tabla se arma al CARGAR el módulo --cambiar de idioma recarga la
 * página entera--, así que cada caso se prueba volviendo a importarlo con
 * el idioma ya puesto.
 */
// Este fichero corre sin navegador, y el idioma se guarda en
// `localStorage`: lo mínimo para que el módulo lo lea al cargarse.
const guardado: Record<string, string> = {};
vi.stubGlobal("localStorage", {
  getItem: (clave: string) => guardado[clave] ?? null,
  setItem: (clave: string, valor: string) => {
    guardado[clave] = valor;
  },
});

async function nombreDePais(idioma: string) {
  // Igual que en la aplicación: el idioma se elige, se guarda y se carga de
  // nuevo. Por eso se deja escrito antes de volver a importar.
  localStorage.setItem("htlens.idioma", idioma);
  vi.resetModules();
  const modulo = await import("./countryCodes");
  return modulo.nombreDePais;
}

describe("el país en el idioma de la aplicación", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it("en español dice Alemania", async () => {
    const nombre = await nombreDePais("es");
    expect(nombre("de", "Alemania")).toBe("Alemania");
  });

  it("en inglés dice Germany, aunque lo guardado diga Alemania", async () => {
    const nombre = await nombreDePais("en");
    expect(nombre("de", "Alemania")).toBe("Germany");
    expect(nombre("es", "España")).toBe("Spain");
    expect(nombre("it", "Italia")).toBe("Italy");
  });

  it("reconoce el texto en español aunque la pantalla esté en inglés", async () => {
    // Sin código, el país hay que sacarlo del nombre guardado, y ese nombre
    // viene de Hattrick en español pase lo que pase con la pantalla.
    const nombre = await nombreDePais("en");
    expect(nombre(null, "Alemania")).toBe("Germany");
    expect(nombre(null, "Madagasikara")).toBe("Madagascar");
  });

  it("la liga que no se llama como su bandera también se traduce", async () => {
    // «Inglaterra» lleva bandera británica, así que su nombre no se puede
    // sacar del código: se traduce como cualquier otro texto.
    expect((await nombreDePais("es"))("gb", "Inglaterra")).toBe("Inglaterra");
    expect((await nombreDePais("en"))("gb", "Inglaterra")).toBe("England");
  });

  it("sin nada que identificar, no inventa", async () => {
    const nombre = await nombreDePais("en");
    expect(nombre(null, null)).toBeNull();
  });
});
