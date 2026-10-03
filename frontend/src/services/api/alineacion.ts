/** La alineacion.
 *
 *  Sale de partir `services/api.ts`, que tenia 4147 lineas y se leia entero
 *  en cada cambio del frontend. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../services/api"` sigue valiendo igual.
 */
import { request } from "./nucleo";

/**
 * Comparación por LÍNEA entre quién jugó el último partido y quién pondría
 * hoy el optimizador. Por línea y no por puesto exacto porque el optimizador
 * asigna "defensa central" sin decidir el lado: comparar "central derecho"
 * contra "central" produciría desacuerdos falsos.
 */
export interface HindsightUsedPlayer {
  player: string;
  htPlayerId: number;
  positionLabel: string;
  playedMinutes: number;
  /** `null` mientras el partido no se haya jugado: no hay nota todavía. */
  rating: number | null;
  /** El optimizador también lo pondría en esta línea. */
  alsoProposed: boolean;
}

export interface HindsightProposedPlayer {
  player: string;
  htPlayerId: number;
  rating: number;
}

export interface HindsightLine {
  key: string;
  label: string;
  used: HindsightUsedPlayer[];
  /** A quién pondría el optimizador en esta línea y no usaste ahí. */
  proposedInstead: HindsightProposedPlayer[];
  usedCount: number;
  agreedCount: number;
}

export interface LineupHindsight {
  matchId: number | null;
  matchLabel: string | null;
  playedAt: string | null;
  proposedFormation: string | null;
  agreementCount: number;
  comparableCount: number;
  lines: HindsightLine[];
  notes: string[];
}

export interface Lineup {
  /** Cuántos jugadores podía considerar el motor. Está presente también en
   *  la respuesta vacía que devuelve una plantilla con menos de once. */
  availableCount?: number;
  requiredCount?: number;
  /** Explicación legible cuando no existe un once completo que devolver. */
  warning?: string | null;
  /** Función objetivo usada para escoger conjuntamente once y órdenes. */
  optimizationObjective?: {
    key: string;
    label: string;
    value: number;
  };
  /** Cuántos de cada línea juegan por dentro; el resto va a las bandas. El
   *  nombre de la formación no lo dice. */
  centralDefenders: number;
  innerMidfielders: number;
  /** Los repartos legales de esa formación, que son los que ofrece el
   *  selector. */
  centralDefenderOptions: number[];
  innerMidfielderOptions: number[];
  formation: string;
  totalRating: number;
  formationRanking: Record<string, number>;
  lineup: {
    slot: number;
    /** La posicion CON su orden individual: "wingback_offensive". */
    position: string;
    label: string;
    player: string;
    htPlayerId: number;
    rating: number;
    /** Orden individual elegida por el optimizador. */
    behaviour: string;
    behaviourLabel: string;
    /** La casilla de la formacion, sin la orden. */
    basePosition: string;
    /** True cuando la orden la fijo el usuario, no el motor. */
    orderPinned: boolean;
    /** Las ordenes que Hattrick permite en esa casilla. */
    orderOptions: { position: string; label: string }[];
  }[];
  /** Las seis plazas del banquillo de Hattrick, cada una con quien mejor la
   *  juega. Sin orden individual: esa la da el manager al hacer el cambio. */
  bench: {
    player: string;
    htPlayerId: number;
    tsi: number;
    slot: string;
    slotLabel: string;
    rating: number;
  }[];
  sectorRatings: {
    ratings: {
      sector: string;
      label: string;
      value: number;
      topContributors: { player: string; position: string; amount: number }[];
    }[];
    note: string;
  };
}

export interface TeamSpiritMultiplier {
  rows: { spirit: string; pic: number; normal: number; mots: number }[];
  note: string;
}

export const apiAlineacion = {
  lineup: (
    teamId: number,
    formation?: string,
    centralDefenders?: number,
    innerMidfielders?: number,
    /** Ordenes fijadas a mano: casilla -> posicion con orden. Las que no
     *  esten aqui las elige el motor. */
    orders?: Record<number, string>,
    /** Identificadores de Hattrick que quedan FUERA del reparto. El motor
     *  vuelve a resolver el once entero con el resto, no deja su casilla
     *  vacía. */
    exclude?: number[],
  ) => {
    const q = new URLSearchParams();
    if (formation) q.set("formation", formation);
    if (centralDefenders != null)
      q.set("central_defenders", String(centralDefenders));
    if (innerMidfielders != null)
      q.set("inner_midfielders", String(innerMidfielders));
    const fijadas = Object.entries(orders ?? {});
    if (fijadas.length > 0) {
      q.set("orders", fijadas.map(([slot, pos]) => `${slot}:${pos}`).join(","));
    }
    if (exclude && exclude.length > 0) q.set("exclude", exclude.join(","));
    const qs = q.toString();
    return request<Lineup>(`/teams/${teamId}/lineup${qs ? `?${qs}` : ""}`);
  },
  lineupHindsight: (teamId: number) =>
    request<LineupHindsight>(`/teams/${teamId}/lineup/hindsight`),
  teamSpiritMultiplier: (teamId: number) =>
    request<TeamSpiritMultiplier>(`/teams/${teamId}/lineup/team-spirit`),
};
