import { useState } from "react";
import type { CSSProperties } from "react";
import { useParams } from "react-router-dom";
import { Chart } from "../charts/Chart";
import { barOption } from "../charts/chartOptions";
import { Column, DataTable } from "../components/DataTable";
import { Empty, ErrorState, Kpi, Loading, Note, Panel, ProjectionPanel } from "../components/Panels";
import { TsiHistogramPanel } from "../components/TsiHistogramPanel";
import { number } from "../hooks/useFormat";
import { useDashboard, useRivalScouting } from "../hooks/useTeam";
import type { PitchZoneDuel, PitchZoneScope, RivalScouting } from "../services/api";

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
export function RivalPage() {
  const { rivalHtTeamId } = useParams<{ rivalHtTeamId: string }>();
  const id = Number(rivalHtTeamId);
  const [logTsi, setLogTsi] = useState(false);
  const [excludeKeeper, setExcludeKeeper] = useState(true);
  const [top11, setTop11] = useState(false);
  const [includeCompetitive, setIncludeCompetitive] = useState(true);
  const [includeFriendlies, setIncludeFriendlies] = useState(true);
  const [pitchZoneScope, setPitchZoneScope] = useState<PitchZoneScope>("mixed");
  const { data, isLoading, isError, error } = useRivalScouting(
    id, logTsi, excludeKeeper, top11, includeCompetitive, includeFriendlies, pitchZoneScope,
  );
  const dashboard = useDashboard();

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return <Empty>Rival no encontrado.</Empty>;

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
    { key: "name", header: "Jugador", value: (r) => r.name },
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

      <div className="grid gap-4 sm:grid-cols-2">
        <Kpi label="Partidos analizados" value={String(data.matchesAnalysed)} />
        <Kpi
          label="TSI medio del rival"
          value={rivalTsiAvg != null ? number(rivalTsiAvg) : "—"}
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
        excludeKeeper={excludeKeeper}
        onExcludeKeeperChange={setExcludeKeeper}
        top11={top11}
        onTop11Change={setTop11}
        noteSuffix={
          "del rival" +
          (top11
            ? " — tu once real (motor de posiciones) contra los 11 de mayor TSI del rival"
            : "") +
          ". El TSI del rival es un dato público real; sus habilidades exactas están " +
          "ocultas por CHPP"
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
          Estimación {data.winProbability.confidence}. TSI de tus 11 probables (
          {number(data.winProbability.ownTsiTotal)}) contra los 11 de mayor TSI del rival (
          {number(data.winProbability.rivalTsiTotal)}).
        </Note>
      </ProjectionPanel>

      <div className="grid gap-4 lg:grid-cols-2">
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

        <Panel title="¿Su ataque rota de lado?">
          {data.sideRotation ? (
            <div className="space-y-3 p-4">
              <div className="grid grid-cols-3 gap-2 text-center text-xs">
                {(
                  [
                    ["izquierda", data.sideRotation.attackLeftAvg, data.sideRotation.attackLeftStd],
                    ["centro", data.sideRotation.attackCentralAvg, data.sideRotation.attackCentralStd],
                    ["derecha", data.sideRotation.attackRightAvg, data.sideRotation.attackRightStd],
                  ] as const
                ).map(([label, avg, std]) => (
                  <div
                    key={label}
                    className={`rounded border p-2 ${
                      data.sideRotation!.strongSide === label
                        ? "border-[var(--accent)] bg-[var(--accent)]/10"
                        : "border-[var(--border)]"
                    }`}
                  >
                    <div className="text-[10px] uppercase text-[var(--muted)]">{label}</div>
                    <div className="tabular-nums font-semibold">
                      {avg.toFixed(0)}{" "}
                      <span className="text-[10px] font-normal text-[var(--muted)]">
                        ± {std.toFixed(1)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
              <div className="flex items-center gap-1.5 text-xs text-[var(--muted)]">
                <span>Lado más fuerte por partido (más antiguo → más reciente):</span>
                {data.sideRotation.dominantSideByMatch.map((side, i) => (
                  <span
                    key={i}
                    className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-semibold ${
                      side === data.sideRotation!.strongSide
                        ? "bg-[var(--accent)] text-white"
                        : "bg-[var(--surface-2)] text-[var(--muted)]"
                    }`}
                  >
                    {side.charAt(0).toUpperCase()}
                  </span>
                ))}
              </div>
              <p className="text-xs text-[var(--muted)]">
                {data.sideRotation.dominantPct === 100
                  ? `Lado fuerte fijo, sin excepción: la ${data.sideRotation.strongSide} fue el carril más fuerte en los ${data.sideRotation.matchesAnalysed} de ${data.sideRotation.matchesAnalysed} partidos vistos.`
                  : data.sideRotation.rotates
                    ? `Rota: ningún lado domina de forma consistente — el más fuerte cambió partido a partido en sus últimos ${data.sideRotation.matchesAnalysed} partido(s) oficiales.`
                    : `Lado fuerte habitual: la ${data.sideRotation.strongSide} fue el carril más fuerte en el ${data.sideRotation.dominantPct.toFixed(0)}% de sus últimos ${data.sideRotation.matchesAnalysed} partido(s) — con variación partido a partido, no siempre por el mismo margen.`}
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
        scope={pitchZoneScope}
        onScopeChange={setPitchZoneScope}
      />

      {data.tacticHistory && (
        <Panel
          title="Táctica habitual del rival"
          meta={`${data.tacticHistory.matchesAnalysed} partido(s) con datos de sector`}
        >
          <div className="grid gap-4 p-4 sm:grid-cols-2">
            <div>
              <Chart
                ariaLabel="Frecuencia de tácticas usadas por el rival en partidos ya jugados"
                height={Math.max(140, data.tacticHistory.tactics.length * 36)}
                option={barOption(
                  data.tacticHistory.tactics.map((t) => t.label),
                  data.tacticHistory.tactics.map((t) => t.count),
                  "Partidos",
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
          <Note>
            Táctica, nivel de táctica y formación son datos reales de sus últimos{" "}
            {data.tacticHistory.matchesAnalysed} partido(s) oficiales ya finalizados, sea contra
            quien sea — hecho público permanente de un partido jugado, también para un equipo
            que no es el tuyo. Duelos y Escaleras nunca cuentan para esto.
          </Note>
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

      {data.caveats.length > 0 && (
        <Panel title="Qué puede y no puede ver esta ficha">
          <div className="space-y-1 p-4 text-xs text-[var(--muted)]">
            {data.caveats.map((c, i) => (
              <p key={i}>{c}</p>
            ))}
          </div>
        </Panel>
      )}
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
    <Panel title="Comparación de plantilla" meta={`${ownLabel} vs. ${rivalLabel}`}>
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
      </div>
    </Panel>
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
          {own != null ? format(own) : "—"}
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

const PITCH_ZONE_SCOPE_LABEL: Record<PitchZoneScope, string> = {
  mixed: "Últimos 5",
  official: "Últimos 5 oficiales",
  friendly: "Últimos 5 amistosos",
};

function PitchZoneScopeSelector({
  scope,
  onScopeChange,
}: {
  scope: PitchZoneScope;
  onScopeChange: (v: PitchZoneScope) => void;
}) {
  return (
    <div className="mb-3 flex overflow-hidden rounded border border-[var(--border)] text-xs">
      {(["mixed", "official", "friendly"] as const).map((s) => (
        <button
          key={s}
          onClick={() => onScopeChange(s)}
          className={`px-3 py-1 ${scope === s ? "bg-[var(--accent)] text-white" : "bg-[var(--surface)]"}`}
        >
          {PITCH_ZONE_SCOPE_LABEL[s]}
        </button>
      ))}
    </div>
  );
}

function PitchZoneDuelsPanel({
  duels,
  matchesAnalysed,
  scope,
  onScopeChange,
}: {
  duels: PitchZoneDuel[] | null;
  matchesAnalysed: { own: number | null; rival: number | null };
  scope: PitchZoneScope;
  onScopeChange: (v: PitchZoneScope) => void;
}) {
  if (!duels) {
    return (
      <Panel title="Duelos por zona de la cancha">
        <div className="p-4 pb-0">
          <PitchZoneScopeSelector scope={scope} onScopeChange={onScopeChange} />
        </div>
        <Empty>
          Falta alguno de los dos lados con partidos y datos de sector para{" "}
          {PITCH_ZONE_SCOPE_LABEL[scope].toLowerCase()} — sin eso no hay duelo honesto que
          mostrar.
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
      meta={`tú: ${matchesAnalysed.own} · rival: ${matchesAnalysed.rival} partido(s)`}
    >
      <div className="p-4 pb-0">
        <PitchZoneScopeSelector scope={scope} onScopeChange={onScopeChange} />
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
        <div
          className="grid gap-1.5 rounded-xl border border-[var(--border)] p-2"
          style={{
            gridTemplateColumns: "1fr 0.7fr 1fr",
            gridTemplateRows: "repeat(3, minmax(52px, auto))",
            background: "#173323",
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
      <Note>
        Cada duelo enfrenta tu rating de sector (real, de tus partidos ya sincronizados) contra
        el del rival (real, pedido en vivo) en el carril físico que le corresponde — tu ataque
        izquierdo corre por el mismo lateral que defiende el derecho rival, como en cualquier
        alineación reflejada. El % es una PROYECCIÓN simple (rating entre la suma de los dos),
        no la fórmula real del motor de partido de Hattrick.
      </Note>
    </Panel>
  );
}
