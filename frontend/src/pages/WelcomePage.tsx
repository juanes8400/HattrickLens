import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ApiError, api } from "../services/api";

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    if (typeof error.detail === "string") return error.detail;
    if (error.status === 0 || error.status === 502) {
      return "No se pudo contactar el servicio local. Comprueba que el backend esté en marcha.";
    }
  }
  return "No fue posible iniciar la conexión. Inténtalo de nuevo en unos segundos.";
}

/** Primer punto de contacto. Ningún dato de Hattrick se solicita hasta que el
 * manager decide iniciar el flujo OAuth oficial. */
export function WelcomePage() {
  const [error, setError] = useState<string | null>(null);
  const connect = useMutation({
    mutationFn: api.connectChpp,
    onSuccess: ({ authorizeUrl }) => {
      window.location.assign(authorizeUrl);
    },
    onError: (reason) => setError(messageFor(reason)),
  });

  return (
    <main className="grid min-h-screen place-items-center bg-[var(--bg)] px-6 py-12">
      <section className="w-full max-w-xl rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-8 shadow-sm sm:p-10">
        <div className="mb-8 flex items-center gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-xl bg-[var(--accent)] font-bold text-white">HL</span>
          <div>
            <p className="text-lg font-semibold">HT Lens</p>
            <p className="text-sm text-[var(--muted)]">Tu centro de mando para Hattrick</p>
          </div>
        </div>

        <p className="text-xs font-medium uppercase tracking-[0.16em] text-[var(--accent)]">Empieza con tus datos reales</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">Conecta tu club</h1>
        <p className="mt-3 max-w-md leading-6 text-[var(--muted)]">
          Autoriza HT Lens mediante la conexión oficial de Hattrick. Después podrás sincronizar tu plantilla,
          entrenamiento, finanzas y partidos cuando tú lo decidas.
        </p>

        <div className="mt-7 space-y-3 rounded-xl bg-[var(--surface-2)] p-4 text-sm">
          <div className="flex gap-3"><span className="font-semibold text-[var(--accent)]">01</span><p><b>Inicia sesión en Hattrick.</b><br /><span className="text-[var(--muted)]">La autorización se realiza en Hattrick.org.</span></p></div>
          <div className="flex gap-3"><span className="font-semibold text-[var(--accent)]">02</span><p><b>Elige tu club.</b><br /><span className="text-[var(--muted)]">Volverás aquí con tu equipo real seleccionado.</span></p></div>
          <div className="flex gap-3"><span className="font-semibold text-[var(--accent)]">03</span><p><b>Sincroniza bajo demanda.</b><br /><span className="text-[var(--muted)]">HT Lens nunca descarga datos automáticamente.</span></p></div>
        </div>

        {error && <p role="alert" className="mt-5 rounded-lg bg-[var(--danger)]/10 p-3 text-sm text-[var(--danger)]">{error}</p>}

        <button
          type="button"
          onClick={() => { setError(null); connect.mutate(); }}
          disabled={connect.isPending}
          className="mt-7 w-full rounded-lg bg-[var(--accent)] px-4 py-3 text-sm font-semibold text-white transition hover:brightness-95 disabled:cursor-wait disabled:opacity-70"
        >
          {connect.isPending ? "Abriendo Hattrick…" : "Conectar con Hattrick"}
        </button>
        <p className="mt-4 text-center text-xs leading-5 text-[var(--muted)]">
          HT Lens usa información de Hattrick.org con autorización de sus propietarios. Tus credenciales de Hattrick nunca pasan por esta aplicación.
        </p>
      </section>
    </main>
  );
}
