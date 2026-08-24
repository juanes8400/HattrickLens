import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../services/api";
import type { Formation, PitchZoneMethod, PitchZoneScope } from "../services/api";

/**
 * El equipo activo. Antes de conectar con Hattrick no hay ninguno real, así
 * que se cae al 1 sembrado en desarrollo; tras el callback OAuth,
 * `ConnectedPage` guarda el id real del equipo del usuario aquí y recarga,
 * con lo que este módulo se reevalúa con el valor correcto.
 *
 * Single team por ahora; multi-club por usuario es una vista de selección a
 * futuro (`user_teams`), no necesaria mientras cada cuenta conectada gestiona
 * un solo club.
 */
const TEAM_ID_STORAGE_KEY = "htlens_team_id";

export const TEAM_ID = Number(localStorage.getItem(TEAM_ID_STORAGE_KEY)) || 1;

/** `TEAM_ID` conserva el fallback de desarrollo para no romper las consultas
 * existentes, pero la interfaz no debe intentar usarlas hasta que OAuth haya
 * elegido un equipo real. */
export function hasActiveTeam(): boolean {
  const teamId = Number(localStorage.getItem(TEAM_ID_STORAGE_KEY));
  return Number.isInteger(teamId) && teamId > 0;
}

export function setActiveTeamId(teamId: number): void {
  localStorage.setItem(TEAM_ID_STORAGE_KEY, String(teamId));
}

export function clearActiveTeamId(): void {
  localStorage.removeItem(TEAM_ID_STORAGE_KEY);
}

export const useSessionProfile = () =>
  useQuery({
    queryKey: ["session-profile"],
    queryFn: api.sessionProfile,
    staleTime: 5 * 60_000,
  });

export const useDashboard = () =>
  useQuery({ queryKey: ["dashboard", TEAM_ID], queryFn: () => api.dashboard(TEAM_ID) });

export const useClub = () =>
  useQuery({ queryKey: ["club", TEAM_ID], queryFn: () => api.club(TEAM_ID) });

export const useSquad = (position?: string, comparisonSyncId?: number | null) =>
  useQuery({
    queryKey: ["squad", TEAM_ID, position, comparisonSyncId ?? null],
    queryFn: () => api.squad(TEAM_ID, position, comparisonSyncId),
  });

export const usePlayerDetail = (htPlayerId: number) =>
  useQuery({
    queryKey: ["player", TEAM_ID, htPlayerId],
    queryFn: () => api.playerDetail(TEAM_ID, htPlayerId),
  });

export const useLineup = (
  formation?: string,
  centralDefenders?: number,
  innerMidfielders?: number,
  orders?: Record<number, string>,
) =>
  useQuery({
    queryKey: [
      "lineup", TEAM_ID, formation, centralDefenders ?? null, innerMidfielders ?? null,
      orders ?? null,
    ],
    queryFn: () => api.lineup(TEAM_ID, formation, centralDefenders, innerMidfielders, orders),
    // Mover un reparto no cambia la plantilla: se conserva el once anterior
    // mientras llega el nuevo, en vez de vaciar la pantalla entera.
    placeholderData: (previous) => previous,
  });

export const useTrainingForecast = () =>
  useQuery({ queryKey: ["training", TEAM_ID], queryFn: () => api.trainingForecast(TEAM_ID) });

export const usePostMatchTraining = () =>
  useQuery({
    queryKey: ["post-match-training", TEAM_ID],
    queryFn: () => api.postMatchTraining(TEAM_ID),
  });

export const useTeamOverview = () =>
  useQuery({ queryKey: ["team-overview", TEAM_ID], queryFn: () => api.teamOverview(TEAM_ID) });

export const useInsights = () =>
  useQuery({ queryKey: ["insights", TEAM_ID], queryFn: () => api.insights(TEAM_ID) });

export const useArchivedInsights = () =>
  useQuery({
    queryKey: ["insights-archived", TEAM_ID],
    queryFn: () => api.archivedInsights(TEAM_ID),
  });

/** Archivar y restaurar tocan las dos listas a la vez — una alerta que sale de
 *  la activa entra en el buzón y viceversa — así que ambas se invalidan
 *  juntas. Si solo se refrescara una, la pantalla mostraría la misma alerta en
 *  los dos sitios hasta el siguiente refresco. */
