import { afterAll, beforeAll, describe, expect, it } from "vitest";
import i18n from "../i18n";
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

describe("ningún enlace apunta a un nodo que no existe", () => {
  /**
   * 2026-09-26, fallo reportado: en inglés el diagrama se rompía.
   *
   * El nodo de la caja se creaba traducido (`tx("Caja")` → «Cash») y los dos
   * enlaces que lo tocan apuntaban al literal «Caja». En español las dos
   * cadenas son la misma palabra y coincidían de casualidad; en inglés el
   * enlace buscaba un nodo que no estaba y ECharts se comía el tramo.
   *
   * Esto lo comprueba sin saber nada de idiomas: sea cual sea el nombre que
   * salga del diccionario, todo `source` y todo `target` tienen que existir
   * en la lista de nodos.
   */
  // EN INGLÉS, que es donde el fallo aparecía. En español las dos cadenas
  // que no cuadraban son la misma palabra, así que una prueba en español
  // habría pasado con el error delante.
  beforeAll(async () => {
    await i18n.changeLanguage("en");
  });
  afterAll(async () => {
    await i18n.changeLanguage("es");
  });

  const enlacesCuadran = (income: number, costs: number) => {
    const opcion = economySankeyOption(
      [{ label: "Patrocinadores", amount: income }],
      [{ label: "Sueldos", amount: costs }],
      "US$",
    );
    const serie = (
      opcion.series as {
        data: { name: string }[];
        links: { source: string; target: string }[];
      }[]
    )[0]!;
    const nodos = new Set(serie.data.map((n) => n.name));
    return serie.links.flatMap((l) =>
      [l.source, l.target].filter((punta) => !nodos.has(punta)),
    );
  };

  it("cuando la semana gana y el sobrante va a la caja", () => {
    expect(enlacesCuadran(800_000, 500_000)).toEqual([]);
  });

  it("cuando la semana pierde y la caja cubre el déficit", () => {
    expect(enlacesCuadran(124_000, 565_317)).toEqual([]);
  });

  it("cuando la semana queda en cero y no hay caja que dibujar", () => {
    expect(enlacesCuadran(500_000, 500_000)).toEqual([]);
  });
});
