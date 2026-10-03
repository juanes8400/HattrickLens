/** Entrenamiento.
 *
 *  Sale de partir `services/api.ts`, que tenia 4147 lineas y se leia entero
 *  en cada cambio del frontend. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../services/api"` sigue valiendo igual.
 */
import type { CalculationReference } from "./comun";
import { request } from "./nucleo";

export interface TrainingForecast {
  trainingType: number | null;
  trainedSkill: string | null;
  exposure: number;
  players: {
    player: string;
    htPlayerId: number;
    age: string;
    currentLevel: number;
    weeksToPop: number | null;
  }[];
}

export interface PostMatchTrainingOption {
  trainingType: number;
  name: string;
  trainedSkill: string | null;
  recommendable: boolean;
  rationale: string[];
  score: number;
  /** Aporte posicional ganado por semana, sumando la plantilla. Es lo que
   *  ordena las opciones desde el 2026-09-13; `score` sólo desempata. */
  value: number;
  trainedPlayers: number;
  fullTrainingPlayers: number;
  partialTrainingPlayers: number;
  equivalentMinutes: number;
  averageExposure: number;
  popsSoon: number;
  topTrainees: {
    htPlayerId: number;
    name: string;
    exposure: number;
    equivalentMinutes: number;
    currentLevel: number;
    weeksToPop: number;
  }[];
}

export interface PostMatchTraining {
  team: { id: number; htTeamId: number; name: string };
  trainingWindow: { from: string; to: string; trainingDate: string };
  currentTraining: {
    trainingType: number;
    name: string;
    trainedSkill: string | null;
    intensity: number;
    staminaPart: number;
  } | null;
  recommendation: PostMatchTrainingOption | null;
  options: PostMatchTrainingOption[];
  players: {
    htPlayerId: number;
    name: string;
    segments: {
      matchId: number | null;
      playedAt: string | null;
      matchType: number | null;
      matchTypeName: string | null;
      positionCode: number;
      position: string;
      minutes: number;
      rating: number | null;
      source: string;
    }[];
    bestExposureTrainingType: number;
    bestExposureTrainingName: string | null;
    bestExposure: number;
    exposureByTrainingType: Record<string, number>;
  }[];
  notes: string[];
}

/** El parte de la última actualización semanal de entrenamiento. */
export interface UltimoEntrenamiento {
  /** Instante oficial de la actualización. `null` si no se sabe la hora de
   *  esta liga todavía. */
  at: string | null;
  seasonWeek: string | null;
  trainingType: string | null;
  intensity: number | null;
  staminaShare: number | null;
  trainerName: string | null;
  /** Lo que Hattrick confirmó: subidas Y bajadas, que el mismo fichero
   *  reporta. `delta` positivo sube, negativo baja. */
  ups: {
    htPlayerId: number;
    name: string;
    skill: string;
    skillLabel: string;
    fromLevel: number;
    toLevel: number;
    delta: number;
  }[];
  upCount: number;
  downCount: number;
  previousAt: string | null;
  previousSeasonWeek: string | null;
  previousUps: number;
  /** Cuando en la última no subió nadie, la última que sí movió algo. */
  lastWithUps: string | null;
  /** Hasta cuándo llegan los datos guardados. */
  dataAt: string | null;
  /** Los datos son anteriores al entrenamiento: todavía no se ha mirado. */
  pendingSync: boolean;
  /** Cuándo toca el siguiente. */
  nextAt: string | null;
}

export interface FormulaInput {
  value: number | string | boolean;
  source: string; // "club.xml" | "training.xml" | "stafflist.xml" | "supuesto"
  isRead: boolean; // leído del CHPP, o todavía un supuesto
  note: string;
}

// ── Scouting de rivales ──────────────────────────────────────────────────────

export interface TrainingFormula {
  trainedSkill: string;
  allRead: boolean;
  formula: string;
  limitations?: string[];
  inputs: Record<string, FormulaInput>;
  setup: {
    skill: string;
    trainingType: number | null;
    trainingMode: string;
    intensity: number;
    staminaShare: number;
    coachLevel: number;
    coachIsExcellent: boolean;
    assistantLevelSum: number;
  };
  validation: {
    observations: number;
    meanErrorWeeks: number | null;
    maxErrorWeeks: number | null;
    samples: {
      player_id: number;
      from_level: number;
      to_level: number;
      observed_weeks: number;
      predicted_weeks: number;
      error_weeks: number;
    }[];
    caveats: string[];
  };
  notes: string[];
  reference: CalculationReference;
}

export interface TrainingSquadPlayerRow {
  /** "83-03": la semana de la última subida confirmada. Cadena vacía cuando
   *  no hay ninguna registrada, que no es lo mismo que no haber mejorado: es
   *  que Hattrick no reporta ninguna. */
  lastImprovement: string;

