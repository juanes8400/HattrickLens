import { describe, expect, it } from "vitest";
import type {
  ClasesDeJugador,
  JugadorDeClases,
  TeamOverview,
  TeamOverviewGroup,
} from "../../services/api";
import { clasificaciones } from "../clases/clasificaciones";
import {
  pestanaComparada,
  pestanaDeUnGrupo,
  pestanaEnRejilla,
  seriesDeLaPlantilla,
  type Poblacion,
} from "./graficasPorGrupo";

/** «Mirar a» (6.10.0, 2026-11-17): qué se dibuja con uno o varios grupos. */
const serie = (key: string, values: (number | null)[]) => ({
  key,
  label: key.toUpperCase(),
  values,
  display: "level" as const,
});
const tab = (
  key: string,
  charts: { key: string; series: ReturnType<typeof serie>[]; band?: boolean }[],
): TeamOverviewGroup => ({
  key,
  label: key,
  chart: "line",
  pitch: [],
  specialRoles: [],
  note: "nota del servidor",
  weeks: ["83-10", "83-11"],
  metrics: [],
  charts: charts.map((c) => ({
    key: c.key,
    title: `título ${c.key}`,
    scaleMin: 0,
    scaleMax: 20,
    band: c.band ?? false,
    series: c.series,
  })),
});

const habilidades = tab("skills", [
  {
    key: "offensive",
    series: [serie("winger", [5, 5]), serie("passing", [8, 9])],
  },
]);
const mercado = tab("market", [
  {
    key: "salary",
    band: true,
    series: [serie("salary", [100, 110]), serie("salary_top", [200, 210])],
  },
  {
    key: "tsi_total",
    band: true,
    series: [serie("tsi_total", [9, 9]), serie("tsi_total_top", [7, 7])],
  },
]);
const htms = tab("htms", [
  {
    key: "htms_avg",
    band: true,
    series: [serie("htms", [1500, 1510]), serie("htms28", [1600, 1610])],
  },
  { key: "htms_total", series: [serie("htms_total", [30000, 30100])] },
]);
const resumen = { groups: [habilidades, mercado, htms] } as TeamOverview;
const plantilla = seriesDeLaPlantilla(resumen);

const gangas: Poblacion & { serie: NonNullable<Poblacion["serie"]> } = {
  clave: "gangas",
  nombre: "Gangas",
  color: "#0f0",
  serie: {
    weeks: ["83-10", "83-11"],
    counts: [1, 2],
    fields: {
      winger: [3, 4],
      passing: [3, 5],
      salary: [50, 60],
      tsi_total: [2, 3],
      htms: [900, 950],
      htms28: [1700, 1750],
      htms_total: [900, 1900],
    },
  },
};
const estrellas: Poblacion = {
  ...gangas,
  clave: "estrellas",
  nombre: "Estrellas",
  color: "#00f",
  serie: { ...gangas.serie, counts: [6, 6] },
};
const todos: Poblacion = {
  clave: "plantilla",
  nombre: "Plantilla entera",
  serie: null,
};

describe("seriesDeLaPlantilla", () => {
  it("deja fuera las del once de más TSI", () => {
    expect(plantilla.salary).toEqual([100, 110]);
    expect(plantilla).not.toHaveProperty("salary_top");
  });
});

describe("un grupo", () => {
  it("en Salario y TSI, el grupo contra la plantilla entera en gris", () => {
    const p = pestanaDeUnGrupo(mercado, gangas, plantilla);
    const [sueldo, suma] = p.charts;
    expect(
      sueldo?.series.map((s) => [s.name, s.values, !!s.reference]),
    ).toEqual([
      ["Gangas", [50, 60], false],
      ["Plantilla entera", [100, 110], true],
    ]);
    expect(sueldo?.band).toBe(true);
    // La suma de cuatro contra la de veinte no es una brecha.
    expect(suma?.band).toBe(false);
    expect(p.filas).toEqual([{ conteos: [1, 2] }]);
  });

  it("en HTMS, la suma lleva el nombre del grupo", () => {
    const p = pestanaDeUnGrupo(htms, gangas, plantilla);
    expect(p.charts[1]?.title).toBe("HTMS sumado del grupo");
    expect(p.charts[1]?.series[0]?.name).toBe("Gangas");
    expect(p.charts[0]?.series.map((s) => s.values)).toEqual([
      [900, 950],
      [1700, 1750],
    ]);
  });
});

