import { useState } from "react";
import type { CSSProperties } from "react";
import { useParams, Link } from "react-router-dom";
import { Chart } from "../charts/Chart";
import { sharePieOption } from "../charts/chartOptions";
import { Column, DataTable } from "../components/DataTable";
import { Empty, ErrorState, Kpi, Loading, Note, Panel, ProjectionPanel } from "../components/Panels";
import { TsiHistogramPanel } from "../components/TsiHistogramPanel";
import { number } from "../hooks/useFormat";
import { useDashboard, useLeague, useRivalScouting } from "../hooks/useTeam";
import type {
  LastPurchase,
  PitchZoneDuel,
  PitchZoneMethod,
  RivalScouting,
} from "../services/api";

interface RosterRow {
  name: string;
  position: string | null;
  tsi: number;
}

/**
 * Ficha de rival — HL-099 a HL-110, ampliado en HL-2xx. El gancho: comparar
 * tu plantilla contra la del próximo rival con las mismas herramientas que
 * usas para la tuya.
 *
 * Todo lo del rival se pide en vivo cada vez que se abre la ficha, sin
 * guardarse. El roster, marcaje, táctica y rotación se basan en los
 * ÚLTIMOS PARTIDOS OFICIALES REALES del rival contra CUALQUIER equipo — no
 * solo los que jugó contra ti — porque muchos rivales nunca se han
 * enfrentado a tu equipo todavía. Duelos y Escaleras nunca cuentan para
 * nada de esto, sin importar los toggles: no se consideran representativos
 * de cómo juega el rival normalmente.
 */
/** Cómo le va al rival en la liga, si está en tu misma tabla.
 *
 *  La proyección de al lado sale del TSI, que mide lo que vale una plantilla
 *  y no lo que está haciendo con ella. Las dos cosas pueden discrepar mucho:
 *  el 2026-08-31 esta pantalla daba 95% de victoria contra el segundo
 *  clasificado, mientras la página de Liga --que modela goles-- lo daba a él
 *  como favorito. Ninguna de las dos miente; miden cosas distintas. Lo que no
 *  se puede es enseñar una y callar la otra.
 */
function ComoVaEnLaTabla({ rivalHtTeamId }: { rivalHtTeamId: number }) {
  const liga = useLeague();
  const fila = liga.data?.standings?.find((r) => r.htTeamId === rivalHtTeamId);
  if (!fila) return null;
  return (
    <Note>
      En la tabla van <b className="text-[var(--text)]">{fila.position}º</b> con{" "}
      {fila.points} puntos ({fila.won}-{fila.drawn}-{fila.lost}, {fila.goalDifference > 0 ? "+" : ""}
      {fila.goalDifference}). El TSI mide lo que vale una plantilla, no lo que está
      consiguiendo: cuando las dos cosas no cuadran, el resultado manda.
    </Note>
  );
}

