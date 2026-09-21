import { useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { Chart } from "../charts/Chart";
import {
  highlightedScatterOption,
  radarOption,
  timelineOption,
} from "../charts/chartOptions";
import { Column, DataTable } from "../components/DataTable";
import { Specialty } from "../components/Specialty";
import { CountryCell } from "../components/CountryFlag";
import {
  DateRangeFilter,
  useDateRangeFilter,
} from "../components/DateRangeFilter";
import {
  Empty,
  ErrorState,
  Kpi,
  Loading,
  Panel,
  ProgressBar,
  SkillBar,
} from "../components/Panels";
import { PlayerDistributionPanel } from "../components/PlayerDistributionPanel";
import { TEAM_ID, usePlayerBalance, usePlayerDetail } from "../hooks/useTeam";
import { date, htAge, htAgeTexto, money, number } from "../hooks/useFormat";
import { api } from "../services/api";
import type { ActivePlayerDetail, ExPlayerDetail } from "../services/api";
import { skillLevelLabel } from "../utils/skillLevels";

import { tx } from "../i18n/tx";
import { nivelOficial, terminoOficial } from "../i18n/glosario";
/** El nombre de cada habilidad sale del glosario oficial de Hattrick, no del
 *  diccionario: «Defensa» es la habilidad Defending y también el sector
 *  Defence, y sólo la familia las distingue. Fidelidad no está en el glosario
 *  del juego, así que ésa sí se traduce aquí. */
const habilidad = (clave: string, respaldo: string) =>
  terminoOficial("habilidades", clave, respaldo);

const SKILL_LABELS: Record<string, string> = {
  keeper: habilidad("keeper", "Portería"),
  defending: habilidad("defending", "Defensa"),
  playmaking: habilidad("playmaking", "Jugadas"),
  winger: habilidad("winger", "Lateral"),
  passing: habilidad("passing", "Pases"),
  scoring: habilidad("scoring", "Anotación"),
  set_pieces: habilidad("set_pieces", "Balón parado"),
  experience: habilidad("experience", "Experiencia"),
  loyalty: tx("Fidelidad"),
  form: habilidad("form", "Forma"),
  stamina: habilidad("stamina", "Resistencia"),
};

/** Las mismas familias que enseña la pantalla de Equipo, en el mismo orden:
 *  una gráfica por familia en vez de once líneas juntas. Resistencia y Forma
 *  van aparte porque su escala es mucho más corta. */
const EVOLUCION_GRUPOS: { titulo: string; skills: string[] }[] = [
  {
    titulo: tx("Habilidades Ofensivas"),
    skills: ["winger", "passing", "scoring"],
  },
  {
    titulo: tx("Habilidades Defensivas"),
    skills: ["keeper", "defending", "playmaking"],
  },
  {
    titulo: tx("Habilidades Complementarias"),
    skills: ["set_pieces", "experience", "loyalty"],
  },
  { titulo: tx("Resistencia y Forma"), skills: ["stamina", "form"] },
];

const DETAIL_SKILLS = [
  "experience",
  "form",
  "stamina",
  "keeper",
  "defending",
  "playmaking",
  "passing",
  "winger",
  "scoring",
  "set_pieces",
];

function skillLevel(level: number): string {
  return skillLevelLabel(level);
}

// HL-15x #94: 3 radares agrupados en vez de uno de 9 ejes, agrupación
// editorial (no oficial de CHPP), pensada por rol futbolístico, no una
// tabla del manual. Cubren las 11 variables del historial exactamente una
// vez cada una.
const RADAR_GROUPS: { title: string; axes: string[] }[] = [
  {
    title: tx("Ataque y creación"),
    axes: ["scoring", "set_pieces", "passing", "playmaking"],
  },
  { title: tx("Banda y defensa"), axes: ["winger", "defending", "keeper"] },
  {
    title: tx("Base del jugador"),
    axes: ["experience", "loyalty", "form", "stamina"],
  },
];

const CAREER_STAGE_OPTIONS: { value: string; label: string }[] = [
  { value: "promesa", label: tx("Promesa en desarrollo") },
  { value: "pico", label: tx("En su pico") },
  { value: "veterano", label: tx("Veterano estable") },
  { value: "rotacion", label: tx("Pieza de rotación") },
  { value: "declive", label: tx("En declive") },
];

interface PositionRow {
  position: string;
  label: string;
  rating: number;
  isSpecialRole: boolean;
}

/** Semana ISO (lunes-domingo) de una fecha, para que ningún timeline tenga
 * más de un punto por semana aunque se sincronice varias veces al día. */
function isoWeekKey(dateStr: string): string {
  const d = new Date(dateStr);
  const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const dayNum = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
  const weekNo = Math.ceil(
    ((date.getTime() - yearStart.getTime()) / 86400000 + 1) / 7,
  );
  return `${date.getUTCFullYear()}-W${String(weekNo).padStart(2, "0")}`;
}

/** Un punto por semana ISO por cada serie: el último valor visto esa
 * semana, no todos, HL-15x #101, aplicado a cualquier timeline (TSI,
 * habilidades, rating por partido), no solo TSI. */
function bucketWeekly(
  dates: string[],
  series: { name: string; values: number[] }[],
  seasonWeeks?: (string | null)[],
): { labels: string[]; series: { name: string; values: number[] }[] } {
  const weekKeys = dates.map(isoWeekKey);
  const lastIndexForWeek = new Map<string, number>();
  const order: string[] = [];
  weekKeys.forEach((wk, i) => {
    if (!lastIndexForWeek.has(wk)) order.push(wk);
    lastIndexForWeek.set(wk, i);
  });
  const indices = order.map((wk) => lastIndexForWeek.get(wk) as number);
  const labels = indices.map(
    (i) => seasonWeeks?.[i] ?? (dates[i] ?? "").slice(0, 10),
  );
  return {
    labels,
    series: series.map((s) => ({
      name: s.name,
      values: indices.map((i) => s.values[i] ?? 0),
    })),
  };
}

/** Los índices siempre vienen de un filtro de fechas construido sobre las
 * mismas `labels`/`series` que se recortan aquí, así que la posición
 * siempre existe. */
function pick<T>(items: T[], indices: number[]): T[] {
  return indices.map((i) => items[i] as T);
}

function rankInSquad(
  values: number[],
  own: number,
): { rank: number; total: number } {
  const sorted = [...values].sort((a, b) => b - a);
  const idx = sorted.findIndex((v) => v === own);
  return { rank: idx === -1 ? sorted.length : idx + 1, total: sorted.length };
}

/**
 * Ficha de jugador, el hub al que apunta todo nombre clickeable del
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
  if (!data) return <Empty>{tx("Jugador no encontrado.")}</Empty>;

  // 2026-08-05, pedido explícitamente: un ex-jugador (venta real o
  // despido, `left_team_at` sin `sold_at`) no tiene el resto del
  // dashboard (habilidades, posiciones, entrenamiento…), así que se
  // separa en un componente aparte ANTES de cualquier hook que dependa de
  // campos que solo trae `ActivePlayerDetail`, TypeScript ya lo obliga
  // (unión discriminada por `isExPlayer`), y evita repetir el guard
  // "por si acaso" dentro de cada `useMemo`.
  if (data.isExPlayer) return <ExPlayerDashboard data={data} />;
  return <ActivePlayerDashboard data={data} />;
}

function ActivePlayerDashboard({ data }: { data: ActivePlayerDetail }) {
  const id = data.htPlayerId;
  const qc = useQueryClient();

  const tsiWeekly = useMemo(
    () =>
      bucketWeekly(
        data.history.dates,
        [
          { name: "TSI", values: data.history.tsi },
          { name: tx("Salario"), values: data.history.salary },
        ],
        data.history.seasonWeeks,
      ),
    [data],
  );
  const htmsWeekly = useMemo(
    () =>
      bucketWeekly(
        data.history.dates,
        [
          { name: "HTMS", values: data.history.htms },
          { name: "HTMS28", values: data.history.htms28 },
        ],
        data.history.seasonWeeks,
      ),
    [data],
  );
  const skillsWeekly = useMemo(() => {
    const axes = Object.keys(data.history.skills);
    return bucketWeekly(
      data.history.dates,
      axes.map((k) => ({
        name: SKILL_LABELS[k] ?? k,
        values: data.history.skills[k] ?? [],
      })),
      data.history.seasonWeeks,
    );
  }, [data]);
  const matchRatingWeekly = useMemo(
    () =>
      bucketWeekly(
        data.matchRatingHistory.map((m) => m.date),
        [
          {
            name: tx("Rating"),
            values: data.matchRatingHistory.map((m) => m.rating),
          },
        ],
        data.matchRatingHistory.map((m) => m.seasonWeek),
      ),
    [data],
  );
  const skillsRange = useDateRangeFilter(skillsWeekly.labels);
  const tsiRange = useDateRangeFilter(tsiWeekly.labels);
  const htmsRange = useDateRangeFilter(htmsWeekly.labels);
  const matchRatingRange = useDateRangeFilter(matchRatingWeekly.labels);
  const confirmStage = useMutation({
    mutationFn: (stage: string | null) =>
      api.confirmCareerStage(TEAM_ID, id, stage),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["player", TEAM_ID, id] }),
  });

  const bestPosition = data.positions[0];
  const top10Positions = data.positions.slice(0, 10);

  // HL-15x #1+#24+#94: 3 radares agrupados, pasado-vs-hoy (fusión aprobada
  // por el usuario), del historial real de snapshots. Con un solo punto
  // real todavía (cuenta nueva) se muestra una sola capa: no hay "antes"
  // que comparar, y fingir uno sería inventar datos.
  const histDates = data.history.dates;
  const histSkills = data.history.skills;
  const histSeasonWeeks = data.history.seasonWeeks;
  const oldestIdx = 0;
  const latestIdx = histDates.length - 1;
  // HL-15x, pedido explícito 2026-08-10: el punto "más antiguo" del radar
  // debería anclarse a cuándo el jugador entró al equipo (más honesto que
  // "la primera vez que sincronizamos", que puede ser meses después)
  // `joinedSeasonWeek` ya trae ese respaldo (compra real → manual). Sin
  // ninguna de las dos, se cae al primer snapshot real de siempre.
  const oldestLabel =
    data.joinedSeasonWeek ??
    histSeasonWeeks[oldestIdx] ??
    (histDates[oldestIdx] ?? "").slice(0, 10);
  const latestLabel =
    histSeasonWeeks[latestIdx] ?? (histDates[latestIdx] ?? "").slice(0, 10);
  const axisValues = (axes: string[], idx: number) =>
    axes.map((k) => histSkills[k]?.[idx] ?? 0);
  const radarSeriesFor = (axes: string[]) =>
    histDates.length === 0
      ? []
      : histDates.length === 1
        ? [{ name: latestLabel || "Hoy", value: axisValues(axes, latestIdx) }]
        : [
            { name: oldestLabel, value: axisValues(axes, oldestIdx) },
            { name: latestLabel, value: axisValues(axes, latestIdx) },
          ];

  const ownAgeTsi = data.squadAgeTsi.find(
    (p) => p.htPlayerId === data.htPlayerId,
  );
  const tsiRank = data.squadDistributions
    ? rankInSquad(
        data.squadDistributions.tsi.values,
        data.squadDistributions.tsi.ownValue,
      )
    : null;
  const salaryRank = data.squadDistributions
    ? rankInSquad(
        data.squadDistributions.salary.values,
        data.squadDistributions.salary.ownValue,
      )
    : null;

  const positionColumns: Column<PositionRow>[] = [
    {
      key: "label",
      header: tx("Posición"),
      align: "left",
      value: (r) => r.label,
    },
    {
      key: "rating",
      header: tx("Rating"),
      value: (r) => r.rating,
      render: (r) => (
        <b className="tabular-nums text-[var(--accent)]">
          {r.rating.toFixed(2)}
        </b>
      ),
    },
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
  const effectiveStageKey =
    data.careerStage.confirmedStage ?? data.careerStage.stage;

  // HL-15x #100: agresividad va al revés que carácter/honestidad, nivel
  // bajo (p.ej. "calmada") es el rasgo deseable, así que se invierte para
  // que "lejos del centro" signifique lo mismo en los 3 ejes.
  const aggressivenessPlotted = data.character
    ? 5 - data.character.aggressiveness
    : 0;

  // HL-15x, pedido explícito 2026-08-10: 5 barras parejas (habilidad
  // entrenada, Experiencia, Fidelidad, Forma, Resistencia) en vez de
  // paneles de distinto tamaño, cada una con su propia forma de calcular
  // el tramo rojo, nunca el mismo número reciclado. Ver mockup aprobado en
  // conversación y ProgressBar en components/Panels.tsx.
  const trainedSkill = data.training.trainedSkill;
  const trainedSkillLabel = trainedSkill
    ? (SKILL_LABELS[trainedSkill] ?? trainedSkill)
    : tx("Sin entrenamiento");
  const trainedSkillLevel =
    trainedSkill === "stamina"
      ? data.stamina
      : trainedSkill
        ? (data.skills[trainedSkill] ?? 0)
        : 0;
  const trainedSkillMax = trainedSkill === "stamina" ? 9 : 20;
  const trainedSkillRedFraction =
    data.playedThisWeek && data.training.weeklyProgressPct != null
      ? data.training.weeklyProgressPct / 100
      : 0;

  const expPoints = data.experienceProgress?.points ?? 0;
  const expPerLevel = data.experienceProgress?.pointsPerLevel ?? 0;
  const expRedFraction =
    expPerLevel > 0 ? Math.min(expPoints / expPerLevel, 0.99) : 0;
  const expValueLabel = data.experienceProgress
    ? (data.experience + expRedFraction).toFixed(2)
    : String(data.experience);

  const loyaltyLevel =
    data.loyaltyDecimal != null
      ? Math.floor(data.loyaltyDecimal)
      : (data.loyalty ?? 0);
  const loyaltyRedFraction =
    data.loyaltyDecimal != null ? data.loyaltyDecimal - loyaltyLevel : 0;
  const loyaltyValueLabel =
    data.loyaltyDecimal != null
      ? data.loyaltyDecimal.toFixed(2)
      : String(data.loyalty ?? 0);

  const staminaExpected = data.staminaForecast?.currentExpectedLevel ?? null;
  const staminaDiff =
    staminaExpected != null ? staminaExpected - data.stamina : 0;

  return (
    <div className="space-y-4">
      <header>
        <Link
          to="/team"
          className="text-xs text-[var(--accent)] hover:underline"
        >
          {tx("← Jugadores")}
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold">{data.name}</h1>
          <span
            className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${
              stageTone[effectiveStageKey] ??
              "text-[var(--muted)] border-[var(--border)]"
            }`}
          >
            {effectiveLabel}{" "}
            {confirmedOption ? tx("· confirmado") : tx("· sugerido")}
          </span>
        </div>
        <p className="text-sm text-[var(--muted)]">
          {data.team.name} ·{" "}
          {htAge(
            Number(data.age.split(".")[0]),
            Number(data.age.split(".")[1]),
          )}{" "}
          {tx("años")}
          {bestPosition &&
            ` · ${bestPosition.label} (${bestPosition.rating.toFixed(2)})`}
          {data.nativeLeagueName && ` · ${data.nativeLeagueName}`}
        </p>
      </header>

      <Panel
        title={tx("Momento de la carrera")}
        meta={tx("sugerencia con confianza {{v0}}", {
          v0: data.careerStage.confidence,
        })}
      >
        <div className="space-y-2 p-4">
          <p className="text-sm">{data.careerStage.rationale}</p>
          <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-[var(--muted)]">
            <span>
              {tx("Habilidades subiendo:")}{" "}
              {String(data.careerStage.signals.skillsRising)}
            </span>
            <span>
              {tx("Bajando:")} {String(data.careerStage.signals.skillsFalling)}
            </span>
            <span>
              {tx("Estables:")} {String(data.careerStage.signals.skillsStable)}
            </span>
            <span>
              {tx("Factor de edad:")}{" "}
              {Number(data.careerStage.signals.ageFactor).toFixed(3)}
            </span>
            {data.careerStage.signals.squadPercentile != null && (
              <span>
                {tx("Percentil en plantilla:")}{" "}
                {Number(data.careerStage.signals.squadPercentile).toFixed(1)}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 pt-1">
            <label
              className="text-xs text-[var(--muted)]"
              htmlFor="career-stage-confirm"
            >
              {tx("Tu confirmación:")}
            </label>
            <select
              id="career-stage-confirm"
              className="rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-xs"
              value={data.careerStage.confirmedStage ?? ""}
              disabled={confirmStage.isPending}
              onChange={(e) => confirmStage.mutate(e.target.value || null)}
            >
              <option value="">
                {tx("Sin confirmar, usar sugerencia de la app")}
              </option>
              {CAREER_STAGE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </Panel>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(20rem,0.72fr)] [&>*]:min-w-0">
        <div className="space-y-4">
          <Panel title={tx("Ficha del jugador")}>
            <dl className="grid gap-x-6 gap-y-2 p-4 text-sm sm:grid-cols-2">
              <div className="flex justify-between gap-3">
                <dt className="text-[var(--muted)]">{tx("PlayerID")}</dt>
                <dd className="tabular-nums">{data.htPlayerId}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-[var(--muted)]">{tx("Edad")}</dt>
                <dd>{htAgeTexto(data.age)}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-[var(--muted)]">{tx("Nacionalidad")}</dt>
                <dd>
                  <CountryCell
                    code={data.countryCode}
                    country={data.nativeLeagueName}
                    fallback={tx("País #{{v0}}", { v0: data.countryId })}
                    compact
                  />
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-[var(--muted)]">{tx("Especialidad")}</dt>
                <dd>
                  <Specialty specialty={data.specialty} />
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-[var(--muted)]">{tx("Carácter")}</dt>
                <dd>
                  {data.character
                    ? `${nivelOficial("simpatia", data.character.agreeability) ?? data.character.agreeabilityLabel} (${data.character.agreeability})`
                    : "-"}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-[var(--muted)]">{tx("Agresividad")}</dt>
                <dd>
                  {data.character
                    ? `${nivelOficial("agresividad", data.character.aggressiveness) ?? data.character.aggressivenessLabel} (${data.character.aggressiveness})`
                    : "-"}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-[var(--muted)]">{tx("Honestidad")}</dt>
                <dd>
                  {data.character
                    ? `${nivelOficial("honradez", data.character.honesty) ?? data.character.honestyLabel} (${data.character.honesty})`
                    : "-"}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-[var(--muted)]">{tx("Liderazgo")}</dt>
                <dd>
                  {skillLevel(data.leadership)} ({data.leadership})
                </dd>
              </div>
            </dl>
          </Panel>

          <Panel title={tx("Habilidades")}>
            <div className="grid gap-x-8 gap-y-4 p-4 sm:grid-cols-2">
              {DETAIL_SKILLS.map((skill) => {
                const value =
                  skill === "experience"
                    ? data.experience
                    : skill === "form"
                      ? data.form
                      : skill === "stamina"
                        ? data.stamina
                        : (data.skills[skill] ?? 0);
                const max = skill === "form" ? 8 : skill === "stamina" ? 9 : 20;
                return (
                  <SkillBar
                    key={skill}
                    label={SKILL_LABELS[skill] ?? skill}
                    value={value}
                    max={max}
                  />
                );
              })}
            </div>
          </Panel>
        </div>

        <div className="space-y-4">
          <Panel
            title={tx("Estado y contrato")}
            meta={
              data.isTransferListed ? tx("en venta") : tx("no está en venta")
            }
          >
            <dl className="space-y-2 p-4 text-sm">
              <div className="flex justify-between gap-3">
                <dt className="text-[var(--muted)]">TSI</dt>
                <dd className="font-semibold tabular-nums">
                  {number(data.tsi)}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-[var(--muted)]">HTMS</dt>
                <dd className="font-semibold tabular-nums">
                  {number(data.htms)}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-[var(--muted)]">HTMS28</dt>
                <dd className="font-semibold tabular-nums">
                  {number(data.htms28)}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-[var(--muted)]">{tx("Salario")}</dt>
                <dd className="font-semibold tabular-nums">
                  {money(data.salary)}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-[var(--muted)]">{tx("Precio compra")}</dt>
                <dd>
                  {data.purchasePrice == null
                    ? tx("no disponible")
                    : money(data.purchasePrice)}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-[var(--muted)]">{tx("Fecha compra")}</dt>
                <dd>
                  {data.purchasedAt
                    ? date(data.purchasedAt)
                    : tx("no disponible")}
                </dd>
              </div>
              {/* Nivel 0 es magullado y SÍ puede jugar: pintarlo en rojo como
                  una baja hacía pensar que estaba descartado. Solo desde 1
                  (semanas de baja) es una lesión de verdad. */}
              <div className="flex justify-between gap-3">
                <dt className="text-[var(--muted)]">{tx("Lesión")}</dt>
                <dd
                  className={
                    data.injuryLevel >= 1
                      ? "text-[var(--danger)]"
                      : data.injuryLevel === 0
                        ? "text-[var(--warning)]"
                        : "text-[var(--muted)]"
                  }
                >
                  {data.injuryLevel >= 1
                    ? tx("{{v0}} semana(s)", { v0: data.injuryLevel })
                    : data.injuryLevel === 0
                      ? tx("magullado")
                      : tx("sin lesión")}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-[var(--muted)]">{tx("Último partido")}</dt>
                <dd className="text-right">
                  {data.lastMatch
                    ? `${data.lastMatch.position} · ${data.lastMatch.rating?.toFixed(1) ?? "-"}`
                    : tx("sin detalle")}
                </dd>
              </div>
            </dl>
          </Panel>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 [&>*]:min-w-0">
        <Kpi
          label="TSI"
          value={number(data.tsi)}
          hint={
            tsiRank
              ? tx("puesto {{v0}} de {{v1}} en la plantilla", {
                  v0: tsiRank.rank,
                  v1: tsiRank.total,
                })
              : undefined
          }
        />
        <Kpi
          label={tx("Salario")}
          value={money(data.salary)}
          hint={
            salaryRank
              ? tx("puesto {{v0}} de {{v1}} en la plantilla", {
                  v0: salaryRank.rank,
                  v1: salaryRank.total,
                })
              : undefined
          }
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3 [&>*]:min-w-0">
        {RADAR_GROUPS.map((group) => (
          <Panel
            key={group.title}
            title={group.title}
            meta={
              histDates.length > 1
                ? `${oldestLabel} → ${latestLabel}`
                : tx("sin historial suficiente")
            }
          >
            <div className="p-4">
              <Chart
                ariaLabel={tx("Radar de {{v0}}", {
                  v0: group.title.toLowerCase(),
                })}
                height={260}
                option={radarOption(
                  group.axes.map((k) => ({
                    name: SKILL_LABELS[k] ?? k,
                    max: 20,
                  })),
                  radarSeriesFor(group.axes),
                )}
              />
            </div>
          </Panel>
        ))}
      </div>

      <Panel
        title={tx("Mejores posiciones")}
        meta={tx("top 10 de 19 + roles especiales")}
      >
        <DataTable
          rows={top10Positions}
          columns={positionColumns}
          rowKey={(r) => r.position}
          initialSort="rating"
          csvName={`${data.name}-posiciones`}
          emptyMessage={tx("Sin datos de posición.")}
        />
      </Panel>

      <Panel
        title={tx("Precio de compra")}
        meta={tx("real, de tu libro de transferencias")}
      >
        {data.purchasePrice != null ? (
          <div className="space-y-1 p-4">
            <div className="text-2xl font-semibold tabular-nums">
              {money(data.purchasePrice)}
            </div>
            <div className="text-xs text-[var(--muted)]">
              {data.purchasedAt
                ? `${data.purchasedAtSeasonWeek ?? date(data.purchasedAt)}`
                : tx("fecha no disponible")}
            </div>
          </div>
        ) : (
          <Empty>
            {tx("Sin compra registrada en el historial reciente del equipo.")}
          </Empty>
        )}
      </Panel>

      {/* Pedido explícito 2026-08-10: adenda, no panel principal, por eso
          NO usa <Panel> (borde sólido + título en negrita como el resto de
          la ficha), sino un borde punteado y una etiqueta pequeña/muted. */}
      <div className="rounded-lg border border-dashed border-[var(--border)] p-4">
        <div className="mb-3">
          <span className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
            {tx("Habilidades susceptibles a mejorar")}
          </span>
          <p className="mt-0.5 text-xs text-[var(--muted)]">
            {tx(
              "progreso real hacia el siguiente nivel de cada variable entrenable",
            )}
          </p>
        </div>
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          <ProgressBar
            label={trainedSkillLabel}
            level={trainedSkillLevel}
            max={trainedSkillMax}
            valueLabel={`${trainedSkillLevel} / ${trainedSkillMax}`}
            redFraction={trainedSkillRedFraction}
            redPlacement="append"
            tooltip={tx(
              "Se entrena semana a semana con la fórmula del Manual No Escrito (ver Motor). El rojo es el ritmo semanal esperado, solo aparece si jugó un partido esta semana.",
            )}
          />
          <ProgressBar
            label={tx("Experiencia")}
            level={data.experience}
            max={20}
            valueLabel={`${expValueLabel} / 20`}
            redFraction={expRedFraction}
            redPlacement="append"
            tooltip={tx(
              "Sube por partidos reales jugados (liga, copa, amistosos, selección…), cada uno pesa puntos distintos según su tipo. El rojo son los puntos ya acumulados hacia el siguiente nivel.",
            )}
          />
          <ProgressBar
            label={tx("Fidelidad")}
            level={loyaltyLevel}
            max={20}
            valueLabel={`${loyaltyValueLabel} / 20`}
            redFraction={loyaltyRedFraction}
            redPlacement="append"
            tooltip={tx(
              "Sube solo con tiempo en el club, Hattrick no publica la fórmula. Se calibra por observación propia, transición por transición (ver Motor). El rojo son los días ya transcurridos hacia la siguiente subida, cuando ya hay calibración.",
            )}
          />
          <ProgressBar
            label={tx("Forma")}
            level={data.form}
            max={8}
            valueLabel={`${data.form} / 8`}
            dot={data.playedThisWeek}
            tooltip={tx(
              "Fluctúa partido a partido según rendimiento, no tenemos fórmula propia, solo la observamos. El punto rojo indica que jugó un partido esta semana.",
            )}
          />
          <ProgressBar
            label={tx("Resistencia")}
            level={data.stamina}
            max={9}
            valueLabel={`${data.stamina} / 9`}
            redFraction={Math.abs(staminaDiff)}
            redPlacement={staminaDiff < 0 ? "eat" : "append"}
            tooltip={tx(
              "Sube o baja según el % real de entrenamiento dedicado a resistencia para tu edad (la tabla de referencia está en Motor). El rojo muestra si al ritmo actual se espera subir o bajar de nivel.",
            )}
          />
        </div>
        {data.experienceProgress &&
          data.experienceProgress.unscoredNationalMatches > 0 && (
            <div className="mt-3 text-xs text-[var(--accent)]">
              + {data.experienceProgress.unscoredNationalMatches}{" "}
              {tx(
                "partido(s) de selección detectado(s) desde entonces sin puntaje exacto, o es competitivo (Hattrick no distingue Mundial/Copa continental/Copa de Naciones con el mismo código) o subió el conteo de partidos con la selección (Caps) sin que alcanzáramos a ver ese partido en concreto (el club jugó después y lo tapó antes del siguiente sync).",
              )}
            </div>
          )}
      </div>

      {data.character && (
        <Panel
          title={tx("Carácter")}
          meta={tx("lejos del centro = rasgo deseable en los 3 ejes")}
        >
          <div className="p-4">
            <Chart
              ariaLabel={tx(
                "Perfil de carácter: carácter, agresividad, honestidad",
              )}
              height={280}
              option={radarOption(
                [
                  {
                    name: `${tx("Carácter")} (${nivelOficial("simpatia", data.character.agreeability) ?? data.character.agreeabilityLabel})`,
                    max: 5,
                  },
                  {
                    name: `${tx("Agresividad")} (${nivelOficial("agresividad", data.character.aggressiveness) ?? data.character.aggressivenessLabel})`,
                    max: 5,
                  },
                  {
                    name: `${tx("Honestidad")} (${nivelOficial("honradez", data.character.honesty) ?? data.character.honestyLabel})`,
                    max: 5,
                  },
                ],
                [
                  {
                    name: data.name,
                    value: [
                      data.character.agreeability,
                      aggressivenessPlotted,
                      data.character.honesty,
                    ],
                  },
                ],
              )}
            />
          </div>
        </Panel>
      )}

      {data.topSkillDistributions && (
        <div className="grid gap-4 lg:grid-cols-3 [&>*]:min-w-0">
          {Object.entries(data.topSkillDistributions).map(([skill, dist]) => (
            <PlayerDistributionPanel
              key={skill}
              title={tx("{{v0}} en la plantilla", {
                v0: SKILL_LABELS[skill] ?? skill,
              })}
              xLabel={SKILL_LABELS[skill] ?? skill}
              playerName={data.name}
              distribution={dist}
              formatValue={(v) => v.toFixed(0)}
            />
          ))}
        </div>
      )}

      {data.squadDistributions && (
        <div className="grid gap-4 lg:grid-cols-3 [&>*]:min-w-0">
          <PlayerDistributionPanel
            title={tx("TSI en la plantilla")}
            xLabel="TSI"
            playerName={data.name}
            distribution={data.squadDistributions.tsi}
            formatValue={(v) => number(v)}
          />
          <PlayerDistributionPanel
            title={tx("Salario en la plantilla")}
            xLabel={tx("Salario")}
            playerName={data.name}
            distribution={data.squadDistributions.salary}
            formatValue={(v) => money(v)}
          />
          <PlayerDistributionPanel
            title={tx("$ por punto de TSI")}
            xLabel="$/TSI"
            playerName={data.name}
            distribution={data.squadDistributions.salaryPerTsi}
            formatValue={(v) => v.toFixed(2)}
          />
        </div>
      )}

      <Panel
        title={tx("Evolución de habilidades")}
        meta={
          skillsWeekly.labels.length > 1
            ? tx("1 punto por semana ISO como mínimo")
            : tx("historial corto todavía")
        }
      >
        {skillsWeekly.labels.length > 1 ? (
          <div className="p-4">
            <div className="mb-3">
              <DateRangeFilter
                range={skillsRange.range}
                onChange={skillsRange.setRange}
                min={skillsRange.min}
                max={skillsRange.max}
              />
            </div>
            {EVOLUCION_GRUPOS.map((grupo) => {
              const series = grupo.skills.flatMap((k) => {
                const s = skillsWeekly.series.find(
                  (x) => x.name === (SKILL_LABELS[k] ?? k),
                );
                return s
                  ? [
                      {
                        name: s.name,
                        values: pick(s.values, skillsRange.indices),
                      },
                    ]
                  : [];
              });
              if (series.length === 0) return null;
              return (
                <div key={grupo.titulo} className="mt-5 first:mt-0">
                  <h3 className="mb-1 text-xs font-medium text-[var(--text)]">
                    {grupo.titulo}
                  </h3>
                  <Chart
                    ariaLabel={tx("Evolución semanal de {{v0}}", {
                      v0: grupo.titulo.toLowerCase(),
                    })}
                    height={240}
                    option={timelineOption(
                      pick(skillsWeekly.labels, skillsRange.indices),
                      series,
                    )}
                  />
                </div>
              );
            })}
          </div>
        ) : (
          <Empty>
            {tx(
              "Todavía no hay dos semanas distintas de historial real, esta gráfica se llena a medida que se sincroniza.",
            )}
          </Empty>
        )}
      </Panel>

      <Panel
        title={tx("Evolución de TSI y salario")}
        meta={tx("1 punto por semana ISO como mínimo")}
      >
        {tsiWeekly.labels.length > 1 ? (
          <div className="p-4">
            <div className="mb-3">
              <DateRangeFilter
                range={tsiRange.range}
                onChange={tsiRange.setRange}
                min={tsiRange.min}
                max={tsiRange.max}
              />
            </div>
            <Chart
              ariaLabel={tx(
                "Evolución semanal del TSI y el salario del jugador",
              )}
              height={240}
              option={timelineOption(
                pick(tsiWeekly.labels, tsiRange.indices),
                tsiWeekly.series.map((s) => ({
                  name: s.name,
                  values: pick(s.values, tsiRange.indices),
                })),
              )}
            />
          </div>
        ) : (
          <Empty>
            {tx(
              "Todavía no hay dos semanas distintas de historial real para trazar una evolución.",
            )}
          </Empty>
        )}
      </Panel>

      <Panel
        title={tx("Evolución del HTMS")}
        meta={tx(
          "HTMS28 es una proyección con entrenamiento estándar, no una promesa",
        )}
      >
        {htmsWeekly.labels.length > 1 ? (
          <div className="p-4">
            <div className="mb-3">
              <DateRangeFilter
                range={htmsRange.range}
                onChange={htmsRange.setRange}
                min={htmsRange.min}
                max={htmsRange.max}
              />
            </div>
            <Chart
              ariaLabel={tx(
                "Evolución semanal del HTMS y el HTMS28 del jugador",
              )}
              height={240}
              option={timelineOption(
                pick(htmsWeekly.labels, htmsRange.indices),
                htmsWeekly.series.map((s) => ({
                  name: s.name,
                  values: pick(s.values, htmsRange.indices),
                })),
              )}
            />
          </div>
        ) : (
          <Empty>
            {tx(
              "Todavía no hay dos semanas distintas de historial real para trazar una evolución.",
            )}
          </Empty>
        )}
      </Panel>

      <Panel
        title={tx("Rating por partido")}
        meta={
          matchRatingWeekly.labels.length > 0
            ? tx("{{v0}} semana(s) real(es), 1 punto por semana", {
                v0: matchRatingWeekly.labels.length,
              })
            : tx("sin partidos sincronizados todavía")
        }
      >
        {matchRatingWeekly.labels.length > 0 ? (
          <div className="p-4">
            <div className="mb-3">
              <DateRangeFilter
                range={matchRatingRange.range}
                onChange={matchRatingRange.setRange}
                min={matchRatingRange.min}
                max={matchRatingRange.max}
              />
            </div>
            <Chart
              ariaLabel={tx(
                "Rating real del jugador por semana, un punto por partido más reciente",
              )}
              height={220}
              option={timelineOption(
                pick(matchRatingWeekly.labels, matchRatingRange.indices),
                matchRatingWeekly.series.map((s) => ({
                  name: s.name,
                  values: pick(s.values, matchRatingRange.indices),
                })),
              )}
            />
          </div>
        ) : (
          <Empty>
            {tx(
              "Se llena partido a partido al sincronizar, hoy no hay ninguno todavía en esta cuenta.",
            )}
          </Empty>
        )}
      </Panel>

      {ownAgeTsi && (
        <Panel title={tx("TSI vs. edad de la plantilla")}>
          <div className="p-4">
            <Chart
              ariaLabel={tx(
                "Dispersión de TSI contra edad de toda la plantilla, con este jugador resaltado",
              )}
              height={280}
              option={highlightedScatterOption(
                data.squadAgeTsi.map((p) => ({
                  x: p.age,
                  y: p.tsi,
                  label: p.name,
                })),
                { x: ownAgeTsi.age, y: ownAgeTsi.tsi, label: data.name },
                // Con `tx`, no en crudo: el nombre del eje es texto de
                // pantalla y se quedaba en español (2026-09-20, visto por el
                // usuario). «TSI» no, que se llama igual en los dos idiomas.
                tx("Edad"),
                "TSI",
              )}
            />
          </div>
        </Panel>
      )}
    </div>
  );
}

