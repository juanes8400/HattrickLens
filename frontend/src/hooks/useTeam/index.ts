/** La puerta de `hooks/useTeam`: lo de antes, repartido.
 *
 *  `useTeam.ts` tenia 601 lineas y lo abrian 26 de las 31 pantallas, asi que
 *  cambiar un hook del estadio obligaba a cargar los de la academia y la copa.
 *  Ahora cada funcionalidad tiene el suyo y esto solo los reexporta, por su
 *  nombre, para que la puerta de fuera quede igual que estaba.
 *
 *  Para añadir un hook: al fichero de su funcionalidad, no aqui.
 */
export {
  useArchiveInsight,
  useArchivedInsights,
  useInsights,
  useRestoreInsight,
} from "./alertas";
export { useLineup } from "./alineacion";
export { useSessionProfile } from "./auth";
export { useClub } from "./club";
export { useCup } from "./copa";
export { useDashboard } from "./dashboard";
export { useEconomy } from "./economia";
export {
  usePostMatchTraining,
  useTrainingDevelopment,
  useTrainingForecast,
  useTrainingFormula,
  useTrainingSquad,
  useUltimoEntrenamiento,
} from "./entrenamiento";
export { useArena } from "./estadio";
export { useSkills } from "./habilidades";
export {
  usePlayerDetail,
  usePlayerTrainingLevels,
  usePositionModel,
} from "./jugadores";
export {
  useAcademy,
  useAcademyComparativa,
  useAcademyScouts,
  useAcademyScoutsLedger,
  useAcademySkillScores,
  useAcademyTrainingPlan,
} from "./juveniles";
export {
  useLeague,
  useLeagueComparison,
  useLeagueTeamOfWeek,
  useSectoresRecientes,
} from "./liga";
export { useCalculos, useExperienceModel, useLoyaltyModel } from "./modelos";
export {
  TEAM_ID,
  clearActiveTeamId,
  hasActiveTeam,
  setActiveTeamId,
} from "./nucleo";
export { useLastMatchReport, useMatchDetail, useMatches } from "./partidos";
export { useSquad } from "./plantilla";
export { useTeamOverview } from "./resumen";
export { useRivalScouting } from "./rivales";
export { useChangesHistory, useSyncChanges } from "./sincronizacion";
export { usePlayerBalance } from "./transferencias";
