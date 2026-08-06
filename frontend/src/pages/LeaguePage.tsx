import { useState } from "react";
import type { TooltipComponentFormatterCallbackParams } from "echarts";
import { Link } from "react-router-dom";
import { Chart } from "../charts/Chart";
import { Column, DataTable } from "../components/DataTable";
import { ErrorState, Kpi, Loading, Note, Panel } from "../components/Panels";
import { TsiHistogramPanel } from "../components/TsiHistogramPanel";
import { number } from "../hooks/useFormat";
import { useIsDarkTheme } from "../hooks/useTheme";
import { useLeague, useLeagueComparison } from "../hooks/useTeam";
import type { League, LeagueTeamSummary, OutlookRow } from "../services/api";

/**
 * Liga y predicciones. HL-080, HL-083, HL-090, HL-091, HL-094.
 *
 * La respuesta a «¿en qué puesto acabo?» es una distribución, no un número.
 * Dieciséis jornadas son pocas para que el mejor equipo gane siempre, y una
 * herramienta que devuelva «4º» está escondiendo justo la parte informativa.
 */
export function LeaguePage() {
  const { data, isLoading, isError, error } = useLeague();

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return null;

  const own = data.ownOutlook;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Liga</h1>
        <p className="text-sm text-[var(--muted)]">
          {data.seriesName} · temporada {data.season} · jornada {data.roundsPlayed}
        </p>
      </header>

      {own && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <Kpi
            label="Posición actual"
            value={`${own.currentPosition}º`}
            hint={`${own.currentPoints} puntos`}
          />
          <Kpi
            label="Posición esperada"
            value={own.expectedPosition.toFixed(1)}
            hint={`más probable: ${own.mostLikelyPosition}º`}
          />
          <Kpi
            label="Probabilidad de ascenso"
            value={`${(own.promotionProbability * 100).toFixed(0)}%`}
            hint={data.isTopDivision ? "ya estás en primera división" : "solo asciende el 1º"}
            tone={own.promotionProbability > 0.5 ? "positive" : undefined}
          />
          <Kpi
            label="Promoción (evitar descenso)"
            value={`${(own.relegationPlayoffProbability * 100).toFixed(0)}%`}
            hint={
              data.isBottomDivision
                ? "no aplica: última división"
                : "puestos 5º-6º, playoff de permanencia"
            }
            tone={own.relegationPlayoffProbability > 0.25 ? "danger" : undefined}
          />
          <Kpi
            label="Descenso directo"
            value={`${(own.relegationProbability * 100).toFixed(0)}%`}
            hint={data.isBottomDivision ? "no aplica: última división" : "puestos 7º-8º"}
            tone={own.relegationProbability > 0.2 ? "danger" : undefined}
          />
        </div>
      )}

      {data.nextMatch && <NextMatch data={data} />}

      {own && (
        <Panel
          title="Distribución de la posición final"
          meta={`${data.simulationRuns.toLocaleString("es-CO")} simulaciones`}
        >
          <Chart ariaLabel="Distribución de probabilidad de la posición final"
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
                  data: Object.values(own.positionDistribution).map((v) => v * 100),
                  itemStyle: { borderRadius: 3 },
                },
              ],
            }}
            height={240}
          />
          <p className="border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
            Cada barra es la fracción de temporadas simuladas en las que acabas en ese
            puesto. Si la distribución es ancha, la liga aún no está decidida — y eso es lo
            que un único número escondería.
          </p>
        </Panel>
      )}

      <Panel title="Clasificación" meta={`jornada ${data.roundsPlayed}`}>
        <StandingsTable data={data} />
      </Panel>

      <HistoryPanel data={data} />

      <BestWorstPanel data={data} />

      <LeagueTsiComparison />

      <Panel title="Pronóstico por equipo" meta="ordenado por posición actual">
        <OutlookTable data={data} />
      </Panel>

      <Panel title="Qué modela la simulación" meta={data.model.model}>
        <div className="space-y-2 p-4 text-xs leading-relaxed text-[var(--muted)]">
          <p>
            Los goles salen de dos Poisson independientes con las fuerzas de ataque y defensa
            de cada equipo, encogidas hacia la media de la liga con un peso de{" "}
            {data.model.shrinkageK}. Con pocas jornadas el prior de «equipo medio» pesa más
            que la evidencia propia; según avanza la temporada, la evidencia gana. La ventaja
            de campo es ×{data.model.homeAdvantage}. Media de goles de esta liga:{" "}
            {data.leagueAvgGoals}.
          </p>
          <p>
            <b className="text-[var(--text)]">No modela:</b>{" "}
            {data.model.doesNotModel.join(", ")}. Sirve para las opciones de la temporada, no
            para acertar un partido concreto.
          </p>
          {data.caveats.map((c, i) => (
            <p key={i}>{c}</p>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function NextMatch({ data }: { data: League }) {
  const nm = data.nextMatch!;
  const bars = [
    { label: nm.home, value: nm.homeWin },
    { label: "Empate", value: nm.draw },
    { label: nm.away, value: nm.awayWin },
  ];
  return (
    <Panel title="Próximo partido" meta={nm.verdict}>
      <div className="space-y-3 p-4">
        <div className="flex items-baseline justify-between text-sm">
          <span className={nm.isHome ? "font-medium" : ""}>{nm.home}</span>
          <span className="text-xs text-[var(--muted)]">
            goles esperados {nm.expectedHomeGoals} – {nm.expectedAwayGoals} · resultado más
            probable {nm.mostLikelyScore}
          </span>
          <span className={!nm.isHome ? "font-medium" : ""}>{nm.away}</span>
        </div>
        <div className="flex h-6 overflow-hidden rounded">
          {bars.map((b, i) => (
            <div
              key={b.label}
              className="flex items-center justify-center text-[10px] text-white"
              style={{
                width: `${b.value * 100}%`,
                background: ["#4f7cff", "#6b7280", "#e0574f"][i],
              }}
              title={`${b.label}: ${(b.value * 100).toFixed(1)}%`}
            >
              {b.value > 0.12 ? `${(b.value * 100).toFixed(0)}%` : ""}
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}

function StandingsTable({ data }: { data: League }) {
  type Row = League["standings"][number];
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
          <Link to={`/rivals/${r.htTeamId}`} className="hover:text-[var(--accent)] hover:underline">
            {r.name}
          </Link>
        ),
    },
    { key: "played", header: "PJ", align: "right", value: (r) => r.played },
    { key: "won", header: "G", align: "right", value: (r) => r.won },
    { key: "drawn", header: "E", align: "right", value: (r) => r.drawn },
    { key: "lost", header: "P", align: "right", value: (r) => r.lost },
    { key: "gf", header: "GF", align: "right", value: (r) => r.goalsFor, optional: true },
    { key: "ga", header: "GC", align: "right", value: (r) => r.goalsAgainst, optional: true },
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
    <DataTable
      rows={data.standings}
      columns={columns}
      rowKey={(r) => r.htTeamId}
      initialSort="position"
      initialDescending={false}
      csvName="clasificacion"
      filterPlaceholder="Filtrar equipos…"
    />
  );
}

const HISTORY_COLORS = [
  "#4f7cff", "#2fbf71", "#f5a524", "#e5484d",
  "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16",
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
    <Panel title="Historial de la serie" meta={`${realRounds} jornada(s) sincronizada(s)`}>
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
          xAxis: { type: "category", data: h.rounds.map(String), name: "jornada" },
          yAxis:
            metric === "position"
              ? { type: "value", inverse: true, min: 1, max: nTeams, interval: 1, name: "puesto" }
              : { type: "value", name: "puntos" },
          legend: { data: h.teams.map((t) => t.name), bottom: 0, type: "scroll" },
          grid: { left: 48, right: 16, top: 28, bottom: 64, containLabel: true },
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
            lineStyle: { width: t.isOwnTeam ? 3 : 1.5, color: HISTORY_COLORS[i % HISTORY_COLORS.length] },
            itemStyle: { color: HISTORY_COLORS[i % HISTORY_COLORS.length] },
            z: t.isOwnTeam ? 2 : 1,
          })),
        }}
        height={320}
      />
      <p className="border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
        Cada punto es una jornada realmente sincronizada — sin datos de por medio, la línea se
        corta en vez de interpolar. La jornada "0" es simbólica: 0 puntos para todos antes de
        jugar nada, no un dato sincronizado — por eso el puesto ahí no se dibuja. Con solo{" "}
        {realRounds} jornada(s) sincronizada(s) el historial todavía dice poco; se vuelve útil
        según se sincroniza cada semana.
      </p>
    </Panel>
  );
}

