import { describe, expect, it } from "vitest";
import type { PlayerBalanceRow } from "../../services/api";
import mundo from "./mundo.json";
import {
  SIN_ZONA,
  agruparPorZona,
  colorDelValor,
  decodificar,
  mejoresYPeores,
  naturalEarth,
  paletaDelMapa,
  valorDeLaZona,
  type MundoCrudo,
} from "./zonasDelMapa";

function fila(p: Partial<PlayerBalanceRow>): PlayerBalanceRow {
  return {
    htPlayerId: 1,
    name: "Uno",
    saldo: 100,
    totalCost: 100,
    isSold: true,
    destinationRegion: "it",
    nativeRegion: "co",
    ...p,
  } as PlayerBalanceRow;
}

describe("el mapa de países de Transferencias", () => {
  it("agrupa por zona y manda al círculo lo que no tiene país", () => {
    const zonas = agruparPorZona(
      [
        fila({ htPlayerId: 1, saldo: 300, totalCost: 100 }),
        fila({ htPlayerId: 2, saldo: -100, totalCost: 100 }),
        fila({ htPlayerId: 3, destinationRegion: null }),
        // Una salida sin venta no tiene destino aunque se conozca el club.
        fila({ htPlayerId: 4, isSold: false, destinationRegion: "es" }),
        fila({ htPlayerId: 5, saldo: null }),
      ],
      "destino",
      "absoluto",
    );
    expect(zonas.get("it")).toMatchObject({ n: 2, saldo: 200, coste: 200 });
    expect(zonas.get(SIN_ZONA)?.n).toBe(2);
    expect(zonas.has("es")).toBe(false);
    // Los jugadores, de mejor a peor.
    expect(zonas.get("it")!.jugadores.map((j) => j.id)).toEqual([1, 2]);
  });

  it("el ROI sale de los totales y deja fuera a quien no costó nada", () => {
    const zonas = agruparPorZona(
      [
        fila({ saldo: 300, totalCost: 100 }),
        fila({ saldo: -50, totalCost: 900 }),
        fila({ saldo: 1_000, totalCost: 0 }),
      ],
      "nacionalidad",
      "roi",
    );
    const co = zonas.get("co")!;
    expect(co.n).toBe(2);
    // (300 − 50) ÷ (100 + 900), nunca la media de 200 % y −5,6 %.
    expect(valorDeLaZona(co, "roi")).toBeCloseTo(25);
  });

  it("la tabla: cuatro mejores y cuatro peores con al menos tres", () => {
    const filas = Array.from({ length: 10 }, (_, i) =>
      Array.from({ length: 3 }, () =>
        fila({ destinationRegion: `p${i}`, saldo: i * 10 }),
      ),
    ).flat();
    filas.push(fila({ destinationRegion: "solo", saldo: 99_999 }));
    const tabla = mejoresYPeores(
      agruparPorZona(filas, "destino", "absoluto"),
      "absoluto",
    );
    expect(tabla.map((z) => z?.clave ?? "…")).toEqual([
      "p9",
      "p8",
      "p7",
      "p6",
      "…",
      "p3",
      "p2",
      "p1",
      "p0",
    ]);
  });

  it("el color satura en los extremos y es gris en el cero", () => {
    const paleta = paletaDelMapa(false);
    expect(colorDelValor(0, "roi", paleta)).toBe("rgb(220, 220, 224)");
    expect(colorDelValor(100, "roi", paleta)).toBe(
      colorDelValor(5_000, "roi", paleta),
    );
    expect(colorDelValor(-8_000_000, "absoluto", paleta)).toBe(
      "rgb(209, 56, 61)",
    );
  });

  it("el mapa trae las cuatro británicas por separado y Oceanía junta", () => {
    const zonas = new Set(
      decodificar(mundo as unknown as MundoCrudo).map((z) => z.zona),
    );
    for (const z of ["gb-eng", "gb-sct", "gb-wls", "gb-nir", "oc", "co"])
      expect(zonas.has(z)).toBe(true);
    expect(zonas.has("gb")).toBe(false);
    expect(zonas.has("au")).toBe(false);
    expect(zonas.has("nz")).toBe(false);
  });

  it("Natural Earth deja el meridiano cero en el centro y el norte arriba", () => {
    expect(naturalEarth(0, 0)).toEqual([0, -0]);
    expect(naturalEarth(0, 60)[1]).toBeLessThan(0);
    expect(naturalEarth(90, 0)[0]).toBeGreaterThan(0);
  });
});