  htPlayerId: number;
  name: string;
  nativeCountry: string | null;
  countryCode: string | null;
  age: string;
  level: number;
  levelName: string;
  weeksElapsed: number | null;
  weeksTotal: number;
  progressPct: number | null;
  hasReference: boolean;
  hasHistoricalReference: boolean;
  currentWeekMinutes: number;
  currentWeekExposure: number;
  /** Veterano sin habilidades de campo: la tabla lo esconde por defecto. */
  withoutFieldSkills: boolean;
}

export interface TrainingSquadWeeklyLogEntry {
  seasonWeek: string | null;
  date: string;
  trainingType: string;
  intensity: number;
  staminaShare: number;
  trainerName: string;
}

export interface TrainingSquad {
  skill: string;
  skillLabel: string;
  availableSkills: { skill: string; label: string }[];
  includeThisWeek: boolean;
  setup: {
    skill: string;
    trainingType: number | null;
    trainingMode: string;
    intensity: number;
    staminaShare: number;
    coachLevel: number;
    coachIsExcellent: boolean;
    assistantLevelSum: number;
  };
  players: TrainingSquadPlayerRow[];
  weeklyLog: TrainingSquadWeeklyLogEntry[];
  notes: string[];
}

export interface TrainingExperienceRow {
  /** "83-03": la semana de la última subida confirmada. Cadena vacía cuando
   *  no hay ninguna registrada, que no es lo mismo que no haber mejorado: es
   *  que Hattrick no reporta ninguna. */
  lastImprovement: string;

  htPlayerId: number;
  name: string;
  nativeCountry: string | null;
  countryCode: string | null;
  age: string;
  level: number;
  levelName: string;
  decimalLevel: number | null;
  points: number | null;
  pointsPerLevel: number;
  remainingPoints: number | null;
  progressPct: number | null;
  breakdown: Record<string, number>;
  matchCounts: Record<string, number>;
  unscoredNationalMatches: number;
}

export interface TrainingLoyaltyRow {
  /** "83-03": la semana de la última subida confirmada. Cadena vacía cuando
   *  no hay ninguna registrada, que no es lo mismo que no haber mejorado: es
   *  que Hattrick no reporta ninguna. */
  lastImprovement: string;

  htPlayerId: number;
  name: string;
  nativeCountry: string | null;
  countryCode: string | null;
  age: string;
  reportedLevel: number;
  calculatedLevel: number | null;
  levelName: string;
  decimalLevel: number | null;
  progressPct: number | null;
  daysInClub: number | null;
  nextLevel: number | null;
  daysToNextLevel: number | null;
  dateSource: "transferencia" | "manual" | null;
}

export interface TrainingStaminaRow {
  /** "83-03": la semana de la última subida confirmada. Cadena vacía cuando
   *  no hay ninguna registrada, que no es lo mismo que no haber mejorado: es
   *  que Hattrick no reporta ninguna. */
  lastImprovement: string;

  htPlayerId: number;
  name: string;
  nativeCountry: string | null;
  countryCode: string | null;
  age: string;
  level: number;
  levelName: string;
  effectiveTrainingPct: number;
  expectedLevel: number | null;
  expectedLevelName: string | null;
  trend: "sube" | "baja" | "estable" | "sin_dato";
}

export interface TrainingDevelopment {
  experience: TrainingExperienceRow[];
  loyalty: TrainingLoyaltyRow[];
  stamina: TrainingStaminaRow[];
  notes: string[];
}

export const apiEntrenamiento = {
  trainingForecast: (teamId: number) =>
    request<TrainingForecast>(`/teams/${teamId}/training/forecast`),
  postMatchTraining: (teamId: number) =>
    request<PostMatchTraining>(`/teams/${teamId}/training/post-match`),
  ultimoEntrenamiento: (teamId: number) =>
    request<UltimoEntrenamiento>(`/teams/${teamId}/training/last`),
  trainingFormula: (teamId: number) =>
    request<TrainingFormula>(`/teams/${teamId}/training/formula`),
  trainingSquad: (
    teamId: number,
    skill?: string | null,
    includeThisWeek = true,
  ) => {
    const q = new URLSearchParams();
    if (skill) q.set("skill", skill);
    if (!includeThisWeek) q.set("include_this_week", "false");
    const qs = q.toString();
    return request<TrainingSquad>(
      `/teams/${teamId}/training/squad${qs ? `?${qs}` : ""}`,
    );
  },
  trainingDevelopment: (teamId: number) =>
    request<TrainingDevelopment>(`/teams/${teamId}/training/development`),
};
