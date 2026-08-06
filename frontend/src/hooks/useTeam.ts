import { useQuery } from "@tanstack/react-query";
import { api } from "../services/api";
import type { PitchZoneScope } from "../services/api";

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

export const useValuations = () =>
  useQuery({ queryKey: ["valuations", TEAM_ID], queryFn: () => api.valuations(TEAM_ID) });

export const useInsights = () =>
  useQuery({ queryKey: ["insights", TEAM_ID], queryFn: () => api.insights(TEAM_ID) });

export const usePositionModel = () =>
  useQuery({ queryKey: ["position-model"], queryFn: api.positionModel });

export const useExperienceModel = () =>
  useQuery({
    queryKey: ["experience-model", TEAM_ID],
    queryFn: () => api.experienceModel(TEAM_ID),
  });

export const useEconomy = (horizonWeeks = 52) =>
  useQuery({
    queryKey: ["economy", TEAM_ID, horizonWeeks],
    queryFn: () => api.economy(TEAM_ID, horizonWeeks),
  });

export const useArena = (fillRate?: number, includeNonOfficial = false) =>
  useQuery({
    queryKey: ["arena", TEAM_ID, fillRate ?? null, includeNonOfficial],
    queryFn: () => api.arena(TEAM_ID, fillRate, includeNonOfficial),
  });

export const useMatches = (includeNonOfficial = false) =>
  useQuery({
    queryKey: ["matches", TEAM_ID, includeNonOfficial],
    queryFn: () => api.matches(TEAM_ID, includeNonOfficial),
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

export const useLeagueComparison = (logTsi: boolean, excludeKeeper: boolean, top11: boolean) =>
  useQuery({
    queryKey: ["league-comparison", TEAM_ID, logTsi, excludeKeeper, top11],
    queryFn: () => api.leagueComparison(TEAM_ID, logTsi, excludeKeeper, top11),
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