export function RivalPage() {
  const { rivalHtTeamId } = useParams<{ rivalHtTeamId: string }>();
  const id = Number(rivalHtTeamId);
  const [logTsi, setLogTsi] = useState(false);
  const [top11, setTop11] = useState(false);
  const [includeCompetitive, setIncludeCompetitive] = useState(true);
  const [includeFriendlies, setIncludeFriendlies] = useState(true);
  const [methodOwn, setMethodOwn] = useState<PitchZoneMethod>("submitted");
  const [methodRival, setMethodRival] = useState<PitchZoneMethod>("average");
  const { data, isLoading, isError, error } = useRivalScouting(
    id, logTsi, top11, includeCompetitive, includeFriendlies, "mixed",
    methodOwn, methodRival,
  );
  const dashboard = useDashboard();

  // Esta pantalla no es como las demás: pide a Hattrick la plantilla y los
  // últimos partidos de un equipo que no es el tuyo, y eso tarda del orden de
  // diez segundos --medido el 2026-08-31--. El esqueleto genérico de cuatro
  // tarjetas no dice nada durante ese rato, y diez segundos sin explicación
  // se leen como que la aplicación se colgó.
  if (isLoading) {
    return (
      <div className="space-y-4" role="status" aria-busy="true">
        <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-sm">
          <b>Estudiando al rival…</b>{" "}
          <span className="text-[var(--muted)]">
            Se le está pidiendo a Hattrick su plantilla y sus últimos partidos.
            Suele tardar unos segundos: no son datos que estén guardados aquí.
          </span>
        </div>
        <Loading />
      </div>
    );
  }
  if (isError) return <ErrorState error={error} />;
  if (!data) return <Empty>Rival no encontrado.</Empty>;

  // Un identificador que no corresponde a ningún equipo devolvía un informe
  // ENTERO: nombre «Rival», cero partidos, TSI vacío y una proyección del
  // 100% de victoria --contra nadie--. Quien se equivoca escribiendo un ID en
  // «Ir directo por ID de equipo» recibía un análisis con pinta de real
  // (2026-08-31). Sin nombre y sin plantilla no hay rival que estudiar.
  if (!data.rivalName || (data.rivalRosterSample?.length ?? 0) === 0) {
    return (
      <div className="space-y-4">
        <header>
          <h1 className="text-xl font-semibold">Rival no encontrado</h1>
          <p className="text-sm text-[var(--muted)]">
            Hattrick no devolvió ningún equipo con el identificador {id}.
          </p>
        </header>
        <Panel title="Qué pudo pasar">
          <ul className="list-disc space-y-1.5 p-4 pl-8 text-sm text-[var(--muted)]">
            <li>El identificador está mal escrito.</li>
            <li>El equipo ya no existe: se disolvió o cambió de manager.</li>
            <li>
              Si lo buscabas por el nombre, es más seguro elegirlo en{" "}
              <Link to="/rivals" className="text-[var(--accent)] hover:underline">
                la lista de rivales
              </Link>
              , que sólo ofrece equipos que existen.
            </li>
          </ul>
        </Panel>
      </div>
    );
  }

  const h = data.tsiHistogram;
  const rivalLabel = data.rivalName ?? "Rival";
  const ownLabel = dashboard.data?.teamName ?? "tu equipo";

  // TSI medio SIEMPRE lineal — a diferencia de tsiHistogram.ownValues/rivalValues,
  // que se transforman a log(TSI+1) cuando el toggle Log(TSI+1) está activo.
  // Este KPI no debe moverse al tocar ese toggle.
  const ownTsiAvg = data.comparison.tsi.own;
  const rivalTsiAvg = data.comparison.tsi.rival;
  const tsiRatio =
    ownTsiAvg && rivalTsiAvg != null && ownTsiAvg > 0 ? rivalTsiAvg / ownTsiAvg : null;

  const rosterColumns: Column<RosterRow>[] = [
    { key: "name", header: "Jugador", align: "left", value: (r) => r.name },
    {
      key: "position", header: "Posición", value: (r) => r.position ?? "",
      render: (r) =>
        r.position ? r.position : <span className="text-[var(--muted)]">—</span>,
    },
    {
      key: "tsi", header: "TSI", align: "right", value: (r) => r.tsi,
      render: (r) => <span className="tabular-nums">{number(r.tsi)}</span>,
    },
  ];

  return (
    <div className="space-y-4">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">
            {dashboard.data?.teamName ?? "Tu equipo"}{" "}
            <span className="text-[var(--muted)]">vs.</span> {rivalLabel}
          </h1>
          <p className="text-sm text-[var(--muted)]">
            {data.matchesAnalysed > 0
              ? `${data.matchesAnalysed} partido(s) oficial(es) reciente(s) del rival analizado(s)`
              : "el rival no tiene partidos oficiales recientes de los tipos seleccionados"}
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          <button
            onClick={() => setIncludeCompetitive((v) => !v)}
            className={
              includeCompetitive
                ? "rounded-md border border-[var(--accent)] px-3 py-1.5 text-xs text-[var(--accent)]"
                : "rounded-md border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--muted)] hover:text-[var(--text)]"
            }
          >
            Liga/Copa/Promoción
          </button>
          <button
            onClick={() => setIncludeFriendlies((v) => !v)}
            className={
              includeFriendlies
                ? "rounded-md border border-[var(--accent)] px-3 py-1.5 text-xs text-[var(--accent)]"
                : "rounded-md border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--muted)] hover:text-[var(--text)]"
            }
          >
            Amistosos
          </button>
        </div>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 [&>*]:min-w-0">
        <Kpi
          label="Partidos analizados"
          value={String(data.matchesAnalysed)}
          hint={
            data.matchesByCompetition.length > 0
              ? data.matchesByCompetition.map((c) => `${c.count} de ${c.label}`).join(" · ")
              : undefined
          }
        />
        <Kpi
          label="TSI medio del rival"
          value={rivalTsiAvg != null ? number(rivalTsiAvg) : "-"}
          hint={tsiRatio != null ? `${tsiRatio.toFixed(2)}x el TSI de ${ownLabel}` : undefined}
        />
      </div>

      <ComparisonPanel data={data} rivalLabel={rivalLabel} ownLabel={ownLabel} />

      <TsiHistogramPanel
        title="TSI: tu plantilla vs. el rival"
        rivalLabel={rivalLabel}
        histogram={h}
        logTsi={logTsi}
        onLogTsiChange={setLogTsi}
        top11={top11}
        onTop11Change={setTop11}
        noteSuffix={
          "del rival" +
          (top11
            ? ", tu once real (motor de posiciones) contra los 11 de mayor TSI del rival"
            : "") +
          ". El TSI del rival es un dato público real; sus habilidades exactas están " +
          "ocultas por Hattrick"
        }
      />

      <ProjectionPanel
        title="Proyección de victoria por TSI"
        meta="modelo simple por TSI, no calibrado"
      >
        <div className="flex items-center gap-4 p-4">
          <div className="text-3xl font-semibold tabular-nums text-[var(--accent)]">
            {(data.winProbability.ownProbability * 100).toFixed(0)}%
          </div>
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-[var(--surface-2)]">
            <div
              className="h-full bg-[var(--accent)]"
              style={{ width: `${data.winProbability.ownProbability * 100}%` }}
            />
          </div>
        </div>
        <Note>
          {data.comparisonReference.ownSource === "submitted_orders" ? "Tu alineación enviada" : "Tus 11 probables"}
          {" "}({number(data.winProbability.ownTsiTotal)} TSI) contra{" "}
          {data.comparisonReference.rivalSource === "probable_recent_starters" ? "el once probable del rival" : "los 11 de mayor TSI del rival"}
          {" "}({number(data.winProbability.rivalTsiTotal)}).
        </Note>
        <ComoVaEnLaTabla rivalHtTeamId={data.rivalHtTeamId} />
      </ProjectionPanel>

      <div className="grid gap-4 lg:grid-cols-2 [&>*]:min-w-0">
        <Panel title="Sugerencia de marcaje al hombre">
          {data.manMarking ? (
            <div className="space-y-2 p-4">
              <p className="text-sm">{data.manMarking.rationale}</p>
              <div className="flex flex-wrap items-center gap-6 text-xs text-[var(--muted)]">
                <span>
                  Objetivo: <b className="text-[var(--text)]">{data.manMarking.targetName}</b>{" "}
                  ({data.manMarking.targetPosition})
                </span>
                <span>
                  Marcador: <b className="text-[var(--text)]">{data.manMarking.markerName}</b>{" "}
                  ({data.manMarking.markerPosition})
                </span>
                <span
                  className={`rounded px-2 py-0.5 text-[11px] font-semibold ${
                    data.manMarking.efficiency === "cerca"
                      ? "bg-[var(--positive)]/15 text-[var(--positive)]"
                      : "bg-[var(--warning)]/15 text-[var(--warning)]"
                  }`}
                >
                  {data.manMarking.efficiency === "cerca" ? "Combinación óptima" : "Combinación lejos"}
                  {" "}(-{(data.manMarking.markerLossPct * 100).toFixed(0)}%)
                </span>
              </div>
              <p className="text-xs text-[var(--muted)]">
                Confianza: {data.manMarking.confidence}. Solo compensa si el objetivo es una
                amenaza clara.
              </p>
              <p className="text-xs text-[var(--muted)]">{data.manMarking.riskNote}</p>
            </div>
          ) : (
            <Empty>
              Sin datos suficientes: ningún jugador rival marcable (delantero, extremo o
              interior) apareció en los partidos vistos con posición conocida, o no tienes un
              jugador propio elegible para marcarlo.
            </Empty>
          )}
        </Panel>

        <Panel title="Rotación del ataque">
          {data.sideRotation ? (
            <div className="space-y-3 p-4">
              <AttackLanes rotation={data.sideRotation} />
              <p className="text-xs text-[var(--muted)]">
                {data.sideRotation.dominantPct === 100
                  ? `Lado fuerte fijo, sin excepción: la ${data.sideRotation.strongSide} fue el carril más fuerte en los ${data.sideRotation.matchesAnalysed} de ${data.sideRotation.matchesAnalysed} partidos vistos.`
                  : data.sideRotation.rotates
                    ? `Rota: ningún lado domina de forma consistente, el más fuerte cambió partido a partido en sus últimos ${data.sideRotation.matchesAnalysed} partido(s) oficiales.`
                    : `Lado fuerte habitual: la ${data.sideRotation.strongSide} fue el carril más fuerte en el ${data.sideRotation.dominantPct.toFixed(0)}% de sus últimos ${data.sideRotation.matchesAnalysed} partido(s), con variación partido a partido, no siempre por el mismo margen.`}
              </p>
            </div>
          ) : (
            <Empty>Sin partidos oficiales recientes del rival con datos de sector.</Empty>
          )}
        </Panel>
      </div>

      <PitchZoneDuelsPanel
        duels={data.pitchZoneDuels}
        matchesAnalysed={data.pitchZonesMatchesAnalysed}
        sources={data.pitchZoneSources}
        methodOwn={methodOwn}
        methodRival={methodRival}
        onMethodOwnChange={setMethodOwn}
        onMethodRivalChange={setMethodRival}
        submittedAvailable={data.submittedLineupAvailable}
      />

      {data.tacticHistory && (
        <Panel
          title="Táctica habitual del rival"
          meta={`${data.tacticHistory.matchesAnalysed} partido(s) con datos de sector`}
        >
          <div className="grid gap-4 p-4 sm:grid-cols-2 [&>*]:min-w-0">
            <div>
              <Chart
                ariaLabel="Reparto de las tácticas que ha usado el rival en los partidos vistos"
                height={Math.max(200, data.tacticHistory.tactics.length * 30)}
                option={sharePieOption(
                  data.tacticHistory.tactics.map((t) => ({ name: t.label, value: t.count })),
                )}
              />
            </div>
            <div className="space-y-3">
              {data.tacticHistory.mostCommonTactic && (
                <div>
                  <div className="text-xs text-[var(--muted)]">Táctica más usada</div>
                  <div className="text-lg font-semibold">
                    {data.tacticHistory.mostCommonTactic.label}{" "}
                    <span className="text-sm font-normal text-[var(--muted)]">
                      ({data.tacticHistory.mostCommonTactic.count} de{" "}
                      {data.tacticHistory.matchesAnalysed} ·{" "}
                      {data.tacticHistory.mostCommonTactic.pct.toFixed(0)}%)
                    </span>
                  </div>
                </div>
              )}
              {data.tacticHistory.avgTacticSkill != null && (
                <div>
                  <div className="text-xs text-[var(--muted)]">Nivel medio de táctica</div>
                  <div className="text-lg font-semibold tabular-nums">
                    {data.tacticHistory.avgTacticSkill.toFixed(1)}
                  </div>
                </div>
              )}
              {data.tacticHistory.mostCommonFormation && (
                <div>
                  <div className="text-xs text-[var(--muted)]">Formación más usada</div>
                  <div className="text-lg font-semibold">
                    {data.tacticHistory.mostCommonFormation.formation}{" "}
                    <span className="text-sm font-normal text-[var(--muted)]">
                      ({data.tacticHistory.mostCommonFormation.count} de{" "}
                      {data.tacticHistory.matchesAnalysed} ·{" "}
                      {data.tacticHistory.mostCommonFormation.pct.toFixed(0)}%)
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </Panel>
      )}

      <Panel
        title="Jugadores del rival identificados"
        meta="top 5 por TSI, de sus últimos partidos oficiales, sea contra quien sea"
      >
        {data.rivalRosterSample.length === 0 ? (
          <Empty>Aún no se ha visto a ningún jugador de este equipo en un partido jugado.</Empty>
        ) : (
          <DataTable
            rows={data.rivalRosterSample}
            columns={rosterColumns}
            rowKey={(r) => r.name}
            initialSort="tsi"
            csvName={`${rivalLabel}-jugadores`}
            emptyMessage="Sin jugadores identificados."
          />
        )}
      </Panel>

    </div>
  );
}

/** Los tres carriles del ataque rival, un partido por columna.
 *
 * Tres promedios no distinguen "45 todas las semanas" de "70, 20, 45", y esa
 * diferencia es justo la que decide si preparas un lado o los tres. Aquí cada
 * columna es un partido en orden cronológico y cada fila un carril: la altura
 * de la barra es el rating de ese carril ese día, y el punto marca por dónde
 * atacó mejor. Un carril oscuro y continuo es un lado fijo; los puntos
 * saltando de fila en fila son rotación de verdad.
 *
 * A la derecha, el promedio con su barra de dispersión: un promedio alto con
 * mucha dispersión avisa de que ese lado depende del día.
 */
function AttackLanes({ rotation }: { rotation: NonNullable<RivalScouting["sideRotation"]> }) {
  const carriles = [
    ["izquierda", "left", rotation.attackLeftAvg, rotation.attackLeftStd],
    ["centro", "central", rotation.attackCentralAvg, rotation.attackCentralStd],
    ["derecha", "right", rotation.attackRightAvg, rotation.attackRightStd],
  ] as const;
  // `?? []` y no confiar en el tipo: una respuesta vieja en caché del
  // navegador no trae el campo, y un panel roto es peor que uno vacío.
  const partidos = rotation.attackByMatch ?? [];
  // Escala común a los tres carriles: si cada fila tuviera la suya, un carril
  // flojo se vería igual de alto que el fuerte.
  const techo = Math.max(
    1,
    ...partidos.flatMap((p) => [p.left, p.central, p.right]),
  );

  if (partidos.length === 0) {
    return <Empty>Sin partidos con datos de sector.</Empty>;
  }

  return (
    <div className="space-y-1.5">
      {carriles.map(([etiqueta, clave, avg, std]) => (
        <div key={etiqueta} className="flex items-stretch gap-2">
          <div className="w-20 shrink-0 self-center text-[10px] uppercase text-[var(--muted)]">
            {etiqueta}
          </div>
          <div className="flex flex-1 items-end gap-1">
            {partidos.map((partido, i) => {
              const valor = partido[clave];
              const gana = partido.best === etiqueta;
              return (
                <div
                  key={i}
                  className="group relative flex flex-1 flex-col items-center justify-end"
                  title={`${partido.label}: ${valor} en ${etiqueta}${gana ? " (su mejor carril ese día)" : ""}`}
                >
                  <div
                    className="w-full rounded-sm"
                    style={{
                      height: `${Math.max(3, (valor / techo) * 34)}px`,
                      background: gana ? RIVAL_COLOR : "var(--surface-2)",
                      border: gana ? "none" : "1px solid var(--border)",
                    }}
                  />
                </div>
              );
            })}
          </div>
          <div className="w-24 shrink-0 self-center text-right">
            <span className="tabular-nums text-xs font-semibold">{avg.toFixed(0)}</span>
            <span className="ml-1 text-[10px] text-[var(--muted)]">± {std.toFixed(1)}</span>
          </div>
        </div>
      ))}
      <div className="flex gap-2 text-[10px] text-[var(--muted)]">
        <div className="w-20 shrink-0" />
        <div className="flex flex-1 justify-between">
          <span>más antiguo</span>
          <span>más reciente</span>
        </div>
        <div className="w-24 shrink-0 text-right">media ± desv.</div>
      </div>
    </div>
  );
}

const OWN_COLOR = "#4f7cff";
const RIVAL_COLOR = "#8b5cf6";

interface ComparisonMetric {
  label: string;
  own: number | null;
  rival: number | null;
  format?: (v: number) => string;
}

/** Barras espejadas "propio vs. rival": cada valor crece desde el centro
 * hacia su lado, así el ojo compara longitudes en vez de tener que leer dos
 * columnas de números sueltos. Cuando el rival no tiene dato (liderazgo del
 * entrenador — CHPP lo deniega para un equipo ajeno), el lado del rival se
 * pinta rayado en vez de fingir una barra con un cero. */
function ComparisonPanel({
  data,
  rivalLabel,
  ownLabel,
}: {
  data: RivalScouting;
  rivalLabel: string;
  ownLabel: string;
}) {
  const metrics: ComparisonMetric[] = [
    { label: "TSI", own: data.comparison.tsi.own, rival: data.comparison.tsi.rival, format: number },
    { label: "Forma", own: data.comparison.form.own, rival: data.comparison.form.rival },
    { label: "Condición", own: data.comparison.stamina.own, rival: data.comparison.stamina.rival },
    { label: "Experiencia", own: data.comparison.experience.own, rival: data.comparison.experience.rival },
  ];

  return (
    <Panel
      title={data.comparisonReference.ownSource === "submitted_orders"
        ? "Comparación para el partido"
        : "Comparación de plantilla"}
      meta={`${ownLabel} vs. ${rivalLabel}`}
    >
      <div className="space-y-5 p-4">
        <div className="flex items-center justify-center gap-6 text-xs">
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: OWN_COLOR }} />
            <span className="text-[var(--muted)]">{ownLabel}</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: RIVAL_COLOR }} />
            <span className="text-[var(--muted)]">{rivalLabel}</span>
          </span>
        </div>
        {metrics.map((m) => (
          <ComparisonRow key={m.label} {...m} />
        ))}
        <ComparisonRow
          label="Liderazgo del entrenador"
          own={data.comparison.trainerLeadership.own}
          rival={data.comparison.trainerLeadership.rival}
        />
        <LastConnectionRow
          ownDays={data.comparison.lastLoginDays.own}
          rivalDays={data.comparison.lastLoginDays.rival}
        />
        <LastPurchaseRow own={data.lastPurchase.own} rival={data.lastPurchase.rival} />
      </div>
    </Panel>
  );
}

