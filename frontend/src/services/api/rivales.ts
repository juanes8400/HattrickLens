/** Scouting de rivales.
 *
 *  Sale de partir `services/api.ts`, que tenia 4147 lineas y se leia entero
 *  en cada cambio del frontend. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../services/api"` sigue valiendo igual.
 */
import type { PitchZoneMethod } from "./comun";
import { request } from "./nucleo";

export interface PartidoConMarcador {
  homeName: string;
  awayName: string;
  homeGoals: number;
  awayGoals: number;
  playedAt: string | null;
  competition: string;
}

/** Un duelo cabeza a cabeza por carril de la cancha. `zone` es el carril
 * físico (izquierda/centro/derecha, o "midfield" para el de medio campo);
 * `half` dice de qué mitad de la cancha es ese duelo: "own" = tu campo (tu
 * defensa contra el ataque espejado del rival), "rival" = su campo (tu
 * ataque espejado contra su defensa), "midfield" = el único de medio
 * campo. `ownPct`/`rivalPct` sí suman 1 siempre. */
export interface PitchZoneDuel {
  zone: "left" | "central" | "right" | "midfield";
  half: "own" | "rival" | "midfield";
  ownValue: number;
  rivalValue: number;
  ownPct: number;
  rivalPct: number;
}

export interface PitchZoneSource {
  kind: "submitted_chpp_prediction" | "historical_observed";
  label: string;
  matchId: number | null;
  observations: number | null;
  capturedAt: string | null;
  tacticType: number | null;
  tacticSkill: number | null;
}

export interface LastPurchase {
  playerName: string;
  htPlayerId: number;
  /** TSI en el momento de la compra. */
  tsi: number;
  price: number;
  deadline: string;
  /** Días desde la compra. La barra se llena con esto: recién comprado la
   *  llena entera, una temporada entera la deja a cero. */
  daysAgo: number | null;
  /** El puesto en el que se le ha visto jugar, de las alineaciones ya leídas.
   *  `null` si todavía no ha jugado ninguno de los partidos vistos. */
  lastPosition: string | null;
}

