import { describe, expect, it } from "vitest";
import { proximaJornada } from "./SimularJornada";
import type { League } from "../services/api";

/**
 * Qué jornada se ofrece simular, y sobre todo CUÁNDO no hay ninguna.
 *
 * 2026-09-20: el usuario preguntó qué enseña esta pantalla con la liga
 * terminada. Enseñaba nada: el panel devolvía `null` y, como tiene pestaña
 * propia, la pantalla se quedaba en blanco. Lo que se fija aquí es que los
 * dos estados vacíos se reconozcan, para que la pantalla pueda contarlos en
 * vez de desaparecer.
 */

type Fixture = League["fixtures"][number];

const cruce = (
  matchRound: number,
  home: string,
  away: string,
  played = false,
): Fixture => ({
  date: "2026-09-13",
  matchRound,
  home,
  away,
  played,
  score: played ? "1-1" : null,
});

describe("proximaJornada", () => {
  it("elige la jornada pendiente más temprana", () => {
    const j = proximaJornada([
      cruce(1, "A", "B", true),
      cruce(3, "A", "C"),
      cruce(2, "B", "C"),
      cruce(2, "D", "E"),
    ]);
    expect(j?.numero).toBe(2);
    expect(j?.cruces).toHaveLength(2);
  });

  it("no es «la jugada + 1»: una jornada aplazada manda", () => {
    // La 2 se aplazó y la 3 ya se jugó. Lo siguiente que hay que simular es
    // la 2, no la 4.
    const j = proximaJornada([
      cruce(1, "A", "B", true),
      cruce(2, "C", "D"),
      cruce(3, "A", "C", true),
      cruce(4, "B", "D"),
    ]);
    expect(j?.numero).toBe(2);
  });

  it("con la temporada terminada no hay jornada que ofrecer", () => {
    const j = proximaJornada([
      cruce(1, "A", "B", true),
      cruce(2, "C", "D", true),
    ]);
    expect(j).toBeNull();
  });

  it("en pretemporada, sin calendario, tampoco", () => {
    expect(proximaJornada([])).toBeNull();
  });

  it("sólo trae los cruces de esa jornada, no los de las siguientes", () => {
    const j = proximaJornada([
      cruce(5, "A", "B"),
      cruce(5, "C", "D"),
      cruce(6, "A", "C"),
    ]);
    expect(j?.numero).toBe(5);
    expect(j?.cruces.map((c) => `${c.local}-${c.visitante}`)).toEqual([
      "A-B",
      "C-D",
    ]);
  });

  it("el índice apunta al cruce original, no a su posición en la jornada", () => {
    // De ese índice depende que cada marcador escrito vaya a su partido: si
    // se renumerara, dos jornadas distintas compartirían casillas.
    const j = proximaJornada([
      cruce(1, "A", "B", true),
      cruce(1, "C", "D", true),
      cruce(2, "A", "C"),
    ]);
    expect(j?.cruces[0].indice).toBe(2);
  });
});
