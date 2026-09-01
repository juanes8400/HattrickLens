import { dateTime } from "../hooks/useFormat";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ErrorState, Panel } from "../components/Panels";
import { api } from "../services/api";

/** Qué usa la gente. Sólo la abre el administrador —la comprobación de verdad
 *  está en el servidor, en `require_admin`; esconder el enlace no protege nada.
 *
 *  2026-08-26. Todo lo que se enseña aquí sale de la misma tabla de eventos:
 *  ningún servicio de fuera, ninguna cookie que consentir.
 */

/** `2 h 15 min`, `3 min 20 s`, `45 s`.
 *
 *  Cada tramo se queda con dos unidades: pasado el minuto los segundos
 *  sueltos no se leen, y pasada la hora tampoco los segundos.
 */
function duracion(segundos: number): string {
  if (segundos < 60) return `${segundos} s`;
  const m = Math.floor(segundos / 60);
  if (m < 60) {
    const s = segundos % 60;
    return s === 0 ? `${m} min` : `${m} min ${s} s`;
  }
  const h = Math.floor(m / 60);
  const resto = m % 60;
  return resto === 0 ? `${h} h` : `${h} h ${resto} min`;
}

/** Los minutos que manda el servidor vienen con decimal (`4427.7`). */
function desdeMinutos(minutos: number): string {
  return duracion(Math.round(minutos * 60));
}

function Cifra({ valor, de }: { valor: string; de: string }) {
  return (
    <div className="rounded-md border border-[var(--border)] p-3">
      <div className="text-xs text-[var(--muted)]">{de}</div>
      <div className="mt-1 text-xl font-semibold tabular-nums">{valor}</div>
    </div>
  );
}

const PLAZOS = [7, 30, 90] as const;

