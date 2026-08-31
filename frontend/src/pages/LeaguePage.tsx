import { useState } from "react";
import type { TooltipComponentFormatterCallbackParams } from "echarts";
import { Link } from "react-router-dom";
import { Chart } from "../charts/Chart";
import { Column, DataTable } from "../components/DataTable";
import {
  ErrorState,
  Kpi,
  Loading,
  Note,
  Panel,
  ProjectionPanel,
  SinDatos,
} from "../components/Panels";
import { PITCH_CARD_CLASS, PitchField, PitchGrid } from "../components/PitchField";
import { SplitSelector } from "../components/SplitSelector";
import { Tabs } from "../components/Tabs";
import { TsiHistogramPanel } from "../components/TsiHistogramPanel";
import { number } from "../hooks/useFormat";
import { useIsDarkTheme } from "../hooks/useTheme";
import {
  useLeague,
  useLeagueComparison,
  useLeagueTeamOfWeek,
} from "../hooks/useTeam";
import { FORMATIONS } from "../services/api";
import type {
  Formation,
  League,
  LeagueStandingRow,
  LeagueTeamSummary,
  OutlookRow,
  TeamOfWeekRoleKey,
} from "../services/api";

/**
 * Liga y predicciones. HL-080, HL-083, HL-090, HL-091, HL-094.
 *
 * La respuesta a «¿en qué puesto acabo?» es una distribución, no un número.
 * Dieciséis jornadas son pocas para que el mejor equipo gane siempre, y una
 * herramienta que devuelva «4º» está escondiendo justo la parte informativa.
 */
/** Puntos sobre el líder (si vas primero) o bajo el líder (si no) — de
 * `standings`, nunca de la simulación: es un hecho de hoy, no una
 * proyección. */
function leaderGap(data: League): { label: string; value: string } {
  const leader = data.standings.find((s) => s.position === 1);
  const own = data.standings.find((s) => s.isOwnTeam);
  if (!leader || !own) return { label: "Brecha", value: "-" };
  if (own.position === 1) {
    const second = data.standings.find((s) => s.position === 2);
    if (!second) return { label: "Ventaja sobre el 2º", value: "-" };
    return {
      label: "Ventaja sobre el 2º",
      value: `+${own.points - second.points} pts`,
    };
  }
  return {
    label: "Brecha frente al líder",
    value: `-${leader.points - own.points} pts`,
  };
}

type LeagueSection = "resumen" | "proyeccion" | "comparativa";

