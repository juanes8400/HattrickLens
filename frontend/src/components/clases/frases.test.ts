import { describe, expect, it } from "vitest";
import type { ClasesDeJugador, JugadorDeClases } from "../../services/api";
import {
  enLista,
  fraseDeEtapa,
  fraseDeMisGrupos,
  fraseDeRentabilidad,
  fraseDeTitularidad,
  pertenencias,
} from "./frases";

/** Las frases que el usuario aprobó el 2026-11-18, una a una: cada una dice
 *  el grupo y el dato que lo decide, para poder comprobarlo. */

function jugador(cambios: Partial<JugadorDeClases> = {}): JugadorDeClases {
  return {
    htPlayerId: 1,
    name: "Juan Prueba",
    shortName: "Prueba",
    ageYears: 25,
    ageDays: 10,
    htms: 1500,
    htms28: 1800,
    salary: 30000,
    titularidad: "titular",
    rentabilidad: "estrellas",
    etapa: {
      stage: "pico",
      confirmed: false,
      percentile: 72.4,
      rising: 1,
      falling: 0,
      hasSufficientHistory: true,
      side: null,
    },
    groupId: null,
    ...cambios,
  };
}

const casilla = (htPlayerId: number | null, base: string, slot: number) => ({
  slot,
  base,
  position: null,
  label: null,
  htPlayerId,
  rating: null,
});

function datos(j: JugadorDeClases, cambios: Partial<ClasesDeJugador> = {}) {
  return {
    formations: ["4-4-2", "3-5-2"],
    experience: {},
    starters: [
      { formation: "4-4-2", slots: [casilla(1, "inner_midfield", 7)] },
      { formation: "3-5-2", slots: [casilla(1, "winger", 6)] },
    ],
    substitutes: [
      { formation: "4-4-2", slots: [casilla(2, "central_defender", 3)] },
    ],
    medians: { htms28: 1600, salary: 23500 },
    currency: "€",
    groups: [],
    stageRules: {
      youngMaxAge: 21,
      peakMaxAge: 27,
      rotationBelowPercentile: 40,
      splitAbove: 11,
    },
    players: [j],
    ...cambios,
  } as ClasesDeJugador;
}

describe("Titularidad", () => {
  it("el titular dice en qué once y de qué sale", () => {
    const j = jugador();
    const p = fraseDeTitularidad(datos(j), j);
    expect(p.grupo).toBe("Titular");
    expect(p.frase).toContain("de Mediocentro en 4-4-2");
    expect(p.frase).toContain("de Extremo en 3-5-2");
  });

  it("el mismo puesto en dos formaciones se dice una vez", () => {
    const j = jugador();
    const d = datos(j, {
      starters: [
        { formation: "4-4-2", slots: [casilla(1, "inner_midfield", 7)] },
        { formation: "3-5-2", slots: [casilla(1, "inner_midfield", 7)] },
      ],
    });
    expect(fraseDeTitularidad(d, j).frase).toContain(
      `de Mediocentro en ${enLista(["4-4-2", "3-5-2"])}`,
    );
  });

  it("la reserva nombra las formaciones en las que no entra", () => {
    const j = jugador({ titularidad: "reserva" });
    expect(fraseDeTitularidad(datos(j), j).frase).toContain("4-4-2, 3-5-2");
  });

  it("sin experiencia leída pide sincronizar, no inventa", () => {
    const j = jugador();
    const p = fraseDeTitularidad(datos(j, { formations: [] }), j);
    expect(p.frase).toContain("Sincroniza");
  });
});

describe("Rentabilidad deportiva", () => {
  it("dice su valor y la mediana con la que se compara", () => {
    const j = jugador();
    const p = fraseDeRentabilidad(datos(j), j);
    expect(p?.grupo).toBe("Estrella");
    expect(p?.frase).toContain("por encima de la mediana");
  });

  it("justo en la mediana lo dice, en vez de «por encima»", () => {
    const j = jugador({ salary: 23500 });
    expect(fraseDeRentabilidad(datos(j), j)?.frase).toContain("en la mediana");
  });

  it("sin medianas no hay frase", () => {
    const j = jugador();
    expect(fraseDeRentabilidad(datos(j, { medians: null }), j)).toBeNull();
  });
});

describe("Etapa de carrera", () => {
  it("en su pico, con el percentil redondeado", () => {
    const j = jugador();
    expect(fraseDeEtapa(datos(j), j).frase).toContain("percentil 72");
  });

  it("sin historial es provisional y lo dice", () => {
    const j = jugador({
      etapa: { ...jugador().etapa, hasSufficientHistory: false },
    });
    const p = fraseDeEtapa(datos(j), j);
    expect(p.grupo).toContain("provisional");
    expect(p.frase).toContain("otra sincronización");
  });

  it("la confirmada a mano manda sobre todo lo demás", () => {
    const j = jugador({
      etapa: {
        ...jugador().etapa,
        confirmed: true,
        hasSufficientHistory: false,
      },
    });
    expect(fraseDeEtapa(datos(j), j).frase).toContain("confirmada a mano");
  });

  it("si la etapa se partió, dice de qué lado está", () => {
    const j = jugador({ etapa: { ...jugador().etapa, side: "suplente" } });
    expect(fraseDeEtapa(datos(j), j).frase).toContain("lado de suplentes");
  });
});

describe("Mis grupos", () => {
  it("sin grupos creados no sale la línea", () => {
    const j = jugador();
    expect(fraseDeMisGrupos(datos(j), j)).toBeNull();
    expect(pertenencias(datos(j), 1)).toHaveLength(3);
  });

  it("con grupos, dice en cuál está o que en ninguno", () => {
    const grupos = [{ id: 5, groupName: "Cantera", color: "verde" }];
    const dentro = jugador({ groupId: 5 });
    const fuera = jugador();
    expect(
      fraseDeMisGrupos(datos(dentro, { groups: grupos }), dentro)?.frase,
    ).toContain("«Cantera»");
    expect(
      fraseDeMisGrupos(datos(fuera, { groups: grupos }), fuera)?.frase,
    ).toContain("ninguno");
  });
});
