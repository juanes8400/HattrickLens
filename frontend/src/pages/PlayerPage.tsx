import { useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { Chart } from "../charts/Chart";
import { highlightedScatterOption, radarOption, timelineOption } from "../charts/chartOptions";
import { Column, DataTable } from "../components/DataTable";
import { DateRangeFilter, useDateRangeFilter } from "../components/DateRangeFilter";
import {
  Empty, ErrorState, GaugeBar, Kpi, Loading, Note, Panel,
} from "../components/Panels";
import { PlayerDistributionPanel } from "../components/PlayerDistributionPanel";
import { TEAM_ID, usePlayerBalance, usePlayerDetail } from "../hooks/useTeam";
import { date, htAge, money, number } from "../hooks/useFormat";
import { api } from "../services/api";
import type { ActivePlayerDetail, ExPlayerDetail } from "../services/api";

const SKILL_LABELS: Record<string, string> = {
  keeper: "Portería", defending: "Defensa", playmaking: "Jugadas", winger: "Lateral",
  passing: "Pases", scoring: "Anotación", set_pieces: "Balón parado",
  experience: "Experiencia", loyalty: "Fidelidad", form: "Forma", stamina: "Condición",
};

const EXPERIENCE_CATEGORY_LABELS: Record<string, string> = {
  league: "Liga", cup: "Copa", qualification: "Promoción", friendly: "Amistoso",
  friendly_international: "Amistoso internacional", tournament: "Torneo",
  masters: "HT Masters", national_team_friendly: "Amistoso de selección",
  youth_league: "Liga juvenil", youth_friendly: "Amistoso juvenil",
};

const SKILL_LEVELS = [
  "nulo", "desastroso", "horrible", "pobre", "débil", "insuficiente",
  "aceptable", "bueno", "excelente", "formidable", "destacado", "brillante",
  "magnífico", "clase mundial", "sobrenatural", "titánico", "extraterrestre",
  "mítico", "mágico", "utópico", "divino",
];

const DETAIL_SKILLS = [
  "experience", "form", "stamina", "keeper", "defending", "playmaking",
  "passing", "winger", "scoring", "set_pieces",
];

const TRAINER_TYPES: Record<number, string> = {
  0: "Defensivo", 1: "Ofensivo", 2: "Equilibrado",
};

function skillLevel(level: number): string {
  return SKILL_LEVELS[level] ?? `divino+${level - 20}`;
}

// HL-15x #94: 3 radares agrupados en vez de uno de 9 ejes — agrupación
// editorial (no oficial de CHPP), pensada por rol futbolístico, no una
// tabla del manual. Cubren las 11 variables del historial exactamente una
// vez cada una.
const RADAR_GROUPS: { title: string; axes: string[] }[] = [
  { title: "Ataque y creación", axes: ["scoring", "set_pieces", "passing", "playmaking"] },
  { title: "Banda y defensa", axes: ["winger", "defending", "keeper"] },
  { title: "Base del jugador", axes: ["experience", "loyalty", "form", "stamina"] },
];

const CAREER_STAGE_OPTIONS: { value: string; label: string }[] = [
  { value: "promesa", label: "Promesa en desarrollo" },
  { value: "pico", label: "En su pico" },
  { value: "veterano", label: "Veterano estable" },
  { value: "rotacion", label: "Pieza de rotación" },
  { value: "declive", label: "En declive" },
];

interface PositionRow {
  position: string;
  label: string;
  rating: number;
  isSpecialRole: boolean;
}

/** Semana ISO (lunes-domingo) de una fecha — para que ningún timeline tenga
 * más de un punto por semana aunque se sincronice varias veces al día. */
function isoWeekKey(dateStr: string): string {
  const d = new Date(dateStr);
  const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const dayNum = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
  const weekNo = Math.ceil((((date.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
  return `${date.getUTCFullYear()}-W${String(weekNo).padStart(2, "0")}`;
}

/** Un punto por semana ISO por cada serie: el último valor visto esa
 * semana, no todos — HL-15x #101, aplicado a cualquier timeline (TSI,
 * habilidades, rating por partido), no solo TSI. */
function bucketWeekly(
  dates: string[],
  series: { name: string; values: number[] }[],
): { labels: string[]; series: { name: string; values: number[] }[] } {
  const weekKeys = dates.map(isoWeekKey);
  const lastIndexForWeek = new Map<string, number>();
  const order: string[] = [];
  weekKeys.forEach((wk, i) => {
    if (!lastIndexForWeek.has(wk)) order.push(wk);
    lastIndexForWeek.set(wk, i);
  });
  const indices = order.map((wk) => lastIndexForWeek.get(wk) as number);
  const labels = indices.map((i) => (dates[i] ?? "").slice(0, 10));
  return {
    labels,
    series: series.map((s) => ({
      name: s.name, values: indices.map((i) => s.values[i] ?? 0),
    })),
  };
}

/** Los índices siempre vienen de un filtro de fechas construido sobre las
 * mismas `labels`/`series` que se recortan aquí, así que la posición
 * siempre existe. */
function pick<T>(items: T[], indices: number[]): T[] {
  return indices.map((i) => items[i] as T);
}

function rankInSquad(values: number[], own: number): { rank: number; total: number } {
  const sorted = [...values].sort((a, b) => b - a);
  const idx = sorted.findIndex((v) => v === own);
  return { rank: idx === -1 ? sorted.length : idx + 1, total: sorted.length };
}

/**
 * Ficha de jugador — el hub al que apunta todo nombre clickeable del
 * producto. Reúne lo que ya calculan los motores para este jugador en
 * particular: habilidades, posiciones, preclasificación de carrera,
 * entrenamiento/experiencia real, y su lugar dentro de la plantilla.
 */
export function PlayerPage() {
  const { htPlayerId } = useParams<{ htPlayerId: string }>();
  const id = Number(htPlayerId);
  const { data, isLoading, isError, error } = usePlayerDetail(id);

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return <Empty>Jugador no encontrado.</Empty>;

  // 2026-08-05, pedido explícitamente: un ex-jugador (venta real o
  // despido — `left_team_at` sin `sold_at`) no tiene el resto del
  // dashboard (habilidades, posiciones, entrenamiento…), así que se
  // separa en un componente aparte ANTES de cualquier hook que dependa de
  // campos que solo trae `ActivePlayerDetail` — TypeScript ya lo obliga
  // (unión discriminada por `isExPlayer`), y evita repetir el guard
  // "por si acaso" dentro de cada `useMemo`.
  if (data.isExPlayer) return <ExPlayerDashboard data={data} />;
  return <ActivePlayerDashboard data={data} />;
}

function ActivePlayerDashboard({ data }: { data: ActivePlayerDetail }) {
  const id = data.htPlayerId;
  const qc = useQueryClient();

  const tsiWeekly = useMemo(
    () => bucketWeekly(data.history.dates, [{ name: "TSI", values: data.history.tsi }]),
    [data],
  );
  const skillsWeekly = useMemo(() => {
    const axes = Object.keys(data.history.skills);
    return bucketWeekly(
      data.history.dates,
      axes.map((k) => ({ name: SKILL_LABELS[k] ?? k, values: data.history.skills[k] ?? [] })),
    );
  }, [data]);
  const matchRatingWeekly = useMemo(
    () => bucketWeekly(
      data.matchRatingHistory.map((m) => m.date),
      [{ name: "Rating", values: data.matchRatingHistory.map((m) => m.rating) }],
    ),
    [data],
  );
  const skillsRange = useDateRangeFilter(skillsWeekly.labels);
  const tsiRange = useDateRangeFilter(tsiWeekly.labels);
  const matchRatingRange = useDateRangeFilter(matchRatingWeekly.labels);
  const confirmStage = useMutation({
    mutationFn: (stage: string | null) => api.confirmCareerStage(TEAM_ID, id, stage),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["player", TEAM_ID, id] }),
  });

  const bestPosition = data.positions[0];
  const top10Positions = data.positions.slice(0, 10);

  // HL-15x #1+#24+#94: 3 radares agrupados, pasado-vs-hoy (fusión aprobada
  // por el usuario) — del historial real de snapshots. Con un solo punto
  // real todavía (cuenta nueva) se muestra una sola capa: no hay "antes"
  // que comparar, y fingir uno sería inventar datos.
  const histDates = data.history.dates;
  const histSkills = data.history.skills;
  const oldestIdx = 0;
  const latestIdx = histDates.length - 1;
  const oldestLabel = (histDates[oldestIdx] ?? "").slice(0, 10);
  const latestLabel = (histDates[latestIdx] ?? "").slice(0, 10);
  const axisValues = (axes: string[], idx: number) => axes.map((k) => histSkills[k]?.[idx] ?? 0);
  const radarSeriesFor = (axes: string[]) =>
    histDates.length === 0
      ? []
      : histDates.length === 1
        ? [{ name: latestLabel || "Hoy", value: axisValues(axes, latestIdx) }]
        : [
            { name: oldestLabel, value: axisValues(axes, oldestIdx) },
            { name: latestLabel, value: axisValues(axes, latestIdx) },
          ];

  const ownAgeTsi = data.squadAgeTsi.find((p) => p.htPlayerId === data.htPlayerId);
  const tsiRank = data.squadDistributions
    ? rankInSquad(data.squadDistributions.tsi.values, data.squadDistributions.tsi.ownValue)
    : null;
  const salaryRank = data.squadDistributions
    ? rankInSquad(data.squadDistributions.salary.values, data.squadDistributions.salary.ownValue)
    : null;

  const positionColumns: Column<PositionRow>[] = [
    { key: "label", header: "Posición", align: "left", value: (r) => r.label },
    { key: "rating", header: "Rating", value: (r) => r.rating,
      render: (r) => <b className="tabular-nums text-[var(--accent)]">{r.rating.toFixed(2)}</b> },
  ];

  const stageTone: Record<string, string> = {
    pico: "text-[var(--positive)] border-[var(--positive)]",
    promesa: "text-[var(--positive)] border-[var(--positive)]",
    veterano: "text-[var(--text)] border-[var(--border)]",
    rotacion: "text-[var(--muted)] border-[var(--border)]",
    declive: "text-[var(--danger)] border-[var(--danger)]",
    sin_historial: "text-[var(--muted)] border-[var(--border)]",
  };
  const confirmedOption = CAREER_STAGE_OPTIONS.find(
    (o) => o.value === data.careerStage.confirmedStage,
  );
  const effectiveLabel = confirmedOption?.label ?? data.careerStage.label;
  const effectiveStageKey = data.careerStage.confirmedStage ?? data.careerStage.stage;

  // HL-15x #100: agresividad va al revés que carácter/honestidad — nivel
  // bajo (p.ej. "calmada") es el rasgo deseable, así que se invierte para
  // que "lejos del centro" signifique lo mismo en los 3 ejes.
  const aggressivenessPlotted = data.character ? 5 - data.character.aggressiveness : 0;

  return (
    <div className="space-y-4">
      <header>
        <Link to="/team" className="text-xs text-[var(--accent)] hover:underline">← Jugadores</Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold">{data.name}</h1>
          <span
            className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${
              stageTone[effectiveStageKey] ?? "text-[var(--muted)] border-[var(--border)]"
            }`}
          >
            {effectiveLabel} {confirmedOption ? "· confirmado" : "· sugerido"}
          </span>
        </div>
        <p className="text-sm text-[var(--muted)]">
          {data.team.name} · {htAge(Number(data.age.split(".")[0]), Number(data.age.split(".")[1]))} años
          {bestPosition && ` · ${bestPosition.label} (${bestPosition.rating.toFixed(2)})`}
          {data.nativeLeagueName && ` · ${data.nativeLeagueName}`}
        </p>
      </header>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(20rem,0.72fr)]">
        <div className="space-y-4">
          <Panel title="Ficha del jugador">
            <dl className="grid gap-x-6 gap-y-2 p-4 text-sm sm:grid-cols-2">
              <div className="flex justify-between gap-3"><dt className="text-[var(--muted)]">PlayerID</dt><dd className="tabular-nums">{data.htPlayerId}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-[var(--muted)]">Edad</dt><dd>{data.age} años</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-[var(--muted)]">Nacionalidad</dt><dd>{data.nativeLeagueName ?? `País #${data.countryId}`}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-[var(--muted)]">Especialidad</dt><dd>{data.specialty || "Sin especialidad"}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-[var(--muted)]">Carácter</dt><dd>{data.character?.agreeabilityLabel ?? "—"}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-[var(--muted)]">Agresividad</dt><dd>{data.character?.aggressivenessLabel ?? "—"}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-[var(--muted)]">Honestidad</dt><dd>{data.character?.honestyLabel ?? "—"}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-[var(--muted)]">Liderazgo</dt><dd>{skillLevel(data.leadership)}</dd></div>
            </dl>
          </Panel>

          <Panel title="Habilidades">
            <div className="grid gap-x-8 gap-y-3 p-4 sm:grid-cols-2">
              {DETAIL_SKILLS.map((skill) => {
                const value = skill === "experience" ? data.experience
                  : skill === "form" ? data.form
                    : skill === "stamina" ? data.stamina
                      : data.skills[skill] ?? 0;
                return (
                  <div key={skill} className="flex items-baseline justify-between gap-3 text-sm">
                    <span className="font-semibold">{SKILL_LABELS[skill]}</span>
                    <span className="text-right font-semibold text-[var(--accent)]">{skillLevel(value)} <small className="ml-1 text-[var(--muted)]">{value}</small></span>
                  </div>
                );
              })}
            </div>
            <Note>La ficha muestra el nivel actual; las variaciones y la evolución completa permanecen más abajo.</Note>
          </Panel>
        </div>

        <div className="space-y-4">
          <Panel title="Estado y contrato" meta={data.isTransferListed ? "en venta" : "no está en venta"}>
            <dl className="space-y-2 p-4 text-sm">
              <div className="flex justify-between gap-3"><dt className="text-[var(--muted)]">TSI</dt><dd className="font-semibold tabular-nums">{number(data.tsi)}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-[var(--muted)]">Salario</dt><dd className="font-semibold tabular-nums">{money(data.salary)}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-[var(--muted)]">Precio compra</dt><dd>{data.purchasePrice == null ? "no disponible" : money(data.purchasePrice)}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-[var(--muted)]">Fecha compra</dt><dd>{data.purchasedAt ? date(data.purchasedAt) : "no disponible"}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-[var(--muted)]">Lesión</dt><dd className={data.injuryLevel >= 0 ? "text-[var(--danger)]" : "text-[var(--muted)]"}>{data.injuryLevel >= 0 ? data.injuryLevel : "sin lesión"}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-[var(--muted)]">Último partido</dt><dd className="text-right">{data.lastMatch ? `${data.lastMatch.position} · ${data.lastMatch.rating?.toFixed(1) ?? "—"}` : "sin detalle"}</dd></div>
            </dl>
          </Panel>

          <Panel title="Entrenamiento" meta="estimación Lens">
            <div className="space-y-3 p-4 text-sm">
              <div className="flex justify-between gap-3"><span className="text-[var(--muted)]">Objetivo actual</span><b>{data.training.trainedSkill ? SKILL_LABELS[data.training.trainedSkill] ?? data.training.trainedSkill : "sin tipo sincronizado"}</b></div>
              <div className="flex justify-between gap-3"><span className="text-[var(--muted)]">Próxima subida</span><span>{data.training.weeksToPop == null ? "sin previsión" : `~${data.training.weeksToPop} sem`}</span></div>
              {data.training.weeklyProgressPct != null && <GaugeBar label="Ritmo semanal" value={data.training.weeklyProgressPct} max={100} />}
            </div>
            <Note>El ritmo es una estimación del motor; no se presenta como un progreso oficial de Hattrick.</Note>
          </Panel>

          <Panel title="Entrenador y goles">
            <dl className="space-y-2 p-4 text-sm">
              <div className="flex justify-between gap-3"><dt className="text-[var(--muted)]">Entrenador</dt><dd>{data.playerTrainer ? `${skillLevel(data.playerTrainer.level)} · ${TRAINER_TYPES[data.playerTrainer.type] ?? "—"}` : "no es entrenador"}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-[var(--muted)]">Liga / Copa</dt><dd>{data.goals ? `${data.goals.league} / ${data.goals.cup}` : "—"}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-[var(--muted)]">Carrera</dt><dd>{data.goals?.career ?? "—"}</dd></div>
              <div className="flex justify-between gap-3"><dt className="text-[var(--muted)]">Hat-tricks</dt><dd>{data.goals?.hattricks ?? "—"}</dd></div>
            </dl>
          </Panel>
        </div>
      </div>

      <Panel title="Momento de la carrera" meta={`sugerencia con confianza ${data.careerStage.confidence}`}>
        <div className="space-y-2 p-4">
          <p className="text-sm">{data.careerStage.rationale}</p>
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-[var(--muted)]">
            <span>Habilidades subiendo: {String(data.careerStage.signals.skillsRising)}</span>
            <span>Bajando: {String(data.careerStage.signals.skillsFalling)}</span>
            <span>Estables: {String(data.careerStage.signals.skillsStable)}</span>
            <span>Factor de edad: {String(data.careerStage.signals.ageFactor)}</span>
            {data.careerStage.signals.squadPercentile != null && (
              <span>Percentil en plantilla: {String(data.careerStage.signals.squadPercentile)}</span>
            )}
          </div>
          <div className="flex items-center gap-2 pt-1">
            <label className="text-xs text-[var(--muted)]" htmlFor="career-stage-confirm">
              Tu confirmación:
            </label>
            <select
              id="career-stage-confirm"
              className="rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-xs"
              value={data.careerStage.confirmedStage ?? ""}
              disabled={confirmStage.isPending}
              onChange={(e) => confirmStage.mutate(e.target.value || null)}
            >
              <option value="">Sin confirmar — usar sugerencia de la app</option>
              {CAREER_STAGE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        </div>
        <Note>
          La app SUGIERE con reglas de producto (edad, tendencia real de habilidades,
          percentil, liderazgo) — nunca fija la etiqueta sola: la confirmas tú arriba.
        </Note>
      </Panel>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi
          label="TSI" value={number(data.tsi)}
          hint={tsiRank ? `puesto ${tsiRank.rank} de ${tsiRank.total} en la plantilla` : undefined}
        />
        <Kpi
          label="Salario" value={money(data.salary)}
          hint={salaryRank ? `puesto ${salaryRank.rank} de ${salaryRank.total} en la plantilla` : undefined}
        />
        <Kpi label="Forma" value={String(data.form)} />
        <Kpi label="Experiencia" value={String(data.experience)} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {RADAR_GROUPS.map((group) => (
          <Panel
            key={group.title}
            title={group.title}
            meta={histDates.length > 1 ? `${oldestLabel} → ${latestLabel}` : "sin historial suficiente"}
          >
            <div className="p-4">
              <Chart
                ariaLabel={`Radar de ${group.title.toLowerCase()}`}
                height={260}
                option={radarOption(
                  group.axes.map((k) => ({ name: SKILL_LABELS[k] ?? k, max: 20 })),
                  radarSeriesFor(group.axes),
                )}
              />
            </div>
          </Panel>
        ))}
      </div>

      <Panel title="Mejores posiciones" meta="top 10 de 19 + roles especiales">
        <DataTable
          rows={top10Positions}
          columns={positionColumns}
          rowKey={(r) => r.position}
          initialSort="rating"
          csvName={`${data.name}-posiciones`}
          emptyMessage="Sin datos de posición."
        />
      </Panel>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <Panel title="Precio de compra" meta="real, de transfersteam.xml">
          {data.purchasePrice != null ? (
            <div className="space-y-1 p-4">
              <div className="text-2xl font-semibold tabular-nums">
                {money(data.purchasePrice)}
              </div>
              <div className="text-xs text-[var(--muted)]">
                {data.purchasedAt ? date(data.purchasedAt) : "fecha no disponible"}
              </div>
            </div>
          ) : (
            <Empty>Sin compra registrada en el historial reciente del equipo.</Empty>
          )}
        </Panel>
        <Panel
          title="Entrenamiento"
          meta={
            data.training.weeklyProgressPct != null
              ? `ritmo real ~${data.training.weeklyProgressPct}%/semana`
              : undefined
          }
        >
          {data.training.trainedSkill ? (
            <div className="space-y-2 p-4">
              <div className="text-sm">
                Entrena {SKILL_LABELS[data.training.trainedSkill] ?? data.training.trainedSkill}
              </div>
              <div className="text-xs text-[var(--muted)]">
                {data.training.weeksToPop != null
                  ? `próxima subida estimada en ~${data.training.weeksToPop} sem`
                  : "sin previsión disponible"}
              </div>
              {data.training.weeklyProgressPct != null && (
                <GaugeBar
                  label="Ritmo semanal (fórmula real)"
                  value={data.training.weeklyProgressPct}
                  max={100}
                />
              )}
            </div>
          ) : (
            <Empty>Sin tipo de entrenamiento sincronizado.</Empty>
          )}
          <Note>
            Ritmo teórico de la fórmula ya calibrada (1/semanas). El acumulado real por
            partidos y posición jugada todavía no está cableado — falta verificar la tabla
            de compatibilidad posición→entrenamiento.
          </Note>
        </Panel>
        <Panel
          title="Experiencia"
          meta={
            data.experienceProgress
              ? `${data.experienceProgress.calibrationSource === "observed" ? "calibrado" : "fórmula base"}`
              : undefined
          }
        >
          {data.experienceProgress ? (
            <div className="space-y-2 p-4">
              <GaugeBar
                label={`Hacia el nivel ${data.experience + 1}`}
                value={data.experienceProgress.percent}
                max={100}
              />
              <div className="text-xs text-[var(--muted)]">
                {data.experienceProgress.points} de {data.experienceProgress.pointsPerLevel} puntos
                {" · "}
                {Object.entries(data.experienceProgress.breakdown)
                  .map(([k, v]) => `${EXPERIENCE_CATEGORY_LABELS[k] ?? k}: ${v}`)
                  .join(" · ") || "sin partidos contados todavía"}
              </div>
              {data.experienceProgress.unscoredNationalMatches > 0 && (
                <div className="text-xs text-[var(--accent)]">
                  + {data.experienceProgress.unscoredNationalMatches} partido(s) de selección
                  detectado(s) desde entonces sin puntaje exacto — o es competitivo (Hattrick no
                  distingue Mundial/Copa continental/Copa de Naciones con el mismo código) o
                  subió el conteo de partidos con la selección (Caps) sin que alcanzáramos a
                  ver ese partido en concreto (el club jugó después y lo tapó antes del
                  siguiente sync).
                </div>
              )}
              {data.nationalTeam && (
                <div className="text-xs text-[var(--muted)]">
                  Selección nacional (carrera): {data.nationalTeam.caps} partido(s) mayor
                  {data.nationalTeam.capsU20 > 0 && `, ${data.nationalTeam.capsU20} sub-20`}
                </div>
              )}
            </div>
          ) : (
            <Empty>Sin historial suficiente para contar partidos.</Empty>
          )}
          <Note>
            Fórmula del Manual No Escrito, verificada contra Hattrick Control para liga y
            amistoso internacional; Masters, amistoso de selección y partidos juveniles ya
            puntúan con el valor real de Hattrick (docs/reference/tabla_experiencia.html), pero
            todavía sin observaciones propias que los confirmen. Cada partido pesa proporcional a
            los minutos jugados sobre 90 (jugar 70 = 70/90 de esos puntos; 90 o más, el 100%,
            nunca de más). Cuenta partidos reales jugados desde que se observó este nivel — puede
            subestimar si el nivel es anterior a esta cuenta. "Selección nacional (carrera)" viene
            de Caps/CapsU20 (playerdetails.xml, botón "Actualizar detalles de jugadores") y no se
            actualiza en el sync normal.
          </Note>
        </Panel>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <GaugeBar label="Fidelidad" value={data.loyalty ?? 0} max={20} />
        <GaugeBar label="Forma" value={data.form} max={20} />
        <GaugeBar label="Resistencia" value={data.stamina} max={20} />
      </div>

      {data.character && (
        <Panel title="Carácter" meta="lejos del centro = rasgo deseable en los 3 ejes">
          <div className="p-4">
            <Chart
              ariaLabel="Perfil de carácter: carácter, agresividad, honestidad"
              height={280}
              option={radarOption(
                [
                  { name: `Carácter (${data.character.agreeabilityLabel})`, max: 5 },
                  { name: `Agresividad (${data.character.aggressivenessLabel})`, max: 5 },
                  { name: `Honestidad (${data.character.honestyLabel})`, max: 5 },
                ],
                [{
                  name: data.name,
                  value: [
                    data.character.agreeability, aggressivenessPlotted, data.character.honesty,
                  ],
                }],
              )}
            />
          </div>
          <Note>
            Agresividad se muestra invertida (5 − nivel real: {data.character.aggressiveness}):
            "{data.character.aggressivenessLabel}" es el rasgo deseable, igual que en los otros
            dos ejes. Traducido con el fichero oficial de CHPP.
          </Note>
        </Panel>
      )}

      {data.topSkillDistributions && (
        <div className="grid gap-4 lg:grid-cols-3">
          {Object.entries(data.topSkillDistributions).map(([skill, dist]) => (
            <PlayerDistributionPanel
              key={skill}
              title={`${SKILL_LABELS[skill] ?? skill} en la plantilla`}
              xLabel={SKILL_LABELS[skill] ?? skill}
              playerName={data.name}
              distribution={dist}
              formatValue={(v) => v.toFixed(0)}
            />
          ))}
        </div>
      )}

      {data.squadDistributions && (
        <div className="grid gap-4 lg:grid-cols-3">
          <PlayerDistributionPanel
            title="TSI en la plantilla"
            xLabel="TSI"
            playerName={data.name}
            distribution={data.squadDistributions.tsi}
            formatValue={(v) => number(v)}
          />
          <PlayerDistributionPanel
            title="Salario en la plantilla"
            xLabel="Salario"
            playerName={data.name}
            distribution={data.squadDistributions.salary}
            formatValue={(v) => money(v)}
          />
          <PlayerDistributionPanel
            title="$ por punto de TSI"
            xLabel="$/TSI"
            playerName={data.name}
            distribution={data.squadDistributions.salaryPerTsi}
            formatValue={(v) => v.toFixed(2)}
          />
        </div>
      )}

      <Panel
        title="Evolución de habilidades"
        meta={skillsWeekly.labels.length > 1 ? "1 punto por semana ISO como mínimo" : "historial corto todavía"}
      >
        {skillsWeekly.labels.length > 1 ? (
          <div className="p-4">
            <div className="mb-3">
              <DateRangeFilter
                range={skillsRange.range} onChange={skillsRange.setRange}
                min={skillsRange.min} max={skillsRange.max}
              />
            </div>
            <Chart
              ariaLabel="Evolución semanal de las habilidades del jugador"
              height={300}
              option={timelineOption(
                pick(skillsWeekly.labels, skillsRange.indices),
                skillsWeekly.series.map((s) => ({
                  name: s.name, values: pick(s.values, skillsRange.indices),
                })),
              )}
            />
          </div>
        ) : (
          <Empty>
            Todavía no hay dos semanas distintas de historial real — esta gráfica se llena a
            medida que se sincroniza.
          </Empty>
        )}
      </Panel>

      <Panel title="Evolución de TSI" meta="1 punto por semana ISO como mínimo">
        {tsiWeekly.labels.length > 1 ? (
          <div className="p-4">
            <div className="mb-3">
              <DateRangeFilter
                range={tsiRange.range} onChange={tsiRange.setRange}
                min={tsiRange.min} max={tsiRange.max}
              />
            </div>
            <Chart
              ariaLabel="Evolución semanal del TSI del jugador"
              height={240}
              option={timelineOption(
                pick(tsiWeekly.labels, tsiRange.indices),
                tsiWeekly.series.map((s) => ({
                  name: s.name, values: pick(s.values, tsiRange.indices),
                })),
              )}
            />
          </div>
        ) : (
          <Empty>
            Todavía no hay dos semanas distintas de historial real para trazar una evolución.
          </Empty>
        )}
      </Panel>

      <Panel title="Goles">
        <div className="grid gap-4 p-4 sm:grid-cols-3 xl:grid-cols-6">
          <Kpi label="Liga" value={String(data.goals?.league ?? 0)} />
          <Kpi label="Copa" value={String(data.goals?.cup ?? 0)} />
          <Kpi label="Amistosos" value={String(data.goals?.friendlies ?? 0)} />
          <Kpi label="Carrera" value={String(data.goals?.career ?? 0)} />
          <Kpi label="Hat-tricks" value={String(data.goals?.hattricks ?? 0)} />
          <Kpi label="Asistencias" value={String(data.goals?.assists ?? 0)} />
        </div>
      </Panel>

      <Panel
        title="Rating por partido"
        meta={
          matchRatingWeekly.labels.length > 0
            ? `${matchRatingWeekly.labels.length} semana(s) real(es), 1 punto por semana`
            : "sin partidos sincronizados todavía"
        }
      >
        {matchRatingWeekly.labels.length > 0 ? (
          <div className="p-4">
            <div className="mb-3">
              <DateRangeFilter
                range={matchRatingRange.range} onChange={matchRatingRange.setRange}
                min={matchRatingRange.min} max={matchRatingRange.max}
              />
            </div>
            <Chart
              ariaLabel="Rating real del jugador por semana, un punto por partido más reciente"
              height={220}
              option={timelineOption(
                pick(matchRatingWeekly.labels, matchRatingRange.indices),
                matchRatingWeekly.series.map((s) => ({
                  name: s.name, values: pick(s.values, matchRatingRange.indices),
                })),
              )}
            />
          </div>
        ) : (
          <Empty>
            Se llena partido a partido al sincronizar — hoy no hay ninguno todavía en esta
            cuenta.
          </Empty>
        )}
      </Panel>

      {ownAgeTsi && (
        <Panel title="TSI vs. edad de la plantilla">
          <div className="p-4">
            <Chart
              ariaLabel="Dispersión de TSI contra edad de toda la plantilla, con este jugador resaltado"
              height={280}
              option={highlightedScatterOption(
                data.squadAgeTsi.map((p) => ({ x: p.age, y: p.tsi, label: p.name })),
                { x: ownAgeTsi.age, y: ownAgeTsi.tsi, label: data.name },
                "Edad", "TSI",
              )}
            />
          </div>
        </Panel>
      )}
    </div>
  );
}

/**
 * Ficha de EX-jugador — pedido explícitamente 2026-08-05: nada de
 * habilidades/posiciones/entrenamiento (no tiene sentido para alguien que
 * ya no vemos), solo las fechas en que estuvo en el equipo y las partes
 * del cálculo del ROI, en cuadritos — mismo dato ya calculado por
 * `usePlayerBalance` (el que alimenta "Detalle" en Saldo por jugador),
 * nunca un cálculo aparte.
 */
function ExPlayerDashboard({ data }: { data: ExPlayerDetail }) {
  const { data: balance, isLoading, isError, error } = usePlayerBalance();

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;

  const row = balance?.players.find((p) => p.htPlayerId === data.htPlayerId);

  return (
    <div className="space-y-4">
      <header>
        <Link to="/team" className="text-xs text-[var(--accent)] hover:underline">← Jugadores</Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold">{data.name}</h1>
          <span className="rounded-full border px-2.5 py-0.5 text-xs font-medium text-[var(--muted)] border-[var(--border)]">
            Ex-jugador
          </span>
        </div>
        <p className="text-sm text-[var(--muted)]">
          Ya no está en la plantilla — esta ficha solo trae las fechas y el saldo, no el resto
          del análisis de plantilla.
        </p>
      </header>

      <Panel title="Tiempo en el equipo">
        <dl className="grid gap-x-6 gap-y-2 p-4 text-sm sm:grid-cols-2">
          <div className="flex justify-between gap-3">
            <dt className="text-[var(--muted)]">Fecha de compra</dt>
            <dd className="tabular-nums">{date(data.purchasedAt)}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-[var(--muted)]">
              {row?.isDepartureWithoutSale ? "Fecha de salida" : "Fecha de venta"}
            </dt>
            <dd className="tabular-nums">
              {date(data.soldAt ?? data.leftTeamAt)}
              {row?.isDepartureWithoutSale && (
                <span className="text-[var(--muted)]"> (despedido)</span>
              )}
            </dd>
          </div>
        </dl>
      </Panel>

      {row ? (
        <>
          <Panel title="Cálculo del ROI" meta="mismo desglose que Detalle en Saldo por jugador">
            <div className="grid gap-4 p-4 sm:grid-cols-2 xl:grid-cols-4">
              <Kpi label="Precio de compra" value={row.purchasePrice != null ? money(row.purchasePrice, balance!.currency) : "?"} />
              <Kpi label="Salario acumulado" value={money(row.salaryTotal, balance!.currency)} />
              <Kpi label="Costo de listados" value={money(row.listingCost, balance!.currency)} />
              <Kpi
                label="Precio de venta"
                value={row.salePrice != null ? money(row.salePrice, balance!.currency) : "—"}
                hint={row.isDepartureWithoutSale ? "despedido" : undefined}
              />
              <Kpi label="% agente" value={row.agentPct != null ? `${(row.agentPct * 100).toFixed(1)}%` : "—"} />
              <Kpi
                label="Venta neta"
                value={
                  row.salePrice != null && row.commissionAmount !== "?"
                    ? money(row.salePrice - row.commissionAmount, balance!.currency)
                    : "?"
                }
                hint="precio de venta × (1 − % agente)"
              />
              <Kpi label="Reventa (est.)" value={money(row.resaleBonusShare, balance!.currency)} />
              <Kpi
                label="ROI"
                value={row.roiPct !== "?" ? `${row.roiPct.toFixed(1)}%` : "?"}
                tone={row.roiPct === "?" ? undefined : row.roiPct >= 0 ? "positive" : "danger"}
              />
            </div>
          </Panel>
          <Panel title="Ganancia">
            <div className="p-4">
              <div
                className={
                  row.saldo == null ? "text-2xl font-semibold text-[var(--muted)]"
                    : row.saldo >= 0 ? "text-2xl font-semibold tabular-nums text-[var(--positive)]"
                      : "text-2xl font-semibold tabular-nums text-[var(--danger)]"
                }
              >
                {row.saldo != null ? money(row.saldo, balance!.currency) : "—"}
              </div>
            </div>
          </Panel>
        </>
      ) : (
        <Empty>Sin datos de saldo todavía para este jugador.</Empty>
      )}
    </div>
  );
}
