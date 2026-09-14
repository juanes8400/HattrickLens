import { describe, expect, it } from "vitest";
import { chiCuadrado, gammaP } from "./chiCuadrado";

describe("gamma incompleta", () => {
  it("coincide con valores de referencia", () => {
    // P(1, x) = 1 − e^−x.
    expect(gammaP(1, 2)).toBeCloseTo(1 - Math.exp(-2), 10);
    // Chi-cuadrado con 1 gl: P(0,5; 3,841/2) ≈ 0,95.
    expect(gammaP(0.5, 3.841459 / 2)).toBeCloseTo(0.95, 5);
  });
});

describe("chi-cuadrado de independencia", () => {
  it("reproduce un ejemplo de libro", () => {
    // 2×2: [[10, 20], [30, 40]] → χ² ≈ 0,7937, gl = 1, p ≈ 0,373.
    const r = chiCuadrado([
      [10, 20],
      [30, 40],
    ])!;
    expect(r.chi2).toBeCloseTo(0.7937, 3);
    expect(r.gradosDeLibertad).toBe(1);
    expect(r.p).toBeCloseTo(0.373, 3);
  });

  it("una tabla sin relación da p = 1", () => {
    const r = chiCuadrado([
      [2, 4],
      [1, 2],
    ])!;
    expect(r.chi2).toBeCloseTo(0, 10);
    expect(r.p).toBeCloseTo(1, 10);
  });

  it("ignora filas y columnas vacías", () => {
    const r = chiCuadrado([
      [10, 0, 20],
      [0, 0, 0],
      [30, 0, 40],
    ])!;
    expect(r.gradosDeLibertad).toBe(1);
  });

  it("sin dos filas con datos no hay prueba", () => {
    expect(chiCuadrado([[1, 2]])).toBeNull();
  });
});
