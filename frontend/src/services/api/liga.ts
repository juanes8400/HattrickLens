/** Liga y predicciones.
 *
 *  Sale de partir `services/api.ts`, que tenia 4147 lineas y se leia entero
 *  en cada cambio del frontend. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../services/api"` sigue valiendo igual.
 */
import type { PitchZoneMethod } from "./comun";
import { request } from "./nucleo";

export interface OutlookRow {
  htTeamId: number;
  name: string;
  isOwnTeam: boolean;
  currentPosition: number;
  currentPoints: number;
  expectedPoints: number;
  expectedPosition: number;
  mostLikelyPosition: number;
  titleProbability: number;
  promotionProbability: number;
  secondToFourthProbability: number;
  relegationPlayoffProbability: number;
  relegationProbability: number;
  attackStrength: number;
  defenceStrength: number;
  positionDistribution: Record<string, number>;
}

export interface LeagueStandingRow {
  position: number;
  htTeamId: number;
  name: string;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  goalsFor: number;
  goalsAgainst: number;
  goalDifference: number;
  points: number;
  isOwnTeam: boolean;
}

export interface League {
  teamName: string;
  seriesName: string | null;
  season: number | null;
  roundsPlayed: number;
  roundsRemaining: number;
  standings: LeagueStandingRow[];
  // 2026-08-08, pedido explícitamente: leaguedetails.xml solo da la tabla
  // combinada, estas se calculan desde los resultados reales de cada
  // partido (ver `_standings_from_matches` en el backend).
  standingsHome: LeagueStandingRow[];
  standingsAway: LeagueStandingRow[];
  /** Historial real de posición/puntos por jornada sincronizada, cada sync
   * guarda una foto de TODA la serie, no solo del equipo propio. `null`
   * donde falta una jornada por sincronizar, nunca un valor inventado. */
  history: {
    rounds: number[];
    teams: {
      htTeamId: number;
      name: string;
      isOwnTeam: boolean;
      positions: (number | null)[];
      points: (number | null)[];
    }[];
  };
  fixtures: {
    date: string;
    matchRound: number;
    home: string;
    away: string;
    played: boolean;
    score: string | null;
  }[];
  outlook: OutlookRow[];
  ownOutlook: OutlookRow | null;
  /** Mejor y peor caso del equipo propio con lo que queda de temporada,
   * re-simulado goleando o siendo goleado en lo propio, el resto de la
   * liga sigue siendo incierto, por eso es una distribución de puestos. */
  bestWorst: {
    htTeamId: number;
    name: string;
    remainingMatches: number;
    currentPoints: number;
    currentPosition: number;
    bestCasePositionDistribution: Record<string, number>;
    bestCaseExpectedPoints: number;
    worstCasePositionDistribution: Record<string, number>;
    worstCaseExpectedPoints: number;
  } | null;
  nextMatch: {
    home: string;
    away: string;
    round: number;
    homeWin: number;
    draw: number;
    awayWin: number;
    expectedHomeGoals: number;
    expectedAwayGoals: number;
    mostLikelyScore: string;
    verdict: string;
    isHome: boolean;
    /** De dónde sale cada lado (2026-09-12). `null` sin ratings de los dos:
     *  entonces el pronóstico sale de los goles de la temporada. */
    sources: {
      own: {
        /** Tus órdenes para este partido, o tu último partido. */
        kind: "submitted" | "last";
        match: LeagueMatchRef | null;
        /** Con la enviada: de qué partido salen las dos indirectas a balón
         *  parado, que Hattrick no prevé para unas órdenes. */
        setPiecesFrom: LeagueMatchRef | null;
        tactic: string;
      };
      rival: { kind: "last"; match: LeagueMatchRef | null; tactic: string };
    } | null;
  } | null;
  /** Cuánto movió la última jornada. `null` en la jornada 1, cuando no hay
   *  con qué comparar. Los deltas van en PUNTOS PORCENTUALES. */
  change: {
    matchRound: number;
    positionDelta: Record<string, number>;
    bestCaseDelta: Record<string, number>;
    worstCaseDelta: Record<string, number>;
    ownTitleBefore: number;
    ownTitleAfter: number;
    biggestGainer: string | null;
    biggestGainerBefore: number;
    biggestGainerAfter: number;
  } | null;
  simulationRuns: number;
  leagueAvgGoals: number;
  model: {
    model: string;
    shrinkageK: number;
    homeAdvantage: number;
    doesNotModel: string[];
  };
  isTopDivision: boolean;
  isBottomDivision: boolean;
  caveats: string[];
  /** Con cuál de los cuatro resúmenes se calcularon las predicciones de esta
   *  respuesta. Viene de vuelta para que el selector marque el que de verdad
   *  se usó, no el que la pantalla cree haber pedido. */
  pitchZoneMethod: LeaguePitchZoneMethod;
}

