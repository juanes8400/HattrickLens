import { describe, expect, it } from "vitest";
import type { ClasesDeJugador, JugadorDeClases } from "../../services/api";
import { clasificacionesElegibles, idsDelFiltro, SIN_FILTRO } from "./filtro";

function jugador(
  htPlayerId: number,
  cambios: Partial<JugadorDeClases> = {},
): JugadorDeClases {
  return {
    htPlayerId,
    name: `J${htPlayerId}`,
    shortName: `J${htPlayerId}`,
    ageYears: 25,
    ageDays: 0,
    htms: 1000,
    htms28: 1000,
    salary: 1000,
    titularidad: "titular",
    rentabilidad: "estrellas",
    etapa: {
      stage: "pico",
      confirmed: false,
      percentile: 50,
      rising: 0,
      falling: 0,
      hasSufficientHistory: true,
      side: null,
    },
    groupIds: {},
    ...cambios,
  };
}

const datos = (classifications: ClasesDeJugador["classifications"] = []) =>
  ({
    formations: ["4-4-2"],
    experience: {},
    starters: [],
    substitutes: [],
    medians: { htms28: 1000, salary: 1000 },
    currency: "€",
    classifications,
    stageRules: {
      youngMaxAge: 21,
      peakMaxAge: 27,
      rotationBelowPercentile: 40,
      splitAbove: 11,
    },
    players: [
      jugador(1),
      jugador(2, { rentabilidad: "caros", groupIds: { "3": 9 } }),
      jugador(3, { rentabilidad: "caros" }),
    ],
  }) as ClasesDeJugador;

describe("el filtro clasificación → grupo", () => {
  it("sin elegir nada no filtra", () => {
    expect(idsDelFiltro(datos(), SIN_FILTRO)).toBeNull();
    expect(
      idsDelFiltro(datos(), { clasificacion: "rentabilidad", grupo: "" }),
    ).toBeNull();
  });

  it("con un grupo deja pasar sólo a los suyos", () => {
    const ids = idsDelFiltro(datos(), {
      clasificacion: "rentabilidad",
      grupo: "caros",
    });
    expect([...(ids ?? [])].sort()).toEqual([2, 3]);
  });

  it("una elección guardada que ya no existe no vacía la tabla", () => {
    expect(
      idsDelFiltro(datos(), { clasificacion: "propia-3", grupo: "9" }),
    ).toBeNull();
  });

  it("una clasificación propia sólo se ofrece si tiene grupos", () => {
    const claves = (d: ClasesDeJugador) =>
      clasificacionesElegibles(d).map((c) => c.clave);
    const sinGrupos = datos([
      { id: 3, classificationName: "Mercado", groups: [] },
    ]);
    expect(claves(sinGrupos)).not.toContain("propia-3");
    const conGrupo = datos([
      {
        id: 3,
        classificationName: "Mercado",
        groups: [{ id: 9, groupName: "Vender", color: "red" }],
      },
    ]);
    expect(claves(conGrupo)).toContain("propia-3");
    expect(
      idsDelFiltro(conGrupo, { clasificacion: "propia-3", grupo: "9" }),
    ).toEqual(new Set([2]));
  });
});