export function LeaguePage() {
  const { data, isLoading, isError, error } = useLeague();
  const [section, setSection] = useState<LeagueSection>("resumen");

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return <SinDatos />;

  const own = data.ownOutlook;
  // Mismo umbral que `SHRINKAGE_K` en el motor: por debajo de eso, el prior
  // de "equipo medio" pesa más que la evidencia propia de este equipo.
  const lowConfidence = data.roundsPlayed < data.model.shrinkageK;
  const gap = leaderGap(data);

  return (
    <div className="space-y-4">
      <header className="space-y-3">
        <div>
          <h1 className="text-xl font-semibold">Liga</h1>
          <p className="text-sm text-[var(--muted)]">
            {data.seriesName} · temporada {data.season} · jornada{" "}
            {data.roundsPlayed}
          </p>
        </div>
        <Tabs
          tabs={[
            { key: "resumen", label: "Resumen" },
            { key: "proyeccion", label: "Proyección" },
            { key: "comparativa", label: "Comparativa" },
          ]}
          active={section}
          onChange={setSection}
        />
      </header>

      {section === "resumen" && (
        <div className="space-y-4">
          {/* Resumen oficial, solo hechos: lo que Hattrick ya reportó,
              nada proyectado. */}
          {own && (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 [&>*]:min-w-0">
              <Kpi
                label="Posición actual"
                value={`${own.currentPosition}º`}
                hint={`${own.currentPoints} puntos · jornada ${data.roundsPlayed}`}
              />
              <Kpi label="Puntos actuales" value={String(own.currentPoints)} />
              <Kpi
                label={gap.label}
                value={gap.value}
                hint="frente a hoy, de la clasificación"
              />
            </div>
          )}

          <Panel title="Clasificación" meta={`jornada ${data.roundsPlayed}`}>
            <StandingsTable data={data} />
          </Panel>

          {data.nextMatch && <NextMatch data={data} />}

          <HistoryPanel data={data} />

          <FixturesCalendar data={data} />
        </div>
      )}

      {section === "proyeccion" && own && (
        <div className="space-y-4">
          {lowConfidence && (
            <div
              role="alert"
              className="rounded-lg border border-[var(--warning)]/30 bg-[var(--warning)]/10 px-4 py-3 text-sm text-[var(--warning)]"
            >
              Confianza todavía baja: {data.roundsPlayed} jornada(s) jugada(s);
              el prior pesa más que los resultados observados.
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 [&>*]:min-w-0">
            <Kpi
              label="Posición esperada"
              value={own.expectedPosition.toFixed(1)}
              hint={`más probable: ${own.mostLikelyPosition}º`}
            />
            <Kpi
              label="Probabilidad de terminar 1º"
              value={`${(own.titleProbability * 100).toFixed(0)}%`}
              hint={
                data.isTopDivision
                  ? "ya estás en primera división"
                  : "ascenso directo o promoción según el ranking nacional, no modelado"
              }
              tone={own.titleProbability > 0.5 ? "positive" : undefined}
            />
            <Kpi
              label="Probabilidad de Top 4"
              value={`${((own.titleProbability + own.secondToFourthProbability) * 100).toFixed(0)}%`}
              hint="1º-4º combinados"
            />
            <Kpi
              label="Puntos finales esperados"
              value={own.expectedPoints.toFixed(1)}
              hint={`hoy: ${own.currentPoints}`}
            />
          </div>
          <p className="text-xs text-[var(--muted)]">
            Riesgo de promoción de permanencia y descenso directo: ver la tabla
            "Pronóstico por equipo" más abajo, columnas 5º-6º y 7º-8º.
          </p>

          <ProjectionPanel
            title="Distribución de la posición final"
            meta={`${number(data.simulationRuns)} simulaciones`}
          >
            <Chart
              ariaLabel="Distribución de probabilidad de la posición final"
              option={{
                xAxis: {
                  type: "category",
                  data: Object.keys(own.positionDistribution),
                  name: "puesto",
                },
                yAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
                tooltip: {
                  trigger: "item",
                  formatter: (p: TooltipComponentFormatterCallbackParams) => {
                    const item = Array.isArray(p) ? p[0] : p;
                    if (!item) return "";
                    return `${item.name}º puesto: ${Number(item.value).toFixed(1)}%`;
                  },
                },
                series: [
                  {
                    type: "bar",
                    data: Object.values(own.positionDistribution).map(
                      (v) => v * 100,
                    ),
                    itemStyle: { borderRadius: 3 },
                  },
                ],
              }}
              height={240}
            />
            <p className="border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
              Cada barra es la fracción de temporadas simuladas en las que
              acabas en ese puesto. Si la distribución es ancha, la liga aún no
              está decidida, y eso es lo que un único número escondería.
            </p>
          </ProjectionPanel>

          <BestWorstPanel data={data} />

          <ProjectionPanel
            title="Pronóstico por equipo"
            meta="ordenado por posición actual"
          >
            <OutlookTable data={data} />
          </ProjectionPanel>

          <ProjectionPanel
            title="Qué modela la simulación"
            meta={data.model.model}
          >
            <div className="space-y-2 p-4 text-xs leading-relaxed text-[var(--muted)]">
              <p>
                Los goles salen de dos Poisson independientes con las fuerzas de
                ataque y defensa de cada equipo, encogidas hacia la media de la
                liga con un peso de {data.model.shrinkageK}. Con pocas jornadas
                el prior de «equipo medio» pesa más que la evidencia propia;
                según avanza la temporada, la evidencia gana. La ventaja de
                campo es ×{data.model.homeAdvantage}. Media de goles de esta
                liga: {data.leagueAvgGoals}.
              </p>
              <p>
                <b className="text-[var(--text)]">No modela:</b>{" "}
                {data.model.doesNotModel.join(", ")}. Sirve para las opciones de
                la temporada, no para acertar un partido concreto.
              </p>
              {data.caveats.map((c, i) => (
                <p key={i}>{c}</p>
              ))}
            </div>
          </ProjectionPanel>
        </div>
      )}

      {section === "comparativa" && <LeagueTsiComparison />}
    </div>
  );
}

function NextMatch({ data }: { data: League }) {
  const nm = data.nextMatch!;

  // Los tres desenlaces vistos DESDE TU LADO, que es la única lectura que le
  // sirve al usuario. Antes la barra iba coloreada por local/visitante: azul
  // el de casa, rojo el de fuera. Jugando de visitante, el azul era el rival
  // y el rojo eras tú, así que el color decía lo contrario de lo que parecía.
  const barras = [
    {
      label: nm.isHome ? nm.home : nm.away,
      value: nm.isHome ? nm.homeWin : nm.awayWin,
      color: "var(--positive)",
      tuyo: true,
    },
    { label: "Empate", value: nm.draw, color: "var(--muted)", tuyo: false },
    {
      label: nm.isHome ? nm.away : nm.home,
      value: nm.isHome ? nm.awayWin : nm.homeWin,
      color: "var(--danger)",
      tuyo: false,
    },
  ];

  return (
    <Panel title="Próximo partido" meta="tendencia histórica de liga">
      <div className="space-y-3 p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
          <span>
            <span className={nm.isHome ? "font-medium" : ""}>{nm.home}</span>
            <span className="mx-2 text-[var(--muted)]">vs</span>
            <span className={!nm.isHome ? "font-medium" : ""}>{nm.away}</span>
          </span>
          <span className="text-xs text-[var(--muted)]">
            goles esperados {nm.expectedHomeGoals} – {nm.expectedAwayGoals} ·
            resultado más probable {nm.mostLikelyScore}
          </span>
        </div>

        <div className="flex h-6 overflow-hidden rounded">
          {barras.map((b) => (
            <div
              key={b.label}
              className="flex items-center justify-center text-[10px] font-medium text-white"
              style={{ width: `${b.value * 100}%`, background: b.color }}
              title={`${b.label}: ${(b.value * 100).toFixed(1)}%`}
            >
              {b.value > 0.12 ? `${(b.value * 100).toFixed(0)}%` : ""}
            </div>
          ))}
        </div>

        {/* La leyenda no es adorno: sin ella los tres porcentajes se asocian a
            su equipo sólo por posición, y «Empate» no aparecía en ninguna
            parte salvo dentro del tooltip. */}
        <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs">
          {barras.map((b) => (
            <span key={b.label} className="inline-flex items-baseline gap-1.5">
              <i
                className="inline-block h-2 w-2 shrink-0 translate-y-[-1px] rounded-full"
                style={{ background: b.color }}
              />
              <span className={b.tuyo ? "font-medium" : "text-[var(--muted)]"}>
                {b.label}
                {b.tuyo && <span className="text-[var(--muted)]"> (tú)</span>}
              </span>
              <b className="tabular-nums">{(b.value * 100).toFixed(0)}%</b>
            </span>
          ))}
        </div>
      </div>
      <p className="flex items-center justify-between gap-3 border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
        <span>
          {nm.verdict}, estimado solo con goles agregados de liga; no conoce
          alineación, tácticas ni bajas.
        </span>
        <Link
          to="/rivals"
          className="shrink-0 whitespace-nowrap text-[var(--accent)] hover:underline"
        >
          Estudiar al rival →
        </Link>
      </p>
    </Panel>
  );
}

const STANDINGS_MODES: ["all", "home", "away"] = ["all", "home", "away"];
const STANDINGS_MODE_LABELS: Record<(typeof STANDINGS_MODES)[number], string> =
  {
    all: "Total",
    home: "Local",
    away: "Visitante",
  };

function StandingsTable({ data }: { data: League }) {
  type Row = LeagueStandingRow;
  // 2026-08-08, pedido explícitamente: leaguedetails.xml solo da la tabla
  // combinada — Local/Visitante se calculan aparte en el backend desde los
  // resultados reales (ver `standingsHome`/`standingsAway`).
  const [mode, setMode] = useState<(typeof STANDINGS_MODES)[number]>("all");
  const rows =
    mode === "home"
      ? data.standingsHome
      : mode === "away"
        ? data.standingsAway
        : data.standings;
  const columns: Column<Row>[] = [
    { key: "position", header: "#", align: "right", value: (r) => r.position },
    {
      key: "name",
      header: "Equipo",
      align: "left",
      value: (r) => r.name,
      render: (r) =>
        r.isOwnTeam ? (
          <span className="font-medium text-[var(--text)]">{r.name}</span>
        ) : (
          <Link
            to={`/rivals/${r.htTeamId}`}
            className="hover:text-[var(--accent)] hover:underline"
          >
            {r.name}
          </Link>
        ),
    },
    { key: "played", header: "PJ", align: "right", value: (r) => r.played },
    { key: "won", header: "G", align: "right", value: (r) => r.won },
    { key: "drawn", header: "E", align: "right", value: (r) => r.drawn },
    { key: "lost", header: "P", align: "right", value: (r) => r.lost },
    {
      key: "gf",
      header: "GF",
      align: "right",
      value: (r) => r.goalsFor,
      optional: true,
    },
    {
      key: "ga",
      header: "GC",
      align: "right",
      value: (r) => r.goalsAgainst,
      optional: true,
    },
    {
      key: "gd",
      header: "DG",
      align: "right",
      value: (r) => r.goalDifference,
      render: (r) => (
        <span className="tabular-nums">
          {r.goalDifference > 0 ? "+" : ""}
          {r.goalDifference}
        </span>
      ),
    },
    { key: "points", header: "Pts", align: "right", value: (r) => r.points },
  ];
  return (
    <div className="space-y-3">
      <div className="flex overflow-hidden rounded border border-[var(--border)] text-xs w-fit">
        {STANDINGS_MODES.map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`px-3 py-1 ${mode === m ? "bg-[var(--accent)] text-white" : "bg-[var(--surface)]"}`}
          >
            {STANDINGS_MODE_LABELS[m]}
          </button>
        ))}
      </div>
      <DataTable
        emptyMessage="Sin clasificación: se llena cuando se sincronice la liga."
        rows={rows}
        columns={columns}
        rowKey={(r) => r.htTeamId}
        initialSort="position"
        initialDescending={false}
        csvName={`clasificacion-${mode}`}
        filterPlaceholder="Filtrar equipos…"
      />
    </div>
  );
}

