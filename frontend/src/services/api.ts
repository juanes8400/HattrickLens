/**
 * HT Lens API client.
 *
 * UI_GUIDELINES.md: business rules must not live in React components. This
 * module only transports data; every number it returns was computed by an
 * engine on the server.
 */
const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly detail?: unknown,
  ) {
    super(message);
  }
}

// La cookie de acceso dura pocos minutos (`jwt_access_ttl_minutes`) a
// propósito. La de refresco (días) la renueva en silencio: un 401 dispara
// como mucho UN intento de /auth/refresh, compartido entre requests
// simultáneos (varias queries pueden expirar a la vez), antes de reintentar
// la petición original. Si el refresco también falla (sesión realmente
// muerta), se deja pasar el 401 tal cual — la UI ya sabe pedir reconectar.
let refreshing: Promise<boolean> | null = null;

function expireLocalSession(): void {
  localStorage.removeItem("htlens_team_id");
  if (!window.location.pathname.startsWith("/welcome")) {
    window.location.assign("/welcome?reason=session_expired");
  }
}

function refreshSession(): Promise<boolean> {
  if (!refreshing) {
    refreshing = fetch(`${BASE}/auth/chpp/refresh`, {
      method: "POST",
      credentials: "include",
    })
      .then((res) => res.ok)
      .catch(() => false)
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const doFetch = () =>
    fetch(`${BASE}${path}`, {
      credentials: "include",
      headers: { "Content-Type": "application/json", ...init?.headers },
      ...init,
    });

  let res = await doFetch();
  const mayRefresh = path !== "/auth/chpp/refresh" && path !== "/auth/chpp/connect";
  if (res.status === 401 && mayRefresh) {
    const refreshed = await refreshSession();
    if (refreshed) res = await doFetch();
  }

  if (res.status === 401 && mayRefresh) expireLocalSession();

  if (!res.ok) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      detail = await res.text();
    }
    throw new ApiError(`${res.status} ${res.statusText}`, res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  sessionProfile: () => request<SessionProfile>(`/auth/chpp/session`),
  dashboard: (teamId: number) =>
    request<Dashboard>(`/teams/${teamId}/dashboard`),
  club: (teamId: number) => request<Club>(`/teams/${teamId}/club`),
  squad: (
    teamId: number,
    position?: string,
    comparisonSyncId?: number | null,
  ) => {
    const query = new URLSearchParams();
    if (position) query.set("position", position);
    if (comparisonSyncId != null)
      query.set("comparison_sync_id", String(comparisonSyncId));
    const suffix = query.toString();
    return request<Squad>(
      `/teams/${teamId}/squad${suffix ? `?${suffix}` : ""}`,
    );
  },
  playerPositions: (htPlayerId: number) =>
    request<PositionRating[]>(`/teams/players/${htPlayerId}/positions`),
  playerDetail: (teamId: number, htPlayerId: number) =>
    request<PlayerDetail>(`/teams/${teamId}/players/${htPlayerId}`),
  lineup: (teamId: number, formation?: string, weather?: string) => {
    const q = new URLSearchParams();
    if (formation) q.set("formation", formation);
    if (weather) q.set("weather", weather);
    const qs = q.toString();
    return request<Lineup>(`/teams/${teamId}/lineup${qs ? `?${qs}` : ""}`);
  },
  weatherImpact: (teamId: number, formation = "4-4-2") =>
    request<Record<string, number>>(
      `/teams/${teamId}/lineup/weather?formation=${formation}`,
    ),
  teamSpiritMultiplier: (teamId: number) =>
    request<TeamSpiritMultiplier>(`/teams/${teamId}/lineup/team-spirit`),
  trainingForecast: (teamId: number) =>
    request<TrainingForecast>(`/teams/${teamId}/training/forecast`),
  postMatchTraining: (teamId: number) =>
    request<PostMatchTraining>(`/teams/${teamId}/training/post-match`),
  insights: (teamId: number) => request<Insight[]>(`/teams/${teamId}/insights`),
  positionModel: () => request<PositionModel>(`/teams/positions/model`),
  experienceModel: (teamId: number) =>
    request<ExperienceModel>(`/teams/${teamId}/experience/calibration`),
  loyaltyModel: (teamId: number) =>
    request<LoyaltyModel>(`/teams/${teamId}/loyalty/calibration`),
  economy: (teamId: number, horizonWeeks = 52) =>
    request<Economy>(`/teams/${teamId}/economy?horizon_weeks=${horizonWeeks}`),
  arena: (teamId: number, fillRate?: number) => {
    const q = new URLSearchParams();
    if (fillRate != null) q.set("fill_rate", String(fillRate));
    const qs = q.toString();
    return request<Arena>(`/teams/${teamId}/arena${qs ? `?${qs}` : ""}`);
  },
  matches: (teamId: number, includeFriendlies = false, season?: number | null) => {
    const q = new URLSearchParams();
    if (includeFriendlies) q.set("include_friendlies", "true");
    if (season != null) q.set("season", String(season));
    const qs = q.toString();
    return request<Matches>(`/teams/${teamId}/matches${qs ? `?${qs}` : ""}`);
  },
  matchDetail: (teamId: number, htMatchId: number) =>
    request<MatchDetail>(`/teams/${teamId}/matches/${htMatchId}`),
  league: (teamId: number, runs = 10000) =>
    request<League>(`/teams/${teamId}/league?runs=${runs}`),
  academy: (teamId: number) => request<Academy>(`/teams/${teamId}/academy`),
  playerBalance: (teamId: number, season?: string) => {
    const params = new URLSearchParams();
    if (season && season !== "all") params.set("season", season);
    const qs = params.toString();
    return request<PlayerBalance>(`/teams/${teamId}/player-balance${qs ? `?${qs}` : ""}`);
  },
  syncPurchasePrices: (teamId: number) =>
    request<PlayerDetailsSyncResult>(`/teams/${teamId}/players/purchase-price/sync`, {
      method: "POST",
    }),
  syncTransfersHistory: (teamId: number) =>
    request<TransfersHistorySyncResult>(`/teams/${teamId}/transfers/sync`, {
      method: "POST",
    }),
  setManualPurchasePrice: (teamId: number, htPlayerId: number, price: number, purchasedAt?: string) =>
    request<{ htPlayerId: number; purchasePriceManual: number }>(
      `/teams/${teamId}/players/${htPlayerId}/purchase-price`,
      { method: "PUT", body: JSON.stringify({ price, purchased_at: purchasedAt ?? null }) },
    ),
  trainingFormula: (teamId: number) =>
    request<TrainingFormula>(`/teams/${teamId}/training/formula`),
  trainingSquad: (teamId: number, skill?: string | null, includeThisWeek = true) => {
    const q = new URLSearchParams();
    if (skill) q.set("skill", skill);
    if (!includeThisWeek) q.set("include_this_week", "false");
    const qs = q.toString();
    return request<TrainingSquad>(`/teams/${teamId}/training/squad${qs ? `?${qs}` : ""}`);
  },
  playerTrainingLevels: (teamId: number, htPlayerId: number, skill?: string | null) => {
    const q = new URLSearchParams();
    if (skill) q.set("skill", skill);
    const qs = q.toString();
    return request<PlayerTrainingLevels>(
      `/teams/${teamId}/players/${htPlayerId}/training/levels${qs ? `?${qs}` : ""}`,
    );
  },
  sync: (teamId: number) =>
    request<SyncResult>(`/teams/${teamId}/sync`, { method: "POST" }),
  // 2026-08-05, pedido explícitamente: como la ventana "Conexión" de
  // Hattrick Control — una línea por fichero/jugador/partido a medida que
  // se descarga, no una espera muda de 15-20s. NDJSON sobre `fetch`, no
  // `EventSource` (solo hace GET, y este endpoint es un POST): se lee el
  // body como stream y se parte por saltos de línea a mano.
  syncStream: async (teamId: number, onEvent: (event: SyncStreamEvent) => void): Promise<void> => {
    const doSync = () => fetch(`${BASE}/teams/${teamId}/sync/stream`, {
      method: "POST",
      credentials: "include",
    });
    let res = await doSync();
    if (res.status === 401 && await refreshSession()) res = await doSync();
    if (res.status === 401) expireLocalSession();
    if (!res.ok || !res.body) {
      let detail: unknown;
      try {
        detail = await res.json();
      } catch {
        detail = await res.text();
      }
      throw new ApiError(`${res.status} ${res.statusText}`, res.status, detail);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (line.trim()) onEvent(JSON.parse(line) as SyncStreamEvent);
      }
    }
    if (buffer.trim()) onEvent(JSON.parse(buffer) as SyncStreamEvent);
  },
  syncChanges: (teamId: number) =>
    request<LastSyncChanges>(`/teams/${teamId}/sync/changes`),
  changesHistory: (teamId: number, playerId?: number | null) =>
    request<ChangesHistory>(
      `/teams/${teamId}/changes/history${playerId == null ? "" : `?player_id=${playerId}`}`,
    ),
  syncMatchDetails: (teamId: number) =>
    request<MatchDetailsSyncResult>(`/teams/${teamId}/matches/details/sync`, {
      method: "POST",
    }),
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
  connectChpp: () => request<{ authorizeUrl: string }>(`/auth/chpp/connect`),
  rivalScouting: (
    teamId: number,
    rivalHtTeamId: number,
    logTsi: boolean,
    excludeKeeper: boolean,
    top11: boolean,
    includeCompetitive = true,
    includeFriendlies = true,
    pitchZoneScope: PitchZoneScope = "mixed",
  ) =>
    request<RivalScouting>(
      `/teams/${teamId}/rivals/${rivalHtTeamId}/scouting` +
        `?log_tsi=${logTsi}&exclude_keeper=${excludeKeeper}&top11=${top11}` +
        `&include_competitive=${includeCompetitive}&include_friendlies=${includeFriendlies}` +
        `&pitch_zone_scope=${pitchZoneScope}`,
    ),
  nextMatchAnalysis: (teamId: number) =>
    request<NextMatchAnalysis>(`/teams/${teamId}/next-match/analysis`),
  leagueComparison: (
    teamId: number,
    logTsi: boolean,
    excludeKeeper: boolean,
    top11: boolean,
  ) =>
    request<LeagueComparison>(
      `/teams/${teamId}/league/comparison` +
        `?log_tsi=${logTsi}&exclude_keeper=${excludeKeeper}&top11=${top11}`,
    ),
  leagueTeamOfWeek: (
    teamId: number, scope: "week" | "season", formation: Formation, round?: number,
  ) =>
    request<TeamOfTheWeek>(
      `/teams/${teamId}/league/team-of-the-week?scope=${scope}&formation=${formation}` +
        (round != null ? `&round=${round}` : ""),
    ),
  cup: (teamId: number) => request<Cup>(`/teams/${teamId}/cup`),
};