// ── Juveniles ───────────────────────────────────────────────────────────────

/** Los cuatro de Liga: los mismos menos "submitted". Ahí se describen ocho
 *  equipos y de siete no se pueden ver las órdenes, así que la alineación
 *  enviada no es un resumen de esa pantalla. */
export type LeaguePitchZoneMethod = Exclude<PitchZoneMethod, "submitted">;

/** Un partido con su marcador, para poder nombrarlo en una frase:
 *  «Equipo A 1 - 0 Equipo B». Lo arma el servidor porque allí ya están juntos
 *  los nombres y los goles; mandarlos sueltos obligaría a la pantalla a
 *  volver a emparejarlos, y a equivocarse de lado la primera vez. */
/** Un partido de liga ya jugado, lo justo para nombrarlo en pantalla:
 *  «Deportivo Uno 1 - 2 Pulgas Arrechas · jornada 6». */
export interface LeagueMatchRef {
  round: number | null;
  home: string;
  away: string;
  homeGoals: number;
  awayGoals: number;
}

export interface LeagueTeamSummary {
  teamHtId: number;
  teamName: string;
  totalTsi: number;
  avgTsi: number;
  playerCount: number;
  isOwn: boolean;
  rank: number;
  // 2026-08-08, pedido explícitamente: jugador de mayor TSI del equipo,
  // su TSI, su última posición jugada en partido oficial (playerdetails.xml,
  // una llamada aparte solo para él) y la forma/resistencia media de la
  // plantilla comparada, null cuando CHPP no mostró el dato para un rival.
  topPlayerName: string | null;
  topPlayerTsi: number | null;
  topPlayerLastPosition: string | null;
  avgForm: number | null;
  avgStamina: number | null;
  /** Experiencia media, con la misma regla que forma y condición. */
  avgExperience?: number | null;
}

/** Medio campo, defensa y ataque de cada equipo de la serie: media de sus
 *  últimos cinco partidos oficiales. Para la flor del Dashboard. */
export interface SectoresRecientes {
  partidosPorEquipo: number;
  equipos: {
    htTeamId: number;
    nombre: string;
    esPropio: boolean;
    partidos: number;
    medio: number | null;
    defensa: number | null;
    ataque: number | null;
    /** El próximo rival de Copa, que no es de tu serie (2026-09-15). */
    esCopa?: boolean;
    copa?: string | null;
  }[];
}

export interface LeagueComparison {
  seriesName: string;
  teamsInSeries: number;
  ownRank: number;
  ranking: LeagueTeamSummary[];
  /** Sólo con `incluir_copa`: tu próximo rival de Copa, fuera del ranking. */
  cupRival?:
    | (Omit<LeagueTeamSummary, "rank"> & {
        rank: null;
        cupName: string | null;
      })
    | null;
  tsiHistogram: {
    grid: number[];
    ownDensity: number[];
    rivalDensity: number[];
    ownValues: number[];
    rivalValues: number[];
    logTransform: boolean;
    top11: boolean;
  };
  caveats: string[];
}

export interface TeamOfWeekPlayer {
  htPlayerId: number;
  name: string;
  teamHtId: number;
  teamName: string;
  ratingStars: number;
  roleId: number;
  htMatchId: number;
}