/**
 * Mismo estilo que "Distribución de la posición final": el mejor y el peor
 * caso también son una distribución, no un número — forzar tu propio
 * resultado a un extremo (goleada) no fija el de los demás, que siguen
 * jugando con su nivel real.
 */
function BestWorstPanel({ data }: { data: League }) {
  const isDark = useIsDarkTheme();
  const bw = data.bestWorst;
  if (!bw) {
    return (
      <Panel title="Mejor caso y peor caso">
        <Note>No hay calendario pendiente sincronizado: no queda nada que forzar a un extremo.</Note>
      </Panel>
    );
  }
  const positions = Object.keys(bw.bestCasePositionDistribution);
  const positive = isDark ? "#2fbf71" : "#1a9e5c";
  const danger = isDark ? "#e5484d" : "#d1383d";

  return (
    <Panel
      title="Mejor caso y peor caso"
      meta={`${bw.remainingMatches} partidos pendientes · ${data.simulationRuns.toLocaleString("es-CO")} simulaciones`}
    >
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
                .map((it) => `${it.seriesName} · ${it.name}º: ${Number(it.value).toFixed(1)}%`)
                .join("<br/>");
            },
          },
          series: [
            {
              name: "Mejor caso",
              type: "bar",
              data: Object.values(bw.bestCasePositionDistribution).map((v) => v * 100),
              itemStyle: { borderRadius: 3, color: positive },
            },
            {
              name: "Peor caso",
              type: "bar",
              data: Object.values(bw.worstCasePositionDistribution).map((v) => v * 100),
              itemStyle: { borderRadius: 3, color: danger },
            },
          ],
        }}
        height={240}
      />
      <p className="border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
        Mejor caso: en cada partido que te queda marcas de goleada y no encajas. Peor caso: al
        revés. El resto de la liga sigue con su nivel real, así que aun forzando tu propio
        resultado al extremo, tu puesto final sigue siendo una distribución.
      </p>
    </Panel>
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
function groupProbability(dist: Record<string, number>, positions: number[]): number {
  return positions.reduce((sum, p) => sum + (dist[String(p)] ?? 0), 0);
}

