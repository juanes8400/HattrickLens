import type { ComponentType, ReactNode } from "react";
import { Suspense, lazy, useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppLayout } from "./layouts/AppLayout";
import { tituloDeRuta } from "./layouts/navegacion";
// Van en el paquete principal: el Dashboard es lo primero que se abre, y las
// pantallas de entrada tienen que funcionar antes de que haya nada más.
import { DashboardNuevo } from "./pages/DashboardNuevo";
// El Dashboard anterior no se difiere: el nuevo ya importa sus paneles, así
// que viaja en el paquete principal de todas formas.
import { DashboardPage } from "./pages/DashboardPage";
import { ConnectedPage } from "./pages/ConnectedPage";
import { WelcomePage } from "./pages/WelcomePage";
import { SetupPage } from "./pages/SetupPage";
import { arrancarTelemetria, verPagina } from "./services/telemetria";
import { hasActiveTeam, useDashboard } from "./hooks/useTeam";
import { ErrorState, Loading } from "./components/Panels";

/** Una pantalla que se descarga al abrirla, no al entrar en la app.
 *
 *  2026-09-14, medido en producción: todo iba en un único archivo de 1,87 MB,
 *  así que abrir el Dashboard descargaba también la Wiki, Transferencias y
 *  el resto. Ahora cada una viaja aparte y sólo cuando se visita. */
function diferida<K extends string>(
  cargar: () => Promise<Record<K, ComponentType>>,
  nombre: K,
) {
  return lazy(() => cargar().then((m) => ({ default: m[nombre] })));
}

const ClubPage = diferida(() => import("./pages/ClubPage"), "ClubPage");
const TeamOverviewPage = diferida(
  () => import("./pages/TeamOverviewPage"),
  "TeamOverviewPage",
);
const TeamPage = diferida(() => import("./pages/TeamPage"), "TeamPage");
const PlayerPage = diferida(() => import("./pages/PlayerPage"), "PlayerPage");
const PositionsPage = diferida(
  () => import("./pages/PositionsPage"),
  "PositionsPage",
);
const SkillsPage = diferida(() => import("./pages/SkillsPage"), "SkillsPage");
const WikiPage = diferida(() => import("./pages/WikiPage"), "WikiPage");
const LineupPage = diferida(() => import("./pages/LineupPage"), "LineupPage");
const TrainingPage = diferida(
  () => import("./pages/TrainingPage"),
  "TrainingPage",
);
const ApoyarPage = diferida(() => import("./pages/ApoyarPage"), "ApoyarPage");
const LibroDeVisitasPage = diferida(
  () => import("./pages/LibroDeVisitasPage"),
  "LibroDeVisitasPage",
);
const PlayerBalancePage = diferida(
  () => import("./pages/PlayerBalancePage"),
  "PlayerBalancePage",
);
const InsightsPage = diferida(
  () => import("./pages/InsightsPage"),
  "InsightsPage",
);
const TransparencyPage = diferida(
  () => import("./pages/TransparencyPage"),
  "TransparencyPage",
);
const SyncChangesPage = diferida(
  () => import("./pages/SyncChangesPage"),
  "SyncChangesPage",
);
const SyncPage = diferida(() => import("./pages/SyncPage"), "SyncPage");
const UsagePage = diferida(() => import("./pages/UsagePage"), "UsagePage");
const AutorPage = diferida(() => import("./pages/AutorPage"), "AutorPage");
const EconomyPage = diferida(
  () => import("./pages/EconomyPage"),
  "EconomyPage",
);
const ArenaPage = diferida(() => import("./pages/ArenaPage"), "ArenaPage");
const MatchesPage = diferida(
  () => import("./pages/MatchesPage"),
  "MatchesPage",
);
const LeaguePage = diferida(() => import("./pages/LeaguePage"), "LeaguePage");
const CupPage = diferida(() => import("./pages/CupPage"), "CupPage");
const AcademyPage = diferida(
  () => import("./pages/AcademyPage"),
  "AcademyPage",
);
const RivalPage = diferida(() => import("./pages/RivalPage"), "RivalPage");
const RivalPickerPage = diferida(
  () => import("./pages/RivalPickerPage"),
  "RivalPickerPage",
);

/** El hueco mientras llega la pantalla: dentro del marco, que no parpadea. */
function Espera({ children }: { children: ReactNode }) {
  return <Suspense fallback={<Loading />}>{children}</Suspense>;
}

function RequireTeam({ children }: { children: ReactNode }) {
  return hasActiveTeam() ? children : <Navigate to="/welcome" replace />;
}

function RequireImportedTeam({ children }: { children: ReactNode }) {
  const dashboard = useDashboard();
  if (dashboard.isLoading) {
    return (
      <main className="grid min-h-screen place-items-center">
        <Loading />
      </main>
    );
  }
  if (dashboard.isError) {
    return (
      <main className="grid min-h-screen place-items-center p-6">
        <ErrorState error={dashboard.error} />
      </main>
    );
  }
  if (!dashboard.data?.syncedAt) return <Navigate to="/setup" replace />;
  return children;
}

/** Avisa al recolector de cada cambio de página.
 *
 *  Va aquí, en un solo sitio, y no repartido por cada pantalla: así una página
 *  nueva se mide sola y nadie tiene que acordarse de nada. La ruta con
 *  parámetros se manda tal cual --`/players/123`-- y es el recolector quien la
 *  traduce a un módulo, para que un identificador de jugador no acabe siendo
 *  una fila más en los resúmenes. */
