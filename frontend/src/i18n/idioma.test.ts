import { describe, expect, it } from "vitest";

import { idiomaPreferido } from ".";

describe("idiomaPreferido", () => {
  it("respeta el español del navegador", () => {
    expect(idiomaPreferido(["es-CO", "es"])).toBe("es");
    expect(idiomaPreferido(["es"])).toBe("es");
  });

  it("da inglés a quien no tiene el navegador en español", () => {
    expect(idiomaPreferido(["en-GB", "en"])).toBe("en");
    // Un idioma que la app no habla todavía: inglés, que es lo que entiende
    // más gente, y nunca español por defecto.
    expect(idiomaPreferido(["sv-SE", "de"])).toBe("en");
    expect(idiomaPreferido([])).toBe("en");
  });

  it("toma el primero de la lista que la app hable", () => {
    expect(idiomaPreferido(["fr", "es", "en"])).toBe("es");
    expect(idiomaPreferido(["fr", "en", "es"])).toBe("en");
  });
});

describe("los idiomas a medias no se le dan a nadie", () => {
  it("un navegador en italiano recibe inglés, no el italiano a medias", () => {
    // El italiano está traducido a medias A PROPÓSITO y escondido del
    // selector. Escondido de la lista no basta: la detección automática
    // miraba todos los idiomas con diccionario y se lo servía igual a quien
    // tuviera el navegador en italiano, que es justo a quien se le quería
    // ahorrar media pantalla en español.
    expect(idiomaPreferido(["it-IT", "it"])).toBe("en");
    expect(idiomaPreferido(["it"])).toBe("en");
  });

  it("el español sigue ganando aunque el italiano vaya delante", () => {
    expect(idiomaPreferido(["it", "es"])).toBe("es");
  });
});
