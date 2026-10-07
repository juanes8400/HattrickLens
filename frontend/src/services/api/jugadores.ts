/** Ficha de jugador y puestos.
 *
 *  Sale de partir `services/api.ts`, que tenia 4147 lineas y se leia entero
 *  en cada cambio del frontend. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../services/api"` sigue valiendo igual.
 */
import type { CalculationReference, PositionRating } from "./comun";
import { request } from "./nucleo";

export interface PlayerDetailsSyncResult {
  playersProcessed: number;
  snapshotsWritten: number;
  errors: string[];
}

// 2026-08-05, pedido explícitamente: un jugador que ya no está en la
// plantilla actual (`roster()` en el backend, `left_team_at IS NULL`) trae
// una ficha reducida, nada de habilidades/posiciones/entrenamiento (no
// tiene sentido para alguien que ya no vemos), solo identidad y fechas. El
// saldo/ROI se pide aparte, del mismo endpoint que ya alimenta "Detalle" en
// Transferencias (nunca se duplica ese cálculo).
export interface ExPlayerDetail {
  isExPlayer: true;
  htPlayerId: number;
  name: string;
  purchasedAt: string | null;
  leftTeamAt: string | null;
  soldAt: string | null;
  /** Partidos que jugo de verdad con nosotros. null = todavia sin contar. */
  gamesWithUs: number | null;
  /** Ya no puede darnos comision, y por que. */
  resaleClosed: boolean;
  resaleClosedReason: string | null;
}

export interface ActivePlayerDetail {
  isExPlayer: false;
  htPlayerId: number;
  name: string;
  team: { htTeamId: number; name: string };
  age: string;
  tsi: number;
  htms: number;
  htms28: number;
  form: number;
  stamina: number;
  experience: number;
  salary: number;
  injuryLevel: number;
  countryId: number;
  countryCode: string | null;
  specialty: string;
  leadership: number;
  isTransferListed: boolean;
  lastMatch: {
    position: string;
    rating: number | null;
    minutes: number | null;
  } | null;
  playerTrainer: { level: number; type: number } | null;
  skills: Record<string, number>;
  positions: {
    position: string;
    label: string;
    rating: number;
    isSpecialRole: boolean;
  }[];
  training: {
    trainedSkill: string | null;
    weeksToPop: number | null;
    weeklyProgressPct: number | null;
  };
  salaryEstimate: {
    weeklySalary: number;
    mainSkill: string;
    afterNextPop: number | null;
    confidence: string;
  } | null;
  loyalty: number | null;
  // Curva continua de Fidelidad calculada solo con días desde la compra.
  // Es `null` únicamente cuando no existe una fecha de compra disponible.
  loyaltyDecimal: number | null;
  // Proyección de Resistencia, tabla Federación Ocerin, `null` solo sin
  // WorldContext propio. Las edades fuera de la tabla (17-36) usan la fila
  // del extremo más cercano, así que ya no cortan la proyección.
  staminaForecast: {
    seasonWeeks: (string | null)[];
    levels: number[];
    trainingPct: number;
    currentExpectedLevel: number | null;
  } | null;
  // "TT-ss" de cuándo entró al equipo (compra real o respaldo manual)
  // ancla el punto más antiguo del radar. `null` si no hay ninguna fecha.
  joinedSeasonWeek: string | null;
  // "TT-ss" de la compra real (transfersteam.xml), nunca el respaldo
  // manual, para no ponerle TT-ss a una fecha estimada.
  purchasedAtSeasonWeek: string | null;
  // Si el último partido con rating capturado cae en la semana actual.
  playedThisWeek: boolean;
  // null = playerdetails.xml nunca se ha pedido para este jugador (distinto
  // de "0 caps reales"), botón "Actualizar detalles de jugadores".
  nationalTeam: { caps: number; capsU20: number } | null;
  nativeLeagueName: string | null;
  purchasePrice: number | null;
  purchasedAt: string | null;
  careerStage: {
    stage: string;
    label: string;
    rationale: string;
    confidence: string;
    signals: Record<string, number | string | boolean | null>;
    confirmedStage: string | null;
    confirmedAt: string | null;
  };
  goals: {
    league: number;
    cup: number;
    friendlies: number;
    career: number;
    hattricks: number;
    assists: number;
  } | null;
  character: {
    agreeability: number;
    agreeabilityLabel: string;
    aggressiveness: number;
    aggressivenessLabel: string;
    honesty: number;
    honestyLabel: string;
  } | null;
  history: {
    dates: string[];
    seasonWeeks: (string | null)[];
    tsi: number[];
    salary: number[];
    skills: Record<string, number[]>;
    htms: number[];
    htms28: number[];
  };
  matchRatingHistory: {
    matchId: number;
    date: string;
    seasonWeek: string | null;
    rating: number;
    position: string;
    minutes: number;
  }[];
  squadDistributions: Record<
    "tsi" | "salary" | "salaryPerTsi",
    { grid: number[]; density: number[]; values: number[]; ownValue: number }
  > | null;
  percentile: {
    skill: string;
    value: number;
    percentile: number;
    squadSize: number;
  } | null;
  topSkillDistributions: Record<
    string,
    { grid: number[]; density: number[]; values: number[]; ownValue: number }
  > | null;
  experienceProgress: {
    points: number;
    percent: number;
    remainingPoints: number;
    pointsPerLevel: number;
    calibrationSource: string;
    breakdown: Record<string, number>;
    unscoredNationalMatches: number;
  } | null;
  squadAgeTsi: { htPlayerId: number; name: string; age: number; tsi: number }[];
}

