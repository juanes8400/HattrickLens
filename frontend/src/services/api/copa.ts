/** Copa.
 *
 *  Sale de partir `services/api.ts`, que tenia 4147 lineas y se leia entero
 *  en cada cambio del frontend. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../services/api"` sigue valiendo igual.
 */
import type { PitchZoneMethod } from "./comun";
import { request } from "./nucleo";

export interface CupHistoryRow {
  htMatchId: number;
  date: string;
  opponent: string;
  opponentHtTeamId: number;
  isHome: boolean;
  goalsFor: number;
  goalsAgainst: number;
  result: "V" | "E" | "D";
  hatstats: number | null;
  round: number | null;
  cupName: string | null;
}

export interface CupNextMatch {
  htMatchId: number;
  date: string;
  opponent: string;
  opponentHtTeamId: number;
  isHome: boolean;
  isNeutral: boolean;
  venueLabel: string;
  roundEstimate: number | null;
  officialRound: number | null;
  cupName: string | null;
}

/** Un cruce del Hattrick Masters de esta temporada, jugado o programado. */
export interface MastersRival {
  htMatchId: number;
  date: string;
  opponent: string;
  opponentHtTeamId: number;
  played: boolean;
  goalsFor: number | null;
  goalsAgainst: number | null;
}

export interface CupPrizeStage {
  stage: string;
  amount: number;
  roundsFromTitle: number;
  status: "passed" | "current" | "future";
  winsNeeded: number | null;
  trophyOnly: boolean;
}

export interface CupLadderStep {
  cupLevel: number;
  cupLevelIndex: number;
  cupName: string | null;
  fromDate: string;
  toDate: string;
  matches: number;
}

export interface Cup {
  teamName: string;
  currency: string;
  matchesPlayed: number;
  record: string;
  goalsFor: number;
  goalsAgainst: number;
  currentCupName: string | null;
  currentStreak: { count: number; result: "V" | "E" | "D" } | null;
  status: {
    stillInCup: boolean;
    source: "teamdetails" | "calendario";
    cupId: number | null;
    cupName: string | null;
    scope: "national" | "divisional" | null;
    scopeLabel: string;
    tier: "main" | "challenge" | "consolation" | "other" | null;
    tierLabel: string;
    officialRound: number | null;
    /** Rondas que salen de CONTAR los partidos guardados. Si no coincide con
     *  `officialRound`, faltan partidos por sincronizar y `notes` lo dice. */
    countedRounds: number | null;
    roundsLeft: number | null;
    stageLabel: string | null;
    nextCupMatchDate: string | null;
  };
  /** La predicción del próximo cruce con el motor de zonas. `null` cuando no
   *  hay con qué: sin cruce pendiente, sin sesión de Hattrick, o sin historia
   *  de Copa del rival (su primera ronda). */
  prediction: {
    ownProbability: number;
    rivalProbability: number;
    expectedOwnGoals: number;
    expectedRivalGoals: number;
    mostLikelyScore: string;
    ownMatches: number;
    rivalMatches: number;
    /** Con qué resumen salió cada lado. Vuelve del servidor y no se supone:
     *  si pediste «Alineación enviada» y todavía no has mandado ninguna, aquí
     *  llega el resumen que de verdad se usó. */
    metodoPropio: PitchZoneMethod;
    metodoRival: PitchZoneMethod;
    /** `true` cuando los siete sectores salen de la alineación enviada y los
     *  dos de acciones indirectas a balón parado se toman de lo ya jugado,
     *  porque Hattrick no los prevé. */
    indirectasPrestadas: boolean;
  } | null;
  goal: {
    stage: string | null;
    roundsLeft: number | null;
    winsToTitle: number | null;
    securedAmount: number;
    nextMilestone: CupPrizeStage | null;
    titleAmount: number;
    trophyOnly: boolean;
  };
  scenarios: {
    win: CupScenario;
    loss: CupScenario;
  } | null;
  impact: {
    experienceMultiplierVsLeague: number;
    experiencePointsPer90: number;
    affectsClubMood: boolean;
    injuryEffect: string;
  };
  economy: {
    currency: string;
    observedHomeMatches: number;
    /** Público, no dinero. La taquilla de UN partido no llega por ningún
     *  sitio: ni Hattrick la publica por partido, ni se puede reconstruir sin
     *  replicar la asistencia por sector, que es función de HT Supporter. */
    observedAttendance: number;
    bestAttendance: number;
    averageAttendance: number;
    /** Cuántos de esos partidos tienen taquilla calculada. Menos que los
     *  medidos = faltan desgloses por completar, y la pantalla lo dice. */
    matchesWithGate: number;
    /** La suma de las taquillas calculadas, en bruto. */
    observedGrossGate: number;
    /** Tu parte de esa suma: en Copa el local se queda el 67 %. */
    observedShare: number;
    sharePercent: number;
    /** Cuántos de los partidos con taquilla se jugaron fuera: ésos entran al
     *  33 %, no al 67 %. */
    awayMatchesWithGate: number;
  };
  readiness: {
    referenceVariants: CupReadinessVariant[];
    defaultMode: "top_tsi" | "submitted" | "last_cup" | "last_league";
    penaltyCandidates: CupPenaltyCandidate[];
    goalkeeper: { htPlayerId: number; name: string; keeper: number } | null;
    penaltyMethod: string;
  };
  ladder: CupLadderStep[];
  history: CupHistoryRow[];
  nextMatches: CupNextMatch[];
  mastersRivals: MastersRival[];
  prizeTable: CupPrizeStage[];
  notes: string[];
}

export interface CupScenario {
  continues: boolean | null;
  destination: string | null;
  description: string;
  nextStage: string | null;
  prizeAmount: number;
}

export interface CupReadinessVariant {
  mode: "top_tsi" | "submitted" | "last_cup" | "last_league";
  label: string;
  sourceMatchId: number | null;
  sourceOpponent: string | null;
  sourceDate: string | null;
  averageStamina: number | null;
  staminaBands: { label: string; min: number; max: number; count: number }[];
  startersCount: number;
  /** Los once que patearían si ESTE once está en el campo, del primero al
   *  último. Cada variante trae el suyo. */
  penaltyCandidates: CupPenaltyCandidate[];
}

export interface CupPenaltyCandidate {
  htPlayerId: number;
  name: string;
  setPieces: number;
  scoring: number;
  experience: number;
  technical: boolean;
  readinessIndex: number;
}

export const apiCopa = {
  cup: (
    teamId: number,
    // Los mismos dos selectores que la ficha de rival: uno por lado, y del
    // propio existe además la alineación ya enviada.
    pitchZoneMethodOwn: PitchZoneMethod = "submitted",
    pitchZoneMethodRival: PitchZoneMethod = "average",
  ) =>
    request<Cup>(
      `/teams/${teamId}/cup` +
        `?pitch_zone_method_own=${pitchZoneMethodOwn}` +
        `&pitch_zone_method_rival=${pitchZoneMethodRival}`,
    ),
};
