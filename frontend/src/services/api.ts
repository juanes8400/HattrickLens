/**
 * HT Lens API client.
 *
 * UI_GUIDELINES.md: business rules must not live in React components. This
 * module only transports data; every number it returns was computed by an
 * engine on the server.
 */
// En desarrollo usamos el proxy de Vite (`/api` → backend). Mantener la
// petición en el mismo origen evita que `localhost` y `127.0.0.1` creen
// sesiones distintas o que el navegador bloquee la llamada entre puertos.
// Los despliegues pueden seguir definiendo VITE_API_URL explícitamente.
const BASE = import.meta.env.VITE_API_URL ?? "/api/v1";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly detail?: unknown,
  ) {
    super(message);
  }
}

/**
 * Mensaje legible de cualquier error: desenvuelve el `detail` de FastAPI, que
 * a veces llega como string y a veces como `{detail: "..."}`. Vive aquí (y no
 * en una pantalla) porque lo necesitan todas las que disparan mutaciones.
 */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const detail = error.detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "detail" in detail) {
      const inner = (detail as { detail: unknown }).detail;
      if (typeof inner === "string") return inner;
    }
    return error.message;
  }
  return error instanceof Error ? error.message : "Error desconocido.";
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
  const mayRefresh =
    path !== "/auth/chpp/refresh" && path !== "/auth/chpp/connect";
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
  lineup: (
    teamId: number,
    formation?: string,
    centralDefenders?: number,
    innerMidfielders?: number,
    /** Ordenes fijadas a mano: casilla -> posicion con orden. Las que no
     *  esten aqui las elige el motor. */
    orders?: Record<number, string>,
  ) => {
    const q = new URLSearchParams();
    if (formation) q.set("formation", formation);
    if (centralDefenders != null) q.set("central_defenders", String(centralDefenders));
    if (innerMidfielders != null) q.set("inner_midfielders", String(innerMidfielders));
    const fijadas = Object.entries(orders ?? {});
    if (fijadas.length > 0) {
      q.set("orders", fijadas.map(([slot, pos]) => `${slot}:${pos}`).join(","));
    }
    const qs = q.toString();
    return request<Lineup>(`/teams/${teamId}/lineup${qs ? `?${qs}` : ""}`);
  },
  lineupHindsight: (teamId: number) =>
    request<LineupHindsight>(`/teams/${teamId}/lineup/hindsight`),
  teamSpiritMultiplier: (teamId: number) =>
    request<TeamSpiritMultiplier>(`/teams/${teamId}/lineup/team-spirit`),
  trainingForecast: (teamId: number) =>
    request<TrainingForecast>(`/teams/${teamId}/training/forecast`),
  postMatchTraining: (teamId: number) =>
    request<PostMatchTraining>(`/teams/${teamId}/training/post-match`),
  teamOverview: (teamId: number) => request<TeamOverview>(`/teams/${teamId}/overview`),
  insights: (teamId: number) => request<Insight[]>(`/teams/${teamId}/insights`),
  archivedInsights: (teamId: number) =>
    request<ArchivedInsight[]>(`/teams/${teamId}/insights/archived`),
  archiveInsight: (teamId: number, key: string) =>
    request<{ key: string; archived: boolean }>(
      `/teams/${teamId}/insights/${encodeURIComponent(key)}/archive`,
      { method: "POST" },
    ),
  restoreInsight: (teamId: number, key: string) =>
    request<{ key: string; archived: boolean }>(
      `/teams/${teamId}/insights/${encodeURIComponent(key)}/archive`,
      { method: "DELETE" },
    ),
  positionModel: () => request<PositionModel>(`/teams/positions/model`),
  experienceModel: (teamId: number) =>
    request<ExperienceModel>(`/teams/${teamId}/experience/calibration`),
  loyaltyModel: (teamId: number) =>
    request<LoyaltyModel>(`/teams/${teamId}/loyalty/model`),
  economy: (teamId: number, horizonWeeks = 52) =>
    request<Economy>(`/teams/${teamId}/economy?horizon_weeks=${horizonWeeks}`),
  arena: (teamId: number, fillRate?: number) => {
    const q = new URLSearchParams();
    if (fillRate != null) q.set("fill_rate", String(fillRate));
    const qs = q.toString();
    return request<Arena>(`/teams/${teamId}/arena${qs ? `?${qs}` : ""}`);
  },
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
  league: (teamId: number, runs = 10000) =>
    request<League>(`/teams/${teamId}/league?runs=${runs}`),
  academy: (teamId: number) => request<Academy>(`/teams/${teamId}/academy`),
  academyScouts: (teamId: number) =>
    request<AcademyScouts>(`/teams/${teamId}/academy/scouts`),
  playerBalance: (teamId: number, season?: string) => {
    const params = new URLSearchParams();
    if (season && season !== "all") params.set("season", season);
    const qs = params.toString();
    return request<PlayerBalance>(
      `/teams/${teamId}/player-balance${qs ? `?${qs}` : ""}`,
    );
  },
  syncPurchasePrices: (teamId: number) =>
    request<PlayerDetailsSyncResult>(
      `/teams/${teamId}/players/purchase-price/sync`,
      {
        method: "POST",
      },
    ),
  syncTransfersHistory: (teamId: number) =>
    request<TransfersHistorySyncResult>(`/teams/${teamId}/transfers/sync`, {
      method: "POST",
    }),
  /** Cuantas fichas quedan por descargar. No llama a Hattrick: solo lee la base. */
  backfillPending: (teamId: number) =>
    request<BackfillPending>(`/teams/${teamId}/backfill`),
  /** Un lote y para. Devuelve cuantos atendio y cuantos quedan.
   *  `since` es el momento en que se pulso: acota la vigilancia de reventas a
   *  una sola pasada, porque esa cola no se agota sola. */
  runBackfillBatch: (teamId: number, since?: string) =>
    request<BackfillBatchResult>(
      `/teams/${teamId}/backfill/run${since ? `?since=${encodeURIComponent(since)}` : ""}`,
      { method: "POST" },
    ),
  /** Cada intento de venta, con su final. */
  transferAttempts: (teamId: number) =>
    request<TransferAttempts>(`/teams/${teamId}/transfer-attempts`),
  /** El resumen de uso. Sólo lo abre el administrador. */
  usage: (dias = 30) => request<UsageSummary>(`/usage?dias=${dias}`),
  /** Anota cuantas veces vieron al jugador, o ignora la pregunta. */
  setTimesSeen: (
    teamId: number,
    attemptId: number,
    cambios: {
      times_seen?: number;
      asking_price?: number;
      dismissed?: boolean;
    },
  ) =>
    request<{
      id: number;
      timesSeen: number | null;
      askingPrice: number | null;
      asked: boolean;
    }>(
      `/teams/${teamId}/transfer-attempts/${attemptId}`,
      { method: "PATCH", body: JSON.stringify(cambios) },
    ),
  /** Borra un intento de venta. Distinto de "no tener en cuenta". */
  deleteTransferAttempt: (teamId: number, attemptId: number) =>
    request<{ deleted: number }>(
      `/teams/${teamId}/transfer-attempts/${attemptId}`,
      { method: "DELETE" },
    ),
  /** Atribuye a mano lo que falta de una etapa cerrada, o la excluye. */
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
  sync: (teamId: number) =>
    request<SyncResult>(`/teams/${teamId}/sync`, { method: "POST" }),
  // 2026-08-05, pedido explícitamente: como la ventana "Conexión" de
  // Hattrick Control — una línea por fichero/jugador/partido a medida que
  // se descarga, no una espera muda de 15-20s. NDJSON sobre `fetch`, no
  // `EventSource` (solo hace GET, y este endpoint es un POST): se lee el
  // body como stream y se parte por saltos de línea a mano.
  syncStream: async (
    teamId: number,
    onEvent: (event: SyncStreamEvent) => void,
  ): Promise<void> => {
    const doSync = () =>
      fetch(`${BASE}/teams/${teamId}/sync/stream`, {
        method: "POST",
        credentials: "include",
      });
    let res = await doSync();
    if (res.status === 401 && (await refreshSession())) res = await doSync();
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
  syncChanges: (teamId: number, syncId?: number | null) =>
    request<LastSyncChanges>(
      `/teams/${teamId}/sync/changes${syncId == null ? "" : `?sync_id=${syncId}`}`,
    ),
  academySkillScores: (
    teamId: number,
    params: {
      soonMaxDays: number;
      weightBase: number;
      trainableMethod: string;
      trainable: Record<string, number>;
      /** `null` = que lo sugiera la escalera. */
      trainableWeight?: number | null;
    },
  ) => {
    const q = new URLSearchParams({
      soon_max_days: String(params.soonMaxDays),
      weight_base: String(params.weightBase),
      trainable_method: params.trainableMethod,
      ...(params.trainableWeight == null
        ? {}
        : { trainable_weight: String(params.trainableWeight) }),
      trainable: Object.entries(params.trainable)
        .filter(([, n]) => n > 0)
        .map(([skill, n]) => `${skill}:${n}`)
        .join(","),
    });
    return request<AcademySkillScores>(`/teams/${teamId}/academy/skill-scores?${q}`);
  },
  academyTrainingPlan: (
    teamId: number,
    params: { main: string; secondary: string; soonMaxDays: number; weightBase: number },
  ) => {
    const q = new URLSearchParams({
      main: params.main,
      secondary: params.secondary,
      soon_max_days: String(params.soonMaxDays),
      weight_base: String(params.weightBase),
    }).toString();
    return request<AcademyTrainingPlan>(`/teams/${teamId}/academy/training-plan?${q}`);
  },
  changesHistory: (teamId: number, playerId?: number | null, weeks?: number) => {
    const params = new URLSearchParams();
    if (playerId != null) params.set("player_id", String(playerId));
    if (weeks != null) params.set("weeks", String(weeks));
    const query = params.toString();
    return request<ChangesHistory>(
      `/teams/${teamId}/changes/history${query ? `?${query}` : ""}`,
    );
  },
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
    top11: boolean,
    includeCompetitive = true,
    includeFriendlies = true,
    pitchZoneScope: PitchZoneScope = "mixed",
    pitchZoneMethodOwn: PitchZoneMethod = "submitted",
    pitchZoneMethodRival: PitchZoneMethod = "average",
  ) =>
    request<RivalScouting>(
      `/teams/${teamId}/rivals/${rivalHtTeamId}/scouting` +
        `?log_tsi=${logTsi}&top11=${top11}` +
        `&include_competitive=${includeCompetitive}&include_friendlies=${includeFriendlies}` +
        `&pitch_zone_scope=${pitchZoneScope}&pitch_zone_method_own=${pitchZoneMethodOwn}` +
        `&pitch_zone_method_rival=${pitchZoneMethodRival}`,
    ),
  leagueComparison: (
    teamId: number,
    logTsi: boolean,
    top11: boolean,
  ) =>
    request<LeagueComparison>(
      `/teams/${teamId}/league/comparison` +
        `?log_tsi=${logTsi}&top11=${top11}`,
    ),
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
        (centralDefenders != null ? `&central_defenders=${centralDefenders}` : "") +
        (innerMidfielders != null ? `&inner_midfielders=${innerMidfielders}` : ""),
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

