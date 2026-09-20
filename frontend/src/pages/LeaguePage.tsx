import { EnlaceATransparencia } from "../components/EnlaceATransparencia";
import type { ReactNode } from "react";
import { useState } from "react";
import type { TooltipComponentFormatterCallbackParams } from "echarts";
import { Link } from "react-router-dom";
import { Chart } from "../charts/Chart";
import { BarraDePrediccion } from "../components/BarraDePrediccion";
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
import {
  PITCH_CARD_CLASS,
  PitchField,
  PitchGrid,
} from "../components/PitchField";
import { SplitSelector } from "../components/SplitSelector";
import { Tabs, PanelDePestanas } from "../components/Tabs";
import { PitchZoneMethodSelector } from "../components/PitchZoneMethodSelector";
import { PITCH_ZONE_METHODS } from "../components/pitchZoneMethods";
import { TsiHistogramPanel } from "../components/TsiHistogramPanel";
import { number, ordinal } from "../hooks/useFormat";
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
  LeagueMatchRef,
  LeaguePitchZoneMethod,
  LeagueStandingRow,
  LeagueTeamSummary,
  OutlookRow,
  TeamOfWeekRoleKey,
} from "../services/api";

import { tx } from "../i18n/tx";
/**
 * Liga y predicciones. HL-080, HL-083, HL-090, HL-091, HL-094.
 *
 * La respuesta a «¿en qué puesto acabo?» es una distribución, no un número.
 * Dieciséis jornadas son pocas para que el mejor equipo gane siempre, y una
 * herramienta que devuelva «4º» está escondiendo justo la parte informativa.
 */
/** Puntos sobre el líder (si vas primero) o bajo el líder (si no), de
 * `standings`, nunca de la simulación: es un hecho de hoy, no una
 * proyección. */
function leaderGap(data: League): { label: string; value: string } {
  const leader = data.standings.find((s) => s.position === 1);
  const own = data.standings.find((s) => s.isOwnTeam);
  if (!leader || !own) return { label: tx("Brecha"), value: "-" };
  if (own.position === 1) {
    const second = data.standings.find((s) => s.position === 2);
    if (!second) return { label: tx("Ventaja sobre el 2º"), value: "-" };
    return {
      label: tx("Ventaja sobre el 2º"),
      value: `+${own.points - second.points} pts`,
    };
  }
  return {
    label: tx("Brecha frente al líder"),
    value: `-${leader.points - own.points} pts`,
  };
}

type LeagueSection = "resumen" | "proyeccion" | "comparativa";