/** Una temporada de Hattrick. Una compra más vieja que esto ya no dice nada
 *  del equipo que te vas a encontrar: el jugador lleva demasiado ahí. */
const PURCHASE_FRESH_DAYS = 112;

/**
 * El último fichaje de cada club, con la barra llena según lo reciente que sea.
 *
 * 2026-08-19, pedido explícito: comprado hoy la llena entera y va vaciándose
 * hasta que, pasada una temporada, no se muestra nada. La idea es que el
 * tamaño de la barra sea "cuánto me importa esto ahora": un fichaje de esta
 * semana cambia el partido, uno de hace cuatro meses ya es plantilla vieja.
 *
 * Dentro de la barra van el TSI del momento de la compra y el puesto en el que
 * se le ha visto jugar.
 */
function LastPurchaseRow({
  own,
  rival,
}: {
  own: LastPurchase | null;
  rival: LastPurchase | null;
}) {
  const reciente = (compra: LastPurchase | null) =>
    compra && compra.daysAgo != null && compra.daysAgo < PURCHASE_FRESH_DAYS
      ? compra
      : null;
  const mio = reciente(own);
  const suyo = reciente(rival);
  if (!mio && !suyo) return null;

  const ancho = (compra: LastPurchase | null) =>
    compra && compra.daysAgo != null
      ? Math.max(4, ((PURCHASE_FRESH_DAYS - compra.daysAgo) / PURCHASE_FRESH_DAYS) * 100)
      : 0;
  const dentro = (compra: LastPurchase | null) =>
    compra
      ? `${number(compra.tsi)}${compra.lastPosition ? ` · ${compra.lastPosition}` : ""}`
      : "";
  const pie = (compra: LastPurchase | null) =>
    compra
      ? `${compra.playerName} · hace ${compra.daysAgo} día(s)`
      : "sin fichajes esta temporada";

  return (
    <div>
      {/* La misma anatomía que las demás filas: los valores arriba, el
          rótulo en medio y una barra de 2,5 unidades de alto. Antes tenía el
          número DENTRO de la barra y por eso salía el triple de gruesa. */}
      {/* Rejilla de tres columnas iguales en vez de `justify-between`: los
          dos valores no miden lo mismo (uno lleva el puesto detrás) y con
          `justify-between` el rótulo se descolgaba del centro. */}
      <div className="mb-1.5 grid grid-cols-3 items-center text-xs">
        <span className="tabular-nums font-semibold text-[var(--text)]">
          {mio ? dentro(mio) : "-"}
        </span>
        <span className="text-center text-[var(--muted)]">Último fichaje</span>
        <span className="text-right tabular-nums font-semibold text-[var(--text)]">
          {suyo ? dentro(suyo) : "-"}
        </span>
      </div>
      <div className="flex h-2.5 items-center gap-1">
        <div className="flex h-2.5 flex-1 justify-end overflow-hidden rounded-l-full bg-[var(--surface-2)]">
          {mio && (
            <div
              className="h-full rounded-l-full transition-[width]"
              style={{ width: `${ancho(mio)}%`, background: OWN_COLOR }}
            />
          )}
        </div>
        <div className="h-4 w-px shrink-0 bg-[var(--border)]" />
        <div className="h-2.5 flex-1 overflow-hidden rounded-r-full bg-[var(--surface-2)]">
          {suyo && (
            <div
              className="h-full rounded-r-full transition-[width]"
              style={{ width: `${ancho(suyo)}%`, background: RIVAL_COLOR }}
            />
          )}
        </div>
      </div>
      <div className="mt-1 flex justify-between gap-3 text-[10px] text-[var(--muted)]">
        <span className="truncate">{pie(mio)}</span>
        <span className="truncate text-right">{pie(suyo)}</span>
      </div>
    </div>
  );
}