function useInsightArchiveMutation(fn: (teamId: number, key: string) => Promise<unknown>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (key: string) => fn(TEAM_ID, key),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["insights", TEAM_ID] });
      queryClient.invalidateQueries({ queryKey: ["insights-archived", TEAM_ID] });
    },
  });
}

export const useArchiveInsight = () => useInsightArchiveMutation(api.archiveInsight);
export const useRestoreInsight = () => useInsightArchiveMutation(api.restoreInsight);

export const usePositionModel = () =>
  useQuery({ queryKey: ["position-model"], queryFn: api.positionModel });

export const useExperienceModel = () =>
  useQuery({
    queryKey: ["experience-model", TEAM_ID],
    queryFn: () => api.experienceModel(TEAM_ID),
  });

export const useLoyaltyModel = () =>
  useQuery({
    queryKey: ["loyalty-model", TEAM_ID],
    queryFn: () => api.loyaltyModel(TEAM_ID),
  });

export const useEconomy = (horizonWeeks = 52) =>
  useQuery({
    queryKey: ["economy", TEAM_ID, horizonWeeks],
    queryFn: () => api.economy(TEAM_ID, horizonWeeks),
  });

export const useArena = (fillRate?: number) =>
  useQuery({
    queryKey: ["arena", TEAM_ID, fillRate ?? null],
    queryFn: () => api.arena(TEAM_ID, fillRate),
  });

export const useMatches = (includeFriendlies = false, season?: number | null) =>
  useQuery({
    queryKey: ["matches", TEAM_ID, includeFriendlies, season ?? null],
    queryFn: () => api.matches(TEAM_ID, includeFriendlies, season),
  });

export const useMatchDetail = (htMatchId: number | null) =>
  useQuery({
    queryKey: ["match", TEAM_ID, htMatchId],
    queryFn: () => api.matchDetail(TEAM_ID, htMatchId as number),
    enabled: htMatchId != null,
  });

export const useLeague = (runs = 10000) =>
  useQuery({
    queryKey: ["league", TEAM_ID, runs],
    queryFn: () => api.league(TEAM_ID, runs),
  });

export const useLeagueTeamOfWeek = (
  scope: "week" | "season",
  formation: Formation,
  round?: number,
  centralDefenders?: number,
  innerMidfielders?: number,
) =>
  useQuery({
    queryKey: [
      "league-team-of-week", TEAM_ID, scope, formation, round,
      centralDefenders ?? null, innerMidfielders ?? null,
    ],
    queryFn: () =>
      api.leagueTeamOfWeek(
        TEAM_ID, scope, formation, round, centralDefenders, innerMidfielders,
      ),
    // Mover un reparto no cambia qué partidos se leen: se conserva el once
    // anterior mientras llega el nuevo en vez de vaciar el panel.
    placeholderData: (previous) => previous,
  });

export const useAcademy = () =>
  useQuery({ queryKey: ["academy", TEAM_ID], queryFn: () => api.academy(TEAM_ID) });

/** Quién trajo a cada canterano. Va aparte de `useAcademy` porque son datos
 *  que sólo mira la pestaña de Ojeadores. */
export const useAcademyScouts = () =>
  useQuery({
    queryKey: ["academy-scouts", TEAM_ID],
    queryFn: () => api.academyScouts(TEAM_ID),
  });

export const usePlayerBalance = (season?: string) =>
  useQuery({
    queryKey: ["player-balance", TEAM_ID, season ?? "all"],
    queryFn: () => api.playerBalance(TEAM_ID, season),
  });

export const useTrainingFormula = () =>
  useQuery({
    queryKey: ["training-formula", TEAM_ID],
    queryFn: () => api.trainingFormula(TEAM_ID),
  });

export const useTrainingSquad = (skill?: string | null, includeThisWeek = true) =>
  useQuery({
    queryKey: ["training-squad", TEAM_ID, skill ?? "default", includeThisWeek],
    queryFn: () => api.trainingSquad(TEAM_ID, skill, includeThisWeek),
  });

export const useTrainingDevelopment = (enabled = true) =>
  useQuery({
    queryKey: ["training-development", TEAM_ID],
    queryFn: () => api.trainingDevelopment(TEAM_ID),
    enabled,
  });

export const usePlayerTrainingLevels = (htPlayerId: number | null, skill?: string | null) =>
  useQuery({
    queryKey: ["player-training-levels", TEAM_ID, htPlayerId, skill ?? "default"],
    queryFn: () => api.playerTrainingLevels(TEAM_ID, htPlayerId as number, skill),
    enabled: htPlayerId != null,
  });

