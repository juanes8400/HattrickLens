import { useQuery } from "@tanstack/react-query";
import { api } from "../services/api";
import type { Formation, PitchZoneScope } from "../services/api";

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

export const useLineup = (formation?: string, weather?: string) =>
  useQuery({
    queryKey: ["lineup", TEAM_ID, formation, weather],
    queryFn: () => api.lineup(TEAM_ID, formation, weather),
  });

export const useTrainingForecast = () =>
  useQuery({ queryKey: ["training", TEAM_ID], queryFn: () => api.trainingForecast(TEAM_ID) });

export const usePostMatchTraining = () =>
  useQuery({
    queryKey: ["post-match-training", TEAM_ID],
    queryFn: () => api.postMatchTraining(TEAM_ID),
  });

export const useInsights = () =>
  useQuery({ queryKey: ["insights", TEAM_ID], queryFn: () => api.insights(TEAM_ID) });

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
  scope: "week" | "season", formation: Formation, round?: number,
) =>
  useQuery({
    queryKey: ["league-team-of-week", TEAM_ID, scope, formation, round],
    queryFn: () => api.leagueTeamOfWeek(TEAM_ID, scope, formation, round),
  });

export const useAcademy = () =>
  useQuery({ queryKey: ["academy", TEAM_ID], queryFn: () => api.academy(TEAM_ID) });

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
  logTsi: boolean, excludeKeeper: boolean, top11: boolean, enabled = true,
) =>
  useQuery({
    queryKey: ["league-comparison", TEAM_ID, logTsi, excludeKeeper, top11],
    queryFn: () => api.leagueComparison(TEAM_ID, logTsi, excludeKeeper, top11),
    enabled,
  });

export const useSyncChanges = () =>
  useQuery({ queryKey: ["sync-changes", TEAM_ID], queryFn: () => api.syncChanges(TEAM_ID) });

export const useChangesHistory = (playerId?: number | null) =>
  useQuery({
    queryKey: ["changes-history", TEAM_ID, playerId ?? null],
    queryFn: () => api.changesHistory(TEAM_ID, playerId),
  });

export const useCup = () =>
  useQuery({ queryKey: ["cup", TEAM_ID], queryFn: () => api.cup(TEAM_ID) });

export const useRivalScouting = (
  rivalHtTeamId: number | null,
  logTsi: boolean,
  excludeKeeper: boolean,
  top11: boolean,
  includeCompetitive = true,
  includeFriendlies = true,
  pitchZoneScope: PitchZoneScope = "mixed",
) =>
  useQuery({
    queryKey: [
      "rival-scouting", TEAM_ID, rivalHtTeamId, logTsi, excludeKeeper, top11,
      includeCompetitive, includeFriendlies, pitchZoneScope,
    ],
    queryFn: () =>
      api.rivalScouting(
        TEAM_ID, rivalHtTeamId as number, logTsi, excludeKeeper, top11,
        includeCompetitive, includeFriendlies, pitchZoneScope,
      ),
    enabled: rivalHtTeamId != null,
  });

export const useNextMatchAnalysis = () =>
  useQuery({
    queryKey: ["next-match-analysis", TEAM_ID],
    queryFn: () => api.nextMatchAnalysis(TEAM_ID),
  });