export function LeaguePage() {
  // UN SOLO RESUMEN PARA LA PROYECCIÓN (2026-09-09, pedido del usuario). El
  // mando vive en esa pestaña y el estado aquí, en la página. Hasta el
  // 2026-09-12 mandaba también sobre el próximo partido del Resumen; desde
  // entonces ese panel usa una alineación concreta por lado --tu enviada o tu
  // última, su última-- y no depende de esto.
  const [metodo, setMetodo] = useState<LeaguePitchZoneMethod>("average");
  const { data, isLoading, isError, error } = useLeague(10_000, metodo);
  const [section, setSection] = useState<LeagueSection>("resumen");
  // ARRIBA DEL TODO, antes de cualquier return: un hook detrás de un return
  // temprano se salta en las cargas en las que ese return dispara, y React
  // tumba la pantalla entera con «Rendered more hooks than during the
  // previous render». Aquí pasó, con la página en blanco.
  const modoOscuro = useIsDarkTheme();
  // En hexadecimal porque el gráfico va sobre canvas: ver `marcasDeCambio`.
  const subida = modoOscuro ? "#2fbf71" : "#1a9e5c";
  const bajada = modoOscuro ? "#e5484d" : "#d1383d";
  // El mismo azul que el tema le daría por defecto a la primera serie; se
  // escribe aquí porque la barra ya no puede heredarlo: al fijarle opacidad
  // hay que fijarle también el color, o echarts pinta la transparencia sobre
  // el negro del canvas en vez de sobre el azul.
  const azul = modoOscuro ? "#4f7cff" : "#3b63e0";

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
          <h1 className="text-xl font-semibold">{tx("Liga")}</h1>
          <p className="text-sm text-[var(--muted)]">
            {data.seriesName} {tx("· temporada")} {data.season}{" "}
            {tx("· jornada")} {data.roundsPlayed}
          </p>
          <EnlaceATransparencia seccion="liga" calculo="simulacion" />
        </div>
        <Tabs
          grupo="liga"
          tabs={[
            { key: "resumen", label: tx("Resumen") },
            { key: "proyeccion", label: tx("Proyección") },
            { key: "comparativa", label: tx("Comparativa") },
          ]}
          active={section}
          onChange={setSection}
        />
      </header>

      <PanelDePestanas grupo="liga" activa={section} className="space-y-4">
        {section === "resumen" && (
          <div className="space-y-4">
            {/* Resumen oficial, solo hechos: lo que Hattrick ya reportó,
                nada proyectado. */}
            {own && (
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 [&>*]:min-w-0">
                <Kpi
                  label={tx("Posición actual")}
                  value={ordinal(own.currentPosition)}
                  hint={tx("{{v0}} puntos · jornada {{v1}}", {
                    v0: own.currentPoints,
                    v1: data.roundsPlayed,
                  })}
                />
                <Kpi
                  label={tx("Puntos actuales")}
                  value={String(own.currentPoints)}
                />
                <Kpi
                  label={gap.label}
                  value={gap.value}
                  hint={tx("frente a hoy, de la clasificación")}
                />
              </div>
            )}

            <Panel
              title={tx("Clasificación")}
              meta={tx("jornada {{v0}}", { v0: data.roundsPlayed })}
            >
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
                {tx("Confianza todavía baja:")} {data.roundsPlayed}{" "}
                {tx(
                  "jornada(s) jugada(s); el prior pesa más que los resultados observados.",
                )}
              </div>
            )}

            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 [&>*]:min-w-0">
              <Kpi
                label={tx("Posición esperada")}
                value={own.expectedPosition.toFixed(1)}
                hint={tx("más probable: {{v0}}", {
                  v0: ordinal(own.mostLikelyPosition),
                })}
              />
              <Kpi
                label={tx("Probabilidad de terminar 1º")}
                value={`${(own.titleProbability * 100).toFixed(0)}%`}
                hint={
                  data.isTopDivision
                    ? tx("ya estás en primera división")
                    : tx(
                        "ascenso directo o promoción según el ranking nacional, no modelado",
                      )
                }
                tone={own.titleProbability > 0.5 ? "positive" : undefined}
              />
              <Kpi
                label={tx("Probabilidad de Top 4")}
                value={`${((own.titleProbability + own.secondToFourthProbability) * 100).toFixed(0)}%`}
                hint={tx("1º-4º combinados")}
              />
              <Kpi
                label={tx("Puntos finales esperados")}
                value={own.expectedPoints.toFixed(1)}
                hint={tx("hoy: {{v0}}", { v0: own.currentPoints })}
              />
            </div>
            <p className="text-xs text-[var(--muted)]">
              {tx(
                'Riesgo de promoción de permanencia y descenso directo: ver la tabla "Pronóstico por equipo" más abajo, columnas 5º-6º y 7º-8º.',
              )}
            </p>

            {/* Antes de las gráficas: es el mando que las mueve, y ponerlo
                debajo obligaba a bajar, tocar y volver a subir para ver el
                efecto. Sin «Alineación enviada» --de siete de los ocho
                equipos no se pueden ver las órdenes--. */}
            <Panel title={tx("Cómo se resume cada equipo")}>
              <div className="px-4 pb-4 pt-1">
                {/* Qué MUEVE el mando va antes de los botones; qué SIGNIFICA
                    cada botón lo cuenta el propio selector, debajo. */}
                <p className="prosa text-xs leading-relaxed text-[var(--muted)]">
                  {tx(
                    "Cada equipo juega varios partidos y hay que quedarse con un número por zona. Esto elige con cuál, y vale para los ocho equipos: mueve los puntos esperados, la distribución de puestos y los límites. El próximo partido del Resumen no lo sigue: ahí va una alineación concreta por lado.",
                  )}
                </p>
                <PitchZoneMethodSelector
                  method={data.pitchZoneMethod}
                  onMethodChange={(v) => setMetodo(v as LeaguePitchZoneMethod)}
                  options={PITCH_ZONE_METHODS}
                />
              </div>
            </Panel>

            <ProjectionPanel
              title={tx("Distribución de la posición final")}
              meta={tx("{{v0}} simulaciones", {
                v0: number(data.simulationRuns),
              })}
            >
              {data.change && (
                <FranjaDeCambio>
                  {tx("Tras la jornada")} {data.change.matchRound}{" "}
                  {data.change.ownTitleAfter >= data.change.ownTitleBefore
                    ? tx("subes")
                    : tx("caes")}{" "}
                  {tx("de")} {(data.change.ownTitleBefore * 100).toFixed(1)}
                  {tx("% a")} {(data.change.ownTitleAfter * 100).toFixed(1)}
                  {tx("% de ser campeón.")}
                  {data.change.biggestGainer && (
                    <>
                      {" "}
                      {tx("Quien más ganó fue")} {data.change.biggestGainer}
                      {tx(", de")}{" "}
                      {(data.change.biggestGainerBefore * 100).toFixed(1)}
                      {tx("% a")}{" "}
                      {(data.change.biggestGainerAfter * 100).toFixed(1)}%.
                    </>
                  )}
                </FranjaDeCambio>
              )}
              <Chart
                ariaLabel={tx(
                  "Distribución de probabilidad de la posición final",
                )}
                option={{
                  xAxis: {
                    type: "category",
                    data: Object.keys(own.positionDistribution),
                    name: tx("puesto"),
                  },
                  yAxis: {
                    type: "value",
                    axisLabel: { formatter: "{value}%" },
                  },
                  tooltip: {
                    trigger: "item",
                    formatter: (p: TooltipComponentFormatterCallbackParams) => {
                      const item = Array.isArray(p) ? p[0] : p;
                      if (!item) return "";
                      return tx("{{v0}} puesto: {{v1}}%", {
                        v0: ordinal(String(item.name)),
                        v1: Number(item.value).toFixed(1),
                      });
                    },
                  },
                  series: [
                    {
                      type: "bar",
                      data: barrasConCambio(
                        Object.values(own.positionDistribution).map(
                          (v) => v * 100,
                        ),
                        Object.keys(own.positionDistribution),
                        data.change?.positionDelta,
                        { sube: subida, baja: bajada },
                      ),
                      itemStyle: {
                        borderRadius: 3,
                        color: azul,
                        opacity: OPACIDAD_BARRA,
                      },
                    },
                  ],
                }}
                height={240}
              />
              <p className="prosa border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
                {tx(
                  "Cada barra es la fracción de temporadas simuladas en las que acabas en ese puesto. Si la distribución es ancha, la liga aún no está decidida, y eso es lo que un único número escondería.",
                )}
              </p>
            </ProjectionPanel>

            <BestWorstPanel data={data} />

            <ProjectionPanel
              title={tx("Pronóstico por equipo")}
              meta={tx("ordenado por posición actual")}
            >
              <OutlookTable data={data} />
            </ProjectionPanel>
          </div>
        )}

        {/* Las dos a la vez (2026-09-14, pedido del usuario): la mejor
            alineación vivía DENTRO de la comparativa, después de su «cargando»,
            así que no empezaba a pedirse hasta que la comparativa terminaba. */}
        {section === "comparativa" && (
          <>
            <LeagueTsiComparison />
            <TeamOfTheWeekPanel />
          </>
        )}
      </PanelDePestanas>
    </div>
  );
}