// La comparativa de TSI de liga pide las plantillas de 7-8 rivales a CHPP —
// carga sola al entrar a /league (2026-08-08: revertido el arranque
// colapsado del 2026-08-05). `enabled` queda disponible por si otro caller
// necesita retrasar el fetch, pero por defecto en `true`.
export const useLeagueComparison = (
  logTsi: boolean, top11: boolean, enabled = true,
) =>
  useQuery({
    queryKey: ["league-comparison", TEAM_ID, logTsi, top11],
    queryFn: () => api.leagueComparison(TEAM_ID, logTsi, top11),
    enabled,
    // Los mandos de esta pantalla son post-proceso sobre los mismos XML: al
    // cambiarlos se conserva lo que ya está pintado mientras llega lo nuevo.
    // Sin esto la página entera se vaciaba y volvía, que es lo que se siente
    // como "tarda un montón" aunque la respuesta tarde medio segundo.
    placeholderData: (previous) => previous,
  });

export const useSyncChanges = (syncId?: number | null) =>
  useQuery({
    queryKey: ["sync-changes", TEAM_ID, syncId ?? null],
    queryFn: () => api.syncChanges(TEAM_ID, syncId),
    // Al cambiar de fecha se mantiene la tabla anterior mientras llega la
    // nueva, en vez de parpadear a vacío en cada selección.
    placeholderData: (previous) => previous,
  });

export const useAcademyTrainingPlan = (params: {
  main: string;
  secondary: string;
  soonMaxDays: number;
  weightBase: number;
}) =>
  useQuery({
    queryKey: ["academy-training-plan", TEAM_ID, params],
    queryFn: () => api.academyTrainingPlan(TEAM_ID, params),
    enabled: Boolean(params.main && params.secondary),
    placeholderData: (previous) => previous,
  });

export const useAcademySkillScores = (params: {
  soonMaxDays: number;
  weightBase: number;
  trainableMethod: string;
  trainable: Record<string, number>;
  trainableWeight?: number | null;
}) =>
  useQuery({
    queryKey: ["academy-skill-scores", TEAM_ID, params],
    queryFn: () => api.academySkillScores(TEAM_ID, params),
    // Al mover un deslizador se conserva la tabla anterior mientras llega la
    // nueva: parpadear a vacío en cada píxel haría el mando inusable.
    placeholderData: (previous) => previous,
  });

export const useChangesHistory = (
  playerId?: number | null,
  weeks?: number,
  enabled = true,
) =>
  useQuery({
    queryKey: ["changes-history", TEAM_ID, playerId ?? null, weeks ?? null],
    queryFn: () => api.changesHistory(TEAM_ID, playerId, weeks),
    enabled,
    // Al cambiar de ventana se conserva la tabla anterior mientras llega la
    // nueva, en vez de parpadear a vacío en cada clic.
    placeholderData: (previous) => previous,
  });

export const useCup = () =>
  useQuery({ queryKey: ["cup", TEAM_ID], queryFn: () => api.cup(TEAM_ID) });

export const useRivalScouting = (
  rivalHtTeamId: number | null,
  logTsi: boolean,
  top11: boolean,
  includeCompetitive = true,
  includeFriendlies = true,
  pitchZoneScope: PitchZoneScope = "mixed",
  pitchZoneMethodOwn: PitchZoneMethod = "submitted",
  pitchZoneMethodRival: PitchZoneMethod = "average",
) =>
  useQuery({
    queryKey: [
      "rival-scouting", TEAM_ID, rivalHtTeamId, logTsi, top11,
      includeCompetitive, includeFriendlies, pitchZoneScope,
      pitchZoneMethodOwn, pitchZoneMethodRival,
    ],
    queryFn: () =>
      api.rivalScouting(
        TEAM_ID, rivalHtTeamId as number, logTsi, top11,
        includeCompetitive, includeFriendlies, pitchZoneScope,
        pitchZoneMethodOwn, pitchZoneMethodRival,
      ),
    enabled: rivalHtTeamId != null,
    // Igual que en la comparativa de liga: método de zonas, TSI logarítmico y
    // once/plantilla no piden datos nuevos a Hattrick, así que la ficha no
    // debe desaparecer mientras se recalculan.
    placeholderData: (previous) => previous,
  });
