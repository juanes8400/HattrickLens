/** Clases de Jugador (2026-11-16): la plantilla partida de cuatro formas, y
 *  los grupos propios del usuario. Las reglas, en el backend:
 *  `domain/engines/clases_de_jugador.py`. */
import { request } from "./nucleo";

export type Titularidad = "titular" | "suplencia" | "reserva";
export type GrupoDePotencial =
  "consolidados" | "veteranos" | "promesas" | "relleno";
export type EtapaDeCarrera =
  "promesa" | "pico" | "rotacion" | "veterano" | "declive" | "sin_historial";

/** Una casilla de un once. Sin `htPlayerId` es un hueco. */
export interface CasillaDeOnce {
  slot: number;
  /** La casilla sin orden: «keeper», «wingback», «central_defender»… */
  base: string;
  position: string | null;
  label: string | null;
  htPlayerId: number | null;
  rating: number | null;
}

export interface OnceDeFormacion {
  formation: string;
  slots: CasillaDeOnce[];
}

export interface JugadorDeClases {
  htPlayerId: number;
  name: string;
  /** El apellido, para rotular puntos y casillas. */
  shortName: string;
  ageYears: number;
  ageDays: number;
  htms: number;
  htms28: number;
  titularidad: Titularidad;
  potencial: GrupoDePotencial;
  etapa: {
    stage: EtapaDeCarrera;
    /** La confirmó el usuario a mano en la ficha. */
    confirmed: boolean;
    percentile: number | null;
    rising: number;
    falling: number;
    hasSufficientHistory: boolean;
    /** Sólo si su etapa tiene más de 11 y se partió. */
    side: "titular" | "suplente" | null;
  };
  groupId: number | null;
}

export interface GrupoPropio {
  id: number;
  name: string;
  color: string;
}

export interface ClasesDeJugador {
  formations: string[];
  experience: Record<string, number>;
  starters: OnceDeFormacion[];
  substitutes: OnceDeFormacion[];
  medians: { htms: number; htms28: number } | null;
  groups: GrupoPropio[];
  players: JugadorDeClases[];
}

export const apiClases = {
  playerClasses: (teamId: number) =>
    request<ClasesDeJugador>(`/teams/${teamId}/player-classes`),
  createPlayerGroup: (teamId: number, name: string, color: string) =>
    request<GrupoPropio>(`/teams/${teamId}/player-groups`, {
      method: "POST",
      body: JSON.stringify({ name, color }),
    }),
  updatePlayerGroup: (
    teamId: number,
    groupId: number,
    cambio: { name?: string; color?: string },
  ) =>
    request<GrupoPropio>(`/teams/${teamId}/player-groups/${groupId}`, {
      method: "PATCH",
      body: JSON.stringify(cambio),
    }),
  deletePlayerGroup: (teamId: number, groupId: number) =>
    request<{ deleted: number }>(`/teams/${teamId}/player-groups/${groupId}`, {
      method: "DELETE",
    }),
  setPlayerGroup: (
    teamId: number,
    htPlayerId: number,
    groupId: number | null,
  ) =>
    request<{ htPlayerId: number; groupId: number | null }>(
      `/teams/${teamId}/player-groups/members/${htPlayerId}`,
      { method: "PUT", body: JSON.stringify({ groupId }) },
    ),
};
