import { describe, expect, it } from "vitest";
import { economySankeyOption } from "./chartOptions";

type Nodo = {
  name: string;
  itemStyle?: { color?: string };
  label?: { formatter?: () => string };
};

function nodoDelSaldo(income: number, costs: number) {
  const opcion = economySankeyOption(
    [{ label: "Patrocinadores", amount: income }],
    [{ label: "Sueldos", amount: costs }],
    "US$",
  );
  const serie = (opcion.series as { data: Nodo[] }[])[0]!;
  return serie.data.find((n) => n.name === "Saldo de la semana")!;
}

describe("el nodo del saldo dice si la semana gana o pierde", () => {
  it("en rojo y con signo menos cuando se pierde", () => {
    const nodo = nodoDelSaldo(124_000, 565_317);
    expect(nodo.itemStyle?.color).toBe("#e5484d");
    expect(nodo.label?.formatter?.()).toBe("Saldo: −441.317 US$");
  });

  it("en verde y con signo más cuando se gana", () => {
    const nodo = nodoDelSaldo(800_000, 500_000);
    expect(nodo.itemStyle?.color).toBe("#2fbf71");
    expect(nodo.label?.formatter?.()).toBe("Saldo: +300.000 US$");
  });
});