const LAST_CONNECTION_EMPTY_DAYS = 14;

function lastConnectionWidth(days: number | null): number {
  if (days == null) return 0;
  const bounded = Math.min(Math.max(days, 0), LAST_CONNECTION_EMPTY_DAYS);
  return ((LAST_CONNECTION_EMPTY_DAYS - bounded) / LAST_CONNECTION_EMPTY_DAYS) * 100;
}

function lastConnectionLabel(days: number | null): string {
  if (days == null) return "no disponible";
  if (days === 0) return "hoy";
  if (days === 1) return "hace 1 día";
  return `hace ${days} días`;
}

/** Actividad absoluta del manager: 0 días llena cada mitad; 14 o más la
 * vacía. No se normaliza contra el otro equipo, para que dos managers con
 * la misma antigüedad intermedia no aparezcan engañosamente al 100%. */
function LastConnectionRow({
  ownDays,
  rivalDays,
}: {
  ownDays: number | null;
  rivalDays: number | null;
}) {
  const ownPct = lastConnectionWidth(ownDays);
  const rivalPct = lastConnectionWidth(rivalDays);

  return (
    <div aria-label="Actividad reciente de los managers">
      <div className="mb-1.5 flex items-center justify-between text-xs">
        <span className="tabular-nums font-semibold text-[var(--text)]">
          {lastConnectionLabel(ownDays)}
        </span>
        <span className="text-[var(--muted)]">&Uacute;ltima conexi&oacute;n</span>
        <span className="tabular-nums font-semibold text-[var(--text)]">
          {lastConnectionLabel(rivalDays)}
        </span>
      </div>
      <div className="flex h-2.5 items-center gap-1">
        <div className="flex h-2.5 flex-1 justify-end overflow-hidden rounded-l-full bg-[var(--surface-2)]">
          {ownDays != null ? (
            <div
              className="h-full rounded-l-full transition-[width]"
              style={{ width: `${ownPct}%`, background: OWN_COLOR }}
            />
          ) : (
            <UnavailableBar />
          )}
        </div>
        <div className="h-4 w-px shrink-0 bg-[var(--border)]" />
        <div className="h-2.5 flex-1 overflow-hidden rounded-r-full bg-[var(--surface-2)]">
          {rivalDays != null ? (
            <div
              className="h-full rounded-r-full transition-[width]"
              style={{ width: `${rivalPct}%`, background: RIVAL_COLOR }}
            />
          ) : (
            <UnavailableBar />
          )}
        </div>
      </div>
    </div>
  );
}

