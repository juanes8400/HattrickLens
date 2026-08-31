import { useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import clsx from "clsx";
import { api, errorMessage } from "../services/api";
import { useDashboard, useSessionProfile } from "../hooks/useTeam";
import { relative } from "../hooks/useFormat";
import { NAV, agrupar } from "./navegacion";
import { SIGUIENTE_TEMA, useTema, type Tema } from "../hooks/useTheme";

function NavigationLinks({ onNavigate }: { onNavigate?: () => void }) {
  // «Uso» sólo se le enseña al dueño de la instalación. Esconder el enlace no
  // protege nada --el candado vive en el servidor-- pero evita enseñar a los
  // demás una puerta que no van a poder abrir.
  const profile = useSessionProfile();
  const items = profile.data?.user.isAdmin
    ? [...NAV, { to: "/uso", label: "Uso" }]
    : NAV;
  return (
    // El menú es uno de los dos landmarks de navegación de la página --el otro
    // son las migas, que sí se llamaban «Breadcrumb»--. Sin nombre, el menú de
    // verdad era el que aparecía como «navigation» a secas (2026-08-31).
    <nav aria-label="Secciones de HT Lens" className="flex flex-col gap-0.5">
      {agrupar(items).map((grupo) => (
        <div key={grupo.titulo} className="flex flex-col gap-0.5">
          {/* El rótulo se pinta aquí y se REPITE como nombre de la lista de
              abajo; por eso se oculta a la lectura, para no oírlo dos veces.
              Las mayúsculas van por CSS y no en el texto, así que se sigue
              pronunciando «Club» y no «ce-ele-u-be». */}
          <div
            aria-hidden="true"
            className="px-2 pb-1 pt-3 text-[11px] uppercase tracking-wide text-[var(--muted)]"
          >
            {grupo.titulo}
          </div>
          {/* Una lista de verdad por grupo: los veinte enlaces eran hermanos
              sueltos, así que la agrupación que se ve --cinco bloques
              temáticos-- no existía para quien no la ve. Con `ul` se oye
              «lista de 6, elemento 3» y se sabe cuánto queda. */}
          <ul
            aria-label={grupo.titulo}
            className="flex list-none flex-col gap-0.5"
          >
            {grupo.enlaces.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    clsx(
                      "block rounded-md px-2 py-1.5 text-sm",
                      isActive
                        ? "bg-[var(--accent-soft)] font-medium text-[var(--accent)]"
                        : "text-[var(--muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text)]",
                    )
                  }
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      ))}
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
        <span className="flex h-6 w-6 items-center justify-center rounded-md bg-[var(--accent)] text-xs font-bold text-white">
          HL
        </span>
        HT Lens
      </div>
      <div className="mb-4 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-2">
        <div className="text-sm">{teamName ?? "-"}</div>
        <div className="text-xs text-[var(--muted)]">
          {[seriesName, leagueName].filter(Boolean).join(" · ")}
        </div>
      </div>
      <NavigationLinks onNavigate={onNavigate} />
    </>
  );
}

/** Cómo se llama cada estado del tema en voz alta. El ciclo vive junto al
 *  tipo, en `useTheme`, porque es lógica y se prueba aparte. */
const ETIQUETA_TEMA: Record<Tema, string> = {
  sistema: "el del sistema",
  claro: "claro",
  oscuro: "oscuro",
};
const ICONO_TEMA: Record<Tema, string> = {
  sistema: "◐",
  claro: "○",
  oscuro: "●",
};

export function AppLayout() {
  const [tema, cambiarTema] = useTema();
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
    onError: (error) =>
      setBanner({
        tone: "danger",
        text: `No se pudo reconectar con Hattrick: ${errorMessage(error)}`,
      }),
  });

  const current = NAV.find(
    (item) => "to" in item && item.to === location.pathname,
  );
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
              <button
                className="rounded-md px-2 py-1 text-sm text-[var(--muted)]"
                onClick={() => setMobileOpen(false)}
              >
                Cerrar ×
              </button>
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
        <ClubNavigation
          teamName={data?.teamName}
          seriesName={data?.seriesName}
          leagueName={data?.leagueName}
        />
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

          <nav
            aria-label="Breadcrumb"
            className="min-w-0 truncate text-sm text-[var(--muted)]"
          >
            <span className="font-medium text-[var(--text)]">
              {current && "label" in current ? current.label : "HT Lens"}
            </span>
            <span className="hidden sm:inline">
              {data?.teamName && ` · ${data.teamName}`}
            </span>
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
              <span className="ml-1 hidden md:inline">
                {connected ? "Hattrick conectado" : "Reconectar Hattrick"}
              </span>
            </button>
            {accountOpen && (
              <div className="absolute right-0 top-11 z-20 w-64 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3 shadow-xl">
                <div className="text-sm font-semibold">
                  {profile.data?.user.loginName ?? "Cuenta Hattrick"}
                </div>
                <div className="mt-1 text-xs text-[var(--muted)]">
                  {connected
                    ? "Conexión con Hattrick activa"
                    : "La conexión requiere atención"}
                </div>
                <div className="mt-3 border-t border-[var(--border)] pt-3">
                  <Link
                    to="/setup"
                    className="block rounded-md px-2 py-1.5 text-sm hover:bg-[var(--surface-2)]"
                  >
                    Club e importación
                  </Link>
                  <button
                    onClick={() => connect.mutate()}
                    disabled={connect.isPending}
                    className="mt-1 w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-[var(--surface-2)] disabled:opacity-60"
                  >
                    {connect.isPending
                      ? "Abriendo Hattrick…"
                      : "Reconectar con Hattrick"}
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

          {/* Tres estados, no dos: el ciclo tiene que poder VOLVER a seguir
              al sistema, o el primer clic encierra al usuario fuera de su
              propia preferencia para siempre. El nombre accesible dice en
              cuál está, porque el estado no puede vivir sólo en el icono. */}
          <button
            onClick={() => cambiarTema(SIGUIENTE_TEMA[tema])}
            aria-label={`Tema: ${ETIQUETA_TEMA[tema]}. Cambiar a ${ETIQUETA_TEMA[SIGUIENTE_TEMA[tema]]}`}
            title={`Tema: ${ETIQUETA_TEMA[tema]}`}
            className="rounded-md border border-[var(--border)] px-2 py-1.5 text-sm text-[var(--muted)]"
          >
            <span aria-hidden="true">{ICONO_TEMA[tema]}</span>
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
            <button
              onClick={() => setBanner(null)}
              aria-label="Descartar aviso"
              className="shrink-0 opacity-70 hover:opacity-100"
            >
              ×
            </button>
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
