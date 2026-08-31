import { describe, expect, it } from "vitest";
import { compact, dateTime, decimal, number, percent } from "./useFormat";

/** La política numérica de la casa, vigilada.
 *
 *  El módulo declara desde el 2026-08-14 que los miles llevan punto y los
 *  decimales TAMBIÉN punto, sin depender del idioma del navegador. Aun así
 *  ocho sitios formateaban por su cuenta con tres criterios distintos --«es»,
 *  «es-CO» y uno SIN idioma, que usaba el del navegador de quien mirara--, y
 *  `toLocaleString("es", …)` devuelve justo la coma decimal que la política
 *  prohíbe (2026-08-31).
 *
 *  Lo que se fija aquí es que el resultado no lleve nunca una coma.
 */
describe("la política de formato", () => {
  it("los miles van con punto", () => {
    expect(number(1234567)).toBe("1.234.567");
  });

  it("los decimales van con PUNTO, no con coma", () => {
    expect(decimal(3.5)).toBe("3.5");
    expect(percent(12.34)).toBe("12.3%");
    expect(compact(2_400_000)).toBe("2.4 M");
  });

  it("ningún formateador devuelve una coma", () => {
    // La coma es la huella de un `toLocaleString` en español colándose otra vez.
    const muestras = [
      number(1234567),
      decimal(1234.56),
      percent(99.95),
      compact(2_400_000),
      compact(15_300),
      compact(842),
    ];
    for (const s of muestras) expect(s).not.toContain(",");
  });

  it("la fecha con hora no depende del navegador", () => {
    // Con `toLocaleString()` sin idioma esto salía «8/31/2026, 4:12:00 PM»
    // en un navegador en inglés y en español en otro.
    expect(dateTime("2026-08-31T15:45:00Z")).toMatch(/^\d{2}\/\d{2}\/\d{4} \d{2}:\d{2}$/);
  });

  it("un hueco es una raya, nunca una coma suelta", () => {
    expect(dateTime(null)).toBe("—");
    expect(dateTime("")).toBe("—");
  });
});
