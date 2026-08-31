import { describe, expect, it } from "vitest";
import { estadoDeAlertas } from "../utils/alertas";

/**
 * Cero alertas y cero respuesta no son lo mismo.
 *
 * El panel del Panel recibía `data ?? []` y no se enteraba de si la petición
 * había fallado, así que con las alertas caídas afirmaba «Nada requiere tu
 * atención» a alguien con un jugador lesionado y la caja en déficit
 * (2026-08-31, reproducido tumbando esa petición a propósito).
 *
 * Una tranquilidad falsa es peor que un hueco declarado, y es el mismo
 * principio que el proyecto ya aplica a los salarios y a los techos juveniles.
 */
describe("qué enseña el panel de alertas", () => {
  it("un fallo NUNCA se cuenta como que no hay nada", () => {
    expect(estadoDeAlertas({ loading: false, failed: true, cuantas: 0 })).toBe("fallo");
  });

  it("el fallo manda aunque hubiera alertas viejas en memoria", () => {
    expect(estadoDeAlertas({ loading: false, failed: true, cuantas: 8 })).toBe("fallo");
  });

  it("sin fallo y sin alertas sí se puede tranquilizar", () => {
    expect(estadoDeAlertas({ loading: false, failed: false, cuantas: 0 })).toBe("vacio");
  });

  it("con alertas, se listan", () => {
    expect(estadoDeAlertas({ loading: false, failed: false, cuantas: 3 })).toBe("lista");
  });

  it("mientras carga no se afirma nada", () => {
    expect(estadoDeAlertas({ loading: true, failed: false, cuantas: 0 })).toBe("cargando");
    expect(estadoDeAlertas({ loading: true, failed: true, cuantas: 0 })).toBe("cargando");
  });
});
