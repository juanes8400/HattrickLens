import { useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { setActiveTeamId } from "../hooks/useTeam";

/** Destino del callback CHPP: conserva el club elegido y abre la importación. */
export function ConnectedPage() {
  const [params] = useSearchParams();
  const teamId = Number(params.get("teamId"));

  useEffect(() => {
    if (!Number.isInteger(teamId) || teamId <= 0) return;
    setActiveTeamId(teamId);
    // TEAM_ID se evalúa al cargar el módulo; una recarga real garantiza que
    // todo el árbol use el club recién seleccionado.
    window.location.replace("/setup");
  }, [teamId]);

  if (!Number.isInteger(teamId) || teamId <= 0) {
    return (
      <main className="grid min-h-screen place-items-center bg-[var(--bg)] p-6">
        <section className="max-w-md rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-8 text-center">
          <h1 className="text-xl font-semibold">
            La conexión quedó incompleta
          </h1>
          <p className="mt-2 text-sm leading-6 text-[var(--muted)]">
            Hattrick no devolvió un club seleccionable. Puedes repetir la
            autorización sin perder información previa.
          </p>
          <Link
            to="/welcome"
            className="mt-6 inline-flex rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white"
          >
            Volver a conectar
          </Link>
        </section>
      </main>
    );
  }

  return (
    <main className="grid min-h-screen place-items-center bg-[var(--bg)] p-6">
      <div className="text-center">
        <div className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-[var(--positive)]/15 text-xl text-[var(--positive)]">
          ✓
        </div>
        <div className="mt-4 font-semibold">Hattrick conectado</div>
        <div className="mt-1 text-sm text-[var(--muted)]">
          Preparando la importación de tu club…
        </div>
      </div>
    </main>
  );
}
