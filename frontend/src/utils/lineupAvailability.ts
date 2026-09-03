export const MINIMUM_LINEUP_PLAYERS = 11;

export interface LineupExcludedPlayer {
  htPlayerId: number;
  player: string;
}

export interface LineupExclusionState {
  players: LineupExcludedPlayer[];
  warning: string | null;
}

interface PlayerAvailability {
  htPlayerId: number;
  injuryLevel: number;
}

/**
 * Los mismos jugadores que puede usar el optimizador.
 *
 * `injuryLevel === 0` significa magullado y todavía puede jugar; solo una
 * lesión de una semana o más deja al jugador fuera. Mantener esa frontera
 * aquí evita que el navegador crea que hay once mientras el motor solo ve
 * diez.
 */
export function availableLineupPlayerIds(
  players: readonly PlayerAvailability[],
): Set<number> {
  return new Set(
    players
      .filter((player) => player.injuryLevel < 1)
      .map((player) => player.htPlayerId),
  );
}

export function availablePlayersAfterExclusions(
  availableIds: ReadonlySet<number>,
  excluded: readonly LineupExcludedPlayer[],
): number {
  const excludedAvailable = new Set(
    excluded
      .map((player) => player.htPlayerId)
      .filter((playerId) => availableIds.has(playerId)),
  );
  return availableIds.size - excludedAvailable.size;
}

/**
 * Intenta sacar a un jugador sin permitir nunca que el reparto baje de once.
 * El aviso forma parte del mismo estado que la lista: así dos clics rápidos
 * tampoco pueden calcular ambos contra una lista vieja y saltarse el límite.
 */
export function tryExcludeLineupPlayer(
  current: LineupExclusionState,
  candidate: LineupExcludedPlayer,
  availableIds: ReadonlySet<number>,
): LineupExclusionState {
  if (
    current.players.some((player) => player.htPlayerId === candidate.htPlayerId)
  ) {
    return current;
  }

  const remaining = availablePlayersAfterExclusions(
    availableIds,
    current.players,
  );
  if (
    availableIds.has(candidate.htPlayerId) &&
    remaining <= MINIMUM_LINEUP_PLAYERS
  ) {
    return {
      ...current,
      warning: `No puedes sacar a ${candidate.player}: solo quedan 11 jugadores disponibles y la alineación necesita 11.`,
    };
  }

  return {
    players: [...current.players, candidate],
    warning: null,
  };
}

export function restoreLineupPlayer(
  current: LineupExclusionState,
  htPlayerId: number,
): LineupExclusionState {
  return {
    players: current.players.filter(
      (player) => player.htPlayerId !== htPlayerId,
    ),
    warning: null,
  };
}