/** «Deportivo Uno 1 - 2 Pulgas Arrechas · jornada 6»: el mismo formato que
 *  la ficha de rival, para que un partido se lea igual en toda la app. */
function PartidoNombrado({ partido }: { partido: LeagueMatchRef }) {
  return (
    <>
      {partido.home}{" "}
      <b className="tabular-nums text-[var(--text)]">
        {partido.homeGoals} - {partido.awayGoals}
      </b>{" "}
      {partido.away}
      {partido.round != null
        ? tx(" · jornada {{v0}}", { v0: partido.round })
        : ""}
    </>
  );
}

/** Un lado del próximo partido: qué alineación se toma, cuál fue y por qué.
 *  Mismo dibujo que las dos tarjetas de fuente de la ficha de rival. */
function LadoDelProximo({
  equipo,
  fuente,
  partido,
  tactica,
  porque,
  nota,
}: {
  equipo: string;
  fuente: string;
  partido: LeagueMatchRef | null;
  tactica: string;
  porque: string;
  nota?: ReactNode;
}) {
  return (
    <div className="rounded border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2">
      <div className="text-[10px] uppercase text-[var(--muted)]">{equipo}</div>
      <div className="text-xs font-semibold">{fuente}</div>
      {partido && (
        <p className="mt-0.5 text-[11px] text-[var(--muted)]">
          <PartidoNombrado partido={partido} />
        </p>
      )}
      <p className="mt-0.5 text-[11px] text-[var(--muted)]">
        {tx("Táctica:")} {tactica}
      </p>
      <p className="prosa mt-1.5 text-[11px] leading-relaxed text-[var(--muted)]">
        {porque}
      </p>
      {nota && (
        <p className="prosa mt-1 text-[11px] leading-relaxed text-[var(--muted)]">
          {nota}
        </p>
      )}
    </div>
  );
}

