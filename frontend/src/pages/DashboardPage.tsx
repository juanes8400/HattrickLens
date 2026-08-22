import { useState } from "react";
import {
  useArchiveInsight,
  useDashboard,
  useInsights,
  useLeague,
  useLeagueComparison,
  useLineup,
} from "../hooks/useTeam";
import { Link, useSearchParams } from "react-router-dom";
import { Empty, ErrorState, Kpi, Loading, Note, Panel } from "../components/Panels";
import { InsightRow, SeverityTally } from "../components/Insights";
import { Chart } from "../charts/Chart";
import { PITCH_CARD_CLASS, PitchField, PitchGrid } from "../components/PitchField";
import { SplitSelector } from "../components/SplitSelector";
import { FORMATIONS } from "../services/api";
import type { Dashboard } from "../services/api";
import { radarOption } from "../charts/chartOptions";
import { decimal, money, number } from "../hooks/useFormat";
import type { Insight } from "../services/api";

export function DashboardPage() {
  const [params] = useSearchParams();
  const { data, isLoading, isError, error } = useDashboard();
  const insights = useInsights();
  // Mismos mandos que en Alineación: formación y, dentro de ella, cuántos
  // juegan por el centro. Vacío = que el optimizador elija la formación.
  const [formacion, setFormacion] = useState("");
  const [centrales, setCentrales] = useState<number | undefined>(undefined);
  const [interiores, setInteriores] = useState<number | undefined>(undefined);
  const lineup = useLineup(formacion || undefined, centrales, interiores);

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return null;

  const cur = data.finance?.currency ?? "";

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-semibold">{data.teamName}</h1>
        <p className="text-sm text-[var(--muted)]">
          {data.squad?.playerCount ?? 0} jugadores · edad media {data.squad?.avgAge ?? "-"}
        </p>
      </header>

      {params.get("welcome") === "1" && (
        <section className="rounded-xl border border-[var(--accent)]/30 bg-[var(--accent-soft)] p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-[var(--accent)]">Importación completada</p>
              <h2 className="mt-1 text-lg font-semibold">Empieza por una decisión real</h2>
              <p className="mt-1 text-sm text-[var(--muted)]">Tus datos ya están listos. Estas son las tres rutas más útiles para comenzar.</p>
            </div>
            <Link to="/dashboard" className="text-xs text-[var(--muted)] hover:text-[var(--text)]">Ocultar</Link>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <WelcomeAction to="/news" title="Revisar cambios" detail="Comprueba pops y variaciones desde el snapshot anterior." />
            <WelcomeAction to="/rivals" title="Estudiar al rival" detail="Once probable, duelos por zona y rotación del ataque." />
            <WelcomeAction to="/training" title="Revisar entrenamiento" detail="Valida la carga y las próximas subidas." />
          </div>
        </section>
      )}

      <AlertsBand insights={insights.data ?? []} loading={insights.isLoading} />

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
          <Panel
            title="Mejor once"
            meta={lineup.data ? `${lineup.data.formation} · índice ${lineup.data.totalRating}` : ""}
          >
            <div className="flex flex-wrap items-center gap-3 border-b border-[var(--border)] px-4 py-3">
              <label className="flex items-center gap-2 text-xs text-[var(--muted)]">
                Formación
                <select
                  value={formacion}
                  onChange={(e) => {
                    setFormacion(e.target.value);
                    setCentrales(undefined);
                    setInteriores(undefined);
                  }}
                  className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-sm text-[var(--text)]"
                >
                  <option value="">Mejor formación</option>
                  {FORMATIONS.map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </select>
              </label>
              {/* Con "Mejor formación" no se ofrecen: ahí se comparan las diez
                  con su reparto propio, y mezclar uno elegido a mano daría un
                  ranking que no compara lo mismo. */}
              {formacion && lineup.data && (
                <>
                  <SplitSelector
                    label="Defensa central"
                    value={lineup.data.centralDefenders}
                    options={lineup.data.centralDefenderOptions}
                    onChange={setCentrales}
                  />
                  <SplitSelector
                    label="Medio central"
                    value={lineup.data.innerMidfielders}
                    options={lineup.data.innerMidfielderOptions}
                    onChange={setInteriores}
                  />
                </>
              )}
            </div>
            {lineup.data ? (
              <BestElevenPitch lineup={lineup.data.lineup} formation={lineup.data.formation} />
            ) : (
              <Empty>Sincroniza para calcular la alineación.</Empty>
            )}
          </Panel>
        </div>

        {data.training && <TrainingPanel training={data.training} />}
      </div>

    </div>
  );
}

/**
 * El mejor once, puesto sobre la cancha.
 *
 * Antes eran once barras horizontales ordenadas por índice: para saber quién
 * juega de lateral derecho había que leer once etiquetas. Un once se lee de un
 * vistazo cuando está en su sitio, y el índice de cada uno cabe dentro de su
 * tarjeta. La misma cancha que usan Equipo, Alineación y la Comparativa de
 * liga, para que la figura signifique siempre lo mismo.
 */
