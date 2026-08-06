import {
  useDashboard,
  useInsights,
  useLeague,
  useLeagueComparison,
  useLineup,
} from "../hooks/useTeam";
import { Empty, ErrorState, Kpi, Loading, Note, Panel } from "../components/Panels";
import { Chart } from "../charts/Chart";
import { barOption, radarOption } from "../charts/chartOptions";
import { money, number } from "../hooks/useFormat";

export function DashboardPage() {
  const { data, isLoading, isError, error } = useDashboard();
  const insights = useInsights();
  const lineup = useLineup();

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return null;

  const cur = data.finance?.currency ?? "";

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-semibold">{data.teamName}</h1>
        <p className="text-sm text-[var(--muted)]">
          {data.squad?.playerCount ?? 0} jugadores · edad media {data.squad?.avgAge ?? "—"}
        </p>
      </header>

      <ClubRadar teamName={data.teamName} />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi label="Caja" value={money(data.finance?.cash ?? 0)} hint={cur} />
        <Kpi
          label="Balance estructural"
          value={`${money(data.finance?.structuralBalance ?? 0)}/sem`}
          hint="sin transferencias"
          tone={(data.finance?.structuralBalance ?? 0) < 0 ? "danger" : "positive"}
        />
        <Kpi label="Salarios" value={money(data.squad?.totalSalary ?? 0)} hint={cur} />
        <Kpi label="TSI total" value={number(data.squad?.totalTsi ?? 0)} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Panel title="Mejor once" meta={lineup.data ? `${lineup.data.formation} · ${lineup.data.totalRating}` : ""}>
            {lineup.data ? (
              <Chart
                ariaLabel="Rating de cada jugador del once ideal"
                height={320}
                option={barOption(
                  lineup.data.lineup.map((a) => `${a.label} · ${a.player}`),
                  lineup.data.lineup.map((a) => a.rating),
                  "Rating",
                )}
              />
            ) : (
              <Empty>Sincroniza para calcular la alineación.</Empty>
            )}
            <Note>
              El optimizador resuelve la asignación óptima de la plantilla a los once puestos.
              Elegir el mejor jugador para cada puesto por separado produce equipos peores.
            </Note>
          </Panel>
        </div>

        <Panel title="Alertas" meta={`${insights.data?.length ?? 0} activas`}>
          {insights.data?.length ? (
            <ul>
              {insights.data.slice(0, 5).map((i) => (
                <li key={i.key} className="border-b border-[var(--border)] px-4 py-3 last:border-0">
                  <div className="text-sm font-medium">{i.title}</div>
                  <p className="mt-0.5 text-xs text-[var(--muted)]">{i.detail}</p>
                </li>
              ))}
            </ul>
          ) : (
            <Empty>Nada requiere tu atención.</Empty>
          )}
        </Panel>
      </div>

      {data.training && (
        <Panel title="Entrenamiento" meta={data.training.typeName}>
          <dl className="grid grid-cols-2 gap-3 p-4 text-sm sm:grid-cols-4">
            <div><dt className="text-[var(--muted)]">Intensidad</dt><dd>{data.training.level}%</dd></div>
            <div><dt className="text-[var(--muted)]">Resistencia</dt><dd>{data.training.staminaPart}%</dd></div>
            <div><dt className="text-[var(--muted)]">Entrenador</dt><dd>{data.training.trainerName}</dd></div>
            <div><dt className="text-[var(--muted)]">Espíritu</dt><dd>{data.training.moraleName}</dd></div>
          </dl>
        </Panel>
      )}
    </div>
  );
}

/**
 * Radar de fuerza — lo primero que se ve al entrar. Cuatro ejes, todos
 * relativos a la propia serie (no números absolutos inventados):
 *
 * - Ataque/Defensa: `attackStrength`/`defenceStrength` del simulador de
 *   temporada (Poisson + encogimiento bayesiano), donde 1,0 ya es "exactamente
 *   la media de la liga" — se reescala a 50 en el eje.
 * - TSI en la liga / Posición esperada: percentil real dentro de la serie
 *   (comparativa de TSI y simulación), 100 = mejor de la serie.
 *
 * Deliberadamente NO incluye economía ni afición: no hay con qué compararlas
 * de forma justa dentro de la serie (a diferencia de ataque/defensa/TSI/
 * posición, que sí son relativos a los demás equipos), así que forzarlas al
 * mismo radar sería fingir una escala que no existe.
 */
function ClubRadar({ teamName }: { teamName: string }) {
  const league = useLeague();
  const comparison = useLeagueComparison(false, true, false);

  if (league.isLoading || comparison.isLoading) {
    return (
      <Panel title="Radar de fuerza">
        <div className="p-4"><Loading /></div>
      </Panel>
    );
  }

  const own = league.data?.ownOutlook;
  const n = comparison.data?.teamsInSeries ?? 0;
  const rank = comparison.data?.ownRank ?? 0;
  if (!own || !league.data || n < 2) {
    return (
      <Panel title="Radar de fuerza">
        <Empty>Sincroniza la clasificación de tu liga para ver el radar.</Empty>
      </Panel>
    );
  }

  const clamp = (v: number) => Math.max(0, Math.min(100, v));
  const attackAxis = clamp(own.attackStrength * 50);
  const defenceAxis = clamp((2 - own.defenceStrength) * 50);
  const tsiAxis = clamp((1 - (rank - 1) / (n - 1)) * 100);
  const positionAxis = clamp((1 - (own.expectedPosition - 1) / (n - 1)) * 100);

  const indicators = [
    { name: "Ataque", max: 100 },
    { name: "Posición esperada", max: 100 },
    { name: "Defensa", max: 100 },
    { name: "TSI en la liga", max: 100 },
  ];

  return (
    <Panel title="Radar de fuerza" meta={`relativo a ${league.data.seriesName ?? "tu liga"}`}>
      <Chart
        ariaLabel="Radar de fuerza del equipo, relativo a la media de la liga"
        height={300}
        option={radarOption(indicators, [
          { name: teamName, value: [attackAxis, positionAxis, defenceAxis, tsiAxis] },
        ])}
      />
      <Note>
        50 es la media de {league.data.seriesName}, 100 el mejor de la serie en ese eje.
        Ataque/Defensa vienen del simulador de temporada; TSI y posición esperada, del ranking
        real. No incluye economía ni afición: no hay con qué compararlas de forma justa dentro
        de la serie.
      </Note>
    </Panel>
  );
}