function NextMatch({ data }: { data: League }) {
  const nm = data.nextMatch!;
  const fuentes = nm.sources;
  const tuNombre = nm.isHome ? nm.home : nm.away;
  const suNombre = nm.isHome ? nm.away : nm.home;
  // LA CABECERA DICE CON QUÉ ESTÁ HECHO (2026-09-12). Decía «tendencia
  // histórica de liga», que describía el método de antes --los goles de la
  // temporada-- y no el que corría.
  const meta = !fuentes
    ? tx("goles de la temporada")
    : fuentes.own.kind === "submitted"
      ? tx("tu alineación enviada contra su último partido")
      : tx("tu último partido contra el suyo");

  return (
    <Panel title={tx("Próximo partido")} meta={meta}>
      <div className="space-y-3 p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
          <span>
            <span className={nm.isHome ? "font-medium" : ""}>{nm.home}</span>
            <span className="mx-2 text-[var(--muted)]">{tx("vs")}</span>
            <span className={!nm.isHome ? "font-medium" : ""}>{nm.away}</span>
          </span>
          <span className="text-xs text-[var(--muted)]">
            {tx("goles esperados")} {nm.expectedHomeGoals} –{" "}
            {nm.expectedAwayGoals} {tx("· resultado más probable")}{" "}
            {nm.mostLikelyScore}
          </span>
        </div>

        {/* La misma barra que Copa y Rivales: un solo componente para que
            el mismo motor no se lea distinto en cada pantalla. */}
        <BarraDePrediccion
          tuLabel={tuNombre}
          tuValor={nm.isHome ? nm.homeWin : nm.awayWin}
          rivalLabel={suNombre}
          rivalValor={nm.isHome ? nm.awayWin : nm.homeWin}
          empate={nm.draw}
        />
      </div>
      {/* UNA ALINEACIÓN CONCRETA POR LADO (2026-09-12, pedido del usuario:
          «deja claro cuál se toma y el por qué»). No sigue al selector de
          Proyección: aquí se pronostica un partido, y un partido se juega
          con un once. */}
      {fuentes && (
        <div className="grid gap-2 border-t border-[var(--border)] px-4 py-3 sm:grid-cols-2">
          <LadoDelProximo
            equipo={tuNombre}
            fuente={
              fuentes.own.kind === "submitted"
                ? tx("Alineación enviada")
                : tx("Último partido")
            }
            partido={fuentes.own.match}
            tactica={fuentes.own.tactic}
            porque={
              fuentes.own.kind === "submitted"
                ? tx(
                    "Ya mandaste las órdenes para este partido, así que no hay nada que adivinar: son los ratings que Hattrick prevé para esa alineación, con su táctica.",
                  )
                : tx(
                    "Todavía no mandaste alineación, y tu último once es lo más parecido a lo que vas a poner. En cuanto mandes las órdenes, este lado pasa a usarlas.",
                  )
            }
            nota={
              fuentes.own.kind === "submitted" && fuentes.own.setPiecesFrom ? (
                <>
                  {tx(
                    "Las acciones indirectas a balón parado Hattrick no las prevé para unas órdenes: salen de tu último partido,",
                  )}{" "}
                  <PartidoNombrado partido={fuentes.own.setPiecesFrom} />.
                </>
              ) : null
            }
          />
          <LadoDelProximo
            equipo={suNombre}
            fuente={tx("Último partido")}
            partido={fuentes.rival.match}
            tactica={fuentes.rival.tactic}
            porque={tx(
              "Sus órdenes son privadas hasta que se juega. Su último partido es lo más reciente que se sabe de él: recoge fichajes, lesiones y cambios de sistema antes que ningún resumen.",
            )}
          />
        </div>
      )}
      <p className="flex items-center justify-between gap-3 border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
        <span>
          {fuentes ? (
            <>
              {nm.verdict}
              {tx(
                ", con una alineación concreta por lado y la táctica de cada una. Un solo partido es lo más al día y también lo más frágil: si alguien rotó o jugó raro ese día, el pronóstico lo hereda. Los resúmenes de varios partidos están en Proyección.",
              )}
            </>
          ) : (
            <>
              {nm.verdict}
              {tx(
                ", con los goles a favor y en contra de la temporada: todavía no hay ratings de los dos equipos.",
              )}
            </>
          )}{" "}
          {/* El capítulo entero del motor, no un resumen: quien pregunta «de
              dónde sale este 32 %» quiere el paso a paso. */}
          <EnlaceATransparencia
            seccion="pronostico"
            calculo="pronostico-resumen"
          />
        </span>
        <Link
          to="/rivals"
          className="shrink-0 whitespace-nowrap text-[var(--accent)] hover:underline"
        >
          {tx("Estudiar al rival →")}
        </Link>
      </p>
    </Panel>
  );
}

const STANDINGS_MODES: ["all", "home", "away"] = ["all", "home", "away"];
const STANDINGS_MODE_LABELS: Record<(typeof STANDINGS_MODES)[number], string> =
  {
    all: tx("Total"),
    home: tx("Local"),
    away: tx("Visitante"),
  };

