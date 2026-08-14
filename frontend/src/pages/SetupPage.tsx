import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ErrorState, Loading } from "../components/Panels";
import { SyncProgressPanel } from "../components/SyncProgressPanel";
import { TEAM_ID, setActiveTeamId, useDashboard, useSessionProfile } from "../hooks/useTeam";
import { ApiError, api } from "../services/api";
import type { SyncResult } from "../services/api";

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (typeof error.detail === "string") return error.detail;
    if (error.detail && typeof error.detail === "object" && "detail" in error.detail) {
      const detail = (error.detail as { detail: unknown }).detail;
      if (typeof detail === "string") return detail;
    }
  }
  return error instanceof Error ? error.message : "No fue posible completar la importación.";
}

export function SetupPage() {
  const profile = useSessionProfile();
  const dashboard = useDashboard();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [progress, setProgress] = useState<string[] | null>(null);
  const [completed, setCompleted] = useState<{
    result: SyncResult;
    playerCount: number;
    initialImport: boolean;
  } | null>(null);

  const selectedTeam = profile.data?.teams.find((team) => team.id === TEAM_ID);
  const alreadyImported = Boolean(dashboard.data?.syncedAt);

  useEffect(() => {
    const firstTeam = profile.data?.teams[0];
    if (!firstTeam || selectedTeam) return;
    setActiveTeamId(firstTeam.id);
    window.location.replace("/setup");
  }, [profile.data, selectedTeam]);

  const sync = useMutation({
    mutationFn: () =>
      new Promise<SyncResult>((resolve, reject) => {
        setCompleted(null);
        setProgress([]);
        api.syncStream(TEAM_ID, (event) => {
          if (event.type === "progress") {
            setProgress((current) => [...(current ?? []), event.message]);
          } else if (event.type === "done") {
            resolve(event.result);
          } else {
            reject(new Error(event.message));
          }
        }).catch(reject);
      }),
    onSuccess: async (result) => {
      setProgress(null);
      await queryClient.invalidateQueries();
      const refreshed = await dashboard.refetch();
      setCompleted({
        result,
        playerCount: refreshed.data?.squad?.playerCount ?? 0,
        initialImport: !alreadyImported,
      });
    },
    onError: () => setProgress(null),
  });

  if (profile.isLoading || dashboard.isLoading) return <FullScreen><Loading /></FullScreen>;
  if (profile.isError) return <FullScreen><ErrorState error={profile.error} /></FullScreen>;
  if (dashboard.isError) return <FullScreen><ErrorState error={dashboard.error} /></FullScreen>;
  if (!profile.data || !dashboard.data) return null;

  if (profile.data.teams.length === 0) {
    return (
      <FullScreen>
        <div className="max-w-lg rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-8">
          <h1 className="text-xl font-semibold">No encontramos un club</h1>
          <p className="mt-2 text-sm text-[var(--muted)]">
            Hattrick autenticó la cuenta, pero CHPP no devolvió ningún equipo administrado.
          </p>
          <Link className="mt-6 inline-flex rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white" to="/welcome">
            Volver a conectar
          </Link>
        </div>
      </FullScreen>
    );
  }

  if (!selectedTeam) return <FullScreen><Loading /></FullScreen>;

  const partial = completed?.result.status === "partial";

  return (
    <main className="min-h-screen bg-[var(--bg)] px-4 py-8 sm:px-6 sm:py-12">
      <div className="mx-auto max-w-4xl space-y-6">
        <header className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-[var(--accent)] font-bold text-white">HL</span>
          <div>
            <div className="font-semibold">HT Lens</div>
            <div className="text-xs text-[var(--muted)]">Configuración de tu club</div>
          </div>
        </header>

        <ol className="grid gap-2 sm:grid-cols-3" aria-label="Progreso de configuración">
          <SetupStep number="1" title="Hattrick conectado" state="done" />
          <SetupStep
            number="2"
            title={completed || alreadyImported ? "Datos importados" : "Importar datos"}
            state={completed || alreadyImported ? "done" : "current"}
          />
          <SetupStep number="3" title="Explorar HT Lens" state={completed || alreadyImported ? "current" : "pending"} />
        </ol>

        <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)] shadow-sm">
          <div className="border-b border-[var(--border)] p-6 sm:p-8">
            <p className="text-xs font-medium uppercase tracking-[0.16em] text-[var(--positive)]">
              Conexión CHPP activa
            </p>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
              {completed ? "Tu club está listo" : `${selectedTeam.name} está conectado`}
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)]">
              {completed
                ? "La información real de Hattrick ya está disponible. Ahora puedes revisar el equipo, preparar el próximo partido y seguir el entrenamiento."
                : alreadyImported
                  ? "Este club ya tiene información importada. Puedes entrar directamente o actualizarla antes de continuar."
                  : "Confirma el club y decide cuándo traer sus jugadores, partidos, entrenamiento y finanzas. Nada se importa hasta que pulses el botón."}
            </p>
          </div>

          <div className="grid gap-5 p-6 sm:p-8 lg:grid-cols-[1fr_1.4fr]">
            <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] p-4">
              <div className="text-xs uppercase tracking-wide text-[var(--muted)]">Club seleccionado</div>
              {profile.data.teams.length > 1 ? (
                <select
                  aria-label="Club administrado"
                  className="mt-2 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 font-medium"
                  value={selectedTeam.id}
                  onChange={(event) => {
                    setActiveTeamId(Number(event.target.value));
                    window.location.replace("/setup");
                  }}
                >
                  {profile.data.teams.map((team) => (
                    <option key={team.id} value={team.id}>{team.name}</option>
                  ))}
                </select>
              ) : (
                <div className="mt-2 text-lg font-semibold">{selectedTeam.name}</div>
              )}
              <div className="mt-1 text-sm text-[var(--muted)]">
                {[selectedTeam.seriesName, selectedTeam.leagueName].filter(Boolean).join(" · ")}
              </div>
              <div className="mt-4 border-t border-[var(--border)] pt-3 text-xs text-[var(--muted)]">
                Manager: {profile.data.user.loginName ?? "cuenta Hattrick"}
              </div>
            </div>

            {completed ? (
              <div className="space-y-4">
                <div className={`rounded-xl border p-4 ${partial ? "border-[var(--warning)]/40 bg-[var(--warning)]/10" : "border-[var(--positive)]/40 bg-[var(--positive)]/10"}`}>
                  <div className="font-semibold">
                    {partial
                      ? completed.initialImport ? "Importación inicial completada parcialmente" : "Sincronización completada parcialmente"
                      : completed.initialImport ? "Importación inicial completada" : "Sincronización completada"}
                  </div>
                  <div className="mt-3 grid grid-cols-3 gap-3 text-sm">
                    <SummaryValue value={completed.playerCount} label="jugadores" />
                    <SummaryValue value={completed.result.snapshotsWritten} label="registros guardados" />
                    <SummaryValue value={completed.result.changes.length} label="cambios detectados" />
                  </div>
                  {partial && (
                    <p className="mt-3 text-xs text-[var(--warning)]">
                      {completed.result.errors.join(" · ")}
                    </p>
                  )}
                </div>
                <button
                  className="w-full rounded-lg bg-[var(--accent)] px-4 py-3 text-sm font-semibold text-white"
                  onClick={() => navigate("/dashboard?welcome=1")}
                >
                  Entrar al Dashboard
                </button>
              </div>
            ) : (
              <div className="flex flex-col justify-center">
                <h2 className="font-semibold">{alreadyImported ? "Tus datos ya están disponibles" : "Importación inicial"}</h2>
                <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
                  {alreadyImported
                    ? "La próxima sincronización conservará el historial y mostrará únicamente las diferencias nuevas."
                    : "La primera importación crea la base histórica. Por eso no presenta ausencias de cambios como un error."}
                </p>
                <div className="mt-5 flex flex-col gap-2 sm:flex-row">
                  <button
                    onClick={() => sync.mutate()}
                    disabled={sync.isPending}
                    className="rounded-lg bg-[var(--accent)] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
                  >
                    {sync.isPending ? "Importando…" : alreadyImported ? "Actualizar datos ahora" : "Importar datos del club"}
                  </button>
                  {alreadyImported && (
                    <button
                      onClick={() => navigate("/dashboard")}
                      className="rounded-lg border border-[var(--border)] px-4 py-2.5 text-sm font-medium"
                    >
                      Ir al Dashboard
                    </button>
                  )}
                </div>
                {sync.isError && (
                  <p role="alert" className="mt-4 rounded-lg bg-[var(--danger)]/10 p-3 text-sm text-[var(--danger)]">
                    {errorMessage(sync.error)}
                  </p>
                )}
              </div>
            )}
          </div>

          {progress && <SyncProgressPanel lines={progress} />}
        </section>

        {(completed || alreadyImported) && (
          <section className="grid gap-3 sm:grid-cols-3">
            <NextAction to="/news" title="Revisar cambios" detail="Pops, forma, experiencia y variaciones del club." />
            <NextAction to="/next-match" title="Preparar el partido" detail="Rival, condición, alineación y ratings." />
            <NextAction to="/training" title="Revisar entrenamiento" detail="Carga, progreso y próximas subidas." />
          </section>
        )}
      </div>
    </main>
  );
}

