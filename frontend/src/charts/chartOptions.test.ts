import { describe, expect, it } from "vitest";
import { bandBetween } from "./chartOptions";

/** La banda son dos series apiladas: una base invisible y encima el hueco,
 *  que es la única con relleno. Lo que se comprueba aquí es que base+hueco
 *  reconstruye siempre la línea de arriba, sea cual sea el orden. */
describe("bandBetween", () => {
  const valores = (serie: Record<string, unknown>) =>
    serie.data as (number | null)[];

  it("apila desde la línea de abajo hasta la de arriba", () => {
    const [base, hueco] = bandBetween([10, 20, 30], [15, 25, 35]);
    expect(valores(base!)).toEqual([10, 20, 30]);
    expect(valores(hueco!)).toEqual([5, 5, 5]);
  });

  it("sigue cubriendo el hueco real cuando las líneas se cruzan", () => {
    // Punto 1: la primera va por debajo. Punto 2: por encima. La banda no se
    // invierte — la base baja al mínimo de cada semana.
    const [base, hueco] = bandBetween([10, 40], [15, 25]);
    expect(valores(base!)).toEqual([10, 25]);
    expect(valores(hueco!)).toEqual([5, 15]);
  });

  it("deja hueco en la banda si falta cualquiera de las dos lecturas", () => {
    const [base, hueco] = bandBetween([null, 20, 30], [15, null, 35]);
    expect(valores(base!)).toEqual([null, null, 30]);
    expect(valores(hueco!)).toEqual([null, null, 5]);
  });

  it("no pinta ni línea ni símbolo: solo el relleno del hueco", () => {
    const [base, hueco] = bandBetween([10], [20]);
    expect(base!.areaStyle).toBeUndefined();
    expect(hueco!.areaStyle).toBeDefined();
    expect(base!.stack).toBe(hueco!.stack);
  });
});