/**
 * Ficha de EX-jugador, pedido explícitamente 2026-08-05: nada de
 * habilidades/posiciones/entrenamiento (no tiene sentido para alguien que
 * ya no vemos), solo las fechas en que estuvo en el equipo y las partes
 * del cálculo del ROI, en cuadritos, mismo dato ya calculado por
 * `usePlayerBalance` (el que alimenta "Detalle" en Transferencias),
 * nunca un cálculo aparte.
 */
function ExPlayerDashboard({ data }: { data: ExPlayerDetail }) {
  const { data: balance, isLoading, isError, error } = usePlayerBalance();

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;

  const row = balance?.players.find((p) => p.htPlayerId === data.htPlayerId);
  const listingCostPerAttempt =
    row && row.listingCount > 0 ? row.listingCost / row.listingCount : 0;
  const undatedListingCount = row
    ? Math.max(row.listingCount - row.listingAttempts.length, 0)
    : 0;

  return (
    <div className="space-y-4">
      <header>
        <Link
          to="/transfers/balance"
          className="text-xs text-[var(--accent)] hover:underline"
        >
          {tx("← Transferencias")}
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold">{data.name}</h1>
          <span className="rounded-full border px-2.5 py-0.5 text-xs font-medium text-[var(--muted)] border-[var(--border)]">
            {tx("Ex-jugador")}
          </span>
          {row?.isAcademyGraduate && (
            <span className="rounded-full border px-2.5 py-0.5 text-xs font-medium text-[var(--positive)] border-[var(--positive)]">
              {tx("Canterano")}
            </span>
          )}
        </div>
        <p className="text-sm text-[var(--muted)]">
          {tx(
            "Ya no está en la plantilla, esta ficha solo trae las fechas y el saldo, no el resto del análisis de plantilla.",
          )}
        </p>
      </header>

      <Panel title={tx("Tiempo en el equipo")}>
        <dl className="grid gap-x-6 gap-y-2 p-4 text-sm sm:grid-cols-2">
          <div className="flex justify-between gap-3">
            <dt className="text-[var(--muted)]">{tx("Fecha de compra")}</dt>
            <dd className="tabular-nums">{date(data.purchasedAt)}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-[var(--muted)]">
              {row?.isDepartureWithoutSale
                ? tx("Fecha de salida")
                : tx("Fecha de venta")}
            </dt>
            <dd className="tabular-nums">
              {date(data.soldAt ?? data.leftTeamAt)}
              {row?.isDepartureWithoutSale && (
                <span className="text-[var(--muted)]">
                  {" "}
                  {tx("(despedido)")}
                </span>
              )}
            </dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-[var(--muted)]">
              {tx("Partidos jugados con nosotros")}
            </dt>
            <dd className="tabular-nums">
              {data.gamesWithUs != null ? (
                data.gamesWithUs
              ) : (
                <span className="text-[var(--muted)]">{tx("sin contar")}</span>
              )}
            </dd>
          </div>
          {data.resaleClosed && (
            <div className="flex justify-between gap-3">
              <dt className="text-[var(--muted)]">{tx("Comisión futura")}</dt>
              <dd
                className="text-[var(--muted)]"
                title={
                  data.resaleClosedReason === "revendido"
                    ? tx(
                        "El club que te lo compró ya lo revendió: esa comisión se cobró y no habrá otra.",
                      )
                    : data.resaleClosedReason === "despedido"
                      ? tx(
                          "Ya no existe en Hattrick, así que nadie volverá a venderlo.",
                        )
                      : tx(
                          "Salió sin comprador, así que nunca hubo club anterior al que pagarle.",
                        )
                }
              >
                {tx("ya no")}
              </dd>
            </div>
          )}
        </dl>
      </Panel>

      {row ? (
        <>
          <Panel
            title={tx("Entrenamiento inferido al vender")}
            meta={tx(
              "primer snapshot contra último snapshot anterior a la venta",
            )}
          >
            <div className="grid gap-4 p-4 sm:grid-cols-3 [&>*]:min-w-0">
              <Kpi
                label={tx("Habilidad asignada")}
                value={row.derivedTrainingSkill ?? tx("Sin resolver")}
              />
              <Kpi
                label={tx("Niveles subidos")}
                value={
                  row.derivedTrainingLevels != null
                    ? number(row.derivedTrainingLevels)
                    : "-"
                }
              />
              <Kpi
                label={tx("Método")}
                value={row.derivedTrainingMethodLabel}
              />
            </div>
          </Panel>
          <Panel
            title={tx("Cálculo del ROI")}
            meta={tx("mismo desglose que Detalle en Transferencias")}
          >
            <div className="grid gap-4 p-4 sm:grid-cols-2 xl:grid-cols-4 [&>*]:min-w-0">
              {/* De la cantera no se paga precio de mercado, se paga el
                  ascenso: el rótulo lo dice para que la cifra no se lea como
                  un fichaje que nunca hubo. */}
              <Kpi
                label={
                  row.isAcademyGraduate
                    ? tx("Coste del ascenso")
                    : tx("Precio de compra")
                }
                value={
                  row.purchasePrice != null
                    ? money(row.purchasePrice, balance!.currency)
                    : "?"
                }
                hint={
                  row.isAcademyGraduate
                    ? tx("subido desde tu cantera")
                    : undefined
                }
              />
              <Kpi
                label={tx("Salario acumulado")}
                value={
                  row.salaryKnown
                    ? money(row.salaryTotal, balance!.currency)
                    : "?"
                }
                hint={
                  row.salaryKnown
                    ? undefined
                    : tx("Falta sincronizar el calendario económico de la liga")
                }
              />
              <Kpi
                label={tx("Costo de listados")}
                value={money(row.listingCost, balance!.currency)}
              />
              <Kpi
                label={tx("Precio de venta")}
                value={
                  row.salePrice != null
                    ? money(row.salePrice, balance!.currency)
                    : "-"
                }
                hint={row.isDepartureWithoutSale ? tx("despedido") : undefined}
              />
              <Kpi
                label={tx("% agente")}
                value={
                  row.agentPct != null
                    ? `${(row.agentPct * 100).toFixed(1)}%`
                    : "-"
                }
                hint={
                  row.agentPct != null && row.commissionAmount !== "?"
                    ? money(row.commissionAmount, balance!.currency)
                    : undefined
                }
              />
              <Kpi
                label={tx("Venta neta")}
                value={
                  row.salePrice != null && row.commissionAmount !== "?"
                    ? money(
                        row.salePrice - row.commissionAmount,
                        balance!.currency,
                      )
                    : "?"
                }
                hint={tx("precio de venta × (1 − % agente)")}
              />
              <Kpi
                label={tx("Club anterior")}
                value={money(row.resaleBonusShare, balance!.currency)}
                hint={
                  row.resaleBonusShare > 0
                    ? tx("comisión exacta cobrada por reventa(s) confirmada(s)")
                    : tx(
                        "el club al que se lo vendimos todavía no lo ha revendido",
                      )
                }
              />
              <Kpi
                label="ROI"
                value={row.roiPct !== "?" ? `${row.roiPct.toFixed(1)}%` : "?"}
                tone={
                  row.roiPct === "?"
                    ? undefined
                    : row.roiPct >= 0
                      ? "positive"
                      : "danger"
                }
              />
            </div>
          </Panel>
          {row.listingCount > 0 && (
            <Panel
              title={tx("Intentos de venta")}
              meta={
                row.listingAttempts.length < row.listingCount
                  ? tx(
                      "{{v0}} en total · {{v1}} por intento · {{v2}} de costo total · solo los {{v3}} más recientes quedaron registrados con fecha",
                      {
                        v0: number(row.listingCount),
                        v1: money(listingCostPerAttempt, balance!.currency),
                        v2: money(row.listingCost, balance!.currency),
                        v3: number(row.listingAttempts.length),
                      },
                    )
                  : tx(
                      "{{v0}} en total · {{v1}} por intento · {{v2}} de costo total",
                      {
                        v0: number(row.listingCount),
                        v1: money(listingCostPerAttempt, balance!.currency),
                        v2: money(row.listingCost, balance!.currency),
                      },
                    )
              }
            >
              <ul className="divide-y divide-[var(--border)] p-4 text-sm">
                {row.listingAttempts.map((attempt, i) => (
                  <li key={i} className="flex justify-between gap-3 py-1.5">
                    <span className="text-[var(--muted)]">
                      {date(attempt.detectedAt)}
                    </span>
                    <span className="tabular-nums font-medium">
                      {tx("Costo:")}{" "}
                      {money(listingCostPerAttempt, balance!.currency)}
                    </span>
                  </li>
                ))}
                {undatedListingCount > 0 && (
                  <li className="flex justify-between gap-3 py-1.5">
                    <span className="text-[var(--muted)]">
                      {number(undatedListingCount)} {tx("intento")}
                      {undatedListingCount === 1 ? "" : tx("s")}{" "}
                      {tx("anterior")}
                      {undatedListingCount === 1 ? "" : tx("es")}{" "}
                      {tx("sin fecha registrada")}
                    </span>
                    <span className="tabular-nums font-medium">
                      {tx("Costo:")}{" "}
                      {money(
                        undatedListingCount * listingCostPerAttempt,
                        balance!.currency,
                      )}
                    </span>
                  </li>
                )}
              </ul>
            </Panel>
          )}
          {row.salaryBreakdown.length > 0 && (
            <Panel
              title={tx("Desglose del salario")}
              meta={tx("tramos de semanas consecutivas con el mismo sueldo")}
            >
              <ul className="divide-y divide-[var(--border)] p-4 text-sm">
                {row.salaryBreakdown.map((segment, i) => (
                  <li key={i} className="flex justify-between gap-3 py-1.5">
                    <span className="text-[var(--muted)]">
                      {segment.weeks} {tx("cobro")}
                      {segment.weeks === 1 ? "" : tx("s")} {tx("en")}{" "}
                      {segment.season}
                    </span>
                    <span className="tabular-nums">
                      {number(segment.weeks)} ×{" "}
                      {money(segment.salary, balance!.currency)}
                      {" = "}
                      {money(segment.total, balance!.currency)}
                    </span>
                  </li>
                ))}
              </ul>
            </Panel>
          )}
          <Panel title={tx("Ganancia")}>
            <div className="p-4">
              <div
                className={
                  row.saldo == null
                    ? "text-2xl font-semibold text-[var(--muted)]"
                    : row.saldo >= 0
                      ? "text-2xl font-semibold tabular-nums text-[var(--positive)]"
                      : "text-2xl font-semibold tabular-nums text-[var(--danger)]"
                }
              >
                {row.saldo != null ? money(row.saldo, balance!.currency) : "-"}
              </div>
            </div>
          </Panel>
        </>
      ) : (
        <Empty>{tx("Sin datos de saldo todavía para este jugador.")}</Empty>
      )}
    </div>
  );
}