describe("la rejilla: una forma fija (2026-11-18)", () => {
  it("en Habilidades, una gráfica por dato y en todas una línea por lo marcado", () => {
    const uno = pestanaEnRejilla(habilidades, [estrellas], plantilla);
    const tres = pestanaEnRejilla(
      habilidades,
      [todos, estrellas, gangas],
      plantilla,
    );
    // Marcar más grupos no cambia cuántas gráficas hay: añade líneas.
    expect(uno.rejilla).toBe(true);
    expect(uno.charts.map((c) => c.title)).toEqual(["WINGER", "PASSING"]);
    expect(tres.charts.map((c) => c.title)).toEqual(["WINGER", "PASSING"]);
    expect(uno.charts.every((c) => c.series.length === 1)).toBe(true);
    expect(tres.charts.every((c) => c.series.length === 3)).toBe(true);
    expect(tres.charts[0]?.series[0]?.reference).toBe(true);
  });

  it("con sólo la plantilla, la misma rejilla con su línea gris", () => {
    const p = pestanaEnRejilla(habilidades, [todos], plantilla);
    expect(p.rejilla).toBe(true);
    expect(p.charts.map((c) => c.title)).toEqual(["WINGER", "PASSING"]);
    expect(p.charts.every((c) => c.series.length === 1)).toBe(true);
  });

  it("con la plantilla marcada, Salario y TSI llevan también los 11 mejores", () => {
    const sola = pestanaEnRejilla(mercado, [todos], plantilla);
    expect(sola.charts[0]?.series.map((s) => s.name)).toEqual([
      "Plantilla entera",
      "SALARY_TOP",
    ]);
    const sinPlantilla = pestanaEnRejilla(mercado, [estrellas], plantilla);
    expect(
      sinPlantilla.charts[0]?.series.some((s) => s.name === "SALARY_TOP"),
    ).toBe(false);
  });

  it("en Salario y TSI, una gráfica por medida, igual con uno que con dos", () => {
    const uno = pestanaEnRejilla(mercado, [estrellas], plantilla);
    const dos = pestanaEnRejilla(mercado, [estrellas, gangas], plantilla);
    expect(uno.charts.map((c) => c.key)).toEqual(dos.charts.map((c) => c.key));
    expect(dos.charts.every((c) => c.series.length === 2)).toBe(true);
  });
});

describe("varios grupos", () => {
  it("en Habilidades, un dato cada vez y una línea por grupo", () => {
    const p = pestanaComparada(
      habilidades,
      [todos, estrellas, gangas],
      plantilla,
      "passing",
    );
    expect(p.charts).toHaveLength(1);
    expect(p.charts[0]?.title).toBe("PASSING");
    expect(p.charts[0]?.series.map((s) => [s.name, !!s.reference])).toEqual([
      ["Plantilla entera", true],
      ["Estrellas", false],
      ["Gangas", false],
    ]);
    // Una fila de «en la media» por grupo, no por la plantilla.
    expect(p.filas).toEqual([
      { conteos: [6, 6], color: "#00f" },
      { conteos: [1, 2], color: "#0f0" },
    ]);
  });

  it("cada grupo lleva sus propios conteos para puntear sus saltos", () => {
    const p = pestanaComparada(
      habilidades,
      [estrellas, gangas],
      plantilla,
      "winger",
    );
    expect(p.charts[0]?.series.map((s) => s.conteos)).toEqual([
      [6, 6],
      [1, 2],
    ]);
  });

  it("en HTMS, hoy y a los 28 van en gráficas aparte, sin sombreado", () => {
    const p = pestanaComparada(htms, [estrellas, gangas], plantilla, "winger");
    expect(p.charts.map((c) => c.title)).toEqual([
      "HTMS",
      "HTMS28",
      "HTMS sumado",
    ]);
    expect(p.charts.every((c) => !c.band)).toBe(true);
  });

  it("en Salario y TSI, nada del once de más TSI", () => {
    const p = pestanaComparada(mercado, [todos, gangas], plantilla, "winger");
    expect(p.charts.map((c) => c.key)).toEqual(["salary", "tsi_total"]);
  });
});

describe("clasificaciones", () => {
  const jugador = (
    id: number,
    extra: Partial<JugadorDeClases>,
  ): JugadorDeClases =>
    ({
      htPlayerId: id,
      shortName: `J${id}`,
      ageYears: 25,
      ageDays: 0,
      titularidad: "titular",
      rentabilidad: "gangas",
      groupIds: {},
      etapa: { stage: "pico", side: null },
      ...extra,
    }) as JugadorDeClases;
  const datos = {
    classifications: [],
    players: [
      jugador(1, {}),
      jugador(2, { rentabilidad: "estrellas", titularidad: "reserva" }),
    ],
  } as unknown as ClasesDeJugador;

  it("cada jugador cae en un solo grupo de cada clasificación", () => {
    for (const c of clasificaciones(datos)) {
      const ids = c.grupos.flatMap((g) => g.jugadores.map((j) => j.htPlayerId));
      expect(ids.sort()).toEqual([1, 2]);
    }
  });

  it("sin clasificaciones propias, sólo están las tres de la app", () => {
    expect(clasificaciones(datos).map((c) => c.clave)).toEqual([
      "rentabilidad",
      "titularidad",
      "etapa",
    ]);
  });
});
