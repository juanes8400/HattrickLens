import { useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { ApiError, api } from "../services/api";
import type { SyncChange, SyncResult } from "../services/api";
import { TEAM_ID, useDashboard, useSessionProfile, useSquad } from "../hooks/useTeam";
import { relative } from "../hooks/useFormat";
import { SyncChangesFeed } from "../components/SyncChangesFeed";
import { SyncProgressPanel } from "../components/SyncProgressPanel";

function errorMessage(error: unknown): string {
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

const NAV = [
  { section: "Club" },
  { to: "/dashboard", label: "Dashboard" },
  { to: "/club", label: "Club y staff" },
  { to: "/team", label: "Equipo" },
  { to: "/positions", label: "Posiciones" },
  { to: "/lineup", label: "Alineación" },
  { section: "Desarrollo" },
  { to: "/training", label: "Entrenamiento" },
  { to: "/academy", label: "Juveniles" },
  { to: "/transfers/balance", label: "Saldo por jugador" },
  { section: "Competición" },
  { to: "/next-match", label: "Próximo partido" },
  { to: "/matches", label: "Partidos" },
  { to: "/league", label: "Liga" },
  { to: "/cup", label: "Copa" },
  { to: "/rivals", label: "Rivales" },
  { section: "Negocio" },
  { to: "/economy", label: "Economía" },
  { to: "/arena", label: "Estadio" },
  { section: "Inteligencia" },
  { to: "/news", label: "Cambios" },
  { to: "/insights", label: "Alertas" },
  { to: "/engine", label: "Motor" },
];

function NavigationLinks({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-0.5">
      {NAV.map((item, index) =>
        "section" in item ? (
          <div key={index} className="px-2 pb-1 pt-3 text-[11px] uppercase tracking-wide text-[var(--muted)]">
            {item.section}
          </div>
        ) : (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={onNavigate}
            className={({ isActive }) => clsx(
              "rounded-md px-2 py-1.5 text-sm",
              isActive
                ? "bg-[var(--accent-soft)] font-medium text-[var(--accent)]"
                : "text-[var(--muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text)]",
            )}
          >
            {item.label}
          </NavLink>
        ),
      )}
    </nav>
  );
}

function ClubNavigation({
  teamName,
  seriesName,
  leagueName,
  onNavigate,
}: {
  teamName?: string;
  seriesName?: string | null;
  leagueName?: string | null;
  onNavigate?: () => void;
}) {
  return (
    <>
      <div className="mb-3 flex items-center gap-2 px-2 py-1.5 font-semibold">
        <span className="flex h-6 w-6 items-center justify-center rounded-md bg-[var(--accent)] text-xs font-bold text-white">HL</span>
        HT Lens
      </div>
      <div className="mb-4 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-2">
        <div className="text-sm">{teamName ?? "—"}</div>
        <div className="text-xs text-[var(--muted)]">{[seriesName, leagueName].filter(Boolean).join(" · ")}</div>
      </div>
      <NavigationLinks onNavigate={onNavigate} />
    </>
  );
}

export function AppLayout() {
  const { data } = useDashboard();
  const profile = useSessionProfile();
  const squad = useSquad();
  const location = useLocation();
  const queryClient = useQueryClient();
  const [banner, setBanner] = useState<{
    tone: "danger" | "warning" | "positive";
    text: string;
  } | null>(null);
  const [changesPopup, setChangesPopup] = useState<SyncChange[] | null>(null);
  const [progressLog, setProgressLog] = useState<string[] | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);

  const sync = useMutation({
    mutationFn: () => new Promise<SyncResult>((resolve, reject) => {
      setProgressLog([]);
      api.syncStream(TEAM_ID, (event) => {
        if (event.type === "progress") {
          setProgressLog((current) => [...(current ?? []), event.message]);
        } else if (event.type === "done") {
          resolve(event.result);
        } else {
          reject(new Error(event.message));
        }
      }).catch(reject);
    }),
    onSuccess: (result) => {
      setProgressLog(null);
      queryClient.invalidateQueries();
      if (result.status === "partial") {
        setBanner({ tone: "warning", text: `Sincronización parcial: ${result.errors.join(" · ")}` });
        setChangesPopup(null);
      } else if (!data?.syncedAt) {
        setBanner({ tone: "positive", text: `Importación inicial completada: ${result.snapshotsWritten} registros guardados.` });
        setChangesPopup(null);
      } else if (result.changes.length === 0) {
        setBanner({ tone: "positive", text: "Sincronización completada: no hubo cambios nuevos." });
        setChangesPopup(null);
      } else {
        setBanner(null);
        setChangesPopup(result.changes);
      }
    },
    onError: (error) => {
      setProgressLog(null);
      setBanner({ tone: "danger", text: errorMessage(error) });
    },
  });

  const connect = useMutation({
    mutationFn: api.connectChpp,
    onSuccess: ({ authorizeUrl }) => {
      window.location.href = authorizeUrl;
    },
    onError: (error) => setBanner({
      tone: "danger",
      text: `No se pudo reconectar con Hattrick: ${errorMessage(error)}`,
    }),
  });

  const current = NAV.find((item) => "to" in item && item.to === location.pathname);
  const connected = profile.data?.connectionStatus === "active";

  return (
    <div className="flex min-h-screen">
      {mobileOpen && (
        <div className="fixed inset-0 z-30 lg:hidden">
          <button
            className="absolute inset-0 bg-black/55"
            onClick={() => setMobileOpen(false)}
            aria-label="Cerrar menú"
          />
          <aside className="relative h-full w-72 max-w-[86vw] overflow-y-auto border-r border-[var(--border)] bg-[var(--bg)] p-3 shadow-2xl">
            <div className="mb-1 flex justify-end">
              <button className="rounded-md px-2 py-1 text-sm text-[var(--muted)]" onClick={() => setMobileOpen(false)}>Cerrar ×</button>
            </div>
            <ClubNavigation
              teamName={data?.teamName}
              seriesName={data?.seriesName}
              leagueName={data?.leagueName}
              onNavigate={() => setMobileOpen(false)}
            />
          </aside>
        </div>
      )}

      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 overflow-y-auto border-r border-[var(--border)] p-3 lg:block">
        <ClubNavigation teamName={data?.teamName} seriesName={data?.seriesName} leagueName={data?.leagueName} />
      </aside>

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-10 flex items-center gap-2 border-b border-[var(--border)] bg-[var(--bg)]/90 px-3 py-3 backdrop-blur sm:gap-3 sm:px-6">
          <button
            className="rounded-md border border-[var(--border)] px-2 py-1.5 text-sm text-[var(--muted)] lg:hidden"
            onClick={() => setMobileOpen(true)}
            aria-label="Abrir menú"
            aria-expanded={mobileOpen}
          >
            ☰
          </button>

          <nav aria-label="Breadcrumb" className="min-w-0 truncate text-sm text-[var(--muted)]">
            <span className="font-medium text-[var(--text)]">{current && "label" in current ? current.label : "HT Lens"}</span>
            <span className="hidden sm:inline">{data?.teamName && ` · ${data.teamName}`}</span>
          </nav>

          <div className="relative ml-auto">
            <button
              onClick={() => setAccountOpen((open) => !open)}
              aria-expanded={accountOpen}
              className={clsx(
                "rounded-md border px-2 py-1.5 text-sm sm:px-3",
                connected
                  ? "border-[var(--positive)]/30 bg-[var(--positive)]/10 text-[var(--positive)]"
                  : "border-[var(--warning)]/30 bg-[var(--warning)]/10 text-[var(--warning)]",
              )}
            >
              <span aria-hidden="true">{connected ? "✓" : "!"}</span>
              <span className="ml-1 hidden md:inline">{connected ? "Hattrick conectado" : "Reconectar Hattrick"}</span>
            </button>
            {accountOpen && (
              <div className="absolute right-0 top-11 z-20 w-64 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3 shadow-xl">
                <div className="text-sm font-semibold">{profile.data?.user.loginName ?? "Cuenta Hattrick"}</div>
                <div className="mt-1 text-xs text-[var(--muted)]">{connected ? "Conexión CHPP activa" : "La conexión requiere atención"}</div>
                <div className="mt-3 border-t border-[var(--border)] pt-3">
                  <Link to="/setup" className="block rounded-md px-2 py-1.5 text-sm hover:bg-[var(--surface-2)]">Club e importación</Link>
                  <button
                    onClick={() => connect.mutate()}
                    disabled={connect.isPending}
                    className="mt-1 w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-[var(--surface-2)] disabled:opacity-60"
                  >
                    {connect.isPending ? "Abriendo Hattrick…" : "Reconectar con Hattrick"}
                  </button>
                </div>
              </div>
            )}
          </div>

          <button
            onClick={() => sync.mutate()}
            disabled={sync.isPending}
            className={clsx(
              "rounded-md px-2 py-1.5 text-sm font-medium sm:px-3",
              data?.stale
                ? "bg-[var(--warning)]/15 text-[var(--warning)]"
                : "bg-[var(--positive)]/15 text-[var(--positive)]",
            )}
          >
            {sync.isPending ? "Sincronizando…" : <><span className="hidden sm:inline">Sincronizar · </span>{relative(data?.syncedAt ?? null)}</>}
          </button>

          <button
            onClick={() => {
              const root = document.documentElement;
              root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
            }}
            aria-label="Cambiar tema"
            className="rounded-md border border-[var(--border)] px-2 py-1.5 text-sm text-[var(--muted)]"
          >
            ●
          </button>
        </header>

        {progressLog && <SyncProgressPanel lines={progressLog} />}

        {banner && (
          <div
            role="alert"
            className={clsx(
              "flex items-center justify-between gap-3 border-b px-4 py-2 text-sm sm:px-6",
              banner.tone === "danger"
                ? "border-[var(--danger)]/30 bg-[var(--danger)]/10 text-[var(--danger)]"
                : banner.tone === "warning"
                  ? "border-[var(--warning)]/30 bg-[var(--warning)]/10 text-[var(--warning)]"
                  : "border-[var(--positive)]/30 bg-[var(--positive)]/10 text-[var(--positive)]",
            )}
          >
            <span>{banner.text}</span>
            <button onClick={() => setBanner(null)} aria-label="Descartar aviso" className="shrink-0 opacity-70 hover:opacity-100">×</button>
          </div>
        )}

        {changesPopup && (
          <SyncChangesFeed
            changes={changesPopup}
            onDismiss={() => setChangesPopup(null)}
            playerLinks={Object.fromEntries((squad.data?.players ?? []).map((player) => [player.name, player.htPlayerId]))}
          />
        )}

        <main className="p-4 sm:p-6"><Outlet /></main>
      </div>
    </div>
  );
}