/** Cómo pintar el par antes/después de un cambio — ver `Change.kind` en
 *  `sync_diff.py`. */
export type SyncChangeKind = "count" | "money" | "skill" | "level" | "event";

/**
 * El mismo cambio como DATO, no como frase. Desde 2026-08-15 el backend lo
 * guarda junto al `summary` para que la UI no tenga que sacar los números del
 * texto con una regex — eso fue lo que rompió al unificar el separador de
 * miles (`Number("202.210")` = 202,21, y se mostró "TSI 202").
 */
export interface SyncChangeDetail {
  metric?: string;
  label?: string;
  subject?: string;
  before?: number;
  after?: number;
  beforeLabel?: string;
  afterLabel?: string;
  kind?: SyncChangeKind;
  good?: boolean;
  currency?: string;
}

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

/** Una plaza del once juvenil y qué entrenamiento le llega ahí. */
export interface NivelLeido {
  label: string;
  current: number | null;
  maximum: number | null;
  maxReached: boolean;
}

export interface TrainingSlot {
  player: string;
  puesto: string;
  /** ambos · solo_principal · solo_secundaria · sin_entrenamiento */
  region: string;
  /** 100, 50 o 0. */
  racionPrincipal: number;
  racionSecundaria: number;
  /** En qué peldaño de la cola venía, de 1 a 9. */
  peldano: number;
  /** Por qué habilidad se le eligió: la principal o la secundaria. */
  elegidoPor: string;
  /** El nombre de esa habilidad, que es de la que habla la columna «Nivel». */
  skillLabel: string;
  /** El nivel de las DOS habilidades que se entrenan, no sólo la que le dio
   *  la plaza. */
  mainLevel: NivelLeido;
  secondaryLevel: NivelLeido;
  /** Las habilidades a las que el ojeador aún no les ha puesto techo: es lo
   *  único que queda por saber de él. */
  openCeilings: string[];
  /** Su edad hoy, en días, y lo que el ojeador dijo de esa habilidad. */
  ageDaysTotal: number;
  /** En qué se puede convertir, en HTMS28. La tabla enseña esto en vez de la
   *  edad, que va dentro del número. */
  htms28Min: number;
  htms28Max: number;
  current: number | null;
  maximum: number | null;
  maxReached: boolean;
}

