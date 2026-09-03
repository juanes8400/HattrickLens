import { describe, expect, it } from "vitest";
import {
  availableLineupPlayerIds,
  availablePlayersAfterExclusions,
  restoreLineupPlayer,
  tryExcludeLineupPlayer,
  type LineupExclusionState,
} from "./lineupAvailability";

const players = (count: number) =>
  Array.from({ length: count }, (_, index) => ({
    htPlayerId: index + 1,
    injuryLevel: -1,
  }));

describe("límite de exclusiones de Alineación", () => {
  it("permite sacar uno de doce y quedarse exactamente con once", () => {
    const result = tryExcludeLineupPlayer(
      { players: [], warning: null },
      { htPlayerId: 12, player: "Jugador doce" },
      availableLineupPlayerIds(players(12)),
    );

    expect(result.players.map((player) => player.htPlayerId)).toEqual([12]);
    expect(result.warning).toBeNull();
  });

  it("bloquea la exclusión que dejaría solo diez y explica el motivo", () => {
    const current: LineupExclusionState = {
      players: [{ htPlayerId: 12, player: "Jugador doce" }],
      warning: null,
    };

    const result = tryExcludeLineupPlayer(
      current,
      { htPlayerId: 11, player: "Jugador once" },
      availableLineupPlayerIds(players(12)),
    );

    expect(result.players).toEqual(current.players);
    expect(result.warning).toContain("Jugador once");
    expect(result.warning).toContain("solo quedan 11");
  });

  it("cuenta como no disponibles a los lesionados, pero no a los magullados", () => {
    const ids = availableLineupPlayerIds([
      ...players(10),
      { htPlayerId: 11, injuryLevel: 0 },
      { htPlayerId: 12, injuryLevel: 1 },
    ]);

    expect(ids.has(11)).toBe(true);
    expect(ids.has(12)).toBe(false);
    expect(ids.size).toBe(11);
  });

  it("no descuenta dos veces un mismo identificador excluido", () => {
    const ids = availableLineupPlayerIds(players(12));
    expect(
      availablePlayersAfterExclusions(ids, [
        { htPlayerId: 12, player: "Doce" },
        { htPlayerId: 12, player: "Doce repetido" },
      ]),
    ).toBe(11);
  });

  it("al devolver un jugador quita el aviso del límite", () => {
    const result = restoreLineupPlayer(
      {
        players: [{ htPlayerId: 12, player: "Doce" }],
        warning: "No puedes sacar a Once",
      },
      12,
    );

    expect(result).toEqual({ players: [], warning: null });
  });
});
