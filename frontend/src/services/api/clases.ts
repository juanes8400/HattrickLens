/** Clases de Jugador (2026-11-16): la plantilla partida de cuatro formas, y
 *  los grupos propios del usuario. Las reglas, en el backend:
 *  `domain/engines/clases_de_jugador.py`. */
import { request } from "./nucleo";

export type Titularidad = "titular" | "suplencia" | "reserva";
export type GrupoDeRentabilidad =
  "estrellas" | "gangas" | "caros" | "economicos";
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
  /** Sueldo semanal, en la moneda del equipo (`currency`). */
  salary: number;
  titularidad: Titularidad;
  rentabilidad: GrupoDeRentabilidad;
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
  /** Su grupo en cada clasificación propia: id de clasificación (en
   *  texto, como llega en JSON) → id de grupo. Sin entrada, «Sin grupo». */
  groupIds: Record<string, number>;
}

export interface GrupoPropio {
  id: number;
  /** Se llama así, y no `name`, para que el servidor no lo traduzca. */
  groupName: string;
  color: string;
}

/** Una clasificación propia, con sus grupos (2026-11-18). Dentro de cada
 *  una, un jugador está en un solo grupo. */
export interface ClasificacionPropia {
  id: number;
  /** Tampoco `name`: lo escribe el usuario y no se traduce. */
  classificationName: string;
  groups: GrupoPropio[];
}

/** Los cortes de la Etapa de carrera, tal como los usa el motor. */
export interface ReglasDeEtapa {
  youngMaxAge: number;
  peakMaxAge: number;
  rotationBelowPercentile: number;
  /** Una etapa con más jugadores que esto se parte en titulares y suplentes. */
  splitAbove: number;
}

export interface ClasesDeJugador {
  formations: string[];
  experience: Record<string, number>;
  starters: OnceDeFormacion[];
  substitutes: OnceDeFormacion[];
  /** Las medianas de la Rentabilidad deportiva; el sueldo, en `currency`. */
  medians: { htms28: number; salary: number } | null;
  currency: string;
  classifications: ClasificacionPropia[];
  stageRules: ReglasDeEtapa;
  players: JugadorDeClases[];
}

export const apiClases = {
  playerClasses: (teamId: number) =>
    request<ClasesDeJugador>(`/teams/${teamId}/player-classes`),
  playerClassChanges: (teamId: number) =>
    request<CambiosDeClase>(`/teams/${teamId}/player-classes/changes`),
  createPlayerClassification: (teamId: number, name: string) =>
    request<{ id: number; classificationName: string }>(
      `/teams/${teamId}/player-classifications`,
      { method: "POST", body: JSON.stringify({ name }) },
    ),
  renamePlayerClassification: (
    teamId: number,
    classificationId: number,
    name: string,
  ) =>
    request<{ id: number; classificationName: string }>(
      `/teams/${teamId}/player-classifications/${classificationId}`,
      { method: "PATCH", body: JSON.stringify({ name }) },
    ),
  deletePlayerClassification: (teamId: number, classificationId: number) =>
    request<{ deleted: number }>(
      `/teams/${teamId}/player-classifications/${classificationId}`,
      { method: "DELETE" },
    ),
  createPlayerGroup: (
    teamId: number,
    classificationId: number,
    name: string,
    color: string,
  ) =>
    request<GrupoPropio>(`/teams/${teamId}/player-groups`, {
      method: "POST",
      body: JSON.stringify({ name, color, classificationId }),
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
    classificationId: number,
    groupId: number | null,
  ) =>
    request<{
      htPlayerId: number;
      classificationId: number;
      groupId: number | null;
    }>(`/teams/${teamId}/player-groups/members/${htPlayerId}`, {
      method: "PUT",
      body: JSON.stringify({ classificationId, groupId }),
    }),
};

/** Quién cambió de clase desde la sincronización anterior (2026-11-18). */
export interface CambioDeClase {
  htPlayerId: number;
  /** `playerName` y no `name`: el servidor traduce los `name`. */
  playerName: string;
  classification: "titularidad" | "rentabilidad" | "etapa";
  before: string;
  after: string;
}

export interface CambiosDeClase {
  syncId: number | null;
  /** Null si todavía no hay una lectura anterior con la que comparar. */
  previousSyncId: number | null;
  changes: CambioDeClase[];
}