/* ── Types mirroring the backend DTOs ─────────────────────────────────────
   Regenerated from OpenAPI with `npm run gen:api`; kept by hand until the
   backend is running in CI. */

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
  tsi: number;
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

export interface SyncChange {
  category: string;
  summary: string;
}

export interface PlayerComparisonChange {
  key: string;
  label: string;
  abbreviation: string;
  before: number | boolean | null;
  current: number | boolean;
  delta: number | null;
  direction: "up" | "down" | "neutral";
}

export interface PlayerComparisonRow {
  htPlayerId: number;
  name: string;
  tsi: number;
  tsiDelta: number | null;
  salary: number;
  salaryDelta: number | null;
  isNew: boolean;
  changes: PlayerComparisonChange[];
}

export interface ChangeMetricSummary {
  key: string;
  label: string;
  abbreviation: string;
  upCount: number;
  upTotal: number;
  downCount: number;
  downTotal: number;
  net: number;
}

export interface ClubComparisonChange {
  key: string;
  label: string;
  before: number | null;
  current: number | null;
  beforeDisplay: string | null;
  currentDisplay: string | null;
  delta: number | null;
  changed: boolean;
  isGood: boolean | null;
}

export interface SyncResult {
  syncId: number;
  status: "completed" | "partial";
  snapshotsWritten: number;
  unchanged: number;
  errors: string[];
  changes: SyncChange[];
}

