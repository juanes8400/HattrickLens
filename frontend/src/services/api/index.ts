/** La puerta de `services/api`: lo de antes, repartido.
 *
 *  `api.ts` tenia 4147 lineas, 3466 de ellas tipos, y se leia entero en
 *  cada cambio del frontend porque ahi viven tambien los tipos que importan
 *  las paginas. Ahora cada funcionalidad tiene el suyo y esto solo los junta,
 *  para que los 45 ficheros que importan "../services/api" no cambien.
 *
 *  Para añadir una llamada: al fichero de su funcionalidad, no aqui.
 */
export type { ArchivedInsight, Insight } from "./alertas";
export type {
  HindsightLine,
  HindsightProposedPlayer,
  HindsightUsedPlayer,
  Lineup,
  LineupHindsight,
  TeamSpiritMultiplier,
} from "./alineacion";
export type { SessionProfile, SessionTeam } from "./auth";
export type {
  Club,
  ClubStaffRole,
  ClubStaffRoleEffect,
  Psychology,
  PsychologyMatch,
  PsychologyMovement,
  PsychologySeries,
} from "./club";
export type {
  AvisoDelBarrido,
  CalculationReference,
  Dashboard,
  NextMatchCondition,
  PitchZoneMethod,
  PositionRating,
  SquadPlayer,
} from "./comun";
export type {
  Cup,
  CupHistoryRow,
  CupLadderStep,
  CupNextMatch,
  CupPenaltyCandidate,
  CupPrizeStage,
  CupReadinessVariant,
  CupScenario,
  MastersRival,
} from "./copa";
export type {
  CostsBreakdown,
  Economy,
  ForecastBand,
  IncomeBreakdown,
  SeasonBreakdownTotals,
  WeeklyBreakdownRow,
} from "./economia";
export type {
  FormulaInput,
  PostMatchTraining,
  PostMatchTrainingOption,
  TrainingDevelopment,
  TrainingExperienceRow,
  TrainingForecast,
  TrainingFormula,
  TrainingLoyaltyRow,
  TrainingSquad,
  TrainingSquadPlayerRow,
  TrainingSquadWeeklyLogEntry,
  TrainingStaminaRow,
  UltimoEntrenamiento,
} from "./entrenamiento";
export type { Arena, ArenaTipo } from "./estadio";
export type {
  Skills,
  SkillsCandidate,
  SkillsDepth,
  SkillsTone,
} from "./habilidades";
export type {
  ActivePlayerDetail,
  ConfirmedLevelUp,
  ExPlayerDetail,
  LevelForecastMilestone,
  PlayerDetail,
  PlayerDetailsSyncResult,
  PlayerTrainingLevels,
  PositionMatrixRow,
  PositionModel,
} from "./jugadores";
export type {
  Academy,
  AcademyComparativa,
  AcademyScouts,
  AcademySkillScores,
  AcademyTrainingPlan,
  LineaDeEntrenamiento,
  NivelLeido,
  ScoutsLedger,
  TrainingSlot,
  VeredictoDeMetodo,
} from "./juveniles";
export type { GuestbookEntry } from "./libro";
export { FORMATIONS } from "./liga";
export type {
  Formation,
  League,
  LeagueComparison,
  LeagueMatchRef,
  LeaguePitchZoneMethod,
  LeagueStandingRow,
  LeagueTeamSummary,
  OutlookRow,
  SectoresRecientes,
  TeamOfTheWeek,
  TeamOfWeekPlayer,
  TeamOfWeekRoleKey,
  TeamOfWeekSlotKey,
} from "./liga";
export type {
  Calculo,
  ConstanteDeCalculo,
  ExperienceModel,
  FuenteDeCalculo,
  LoyaltyModel,
  SeccionDeCalculos,
  TablaDeCalculo,
} from "./modelos";
export { ApiError, errorMessage, leerRenovacion } from "./nucleo";
export type {
  BestRating,
  ConversionSummary,
  HomeAwayRow,
  LastMatchReport,
  MatchDetail,
  MatchDetailsSyncResult,
  MatchRow,
  Matches,
  RatingSeriesPoint,
  ZoneChances,
} from "./partidos";
export type { Squad, VentanaDeComparacion } from "./plantilla";
export type {
  TeamOverview,
  TeamOverviewChart,
  TeamOverviewGroup,
  TeamOverviewMetric,
  TeamOverviewPitchSlot,
  TeamOverviewSeries,
  TeamOverviewSpecialRole,
} from "./resumen";
export type {
  LastPurchase,
  PartidoConMarcador,
  PitchZoneDuel,
  PitchZoneSource,
  RivalScouting,
} from "./rivales";
export type {
  BackfillBatchResult,
  BackfillPending,
  ChangeMetricSummary,
  ChangesHistory,
  ClubComparisonChange,
  HistoricalPlayerChange,
  LastSyncChanges,
  NationalMatchAppearance,
  PlayerComparisonChange,
  PlayerComparisonRow,
  QueueMap,
  SweepBalance,
  SyncChange,
  SyncChangeDetail,
  SyncChangeKind,
  SyncResult,
  SyncSaleEconomics,
  SyncStreamEvent,
  YouthComparisonChange,
  YouthComparisonRow,
  YouthSummary,
} from "./sincronizacion";
export type {
  ComparableDeMercado,
  PlayerBalance,
  PlayerBalanceRow,
  PrecioComparable,
  PuntoDeLaSerie,
  RasgoVisible,
  TransferAttemptRow,
  TransferAttempts,
  TransfersHistorySyncResult,
} from "./transferencias";
export type {
  UsageLog,
  UsageLogFiltros,
  UsageSummary,
  UsageUser,
  UsageUserModule,
} from "./uso";

import { apiAlertas } from "./alertas";
import { apiAlineacion } from "./alineacion";
import { apiAuth } from "./auth";
import { apiClub } from "./club";
import { apiComun } from "./comun";
import { apiCopa } from "./copa";
import { apiDashboard } from "./dashboard";
import { apiEconomia } from "./economia";
import { apiEntrenamiento } from "./entrenamiento";
import { apiEstadio } from "./estadio";
import { apiHabilidades } from "./habilidades";
import { apiJugadores } from "./jugadores";
import { apiJuveniles } from "./juveniles";
import { apiLibro } from "./libro";
import { apiLiga } from "./liga";
import { apiModelos } from "./modelos";
import { apiPartidos } from "./partidos";
import { apiPlantilla } from "./plantilla";
import { apiResumen } from "./resumen";
import { apiRivales } from "./rivales";
import { apiSincronizacion } from "./sincronizacion";
import { apiTransferencias } from "./transferencias";
import { apiUso } from "./uso";

/** El objeto de siempre, junto desde los trozos. */
export const api = {
  ...apiAlertas,
  ...apiAlineacion,
  ...apiAuth,
  ...apiClub,
  ...apiComun,
  ...apiCopa,
  ...apiDashboard,
  ...apiEconomia,
  ...apiEntrenamiento,
  ...apiEstadio,
  ...apiHabilidades,
  ...apiJugadores,
  ...apiJuveniles,
  ...apiLibro,
  ...apiLiga,
  ...apiModelos,
  ...apiPartidos,
  ...apiPlantilla,
  ...apiResumen,
  ...apiRivales,
  ...apiSincronizacion,
  ...apiTransferencias,
  ...apiUso,
};