export type PlayerDetail = ActivePlayerDetail | ExPlayerDetail;

/** Un puesto de la matriz: qué aporta a cada sector y con qué coeficiente. */
export interface PositionMatrixRow {
  id: string;
  label: string;
  /** Sólo los sectores donde el puesto aporta algo. Una fila con huecos
   *  vacíos se lee peor que una con dos columnas. */
  sectors: {
    id: string;
    label: string;
    skills: { skill: string; coef: number }[];
  }[];
}

export interface PositionModel {
  positions: number;
  /** La matriz entera, puesto por puesto. */
  matrixRows: PositionMatrixRow[];
  specialRoles: number;
  source: string;
  sourceUrl: string;
  sourceType: string;
  matrix: string;
  adjustments: Record<string, string>;
  scoreLabel: string;
  configPath: string;
  reference: CalculationReference;
}

export interface ConfirmedLevelUp {
  seasonWeek: string;
  fromLevel: number;
  fromLevelName: string;
  toLevel: number;
  toLevelName: string;
  weeksBetween: number | null;
}

export interface LevelForecastMilestone {
  level: number;
  levelName: string;
  weeksForThisLevel: number;
  weeksFromNow: number;
  seasonWeek: string | null;
  age: string;
}

export interface PlayerTrainingLevels {
  htPlayerId: number;
  name: string;
  skill: string;
  skillLabel: string;
  currentLevel: number;
  currentLevelName: string;
  confirmed: ConfirmedLevelUp[];
  forecast: LevelForecastMilestone[];
  notes: string[];
}

export const apiJugadores = {
  playerPositions: (htPlayerId: number) =>
    request<PositionRating[]>(`/teams/players/${htPlayerId}/positions`),
  playerDetail: (teamId: number, htPlayerId: number) =>
    request<PlayerDetail>(`/teams/${teamId}/players/${htPlayerId}`),
  positionModel: () => request<PositionModel>(`/teams/positions/model`),
  syncPurchasePrices: (teamId: number) =>
    request<PlayerDetailsSyncResult>(
      `/teams/${teamId}/players/purchase-price/sync`,
      {
        method: "POST",
      },
    ),
  setManualPurchasePrice: (
    teamId: number,
    htPlayerId: number,
    price: number,
    purchasedAt?: string,
  ) =>
    request<{ htPlayerId: number; purchasePriceManual: number }>(
      `/teams/${teamId}/players/${htPlayerId}/purchase-price`,
      {
        method: "PUT",
        body: JSON.stringify({ price, purchased_at: purchasedAt ?? null }),
      },
    ),
  playerTrainingLevels: (
    teamId: number,
    htPlayerId: number,
    skill?: string | null,
  ) => {
    const q = new URLSearchParams();
    if (skill) q.set("skill", skill);
    const qs = q.toString();
    return request<PlayerTrainingLevels>(
      `/teams/${teamId}/players/${htPlayerId}/training/levels${qs ? `?${qs}` : ""}`,
    );
  },
  syncPlayerDetails: (teamId: number) =>
    request<PlayerDetailsSyncResult>(`/teams/${teamId}/players/details/sync`, {
      method: "POST",
    }),
  confirmCareerStage: (
    teamId: number,
    htPlayerId: number,
    stage: string | null,
  ) =>
    request<{
      htPlayerId: number;
      confirmedStage: string | null;
      confirmedAt: string | null;
    }>(`/teams/${teamId}/players/${htPlayerId}/career-stage`, {
      method: "POST",
      body: JSON.stringify({ stage }),
    }),
};