export interface SessionTeam {
  id: number;
  htTeamId: number;
  name: string;
  leagueName: string | null;
  seriesName: string | null;
  syncedAt: string | null;
  hasImportedData: boolean;
}

export interface SessionProfile {
  user: {
    id: number;
    htUserId: number | null;
    loginName: string | null;
  };
  connectionStatus: "active" | "revoked" | "missing";
  teams: SessionTeam[];
}

export type SyncStreamEvent =
  | { type: "progress"; message: string }
  | { type: "done"; result: SyncResult }
  | { type: "error"; message: string };

export interface LastSyncChanges {
  syncId: number | null;
  syncedAt: string | null;
  changes: SyncChange[];
  reportSyncId: number | null;
  reportSyncedAt: string | null;
  reportIsLatest: boolean;
  reportChanges: SyncChange[];
  playerRows: PlayerComparisonRow[];
  summary: ChangeMetricSummary[];
  clubChanges: ClubComparisonChange[];
}

export interface MatchDetailsSyncResult {
  matchesProcessed: number;
  snapshotsWritten: number;
  unchanged: number;
  errors: string[];
}

export interface PlayerDetailsSyncResult {
  playersProcessed: number;
  snapshotsWritten: number;
  errors: string[];
}

export interface TransfersHistorySyncResult {
  status: string;
  pagesFetched: number;
  transfersSeen: number;
  transfersNew: number;
  snapshotsWritten: number;
  errors: string[];
}

// 2026-08-05, pedido explícitamente: un jugador que ya no está en la
// plantilla actual (`roster()` en el backend, `left_team_at IS NULL`) trae
// una ficha reducida — nada de habilidades/posiciones/entrenamiento (no
// tiene sentido para alguien que ya no vemos), solo identidad y fechas. El
// saldo/ROI se pide aparte, del mismo endpoint que ya alimenta "Detalle" en
// Saldo por jugador (nunca se duplica ese cálculo).
export interface ExPlayerDetail {
  isExPlayer: true;
  htPlayerId: number;
  name: string;
  purchasedAt: string | null;
  leftTeamAt: string | null;
  soldAt: string | null;
}

