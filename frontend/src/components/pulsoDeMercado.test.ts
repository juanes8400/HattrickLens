import { describe, expect, it } from "vitest";
import { apiladas } from "./SerieConCausas";

/** El pulso de mercado no puede salirse de su carril.
 *
 *  2026-09-01, visto por el usuario en producción: «en Psicología se ven muy
 *  desordenadas las ventas». Cada operación era una cápsula y la pila crecía
 *  sin tope, 7px por operación. En la base real hay un día con CUARENTA
 *  ventas: 280px subiendo, que atraviesan la gráfica entera.
 *
 *  Desde la cuarta venta del mismo día el marcador ya invadía el área de la
 *  línea. En local no se veía porque ahí ningún día pasa de tres.
 */
describe("las cápsulas del pulso de mercado", () => {
  it("mientras caben, se pintan todas", () => {
    expect(apiladas(1, 3)).toEqual({ visibles: 1, resto: 0 });
    expect(apiladas(3, 3)).toEqual({ visibles: 3, resto: 0 });
  });

  it("un día vacío no pinta nada", () => {
    expect(apiladas(0, 3)).toEqual({ visibles: 0, resto: 0 });
  });

  it("el día de las cuarenta ventas se queda dentro del carril", () => {
    const { visibles, resto } = apiladas(40, 3);
    expect(visibles).toBe(2);
    expect(resto).toBe(38);
    // Lo que importa de verdad: la altura ocupada.
    expect(visibles * 7).toBeLessThanOrEqual(3 * 7);
  });

  it("ninguna cantidad, por grande que sea, se sale", () => {
    for (const n of [4, 5, 12, 40, 500]) {
      const { visibles } = apiladas(n, 3);
      expect(visibles).toBeLessThan(3);
    }
  });

  it("no se pierde ni se inventa ninguna operación", () => {
    for (const n of [0, 1, 3, 4, 40]) {
      const { visibles, resto } = apiladas(n, 3);
      expect(visibles + resto).toBe(n);
    }
  });
});
