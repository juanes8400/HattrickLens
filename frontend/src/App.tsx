import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./layouts/AppLayout";
import { DashboardPage } from "./pages/DashboardPage";
import { ClubPage } from "./pages/ClubPage";
import { TeamOverviewPage } from "./pages/TeamOverviewPage";
import { TeamPage } from "./pages/TeamPage";
import { PlayerPage } from "./pages/PlayerPage";
import { ConnectedPage } from "./pages/ConnectedPage";
import { PositionsPage } from "./pages/PositionsPage";
import { LineupPage } from "./pages/LineupPage";
import { TrainingPage } from "./pages/TrainingPage";
import { PlayerBalancePage } from "./pages/PlayerBalancePage";
import { InsightsPage } from "./pages/InsightsPage";
import { EnginePage } from "./pages/EnginePage";
import { SyncChangesPage } from "./pages/SyncChangesPage";
import { SyncPage } from "./pages/SyncPage";
import { EconomyPage } from "./pages/EconomyPage";
import { ArenaPage } from "./pages/ArenaPage";
import { MatchesPage } from "./pages/MatchesPage";
import { LeaguePage } from "./pages/LeaguePage";
import { CupPage } from "./pages/CupPage";
import { AcademyPage } from "./pages/AcademyPage";
import { RivalPage } from "./pages/RivalPage";
import { RivalPickerPage } from "./pages/RivalPickerPage";
import { WelcomePage } from "./pages/WelcomePage";
import { SetupPage } from "./pages/SetupPage";
import { hasActiveTeam, useDashboard } from "./hooks/useTeam";
import { ErrorState, Loading } from "./components/Panels";

function RequireTeam({ children }: { children: ReactNode }) {
  return hasActiveTeam() ? children : <Navigate to="/welcome" replace />;
}

function RequireImportedTeam({ children }: { children: ReactNode }) {
  const dashboard = useDashboard();
  if (dashboard.isLoading) {
    return <main className="grid min-h-screen place-items-center"><Loading /></main>;
  }
  if (dashboard.isError) {
    return <main className="grid min-h-screen place-items-center p-6"><ErrorState error={dashboard.error} /></main>;
  }
  if (!dashboard.data?.syncedAt) return <Navigate to="/setup" replace />;
  return children;
}

export function App() {
  return (
    <Routes>
      <Route path="connected" element={<ConnectedPage />} />
      <Route path="welcome" element={<WelcomePage />} />
      <Route path="setup" element={<RequireTeam><SetupPage /></RequireTeam>} />
      <Route element={<RequireTeam><RequireImportedTeam><AppLayout /></RequireImportedTeam></RequireTeam>}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="club" element={<ClubPage />} />
        <Route path="overview" element={<TeamOverviewPage />} />
        <Route path="team" element={<TeamPage />} />
        <Route path="players/:htPlayerId" element={<PlayerPage />} />
        <Route path="positions" element={<PositionsPage />} />
        <Route path="lineup" element={<LineupPage />} />
        <Route path="training" element={<TrainingPage />} />
        <Route path="transfers/balance" element={<PlayerBalancePage />} />
        <Route path="academy" element={<AcademyPage />} />
        <Route path="matches" element={<MatchesPage />} />
        <Route path="league" element={<LeaguePage />} />
        <Route path="cup" element={<CupPage />} />
        <Route path="rivals" element={<RivalPickerPage />} />
        <Route path="rivals/:rivalHtTeamId" element={<RivalPage />} />
        <Route path="economy" element={<EconomyPage />} />
        <Route path="arena" element={<ArenaPage />} />
        <Route path="insights" element={<InsightsPage />} />
        <Route path="sync" element={<SyncPage />} />
        <Route path="news" element={<SyncChangesPage />} />
        <Route path="engine" element={<EnginePage />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Route>
    </Routes>
  );
}
