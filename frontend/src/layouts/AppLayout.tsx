import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { ApiError, api } from "../services/api";
import type { SyncChange, SyncResult } from "../services/api";
import { TEAM_ID, useDashboard, useSquad } from "../hooks/useTeam";
import { relative } from "../hooks/useFormat";
import { SyncChangesFeed } from "../components/SyncChangesFeed";
import { SyncProgressPanel } from "../components/SyncProgressPanel";

/** El backend habla en español (HTTPException(detail=...)); si no hay detalle
 * legible, mejor el mensaje genérico que un "[object Object]". */
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
  { to: "/transfers", label: "Transferencias" },
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

export function AppLayout() {
  const { data } = useDashboard();
  const squad = useSquad();
  const location = useLocation();
  const qc = useQueryClient();
  const [banner, setBanner] = useState<{ tone: "danger" | "warning"; text: string } | null>(null);
  // 2026-08-05, pedido explícitamente: "la tab o pop up con notificaciones
  // debe verse inmediatamente hayas hecho un sync" — antes SOLO se veía si
  // el usuario navegaba a mano a /news; ahora aparece aquí, en el layout
  // compartido, sin importar desde qué página se sincronizó. Solo lo
  // marginalmente nuevo: `result.changes` ya es el diff contra el snapshot
  // anterior (mismo dato que /news), nunca acumulado entre syncs.
  const [changesPopup, setChangesPopup] = useState<SyncChange[] | null>(null);
  // 2026-08-05, pedido explícitamente ("mira cómo lo hace Hattrick
  // Control"): la ventana "Conexión" de HC muestra en vivo qué se está
  // bajando. `null` = no hay sync en curso; array = líneas recibidas hasta
  // ahora (vacío justo al conectar).
  const [progressLog, setProgressLog] = useState<string[] | null>(null);

  const sync = useMutation({
    mutationFn: () =>
      new Promise<SyncResult>((resolve, reject) => {
        setProgressLog([]);
        api
          .syncStream(TEAM_ID, (event) => {
            if (event.type === "progress") {
              setProgressLog((prev) => [...(prev ?? []), event.message]);
            } else if (event.type === "done") {
              resolve(event.result);
            } else {
              reject(new Error(event.message));
            }
          })
          .catch(reject);
      }),
    onSuccess: (result) => {
      setProgressLog(null);
      qc.invalidateQueries();
      if (result.status === "partial") {
        setBanner({ tone: "warning", text: `Sync parcial: ${result.errors.join(" · ")}` });
        setChangesPopup(null);
      } else if (result.changes.length === 0) {
        setBanner({ tone: "warning", text: "Sync completado: no hubo cambios nuevos." });
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
    mutationFn: () => api.connectChpp(),
    onSuccess: ({ authorizeUrl }) => {
      window.location.href = authorizeUrl;
    },
    onError: (error) =>
      setBanner({ tone: "danger", text: `No se pudo conectar con Hattrick: ${errorMessage(error)}` }),
  });

  const current = NAV.find((n) => "to" in n && n.to === location.pathname);

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 overflow-y-auto border-r border-[var(--border)] p-3 lg:block">
        <div className="mb-3 flex items-center gap-2 px-2 py-1.5 font-semibold">
          <span className="flex h-6 w-6 items-center justify-center rounded-md bg-[var(--accent)] text-xs font-bold text-white">
            HL
          </span>
          HT Lens
        </div>

        <div className="mb-4 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-2">
          <div className="text-sm">{data?.teamName ?? "—"}</div>
          <div className="text-xs text-[var(--muted)]">
            {data?.seriesName} · {data?.leagueName}
          </div>
        </div>

        <nav className="flex flex-col gap-0.5">
          {NAV.map((item, i) =>
            "section" in item ? (
              <div
                key={i}
                className="px-2 pb-1 pt-3 text-[11px] uppercase tracking-wide text-[var(--muted)]"
              >
                {item.section}
              </div>
            ) : (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  clsx(
                    "rounded-md px-2 py-1.5 text-sm",
                    isActive
                      ? "bg-[var(--accent-soft)] font-medium text-[var(--accent)]"
                      : "text-[var(--muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text)]",
                  )
                }
              >
                {item.label}
              </NavLink>
            ),
          )}
        </nav>
      </aside>

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-10 flex items-center gap-3 border-b border-[var(--border)] bg-[var(--bg)]/90 px-6 py-3 backdrop-blur">
          <nav aria-label="Breadcrumb" className="text-sm text-[var(--muted)]">
            <span className="font-medium text-[var(--text)]">
              {current && "label" in current ? current.label : "HT Lens"}
            </span>
            {data?.teamName && ` · ${data.teamName}`}
          </nav>

          <button
            onClick={() => connect.mutate()}
            disabled={connect.isPending}
            className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--muted)] hover:text-[var(--text)]"
          >
            {connect.isPending ? "Conectando…" : "Conectar con Hattrick"}
          </button>

          <button
            onClick={() => sync.mutate()}
            disabled={sync.isPending}
            className={clsx(
              "ml-auto rounded-md px-3 py-1.5 text-sm font-medium",
              data?.stale
                ? "bg-[var(--warning)]/15 text-[var(--warning)]"
                : "bg-[var(--positive)]/15 text-[var(--positive)]",
            )}
          >
            {sync.isPending ? "Sincronizando…" : `Sync · ${relative(data?.syncedAt ?? null)}`}
          </button>

          <button
            onClick={() => {
              const el = document.documentElement;
              el.dataset.theme = el.dataset.theme === "dark" ? "light" : "dark";
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
              "flex items-center justify-between gap-3 border-b px-6 py-2 text-sm",
              banner.tone === "danger"
                ? "border-[var(--danger)]/30 bg-[var(--danger)]/10 text-[var(--danger)]"
                : "border-[var(--warning)]/30 bg-[var(--warning)]/10 text-[var(--warning)]",
            )}
          >
            <span>{banner.text}</span>
            <button
              onClick={() => setBanner(null)}
              aria-label="Descartar aviso"
              className="shrink-0 opacity-70 hover:opacity-100"
            >
              ×
            </button>
          </div>
        )}

        {changesPopup && (
          <SyncChangesFeed
            changes={changesPopup}
            onDismiss={() => setChangesPopup(null)}
            playerLinks={Object.fromEntries(
              (squad.data?.players ?? []).map((p) => [p.name, p.htPlayerId]),
            )}
          />
        )}

        <main className="p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