export interface ActivePlayerDetail {
  isExPlayer: false;
  htPlayerId: number;
  name: string;
  team: { htTeamId: number; name: string };
  age: string;
  tsi: number;
  form: number;
  stamina: number;
  experience: number;
  salary: number;
  injuryLevel: number;
  countryId: number;
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
  // Progreso decimal real (p.ej. 5.62) cuando ya hay calibración observada
  // para la transición en la que está el jugador (ver /loyalty/calibration)
  // — `null` cuando no hay evidencia todavía, y la ficha usa el nivel
  // entero (`loyalty`) como respaldo.
  loyaltyDecimal: number | null;
  // Proyección de Resistencia, tabla Federación Ocerin — `null` sin
  // WorldContext propio o con la edad fuera de la tabla (17-36).
  staminaForecast: {
    seasonWeeks: (string | null)[];
    levels: number[];
    trainingPct: number;
    currentExpectedLevel: number | null;
  } | null;
  // "TT-ss" de cuándo entró al equipo (compra real o respaldo manual) —
  // ancla el punto más antiguo del radar. `null` si no hay ninguna fecha.
  joinedSeasonWeek: string | null;
  // "TT-ss" de la compra real (transfersteam.xml) — nunca el respaldo
  // manual, para no ponerle TT-ss a una fecha estimada.
  purchasedAtSeasonWeek: string | null;
  // Si el último partido con rating capturado cae en la semana actual.
  playedThisWeek: boolean;
  // null = playerdetails.xml nunca se ha pedido para este jugador (distinto
  // de "0 caps reales") — botón "Actualizar detalles de jugadores".
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

export interface Squad {
  teamId: number;
  teamName: string;
  currency: string;
  position: string | null;
  playerCount: number;
  totals: {
    averageAge: number;
    averageForm: number;
    averageExperience: number;
    averageTsi: number;
    totalTsi: number;
    averageSalary: number;
    totalSalary: number;
  };
  comparison: {
    mode: "previous_change" | "snapshot";
    baselineSyncId: number | null;
    baselineCapturedAt: string | null;
  };
  history: { syncId: number; capturedAt: string; snapshots: number }[];
  players: SquadPlayer[];
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
    structuralBalance: number;
    currency: string;
  } | null;
  training: {
    typeId: number;
    typeName: string;
    level: number;
    staminaPart: number;
    trainerName: string;
    morale: number;
    moraleName: string;
    confidence: number;
    confidenceName: string;
  } | null;
  topSalaries: SquadPlayer[];
  alerts: { kind: string; severity: string; message: string }[];
}

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
    youthInvestment: number;
    youthLevel: number;
  } | null;
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

