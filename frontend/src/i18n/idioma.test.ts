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
  it("un navegador en italiano recibe italiano", () => {
    // 2026-09-28: el italiano se terminó y entró en OFRECIDOS, así que la
    // detección automática ya se lo puede servir a quien lo tenga puesto.
    //
    // Hasta ese día esta prueba pedía lo contrario, y por un buen motivo:
    // esconderlo del selector NO bastaba, porque la detección automática
    // miraba todos los idiomas con diccionario y le servía media pantalla en
    // español a quien tuviera el navegador en italiano. La regla que hacía
    // falta --y que sigue aquí-- es que la detección mire lo OFRECIDO, no lo
    // que hay traducido a medias.
    expect(idiomaPreferido(["it-IT", "it"])).toBe("it");
    expect(idiomaPreferido(["it"])).toBe("it");
  });

  it("un idioma sin diccionario sigue recibiendo inglés", () => {
    // La regla de arriba se comprueba con un idioma que la app NO habla: si
    // mañana alguien añade un diccionario a medias, esto tiene que seguir
    // dando inglés hasta que entre en OFRECIDOS.
    expect(idiomaPreferido(["pt-BR", "pt"])).toBe("en");
  });

  it("el español sigue ganando aunque el italiano vaya delante", () => {
    // Sólo porque el navegador los pida en ese orden: gana el primero de la
    // lista que la app ofrezca, y aquí el italiano va antes.
    expect(idiomaPreferido(["it", "es"])).toBe("it");
    expect(idiomaPreferido(["es", "it"])).toBe("es");
  });
});