function BestElevenPitch({
  lineup,
  formation,
}: {
  lineup: NonNullable<ReturnType<typeof useLineup>["data"]>["lineup"];
  formation: string;
}) {
  const lineas = [
    lineup.filter((a) => a.position.startsWith("forward")),
    lineup.filter(
      (a) => a.position.startsWith("inner_midfield") || a.position.startsWith("winger"),
    ),
    lineup.filter(
      (a) => a.position.startsWith("central_defender") || a.position.startsWith("wingback"),
    ),
    lineup.filter((a) => a.position === "keeper"),
  ];
  return (
    <PitchField ariaLabel={`Mejor once en formación ${formation}`}>
      <PitchGrid
        rows={lineas}
        // Gente de banda: extremos arriba y laterales atrás. Son los que
        // ocupan las dos columnas de los bordes.
        isFlank={(a) =>
          a.position.startsWith("winger") || a.position.startsWith("wingback")
        }
        render={(a) => (
          <div key={a.slot} className={PITCH_CARD_CLASS}>
            <div className="truncate text-[9px] uppercase tracking-wide text-white/70">
              {a.label}
            </div>
            <div className="truncate text-[11px] font-semibold text-white">{a.player}</div>
            <div className="tabular-nums text-sm font-semibold text-amber-300">
              {a.rating.toFixed(2)}
            </div>
          </div>
        )}
      />
    </PitchField>
  );
}

/**
 * Entrenamiento en una lectura: qué se entrena, cuánto del máximo posible se
 * está aprovechando y a qué edades les está llegando.
 *
 * El porcentaje responde a "¿podría entrenar más?" sin obligar a comparar tres
 * números sueltos (entrenador, asistentes, intensidad). 100% es el techo del
 * juego: entrenador 5/5, dos asistentes de nivel 5 y toda la intensidad en la
 * habilidad. La barra pinta ese porcentaje y debajo va lo que lo compone, para
 * que se vea DÓNDE se pierde.
 */
function TrainingPanel({ training }: { training: NonNullable<Dashboard["training"]> }) {
  const pct = Math.max(0, Math.min(100, training.efficiencyPct));
  const tono =
    pct >= 85 ? "var(--positive)" : pct >= 60 ? "var(--warning)" : "var(--danger)";
  return (
    <Panel title="Entrenamiento" meta={training.typeName}>
      <div className="space-y-3 p-4">
        <div>
          <div className="flex items-baseline justify-between">
            <span className="text-xs text-[var(--muted)]">Del máximo posible</span>
            <span className="tabular-nums text-2xl font-semibold" style={{ color: tono }}>
              {decimal(pct, 1)}%
            </span>
          </div>
          <div className="mt-1 h-2 overflow-hidden rounded bg-[var(--surface-2)]">
            <div className="h-full rounded" style={{ width: `${pct}%`, background: tono }} />
          </div>
        </div>

        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <dt className="text-[var(--muted)]">Entrenador</dt>
            {/* El motor trabaja en la escala 4-8 de la fórmula pública; en la
                pantalla se muestra la de Hattrick, 1-5. */}
            <dd>{training.trainerName} <span className="text-xs text-[var(--muted)]">({Math.max(1, training.coachLevel - 3)}/5)</span></dd>
          </div>
          <div>
            <dt className="text-[var(--muted)]">Asistentes</dt>
            <dd>{training.assistantLevelSum} <span className="text-xs text-[var(--muted)]">de 10</span></dd>
          </div>
          <div>
            <dt className="text-[var(--muted)]">Intensidad</dt>
            <dd>{training.level}% <span className="text-xs text-[var(--muted)]">· {training.staminaPart}% a resistencia</span></dd>
          </div>
          <div>
            <dt className="text-[var(--muted)]">Edad de los entrenados</dt>
            <dd>
              {training.trainedAvgAge != null
                ? <>{decimal(training.trainedAvgAge, 1)} años <span className="text-xs text-[var(--muted)]">· {training.trainedPlayers} jugadores</span></>
                : <span className="text-[var(--muted)]">sin partidos esta semana</span>}
            </dd>
          </div>
        </dl>
      </div>
    </Panel>
  );
}

/**
 * Alertas, arriba del todo — 2026-08-15, pedido explícito: "las alertas están
 * como muy sueltas, no se les ve importantes, posiblemente tengan sentido en
 * el Dashboard".
 *
 * Estaban en un panel lateral, después del radar y las gráficas, con las 5
 * primeras en gris y sin severidad ni acción. Ahora son lo primero que se lee
 * y sólo se muestran las que de verdad piden algo (peligro y aviso): las
 * oportunidades e info viven en el centro de alertas, un clic más allá, para
 * que este bloque no pierda fuerza por saturación.
 */
