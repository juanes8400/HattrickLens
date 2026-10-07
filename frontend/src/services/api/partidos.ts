/** Partidos.
 *
 *  Sale de partir `services/api.ts`, que tenia 4147 lineas y se leia entero
 *  en cada cambio del frontend. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../services/api"` sigue valiendo igual.
 */
import { request } from "./nucleo";

export interface MatchDetailsSyncResult {
  matchesProcessed: number;
  snapshotsWritten: number;
  unchanged: number;
  errors: string[];
}

/** El ultimo partido jugado, al lado de lo que dijimos antes de jugarlo.
 *
 *  Solo numeros y claves: quien era el favorito, si el marcador cantado cayo
 *  y como le fue al equipo propio se derivan en la pantalla, que es donde se
 *  escribe la frase y donde se puede traducir. */
export interface LastMatchReport {
  htMatchId: number;
  playedAt: string | null;
  competition: string;
  round: number | null;
  home: string;
  away: string;
  homeGoals: number;
  awayGoals: number;
  isHome: boolean;
  /** `null` cuando de ese partido no guardamos nada. Es el caso de todo
   *  partido anterior al 2026-09-26, y no se rellena recalculandolo: eso
   *  seria lo que diriamos hoy, no lo que dijimos. */
  prediction: {
    homeWin: number;
    draw: number;
    awayWin: number;
    expectedHomeGoals: number;
    expectedAwayGoals: number;
    mostLikelyScore: string;
    /** `zonas` mira alineaciones y tacticas; `goles` es el respaldo que solo
     *  mira goles agregados de la temporada, y no se le puede pedir cuentas
     *  igual. La pantalla lo dice. */
    source: string;
    engine: string;
    computedAt: string | null;
  } | null;
}

export interface MatchRow {
  htMatchId: number;
  date: string;
  matchType: number;
  /** El torneo en palabras, y en copa cuál: «Copa Cocuy Rubí». */
  tournament: string;
  opponent: string;
  isHome: boolean;
  goalsFor: number;
  goalsAgainst: number;
  result: string;
  hatstats: number | null;
  hatstatsOpponent: number | null;
  loddar: number | null;
  midfield: number | null;
}

export interface RatingSeriesPoint {
  htMatchId: number;
  date: string;
  seasonWeek: string | null;
  opponent: string;
  result: string;
  goalsFor: number;
  goalsAgainst: number;
  midfield: number;
  defence: number;
  attack: number;
  hatstats: number;
}

export interface ZoneChances {
  zone: string;
  label: string;
  own: number;
  opponent: number;
}

export interface ConversionSummary {
  ownChances: number;
  ownGoals: number;
  ownConversion: number;
  opponentChances: number;
  opponentGoals: number;
  opponentConversion: number;
  isReliable: boolean;
  zones: ZoneChances[];
}

export interface HomeAwayRow {
  scope: "home" | "away";
  label: string;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  goalsFor: number;
  goalsAgainst: number;
}

export interface BestRating {
  metric: string;
  label: string;
  value: number;
  date: string;
  opponent: string;
  htMatchId: number;
}

export interface Matches {
  teamName: string;
  matchesPlayed: number;
  record: string;
  goalsFor: number;
  goalsAgainst: number;
  matches: MatchRow[];
  ratingSeries: RatingSeriesPoint[];
  conversion: ConversionSummary;
  avgHatstats: number | null;
  bestMatch: MatchRow | null;
  worstMatch: MatchRow | null;
  availableSeasons: number[];
  currentSeason: number | null;
  selectedSeason: number | null;
  seasonLabel: string;
  includeFriendlies: boolean;
  homeAway: HomeAwayRow[];
  resultsPie: { won: number; drawn: number; lost: number };
  bestRatings: BestRating[];
  notes: string[];
}

export interface MatchDetail {
  htMatchId: number;
  date: string;
  opponent: string;
  isHome: boolean;
  score: string;
  sectors: {
    sector: string;
    label: string;
    own: number;
    opponent: number;
    delta: number;
    dominance: number;
  }[];
  possession: [number, number];
  hatstats: number;
  hatstatsOpponent: number;
  loddar: number;
  loddarOpponent: number;
  verdict: string;
  strengths: string[];
  weaknesses: string[];
  ownChances: {
    left: number;
    center: number;
    right: number;
    special: number;
    other: number;
    total: number;
    goals: number;
    conversion: number;
  };
  opponentChances: {
    left: number;
    center: number;
    right: number;
    special: number;
    other: number;
    total: number;
    goals: number;
    conversion: number;
  };
}

// ── Liga y predicciones ─────────────────────────────────────────────────────

export const apiPartidos = {
  matches: (
    teamId: number,
    includeFriendlies = false,
    season?: number | null,
  ) => {
    const q = new URLSearchParams();
    if (includeFriendlies) q.set("include_friendlies", "true");
    if (season != null) q.set("season", String(season));
    const qs = q.toString();
    return request<Matches>(`/teams/${teamId}/matches${qs ? `?${qs}` : ""}`);
  },
  matchDetail: (teamId: number, htMatchId: number) =>
    request<MatchDetail>(`/teams/${teamId}/matches/${htMatchId}`),
  lastMatchReport: (teamId: number) =>
    request<LastMatchReport | null>(`/teams/${teamId}/last-match-report`),
  syncMatchDetails: (teamId: number) =>
    request<MatchDetailsSyncResult>(`/teams/${teamId}/matches/details/sync`, {
      method: "POST",
    }),
};