function UnavailableBar() {
  return (
    <div
      className="h-full w-full opacity-40"
      style={{
        backgroundImage:
          "repeating-linear-gradient(135deg, var(--border) 0 4px, transparent 4px 8px)",
      }}
    />
  );
}

function ComparisonRow({ label, own, rival, format = (v: number) => v.toFixed(1) }: ComparisonMetric) {
  const max = Math.max(own ?? 0, rival ?? 0, 1);
  const ownPct = own != null ? Math.max((own / max) * 100, own > 0 ? 3 : 0) : 0;
  const rivalPct = rival != null ? Math.max((rival / max) * 100, rival > 0 ? 3 : 0) : 0;

  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between text-xs">
        <span className="tabular-nums font-semibold text-[var(--text)]">
          {own != null ? format(own) : "-"}
        </span>
        <span className="text-[var(--muted)]">{label}</span>
        <span className="tabular-nums font-semibold text-[var(--text)]">
          {rival != null ? format(rival) : "no disponible"}
        </span>
      </div>
      <div className="flex h-2.5 items-center gap-1">
        <div className="flex h-2.5 flex-1 justify-end overflow-hidden rounded-l-full bg-[var(--surface-2)]">
          <div
            className="h-full rounded-l-full transition-[width]"
            style={{ width: `${ownPct}%`, background: OWN_COLOR }}
          />
        </div>
        <div className="h-4 w-px shrink-0 bg-[var(--border)]" />
        <div className="h-2.5 flex-1 overflow-hidden rounded-r-full bg-[var(--surface-2)]">
          {rival != null ? (
            <div
              className="h-full rounded-r-full transition-[width]"
              style={{ width: `${rivalPct}%`, background: RIVAL_COLOR }}
            />
          ) : (
            <div
              className="h-full w-full opacity-40"
              style={{
                backgroundImage:
                  "repeating-linear-gradient(135deg, var(--border) 0 4px, transparent 4px 8px)",
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
}

// ── Duelos por zona de la cancha (cancha horizontal) ────────────────────────

const DUEL_ROW_LABEL: Record<"left" | "central" | "right", string> = {
  left: "Izquierda", central: "Centro", right: "Derecha",
};

/** Una celda del duelo: se reparte horizontalmente entre tu color y el del
 * rival según el % de cada uno — igual que un marcador de posesión, el
 * ancho de cada bloque ES el dato. */
function DuelCell({ duel, label, style }: { duel: PitchZoneDuel; label: string; style?: CSSProperties }) {
  const ownPct = Math.round(duel.ownPct * 100);
  const rivalPct = 100 - ownPct;
  return (
    <div
      className="flex flex-col overflow-hidden rounded border border-[var(--border)]"
      style={style}
    >
      <div className="bg-[var(--surface-2)] px-1 py-0.5 text-center text-[9px] uppercase text-[var(--muted)]">
        {label}
      </div>
      <div className="flex flex-1 text-white">
        {ownPct > 0 && (
          <div
            className="flex flex-col items-center justify-center px-0.5 py-1.5"
            style={{ width: `${ownPct}%`, background: OWN_COLOR }}
          >
            <span className="text-xs font-bold tabular-nums">{ownPct}%</span>
            <span className="text-[9px] tabular-nums opacity-80">({duel.ownValue.toFixed(1)})</span>
          </div>
        )}
        {rivalPct > 0 && (
          <div
            className="flex flex-col items-center justify-center px-0.5 py-1.5"
            style={{ width: `${rivalPct}%`, background: RIVAL_COLOR }}
          >
            <span className="text-xs font-bold tabular-nums">{rivalPct}%</span>
            <span className="text-[9px] tabular-nums opacity-80">({duel.rivalValue.toFixed(1)})</span>
          </div>
        )}
      </div>
    </div>
  );
}

/** Qué número representa cada zona. El promedio dice cómo juega de costumbre;
 *  el máximo, de lo que es capaz; el máximo de los tres carriles, de lo que es
 *  capaz por cualquiera de ellos (los tres salen iguales y altos a propósito);
 *  y el último partido, con lo que salió el último día. */
const PITCH_ZONE_METHODS: [PitchZoneMethod, string, string][] = [
  ["average", "Promedio", "el promedio de los partidos vistos, zona por zona"],
  ["max", "Máximo", "el mejor registro en cada zona, de todos los partidos vistos"],
  ["max_parallel", "Máximo por carril", "el mejor de los tres carriles paralelos, aplicado a los tres"],
  ["last", "Último partido", "lo del último día, sin promediar nada"],
];

/** Solo del lado propio: de un rival las órdenes son privadas hasta que se
 *  juega el partido, así que esta opción no existe para él. */
const SUBMITTED_METHOD: [PitchZoneMethod, string, string] = [
  "submitted",
  "Alineación enviada",
  "la predicción de minuto 0 que da Hattrick para las órdenes que ya mandaste",
];

function PitchZoneMethodSelector({
  method,
  onMethodChange,
  options = PITCH_ZONE_METHODS,
}: {
  method: PitchZoneMethod;
  onMethodChange: (v: PitchZoneMethod) => void;
  options?: [PitchZoneMethod, string, string][];
}) {
  return (
    <div className="mt-2 flex flex-wrap overflow-hidden rounded border border-[var(--border)] text-xs">
      {options.map(([clave, etiqueta, ayuda]) => (
        <button
          key={clave}
          title={ayuda}
          onClick={() => onMethodChange(clave)}
          className={`px-3 py-1 ${method === clave ? "bg-[var(--accent)] text-white" : "bg-[var(--surface)]"}`}
        >
          {etiqueta}
        </button>
      ))}
    </div>
  );
}

function PitchZoneDuelsPanel({
  duels,
  matchesAnalysed,
  sources,
  methodOwn,
  methodRival,
  onMethodOwnChange,
  onMethodRivalChange,
  submittedAvailable,
}: {
  duels: PitchZoneDuel[] | null;
  matchesAnalysed: { own: number | null; rival: number | null };
  sources: RivalScouting["pitchZoneSources"];
  methodOwn: PitchZoneMethod;
  methodRival: PitchZoneMethod;
  onMethodOwnChange: (v: PitchZoneMethod) => void;
  onMethodRivalChange: (v: PitchZoneMethod) => void;
  submittedAvailable: boolean;
}) {
  // Tu lado tiene una opción más: la predicción de las órdenes ya enviadas.
  // Se ofrece solo si de verdad hay órdenes mandadas.
  const opcionesPropias = submittedAvailable
    ? [SUBMITTED_METHOD, ...PITCH_ZONE_METHODS]
    : PITCH_ZONE_METHODS;
  if (!duels) {
    return (
      <Panel title="Duelos por zona de la cancha">
        <div className="p-4 pb-0">
          <PitchZoneMethodSelector
            method={methodRival}
            onMethodChange={onMethodRivalChange}
          />
        </div>
        <Empty>
          Falta alguno de los dos lados con partidos y datos de sector, sin eso no hay
          duelo honesto que mostrar.
        </Empty>
      </Panel>
    );
  }

  const byKey = new Map(duels.map((d) => [`${d.zone}-${d.half}`, d]));
  const ownHalf = (["left", "central", "right"] as const).map(
    (zone) => [zone, byKey.get(`${zone}-own`)!] as const,
  );
  const rivalHalf = (["left", "central", "right"] as const).map(
    (zone) => [zone, byKey.get(`${zone}-rival`)!] as const,
  );
  const midfield = byKey.get("midfield-midfield")!;

  return (
    <Panel
      title="Duelos por zona de la cancha"
      meta={`${sources.own.kind === "submitted_chpp_prediction"
        ? "la predicción de Hattrick"
        : `tú: ${matchesAnalysed.own} partido(s)`} · rival: ${matchesAnalysed.rival} partido(s)`}
    >
      <div className="grid gap-2 p-4 pb-2 sm:grid-cols-2">
        <div className="rounded border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2">
          <div className="text-[10px] uppercase text-[var(--muted)]">Tu fuente</div>
          <div className="text-xs font-semibold">{sources.own.label}</div>
          {sources.own.tacticSkill != null && (
            <div className="mt-0.5 text-[11px] text-[var(--muted)]">
              Táctica {sources.own.tacticType} · nivel {sources.own.tacticSkill}
            </div>
          )}
          <PitchZoneMethodSelector
            method={methodOwn}
            onMethodChange={onMethodOwnChange}
            options={opcionesPropias}
          />
        </div>
        <div className="rounded border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2">
          <div className="text-[10px] uppercase text-[var(--muted)]">Fuente rival</div>
          <div className="text-xs font-semibold">{sources.rival.label}</div>
          <div className="mt-0.5 text-[11px] text-[var(--muted)]">
            {sources.rival.observations ?? 0} partido(s) vistos
          </div>
          <PitchZoneMethodSelector
            method={methodRival}
            onMethodChange={onMethodRivalChange}
          />
        </div>
      </div>
      <div className="p-4 pt-0">
        <div className="mb-1.5 grid grid-cols-[1fr_0.7fr_1fr] gap-1.5 text-center text-[10px] uppercase text-[var(--muted)]">
          <div className="flex items-center justify-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ background: OWN_COLOR }} />
            Tu campo
          </div>
          <div>Medio</div>
          <div className="flex items-center justify-center gap-1.5">
            Campo rival
            <span className="h-2 w-2 rounded-full" style={{ background: RIVAL_COLOR }} />
          </div>
        </div>
        {/* El fondo va con el tema y no con un verde de cancha fijo: en modo
            día ese verde oscuro se leía como franjas negras entre las celdas.
            `--surface` es blanco de día y casi negro de noche, así que las
            separaciones desaparecen contra el panel en los dos modos. */}
        <div
          className="grid gap-1.5 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-2"
          style={{
            gridTemplateColumns: "1fr 0.7fr 1fr",
            gridTemplateRows: "repeat(3, minmax(52px, auto))",
          }}
        >
          {ownHalf.map(([zone, duel], i) => (
            <DuelCell
              key={`own-${zone}`}
              duel={duel}
              label={DUEL_ROW_LABEL[zone]}
              style={{ gridColumn: 1, gridRow: i + 1 }}
            />
          ))}
          <DuelCell
            duel={midfield}
            label="Medio campo"
            style={{ gridColumn: 2, gridRow: "1 / span 3" }}
          />
          {rivalHalf.map(([zone, duel], i) => (
            <DuelCell
              key={`rival-${zone}`}
              duel={duel}
              label={DUEL_ROW_LABEL[zone]}
              style={{ gridColumn: 3, gridRow: i + 1 }}
            />
          ))}
        </div>
      </div>
    </Panel>
  );
}
