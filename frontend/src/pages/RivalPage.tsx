import { useState } from "react";
import type { CSSProperties } from "react";
import { useParams, Link } from "react-router-dom";
import { Chart } from "../charts/Chart";
import { sharePieOption } from "../charts/chartOptions";
import { BarraDePrediccion } from "../components/BarraDePrediccion";
import { Column, DataTable } from "../components/DataTable";
import { PitchZoneMethodSelector } from "../components/PitchZoneMethodSelector";
import {
  PITCH_ZONE_METHODS,
  SUBMITTED_METHOD,
} from "../components/pitchZoneMethods";
import {
  Empty,
  ErrorState,
  Kpi,
  Loading,
  Note,
  Panel,
  ProjectionPanel,
} from "../components/Panels";
import { TsiHistogramPanel } from "../components/TsiHistogramPanel";
import { number } from "../hooks/useFormat";
import { useDashboard, useRivalScouting } from "../hooks/useTeam";
import type {
  LastPurchase,
  PartidoConMarcador,
  PitchZoneDuel,
  PitchZoneMethod,
  RivalScouting,
} from "../services/api";

import { tx } from "../i18n/tx";
interface RosterRow {
  name: string;
  position: string | null;
  tsi: number;
}

/**
 * Ficha de rival, HL-099 a HL-110, ampliado en HL-2xx. El gancho: comparar
 * tu plantilla contra la del próximo rival con las mismas herramientas que
 * usas para la tuya.
 *
 * Todo lo del rival se pide en vivo cada vez que se abre la ficha, sin
 * guardarse. El roster, marcaje, táctica y rotación se basan en los
 * ÚLTIMOS PARTIDOS OFICIALES REALES del rival contra CUALQUIER equipo, no
 * solo los que jugó contra ti, porque muchos rivales nunca se han
 * enfrentado a tu equipo todavía. Duelos y Escaleras nunca cuentan para
 * nada de esto, sin importar los toggles: no se consideran representativos
 * de cómo juega el rival normalmente.
 */
/** Cómo se llama cada resumen cuando hay que nombrarlo en una frase. Vive
 *  junto a la página y no dentro del selector porque el pronóstico también lo
 *  usa, para decir de dónde salieron sus números. */
const ETIQUETA_DE_METODO: Record<string, string> = {
  average: tx("promedio"),
  max: tx("máximo"),
  max_parallel: tx("máximo por carril"),
  last: tx("último partido"),
  submitted: tx("alineación enviada"),
};