const HISTORY_COLORS = [
  "#4f7cff",
  "#2fbf71",
  "#f5a524",
  "#e5484d",
  "#8b5cf6",
  "#06b6d4",
  "#ec4899",
  "#84cc16",
];

/**
 * Historial real de posición/puntos por jornada sincronizada — una línea
 * por equipo, como el historial de serie de Hattrick. Cada sync guarda una
 * foto de TODA la serie, así que con varias jornadas sincronizadas esto es
 * una serie temporal real, no una jornada — los huecos (jornadas sin
 * sincronizar) se ven como cortes en la línea, nunca se interpolan.
 */
function HistoryPanel({ data }: { data: League }) {
  const [metric, setMetric] = useState<"position" | "points">("position");
  const h = data.history;

  if (h.rounds.length === 0) {
    return null;
  }

  const nTeams = h.teams.length;
  // "0" es la jornada simbólica antes de jugar nada (0 puntos para todos,
  // un hecho, no un dato sincronizado) — no cuenta como jornada real.
  const realRounds = h.rounds.filter((r) => r !== 0).length;
  return (
    <Panel
      title="Historial de la serie"
      meta={`${realRounds} jornada(s) sincronizada(s)`}
    >
      <div className="flex gap-3 border-b border-[var(--border)] px-4 py-3">
        <div className="flex overflow-hidden rounded border border-[var(--border)] text-xs">
          <button
            className={`px-3 py-1 ${metric === "position" ? "bg-[var(--accent)] text-white" : "bg-[var(--surface)]"}`}
            onClick={() => setMetric("position")}
          >
            Puesto
          </button>
          <button
            className={`px-3 py-1 ${metric === "points" ? "bg-[var(--accent)] text-white" : "bg-[var(--surface)]"}`}
            onClick={() => setMetric("points")}
          >
            Puntos
          </button>
        </div>
      </div>
      <Chart
        ariaLabel={`Historial de ${metric === "position" ? "posición" : "puntos"} por jornada`}
        option={{
          xAxis: {
            type: "category",
            data: h.rounds.map(String),
            name: "jornada",
          },
          yAxis:
            metric === "position"
              ? {
                  type: "value",
                  inverse: true,
                  min: 1,
                  max: nTeams,
                  interval: 1,
                  name: "puesto",
                }
              : { type: "value", name: "puntos" },
          legend: {
            data: h.teams.map((t) => t.name),
            bottom: 0,
            type: "scroll",
          },
          grid: {
            left: 48,
            right: 16,
            top: 28,
            bottom: 64,
            containLabel: true,
          },
          tooltip: {
            trigger: "axis",
            formatter: (p: TooltipComponentFormatterCallbackParams) => {
              const items = Array.isArray(p) ? p : [p];
              return items
                .filter((it) => it.value !== null && it.value !== undefined)
                .map((it) => `${it.seriesName}: ${it.value}`)
                .join("<br/>");
            },
          },
          series: h.teams.map((t, i) => ({
            name: t.name,
            type: "line",
            data: metric === "position" ? t.positions : t.points,
            connectNulls: false,
            symbolSize: 6,
            lineStyle: {
              width: t.isOwnTeam ? 3 : 1.5,
              color: HISTORY_COLORS[i % HISTORY_COLORS.length],
            },
            itemStyle: { color: HISTORY_COLORS[i % HISTORY_COLORS.length] },
            z: t.isOwnTeam ? 2 : 1,
          })),
        }}
        height={320}
      />
      <p className="border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
        Cada punto es una jornada realmente jugada, sin datos de por medio, la
        línea se corta en vez de interpolar. La jornada "0" es simbólica: 0
        puntos para todos antes de jugar nada, no un dato sincronizado, por eso
        el puesto ahí no se dibuja. Posición y puntos por jornada se calculan a
        partir de los resultados reales de cada partido de la serie
        no de una foto puntual de la clasificación, así
        que no dependen de cuándo hayas sincronizado. Con solo {realRounds}{" "}
        jornada(s) jugada(s) el historial todavía dice poco; se vuelve más útil
        según avanza la temporada.
      </p>
    </Panel>
  );
}

