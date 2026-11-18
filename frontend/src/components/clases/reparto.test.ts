import { describe, expect, it } from "vitest";
import type { JugadorDeClases } from "../../services/api";
import { repartoDelSalario } from "./reparto";

const conSalario = (salary: number) => ({ salary }) as JugadorDeClases;

describe("la distribución del salario", () => {
  it("suma el salario de cada grupo y reparte el 100 %", () => {
    const { total, partes } = repartoDelSalario([
      {
        clave: "a",
        nombre: "A",
        color: "x",
        jugadores: [conSalario(30), conSalario(25)],
      },
      { clave: "b", nombre: "B", color: "y", jugadores: [conSalario(45)] },
      { clave: "c", nombre: "C", color: "z", jugadores: [] },
    ]);
    expect(total).toBe(100);
    expect(partes.map((p) => p.salario)).toEqual([55, 45, 0]);
    expect(partes.map((p) => Math.round(p.pct * 1e6) / 1e6)).toEqual([
      55, 45, 0,
    ]);
  });

  it("sin salario no divide por cero", () => {
    const { partes } = repartoDelSalario([
      { clave: "a", nombre: "A", color: "x", jugadores: [conSalario(0)] },
    ]);
    expect(partes[0]?.pct).toBe(0);
  });
});
