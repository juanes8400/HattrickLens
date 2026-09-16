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