export interface AcademyTrainingPlan {
  main: string;
  mainLabel: string;
  secondary: string;
  secondaryLabel: string;
  /** Cuántos reciben los dos entrenamientos a la vez. */
  doubleCount: number;
  /** De los que reciben doble, a cuántos no se les sabe nada de esa habilidad. */
  doubleBlind: number;
  /** Cuánto ha revelado el ojeador en toda la academia. */
  scouting: { known: number; total: number; blankPlayers: string[] };
  assignments: TrainingSlot[];
  /** El banquillo: los que no entraron, con su columna sugerida. */
  outside: (TrainingSlot & { benchColumn: string })[];
}

export interface SyncChange {
  category: string;
  summary: string;
  /** `null` en filas guardadas antes de 2026-08-15: para esas la UI cae al
   *  parser de compatibilidad de SyncChangesFeed.tsx. */
  detail?: SyncChangeDetail | null;
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

/** El resumen de uso de la aplicación. */
export interface UsageSummary {
  days: number;
  totals: {
    sessions: number;
    pages: number;
    clicks: number;
    minutes: number;
    medianSessionSeconds: number;
    clicksPerSession: number;
  };
  modules: {
    module: string;
    visits: number;
    clicks: number;
    minutes: number;
    avgSecondsPerVisit: number;
    lastSeen: string | null;
  }[];
  topControls: { label: string; clicks: number }[];
  byHour: Record<string, number>;
  recentSessions: {
    id: string;
    startedAt: string;
    seconds: number;
    pages: number;
    clicks: number;
    modules: string[];
  }[];
}

export interface SessionProfile {
  user: {
    id: number;
    htUserId: number | null;
    loginName: string | null;
    /** Si puede abrir la pantalla de uso. La comprobación de verdad está en el
     *  servidor; esto sólo decide si se enseña el enlace. */
    isAdmin: boolean;
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
  /** Partidos de selección jugados desde el informe anterior. */
  nationalMatches: NationalMatchAppearance[];
  /** Snapshots navegables — sólo los que tuvieron cambios reales, del más
   *  reciente al más antiguo. Elegir uno recalcula toda la comparación. */
  availableReports: { syncId: number; syncedAt: string; changeCount: number }[];
}

export interface NationalMatchAppearance {
  htPlayerId: number;
  name: string;
  minutes: number;
  rating: number | null;
  playedAt: string | null;
  competition: string;
  match: string;
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

export interface TransferAttemptRow {
  /** "483141997_2": el segundo intento de ese jugador. */
  key: string;
  id: number;
  attemptNumber: number;
  htPlayerId: number | null;
  name: string;

