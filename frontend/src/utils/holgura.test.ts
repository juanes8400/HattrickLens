import { describe, expect, it } from "vitest";
import { holgura } from "./holgura";

describe("la holgura para vender", () => {
  it("es partidos menos veces en venta", () => {
    expect(holgura(23, 1)).toBe(22);
    expect(holgura(4, 4)).toBe(0);
  });

  it("sin el número de Hattrick no se inventa", () => {
    expect(holgura(null, 2)).toBeNull();
    expect(holgura(undefined, 0)).toBeNull();
  });
});