function MedidorDePaginas() {
  const { pathname } = useLocation();
  useEffect(() => {
    arrancarTelemetria();
    verPagina(pathname);
    // Y de paso el título de la pestaña, que sale de la misma lista.
    document.title = tituloDeRuta(pathname);
  }, [pathname]);
  return null;
}

export function App() {
  return (
    <>
      <MedidorDePaginas />
      <Routes>
        <Route path="connected" element={<ConnectedPage />} />
        <Route path="welcome" element={<WelcomePage />} />
        {/* FUERA del guardián a propósito. La bienvenida invita a apoyar, y
            con esta ruta protegida ese enlace devolvía a la bienvenida: un
            enlace muerto en la primera pantalla que ve alguien. Quien todavía
            no ha conectado su club también puede querer apoyar, y la página
            no necesita datos suyos --sin país conocido ordena igual que para
            cualquiera de fuera-- (2026-09-05, visto en producción). */}
        <Route
          path="apoyar"
          element={
            <Espera>
              <ApoyarPage />
            </Espera>
          }
        />
        <Route
          path="setup"
          element={
            <RequireTeam>
              <SetupPage />
            </RequireTeam>
          }
        />
        <Route
          element={
            <RequireTeam>
              <RequireImportedTeam>
                <AppLayout />
              </RequireImportedTeam>
            </RequireTeam>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          {/* 2026-09-13, Dashboard nuevo a prueba. Para volver al de antes,
              cambiar DashboardNuevo por DashboardPage en esta línea. Mientras
              tanto el de antes sigue en /dashboard-anterior para comparar. */}
          <Route path="dashboard" element={<DashboardNuevo />} />
          <Route
            path="dashboard-anterior"
            element={
              <Espera>
                <DashboardPage />
              </Espera>
            }
          />
          <Route
            path="club"
            element={
              <Espera>
                <ClubPage />
              </Espera>
            }
          />
          <Route
            path="overview"
            element={
              <Espera>
                <TeamOverviewPage />
              </Espera>
            }
          />
          <Route
            path="team"
            element={
              <Espera>
                <TeamPage />
              </Espera>
            }
          />
          <Route
            path="skills"
            element={
              <Espera>
                <SkillsPage />
              </Espera>
            }
          />
          <Route
            path="players/:htPlayerId"
            element={
              <Espera>
                <PlayerPage />
              </Espera>
            }
          />
          <Route
            path="positions"
            element={
              <Espera>
                <PositionsPage />
              </Espera>
            }
          />
          <Route
            path="lineup"
            element={
              <Espera>
                <LineupPage />
              </Espera>
            }
          />
          <Route
            path="training"
            element={
              <Espera>
                <TrainingPage />
              </Espera>
            }
          />
          <Route
            path="transfers/balance"
            element={
              <Espera>
                <PlayerBalancePage />
              </Espera>
            }
          />
          <Route
            path="libro"
            element={
              <Espera>
                <LibroDeVisitasPage />
              </Espera>
            }
          />
          <Route
            path="academy"
            element={
              <Espera>
                <AcademyPage />
              </Espera>
            }
          />
          <Route
            path="matches"
            element={
              <Espera>
                <MatchesPage />
              </Espera>
            }
          />
          <Route
            path="league"
            element={
              <Espera>
                <LeaguePage />
              </Espera>
            }
          />
          <Route
            path="cup"
            element={
              <Espera>
                <CupPage />
              </Espera>
            }
          />
          <Route
            path="rivals"
            element={
              <Espera>
                <RivalPickerPage />
              </Espera>
            }
          />
          <Route
            path="rivals/:rivalHtTeamId"
            element={
              <Espera>
                <RivalPage />
              </Espera>
            }
          />
          <Route
            path="economy"
            element={
              <Espera>
                <EconomyPage />
              </Espera>
            }
          />
          <Route
            path="arena"
            element={
              <Espera>
                <ArenaPage />
              </Espera>
            }
          />
          <Route
            path="insights"
            element={
              <Espera>
                <InsightsPage />
              </Espera>
            }
          />
          <Route
            path="sync"
            element={
              <Espera>
                <SyncPage />
              </Espera>
            }
          />
          <Route
            path="news"
            element={
              <Espera>
                <SyncChangesPage />
              </Espera>
            }
          />
          <Route
            path="transparency"
            element={
              <Espera>
                <TransparencyPage />
              </Espera>
            }
          />
          <Route
            path="wiki"
            element={
              <Espera>
                <WikiPage />
              </Espera>
            }
          />
          {/* Motor se llamaba así hasta el 2026-08-31. El enlace viejo
            sigue funcionando: romper marcadores por un renombre no. */}
          <Route
            path="engine"
            element={<Navigate to="/transparency" replace />}
          />
          {/* Sólo la abre el administrador; el candado está en el
            servidor, no aquí. */}
          <Route
            path="uso"
            element={
              <Espera>
                <UsagePage />
              </Espera>
            }
          />
          <Route
            path="autor"
            element={
              <Espera>
                <AutorPage />
              </Espera>
            }
          />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Route>
      </Routes>
    </>
  );
}