export function RivalPage() {
  const { rivalHtTeamId } = useParams<{ rivalHtTeamId: string }>();
  const id = Number(rivalHtTeamId);
  const [logTsi, setLogTsi] = useState(false);
  const [top11, setTop11] = useState(false);
  // UNO U OTRO, NUNCA LOS DOS NI NINGUNO (2026-09-09, pedido del usuario).
  // Un solo estado con dos valores en vez de dos booleanos sueltos: así el
  // estado imposible --ambos apagados, o ambos encendidos-- no se puede ni
  // representar, no es que se corrija después. Abre en oficiales.
  const [clase, setClase] = useState<"oficiales" | "amistosos">("oficiales");
  const includeCompetitive = clase === "oficiales";
  const includeFriendlies = clase === "amistosos";
  const [methodOwn, setMethodOwn] = useState<PitchZoneMethod>("submitted");
  const [methodRival, setMethodRival] = useState<PitchZoneMethod>("average");
  const { data, isLoading, isError, error } = useRivalScouting(
    id,
    logTsi,
    top11,
    includeCompetitive,
    includeFriendlies,
    methodOwn,
    methodRival,
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
          <b>{tx("Estudiando al rival…")}</b>{" "}
          <span className="text-[var(--muted)]">
            {tx(
              "Se le está pidiendo a Hattrick su plantilla y sus últimos partidos. Suele tardar unos segundos: no son datos que estén guardados aquí.",
            )}
          </span>
        </div>
        <Loading />
      </div>
    );
  }
  if (isError) return <ErrorState error={error} />;
  if (!data) return <Empty>{tx("Rival no encontrado.")}</Empty>;

  // Un identificador que no corresponde a ningún equipo devolvía un informe
  // ENTERO: nombre «Rival», cero partidos, TSI vacío y una proyección del
  // 100% de victoria --contra nadie--. Quien se equivoca escribiendo un ID en
  // «Ir directo por ID de equipo» recibía un análisis con pinta de real
  // (2026-08-31). Sin nombre y sin plantilla no hay rival que estudiar.
  //
  // LO QUE MIDE «no existe» ES LA PLANTILLA, no los partidos. Antes esto
  // mismo miraba `rivalRosterSample`, que se construye de las alineaciones de
  // los partidos ANALIZADOS: dejando sólo «Amistosos» marcado, un rival que
  // no ha jugado ninguno se quedaba con la lista vacía y esta pantalla
  // anunciaba que el equipo no existía --sobre un equipo con 22 jugadores
  // delante (2026-09-09)--. La plantilla se pide siempre y sin filtrar, así
  // que es lo único que de verdad contesta «¿existe este equipo?».
  if (!data.rivalName || (data.tsiHistogram?.rivalValues?.length ?? 0) === 0) {
    return (
      <div className="space-y-4">
        <header>
          <h1 className="text-xl font-semibold">{tx("Rival no encontrado")}</h1>
          <p className="text-sm text-[var(--muted)]">
            {tx("Hattrick no devolvió ningún equipo con el identificador")} {id}
            .
          </p>
        </header>
        <Panel title={tx("Qué pudo pasar")}>
          <ul className="list-disc space-y-1.5 p-4 pl-8 text-sm text-[var(--muted)]">
            <li>{tx("El identificador está mal escrito.")}</li>
            <li>
              {tx("El equipo ya no existe: se disolvió o cambió de manager.")}
            </li>
            <li>
              {tx("Si lo buscabas por el nombre, es más seguro elegirlo en")}{" "}
              <Link
                to="/rivals"
                className="text-[var(--accent)] hover:underline"
              >
                {tx("la lista de rivales")}
              </Link>
              {tx(", que sólo ofrece equipos que existen.")}
            </li>
          </ul>
        </Panel>
      </div>
    );
  }

  const h = data.tsiHistogram;
  const rivalLabel = data.rivalName ?? "Rival";
  const ownLabel = dashboard.data?.teamName ?? "tu equipo";

  // TSI medio SIEMPRE lineal, a diferencia de tsiHistogram.ownValues/rivalValues,
  // que se transforman a log(TSI+1) cuando el toggle Log(TSI+1) está activo.
  // Este KPI no debe moverse al tocar ese toggle.
  const ownTsiAvg = data.comparison.tsi.own;
  const rivalTsiAvg = data.comparison.tsi.rival;
  const tsiRatio =
    ownTsiAvg && rivalTsiAvg != null && ownTsiAvg > 0
      ? rivalTsiAvg / ownTsiAvg
      : null;

  // CÓMO SE LLAMAN LOS PARTIDOS QUE SE ESTÁN MIRANDO. La pantalla decía
  // «oficiales» siempre, incluso con el toggle de oficiales apagado y sólo
  // amistosos marcados (lo vio el usuario el 2026-09-09). El adjetivo sale de
  // lo que hay marcado arriba, que es lo único que decide qué entra.
  //
  // Dos formas, porque acompaña a dos plantillas distintas: «6 partido(s)…»
  // admite el «(es)», y «sus últimos partidos…» ya es plural y con el «(es)»
  // quedaba «partidos oficial(es)».
  //
  // Desde que el selector es excluyente siempre hay adjetivo: ya no existe la
  // mezcla, que era el único caso sin nombre honesto.
  // QUÉ CLASES PUEDE OFRECER ESTA FICHA (2026-09-09, pedido del usuario: «si
  // sólo tiene Oficiales, desactivar el botón de Amistosos de entrada»). Lo
  // dice el servidor, que es quien sabe qué se pidió y qué vino.
  //
  // Y si la clase elegida resulta no estar, se salta a la que sí: dejar el
  // botón marcado sobre una ficha vacía parece un fallo de la aplicación.
  //
  // Con guarda: una respuesta vieja --de una versión anterior del servidor, o
  // servida desde la caché del navegador-- no trae este campo, y leerlo a pelo
  // tumbaba la ficha entera con «Cannot read properties of undefined». Sin
  // dato, se ofrecen los dos botones: es lo que hacía antes de existir esto.
  const hayOficiales = data.clasesDisponibles?.competitive ?? true;
  const hayAmistosos = data.clasesDisponibles?.friendly ?? true;
  if (clase === "amistosos" && !hayAmistosos && hayOficiales) {
    setClase("oficiales");
  } else if (clase === "oficiales" && !hayOficiales && hayAmistosos) {
    setClase("amistosos");
  }

  const claseDePartidos = includeCompetitive
    ? tx(" oficial(es)")
    : tx(" amistoso(s)");
  const claseDePartidosPlural = includeCompetitive
    ? tx(" oficiales")
    : tx(" amistosos");

  const rosterColumns: Column<RosterRow>[] = [
    { key: "name", header: tx("Jugador"), align: "left", value: (r) => r.name },
    {
      key: "position",
      header: tx("Posición"),
      value: (r) => r.position ?? "",
      render: (r) =>
        r.position ? (
          r.position
        ) : (
          <span className="text-[var(--muted)]">-</span>
        ),
    },
    {
      key: "tsi",
      header: "TSI",
      align: "right",
      value: (r) => r.tsi,
      render: (r) => <span className="tabular-nums">{number(r.tsi)}</span>,
    },
  ];

  return (
    <div className="space-y-4">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">
            {dashboard.data?.teamName ?? tx("Tu equipo")}{" "}
            <span className="text-[var(--muted)]">{tx("vs.")}</span>{" "}
            {rivalLabel}
          </h1>
          <p className="text-sm text-[var(--muted)]">
            {data.matchesAnalysed > 0
              ? tx(
                  "{{v0}} partido(s){{v1}} reciente(s) del rival analizado(s)",
                  { v0: data.matchesAnalysed, v1: claseDePartidos },
                )
              : // Y se dice qué se cae con eso. Sin esta segunda mitad, media
                // pantalla aparece vacía y parece que falla algo: su plantilla
                // y su TSI siguen ahí, lo que no hay es de dónde sacar cómo
                // juega.
                // Y se nombra la clase que falta: quien marca sólo Amistosos
                // y no ve nada quiere saber si falla la aplicación o si ese
                // equipo no juega amistosos (2026-09-09, lo preguntó el
                // usuario sobre un rival que de verdad no tiene ninguno).
                tx(
                  "este rival no ha jugado partidos{{v0}} recientemente: su plantilla y su TSI siguen siendo suyos, pero once probable, marcaje, táctica, rotación, duelos y pronóstico se quedan vacíos",
                  { v0: claseDePartidosPlural },
                )}
          </p>
        </div>
        {/* Un selector, no dos casillas: van pegados y en un marco común
            para que se lean como dos posiciones de la misma palanca. Volver a
            pulsar el que ya está activo no hace nada --no se puede apagar--,
            y `aria-pressed` cuenta lo mismo a quien no ve el color. */}
        <div
          role="group"
          aria-label={tx("Qué partidos del rival se miran")}
          className="flex shrink-0 overflow-hidden rounded-md border border-[var(--border)]"
        >
          {(
            [
              ["oficiales", "Liga/Copa/Promoción", hayOficiales],
              ["amistosos", "Amistosos", hayAmistosos],
            ] as const
          ).map(([valor, etiqueta, disponible]) => (
            <button
              key={valor}
              type="button"
              onClick={() => setClase(valor)}
              disabled={!disponible}
              aria-pressed={clase === valor}
              title={
                disponible
                  ? undefined
                  : valor === "amistosos"
                    ? tx(
                        "Este rival no tiene amistosos en la muestra que se mira",
                      )
                    : tx(
                        "Este rival no tiene partidos oficiales en la muestra que se mira",
                      )
              }
              className={`px-3 py-1.5 text-xs ${
                clase === valor
                  ? "bg-[var(--accent)] font-medium text-white"
                  : disponible
                    ? "bg-[var(--surface)] text-[var(--muted)] hover:text-[var(--text)]"
                    : "cursor-not-allowed bg-[var(--surface)] text-[var(--muted)] opacity-40"
              }`}
            >
              {etiqueta}
            </button>
          ))}
        </div>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 [&>*]:min-w-0">
        <Kpi
          label={tx("Partidos analizados")}
          value={String(data.matchesAnalysed)}
          hint={
            data.matchesByCompetition.length > 0
              ? data.matchesByCompetition
                  .map((c) => tx("{{v0}} de {{v1}}", { v0: c.count, v1: c.label }))
                  .join(" · ")
              : undefined
          }
        />
        <Kpi
          label={tx("TSI medio del rival")}
          value={rivalTsiAvg != null ? number(rivalTsiAvg) : "-"}
          hint={
            tsiRatio != null
              ? tx("{{v0}}x el TSI de {{v1}}", {
                  v0: tsiRatio.toFixed(2),
                  v1: ownLabel,
                })
              : undefined
          }
        />
      </div>

      <ComparisonPanel
        data={data}
        rivalLabel={rivalLabel}
        ownLabel={ownLabel}
      />

      <TsiHistogramPanel
        title={tx("TSI: tu plantilla vs. el rival")}
        rivalLabel={rivalLabel}
        histogram={h}
        logTsi={logTsi}
        onLogTsiChange={setLogTsi}
        top11={top11}
        onTop11Change={setTop11}
        noteSuffix={
          tx("del rival") +
          (top11
            ? tx(", tu once real (motor de posiciones) contra los 11 de mayor TSI del rival")
            : "") +
          tx(". El TSI del rival es un dato público real; sus habilidades exactas están ocultas por Hattrick")
        }
      />

      <div className="grid gap-4 lg:grid-cols-2 [&>*]:min-w-0">
        <Panel title={tx("Sugerencia de marcaje al hombre")}>
          {data.manMarking ? (
            <div className="space-y-2 p-4">
              <p className="text-sm">{data.manMarking.rationale}</p>
              <div className="flex flex-wrap items-center gap-6 text-xs text-[var(--muted)]">
                <span>
                  {tx("Objetivo:")}{" "}
                  <b className="text-[var(--text)]">
                    {data.manMarking.targetName}
                  </b>{" "}
                  ({data.manMarking.targetPosition})
                </span>
                <span>
                  {tx("Marcador:")}{" "}
                  <b className="text-[var(--text)]">
                    {data.manMarking.markerName}
                  </b>{" "}
                  ({data.manMarking.markerPosition})
                </span>
                <span
                  className={`rounded px-2 py-0.5 text-[11px] font-semibold ${
                    data.manMarking.efficiency === "cerca"
                      ? "bg-[var(--positive)]/15 text-[var(--positive)]"
                      : "bg-[var(--warning)]/15 text-[var(--warning)]"
                  }`}
                >
                  {data.manMarking.efficiency === "cerca"
                    ? tx("Combinación óptima")
                    : tx("Combinación lejos")}{" "}
                  (-{(data.manMarking.markerLossPct * 100).toFixed(0)}%)
                </span>
              </div>
              <p className="text-xs text-[var(--muted)]">
                {tx("Confianza:")} {data.manMarking.confidence}
                {tx(". Solo compensa si el objetivo es una amenaza clara.")}
              </p>
              <p className="text-xs text-[var(--muted)]">
                {data.manMarking.riskNote}
              </p>
            </div>
          ) : (
            <Empty>
              {tx(
                "Sin datos suficientes: ningún jugador rival marcable (delantero, extremo o mediocentro) apareció en los partidos vistos con posición conocida, o no tienes un jugador propio elegible para marcarlo.",
              )}
            </Empty>
          )}
        </Panel>

        <Panel title={tx("Rotación del ataque")}>
          {data.sideRotation ? (
            <div className="space-y-3 p-4">
              <AttackLanes rotation={data.sideRotation} />
              <p className="text-xs text-[var(--muted)]">
                {data.sideRotation.dominantPct === 100
                  ? tx(
                      "Lado fuerte fijo, sin excepción: la {{v0}} fue el carril más fuerte en los {{v1}} de {{v2}} partidos vistos.",
                      {
                        v0: data.sideRotation.strongSide,
                        v1: data.sideRotation.matchesAnalysed,
                        v2: data.sideRotation.matchesAnalysed,
                      },
                    )
                  : data.sideRotation.rotates
                    ? tx(
                        "Rota: ningún lado domina de forma consistente, el más fuerte cambió partido a partido en sus últimos {{v0}} partido(s){{v1}}.",
                        {
                          v0: data.sideRotation.matchesAnalysed,
                          v1: claseDePartidos,
                        },
                      )
                    : tx(
                        "Lado fuerte habitual: la {{v0}} fue el carril más fuerte en el {{v1}}% de sus últimos {{v2}} partido(s), con variación partido a partido, no siempre por el mismo margen.",
                        {
                          v0: data.sideRotation.strongSide,
                          v1: data.sideRotation.dominantPct.toFixed(0),
                          v2: data.sideRotation.matchesAnalysed,
                        },
                      )}
              </p>
            </div>
          ) : (
            <Empty>
              {tx("Sin partidos")}
              {claseDePartidosPlural}{" "}
              {tx("recientes del rival con datos de sector.")}
            </Empty>
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
        ownTeamName={data.ownTeamName}
        rivalTeamName={data.rivalName}
        ultimoPropio={data.ultimoPartidoPropio}
        ultimoRival={data.ultimoPartidoRival}
      />

      {/* EL PRONÓSTICO VA DEBAJO DEL MAPA, y no arriba del todo como estuvo
          hasta el 2026-09-09. Los dos comen de los mismos dos selectores
          --«Tu fuente» y «Fuente rival»-- así que ponerlos separados dejaba a
          quien tocaba un botón sin ver que el otro panel también se movía. */}
      <ProjectionPanel
        title={
          data.prediction
            ? tx("Pronóstico contra {{v0}}", { v0: data.rivalName })
            : tx("Proyección de victoria por TSI")
        }
        meta={
          data.prediction
            ? tx("{{v0}} contra {{v1}}", {
                v0:
                  ETIQUETA_DE_METODO[data.prediction.metodoPropio] ??
                  data.prediction.metodoPropio,
                v1:
                  ETIQUETA_DE_METODO[data.prediction.metodoRival] ??
                  data.prediction.metodoRival,
              })
            : tx("modelo simple por TSI, no calibrado")
        }
      >
        {data.prediction ? (
          <div className="space-y-3 p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
              <span>
                <span className="font-medium">{tx("Tu equipo")}</span>
                <span className="mx-2 text-[var(--muted)]">{tx("vs")}</span>
                <span>{data.rivalName}</span>
              </span>
              <span className="text-xs text-[var(--muted)]">
                {tx("goles esperados")} {data.prediction.expectedOwnGoals} –{" "}
                {data.prediction.expectedRivalGoals}{" "}
                {tx("· resultado más probable")}{" "}
                {data.prediction.mostLikelyScore}
              </span>
            </div>
            <BarraDePrediccion
              tuLabel={tx("Tu equipo")}
              tuValor={data.prediction.ownProbability}
              rivalLabel={data.rivalName}
              rivalValor={data.prediction.rivalProbability}
              empate={data.prediction.drawProbability ?? undefined}
            />
            {/* 2026-09-13, pedido del usuario: fuera la frase de «sale de los
                mismos partidos… no sabe de bajas» y el aviso de las acciones
                indirectas con alineación enviada. Queda sólo lo que cambia
                cómo se lee la barra: un partido sin cruce es hipotético, y en
                Copa no hay empate. */}
            {(data.prediction.esCopa || !data.prediction.hayCruce) && (
              <p className="prosa text-xs leading-relaxed text-[var(--muted)]">
                {!data.prediction.hayCruce
                  ? tx(
                      "No tenéis ningún cruce pendiente: es un partido hipotético.",
                    )
                  : tx(
                      "En Copa alguien tiene que pasar: el empate se reparte entre los dos.",
                    )}
              </p>
            )}
          </div>
        ) : (
          <div className="p-4">
            <div className="flex items-center gap-4">
              <div className="text-3xl font-semibold tabular-nums text-[var(--accent)]">
                {(data.winProbability.ownProbability * 100).toFixed(0)}%
              </div>
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-[var(--surface-2)]">
                <div
                  className="h-full bg-[var(--accent)]"
                  style={{
                    width: `${data.winProbability.ownProbability * 100}%`,
                  }}
                />
              </div>
            </div>
            <Note>
              {tx(
                "Con lo que hay marcado arriba no salen los nueve duelos que el modelo necesita, así que esto es el modelo por TSI.",
              )}{" "}
              {data.comparisonReference.ownSource === "submitted_orders"
                ? tx("Tu alineación enviada")
                : tx("Tus 11 probables")}{" "}
              ({number(data.winProbability.ownTsiTotal)} {tx("TSI) contra")}{" "}
              {data.comparisonReference.rivalSource ===
              "probable_recent_starters"
                ? tx("el once probable del rival")
                : tx("los 11 de mayor TSI del rival")}{" "}
              ({number(data.winProbability.rivalTsiTotal)}).
            </Note>
          </div>
        )}
      </ProjectionPanel>

      {data.tacticHistory && (
        <Panel
          title={tx("Táctica habitual del rival")}
          meta={tx("{{v0}} partido(s) con datos de sector", {
            v0: data.tacticHistory.matchesAnalysed,
          })}
        >
          <div className="grid gap-4 p-4 sm:grid-cols-2 [&>*]:min-w-0">
            <div>
              <Chart
                ariaLabel={tx(
                  "Reparto de las tácticas que ha usado el rival en los partidos vistos",
                )}
                height={Math.max(200, data.tacticHistory.tactics.length * 30)}
                option={sharePieOption(
                  data.tacticHistory.tactics.map((t) => ({
                    name: t.label,
                    value: t.count,
                  })),
                )}
              />
            </div>
            <div className="space-y-3">
              {data.tacticHistory.mostCommonTactic && (
                <div>
                  <div className="text-xs text-[var(--muted)]">
                    {tx("Táctica más usada")}
                  </div>
                  <div className="text-lg font-semibold">
                    {data.tacticHistory.mostCommonTactic.label}{" "}
                    <span className="text-sm font-normal text-[var(--muted)]">
                      ({data.tacticHistory.mostCommonTactic.count} {tx("de")}{" "}
                      {data.tacticHistory.matchesAnalysed} ·{" "}
                      {data.tacticHistory.mostCommonTactic.pct.toFixed(0)}%)
                    </span>
                  </div>
                </div>
              )}
              {data.tacticHistory.avgTacticSkill != null && (
                <div>
                  <div className="text-xs text-[var(--muted)]">
                    {tx("Nivel medio de táctica")}
                  </div>
                  <div className="text-lg font-semibold tabular-nums">
                    {data.tacticHistory.avgTacticSkill.toFixed(1)}
                  </div>
                </div>
              )}
              {data.tacticHistory.mostCommonFormation && (
                <div>
                  <div className="text-xs text-[var(--muted)]">
                    {tx("Formación más usada")}
                  </div>
                  <div className="text-lg font-semibold">
                    {data.tacticHistory.mostCommonFormation.formation}{" "}
                    <span className="text-sm font-normal text-[var(--muted)]">
                      ({data.tacticHistory.mostCommonFormation.count} {tx("de")}{" "}
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
        title={tx("Jugadores del rival identificados")}
        meta={tx(
          "top 5 por TSI, de sus últimos partidos{{v0}}, sea contra quien sea",
          { v0: claseDePartidosPlural },
        )}
      >
        {data.rivalRosterSample.length === 0 ? (
          <Empty>
            {tx(
              "Aún no se ha visto a ningún jugador de este equipo en un partido jugado.",
            )}
          </Empty>
        ) : (
          <DataTable
            rows={data.rivalRosterSample}
            columns={rosterColumns}
            rowKey={(r) => r.name}
            initialSort="tsi"
            csvName={`${rivalLabel}-jugadores`}
            emptyMessage={tx("Sin jugadores identificados.")}
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
function AttackLanes({
  rotation,
}: {
  rotation: NonNullable<RivalScouting["sideRotation"]>;
}) {
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
    return <Empty>{tx("Sin partidos con datos de sector.")}</Empty>;
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
                  title={tx("{{v0}}: {{v1}} en {{v2}}{{v3}}", {
                    v0: partido.label,
                    v1: valor,
                    v2: etiqueta,
                    v3: gana ? " (su mejor carril ese día)" : "",
                  })}
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
            <span className="tabular-nums text-xs font-semibold">
              {avg.toFixed(0)}
            </span>
            <span className="ml-1 text-[10px] text-[var(--muted)]">
              ± {std.toFixed(1)}
            </span>
          </div>
        </div>
      ))}
      <div className="flex gap-2 text-[10px] text-[var(--muted)]">
        <div className="w-20 shrink-0" />
        <div className="flex flex-1 justify-between">
          <span>{tx("más antiguo")}</span>
          <span>{tx("más reciente")}</span>
        </div>
        <div className="w-24 shrink-0 text-right">{tx("media ± desv.")}</div>
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
 * entrenador, CHPP lo deniega para un equipo ajeno), el lado del rival se
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
    {
      label: "TSI",
      own: data.comparison.tsi.own,
      rival: data.comparison.tsi.rival,
      format: number,
    },
    {
      label: tx("Forma"),
      own: data.comparison.form.own,
      rival: data.comparison.form.rival,
    },
    {
      label: tx("Resistencia"),
      own: data.comparison.stamina.own,
      rival: data.comparison.stamina.rival,
    },
    {
      label: tx("Experiencia"),
      own: data.comparison.experience.own,
      rival: data.comparison.experience.rival,
    },
  ];

  return (
    <Panel
      title={
        data.comparisonReference.ownSource === "submitted_orders"
          ? tx("Comparación para el partido")
          : tx("Comparación de plantilla")
      }
      meta={tx("{{v0}} vs. {{v1}}", { v0: ownLabel, v1: rivalLabel })}
    >
      <div className="space-y-5 p-4">
        <div className="flex items-center justify-center gap-6 text-xs">
          <span className="flex items-center gap-1.5">
            <span
              className="h-2.5 w-2.5 rounded-full"
              style={{ background: OWN_COLOR }}
            />
            <span className="text-[var(--muted)]">{ownLabel}</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span
              className="h-2.5 w-2.5 rounded-full"
              style={{ background: RIVAL_COLOR }}
            />
            <span className="text-[var(--muted)]">{rivalLabel}</span>
          </span>
        </div>
        {metrics.map((m) => (
          <ComparisonRow key={m.label} {...m} />
        ))}
        <ComparisonRow
          label={tx("Liderazgo del entrenador")}
          own={data.comparison.trainerLeadership.own}
          rival={data.comparison.trainerLeadership.rival}
        />
        <LastConnectionRow
          ownDays={data.comparison.lastLoginDays.own}
          rivalDays={data.comparison.lastLoginDays.rival}
        />
        <LastPurchaseRow
          own={data.lastPurchase.own}
          rival={data.lastPurchase.rival}
        />
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
      ? Math.max(
          4,
          ((PURCHASE_FRESH_DAYS - compra.daysAgo) / PURCHASE_FRESH_DAYS) * 100,
        )
      : 0;
  const dentro = (compra: LastPurchase | null) =>
    compra
      ? `${number(compra.tsi)}${compra.lastPosition ? ` · ${compra.lastPosition}` : ""}`
      : "";
  const pie = (compra: LastPurchase | null) =>
    compra
      ? tx("{{v0}} · hace {{v1}} día(s)", { v0: compra.playerName, v1: compra.daysAgo })
      : tx("sin fichajes esta temporada");

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
        <span className="text-center text-[var(--muted)]">
          {tx("Último fichaje")}
        </span>
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
  return (
    ((LAST_CONNECTION_EMPTY_DAYS - bounded) / LAST_CONNECTION_EMPTY_DAYS) * 100
  );
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
    <div aria-label={tx("Actividad reciente de los managers")}>
      <div className="mb-1.5 flex items-center justify-between text-xs">
        <span className="tabular-nums font-semibold text-[var(--text)]">
          {lastConnectionLabel(ownDays)}
        </span>
        <span className="text-[var(--muted)]">
          &Uacute;ltima conexi&oacute;n
        </span>
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

function ComparisonRow({
  label,
  own,
  rival,
  format = (v: number) => v.toFixed(1),
}: ComparisonMetric) {
  const max = Math.max(own ?? 0, rival ?? 0, 1);
  const ownPct = own != null ? Math.max((own / max) * 100, own > 0 ? 3 : 0) : 0;
  const rivalPct =
    rival != null ? Math.max((rival / max) * 100, rival > 0 ? 3 : 0) : 0;

  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between text-xs">
        <span className="tabular-nums font-semibold text-[var(--text)]">
          {own != null ? format(own) : "-"}
        </span>
        <span className="text-[var(--muted)]">{label}</span>
        <span className="tabular-nums font-semibold text-[var(--text)]">
          {rival != null ? format(rival) : tx("no disponible")}
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
  left: "Izquierda",
  central: "Centro",
  right: "Derecha",
};

/** Una celda del duelo: se reparte horizontalmente entre tu color y el del
 * rival según el % de cada uno, igual que un marcador de posesión, el
 * ancho de cada bloque ES el dato. */
function DuelCell({
  duel,
  label,
  style,
}: {
  duel: PitchZoneDuel;
  label: string;
  style?: CSSProperties;
}) {
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
            <span className="text-[9px] tabular-nums opacity-80">
              ({duel.ownValue.toFixed(1)})
            </span>
          </div>
        )}
        {rivalPct > 0 && (
          <div
            className="flex flex-col items-center justify-center px-0.5 py-1.5"
            style={{ width: `${rivalPct}%`, background: RIVAL_COLOR }}
          >
            <span className="text-xs font-bold tabular-nums">{rivalPct}%</span>
            <span className="text-[9px] tabular-nums opacity-80">
              ({duel.rivalValue.toFixed(1)})
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

/** Qué es exactamente lo que se está mirando, cuando el resumen elegido se
 *  refiere a UN partido concreto o a una alineación concreta.
 *
 *  2026-09-09, pedido del usuario: «cuando dé clic en Alineación Enviada, que
 *  me diga algo (si ya fue enviada o algo); cuando dé clic en Último partido
 *  que muestre cuál fue ese partido».
 *
 *  Los otros tres resúmenes no dicen nada aquí a propósito: «promedio de
 *  cinco partidos» no tiene un partido que nombrar, y rellenar el hueco con
 *  una frase por cumplir sólo añadiría ruido bajo cada botón.
 */
function DeQuePartidoHablamos({
  metodo,
  partido,
  alineacionEnviada,
}: {
  metodo: PitchZoneMethod;
  partido: PartidoConMarcador | null;
  alineacionEnviada?: boolean;
}) {
  if (metodo === "submitted") {
    // Con órdenes mandadas no se dice nada más: la línea del selector ya lo
    // cuenta, y repetirlo debajo con otras palabras eran dos frases para una
    // idea (2026-09-13).
    if (alineacionEnviada) return null;
    return (
      <p className="mt-1.5 text-[11px] leading-relaxed text-[var(--muted)]">
        {tx(
          "Todavía no has mandado alineación, así que esto cae a tu resumen de lo ya jugado.",
        )}
      </p>
    );
  }
  if (metodo !== "last") return null;
  if (!partido) {
    return (
      <p className="mt-1.5 text-[11px] text-[var(--muted)]">
        {tx("No hay ningún partido en la muestra.")}
      </p>
    );
  }
  return (
    <p className="mt-1.5 text-[11px] leading-relaxed text-[var(--muted)]">
      {partido.homeName}{" "}
      <b className="tabular-nums text-[var(--text)]">
        {partido.homeGoals} - {partido.awayGoals}
      </b>{" "}
      {partido.awayName}
      {partido.competition ? ` · ${partido.competition}` : ""}
    </p>
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
  ownTeamName,
  rivalTeamName,
  ultimoPropio,
  ultimoRival,
}: {
  duels: PitchZoneDuel[] | null;
  matchesAnalysed: { own: number | null; rival: number | null };
  sources: RivalScouting["pitchZoneSources"];
  methodOwn: PitchZoneMethod;
  methodRival: PitchZoneMethod;
  onMethodOwnChange: (v: PitchZoneMethod) => void;
  onMethodRivalChange: (v: PitchZoneMethod) => void;
  submittedAvailable: boolean;
  ownTeamName: string;
  rivalTeamName: string;
  ultimoPropio: PartidoConMarcador | null;
  ultimoRival: PartidoConMarcador | null;
}) {
  // Tu lado tiene una opción más: la predicción de las órdenes ya enviadas.
  // Se ofrece solo si de verdad hay órdenes mandadas.
  const opcionesPropias = submittedAvailable
    ? [SUBMITTED_METHOD, ...PITCH_ZONE_METHODS]
    : PITCH_ZONE_METHODS;
  if (!duels) {
    return (
      <Panel title={tx("Duelos por zona de la cancha")}>
        <div className="p-4 pb-0">
          <PitchZoneMethodSelector
            method={methodRival}
            onMethodChange={onMethodRivalChange}
          />
        </div>
        <Empty>
          {tx(
            "Falta alguno de los dos lados con partidos y datos de sector, sin eso no hay duelo honesto que mostrar.",
          )}
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
      title={tx("Duelos por zona de la cancha")}
      meta={tx("{{v0}} · rival: {{v1}} partido(s)", {
        v0:
          sources.own.kind === "submitted_chpp_prediction"
            ? tx("la predicción de Hattrick")
            : tx("tú: {{v0}} partido(s)", { v0: matchesAnalysed.own }),
        v1: matchesAnalysed.rival,
      })}
    >
      <div className="grid gap-2 p-4 pb-2 sm:grid-cols-2">
        <div className="rounded border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2">
          {/* EL NOMBRE DEL EQUIPO, no «Tu fuente» (2026-09-09, pedido del
              usuario). Los dos paneles se leen de un vistazo como «X contra
              Y», que es lo que de verdad se está comparando. */}
          <div className="text-[10px] uppercase text-[var(--muted)]">
            {ownTeamName}
          </div>
          <div className="text-xs font-semibold">{sources.own.label}</div>
          {/* Con la alineación enviada NO hay táctica leída: Hattrick prevé
              los ratings de unas órdenes, no la táctica con la que se van a
              jugar. Salía «Táctica 0 · nivel 0», que es un doble cero que
              parece un dato y no lo es (lo vio el usuario, 2026-09-09). */}
          {methodOwn !== "submitted" && sources.own.tacticSkill != null && (
            <div className="mt-0.5 text-[11px] text-[var(--muted)]">
              {tx("Táctica")} {sources.own.tacticType} {tx("· nivel")}{" "}
              {sources.own.tacticSkill}
            </div>
          )}
          {/* Lo mismo que dice el lado del rival (2026-09-13). Con la
              alineación enviada no hay partidos que contar: es una sola
              previsión de Hattrick. */}
          {methodOwn !== "submitted" && (
            <div className="mt-0.5 text-[11px] text-[var(--muted)]">
              {sources.own.observations ?? 0} {tx("partido(s) vistos")}
            </div>
          )}
          <PitchZoneMethodSelector
            method={methodOwn}
            onMethodChange={onMethodOwnChange}
            options={opcionesPropias}
          />
          <DeQuePartidoHablamos
            metodo={methodOwn}
            partido={ultimoPropio}
            alineacionEnviada={submittedAvailable}
          />
        </div>
        <div className="rounded border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2">
          <div className="text-[10px] uppercase text-[var(--muted)]">
            {rivalTeamName}
          </div>
          <div className="text-xs font-semibold">{sources.rival.label}</div>
          <div className="mt-0.5 text-[11px] text-[var(--muted)]">
            {sources.rival.observations ?? 0} {tx("partido(s) vistos")}
          </div>
          <PitchZoneMethodSelector
            method={methodRival}
            onMethodChange={onMethodRivalChange}
          />
          <DeQuePartidoHablamos metodo={methodRival} partido={ultimoRival} />
        </div>
      </div>
      <div className="p-4 pt-0">
        <div className="mb-1.5 grid grid-cols-[1fr_0.7fr_1fr] gap-1.5 text-center text-[10px] uppercase text-[var(--muted)]">
          <div className="flex items-center justify-center gap-1.5">
            <span
              className="h-2 w-2 rounded-full"
              style={{ background: OWN_COLOR }}
            />
            {tx("Tu campo")}
          </div>
          <div>{tx("Medio")}</div>
          <div className="flex items-center justify-center gap-1.5">
            {tx("Campo rival")}
            <span
              className="h-2 w-2 rounded-full"
              style={{ background: RIVAL_COLOR }}
            />
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
            label={tx("Medio campo")}
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