function AlertsBand({ insights, loading }: { insights: Insight[]; loading: boolean }) {
  // 2026-08-16, pedido explícito: cada alerta se quita con una X y queda
  // guardada en el buzón, que vive en el centro de alertas.
  const archive = useArchiveInsight();
  if (loading) {
    return (
      <Panel title="Qué requiere tu atención">
        <div className="p-4"><Loading /></div>
      </Panel>
    );
  }
  if (insights.length === 0) {
    return (
      <Panel title="Qué requiere tu atención">
        <Empty>Nada requiere tu atención ahora mismo.</Empty>
      </Panel>
    );
  }

  const urgent = insights.filter(
    (i) => i.severity === "danger" || i.severity === "warning",
  );
  // Sin nada urgente, la mejor primera lectura son las oportunidades: es la
  // diferencia entre "no hay incendios" y "no hay nada que hacer".
  const shown = (urgent.length > 0 ? urgent : insights).slice(0, 6);
  const rest = insights.length - shown.length;

  return (
    <Panel
      title="Qué requiere tu atención"
      meta={`${insights.length} activa${insights.length === 1 ? "" : "s"}`}
    >
      <div className="border-b border-[var(--border)] px-4 py-3">
        <SeverityTally insights={insights} />
      </div>
      <ul>
        {shown.map((i) => (
          <InsightRow
            key={i.key}
            insight={i}
            onArchive={archive.mutate}
            busy={archive.isPending}
          />
        ))}
      </ul>
      <div className="px-4 py-3 text-xs">
        <Link to="/insights" className="text-[var(--accent)] hover:underline">
          {rest > 0 ? `Ver las ${rest} restantes en el centro de alertas →` : "Abrir el centro de alertas →"}
        </Link>
      </div>
    </Panel>
  );
}

function WelcomeAction({ to, title, detail }: { to: string; title: string; detail: string }) {
  return (
    <Link to={to} className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 hover:border-[var(--accent)]/50">
      <div className="text-sm font-semibold">{title} →</div>
      <p className="mt-1 text-xs leading-5 text-[var(--muted)]">{detail}</p>
    </Link>
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
  // Apagada a proposito: el eje de TSI sale de sumar las plantillas de los
  // siete rivales, y eso son siete llamadas a Hattrick que nadie ha pedido al
  // entrar al panel. Con la consulta apagada, esto devuelve lo que ya haya en
  // cache — misma clave que usa Liga, asi que si el usuario paso por alli, el
  // cuarto eje aparece gratis. Y si no paso, el radar se dibuja igual con los
  // tres ejes que la clasificacion ya sabe: antes se quedaba en un aviso
  // pidiendole al usuario que sincronizara algo que ya estaba sincronizado.
  const comparison = useLeagueComparison(true, true, false);

  if (league.isLoading) {
    return (
      <Panel title="Radar de fuerza">
        <div className="p-4"><Loading /></div>
      </Panel>
    );
  }

  const own = league.data?.ownOutlook;
  // Cuantos equipos hay en la serie lo dice la propia clasificacion.
  const n = comparison.data?.teamsInSeries ?? league.data?.standings.length ?? 0;
  const rank = comparison.data?.ownRank ?? 0;
  if (!own || !league.data || n < 2) {
    return (
      <Panel title="Radar de fuerza">
        <Empty>Todavía no hay clasificación de tu serie.</Empty>
      </Panel>
    );
  }
  const hayTsi = comparison.data != null && rank > 0;

  const clamp = (v: number) => Math.max(0, Math.min(100, v));
  const attackAxis = clamp(own.attackStrength * 50);
  const defenceAxis = clamp((2 - own.defenceStrength) * 50);
  const tsiAxis = clamp((1 - (rank - 1) / (n - 1)) * 100);
  const positionAxis = clamp((1 - (own.expectedPosition - 1) / (n - 1)) * 100);

  const indicators = [
    { name: "Ataque", max: 100 },
    { name: "Posición esperada", max: 100 },
    { name: "Defensa", max: 100 },
    ...(hayTsi ? [{ name: "TSI en la liga", max: 100 }] : []),
  ];
  const ejes = hayTsi
    ? [attackAxis, positionAxis, defenceAxis, tsiAxis]
    : [attackAxis, positionAxis, defenceAxis];

  return (
    <Panel title="Radar de fuerza" meta={`relativo a ${league.data.seriesName ?? "tu liga"}`}>
      <Chart
        ariaLabel="Radar de fuerza del equipo, relativo a la media de la liga"
        height={300}
        option={radarOption(indicators, [{ name: teamName, value: ejes }])}
      />
      <Note>
        50 es la media de {league.data.seriesName}, 100 el mejor de la serie en ese eje.
      </Note>
    </Panel>
  );
}