function FullScreen({ children }: { children: React.ReactNode }) {
  return <main className="grid min-h-screen place-items-center bg-[var(--bg)] p-6">{children}</main>;
}

function SetupStep({ number, title, state }: { number: string; title: string; state: "done" | "current" | "pending" }) {
  const tone = state === "done"
    ? "border-[var(--positive)]/40 bg-[var(--positive)]/10 text-[var(--positive)]"
    : state === "current"
      ? "border-[var(--accent)]/40 bg-[var(--accent-soft)] text-[var(--accent)]"
      : "border-[var(--border)] bg-[var(--surface)] text-[var(--muted)]";
  return (
    <li className={`flex items-center gap-3 rounded-xl border px-4 py-3 text-sm ${tone}`}>
      <span className="grid h-6 w-6 place-items-center rounded-full border border-current text-xs font-semibold">
        {state === "done" ? "✓" : number}
      </span>
      <span className="font-medium">{title}</span>
    </li>
  );
}

function SummaryValue({ value, label }: { value: number; label: string }) {
  return (
    <div>
      <div className="text-xl font-semibold">{value}</div>
      <div className="text-xs text-[var(--muted)]">{label}</div>
    </div>
  );
}

function NextAction({ to, title, detail }: { to: string; title: string; detail: string }) {
  return (
    <Link to={to} className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 transition hover:border-[var(--accent)]/50">
      <div className="text-sm font-semibold">{title} →</div>
      <p className="mt-1 text-xs leading-5 text-[var(--muted)]">{detail}</p>
    </Link>
  );
}
