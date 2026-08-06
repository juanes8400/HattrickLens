import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../services/api";
import { TEAM_ID, useLineup } from "../hooks/useTeam";
import { Empty, ErrorState, Kpi, Loading, Note, Panel } from "../components/Panels";
import { PlayerLink } from "../components/PlayerLink";
import { Chart } from "../charts/Chart";
import { barOption } from "../charts/chartOptions";

const FORMATIONS = ["5-5-0", "5-4-1", "5-3-2", "4-5-1", "4-4-2", "4-3-3", "3-5-2", "3-4-3"];
const WEATHER = [
  { id: "", label: "Sin especificar" },
  { id: "sun", label: "Sol" },
  { id: "partly", label: "Parcial" },
  { id: "cloudy", label: "Nublado" },
  { id: "rain", label: "Lluvia" },
];

export function LineupPage() {
  const [formation, setFormation] = useState("");
  const [weather, setWeather] = useState("");
  const { data, isLoading, isError, error } = useLineup(formation || undefined, weather || undefined);

  const impact = useQuery({
    queryKey: ["weather", TEAM_ID, data?.formation],
    queryFn: () => api.weatherImpact(TEAM_ID, data!.formation),
    enabled: !!data,
  });

  const spirit = useQuery({
    queryKey: ["team-spirit-multiplier", TEAM_ID],
    queryFn: () => api.teamSpiritMultiplier(TEAM_ID),
  });

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return <Empty>Sin plantilla sincronizada.</Empty>;

  const lines = {
    forwards: data.lineup.filter((a) => a.position.startsWith("forward")),
    midfield: data.lineup.filter(
      (a) => a.position.startsWith("inner_midfield") || a.position.startsWith("winger"),
    ),
    defence: data.lineup.filter(
      (a) => a.position.startsWith("central_defender") || a.position.startsWith("wingback"),
    ),
    keeper: data.lineup.filter((a) => a.position === "keeper"),
  };

  const Slot = ({ a }: { a: (typeof data.lineup)[number] }) => (
    <div className="min-w-36 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-2 text-center">
      <div className="text-[10px] uppercase tracking-wide text-[var(--muted)]">{a.label}</div>
      <div className="truncate text-sm">
        <PlayerLink htPlayerId={a.htPlayerId} name={a.player} />
      </div>
      <div className="tabular-nums text-base font-semibold text-[var(--accent)]">
        {a.rating.toFixed(2)}
      </div>
    </div>
  );

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Alineación</h1>
          <p className="text-sm text-[var(--muted)]">
            Asignación óptima resuelta con el algoritmo húngaro
          </p>
        </div>
        <div className="flex gap-2">
          <select
            value={formation}
            onChange={(e) => setFormation(e.target.value)}
            aria-label="Formación"
            className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-sm"
          >
            <option value="">Mejor formación</option>
            {FORMATIONS.map((f) => <option key={f}>{f}</option>)}
          </select>
          <select
            value={weather}
            onChange={(e) => setWeather(e.target.value)}
            aria-label="Clima"
            className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-sm"
          >
            {WEATHER.map((w) => <option key={w.id} value={w.id}>{w.label}</option>)}
          </select>
        </div>
      </header>

      <div className="grid gap-4 sm:grid-cols-3">
        <Kpi label="Formación" value={data.formation} />
        <Kpi label="Rating total" value={data.totalRating.toFixed(2)} />
        <Kpi label="Banquillo" value={String(data.bench.length)} />
      </div>

      <div className="space-y-3 rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-4">
        {[lines.forwards, lines.midfield, lines.defence, lines.keeper].map((row, i) => (
          <div key={i} className="flex flex-wrap justify-center gap-2">
            {row.map((a) => <Slot key={a.slot} a={a} />)}
          </div>
        ))}
      </div>

      {data.bench.length > 0 && (
        <Panel title="Banquillo" meta={`${data.bench.length} jugadores`}>
          <ul className="divide-y divide-[var(--border)]">
            {data.bench.map((b) => (
              <li key={b.htPlayerId} className="flex items-center justify-between px-4 py-2 text-sm">
                <PlayerLink htPlayerId={b.htPlayerId} name={b.player} />
                <span className="tabular-nums text-[var(--muted)]">TSI {b.tsi.toLocaleString("es-CO")}</span>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Ranking de formaciones">
          <Chart
            ariaLabel="Rating total por formación"
            option={barOption(
              Object.keys(data.formationRanking),
              Object.values(data.formationRanking),
              "Rating",
            )}
          />
        </Panel>
        <Panel title="Impacto del clima">
          {impact.data ? (
            <>
              <Chart
                ariaLabel="Rating del once según el clima"
                option={barOption(
                  Object.keys(impact.data).map(
                    (k) => ({ rain: "Lluvia", cloudy: "Nublado", partly: "Parcial", sun: "Sol" })[k] ?? k,
                  ),
                  Object.values(impact.data),
                  "Rating",
                )}
              />
              <Note>
                Comparación entre los 4 climas posibles con tu plantilla actual, no un
                pronóstico de qué clima hará en tu próximo partido. Multiplicadores
                aproximados por especialidad (estimados por la comunidad, no confirmados
                oficialmente por CHPP): los técnicos rendirían mejor con sol, los potentes
                con lluvia.
              </Note>
            </>
          ) : (
            <Empty>Calculando…</Empty>
          )}
        </Panel>
      </div>

      <Panel
        title="Espíritu de Equipo × Actitud"
        meta="tabla explorable, no tu Espíritu actual"
      >
        {spirit.data ? (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-[var(--muted)]">
                    <th className="px-4 py-2">Espíritu</th>
                    <th className="px-4 py-2 text-right">PIC</th>
                    <th className="px-4 py-2 text-right">Normal</th>
                    <th className="px-4 py-2 text-right">MOTS</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {spirit.data.rows.map((r) => (
                    <tr key={r.spirit}>
                      <td className="px-4 py-2">{r.spirit}</td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {(r.pic * 100).toFixed(0)}%
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {(r.normal * 100).toFixed(0)}%
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {(r.mots * 100).toFixed(0)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Note>{spirit.data.note}</Note>
          </>
        ) : (
          <Empty>Calculando…</Empty>
        )}
      </Panel>

      <Panel
        title="Calificación por sector"
        meta="fórmula exacta de contribución, segunda opinión sobre este mismo once"
      >
        <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-5">
          {data.sectorRatings.ratings.map((s) => (
            <div key={s.sector} className="rounded-lg border border-[var(--border)] p-3">
              <div className="text-xs text-[var(--muted)]">{s.label}</div>
              <div className="mt-1 text-xl font-semibold tabular-nums text-[var(--accent)]">
                {s.value.toFixed(1)}
              </div>
              <div className="mt-2 space-y-0.5 text-[11px] text-[var(--muted)]">
                {s.topContributors.map((c) => (
                  <div key={c.player} className="truncate">
                    {c.player} <span className="tabular-nums">({c.amount.toFixed(1)})</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
        <Note>{data.sectorRatings.note}</Note>
      </Panel>
    </div>
  );
}