function StandingsTable({ data }: { data: League }) {
  type Row = LeagueStandingRow;
  // 2026-08-08, pedido explícitamente: leaguedetails.xml solo da la tabla
  // combinada, Local/Visitante se calculan aparte en el backend desde los
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
      header: tx("Equipo"),
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
    {
      key: "points",
      header: tx("Pts"),
      align: "right",
      value: (r) => r.points,
    },
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
        emptyMessage={tx(
          "Sin clasificación: se llena cuando se sincronice la liga.",
        )}
        rows={rows}
        columns={columns}
        rowKey={(r) => r.htTeamId}
        initialSort="position"
        initialDescending={false}
        csvName={`clasificacion-${mode}`}
        filterPlaceholder={tx("Filtrar equipos…")}
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
 * Historial real de posición/puntos por jornada sincronizada, una línea
 * por equipo, como el historial de serie de Hattrick. Cada sync guarda una
 * foto de TODA la serie, así que con varias jornadas sincronizadas esto es
 * una serie temporal real, no una jornada, los huecos (jornadas sin
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
  // un hecho, no un dato sincronizado), no cuenta como jornada real.
  const realRounds = h.rounds.filter((r) => r !== 0).length;
  return (
    <Panel
      title={tx("Historial de la serie")}
      meta={tx("{{v0}} jornada(s) sincronizada(s)", { v0: realRounds })}
    >
      <div className="flex gap-3 border-b border-[var(--border)] px-4 py-3">
        <div className="flex overflow-hidden rounded border border-[var(--border)] text-xs">
          <button
            className={`px-3 py-1 ${metric === "position" ? "bg-[var(--accent)] text-white" : "bg-[var(--surface)]"}`}
            onClick={() => setMetric("position")}
          >
            {tx("Puesto")}
          </button>
          <button
            className={`px-3 py-1 ${metric === "points" ? "bg-[var(--accent)] text-white" : "bg-[var(--surface)]"}`}
            onClick={() => setMetric("points")}
          >
            {tx("Puntos")}
          </button>
        </div>
      </div>
      <Chart
        ariaLabel={tx("Historial de {{v0}} por jornada", {
          v0: metric === "position" ? tx("posición") : tx("puntos"),
        })}
        option={{
          xAxis: {
            type: "category",
            data: h.rounds.map(String),
            name: tx("jornada"),
          },
          yAxis:
            metric === "position"
              ? {
                  type: "value",
                  inverse: true,
                  min: 1,
                  max: nTeams,
                  interval: 1,
                  name: tx("puesto"),
                }
              : { type: "value", name: tx("puntos") },
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
    </Panel>
  );
}

/**
 * Calendario completo de la serie, pedido explícitamente 2026-08-08. El
 * backend ya trae `fixtures` (leaguefixtures.xml, calendario COMPLETO de
 * la serie) desde HL-090; solo faltaba pintarlo. Verde = ganó, ámbar =
 * empate, texto normal = perdió, el propio equipo siempre en negrita y
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
    <Panel
      title={tx("Calendario completo")}
      meta={tx("{{v0}} jornada(s)", { v0: rounds.length })}
    >
      <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {rounds.map((rnd) => {
          const matches = byRound.get(rnd)!;
          return (
            <div
              key={rnd}
              className="rounded-lg border border-[var(--border)] p-3 text-xs"
            >
              <div className="mb-2 border-b border-[var(--border)] pb-1.5 font-medium text-[var(--muted)]">
                {tx("Jornada")} {rnd} · {matches[0]?.date ?? ""}
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
 * queda, o al revés), solo sirven para acotar matemáticamente el rango de
 * puestos posible, nunca como pronóstico. Mismo estilo que "Distribución de
 * la posición final": el resultado sigue siendo una distribución, no un
 * número, forzar tu propio resultado a un extremo no fija el de los
 * demás, que siguen jugando con su nivel real.
 */
/** Puntos porcentuales a partir de los cuales un cambio merece enseñarse.
 *
 *  Por debajo de esto el gráfico se queda limpio, que es lo que hace que el
 *  aviso signifique algo cuando aparece. Una jornada tranquila deja el panel
 *  exactamente como estaba antes de existir esta función. */
const CAMBIO_MINIMO = 1;

/** La transparencia de las barras de distribución, en los dos paneles.
 *
 *  Las etiquetas ▲/▼ que van encima son verdes y rojas saturadas: si la barra
 *  también va a plena saturación, el aviso deja de destacar sobre ella. Bajar
 *  la barra deja el color fuerte para lo que señala un cambio. Es el mismo
 *  valor en "Distribución de la posición final" y en "Límites matemáticos de
 *  posición" para que los dos gráficos se lean como una sola pantalla. */
const OPACIDAD_BARRA = 0.72;

/** Las barras de un gráfico, cada una con su etiqueta de cambio si la merece.
 *
 *  Devuelve los DATOS, no una configuración de `label` para la serie, y eso
 *  no es un capricho: `label.color` sólo acepta una cadena. Pasarle una
 *  función --para pintar de verde lo que sube y de rojo lo que baja-- no
 *  falla con un error, hace algo peor: echarts deja de dibujar la serie
 *  ENTERA y el gráfico sale con ejes y sin barras. Pasó, y costó encontrarlo
 *  porque las etiquetas sí seguían pintándose.
 *
 *  Poniendo el color en cada punto, cada barra lleva el suyo y la serie se
 *  dibuja. `neutro` es para los límites, donde subir no es ni bueno ni malo
 *  por sí solo: mover probabilidad del 5º al 4º es una mejora aunque una
 *  barra suba y la otra baje. */
function barrasConCambio(
  valores: number[],
  puestos: string[],
  delta: Record<string, number> | undefined,
  colores: { sube: string; baja: string; neutro?: string },
): Array<number | Record<string, unknown>> {
  return valores.map((v, i) => {
    const d = delta?.[puestos[i] ?? ""] ?? 0;
    if (!delta || Math.abs(d) < CAMBIO_MINIMO) return v;
    return {
      value: v,
      label: {
        show: true,
        position: "top",
        formatter: `${d > 0 ? "▲" : "▼"} ${Math.abs(d).toFixed(1)}%`,
        color: colores.neutro ?? (d > 0 ? colores.sube : colores.baja),
        fontSize: 14,
        fontWeight: 500,
      },
    };
  });
}

/** La frase que cuenta qué pasó, encima del gráfico. */
function FranjaDeCambio({ children }: { children: ReactNode }) {
  return (
    <p className="border-b border-[var(--border)] px-4 py-2 text-xs leading-relaxed text-[var(--muted)]">
      {children}
    </p>
  );
}

function BestWorstPanel({ data }: { data: League }) {
  const isDark = useIsDarkTheme();
  const bw = data.bestWorst;
  if (!bw) {
    return (
      <ProjectionPanel title={tx("Límites matemáticos de posición")}>
        <Note>
          {tx(
            "No hay calendario pendiente sincronizado: no queda nada que forzar a un extremo.",
          )}
        </Note>
      </ProjectionPanel>
    );
  }
  const positions = Object.keys(bw.bestCasePositionDistribution);
  // El puesto que más subió y el que más bajó en el peor caso. Se cuenta así
  // y no como «el suelo pasó de 5º a 4º» porque eso último no aguanta: con 4º
  // al 49,1 % y 5º al 48,9 %, cuál gana depende de la tirada de Monte Carlo.
  const cambioEnLimites = (() => {
    const d = data.change?.worstCaseDelta;
    if (!d) return null;
    const entradas = Object.entries(d).filter(
      ([, v]) => Math.abs(v) >= CAMBIO_MINIMO,
    );
    if (entradas.length === 0) return null;
    const arriba = entradas
      .filter(([, v]) => v > 0)
      .sort((a, b) => b[1] - a[1])[0];
    const abajo = entradas
      .filter(([, v]) => v < 0)
      .sort((a, b) => a[1] - b[1])[0];
    return {
      sube: arriba ? arriba[0] : null,
      subeCuanto: arriba ? arriba[1] : 0,
      baja: abajo ? abajo[0] : null,
      bajaCuanto: abajo ? Math.abs(abajo[1]) : 0,
    };
  })();
  const positive = isDark ? "#2fbf71" : "#1a9e5c";
  const danger = isDark ? "#e5484d" : "#d1383d";
  const gris = isDark ? "#8b8b93" : "#71717a";

  return (
    <ProjectionPanel
      title={tx("Límites matemáticos de posición")}
      meta={tx("{{v0}} partidos pendientes · {{v1}} simulaciones", {
        v0: bw.remainingMatches,
        v1: number(data.simulationRuns),
      })}
    >
      {cambioEnLimites && (
        <FranjaDeCambio>
          {tx("La jornada")} {data.change?.matchRound}{" "}
          {tx("movió el peor caso:")}{" "}
          {cambioEnLimites.sube !== null && (
            <>
              {tx("acabar")} {cambioEnLimites.sube}
              {tx("º sube")} {cambioEnLimites.subeCuanto.toFixed(1)}{" "}
              {tx("puntos")}
            </>
          )}
          {cambioEnLimites.sube !== null &&
            cambioEnLimites.baja !== null &&
            tx(" y ")}
          {cambioEnLimites.baja !== null && (
            <>
              {tx("acabar")} {cambioEnLimites.baja}
              {tx("º baja")} {cambioEnLimites.bajaCuanto.toFixed(1)}
            </>
          )}
          {tx(". El mejor caso no se mueve.")}
        </FranjaDeCambio>
      )}
      <p className="border-b border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
        {tx(
          "Escenarios extremos deliberadamente imposibles (goleada en cada partido restante, en un sentido o en el otro); no son pronósticos.",
        )}
      </p>
      <Chart
        ariaLabel={tx(
          "Distribución de la posición final en el mejor y en el peor caso",
        )}
        option={{
          xAxis: { type: "category", data: positions, name: tx("puesto") },
          yAxis: { type: "value", axisLabel: { formatter: "{value}%" } },
          legend: { data: [tx("Mejor caso"), tx("Peor caso")], top: 0 },
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
              name: tx("Mejor caso"),
              type: "bar",
              data: barrasConCambio(
                Object.values(bw.bestCasePositionDistribution).map(
                  (v) => v * 100,
                ),
                positions,
                data.change?.bestCaseDelta,
                { sube: positive, baja: danger, neutro: gris },
              ),
              itemStyle: {
                borderRadius: 3,
                color: positive,
                opacity: OPACIDAD_BARRA,
              },
            },
            {
              name: tx("Peor caso"),
              type: "bar",
              data: barrasConCambio(
                Object.values(bw.worstCasePositionDistribution).map(
                  (v) => v * 100,
                ),
                positions,
                data.change?.worstCaseDelta,
                { sube: positive, baja: danger, neutro: gris },
              ),
              itemStyle: {
                borderRadius: 3,
                color: danger,
                opacity: OPACIDAD_BARRA,
              },
            },
          ],
        }}
        height={240}
      />
      <p className="prosa border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
        {tx(
          "Mejor caso: en cada partido que te queda marcas de goleada y no encajas. Peor caso: al revés. El resto de la liga se simula con el mismo modelo que la gráfica de arriba, zona por zona, con el resumen que elegiste, así que aun forzando tu propio resultado al extremo, tu puesto final sigue siendo una distribución. Tus partidos van forzados y NO los toca ese modelo: por eso tus puntos de cada extremo no cambian aunque cambies el resumen, y lo que se mueve es dónde acaban los demás.",
        )}
      </p>
    </ProjectionPanel>
  );
}

/**
 * 5º-6º y 7º-8º NO se leen de `relegationPlayoffProbability`/
 * `relegationProbability`: esos campos se ponen a 0 cuando no hay playoff de
 * permanencia o descenso posible (división más baja/más alta del país), lo
 * cual tiene sentido para el KPI de "riesgo" de arriba, pero rompe la
 * partición exhaustiva de esta tabla, el equipo igual termina en algún
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
      header: tx("Ahora"),
      align: "right",
      value: (r) => r.currentPosition,
    },
    {
      key: "name",
      header: tx("Equipo"),
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
      header: tx("Puesto esperado"),
      align: "right",
      value: (r) => r.expectedPosition,
      render: (r) => (
        <span className="tabular-nums">{r.expectedPosition.toFixed(1)}</span>
      ),
    },
    {
      key: "points",
      header: tx("Puntos esperados"),
      align: "right",
      value: (r) => r.expectedPoints,
      render: (r) => (
        <span className="tabular-nums">{r.expectedPoints.toFixed(1)}</span>
      ),
    },
    {
      key: "title",
      header: tx("Título"),
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
        // promoción de permanencia real, el rojo aquí sería una alarma
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
  ];
  return (
    <>
      <DataTable
        emptyMessage={tx(
          "Sin proyección: hacen falta jornadas jugadas para estimarla.",
        )}
        rows={data.outlook}
        columns={columns}
        rowKey={(r) => r.htTeamId}
        initialSort="now"
        initialDescending={false}
        csvName="pronostico"
        filterPlaceholder={tx("Filtrar equipos…")}
      />
    </>
  );
}

/**
 * No solo el próximo rival: dónde queda la plantilla frente a TODA la serie.
 * Mismo motor que la ficha de un rival puntual (`tsi_kde_comparison`), aquí
 * agregado a los 7-8 equipos de la liga a la vez.
 *
 * 2026-08-08, pedido explícitamente: vuelve a cargar sola al entrar a
 * /league (revierte el arranque colapsado del 2026-08-05), pide las
 * plantillas de los 7-8 rivales a CHPP apenas se abre la página, sin
 * esperar a que el usuario la abra a propósito.
 */
function LeagueTsiComparison() {
  // 2026-08-08, pedido explícitamente: default Log(TSI+1), la escala
  // lineal aplasta casi todos los planteles contra el eje cuando hay 1-2
  // fichajes estrella en la liga, así que la vista log es la que de verdad
  // sirve para comparar de un vistazo. "Los 11 mejores" también por
  // defecto: compara fuerza de juego real, no el tamaño de la plantilla.
  const [logTsi, setLogTsi] = useState(true);
  const [top11, setTop11] = useState(true);
  const { data, isLoading, isError } = useLeagueComparison(logTsi, top11);

  if (isLoading)
    return (
      <Panel title={tx("Comparativa de liga")}>
        <Loading />
      </Panel>
    );
  if (isError || !data) {
    return (
      <Panel title={tx("Comparativa de liga")}>
        <Note>
          {tx(
            "No se pudo comparar contra la serie, hace falta una sesión de Hattrick activa y la clasificación sincronizada.",
          )}
        </Note>
      </Panel>
    );
  }

  const columns: Column<LeagueTeamSummary>[] = [
    { key: "rank", header: "#", align: "right", value: (r) => r.rank },
    {
      key: "teamName",
      header: tx("Equipo"),
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
      header: tx("TSI total"),
      align: "right",
      value: (r) => r.totalTsi,
      render: (r) => <span className="tabular-nums">{number(r.totalTsi)}</span>,
    },
    {
      key: "avgTsi",
      header: tx("TSI medio"),
      align: "right",
      value: (r) => r.avgTsi,
      render: (r) => <span className="tabular-nums">{number(r.avgTsi)}</span>,
    },
    {
      key: "playerCount",
      header: tx("Jugadores"),
      align: "right",
      value: (r) => r.playerCount,
    },
    // 2026-08-08, pedido explícitamente: jugador de mayor TSI, su TSI, su
    // última posición jugada en partido oficial, y forma/resistencia
    // medias de la plantilla comparada.
    {
      key: "topPlayerName",
      header: tx("Mejor TSI (jugador)"),
      align: "left",
      value: (r) => r.topPlayerName ?? "",
      // Se enseña el nombre, pero se ordena por su TSI (2026-09-14, pedido
      // del usuario). Sin dato va al fondo.
      sortValue: (r) => r.topPlayerTsi ?? -1,
      render: (r) =>
        r.topPlayerName ? (
          <span>
            {r.topPlayerName}{" "}
            <span className="tabular-nums text-[var(--muted)]">
              ({number(r.topPlayerTsi ?? 0)})
            </span>
          </span>
        ) : (
          <span className="text-[var(--muted)]">-</span>
        ),
    },
    {
      key: "topPlayerLastPosition",
      header: tx("Última posición"),
      align: "left",
      optional: true,
      value: (r) => r.topPlayerLastPosition ?? "",
      render: (r) =>
        r.topPlayerLastPosition ?? (
          <span className="text-[var(--muted)]">-</span>
        ),
    },
    {
      key: "avgForm",
      header: tx("Forma"),
      align: "right",
      optional: true,
      value: (r) => r.avgForm ?? -1,
      render: (r) =>
        r.avgForm != null ? (
          <span className="tabular-nums">{r.avgForm}</span>
        ) : (
          <span className="text-[var(--muted)]">-</span>
        ),
    },
    {
      key: "avgStamina",
      header: tx("Resistencia"),
      align: "right",
      optional: true,
      value: (r) => r.avgStamina ?? -1,
      render: (r) =>
        r.avgStamina != null ? (
          <span className="tabular-nums">{r.avgStamina}</span>
        ) : (
          <span className="text-[var(--muted)]">-</span>
        ),
    },
  ];

  return (
    <>
      <TsiHistogramPanel
        title={tx("TSI: tu plantilla vs. el resto de la liga")}
        meta={tx("{{v0}} equipos · puesto {{v1}} por TSI", {
          v0: data.teamsInSeries,
          v1: data.ownRank,
        })}
        rivalLabel={tx("Resto de la liga")}
        histogram={data.tsiHistogram}
        logTsi={logTsi}
        onLogTsiChange={setLogTsi}
        top11={top11}
        onTop11Change={setTop11}
        noteSuffix={
          tx("del resto de la serie (agregados)") +
          (top11
            ? tx(", tu once real (motor de posiciones) contra los 11 de mayor TSI de cada rival")
            : "") +
          tx(". El TSI de cada rival es real; sus habilidades exactas están ocultas por Hattrick")
        }
      />
      <Panel title={tx("Comparativa de rivales")} meta={data.seriesName}>
        <DataTable
          emptyMessage={tx(
            "Sin comparativa: hacen falta partidos de los rivales.",
          )}
          rows={data.ranking}
          columns={columns}
          rowKey={(r) => r.teamHtId}
          initialSort="totalTsi"
          csvName="comparativa-rivales"
        />
        <p className="prosa border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
          {tx(
            '"Última posición" se consulta aparte, solo para el jugador de mayor TSI de cada equipo; forma y resistencia promedian solo jugadores donde Hattrick de verdad mostró el dato: un rival puede tenerlas ocultas.',
          )}
        </p>
      </Panel>
    </>
  );
}

// Orden de filas (arriba = ataque, abajo = portería), y tamaño de tarjeta
// FIJO, pedido explícitamente 2026-08-08: nunca se achica según cuántos
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
 * Mejor alineación real (semana/temporada), pedido explícitamente
 * 2026-08-08, tras comparar con Hattrick Control. Rating REAL de cada
 * titular (matchlineup.xml, público incluso para un rival: un partido ya
 * jugado es un hecho permanente, no histórico de cuenta ajena), nunca una
 * proyección, por eso usa `Panel` normal y no `ProjectionPanel`.
 */
function TeamOfTheWeekPanel() {
  const [scope, setScope] = useState<"week" | "season">("week");
  const [formation, setFormation] = useState<Formation>("4-4-2");
  // undefined = "automático" (la última jornada completa), el backend
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
    <Panel title={tx("Mejor alineación")} meta={meta}>
      <div className="flex flex-wrap items-center gap-3 border-b border-[var(--border)] px-4 py-3">
        <div className="flex overflow-hidden rounded border border-[var(--border)] text-xs">
          <button
            onClick={() => setScope("week")}
            className={`px-3 py-1 ${scope === "week" ? "bg-[var(--accent)] text-white" : "bg-[var(--surface)]"}`}
          >
            {tx("De la semana")}
          </button>
          <button
            onClick={() => setScope("season")}
            className={`px-3 py-1 ${scope === "season" ? "bg-[var(--accent)] text-white" : "bg-[var(--surface)]"}`}
          >
            {tx("De la temporada")}
          </button>
        </div>
        {scope === "week" && (
          <label className="flex items-center gap-2 text-xs text-[var(--muted)]">
            {tx("Jornada")}
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
          {tx("Formación")}
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
          label={tx("Defensa central")}
          value={data?.centralDefenders}
          options={data?.centralDefenderOptions ?? []}
          onChange={setCentrales}
        />
        <SplitSelector
          label={tx("Medio central")}
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
            ariaLabel={tx(
              "Mejor alineación {{v0}}, formación {{v1}}, por rating real",
              {
                v0:
                  scope === "week" ? tx("de la jornada") : tx("de la temporada"),
                v1: formation,
              },
            )}
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
                <div
                  key={`${rol}-${player.htPlayerId}`}
                  className={PITCH_CARD_CLASS}
                >
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
                {tx("Sin alineaciones encontradas todavía para este rango.")}
              </div>
            )}
          </PitchField>
          <div className="space-y-1 border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
            <p>
              {tx("Total estrellas del once:")}{" "}
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
