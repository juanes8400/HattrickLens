import { useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import clsx from "clsx";
import { api, errorMessage } from "../services/api";
import { useDashboard, useSessionProfile } from "../hooks/useTeam";
import { relative } from "../hooks/useFormat";

export const NAV = [
  { section: "Club" },
  { to: "/dashboard", label: "Dashboard" },
  { to: "/club", label: "Club y cuerpo técnico" },
  { to: "/overview", label: "Equipo" },
  { to: "/team", label: "Jugadores" },
  { to: "/positions", label: "Posiciones" },
  { to: "/lineup", label: "Alineación" },
  { section: "Desarrollo" },
  { to: "/training", label: "Entrenamiento" },
  { to: "/academy", label: "Juveniles" },
  { to: "/transfers/balance", label: "Transferencias" },
  { section: "Competición" },
  { to: "/matches", label: "Partidos" },
  { to: "/league", label: "Liga" },
  { to: "/cup", label: "Copa" },
  { to: "/rivals", label: "Rivales" },
  { section: "Negocio" },
  { to: "/economy", label: "Economía" },
  { to: "/arena", label: "Estadio" },
  { section: "Inteligencia" },
  // Sincronización va justo antes de Cambios: es el orden en que se usan
  // (sincronizas y de inmediato miras qué cambió).
  { to: "/sync", label: "Sincronización" },
  { to: "/news", label: "Cambios" },
  { to: "/insights", label: "Alertas" },
  { to: "/transparency", label: "Transparencia" },
];

/** Cómo se llama la página que hay en esa ruta.
 *
 *  Vive pegado a `NAV` a propósito: es la misma lista que ya nombra cada
 *  pantalla en la barra lateral, así que una página nueva se titula sola y
 *  nadie tiene que acordarse de tocar dos sitios --el mismo trato que ya
 *  tiene la telemetría--.
 *
 *  Hasta el 2026-08-30 las veinticinco pantallas compartían el título «HT
 *  Lens»: dos pestañas abiertas eran indistinguibles, el historial del
 *  navegador era una columna del mismo texto repetido y un marcador no decía
 *  a qué apuntaba. */
const RUTAS_CON_DETALLE: { prefijo: string; label: string }[] = [
  { prefijo: "/players/", label: "Jugador" },
  { prefijo: "/rivals/", label: "Rival" },
];

export function tituloDeRuta(pathname: string): string {
  const detalle = RUTAS_CON_DETALLE.find((r) => pathname.startsWith(r.prefijo));
  if (detalle) return `${detalle.label} · HT Lens`;

  // La coincidencia más larga gana: `/transfers/balance` antes que nada que
  // empiece por `/transfers`.
  const enlaces = [...NAV, { to: "/uso", label: "Uso" }].filter(
    (item): item is { to: string; label: string } => "to" in item,
  );
  let mejor: { to: string; label: string } | undefined;
  for (const item of enlaces) {
    if (pathname === item.to || pathname.startsWith(`${item.to}/`)) {
      if (!mejor || item.to.length > mejor.to.length) mejor = item;
    }
  }
  return mejor ? `${mejor.label} · HT Lens` : "HT Lens";
}

function NavigationLinks({ onNavigate }: { onNavigate?: () => void }) {
  // «Uso» sólo se le enseña al dueño de la instalación. Esconder el enlace no
  // protege nada --el candado vive en el servidor-- pero evita enseñar a los
  // demás una puerta que no van a poder abrir.
  const profile = useSessionProfile();
  const items = profile.data?.user.isAdmin
    ? [...NAV, { to: "/uso", label: "Uso" }]
    : NAV;
  return (
    <nav className="flex flex-col gap-0.5">
      {items.map((item, index) =>
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
        <div className="text-sm">{teamName ?? "-"}</div>
        <div className="text-xs text-[var(--muted)]">{[seriesName, leagueName].filter(Boolean).join(" · ")}</div>
      </div>
      <NavigationLinks onNavigate={onNavigate} />
    </>
  );
}

export function AppLayout() {
  const { data } = useDashboard();
  const profile = useSessionProfile();
  const location = useLocation();
  const [banner, setBanner] = useState<{
    tone: "danger" | "warning" | "positive";
    text: string;
  } | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);

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
      {/* Lo primero que alcanza el tabulador. Sin esto había que pasar por
          las VEINTITRÉS paradas de la barra lateral para llegar al contenido,
          en cada página y en cada visita (medido el 2026-08-31). Está oculto
          hasta que recibe el foco: quien usa ratón no lo ve nunca. */}
      <a
        href="#contenido"
        className="fixed left-3 -top-24 z-50 rounded-md border border-[var(--accent)] bg-[var(--surface)] px-4 py-2 text-sm shadow-lg transition-[top] focus:top-3"
      >
        Saltar al contenido
      </a>
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
                <div className="mt-1 text-xs text-[var(--muted)]">{connected ? "Conexión con Hattrick activa" : "La conexión requiere atención"}</div>
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

          {/* 2026-08-15, pedido explícito: sincronizar ocurre en UNA pantalla,
              no desde cualquier parte. Esto ya no dispara nada, informa de la
              antigüedad del dato y lleva a Sincronización. */}
          <Link
            to="/sync"
            className={clsx(
              "rounded-md px-2 py-1.5 text-sm font-medium sm:px-3",
              data?.stale
                ? "bg-[var(--warning)]/15 text-[var(--warning)]"
                : "bg-[var(--positive)]/15 text-[var(--positive)]",
            )}
          >
            <span className="hidden sm:inline">Datos de </span>
            {relative(data?.syncedAt ?? null)}
          </Link>

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

        {/* `tabIndex={-1}` para que el salto deje el foco AQUÍ y no sólo
            mueva el scroll: sin él, el siguiente tabulador volvería al
            principio de la barra lateral. */}
        <main id="contenido" tabIndex={-1} className="p-4 outline-none sm:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