/**
 * Calendario completo de la serie — pedido explícitamente 2026-08-08. El
 * backend ya trae `fixtures` (leaguefixtures.xml, calendario COMPLETO de
 * la serie) desde HL-090; solo faltaba pintarlo. Verde = ganó, ámbar =
 * empate, texto normal = perdió — el propio equipo siempre en negrita y
 * subrayado, sea cual sea el resultado.
 */
function FixturesCalendar({ data }: { data: League }) {
  const byRound = new Map<number, League["fixtures"]>();
  for (const f of data.fixtures) {
    const list = byRound.get(f.matchRound) ?? [];
    list.push(f);
    byRound.set(f.matchRound, list);
  }
  const rounds = [...byRound.keys()].sort((a, b) => a - b);

  function sideClass(
    f: League["fixtures"][number],
    side: "home" | "away",
  ): string {
    const own =
      side === "home" ? f.home === data.teamName : f.away === data.teamName;
    let tone = "";
    const parts = f.score?.split("-").map(Number);
    if (f.played && parts && parts.length === 2) {
      const [hg, ag] = parts as [number, number];
      const won = side === "home" ? hg > ag : ag > hg;
      const drew = hg === ag;
      tone = won
        ? "text-[var(--positive)]"
        : drew
          ? "text-[var(--warning)]"
          : "";
    }
    return [own ? "font-semibold underline" : "", tone]
      .filter(Boolean)
      .join(" ");
  }

  return (
    <Panel title="Calendario completo" meta={`${rounds.length} jornada(s)`}>
      <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {rounds.map((rnd) => {
          const matches = byRound.get(rnd)!;
          return (
            <div
              key={rnd}
              className="rounded-lg border border-[var(--border)] p-3 text-xs"
            >
              <div className="mb-2 border-b border-[var(--border)] pb-1.5 font-medium text-[var(--muted)]">
                Jornada {rnd} · {matches[0]?.date ?? ""}
              </div>
              {/* Rejilla, no `flex justify-between`: así el marcador tiene
                  columna propia y cae siempre en la misma vertical. Con flex,
                  los tres trozos se dimensionaban según su texto, de modo que
                  un local largo ("San Andrés y Providencia Real") empujaba el
                  resultado a la derecha y otro corto ("etbenianos1") lo dejaba
                  a la izquierda, los marcadores salían torcidos de fila en
                  fila. Las dos pistas laterales son `1fr` iguales, así que la
                  del centro queda centrada; y es de ancho FIJO para que un
                  10-0 no la desplace respecto a un 1-2. `minmax(0,1fr)` es lo
                  que deja que `truncate` recorte dentro de una rejilla. */}
              <div className="space-y-1.5">
                {matches.map((f, i) => (
                  <div
                    key={i}
                    className="grid grid-cols-[minmax(0,1fr)_2.75rem_minmax(0,1fr)] items-center gap-2"
                  >
                    <span className={`truncate ${sideClass(f, "home")}`}>
                      {f.home}
                    </span>
                    <span className="text-center tabular-nums text-[var(--muted)]">
                      {f.played ? f.score : "–"}
                    </span>
                    <span
                      className={`truncate text-right ${sideClass(f, "away")}`}
                    >
                      {f.away}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

/**
 * 2026-08-05, pedido explícitamente: "Mejor caso y peor caso" sonaba a un
 * resultado plausible ("el título suena plausible"), cuando en realidad son
 * extremos DELIBERADAMENTE imposibles (goleada de ~14-0 en cada partido que
 * queda, o al revés) — solo sirven para acotar matemáticamente el rango de
 * puestos posible, nunca como pronóstico. Mismo estilo que "Distribución de
 * la posición final": el resultado sigue siendo una distribución, no un
 * número — forzar tu propio resultado a un extremo no fija el de los
 * demás, que siguen jugando con su nivel real.
 */
function BestWorstPanel({ data }: { data: League }) {
  const isDark = useIsDarkTheme();
  const bw = data.bestWorst;
  if (!bw) {
    return (
      <ProjectionPanel title="Límites matemáticos de posición">
        <Note>
          No hay calendario pendiente sincronizado: no queda nada que forzar a
          un extremo.
        </Note>
      </ProjectionPanel>
    );
  }
  const positions = Object.keys(bw.bestCasePositionDistribution);
  const positive = isDark ? "#2fbf71" : "#1a9e5c";
  const danger = isDark ? "#e5484d" : "#d1383d";

  return (
    <ProjectionPanel
      title="Límites matemáticos de posición"
      meta={`${bw.remainingMatches} partidos pendientes · ${number(data.simulationRuns)} simulaciones`}
    >
      <p className="border-b border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
        Escenarios extremos deliberadamente imposibles (goleada en cada partido
        restante, en un sentido o en el otro); no son pronósticos.
      </p>
      <Chart
        ariaLabel="Distribución de la posición final en el mejor y en el peor caso"
        option={{
          xAxis: { type: "category", data: positions, name: "puesto" },
          yAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
          legend: { data: ["Mejor caso", "Peor caso"], top: 0 },
          tooltip: {
            trigger: "axis",
            formatter: (p: TooltipComponentFormatterCallbackParams) => {
              const items = Array.isArray(p) ? p : [p];
              return items
                .map(
                  (it) =>
                    `${it.seriesName} · ${it.name}º: ${Number(it.value).toFixed(1)}%`,
                )
                .join("<br/>");
            },
          },
          series: [
            {
              name: "Mejor caso",
              type: "bar",
              data: Object.values(bw.bestCasePositionDistribution).map(
                (v) => v * 100,
              ),
              itemStyle: { borderRadius: 3, color: positive },
            },
            {
              name: "Peor caso",
              type: "bar",
              data: Object.values(bw.worstCasePositionDistribution).map(
                (v) => v * 100,
              ),
              itemStyle: { borderRadius: 3, color: danger },
            },
          ],
        }}
        height={240}
      />
      <p className="border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
        Mejor caso: en cada partido que te queda marcas de goleada y no encajas.
        Peor caso: al revés. El resto de la liga sigue con su nivel real, así
        que aun forzando tu propio resultado al extremo, tu puesto final sigue
        siendo una distribución.
      </p>
    </ProjectionPanel>
  );
}

/**
 * 5º-6º y 7º-8º NO se leen de `relegationPlayoffProbability`/
 * `relegationProbability`: esos campos se ponen a 0 cuando no hay playoff de
 * permanencia o descenso posible (división más baja/más alta del país), lo
 * cual tiene sentido para el KPI de "riesgo" de arriba, pero rompe la
 * partición exhaustiva de esta tabla — el equipo igual termina en algún
 * puesto, solo que sin consecuencia deportiva. Se calculan directo de
 * `positionDistribution`, que nunca se pone a 0 artificialmente, así que
 * Título + 2º-4º + 5º-6º + 7º-8º siempre suma 100%.
 */
function groupProbability(
  dist: Record<string, number>,
  positions: number[],
): number {
  return positions.reduce((sum, p) => sum + (dist[String(p)] ?? 0), 0);
}

function OutlookTable({ data }: { data: League }) {
  const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
  const columns: Column<OutlookRow>[] = [
    {
      key: "now",
      header: "Ahora",
      align: "right",
      value: (r) => r.currentPosition,
    },
    {
      key: "name",
      header: "Equipo",
      align: "left",
      value: (r) => r.name,
      render: (r) =>
        r.isOwnTeam ? (
          <span className="font-medium text-[var(--text)]">{r.name}</span>
        ) : (
          <Link
            to={`/rivals/${r.htTeamId}`}
            className="hover:text-[var(--accent)] hover:underline"
          >
            {r.name}
          </Link>
        ),
    },
    {
      key: "expected",
      header: "Puesto esperado",
      align: "right",
      value: (r) => r.expectedPosition,
      render: (r) => (
        <span className="tabular-nums">{r.expectedPosition.toFixed(1)}</span>
      ),
    },
    {
      key: "points",
      header: "Puntos esperados",
      align: "right",
      value: (r) => r.expectedPoints,
      render: (r) => (
        <span className="tabular-nums">{r.expectedPoints.toFixed(1)}</span>
      ),
    },
    {
      key: "title",
      header: "Título",
      align: "right",
      value: (r) => r.titleProbability,
      render: (r) => (
        <span className="tabular-nums">{pct(r.titleProbability)}</span>
      ),
    },
    {
      key: "secondToFourth",
      header: "2º-4º",
      align: "right",
      value: (r) => r.secondToFourthProbability,
      render: (r) => (
        <span className="tabular-nums">{pct(r.secondToFourthProbability)}</span>
      ),
    },
    {
      key: "fifthSixth",
      header: "5º-6º",
      align: "right",
      value: (r) => groupProbability(r.positionDistribution, [5, 6]),
      render: (r) => {
        const v = groupProbability(r.positionDistribution, [5, 6]);
        // 2026-08-05, pedido explícitamente: en la última división del país
        // no hay a dónde descender, así que 5º-6º no juega ninguna
        // promoción de permanencia real — el rojo aquí sería una alarma
        // falsa.
        const danger = !data.isBottomDivision && v > 0.25;
        return (
          <span
            className={
              danger ? "tabular-nums text-[var(--danger)]" : "tabular-nums"
            }
          >
            {pct(v)}
          </span>
        );
      },
    },
    {
      key: "seventhEighth",
      header: "7º-8º",
      align: "right",
      value: (r) => {
        const n = Object.keys(r.positionDistribution).length;
        return groupProbability(r.positionDistribution, [n - 1, n]);
      },
      render: (r) => {
        const n = Object.keys(r.positionDistribution).length;
        const v = groupProbability(r.positionDistribution, [n - 1, n]);
        const danger = !data.isBottomDivision && v > 0.25;
        return (
          <span
            className={
              danger ? "tabular-nums text-[var(--danger)]" : "tabular-nums"
            }
          >
            {pct(v)}
          </span>
        );
      },
    },
    {
      key: "attack",
      header: "Ataque",
      align: "right",
      value: (r) => r.attackStrength,
      optional: true,
    },
    {
      key: "defence",
      header: "Defensa",
      align: "right",
      value: (r) => r.defenceStrength,
      optional: true,
    },
  ];
  return (
    <>
      <DataTable
        emptyMessage="Sin proyección: hacen falta jornadas jugadas para estimarla."
        rows={data.outlook}
        columns={columns}
        rowKey={(r) => r.htTeamId}
        initialSort="now"
        initialDescending={false}
        csvName="pronostico"
        filterPlaceholder="Filtrar equipos…"
      />
      <p className="border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
        Título, 2º-4º, 5º-6º y 7º-8º cubren TODOS los puestos sin solaparse y
        siempre suman 100%, "ascenso" no aparece aparte porque la columna
        "Título" ya es la probabilidad de terminar 1º, la condición necesaria
        (no la suficiente: el ascenso directo o la promoción dependen del
        ranking nacional de campeones, no modelado). "5º-6º" es el playoff de
        promoción para NO descender, no un ascenso extra. En el extremo de la
        pirámide donde no hay a dónde ir (primera división para el título,
        última división del país para el 5º-6º y el 7º-8º), terminar en esos
        puestos sigue siendo posible, solo que sin la consecuencia deportiva
        que el nombre de la columna sugiere (por eso esas dos columnas no se
        resaltan en rojo en la última división).
      </p>
      <p className="border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
        Ataque y defensa son relativos a la media de la liga: 1,00 es
        exactamente la media, 1,30 es marcar un 30% más que un equipo medio. En
        defensa, menos es mejor.
      </p>
    </>
  );
}

/**
 * No solo el próximo rival: dónde queda la plantilla frente a TODA la serie.
 * Mismo motor que la ficha de un rival puntual (`tsi_kde_comparison`), aquí
 * agregado a los 7-8 equipos de la liga a la vez.
 *
 * 2026-08-08, pedido explícitamente: vuelve a cargar sola al entrar a
 * /league (revierte el arranque colapsado del 2026-08-05) — pide las
 * plantillas de los 7-8 rivales a CHPP apenas se abre la página, sin
 * esperar a que el usuario la abra a propósito.
 */
function LeagueTsiComparison() {
  // 2026-08-08, pedido explícitamente: default Log(TSI+1) — la escala
  // lineal aplasta casi todos los planteles contra el eje cuando hay 1-2
  // fichajes estrella en la liga, así que la vista log es la que de verdad
  // sirve para comparar de un vistazo. "Los 11 mejores" también por
  // defecto: compara fuerza de juego real, no el tamaño de la plantilla.
  const [logTsi, setLogTsi] = useState(true);
  const [top11, setTop11] = useState(true);
  const { data, isLoading, isError } = useLeagueComparison(
    logTsi,
    top11,
  );

  if (isLoading)
    return (
      <Panel title="Comparativa de liga">
        <Loading />
      </Panel>
    );
  if (isError || !data) {
    return (
      <Panel title="Comparativa de liga">
        <Note>
          No se pudo comparar contra la serie, hace falta una sesión de
          Hattrick activa y la clasificación sincronizada.
        </Note>
      </Panel>
    );
  }

  const columns: Column<LeagueTeamSummary>[] = [
    { key: "rank", header: "#", align: "right", value: (r) => r.rank },
    {
      key: "teamName",
      header: "Equipo",
      align: "left",
      value: (r) => r.teamName,
      render: (r) => (
        <span className={r.isOwn ? "font-medium text-[var(--text)]" : ""}>
          {r.teamName}
        </span>
      ),
    },
    {
      key: "totalTsi",
      header: "TSI total",
      align: "right",
      value: (r) => r.totalTsi,
      render: (r) => <span className="tabular-nums">{number(r.totalTsi)}</span>,
    },
    {
      key: "avgTsi",
      header: "TSI medio",
      align: "right",
      value: (r) => r.avgTsi,
      render: (r) => <span className="tabular-nums">{number(r.avgTsi)}</span>,
    },
    {
      key: "playerCount",
      header: "Jugadores",
      align: "right",
      value: (r) => r.playerCount,
    },
    // 2026-08-08, pedido explícitamente: jugador de mayor TSI, su TSI, su
    // última posición jugada en partido oficial, y forma/resistencia
    // medias de la plantilla comparada.
    {
      key: "topPlayerName",
      header: "Mejor TSI (jugador)",
      align: "left",
      value: (r) => r.topPlayerName ?? "",
      render: (r) =>
        r.topPlayerName ? (
          <span>
            {r.topPlayerName}{" "}
            <span className="tabular-nums text-[var(--muted)]">
              ({number(r.topPlayerTsi ?? 0)})
            </span>
          </span>
        ) : (
          <span className="text-[var(--muted)]">—</span>
        ),
    },
    {
      key: "topPlayerLastPosition",
      header: "Última posición",
      align: "left",
      optional: true,
      value: (r) => r.topPlayerLastPosition ?? "",
      render: (r) =>
        r.topPlayerLastPosition ?? (
          <span className="text-[var(--muted)]">—</span>
        ),
    },
    {
      key: "avgForm",
      header: "Forma",
      align: "right",
      optional: true,
      value: (r) => r.avgForm ?? -1,
      render: (r) =>
        r.avgForm != null ? (
          <span className="tabular-nums">{r.avgForm}</span>
        ) : (
          <span className="text-[var(--muted)]">—</span>
        ),
    },
    {
      key: "avgStamina",
      header: "Resistencia",
      align: "right",
      optional: true,
      value: (r) => r.avgStamina ?? -1,
      render: (r) =>
        r.avgStamina != null ? (
          <span className="tabular-nums">{r.avgStamina}</span>
        ) : (
          <span className="text-[var(--muted)]">—</span>
        ),
    },
  ];

  return (
    <>
      <TsiHistogramPanel
        title="TSI: tu plantilla vs. el resto de la liga"
        meta={`${data.teamsInSeries} equipos · puesto ${data.ownRank} por TSI`}
        rivalLabel="Resto de la liga"
        histogram={data.tsiHistogram}
        logTsi={logTsi}
        onLogTsiChange={setLogTsi}
        top11={top11}
        onTop11Change={setTop11}
        noteSuffix={
          "del resto de la serie (agregados)" +
          (top11
            ? ", tu once real (motor de posiciones) contra los 11 de mayor TSI de cada rival"
            : "") +
          ". El TSI de cada rival es real; sus habilidades exactas están ocultas por Hattrick"
        }
      />
      <Panel title="Comparativa de rivales" meta={data.seriesName}>
        <DataTable
          emptyMessage="Sin comparativa: hacen falta partidos de los rivales."
          rows={data.ranking}
          columns={columns}
          rowKey={(r) => r.teamHtId}
          initialSort="totalTsi"
          csvName="comparativa-rivales"
        />
        <p className="border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
          "Última posición" se consulta aparte, solo para el jugador de mayor TSI
          de cada equipo; forma y resistencia promedian solo jugadores donde
          Hattrick de verdad mostró el dato: un rival
          puede tenerlas ocultas.
        </p>
      </Panel>
      <TeamOfTheWeekPanel />
    </>
  );
}

// Orden de filas (arriba = ataque, abajo = portería), y tamaño de tarjeta
// FIJO — pedido explícitamente 2026-08-08: nunca se achica según cuántos
// jugadores caben en la fila, así que el nombre completo siempre entra en
// una sola línea (`whitespace-nowrap`, sin truncar). Si una fila no cabe
// entera en pantallas angostas, esa fila concreta se desplaza en
// horizontal (`overflow-x-auto`) en vez de encoger las tarjetas.
/** Las cuatro filas, pero partidas por sub-rol para que la cancha sepa
 *  quién juega por la banda. El orden dentro de cada fila da igual: la rejilla
 *  coloca a los de banda en los bordes y centra al resto. */
const ROLE_ROW_ORDER: TeamOfWeekRoleKey[][] = [
  ["forward"],
  ["winger", "innerMidfield"],
  ["wingback", "centralDefender"],
  ["keeper"],
];


/**
 * Mejor alineación real (semana/temporada) — pedido explícitamente
 * 2026-08-08, tras comparar con Hattrick Control. Rating REAL de cada
 * titular (matchlineup.xml, público incluso para un rival: un partido ya
 * jugado es un hecho permanente, no histórico de cuenta ajena) — nunca una
 * proyección, por eso usa `Panel` normal y no `ProjectionPanel`.
 */
function TeamOfTheWeekPanel() {
  const [scope, setScope] = useState<"week" | "season">("week");
  const [formation, setFormation] = useState<Formation>("4-4-2");
  // undefined = "automático" (la última jornada completa) — el backend
  // decide; en cuanto el usuario elige una jornada concreta del selector,
  // se fija ese número y ya no sigue a la última automáticamente.
  const [round, setRound] = useState<number | undefined>(undefined);
  // `undefined` = el reparto propio de la formación. Al cambiar de formación
  // se vuelve a él, porque un reparto de la anterior puede no ser legal aquí:
  // 3 mediocentros valen en un 5-3-2 y no en un 4-4-2.
  const [centrales, setCentrales] = useState<number | undefined>(undefined);
  const [interiores, setInteriores] = useState<number | undefined>(undefined);
  const { data, isLoading, isError, error } = useLeagueTeamOfWeek(
    scope,
    formation,
    round,
    centrales,
    interiores,
  );

  const meta = data
    ? scope === "week"
      ? `jornada ${data.matchRound ?? "?"} · ${data.lineupsFound}/${data.lineupsExpected} alineaciones encontradas`
      : `${data.roundsCovered} jornada(s) · ${data.lineupsFound}/${data.lineupsExpected} alineaciones encontradas`
    : undefined;

  return (
    <Panel title="Mejor alineación" meta={meta}>
      <div className="flex flex-wrap items-center gap-3 border-b border-[var(--border)] px-4 py-3">
        <div className="flex overflow-hidden rounded border border-[var(--border)] text-xs">
          <button
            onClick={() => setScope("week")}
            className={`px-3 py-1 ${scope === "week" ? "bg-[var(--accent)] text-white" : "bg-[var(--surface)]"}`}
          >
            De la semana
          </button>
          <button
            onClick={() => setScope("season")}
            className={`px-3 py-1 ${scope === "season" ? "bg-[var(--accent)] text-white" : "bg-[var(--surface)]"}`}
          >
            De la temporada
          </button>
        </div>
        {scope === "week" && (
          <label className="flex items-center gap-2 text-xs text-[var(--muted)]">
            Jornada
            <select
              value={round ?? data?.matchRound ?? ""}
              onChange={(event) => setRound(Number(event.target.value))}
              className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-sm text-[var(--text)]"
            >
              {[...(data?.availableRounds ?? [])]
                .sort((a, b) => b - a)
                .map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
            </select>
          </label>
        )}
        <label className="flex items-center gap-2 text-xs text-[var(--muted)]">
          Formación
          <select
            value={formation}
            onChange={(event) => {
              setFormation(event.target.value as Formation);
              setCentrales(undefined);
              setInteriores(undefined);
            }}
            className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-sm text-[var(--text)]"
          >
            {(data?.formations ?? FORMATIONS).map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </label>
        {/* Los dos repartos de Hattrick Control. El nombre de la formación no
            dice cuántos juegan por dentro: un 5-3-2 puede llevar 3
            mediocentros, o 2 y un extremo, o 1 y dos. Cuando la línea solo
            admite un reparto (cinco defensas son siempre 3+2), el selector
            sale con una sola opción, igual que allí. */}
        <SplitSelector
          label="Defensa central"
          value={data?.centralDefenders}
          options={data?.centralDefenderOptions ?? []}
          onChange={setCentrales}
        />
        <SplitSelector
          label="Medio central"
          value={data?.innerMidfielders}
          options={data?.innerMidfielderOptions ?? []}
          onChange={setInteriores}
        />
      </div>

      {isLoading && <Loading />}
      {/* El error real, no una causa supuesta: este panel daba siempre
          "hace falta una sesión de Hattrick activa" pasara lo que pasara, y
          el 2026-08-19 eso escondió un 422 por una formación que la API no
          aceptaba. Culpar a la sesión de cualquier fallo manda a buscar donde
          no es. */}
      {isError && <ErrorState error={error} />}
      {data && (
        <>
          <PitchField
            ariaLabel={`Mejor alineación ${scope === "week" ? "de la jornada" : "de la temporada"}, formación ${formation}, por rating real`}
          >
            {/* La misma rejilla que Alineación y el Mejor once del Dashboard:
                todas las canchas de la app se dibujan igual. Aquí el once
                ideal llega agrupado por LÍNEA y sin lado, así que no hay a
                quién poner en las bandas y cada fila se centra sobre el ancho
                completo. */}
            <PitchGrid
              // Por sub-rol y no por línea: así los de banda van a las orillas
              // como en Alineación y en el Mejor once del Dashboard. Antes
              // esta cancha no podía hacerlo porque el dato llegaba agrupado
              // sin lado.
              rows={ROLE_ROW_ORDER.map((fila) =>
                fila.flatMap((rol) =>
                  data.positions[rol].map((p) => ({ rol, player: p })),
                ),
              )}
              isFlank={({ rol }) => rol === "winger" || rol === "wingback"}
              render={({ rol, player }) => (
                <div key={`${rol}-${player.htPlayerId}`} className={PITCH_CARD_CLASS}>
                  <div className="whitespace-nowrap text-[11px] font-semibold text-white">
                    {player.name}
                  </div>
                  <div className="whitespace-nowrap text-[9px] text-white/70">
                    {player.teamName}
                  </div>
                  <div className="text-[10px] font-medium text-amber-300">
                    ★ {player.ratingStars.toFixed(1)}
                  </div>
                </div>
              )}
            />
            {Object.values(data.positions).every(
              (group) => group.length === 0,
            ) && (
              <div className="flex items-center justify-center px-8 py-16 text-center text-sm text-white/70">
                Sin alineaciones encontradas todavía para este rango.
              </div>
            )}
          </PitchField>
          <div className="space-y-1 border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
            <p>
              Total estrellas del once:{" "}
              <span className="font-medium text-[var(--text)]">
                {data.totalStars}
              </span>
            </p>
            {data.caveats.map((c, i) => (
              <p key={i}>{c}</p>
            ))}
          </div>
        </>
      )}
    </Panel>
  );
}