export interface RivalScouting {
  rivalHtTeamId: number;
  rivalName: string | null;
  /** El tuyo. Lo manda el servidor para que los dos paneles del mapa de
   *  cancha se lean como «X contra Y» en vez de «Tu fuente» / «Fuente
   *  rival». */
  ownTeamName: string;
  matchesAnalysed: number;
  /** Qué clases de partido puede enseñar ESTA ficha. El botón de la clase que
   *  venga en `false` se apaga: contra un rival oficial no se piden amistosos,
   *  y contra cualquier otro puede que sencillamente no tenga. */
  clasesDisponibles?: { competitive: boolean; friendly: boolean };
  /** El último partido de cada lado dentro de la muestra, para poder decir
   *  cuál es cuando el resumen elegido es «Último partido». */
  ultimoPartidoRival: PartidoConMarcador | null;
  ultimoPartidoPropio: PartidoConMarcador | null;
  /** Cuántos de cada competición entran en `matchesAnalysed`: cinco partidos
   *  no dicen lo mismo si son cinco de liga que si son tres y dos amistosos. */
  matchesByCompetition: { label: string; count: number }[];
  /** El último fichaje de cada lado. El TSI es el del MOMENTO de la compra,
   *  no el de hoy: por eso viaja la fecha. `null` si el club no ha comprado
   *  nunca o si CHPP no respondió. */
  lastPurchase: {
    own: LastPurchase | null;
    rival: LastPurchase | null;
  };
  /** TSI, forma, condición y experiencia son públicas de un rival (CHPP
   * expone esos campos aunque oculte las skills exactas). El liderazgo del
   * entrenador rival sale de su stafflist.xml v1.2 (público para cualquier
   * equipo) o, si eso no trajera nada, de su jugador-entrenador en
   * players.xml, `null` solo si ninguna de las dos fuentes tiene dato. */
  comparison: {
    tsi: { own: number | null; rival: number | null };
    form: { own: number | null; rival: number | null };
    stamina: { own: number | null; rival: number | null };
    experience: { own: number | null; rival: number | null };
    trainerLeadership: { own: number | null; rival: number | null };
    /** Días calendario desde el LoginTime más reciente reportado por
     * managercompendium.xml. Cero significa que el manager entró hoy. */
    lastLoginDays: { own: number | null; rival: number | null };
  };
  comparisonReference: {
    ownSource: "submitted_orders" | "full_roster";
    ownLabel: string;
    ownPlayers: number;
    rivalSource: "probable_recent_starters" | "full_roster";
    rivalLabel: string;
    rivalPlayers: number;
  };
  tsiHistogram: {
    grid: number[];
    ownDensity: number[];
    rivalDensity: number[];
    ownValues: number[];
    rivalValues: number[];
    logTransform: boolean;
    top11: boolean;
  };
  manMarking: {
    targetName: string;
    targetPosition: string;
    targetTsi: number;
    markerName: string;
    markerPosition: string;
    confidence: string;
    rationale: string;
    /** "cerca" (-50%, la combinación más eficiente) o "lejos" (-65%, sigue
     * siendo una orden legal, solo menos eficiente). */
    efficiency: "cerca" | "lejos";
    markerLossPct: number;
    riskNote: string;
    evidence: {
      targetCandidates: { name: string; tsi: number; position: string }[];
    };
  } | null;
  sideRotation: {
    attackLeftAvg: number;
    attackCentralAvg: number;
    attackRightAvg: number;
    attackLeftStd: number;
    attackCentralStd: number;
    attackRightStd: number;
    strongSide: string;
    /** % de los partidos vistos en que strongSide fue el lado más fuerte
     * EN ESE partido, 100% es "siempre el mismo lado, sin excepción". */
    dominantPct: number;
    dominantSideByMatch: string[];
    /** Un renglón por partido con los tres carriles, del más viejo al más
     *  reciente. Es lo que dibuja la vista de carriles: un promedio de 45
     *  puede ser "45 siempre" o "70, 20, 45". */
    attackByMatch: {
      label: string;
      date: string;
      left: number;
      central: number;
      right: number;
      best: string;
    }[];
    rotates: boolean;
    matchesAnalysed: number;
  } | null;
  /** 7 duelos cabeza a cabeza por carril de la cancha, de los mismos
   * partidos ya analizados arriba, el rival en vivo, el propio equipo de
   * MatchRating ya sincronizado. `null` si falta alguno de los dos lados
   * (nunca se inventa un duelo con un solo lado real). */
  pitchZoneDuels: PitchZoneDuel[] | null;
  pitchZonesMatchesAnalysed: { own: number | null; rival: number | null };
  pitchZoneSources: { own: PitchZoneSource; rival: PitchZoneSource };
  pitchZoneMethodOwn: PitchZoneMethod;
  pitchZoneMethodRival: PitchZoneMethod;
  /** `false` cuando todavía no has mandado alineación: sin eso, el modo
   *  "alineación enviada" no tiene nada que enseñar. */
  submittedLineupAvailable: boolean;
  rivalRosterSample: { name: string; position: string | null; tsi: number }[];
  /** La predicción del motor de zonas. `null` sin historia con la que
   *  alimentarlo. `drawProbability` es null en Copa: hay prórroga. */
  prediction: {
    esCopa: boolean;
    /** Qué resumen se usó de cada lado. Los mismos que mueven el mapa de
     *  cancha: desde 2026-09-09 el pronóstico no tiene selector propio. */
    metodoPropio: string;
    metodoRival: string;
    /** Hattrick no prevé las acciones indirectas a balón parado de una
     *  alineación enviada: esas dos van con el promedio de lo ya jugado. */
    indirectasPrestadas: boolean;
    hayCruce: boolean;
    ownProbability: number;
    drawProbability: number | null;
    rivalProbability: number;
    expectedOwnGoals: number;
    expectedRivalGoals: number;
    mostLikelyScore: string;
    ownMatches: number;
    rivalMatches: number;
  } | null;
  winProbability: {
    ownProbability: number;
    ownTsiTotal: number;
    rivalTsiTotal: number;
    confidence: string;
  };
  /** Táctica, nivel de táctica y formación, los tres son públicos para
   * cualquier equipo (verificado en vivo). La actitud (TeamAttitude) queda
   * fuera a propósito: CHPP nunca la incluye para un equipo que no es el
   * tuyo, así que no había nada honesto que resumir ahí. */
  tacticHistory: {
    matchesAnalysed: number;
    tactics: { code: number; label: string; count: number; pct: number }[];
    mostCommonTactic: {
      code: number;
      label: string;
      count: number;
      pct: number;
    } | null;
    avgTacticSkill: number | null;
    formations: { formation: string; count: number; pct: number }[];
    mostCommonFormation: {
      formation: string;
      count: number;
      pct: number;
    } | null;
  } | null;
  caveats: string[];
}

// ── Comparativa de liga ───────────────────────────────────────────────────────

export const apiRivales = {
  rivalScouting: (
    teamId: number,
    rivalHtTeamId: number,
    logTsi: boolean,
    top11: boolean,
    // Excluyentes: uno u otro. Los defectos son los del servidor, para que
    // la primera petición no pida una cosa distinta de la que abre.
    includeCompetitive = true,
    includeFriendlies = false,
    pitchZoneMethodOwn: PitchZoneMethod = "submitted",
    pitchZoneMethodRival: PitchZoneMethod = "average",
  ) =>
    request<RivalScouting>(
      `/teams/${teamId}/rivals/${rivalHtTeamId}/scouting` +
        `?log_tsi=${logTsi}&top11=${top11}` +
        `&include_competitive=${includeCompetitive}&include_friendlies=${includeFriendlies}` +
        `&pitch_zone_method_own=${pitchZoneMethodOwn}` +
        `&pitch_zone_method_rival=${pitchZoneMethodRival}`,
    ),
};
