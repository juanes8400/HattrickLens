import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ErrorState, Loading, Panel } from "../components/Panels";
import { relative } from "../hooks/useFormat";
import { api, errorMessage } from "../services/api";

/**
 * El libro de visitas.
 *
 * 2026-09-05, pedido por el usuario: un sitio donde quien usa HT Lens deje un
 * mensaje, y de donde salgan las funcionalidades siguientes.
 *
 * Firma con el nombre del CLUB, no con el de la cuenta: en Hattrick uno se
 * conoce por su equipo. No hay campo de nombre porque no hace falta —quien
 * escribe ya está identificado por su sesión— y un campo menos es un campo
 * que nadie rellena mal.
 */

/** Lo que cabe en una firma, el mismo número que valida el servidor. Se
 *  escribe aquí para poder avisar ANTES de mandar; el servidor sigue siendo
 *  quien manda. */
const MAXIMO = 1000;

export function LibroDeVisitasPage() {
  const qc = useQueryClient();
  const [texto, setTexto] = useState("");
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["guestbook"],
    queryFn: () => api.guestbook(),
  });

  const firmar = useMutation({
    mutationFn: (mensaje: string) => api.signGuestbook(mensaje),
    onSuccess: () => {
      setTexto("");
      qc.invalidateQueries({ queryKey: ["guestbook"] });
    },
  });

  const limpio = texto.trim();
  const puedeEnviar = limpio.length > 0 && limpio.length <= MAXIMO;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Libro de visitas</h1>
        <p className="prosa text-sm text-[var(--muted)]">
          Cuéntame qué te está sirviendo y qué te falta. De aquí salen las
          funcionalidades siguientes.
        </p>
      </header>

      <Panel title="Deja tu mensaje">
        <div className="space-y-3 p-4">
          <label className="block">
            <span className="sr-only">Tu mensaje</span>
            <textarea
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              rows={4}
              maxLength={MAXIMO}
              placeholder="Qué usas, qué te falta, qué te sobra…"
              className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--text)]"
            />
          </label>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-xs text-[var(--muted)]">
              Firmas con el nombre de tu club, no con el de tu cuenta.
            </span>
            <div className="flex items-center gap-3">
              {/* El contador sólo aparece cerca del tope: enseñarlo desde el
                  primer carácter mete prisa a quien está escribiendo. */}
              {limpio.length > MAXIMO - 200 && (
                <span className="tabular-nums text-xs text-[var(--muted)]">
                  {limpio.length} / {MAXIMO}
                </span>
              )}
              <button
                onClick={() => firmar.mutate(limpio)}
                disabled={!puedeEnviar || firmar.isPending}
                className="rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
              >
                {firmar.isPending ? "Enviando…" : "Firmar"}
              </button>
            </div>
          </div>
          {firmar.isError && (
            <p className="text-sm text-[var(--danger)]">
              {errorMessage(firmar.error)}
            </p>
          )}
        </div>
      </Panel>

      <Panel title="Firmas" meta={data ? `${data.entries.length}` : ""}>
        {isLoading ? (
          <Loading />
        ) : isError ? (
          <ErrorState error={error} />
        ) : data && data.entries.length > 0 ? (
          <ul className="divide-y divide-[var(--border)]">
            {data.entries.map((f) => (
              <li key={f.id} className="px-4 py-3">
                <div className="flex flex-wrap items-baseline gap-x-2">
                  <span className="text-sm font-medium">
                    {f.teamName || "Un club sin nombre todavía"}
                  </span>
                  {f.country && (
                    <span className="text-xs text-[var(--muted)]">
                      {f.country}
                    </span>
                  )}
                  <span className="text-xs text-[var(--muted)]">
                    · {relative(f.createdAt)}
                  </span>
                </div>
                {/* `whitespace-pre-line` respeta los saltos que escribió
                    quien firma, sin admitir ningún marcado: el texto se pinta
                    como texto y nunca como HTML. */}
                <p className="prosa mt-1 whitespace-pre-line text-sm leading-relaxed">
                  {f.message}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="prosa p-4 text-sm text-[var(--muted)]">
            Todavía no ha firmado nadie. Estrénalo tú.
          </p>
        )}
      </Panel>
    </div>
  );
}