  detectedAt: string;
  /** Cuando cerro la puja. En un intento fallido no hay fecha de venta. */
  closedAt: string | null;
  open: boolean;
  sold: boolean;

  askingPrice: number | null;
  highestBid: number | null;
  salePrice: number | null;
  /** Solo en los exitosos. */
  agentPct: number | "?";
  timesSeen: number | null;
  asked: boolean;

  tsi: number | "?";
  age: string;
  skills: Record<string, number | "?">;
  specialty: string;
  character: string;
  nativeCountry: string;
  /** Para pintar la bandera. */
  nativeCountryCode: string | null;
  snapshotAt: string | null;
  /** La foto esta lejos del cierre: no leerla como exacta. */
  stale: boolean;

  fromAcademy: boolean;
  purchasedAt: string | null;
  purchasePrice: number | "?";
  ageAtPurchase: string;
  daysSincePurchase: number | "?";
  salaryToDate: number | "?";
  trainingThatWeek: string;
}

export interface TransferAttempts {
  currency: string;
  rows: TransferAttemptRow[];
  /** Los que terminaron y siguen sin respuesta. */
  pendingQuestion: TransferAttemptRow[];
}

export interface BackfillPending {
  /** Jugadores a los que les falta algo por descargar. */
  pending: number;
  batchSize: number;
  detail: {
    profile: number;
    purchasePrice: number;
    destination: number;
    /** A cuantos hay que construirles el historial completo esta primera vez. */
    census: number;
    /** Cuantos siguen pudiendo darnos comision algun dia. */
    resaleWatch: number;
  };
}

/** El recorrido de un barrido de comisiones. El eje se congela al empezar,
 *  así que una posición significa lo mismo de la primera pulsación a la
 *  última. */
export interface QueueMap {
  /** Casillas del eje: el ancho de la barra. */
  total: number;
  /** Posiciones ya atendidas. Se pintan como marcas. */
  done: number[];
  /** Casillas seguidas desde la izquierda: el bloque sólido. */
  front: number;
}

/** Cómo queda la vigilancia cuando el barrido para. */
export interface SweepBalance {
  /** Expedientes vivos: aún pueden dar comisión. */
  open: number;
  /** De este barrido, los que se quedaron sin mirar. */
  toCheck: number;
  /** Zanjados en este barrido, por motivo. */
  closed: Record<string, number>;
  closedTotal: number;
  /** Comisiones atribuidas durante este barrido. */
  commissions: number;
}

export interface BackfillBatchResult {
  status: string;
  /** Jugadores atendidos en este lote. */
  done: number;
  /** Los que siguen esperando. */
  pending: number;
  /** Apellidos de los atendidos, para decir por quien va. */
  players: string[];
  /** El mapa del barrido de comisiones, para pintar la barra como un
   *  recorrido por la cola. Llega entero en cada respuesta. */
  queue: QueueMap | null;
  /** El resumen para enseñar al parar. */
  balance: SweepBalance | null;
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
  // Proyección de Resistencia, tabla Federación Ocerin — `null` solo sin
  // WorldContext propio. Las edades fuera de la tabla (17-36) usan la fila
  // del extremo más cercano, así que ya no cortan la proyección.
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
  /** Los once de más TSI. */
  top11Tsi: number;
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
    structuralBalance: number;
  /** Las dos semanas ya cerradas: cubren siempre un partido en casa. */
  biweeklyBalance: number;
  biweeklyIncome: number;
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
    morale: number;
    moraleName: string;
    confidence: number;
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
    // `CostsYouth` (economy.xml), no del `<Investment>` de club.xml — ese
    // campo Hattrick lo devuelve en 0 aunque el club sí esté invirtiendo
    // (verificado con un fetch en vivo 2026-08-15). `null` si todavía no
    // hay una lectura económica sincronizada.
    youthInvestment: number | null;
    youthInvestmentCurrency: string;
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
    /** La casilla de la formacion, sin la orden. */
    basePosition: string;
    /** True cuando la orden la fijo el usuario, no el motor. */
    orderPinned: boolean;
    /** Las ordenes que Hattrick permite en esa casilla. */
    orderOptions: { position: string; label: string }[];
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

/**
 * Sección Equipo: la plantilla promediada por grupos. Cada grupo dice con
 * qué forma se PUEDE dibujar — `radar` sólo cuando todas sus métricas
 * comparten escala; si no, barras con el techo propio de cada una.
 */
export interface TeamOverviewMetric {
  key: string;
  label: string;
  value: number;
  scaleMax: number;
  display: "level" | "money" | "number" | "count" | "ratio";
  valueLabel: string | null;
}

export interface TeamOverviewSeries {
  key: string;
  label: string;
  /** Un valor por semana, alineado con `weeks`. `null` = semana sin lectura;
   *  nunca se rellena con ceros ni se interpola. */
  values: (number | null)[];
  /** "decimal" es un número con decimales que no es dinero ni un nivel de 0 a
   *  20: la edad media de la plantilla, por ejemplo. */
  display: "level" | "money" | "number" | "count" | "ratio" | "decimal";
}

/** Una gráfica dentro de un grupo. Un grupo lleva varias cuando sus series no
 *  comparten escala — juntarlas en un eje daría a entender que se comparan. */
export interface TeamOverviewChart {
  key: string;
  title: string;
  scaleMin: number | null;
  scaleMax: number | null;
  /** Sombrea el hueco entre las dos series. El backend solo lo marca cuando
   *  ambas miden lo MISMO sobre poblaciones distintas (plantilla contra el
   *  once de más TSI), de modo que el área entre ellas es una cantidad real. */
  band: boolean;
  series: TeamOverviewSeries[];
}

/**
 * Una línea de la cancha, con dos lecturas que NO son la misma población:
 * `bestRating`/`topPlayer`/`bestVariantLabel` salen de evaluar a TODA la
 * plantilla en las variantes de esa línea, mientras que `count` y
 * `averageRating` miran solo a quienes la tienen como su mejor puesto.
 * `count` puede ser 0 y aun así haber un mejor rating — una línea que nadie
 * ocupa de forma natural pero alguien podría cubrir. Se pintan en bloques
 * separados justamente para no confundirlas.
 */
export interface TeamOverviewPitchSlot {
  key: string;
  label: string;
  count: number;
  bestRating: number | null;
  topPlayer: string | null;
  bestVariantLabel: string | null;
  averageRating: number | null;
}

/** Capitán y lanzador de faltas: recomendaciones de rol, no puestos. Su
 *  `rating` NO está en la escala 0-20 de las posiciones — el motor los puntúa
 *  con otra fórmula —, así que se muestra como número pelado, sin barra. */
export interface TeamOverviewSpecialRole {
  key: string;
  label: string;
  topPlayer: string | null;
  rating: number | null;
}

export interface TeamOverviewGroup {
  key: string;
  label: string;
  /** `pending` = la pestaña existe pero su contenido está por definir. */
  chart: "line" | "bars" | "pitch" | "pending";
  pitch: TeamOverviewPitchSlot[];
  specialRoles: TeamOverviewSpecialRole[];
  note: string;
  weeks: string[];
  charts: TeamOverviewChart[];
  metrics: TeamOverviewMetric[];
}

export interface TeamOverview {
  teamName: string;
  playerCount: number;
  currency: string;
  groups: TeamOverviewGroup[];
}

/** "Qué entrenar" recalculado con los parámetros que elija el usuario. El
 *  método es fijo; estos tres números son opiniones. */
export interface AcademySkillScores {
  soonMaxDays: number;
  weightBase: number;
  trainableMethod: string;
  /** El peso que la base da a cada cubo — se pinta sobre su columna. */
  weights: Record<string, number>;
  /** El que sugiere la escalera (peldaño -2 de la base). */
  suggestedTrainableWeight: number;
  /** La pareja sugerida: la que mas puntua y, de la segunda, la FORMA que
   *  mas solapa con la primera. `null` si no hay dos habilidades. */
  suggestion: {
    main: string;
    mainLabel: string;
    secondary: string;
    secondaryLabel: string;
    secondarySkill: string;
    /** Cuantos recibirian las dos cosas con esa pareja. */
    bothCount: number;
  } | null;
  /** Las plazas que entrena cada habilidad, para sembrar el modo manual. */
  /** Todos los entrenamientos, variantes incluidas. */
  trainings: { code: string; label: string; skill: string }[];
  slotCounts: Record<string, number>;
  /** El que de verdad se usó: el sugerido, o el que fijó el usuario. */
  trainableWeight: number;
  skillScores: Academy["skillScores"];
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

/**
 * Una alerta que el usuario mandó al buzón. Conserva el texto tal como estaba
 * cuando la archivó, así que se sigue leyendo aunque la condición ya no se
 * cumpla; `stillActive` distingue justamente esos dos casos.
 */
export interface ArchivedInsight extends Insight {
  dismissedAt: string;
  stillActive: boolean;
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

/** Fórmula de Fidelidad basada únicamente en días desde la compra. */
export interface LoyaltyModel {
  formula: string;
  maxLevel: number;
  fullDays: number;
  seasons: number;
  thresholds: { level: number; day: number }[];
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
  /** Ventana pedida, en semanas. */
  weeks: number;
  /** Fecha del cierre más antiguo con el que se comparó de verdad. Con menos
   *  historia que la ventana pedida, esto es más viejo de lo que sugiere
   *  `weeks` — o `null` si no hay con qué comparar. */
  comparedFrom: string | null;
  players: { htPlayerId: number; name: string }[];
  selectedPlayerId: number | null;
  skillChanges: HistoricalPlayerChange[];
  experienceChanges: HistoricalPlayerChange[];
  loyaltyChanges: HistoricalPlayerChange[];
  formChanges: HistoricalPlayerChange[];
  /** TSI y Salario. El salario ya viene en la moneda local del equipo. */
  marketChanges: HistoricalPlayerChange[];
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
  spectators: number | null; // Aficionados
  sponsors: number | null; // Patrocinados (incl. bono en la semana en curso)
  financial: number | null; // Financieros
  subtotal: number | null;
  other: number | null; // Venta de jugadores + comisión + temporal
  total: number | null;
}

export interface CostsBreakdown {
  arena: number | null; // Estadio (mantenimiento)
  players: number | null; // Jugadores (sueldos)
  financial: number | null; // Financieros (lo más parecido a "Intereses" de HC)
  staff: number | null; // Empleados
  youth: number | null; // Canteranos
  subtotal: number | null;
  other: number | null; // Compra de jugadores + construcción + temporal
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
  /** La semana en curso, con lo acumulado hasta ahora. Va fuera de `series`
   * porque esa lista son semanas cerradas y alimenta balances y pronóstico. */
  currentWeek: Economy["series"][number] | null;
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
  /** Teórico: ingreso con el estadio 100% lleno menos el real. NO es dinero
   *  perdido salvo que los sectores se agoten — alimenta el simulador de
   *  ampliación, no se muestra como KPI. */
  revenueLeftOnTable: number;
  /** Partidos donde algún sector se agotó: el único caso en que sí hubo
   *  demanda que no se pudo atender. */
  soldOutMatches: number;
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
    /** En qué se puede convertir, en HTMS28, con lo que el ojeador ha dicho.
     *  Sustituye a `potentialScore` en pantalla. */
    htms28Min: number;
    htms28Max: number;
    category: string;
    bestSkill: string;
    bestSkillMax: number | null;
    daysUntilDeadline: number;
    weeksUntilDeadline: number;
    /** Días que faltan para PODER subirlo al primer equipo. Distinto del
     *  plazo para no perderlo por edad: entre las dos fechas está la ventana
     *  en la que hay que decidir. */
    canBePromotedIn: number | null;
    revealedSkills: number;
    verdictIsProvisional: boolean;
    promoteAdvice: string;
    trainingExposure: number;
    skills: {
      skill: string;
      /** Nivel al que juega hoy. `null` = el ojeador aún no lo ha dicho, que
       *  NO es lo mismo que jugar a nivel 0. */
      current: number | null;
      /** Techo. Se revela por separado del nivel actual. */
      maximum: number | null;
      isCurrentKnown: boolean;
      isMaxKnown: boolean;
      headroom: number;
      /** Ya tocó su techo: no sube más. Hattrick lo pinta con un candado. */
      maxReached: boolean;
    }[];
  }[];
  /** Qué habilidad conviene entrenar, de mayor a menor. Portado de la hoja
   *  del usuario (`AuxiJuveniles`): en juveniles se entrena una habilidad y la
   *  reciben todos, así que la pregunta no es a quién entrenar sino qué. */
  skillScores: {
    skill: string;
    label: string;
    score: number;
    counts: Record<string, number>;
    trainableCount: number;
    /** Todos los canteranos ordenados por lo que sacan en esta habilidad.
     *  `note` es `null` cuando el ojeador no ha revelado nada — y ése es
     *  justo el caso en que darle minutos sirve para revelarlo. */
    players: {
      name: string;
      note: number | null;
      bucket: string;
      leavesSoon: boolean;
      maxReached: boolean;
      /** El nivel que tiene, se entrene o no: `note` es null si está al tope. */
      level: number | null;
      /** Lo que dijo el ojeador, cada cosa por separado. */
      current: number | null;
      maximum: number | null;
      /** Su puesto en la cola de esa habilidad, de 1 a 9. */
      priority: number;
    }[];
    /** Los que ya tocaron techo: fuera de la cola, pero se enseñan al final. */
    atMax: {
      name: string;
      level: number | null;
      current: number | null;
      maximum: number | null;
      maxReached: boolean;
      leavesSoon: boolean;
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
  weeks: number;
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
  /** Ni comprado ni de cantera: el movimiento llegó sin identificador. */
  originUnknown: boolean;
  /** El identificador que se enseña es el de la transferencia. */
  htPlayerIdIsTransfer: boolean;
  /** Lo que costó ascenderlo desde la cantera, en moneda local. 0 para quien
   *  llegó fichado: ese tiene precio de compra. */
  promotionCost: number;
  isPurchasePriceManual: boolean;
  purchasePrice: number | null;
  purchasedAt: string | null;
  salePrice: number | null;
  soldAt: string | null;
  salaryTotal: number;
  /** False cuando no hay ningun salario guardado del jugador: el 0
   *  de salaryTotal es ignorancia, no un calculo. */
  /** Partidos que jugo de verdad con nosotros; "?" si aun no se conto. */
  gamesWithUs: number | string;
  salaryKnown: boolean;
  /** Identificador de la ETAPA. Dos filas del mismo jugador comparten
   *  htPlayerId, asi que esto es lo que las distingue. */
  stintId: number | null;
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
  /** La semana de temporada (1-16) de cada movimiento, sin la temporada
   *  delante: las cascadas de Transferencias juntan todas las semanas 05 de
   *  cualquier temporada en la misma columna. */
  weekAtSale: number | null;
  weekAtPurchase: number | null;
  topSkillAtSale: string | null;
  bidHourAtSale: string | null;
  nativeCountry: string;
  nativeCountryCode: string | null;
  character: string;
  specialty: string;
  tsiAtPurchase: number | "?";
  tsiAtSale: number | "?";
  deltaTsi: number | "?";
  commissionAmount: number | "?";
  roiPct: number | "?";
  /** Lo invertido en la etapa. Los desgloses ROI suman esto y el saldo
   *  por grupo, y dividen al final. */
  totalCost: number;
  destinationCountry: string;
  destinationCountryCode: string | null;
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

/** Cómo se resume cada zona sobre los partidos vistos. Ver `PitchZoneMethod`
 *  en el motor: el promedio dice cómo juega de costumbre, el máximo de lo que
 *  es capaz, y el máximo de los tres carriles de lo que es capaz por
 *  cualquiera de ellos. */
export type PitchZoneMethod =
  | "average"
  | "max"
  | "max_parallel"
  | "last"
  /** Solo para el lado propio: la predicción de minuto 0 de Hattrick para las
   *  órdenes ya enviadas. De un rival no existe. */
  | "submitted";

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
  matchesAnalysed: number;
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
   * partidos ya analizados arriba — el rival en vivo, el propio equipo de
   * MatchRating ya sincronizado. `null` si falta alguno de los dos lados
   * (nunca se inventa un duelo con un solo lado real). */
  pitchZoneDuels: PitchZoneDuel[] | null;
  pitchZonesMatchesAnalysed: { own: number | null; rival: number | null };
  pitchZoneSources: { own: PitchZoneSource; rival: PitchZoneSource };
  pitchZoneScope: PitchZoneScope;
  pitchZoneMethodOwn: PitchZoneMethod;
  pitchZoneMethodRival: PitchZoneMethod;
  /** `false` cuando todavía no has mandado alineación: sin eso, el modo
   *  "alineación enviada" no tiene nada que enseñar. */
  submittedLineupAvailable: boolean;
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
    mostCommonFormation: {
      formation: string;
      count: number;
      pct: number;
    } | null;
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


/** Quién trajo a cada canterano y qué queda por revelarle.
 *
 * CHPP no publica una lista de ojeadores; lo único que existe es el
 * `ScoutCall` de cada canterano, así que «mis ojeadores» se reconstruye
 * agrupando por quién trajo a quién. */
export interface AcademyScouts {
  scouts: {
    scoutId: number | null;
    scoutName: string;
    regionIds: number[];
    players: number;
  }[];
  players: {
    name: string;
    htYouthPlayerId: number;
    arrivedAt: string | null;
    scoutId: number | null;
    scoutName: string;
    scoutingRegionId: number | null;
    /** El texto literal del informe, tal como lo escribió el ojeador. */
    comments: string[];
    /** Habilidades a las que aún les queda algo por revelar, según el juego. */
    mayUnlock: string[];
    fetchedAt: string | null;
  }[];
}
