/** Club y personal.
 *
 *  Sale de partir `services/api.ts`, que tenia 4147 lineas y se leia entero
 *  en cada cambio del frontend. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../services/api"` sigue valiendo igual.
 */
import { request } from "./nucleo";

export interface ClubStaffRoleEffect {
  trainingSpeedPct?: number;
  injuryRiskPp?: number;
  backgroundForm?: number;
  recoverySpeedPct?: number;
  injuryRiskReductionPp?: number;
  teamSpirit?: number;
  confidence?: number;
  maxFunds?: number;
  weeklyReturn?: number;
  extraOrders?: number;
  styleFlexibilityPp?: number;
}

export interface ClubStaffRole {
  key: string;
  label: string;
  level: number;
  members: { name: string; level: number }[];
  effect: ClubStaffRoleEffect | null;
}

export interface Club {
  teamName: string;
  current: {
    spirit: { level: number; label: string } | null;
    confidence: { level: number; label: string } | null;
    supporters: {
      fanClubSize: number;
      popularity: number;
      popularityLabel: string;
    } | null;
  };
  staff: {
    capturedAt: string;
    trainer: {
      skillLevel: number;
      type: number;
      typeLabel: string;
      leadership: number;
    };
    roles: ClubStaffRole[];
    totalLevels: number;
    // Gasto semanal REAL de la academia, ya en moneda local. Sale de
    // `CostsYouth` (economy.xml), no del `<Investment>` de club.xml, ese
    // campo Hattrick lo devuelve en 0 aunque el club sí esté invirtiendo
    // (verificado con un fetch en vivo 2026-08-15). `null` si todavía no
    // hay una lectura económica sincronizada.
    youthInvestment: number | null;
    youthInvestmentCurrency: string;
    youthLevel: number;
  } | null;
  /** El módulo de Psicología: espíritu y confianza con el motivo de cada
   *  movimiento. Sustituye a la gráfica «Ánimo competitivo», que los metía
   *  en un solo eje pese a tener escalas y causas distintas. */
  psychology: Psychology;
  moodHistory: { capturedAt: string; spirit: number; confidence: number }[];
  supporterHistory: {
    capturedAt: string;
    fanClubSize: number;
    supportersPopularity: number;
  }[];
  staffHistory: {
    capturedAt: string;
    seasonWeek: string | null;
    trainerSkillLevel: number;
    roles: ClubStaffRole[];
  }[];
  notes: string[];
}

/** Un tramo de espíritu o confianza, con lo que lo explica. */
export type PsychologyMovement = {
  at: string;
  from: number;
  to: number;
  delta: number;
  cause: string;
  /** Contexto, NO causa: cuántas operaciones cayeron dentro del tramo. */
  buys?: number;
  sales?: number;
};

export type PsychologySeries = {
  /** La escala ENTERA del juego, se haya pisado o no. */
  scale: { level: number; label: string }[];
  /** La referencia hacia la que tiende. `null` cuando el juego no publica su
   *  valor: entonces no se dibuja ninguna, en vez de inventar una. */
  equilibrium: number | null;
  readings: { at: string; level: number }[];
  movements: PsychologyMovement[];
};

export type PsychologyMatch = {
  playedAt: string;
  rival: string;
  isHome: boolean;
  goalsFor: number;
  goalsAgainst: number;
  result: "win" | "draw" | "loss";
  /** -1 PIC · 0 Normal · 1 MOTS. `null` si no se llegó a leer. */
  attitude: number | null;
  attitudeLabel: string | null;
};

export type Psychology = {
  weeks: number;
  spirit: PsychologySeries;
  confidence: PsychologySeries;
  matches: PsychologyMatch[];
  buyDays: { day: string; count: number }[];
  sellDays: { day: string; count: number }[];
  /** Cuándo se BAJÓ el % de entrenamiento. Vacío también es información. */
  intensityDrops: string[];
};

export const apiClub = {
  club: (teamId: number) => request<Club>(`/teams/${teamId}/club`),
};