function OutlookTable({ data }: { data: League }) {
  const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
  const columns: Column<OutlookRow>[] = [
    { key: "now", header: "Ahora", align: "right", value: (r) => r.currentPosition },
    {
      key: "name",
      header: "Equipo",
      align: "left",
      value: (r) => r.name,
      render: (r) =>
        r.isOwnTeam ? (
          <span className="font-medium text-[var(--text)]">{r.name}</span>
        ) : (
          <Link to={`/rivals/${r.htTeamId}`} className="hover:text-[var(--accent)] hover:underline">
            {r.name}
          </Link>
        ),
    },
    {
      key: "expected",
      header: "Puesto esperado",
      align: "right",
      value: (r) => r.expectedPosition,
      render: (r) => <span className="tabular-nums">{r.expectedPosition.toFixed(1)}</span>,
    },
    {
      key: "points",
      header: "Puntos esperados",
      align: "right",
      value: (r) => r.expectedPoints,
      render: (r) => <span className="tabular-nums">{r.expectedPoints.toFixed(1)}</span>,
    },
    {
      key: "title",
      header: "Título",
      align: "right",
      value: (r) => r.titleProbability,
      render: (r) => <span className="tabular-nums">{pct(r.titleProbability)}</span>,
    },
    {
      key: "secondToFourth",
      header: "2º-4º",
      align: "right",
      value: (r) => r.secondToFourthProbability,
      render: (r) => <span className="tabular-nums">{pct(r.secondToFourthProbability)}</span>,
    },
    {
      key: "fifthSixth",
      header: "5º-6º",
      align: "right",
      value: (r) => groupProbability(r.positionDistribution, [5, 6]),
      render: (r) => {
        const v = groupProbability(r.positionDistribution, [5, 6]);
        return (
          <span className={v > 0.25 ? "tabular-nums text-[var(--danger)]" : "tabular-nums"}>
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
        return (
          <span className={v > 0.25 ? "tabular-nums text-[var(--danger)]" : "tabular-nums"}>
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
        rows={data.outlook}
        columns={columns}
        rowKey={(r) => r.htTeamId}
        initialSort="now"
        initialDescending={false}
        csvName="pronostico"
        filterPlaceholder="Filtrar equipos…"
      />
      <p className="border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
        Título, 2º-4º, 5º-6º y 7º-8º cubren TODOS los puestos sin solaparse y siempre suman
        100% — "ascenso" no aparece aparte porque solo asciende el 1º, el mismo evento que el
        título. "5º-6º" es el playoff de promoción para NO descender, no un ascenso extra. En el
        extremo de la pirámide donde no hay a dónde ir (primera división para el título/ascenso,
        última división del país para el 5º-6º y el descenso directo), terminar en esos puestos
        sigue siendo posible — solo que no acarrea la consecuencia deportiva que el nombre de la
        columna sugiere.
      </p>
      <p className="border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
        Ataque y defensa son relativos a la media de la liga: 1,00 es exactamente la media,
        1,30 es marcar un 30% más que un equipo medio. En defensa, menos es mejor.
      </p>
    </>
  );
}

/**
 * No solo el próximo rival: dónde queda la plantilla frente a TODA la serie.
 * Mismo motor que la ficha de un rival puntual (`tsi_kde_comparison`), aquí
 * agregado a los 7-8 equipos de la liga a la vez.
 */
function LeagueTsiComparison() {
  const [logTsi, setLogTsi] = useState(false);
  const [excludeKeeper, setExcludeKeeper] = useState(true);
  const [top11, setTop11] = useState(false);
  const { data, isLoading, isError } = useLeagueComparison(logTsi, excludeKeeper, top11);

  if (isLoading) return <Panel title="Comparativa de liga"><Loading /></Panel>;
  if (isError || !data) {
    return (
      <Panel title="Comparativa de liga">
        <Note>
          No se pudo comparar contra la serie — hace falta una sesión de Hattrick activa y
          la clasificación sincronizada.
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
        <span className={r.isOwn ? "font-medium text-[var(--text)]" : ""}>{r.teamName}</span>
      ),
    },
    {
      key: "totalTsi", header: "TSI total", align: "right", value: (r) => r.totalTsi,
      render: (r) => <span className="tabular-nums">{number(r.totalTsi)}</span>,
    },
    {
      key: "avgTsi", header: "TSI medio", align: "right", value: (r) => r.avgTsi,
      render: (r) => <span className="tabular-nums">{number(r.avgTsi)}</span>,
    },
    { key: "playerCount", header: "Jugadores", align: "right", value: (r) => r.playerCount },
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
        excludeKeeper={excludeKeeper}
        onExcludeKeeperChange={setExcludeKeeper}
        top11={top11}
        onTop11Change={setTop11}
        noteSuffix={
          "del resto de la serie (agregados)" +
          (top11
            ? " — tu once real (motor de posiciones) contra los 11 de mayor TSI de cada rival"
            : "") +
          ". El TSI de cada rival es real; sus habilidades exactas están ocultas por CHPP"
        }
      />
      <Panel title="Ranking de TSI en la serie" meta={data.seriesName}>
        <DataTable
          rows={data.ranking}
          columns={columns}
          rowKey={(r) => r.teamHtId}
          initialSort="totalTsi"
          csvName="ranking-tsi-liga"
        />
      </Panel>
    </>
  );
}
