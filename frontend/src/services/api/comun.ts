/** Lo que usan varias funcionalidades a la vez.
 *
 *  Sale de partir `services/api.ts`, que tenia 4147 lineas y se leia entero
 *  en cada cambio del frontend. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../services/api"` sigue valiendo igual.
 */
import { request } from "./nucleo";

export interface PositionRating {
  position: string;
  label: string;
  rating: number;
  confidence: string;
}

export interface SquadPlayer {
  htPlayerId: number;
  name: string;
  ageYears: number;
  ageDays: number;
  /** Veterano sin habilidades de campo: Posiciones lo esconde por defecto. */
  withoutFieldSkills: boolean;
  tsi: number;
  /** Valor acumulado de las siete habilidades segun la tabla HTMS. */
  htms: number;
  /** Lo que tendria a los 28 entrenando sin parar desde hoy. */
  htms28: number;
  form: number;
  stamina: number;
  experience: number;
  salary: number;
  specialty: string;
  injuryLevel: number;
  isTransferListed: boolean;
  loyalty: number;
  leadership: number;
  agreeability: number;
  agreeabilityLabel: string;
  aggressiveness: number;
  aggressivenessLabel: string;
  honesty: number;
  honestyLabel: string;
  countryId: number;
  countryCode: string | null;
  leagueGoals: number;
  cupGoals: number;
  friendliesGoals: number;
  careerGoals: number;
  careerHattricks: number;
  careerAssists: number;
  playerTrainerSkillLevel: number;
  playerTrainerType: number;
  motherClubBonus: boolean;
  motherClubTeamName: string | null;
  nativeLeagueName: string | null;
  purchasePrice: number | null;
  purchasedAt: string | null;
  lastMatchPosition: string | null;
  lastMatchRating: number | null;
  lastMatchPlayedMinutes: number | null;
  skills: Record<string, number>;
  deltas: Record<string, number>;
  bestPosition: PositionRating;
  positionRating: PositionRating | null;
}

/** Lo que el barrido de comisiones deja dicho al terminar, para poder
 *  enseñarlo en Cambios sin volver a preguntar nada. Viaja en el estado del
 *  enrutador, no en la URL: es de esta navegación y de ninguna más. */
export interface AvisoDelBarrido {
  commissions: number;
  histories: number;
  closedTotal: number;
  open: number;
  stopped: boolean;
}

export interface Dashboard {
  teamId: number;
  teamName: string;
  leagueName: string | null;
  seriesName: string | null;
  syncedAt: string | null;
  syncId: number | null;
  stale: boolean;
  squad: {
    playerCount: number;
    avgAge: number;
    totalTsi: number;
    /** Los once de más TSI. */
    top11Tsi: number;
    totalSalary: number;
    injuredCount: number;
  } | null;
  finance: {
    cash: number;
    expectedCash: number;
    weeklyDelta: number;
    incomeSum: number;
    costsSum: number;
    costsPlayers: number;
    fanClubSize: number;
    lastWeeksTotal: number;
    /** `null` = no hay ni un cierre semanal guardado. No es 0. */
    structuralBalance: number | null;
    /** Las dos semanas ya cerradas: cubren siempre un partido en casa.
     *  `null` = todavía no hay dos cierres guardados. No es 0. */
    biweeklyBalance: number | null;
    biweeklyIncome: number | null;
    /** `null` = Hattrick no dio los salarios de la semana anterior. No es 0. */
    biweeklySalaries: number | null;
    /** Salarios sobre los ingresos de esas dos semanas, ventas incluidas. */
    salarySharePct: number | null;
    currency: string;
  } | null;
  training: {
    typeId: number;
    typeName: string;
    level: number;
    staminaPart: number;
    trainerName: string;
    morale: number | null;
    moraleName: string;
    confidence: number | null;
    confidenceName: string;
    /** Cuánto del entrenamiento máximo posible recibe el club: 100% es
     *  entrenador 5/5, dos asistentes de nivel 5 y toda la intensidad en la
     *  habilidad. Mismos coeficientes que la proyección. */
    efficiencyPct: number;
    coachLevel: number;
    assistantLevelSum: number;
    /** Edad media de quienes de verdad recibieron el entrenamiento esta
     *  semana. `null` mientras no se haya jugado ningún partido. */
    trainedAvgAge: number | null;
    trainedPlayers: number;
  } | null;
  topSalaries: SquadPlayer[];
  alerts: { kind: string; severity: string; message: string }[];
}

export interface NextMatchCondition {
  players: number;
  staminaAvailable: boolean;
  formAvailable: boolean;
  experienceAvailable: boolean;
  staminaAvg: number | null;
  staminaMedian: number | null;
  formAvg: number | null;
  experienceAvg: number | null;
  lowStaminaCount: number;
  byLine: {
    line: string;
    players: number;
    staminaAvg: number | null;
    formAvg: number | null;
    experienceAvg: number | null;
  }[];
}

export interface CalculationReference {
  implementation: string;
  status: "ported" | "structural" | "pending";
  source_files: string[];
  recovered: string;
  pending: string;
  numeric_profile?: string;
}

/** Cómo se resume cada zona sobre los partidos vistos. Ver `PitchZoneMethod`
 *  en el motor: el promedio dice cómo juega de costumbre, el máximo de lo que
 *  es capaz, y el máximo de los tres carriles de lo que es capaz por
 *  cualquiera de ellos. */
export type PitchZoneMethod =
  /** El que abre. Hubo un "median" delante hasta el 2026-09-13; se retiró
   *  a pedido del usuario y el servidor lo lee como promedio. */
  | "average"
  | "max"
  | "max_parallel"
  | "last"
  /** Solo para el lado propio: la predicción de minuto 0 de Hattrick para las
   *  órdenes ya enviadas. De un rival no existe. */
  | "submitted";

export const apiComun = {
  editStint: (
    teamId: number,
    stintId: number,
    cambios: {
      training_type?: number | null;
      top_skill?: string | null;
      age_years?: number | null;
      age_days?: number | null;
      excluded?: boolean;
    },
  ) =>
    request<{
      stintId: number;
      trainingType: number | null;
      topSkill: string | null;
      ageYears: number | null;
      ageDays: number | null;
      excluded: boolean;
    }>(`/teams/${teamId}/stints/${stintId}`, {
      method: "PATCH",
      body: JSON.stringify(cambios),
    }),
};
