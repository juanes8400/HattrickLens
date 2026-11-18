import { describe, expect, it } from "vitest";
import type { ClasesDeJugador, JugadorDeClases } from "../../services/api";
import {
  enLista,
  fraseDeEtapa,
  fraseDePropia,
  nombreDeGrupo,
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
    groupIds: {},
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
    classifications: [],
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

describe("Clasificaciones propias", () => {
  const mercado = {
    id: 7,
    classificationName: "Mercado",
    groups: [{ id: 5, groupName: "Vender", color: "red" }],
  };

  it("sin clasificaciones propias salen sólo las tres de la app", () => {
    expect(pertenencias(datos(jugador()), 1)).toHaveLength(3);
  });

  it("una por clasificación, con su nombre", () => {
    const j = jugador({ groupIds: { "7": 5 } });
    const lista = pertenencias(datos(j, { classifications: [mercado] }), 1);
    expect(lista).toHaveLength(4);
    expect(lista?.[3]?.clasificacion).toBe("Mercado");
    expect(lista?.[3]?.frase).toContain("«Vender»");
  });

  it("sin grupo en ella, lo dice", () => {
    const p = fraseDePropia(mercado, jugador());
    expect(p?.grupo).toBe("Sin grupo");
    expect(p?.frase).toContain("«Mercado»");
  });

  it("una clasificación sin grupos todavía no saca línea", () => {
    expect(fraseDePropia({ ...mercado, groups: [] }, jugador())).toBeNull();
  });
});

describe("los nombres de grupo que usa Cambios", () => {
  it("traduce la clave del servidor al nombre de la pantalla", () => {
    expect(nombreDeGrupo("titularidad", "suplencia")).toBe("Suplencia");
    expect(nombreDeGrupo("rentabilidad", "caros")).toBe("Caro");
    expect(nombreDeGrupo("etapa", "declive")).toBe("En declive");
  });
});