export interface Lineup {
  formation: string;
  totalRating: number;
  weather: string | null;
  formationRanking: Record<string, number>;
  lineup: {
    slot: number;
    position: string;
    label: string;
    player: string;
    htPlayerId: number;
    rating: number;
  }[];
  bench: { player: string; htPlayerId: number; tsi: number }[];
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

export interface NextMatchAnalysis {
  match: {
    htMatchId: number;
    date: string;
    matchType: number;
    matchTypeLabel: string;
    isHome: boolean;
    home: string;
    away: string;
    rivalHtTeamId: number;
    rivalName: string;
  } | null;
  message?: string;
  rival?: {
    htTeamId: number;
    name: string;
    matchesAnalysed: number;
    selectionMethod: string;
    condition: NextMatchCondition;
    probableLineup: {
      htPlayerId: number;
      name: string;
      positionCode: number | null;
      line: string;
      startsInSample: number;
      sampleSize: number;
      tsi: number;
      stamina: number | null;
      form: number | null;
      experience: number | null;
      ratingStars: number | null;
      ratingStarsEnd: number | null;
      ratingStarDrop: number | null;
    }[];
  };
  own?: {
    condition: NextMatchCondition;
    conditionSource: "submitted_orders" | "recommended_lineup";
    submittedOrders: {
      matchId: number;
      capturedAt: string | null;
      ratingsCapturedAt: string | null;
      tacticType: number | null;
      tacticSkill: number | null;
      ratings: {
        midfield: number | null;
        rightDef: number | null;
        centralDef: number | null;
        leftDef: number | null;
        rightAtt: number | null;
        centralAtt: number | null;
        leftAtt: number | null;
      };
      lineup: {
        htPlayerId: number;
        name: string;
        position: string;
        roleId: number;
        behaviour: number;
        behaviourLabel: string;
        stamina: number;
        form: number;
        experience: number;
      }[];
    } | null;
    formation: {
      formation: string;
      totalRating: number;
      ranking: Record<string, number>;
      lineup: {
        htPlayerId: number;
        name: string;
        position: string;
        stamina: number;
        form: number;
        experience: number;
        rating: number;
      }[];
    } | null;
  };
  dataFreshness?: string;
  notes?: string[];
}

export interface TrainingForecast {
  trainingType: number | null;
  trainedSkill: string | null;
  exposure: number;
  players: {
    player: string;
    htPlayerId: number;
    age: string;
    currentLevel: number;
    weeksToPop: number;
  }[];
}

export interface PostMatchTrainingOption {
  trainingType: number;
  name: string;
  trainedSkill: string | null;
  recommendable: boolean;
  rationale: string[];
  score: number;
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

export interface Insight {
  key: string;
  severity: "info" | "opportunity" | "warning" | "danger";
  title: string;
  detail: string;
  action: string;
  module: string;
  evidence: Record<string, unknown>;
}

/** Points per experience level, measured rather than declared. `source` says
 *  whether the figure comes from observation or is still the configured prior. */
export interface ExperienceModel {
  pointsPerLevel: number;
  configuredPointsPerLevel: number;
  observedMean: number | null;
  standardDeviation: number | null;
  observations: number;
  source: "configured" | "observed" | "blended";
  confidenceInterval: [number, number] | null;
  byLevel: Record<string, number>;
  matchPoints: Record<string, number>;
  verified: string[];
  fromSpec: string[];
  observationsNeeded: number;
  crossingsSeen: number;
  discardedCrossings: number;
  distinctReadings: number;
  levelUps: {
    player: string;
    fromLevel: number;
    toLevel: number;
    pointsAccumulated: number;
  }[];
  reference: CalculationReference;
}

/** Días reales por transición de Fidelidad (N→N+1), calibrados por
 *  observación propia — no hay valor configurado de partida como en
 *  Experiencia: cada transición sin observaciones simplemente no aparece
 *  en `transitions`. */
export interface LoyaltyModel {
  transitions: {
    fromLevel: number;
    toLevel: number;
    avgDays: number;
    observations: number;
    stdDev: number | null;
  }[];
  totalObservations: number;
  crossingsSeen: number;
  discardedCrossings: number;
  levelUps: {
    player: string;
    fromLevel: number;
    toLevel: number;
    daysElapsed: number;
  }[];
  reference: CalculationReference;
}

export interface CalculationReference {
  implementation: string;
  status: "ported" | "structural" | "pending";
  source_files: string[];
  recovered: string;
  pending: string;
  numeric_profile?: string;
}

export interface PositionModel {
  positions: number;
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

export interface HistoricalPlayerChange {
  capturedAt: string;
  htPlayerId: number;
  name: string;
  key: string;
  label: string;
  before: number;
  current: number;
  delta: number;
}

export interface ChangesHistory {
  players: { htPlayerId: number; name: string }[];
  selectedPlayerId: number | null;
  skillChanges: HistoricalPlayerChange[];
  experienceChanges: HistoricalPlayerChange[];
  formChanges: HistoricalPlayerChange[];
  series: {
    capturedAt: string;
    tsi: number;
    salary: number;
    form: number;
    experience: number;
    stamina: number;
  }[];
}

// ── Economía ────────────────────────────────────────────────────────────────

export interface ForecastBand {
  weeks: number[];
  p10: number[];
  p50: number[];
  p90: number[];
  model: string;
  backtestMae: number | null;
  candidates: Record<string, number>;
  /** "TT-ss" (temporada-semana, p. ej. "83-05") por cada entrada de `weeks`.
   * Null en cada una si el equipo todavía no sincronizó worlddetails.xml. */
  weekLabels: (string | null)[];
}

/** Desglose de Detalles al estilo Hattrick Control — SubTotal es lo
 * recurrente/estructural de la semana, Otros lo ligado a compraventa de
 * jugadores o algo puntual. Cualquier campo puede ser null: "sin dato",
 * nunca un 0 fabricado (p. ej. el primer sync de un club no trae desglose
 * de la semana ya cerrada). */
export interface IncomeBreakdown {
  spectators: number | null;   // Aficionados
  sponsors: number | null;      // Patrocinados (incl. bono en la semana en curso)
  financial: number | null;      // Financieros
  subtotal: number | null;
  other: number | null;             // Venta de jugadores + comisión + temporal
  total: number | null;
}

export interface CostsBreakdown {
  arena: number | null;      // Estadio (mantenimiento)
  players: number | null;      // Jugadores (sueldos)
  financial: number | null;      // Financieros (lo más parecido a "Intereses" de HC)
  staff: number | null;             // Empleados
  youth: number | null;               // Canteranos
  subtotal: number | null;
  other: number | null;                  // Compra de jugadores + construcción + temporal
  total: number | null;
}

export interface WeeklyBreakdownRow {
  seasonWeek: string | null;
  date: string;
  /** La semana en curso todavía no cerró — Hattrick puede seguir sumando ahí. */
  isCurrent: boolean;
  income: IncomeBreakdown;
  costs: CostsBreakdown;
}

export interface SeasonBreakdownTotals {
  season: number;
  income: IncomeBreakdown;
  costs: CostsBreakdown;
}

export interface Economy {
  teamName: string;
  currency: string;
  cash: number;
  expectedCash: number;
  weeklyBalance: number;
  structuralBalance: number;
  weeksOfHistory: number;
  series: {
    date: string;
    /** "TT-ss" (temporada-semana, p. ej. "83-05") — null si el equipo
     * todavía no sincronizó worlddetails.xml. */
    seasonWeek: string | null;
    cash: number;
    income: number;
    costs: number;
    balance: number;
    isAnomaly: boolean;
  }[];
  weeklyFinance: {
    income: { code: string; label: string; amount: number | null }[];
    costs: { code: string; label: string; amount: number | null }[];
    incomeTotal: number;
    costsTotal: number;
    expectedBalance: number;
  };
  /** Mismas categorías que `weeklyFinance`, sumando la semana en curso con
   * cada vez más semanas ya cerradas — para el Sankey de varias semanas. */
  sankeyWindows: {
    weeks: number;
    weeksAvailable: number;
    income: { code: string; label: string; amount: number | null }[];
    costs: { code: string; label: string; amount: number | null }[];
  }[];
  balanceWindows: {
    label: string;
    weeksRequested: number;
    weeksAvailable: number;
    income: number | null;
    costs: number | null;
    balance: number | null;
    /** Ingresos − gastos sin compraventa de jugadores. Null si falta el
     * desglose de alguna semana del tramo. */
    balanceExclTransfers: number | null;
  }[];
  structuralForecast: ForecastBand;
  /** Null hasta que haya serie suficiente para validar un modelo temporal. */
  timeseriesForecast: ForecastBand | null;
  recommendedModel: string;
  recommendationReason: string;
  anomalies: string[];
  /** Detalles: más reciente primero (al revés que `series`, que va
   * ascendente porque alimenta gráficos). */
  weeklyBreakdown: WeeklyBreakdownRow[];
  seasonBreakdownTotals: SeasonBreakdownTotals[];
  /** Umbral real para activar el modelo de series de tiempo — usar este
   * valor para el teaser de progreso en Proyección, no copiarlo a mano. */
  minWeeksForTimeseries: number;
}

// ── Estadio ─────────────────────────────────────────────────────────────────

export interface Arena {
  teamName: string;
  currency: string;
  capacityTotal: number;
  /** Si es false, la capacidad por sector se dedujo de las ventas y un lleno
   *  es indetectable: `demandIsCensored` no se puede evaluar. */
  capacityIsReal: boolean;
  matchesAnalysed: number;
  avgOccupancy: number;
  totalRevenue: number;
  revenueLeftOnTable: number;
  sectors: {
    sector: string;
    label: string;
    capacity: number;
    soldAvg: number;
    occupancy: number;
    timesSoldOut: number;
    price: number;
    priceIsVerified: boolean;
    demandIsCensored: boolean;
  }[];
  matches: {
    date: string;
    matchType: number;
    capacity: number;
    sold: number;
    occupancy: number;
    revenue: number;
    soldOutSectors: string[];
    emptySeats: number;
    revenueLeft: number;
  }[];
  expansionOptions: {
    label: string;
    addedSeats: Record<string, number>;
    buildCost: number;
    addedWeeklyMaintenance: number;
    addedRevenuePerMatch: number;
    netPerSeason: number;
    paybackSeasons: number | null;
    verdict: string;
  }[];
  demandIsCensored: boolean;
  censoredSectors: string[];
  notes: string[];
}

// ── Partidos ────────────────────────────────────────────────────────────────

export interface MatchRow {
  htMatchId: number;
  date: string;
  matchType: number;
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
    left: number; center: number; right: number; special: number; other: number;
    total: number; goals: number; conversion: number;
  };
  opponentChances: {
    left: number; center: number; right: number; special: number; other: number;
    total: number; goals: number; conversion: number;
  };
}

// ── Liga y predicciones ─────────────────────────────────────────────────────

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
  // combinada — estas se calculan desde los resultados reales de cada
  // partido (ver `_standings_from_matches` en el backend).
  standingsHome: LeagueStandingRow[];
  standingsAway: LeagueStandingRow[];
  /** Historial real de posición/puntos por jornada sincronizada — cada sync
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
   * re-simulado goleando o siendo goleado en lo propio — el resto de la
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
}

// ── Juveniles ───────────────────────────────────────────────────────────────

export interface Academy {
  teamName: string;
  currency: string;
  squadSize: number;
  players: {
    htYouthPlayerId: number;
    name: string;
    ageYears: number;
    ageDays: number;
    potentialScore: number;
    category: string;
    bestSkill: string;
    bestSkillMax: number | null;
    daysUntilDeadline: number;
    weeksUntilDeadline: number;
    revealedSkills: number;
    verdictIsProvisional: boolean;
    promoteAdvice: string;
    trainingExposure: number;
    skills: {
      skill: string;
      current: number;
      maximum: number | null;
      isRevealed: boolean;
      headroom: number;
    }[];
  }[];
  graduates: {
    name: string;
    promotedAt: string | null;
    soldAt: string | null;
    soldFor: number | null;
    currentTeam: string | null;
    currentTsi: number | null;
  }[];
  invested: number;
  earned: number;
  net: number;
  seasons: number;
  weeklyCost: number;
  breakEvenSales: number;
  roiVerdict: string;
  urgent: string[];
  notes: string[];
}

// ── Saldo neto por jugador ───────────────────────────────────────────────────

export interface PlayerBalanceRow {
  htPlayerId: number;
  name: string;
  isAcademyGraduate: boolean;
  isPurchasePriceManual: boolean;
  purchasePrice: number | null;
  purchasedAt: string | null;
  salePrice: number | null;
  soldAt: string | null;
  salaryTotal: number;
  salaryBreakdown: { weeks: number; salary: number; season: string }[];
  listingCount: number;
  listingAttempts: { highestBid: number | null; detectedAt: string }[];
  listingCost: number;
  agentPct: number | null;
  // HL-161, 2026-08-14: comisión de club anterior EXACTA (partidos reales
  // jugados con nosotros × tabla oficial de Hattrick) — 0 si el club al
  // que se lo vendimos todavía no lo ha revendido. Reemplaza el reparto
  // heurístico "de origen desconocido" que existía antes.
  resaleBonusShare: number;
  saldo: number | null;
  isSold: boolean;
  trainingAtSale: string | null;
  seasonAtSale: string | null;
  topSkillAtSale: string | null;
  bidHourAtSale: string | null;
  nativeCountry: string;
  character: string;
  specialty: string;
  tsiAtPurchase: number | "?";
  tsiAtSale: number | "?";
  deltaTsi: number | "?";
  commissionAmount: number | "?";
  roiPct: number | "?";
  destinationCountry: string;
  ageAtSale: number | "?";
  // 2026-08-05: tabla "Detalle" de 43 columnas.
  ageAtPurchase: number | "?";
  experienceAtPurchase: number | "?";
  leadershipAtPurchase: number | "?";
  formAtPurchase: number | "?";
  staminaAtPurchase: number | "?";
  keeperAtPurchase: number | "?";
  defendingAtPurchase: number | "?";
  playmakingAtPurchase: number | "?";
  wingerAtPurchase: number | "?";
  passingAtPurchase: number | "?";
  scoringAtPurchase: number | "?";
  setPiecesAtPurchase: number | "?";
  experienceAtSale: number | "?";
  formAtSale: number | "?";
  staminaAtSale: number | "?";
  keeperAtSale: number | "?";
  defendingAtSale: number | "?";
  playmakingAtSale: number | "?";
  wingerAtSale: number | "?";
  passingAtSale: number | "?";
  scoringAtSale: number | "?";
  setPiecesAtSale: number | "?";
  daysSincePurchase: number | "?";
  saldoPerDeltaTsi: number | "?";
  isDepartureWithoutSale: boolean;
}

export interface PlayerBalance {
  teamName: string;
  currency: string;
  players: PlayerBalanceRow[];
  totalSaldo: number;
  unknownPurchaseCount: number;
  byTrainingType: Record<string, number>;
  bySeason: Record<string, number>;
  byAgeBucket: Record<string, number>;
  byTopSkill: Record<string, number>;
  byBidHour: Record<string, number>;
  // HL-161, 2026-08-04: <Stats> de transfersteam.xml — TODA la historia de
  // compraventas del equipo, para los KPI de "Resumen".
  transferTotalBuys: number;
  transferTotalSales: number;
  transferNumberBuys: number;
  transferNumberSales: number;
}

// ── Cierre de la fórmula de entrenamiento ────────────────────────────────────

export interface FormulaInput {
  value: number | string | boolean;
  source: string; // "club.xml" | "training.xml" | "stafflist.xml" | "supuesto"
  isRead: boolean; // leído del CHPP, o todavía un supuesto
  note: string;
}

// ── Scouting de rivales ──────────────────────────────────────────────────────

/** Alcance del panel de Duelos por zona — independiente de los toggles
 * globales de la página. "mixed" hereda esos toggles tal cual (comportamiento
 * por defecto); "official"/"friendly" los ignoran y piden en vivo un
 * recorte propio de hasta 5 partidos del rival de ese tipo exacto. */
export type PitchZoneScope = "mixed" | "official" | "friendly";

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

export interface RivalScouting {
  rivalHtTeamId: number;
  rivalName: string | null;
  matchesAnalysed: number;
  /** TSI, forma, condición y experiencia son públicas de un rival (CHPP
   * expone esos campos aunque oculte las skills exactas). El liderazgo del
   * entrenador rival sale de su stafflist.xml v1.2 (público para cualquier
   * equipo) o, si eso no trajera nada, de su jugador-entrenador en
   * players.xml — `null` solo si ninguna de las dos fuentes tiene dato. */
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
    excludedKeeper: boolean;
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
     * EN ESE partido — 100% es "siempre el mismo lado, sin excepción". */
    dominantPct: number;
    dominantSideByMatch: string[];
    rotates: boolean;
    matchesAnalysed: number;
  } | null;
  /** 7 duelos cabeza a cabeza por carril de la cancha, de los mismos
   * partidos ya analizados arriba — el rival en vivo, el propio equipo de
   * MatchRating ya sincronizado. `null` si falta alguno de los dos lados
   * (nunca se inventa un duelo con un solo lado real). */
  pitchZoneDuels: PitchZoneDuel[] | null;
  pitchZonesMatchesAnalysed: { own: number | null; rival: number | null };
  pitchZoneSources: { own: PitchZoneSource; rival: PitchZoneSource };
  pitchZoneScope: PitchZoneScope;
  rivalRosterSample: { name: string; position: string | null; tsi: number }[];
  winProbability: {
    ownProbability: number;
    ownTsiTotal: number;
    rivalTsiTotal: number;
    confidence: string;
  };
  /** Táctica, nivel de táctica y formación — los tres son públicos para
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
    mostCommonFormation: { formation: string; count: number; pct: number } | null;
  } | null;
  caveats: string[];
}

// ── Comparativa de liga ───────────────────────────────────────────────────────

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
  // plantilla comparada — null cuando CHPP no mostró el dato para un rival.
  topPlayerName: string | null;
  topPlayerTsi: number | null;
  topPlayerLastPosition: string | null;
  avgForm: number | null;
  avgStamina: number | null;
}

export interface LeagueComparison {
  seriesName: string;
  teamsInSeries: number;
  ownRank: number;
  ranking: LeagueTeamSummary[];
  tsiHistogram: {
    grid: number[];
    ownDensity: number[];
    rivalDensity: number[];
    ownValues: number[];
    rivalValues: number[];
    logTransform: boolean;
    excludedKeeper: boolean;
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
// solo bloque "medios", y laterales/centrales comparten "defensa" — el
// selector de formación decide cuántos cupos tiene cada bloque, igual que
// Hattrick Control (nunca un reparto fijo).
export type TeamOfWeekSlotKey = "keeper" | "defense" | "midfield" | "forward";

export const FORMATIONS = [
  "4-4-2", "3-5-2", "3-4-3", "4-5-1", "4-3-3", "5-3-2", "5-4-1",
] as const;
export type Formation = (typeof FORMATIONS)[number];

export interface TeamOfTheWeek {
  scope: "week" | "season";
  formation: Formation;
  formations: Formation[];
  matchRound: number | null;
  availableRounds: number[];
  roundsCovered: number;
  lineupsFound: number;
  lineupsExpected: number;
  slotLabels: Record<TeamOfWeekSlotKey, string>;
  positions: Record<TeamOfWeekSlotKey, TeamOfWeekPlayer[]>;
  totalStars: number;
  caveats: string[];
}

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

export interface CupPrizeStage {
  stage: string;
  amount: number;
  roundsFromTitle: number;
  status: "passed" | "current" | "future";
  winsNeeded: number | null;
  trophyOnly: boolean;
}

export interface TeamSpiritMultiplier {
  rows: { spirit: string; pic: number; normal: number; mots: number }[];
  note: string;
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
    roundsLeft: number | null;
    stageLabel: string | null;
    nextCupMatchDate: string | null;
  };
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
    observedGrossGate: number;
    estimatedHistoricalShare: number;
    nextGateProjection: number | null;
    nextSharePercent: number | null;
    projectionBasis: string;
    qualityNote: string;
  };
  readiness: {
    referenceVariants: CupReadinessVariant[];
    defaultMode: "top_tsi" | "last_cup" | "last_league";
    penaltyCandidates: CupPenaltyCandidate[];
    goalkeeper: { htPlayerId: number; name: string; keeper: number } | null;
    penaltyMethod: string;
  };
  ladder: CupLadderStep[];
  history: CupHistoryRow[];
  nextMatches: CupNextMatch[];
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
  mode: "top_tsi" | "last_cup" | "last_league";
  label: string;
  sourceMatchId: number | null;
  sourceOpponent: string | null;
  sourceDate: string | null;
  averageStamina: number | null;
  staminaBands: { label: string; min: number; max: number; count: number }[];
  startersCount: number;
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

export interface TrainingFormula {
  trainedSkill: string;
  allRead: boolean;
  formula: string;
  inputs: Record<string, FormulaInput>;
  setup: {
    skill: string;
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
  htPlayerId: number;
  name: string;
  nativeCountry: string | null;
  age: string;
  level: number;
  levelName: string;
  weeksElapsed: number | null;
  weeksTotal: number;
  progressPct: number | null;
  hasReference: boolean;
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