export function UsagePage() {
  const [dias, setDias] = useState<number>(30);
  const { data, isLoading, error } = useQuery({
    queryKey: ["usage", dias],
    queryFn: () => api.usage(dias),
  });

  if (error) return <ErrorState error={error} />;

  const th = "px-3 py-2 text-xs font-medium text-[var(--muted)]";
  const td = "px-3 py-2 text-sm";
  const maxMinutos = Math.max(
    ...(data?.modules ?? []).map((m) => m.minutes),
    1,
  );
  const maxHora = Math.max(...Object.values(data?.byHour ?? {}), 1);

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Uso de la aplicación</h1>
          <p className="text-sm text-[var(--muted)]">
            Qué se usa de verdad, medido en tu propio servidor.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {PLAZOS.map((p) => (
            <button
              key={p}
              onClick={() => setDias(p)}
              data-track={`Uso: ${p} dias`}
              className={`rounded-md border px-2 py-1 text-xs ${
                dias === p
                  ? "border-[var(--accent)] text-[var(--accent)]"
                  : "border-[var(--border)] text-[var(--muted)]"
              }`}
            >
              {p} días
            </button>
          ))}
          {/* Descarga directa, sin pasar por React: el navegador la resuelve
              solo. Es la salida de emergencia si la base se pierde —no tiene
              copias y en varios proveedores caduca—. */}
          <a
            href={`/api/v1/usage/export.csv?dias=${Math.max(dias, 365)}`}
            data-track="Uso: exportar CSV"
            className="rounded-md border border-[var(--border)] px-2 py-1 text-xs text-[var(--muted)]"
          >
            Exportar CSV
          </a>
        </div>
      </header>

      {isLoading && <p className="text-sm text-[var(--muted)]">Cargando…</p>}

      {data && data.totals.pages === 0 && (
        <Panel title="Todavía no hay nada que enseñar">
          <p className="p-4 text-sm text-[var(--muted)]">
            La medición empieza el día que se despliega: no hay datos de antes.
            Navega un poco y vuelve.
          </p>
        </Panel>
      )}

      {data && data.totals.pages > 0 && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
            <Cifra de="Sesiones" valor={String(data.totals.sessions)} />
            <Cifra de="Páginas vistas" valor={String(data.totals.pages)} />
            <Cifra de="Clics" valor={String(data.totals.clicks)} />
            <Cifra
              de="Tiempo total"
              valor={desdeMinutos(data.totals.minutes)}
            />
            {/* La MEDIANA, no la media: una pestaña olvidada dispara el
                promedio y deja de describir a nadie. */}
            <Cifra
              de="Sesión típica"
              valor={duracion(data.totals.medianSessionSeconds)}
            />
            <Cifra
              de="Clics por sesión"
              valor={String(data.totals.clicksPerSession)}
            />
          </div>

          <Panel title="Por módulo" meta="ordenado por tiempo dentro">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-[var(--surface-2)]">
                  <tr>
                    <th scope="col" className={`${th} text-left`}>
                      Módulo
                    </th>
                    <th scope="col" className={`${th} text-right`}>
                      Visitas
                    </th>
                    <th scope="col" className={`${th} text-right`}>
                      Clics
                    </th>
                    <th
                      scope="col"
                      className={`${th} text-right`}
                      title="con la pestaña de verdad visible"
                    >
                      Tiempo
                    </th>
                    <th scope="col" className={`${th} text-right`}>
                      Por visita
                    </th>
                    <th scope="col" className={`${th} text-left`}>
                      Reparto
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.modules.map((m) => (
                    <tr
                      key={m.module}
                      className="border-t border-[var(--border)]"
                    >
                      <td className={`${td} font-medium`}>{m.module}</td>
                      <td className={`${td} text-right tabular-nums`}>
                        {m.visits}
                      </td>
                      {/* Cero clics con visitas es la señal interesante: se
                          mira y no se toca nada. */}
                      <td
                        className={`${td} text-right tabular-nums ${
                          m.clicks === 0 ? "text-[var(--warning)]" : ""
                        }`}
                        title={
                          m.clicks === 0
                            ? "se mira, pero no se toca nada"
                            : undefined
                        }
                      >
                        {m.clicks}
                      </td>
                      <td className={`${td} text-right tabular-nums`}>
                        {desdeMinutos(m.minutes)}
                      </td>
                      <td
                        className={`${td} text-right tabular-nums text-[var(--muted)]`}
                      >
                        {duracion(Math.round(m.avgSecondsPerVisit))}
                      </td>
                      <td className={td}>
                        <span className="block h-1.5 w-full rounded bg-[var(--surface-2)]">
                          <span
                            className="block h-full rounded bg-[var(--accent)]"
                            style={{
                              width: `${(m.minutes / maxMinutos) * 100}%`,
                            }}
                          />
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          <div className="grid gap-4 lg:grid-cols-2 [&>*]:min-w-0">
            <Panel title="Lo más pulsado" meta="qué se usa, no qué se mira">
              {data.topControls.length === 0 ? (
                <p className="p-4 text-sm text-[var(--muted)]">
                  Ningún clic todavía.
                </p>
              ) : (
                <ul className="divide-y divide-[var(--border)]">
                  {data.topControls.map((c) => (
                    <li
                      key={c.label}
                      className="flex items-baseline justify-between gap-3 px-4 py-2 text-sm"
                    >
                      <span className="truncate">{c.label}</span>
                      <span className="shrink-0 tabular-nums font-medium">
                        {c.clicks}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            <Panel title="A qué horas" meta="hora del servidor, UTC">
              <div className="flex h-32 items-end gap-[2px] p-4">
                {Array.from({ length: 24 }, (_, h) => {
                  const n = data.byHour[String(h)] ?? 0;
                  return (
                    <span
                      key={h}
                      title={`${h}:00 — ${n} eventos`}
                      className="flex-1 rounded-t bg-[var(--accent)]"
                      style={{ height: `${Math.max(2, (n / maxHora) * 100)}%` }}
                    />
                  );
                })}
              </div>
            </Panel>
          </div>

          <Panel title="Sesiones recientes" meta="las 25 últimas">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-[var(--surface-2)]">
                  <tr>
                    <th scope="col" className={`${th} text-left`}>
                      Empezó
                    </th>
                    <th scope="col" className={`${th} text-right`}>
                      Duró
                    </th>
                    <th scope="col" className={`${th} text-right`}>
                      Páginas
                    </th>
                    <th scope="col" className={`${th} text-right`}>
                      Clics
                    </th>
                    <th scope="col" className={`${th} text-left`}>
                      Por dónde pasó
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.recentSessions.map((s) => (
                    <tr key={s.id} className="border-t border-[var(--border)]">
                      <td className={`${td} tabular-nums`}>
                        {dateTime(s.startedAt)}
                      </td>
                      <td className={`${td} text-right tabular-nums`}>
                        {duracion(s.seconds)}
                      </td>
                      <td className={`${td} text-right tabular-nums`}>
                        {s.pages}
                      </td>
                      <td className={`${td} text-right tabular-nums`}>
                        {s.clicks}
                      </td>
                      <td className={`${td} text-[var(--muted)]`}>
                        {s.modules.join(" · ")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </>
      )}
    </div>
  );
}