// 2026-08-08, pedido explícitamente: extremos e interiores comparten un
// solo bloque "medios", y laterales/centrales comparten "defensa", el
// selector de formación decide cuántos cupos tiene cada bloque, igual que
// Hattrick Control (nunca un reparto fijo).
export type TeamOfWeekSlotKey = "keeper" | "defense" | "midfield" | "forward";

/** Las líneas partidas por sub-rol. `defense` y `midfield` son la suma de sus
 *  dos mitades; estas son las que permiten poner a los de banda en las orillas
 *  de la cancha, igual que en las otras dos canchas de la app. */
export type TeamOfWeekRoleKey =
  | "keeper"
  | "centralDefender"
  | "wingback"
  | "innerMidfield"
  | "winger"
  | "forward";

/** Las diez de Hattrick, de la más defensiva a la más ofensiva. Hasta
 *  2026-08-19 aquí había siete: faltaban 5-5-0, 5-2-3 y 2-5-3, así que el
 *  selector no las ofrecía aunque el motor supiera armarlas. */
export const FORMATIONS = [
  "5-5-0",
  "5-4-1",
  "5-3-2",
  "5-2-3",
  "4-5-1",
  "4-4-2",
  "4-3-3",
  "3-5-2",
  "3-4-3",
  "2-5-3",
] as const;
export type Formation = (typeof FORMATIONS)[number];

export interface TeamOfTheWeek {
  /** Cuántos de cada línea juegan por dentro; el resto va a las bandas. El
   *  nombre de la formación no lo dice: un 5-3-2 puede llevar 3 mediocentros
   *  o 1 y dos extremos. */
  centralDefenders: number;
  innerMidfielders: number;
  /** Los repartos legales para ESTA formación, que son los que el selector
   *  puede ofrecer. Una línea de cinco solo admite 3 por dentro. */
  centralDefenderOptions: number[];
  innerMidfielderOptions: number[];
  scope: "week" | "season";
  formation: Formation;
  formations: Formation[];
  matchRound: number | null;
  availableRounds: number[];
  roundsCovered: number;
  lineupsFound: number;
  lineupsExpected: number;
  slotLabels: Record<TeamOfWeekSlotKey, string>;
  positions: Record<TeamOfWeekSlotKey, TeamOfWeekPlayer[]> &
    Record<TeamOfWeekRoleKey, TeamOfWeekPlayer[]>;
  totalStars: number;
  caveats: string[];
}

export const apiLiga = {
  league: (
    teamId: number,
    runs = 10_000,
    // Un solo resumen para toda la pantalla de Liga. Sin "submitted": de
    // siete de los ocho equipos no se pueden ver las órdenes.
    pitchZoneMethod: LeaguePitchZoneMethod = "average",
  ) =>
    request<League>(
      `/teams/${teamId}/league?runs=${runs}` +
        `&pitch_zone_method=${pitchZoneMethod}`,
    ),
  leagueComparison: (
    teamId: number,
    logTsi: boolean,
    top11: boolean,
    incluirCopa = false,
  ) =>
    request<LeagueComparison>(
      `/teams/${teamId}/league/comparison` +
        `?log_tsi=${logTsi}&top11=${top11}` +
        (incluirCopa ? "&incluir_copa=true" : ""),
    ),
  sectoresRecientes: (teamId: number) =>
    request<SectoresRecientes>(`/teams/${teamId}/league/sectores-recientes`),
  leagueTeamOfWeek: (
    teamId: number,
    scope: "week" | "season",
    formation: Formation,
    round?: number,
    centralDefenders?: number,
    innerMidfielders?: number,
  ) =>
    request<TeamOfTheWeek>(
      `/teams/${teamId}/league/team-of-the-week?scope=${scope}&formation=${formation}` +
        (round != null ? `&round=${round}` : "") +
        (centralDefenders != null
          ? `&central_defenders=${centralDefenders}`
          : "") +
        (innerMidfielders != null
          ? `&inner_midfielders=${innerMidfielders}`
          : ""),
    ),
};
