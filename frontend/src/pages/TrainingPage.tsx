import { useState } from "react";
import { Link } from "react-router-dom";
import {
  useClub,
  usePlayerTrainingLevels,
  usePostMatchTraining,
  useTrainingDevelopment,
  useTrainingFormula,
  useTrainingSquad,
} from "../hooks/useTeam";
import { DataTable, type Column } from "../components/DataTable";
import { Empty, ErrorState, Kpi, Loading, Note, Panel, ProjectionPanel } from "../components/Panels";
import { PlayerLink } from "../components/PlayerLink";
import { Tabs } from "../components/Tabs";
import { Chart } from "../charts/Chart";
import { barOption } from "../charts/chartOptions";
import type {
  ClubStaffRole,
  ClubStaffRoleEffect,
  ConfirmedLevelUp,
  LevelForecastMilestone,
  PostMatchTrainingOption,
  TrainingExperienceRow,
  TrainingLoyaltyRow,
  TrainingSquadPlayerRow,
  TrainingSquadWeeklyLogEntry,
} from "../services/api";
import {
  staffEffectLines,
  trainerTrainingSpeedPct,
  trainingStaffLevelColor,
} from "../utils/staffEffects";
import { skillLevelLabel } from "../utils/skillLevels";

type TrainingSection = "datos" | "plantilla" | "experiencia" | "fidelidad" | "posteriori";
type PlayerTab = "mejoras" | "prevision";

const EXPERIENCE_TYPE_LABELS: Record<string, string> = {
  league: "Liga",
  cup: "Copa nacional",
  cup_secondary: "Copa secundaria",
  qualification: "Promoción",
  friendly: "Amistoso",
  friendly_international: "Amistoso internacional",
  tournament: "Torneo",
  masters: "Masters",
  national_team_friendly: "Selección amistoso",
  youth_league: "Liga juvenil",
  youth_friendly: "Amistoso juvenil",
};

function decimal(value: number, digits = 2): string {
  return value.toLocaleString("es-CO", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function ProgressCell({ value }: { value: number | null }) {
  if (value == null) return <span className="text-[var(--muted)]">sin referencia</span>;
  const bounded = Math.max(0, Math.min(100, value));
  return (
    <div className="flex min-w-28 items-center justify-end gap-2">
      <div className="h-2 w-20 overflow-hidden rounded-full bg-[var(--surface-2)]">
        <div className="h-full rounded-full bg-[var(--accent)]" style={{ width: `${bounded}%` }} />
      </div>
      <span className="w-9 text-right text-xs tabular-nums">{bounded.toFixed(0)}%</span>
    </div>
  );
}

function scaledEffect(
  effect: ClubStaffRoleEffect,
  memberLevel: number,
  combinedLevel: number,
): ClubStaffRoleEffect {
  const share = combinedLevel > 0 ? memberLevel / combinedLevel : 0;
  const scale = (value: number | undefined) =>
    value == null ? undefined : Number((value * share).toFixed(3));
  return {
    trainingSpeedPct: scale(effect.trainingSpeedPct),
    injuryRiskPp: scale(effect.injuryRiskPp),
    backgroundForm: scale(effect.backgroundForm),
  };
}

function AssistantCards({ role }: { role: ClubStaffRole }) {
  if (role.members.length === 0) {
    return (
      <p className="p-4 text-sm font-medium text-[var(--danger)]">
        Actualmente no hay asistentes de entrenador registrados.
      </p>
    );
  }

  return (
    <div className="space-y-4 p-4">
      <div className="grid gap-3 sm:grid-cols-2">
        {role.members.map((member) => {
          const lines = role.effect
            ? staffEffectLines(scaledEffect(role.effect, member.level, role.level))
            : [];
          return (
            <div key={member.name} className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-4">
              <div className="flex items-baseline justify-between gap-3">
                <strong className="text-sm">{member.name}</strong>
                <span className={`shrink-0 text-xs font-semibold tabular-nums ${trainingStaffLevelColor(member.level)}`}>
                  Nivel {member.level}/5
                </span>
              </div>
              {lines.length > 0 && (
                <ul className="mt-3 space-y-1 border-t border-[var(--border)] pt-3 text-xs text-[var(--positive)]">
                  {lines.map((line) => <li key={line}>{line}</li>)}
                </ul>
              )}
            </div>
          );
        })}
      </div>
      {role.effect && (
        <div className="rounded-md border border-[var(--border)] px-3 py-2">
          <p className="text-xs font-medium">Aporte combinado · nivel {role.level}</p>
          <ul className="mt-1 flex flex-wrap gap-x-5 gap-y-1 text-xs text-[var(--positive)]">
            {staffEffectLines(role.effect).map((line) => <li key={line}>{line}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

function squadColumns(skillLabel: string): Column<TrainingSquadPlayerRow>[] {
  return [
  {
    key: "training",
    header: "Entrenamiento",
    align: "left",
    value: () => skillLabel,
    render: () => <span className="font-medium">{skillLabel}</span>,
  },
  {
    key: "player",
    header: "Nombre",
    align: "left",
    value: (r) => r.name,
    render: (r) => <PlayerLink htPlayerId={r.htPlayerId} name={r.name} />,
  },
  {
    key: "nativeCountry",
    header: "Nac.",
    align: "left",
    value: (r) => r.nativeCountry ?? "",
    render: (r) => (
      <span className="text-xs text-[var(--muted)]">
        {r.nativeCountry ?? "—"}
      </span>
    ),
  },
  { key: "age", header: "Edad", value: (r) => parseFloat(r.age) },
  {
    key: "progress",
    header: "%",
    value: (r) => r.progressPct ?? -1,
    render: (r) =>
      r.progressPct == null ? (
        <span className="text-[var(--muted)]">sin dato</span>
      ) : (
        <div className="flex items-center justify-end gap-2">
          <div className="h-1.5 w-16 overflow-hidden rounded-full bg-[var(--surface-2)]">
            <div
              className="h-full bg-[var(--accent)]"
              style={{ width: `${Math.min(100, r.progressPct)}%` }}
            />
          </div>
          <span className="tabular-nums text-xs">{r.progressPct.toFixed(0)}%</span>
        </div>
      ),
  },
  {
    key: "weeks",
    header: "Semanas",
    value: (r) => r.weeksElapsed ?? -1,
    render: (r) => (
      <span className="tabular-nums whitespace-nowrap">
        {r.hasReference && r.weeksElapsed != null ? (
          r.weeksElapsed.toFixed(1)
        ) : (
          <span className="text-[var(--muted)]">—</span>
        )}
        <span className="text-[var(--muted)]"> / {r.weeksTotal.toFixed(1)}</span>
      </span>
    ),
  },
  {
    key: "level",
    header: "Nivel",
    value: (r) => r.level,
    render: (r) => (
      <span className="whitespace-nowrap">
        <span>{r.levelName}</span>{" "}
        <span className="text-xs tabular-nums text-[var(--muted)]">({r.level})</span>
      </span>
    ),
  },
  {
    key: "htPlayerId",
    header: "PlayerID",
    value: (r) => r.htPlayerId,
    render: (r) => <span className="tabular-nums text-xs">{r.htPlayerId}</span>,
  },
];
}

const experienceColumns: Column<TrainingExperienceRow>[] = [
  {
    key: "player",
    header: "Nombre",
    align: "left",
    value: (r) => r.name,
    render: (r) => <PlayerLink htPlayerId={r.htPlayerId} name={r.name} />,
  },
  {
    key: "nativeCountry",
    header: "Nac.",
    align: "left",
    value: (r) => r.nativeCountry ?? "",
    render: (r) => <span className="text-xs text-[var(--muted)]">{r.nativeCountry ?? "—"}</span>,
  },
  { key: "age", header: "Edad", value: (r) => parseFloat(r.age) },
  {
    key: "level",
    header: "Experiencia",
    value: (r) => r.decimalLevel ?? r.level,
    render: (r) => (
      <span className="whitespace-nowrap">
        <span>{r.levelName}</span>{" "}
        <span className="text-xs tabular-nums text-[var(--muted)]">
          ({r.decimalLevel == null ? r.level : decimal(r.decimalLevel)})
        </span>
      </span>
    ),
  },
  {
    key: "progress",
    header: "Progreso",
    value: (r) => r.progressPct ?? -1,
    render: (r) => <ProgressCell value={r.progressPct} />,
  },
  {
    key: "points",
    header: "Puntos",
    value: (r) => r.points ?? -1,
    render: (r) =>
      r.points == null ? (
        <span className="text-[var(--muted)]">—</span>
      ) : (
        <span className="whitespace-nowrap tabular-nums">
          {decimal(r.points, 1)} <span className="text-[var(--muted)]">/ {decimal(r.pointsPerLevel, 0)}</span>
        </span>
      ),
  },
  {
    key: "remaining",
    header: "Faltan",
    value: (r) => r.remainingPoints ?? Number.MAX_SAFE_INTEGER,
    render: (r) =>
      r.remainingPoints == null ? "—" : <span className="tabular-nums">{decimal(r.remainingPoints, 1)} pts</span>,
  },
  {
    key: "breakdown",
    header: "Partidos contabilizados",
    align: "left",
    value: (r) => Object.values(r.breakdown).reduce((sum, points) => sum + points, 0),
    render: (r) => {
      const parts = Object.entries(r.breakdown).map(
        ([kind, points]) => `${EXPERIENCE_TYPE_LABELS[kind] ?? kind}: ${decimal(points, 1)}`,
      );
      if (r.unscoredNationalMatches > 0) {
        parts.push(`Selección sin puntaje: ${r.unscoredNationalMatches}`);
      }
      return parts.length > 0 ? (
        <span className="text-xs text-[var(--muted)]">{parts.join(" · ")}</span>
      ) : (
        <span className="text-xs text-[var(--muted)]">Aún sin partidos observados</span>
      );
    },
  },
  {
    key: "htPlayerId",
    header: "PlayerID",
    value: (r) => r.htPlayerId,
    render: (r) => <span className="tabular-nums text-xs">{r.htPlayerId}</span>,
  },
];

const loyaltyColumns: Column<TrainingLoyaltyRow>[] = [
  {
    key: "player",
    header: "Nombre",
    align: "left",
    value: (r) => r.name,
    render: (r) => <PlayerLink htPlayerId={r.htPlayerId} name={r.name} />,
  },
  {
    key: "nativeCountry",
    header: "Nac.",
    align: "left",
    value: (r) => r.nativeCountry ?? "",
    render: (r) => <span className="text-xs text-[var(--muted)]">{r.nativeCountry ?? "—"}</span>,
  },
  { key: "age", header: "Edad", value: (r) => parseFloat(r.age) },
  {
    key: "daysInClub",
    header: "Días en el club",
    value: (r) => r.daysInClub ?? -1,
    render: (r) =>
      r.daysInClub == null ? <span className="text-[var(--muted)]">sin fecha</span> : r.daysInClub,
  },
  {
    key: "level",
    header: "Fidelidad",
    value: (r) => r.decimalLevel ?? r.reportedLevel,
    render: (r) => (
      <span className="whitespace-nowrap">
        <span>{r.levelName}</span>{" "}
        <span className="text-xs tabular-nums text-[var(--muted)]">
          ({r.decimalLevel == null ? r.reportedLevel : decimal(r.decimalLevel)})
        </span>
      </span>
    ),
  },
  {
    key: "progress",
    header: "Al siguiente nivel",
    value: (r) => r.progressPct ?? -1,
    render: (r) => <ProgressCell value={r.progressPct} />,
  },
  {
    key: "next",
    header: "Próximo nivel",
    value: (r) => r.daysToNextLevel ?? Number.MAX_SAFE_INTEGER,
    render: (r) => {
      if (r.daysInClub == null) return <span className="text-[var(--muted)]">—</span>;
      if (r.nextLevel == null) return <span className="text-[var(--positive)]">Máximo alcanzado</span>;
      return (
        <span className="whitespace-nowrap">
          {skillLevelLabel(r.nextLevel)} ({r.nextLevel}){" "}
          <span className="text-xs text-[var(--muted)]">en {r.daysToNextLevel} día(s)</span>
        </span>
      );
    },
  },
  {
    key: "source",
    header: "Fecha base",
    align: "left",
    value: (r) => r.dateSource ?? "",
    render: (r) => (
      <span className="text-xs text-[var(--muted)]">
        {r.dateSource === "transferencia"
          ? "Transferencia CHPP"
          : r.dateSource === "manual"
            ? "Fecha manual"
            : "No disponible"}
      </span>
    ),
  },
  {
    key: "htPlayerId",
    header: "PlayerID",
    value: (r) => r.htPlayerId,
    render: (r) => <span className="tabular-nums text-xs">{r.htPlayerId}</span>,
  },
];

const weeklyLogColumns: Column<TrainingSquadWeeklyLogEntry>[] = [
  { key: "seasonWeek", header: "TT-ss", align: "left", value: (r) => r.seasonWeek ?? "" },
  { key: "date", header: "Fecha", align: "left", value: (r) => r.date },
  { key: "trainingType", header: "Tipo", align: "left", value: (r) => r.trainingType },
  {
    key: "intensity", header: "Intensidad", value: (r) => r.intensity,
    render: (r) => `${r.intensity}%`,
  },
  {
    key: "staminaShare", header: "Condición", value: (r) => r.staminaShare,
    render: (r) => `${r.staminaShare}%`,
  },
  { key: "trainerName", header: "Entrenador", align: "left", value: (r) => r.trainerName },
];

const confirmedColumns: Column<ConfirmedLevelUp>[] = [
  { key: "seasonWeek", header: "TT-ss", align: "left", value: (r) => r.seasonWeek },
  {
    key: "change",
    header: "Subida",
    align: "left",
    value: (r) => `${r.fromLevelName} -> ${r.toLevelName}`,
    render: (r) => (
      <span>
        {r.fromLevelName} <span className="text-[var(--muted)]">→</span> <b>{r.toLevelName}</b>
      </span>
    ),
  },
  {
    key: "weeksBetween",
    header: "Semanas",
    value: (r) => r.weeksBetween ?? -1,
    render: (r) =>
      r.weeksBetween == null ? (
        <span className="text-[var(--muted)]">primera registrada</span>
      ) : (
        `${r.weeksBetween} sem`
      ),
  },
];

const forecastColumns: Column<LevelForecastMilestone>[] = [
  {
    key: "level", header: "Nivel", value: (r) => r.level,
    render: (r) => `${r.level} · ${r.levelName}`,
  },
  {
    key: "weeksFor", header: "Semanas de este nivel", value: (r) => r.weeksForThisLevel,
    render: (r) => r.weeksForThisLevel.toFixed(1),
  },
  {
    key: "cumulative", header: "Semanas desde hoy", value: (r) => r.weeksFromNow,
    render: (r) => r.weeksFromNow.toFixed(1),
  },
  { key: "seasonWeek", header: "TT-ss estimada", align: "left", value: (r) => r.seasonWeek ?? "" },
  { key: "age", header: "Edad proyectada", value: (r) => parseFloat(r.age) },
];

const optionColumns: Column<PostMatchTrainingOption>[] = [
  {
    key: "name",
    header: "Entrenamiento",
    align: "left",
    value: (r) => r.name,
    render: (r) => (
      <span className={r.recommendable ? "" : "text-[var(--muted)]"}>
        {r.name}
        {!r.recommendable && " · referencia"}
      </span>
    ),
  },
  { key: "score", header: "Score", value: (r) => r.score },
  { key: "minutes", header: "Min. equivalentes", value: (r) => r.equivalentMinutes },
  { key: "players", header: "Jugadores", value: (r) => r.trainedPlayers },
  { key: "full", header: "Full", value: (r) => r.fullTrainingPlayers },
  { key: "pops", header: "Pops <=3s", value: (r) => r.popsSoon },
];

export function TrainingPage() {
  const [section, setSection] = useState<TrainingSection>("datos");
  const [selectedSkill, setSelectedSkill] = useState<string | null>(null);
  const [includeThisWeek, setIncludeThisWeek] = useState(true);
  const [selectedPlayerId, setSelectedPlayerId] = useState<number | null>(null);
  const [playerTab, setPlayerTab] = useState<PlayerTab>("mejoras");

  const squad = useTrainingSquad(selectedSkill, includeThisWeek);
  const postMatch = usePostMatchTraining();
  const development = useTrainingDevelopment(
    section === "experiencia" || section === "fidelidad",
  );
  const formula = useTrainingFormula();
  const club = useClub();
  const playerLevels = usePlayerTrainingLevels(selectedPlayerId, selectedSkill);

  if (squad.isLoading || postMatch.isLoading) return <Loading />;
  if (squad.isError) return <ErrorState error={squad.error} />;
  if (postMatch.isError) return <ErrorState error={postMatch.error} />;

  const data = squad.data;
  const post = postMatch.data;
  const validation = formula.data?.validation;
  if (!data) return <Empty>Sincroniza para ver el entrenamiento.</Empty>;

  const recommendation = post?.recommendation ?? null;
  const currentName = post?.currentTraining?.name ?? "sin dato";
  const staff = club.data?.staff ?? null;
  const assistantRole = staff?.roles.find((role) => role.key === "assistant_trainer_levels") ?? null;
  const trainerName = data.weeklyLog[0]?.trainerName || "Sin dato";
  const trainerSpeed = staff ? trainerTrainingSpeedPct(staff.trainer.skillLevel) : null;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Entrenamiento</h1>
        <p className="text-sm text-[var(--muted)]">
          Entrenamiento actual: {currentName} · viendo {data.skillLabel}
        </p>
      </header>

      <Tabs
        tabs={[
          { key: "datos", label: "Datos Entrenamiento" },
          { key: "plantilla", label: "Entrenamiento actual" },
          { key: "experiencia", label: "Experiencia" },
          { key: "fidelidad", label: "Fidelidad" },
          { key: "posteriori", label: "A posteriori" },
        ]}
        active={section}
        onChange={setSection}
      />

      {section === "datos" && (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <Kpi label="Entrenamiento" value={currentName} />
            <Kpi label="% de entrenamiento" value={`${data.setup.intensity}%`} />
            <Kpi label="% condición" value={`${data.setup.staminaShare}%`} />
          </div>

          <div className="grid gap-4 xl:grid-cols-[minmax(18rem,0.72fr)_minmax(0,1.5fr)]">
            <Panel title="Entrenador" meta="training.xml + stafflist.xml">
              {club.isLoading ? (
                <Loading />
              ) : (
                <dl className="space-y-3 p-4 text-sm">
                  <div className="flex justify-between gap-4">
                    <dt className="text-[var(--muted)]">Nombre</dt>
                    <dd className="text-right font-medium">{trainerName}</dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-[var(--muted)]">Nivel de entrenador</dt>
                    <dd className={`font-semibold tabular-nums ${trainingStaffLevelColor(staff?.trainer.skillLevel)}`}>
                      {staff ? `${staff.trainer.skillLevel}/5` : "Sin dato"}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt className="text-[var(--muted)]">Nivel de liderazgo</dt>
                    <dd>
                      {staff
                        ? `${skillLevelLabel(staff.trainer.leadership, true)} (${staff.trainer.leadership})`
                        : "Sin dato"}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-4 border-t border-[var(--border)] pt-3">
                    <dt className="text-[var(--muted)]">Velocidad de entrenamiento</dt>
                    <dd className="tabular-nums font-medium text-[var(--positive)]">
                      {trainerSpeed == null ? "Sin dato" : `${trainerSpeed}%`}
                    </dd>
                  </div>
                </dl>
              )}
            </Panel>

            <Panel
              title="Asistentes de entrenador"
              meta={
                assistantRole
                  ? `${assistantRole.members.length} asistente(s) · nivel combinado ${assistantRole.level}`
                  : "stafflist.xml"
              }
            >
              {club.isLoading ? (
                <Loading />
              ) : club.isError ? (
                <Note>No pudimos cargar el cuerpo técnico.</Note>
              ) : assistantRole ? (
                <AssistantCards role={assistantRole} />
              ) : (
                <Note>Sin datos de asistentes. Sincroniza para leer stafflist.xml.</Note>
              )}
            </Panel>
          </div>
        </div>
      )}

      {section === "plantilla" && (
        <>
          <Panel
            title="Progreso hacia el próximo nivel"
            meta={`${data.players.length} jugadores actuales · ordenados por progreso`}
          >
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] px-4 py-3">
            <h2 className="text-sm font-semibold">Entrenamiento actual</h2>
            <div className="flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-2 text-sm">
                <span className="text-[var(--muted)]">Habilidad</span>
                <select
                  value={selectedSkill ?? data.skill}
                  onChange={(e) => setSelectedSkill(e.target.value)}
                  className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-sm"
                >
                  {data.availableSkills.map((s) => (
                    <option key={s.skill} value={s.skill}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={includeThisWeek}
                  onChange={(e) => setIncludeThisWeek(e.target.checked)}
                />
                Incluir los partidos de esta semana
              </label>
            </div>
          </div>

          <DataTable
            rows={data.players}
            columns={squadColumns(data.skillLabel)}
            rowKey={(r) => r.htPlayerId}
            initialSort="progress"
            csvName="entrenamiento-plantilla"
            selectedRowKey={selectedPlayerId}
            onRowClick={(r) => setSelectedPlayerId(r.htPlayerId)}
            emptyMessage="Sin jugadores en la plantilla."
          />
          </Panel>
          <Note>
            Las semanas transcurridas se cuentan desde la última subida confirmada por Hattrick o,
            cuando esa fuente no expone el historial, desde la primera sincronización real en que
            Lens observó el nuevo nivel. La precisión es semanal porque Lens sincroniza bajo pedido.
            {data.notes.length > 0 ? ` ${data.notes.join(" ")}` : ""}
          </Note>

          {data.weeklyLog.length > 0 && (
            <Panel
              title="Historial de configuración semanal"
              meta={`${data.weeklyLog.length} semana(s) registradas`}
            >
              <Note>
                Cada fila es una lectura real de training.xml al momento de una sincronización —
                no un valor interpolado.
              </Note>
              <DataTable
                rows={data.weeklyLog}
                columns={weeklyLogColumns}
                rowKey={(r) => r.date}
                initialSort="date"
                csvName="entrenamiento-historial-semanal"
              />
            </Panel>
          )}

          {validation && (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-xs text-[var(--muted)]">
              {validation.observations > 0 ? (
                <>
                  Contraste con pops reales: diferencia media de{" "}
                  <b className="text-[var(--text)]">
                    {validation.meanErrorWeeks == null ? "—" : `${validation.meanErrorWeeks} sem`}
                  </b>{" "}
                  sobre {validation.observations} subida(s) confirmada(s) de {formula.data?.trainedSkill}.
                </>
              ) : (
                <>Todavía no hay dos subidas seguidas de {formula.data?.trainedSkill} para contrastar la fórmula.</>
              )}{" "}
              <Link to="/engine" className="underline hover:text-[var(--text)]">
                ver el detalle en Motor
              </Link>
              .
            </div>
          )}

          {selectedPlayerId != null && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold">
                  {playerLevels.data?.name ?? "Cargando…"}
                  {playerLevels.data && (
                    <span className="text-[var(--muted)]"> · {playerLevels.data.skillLabel}</span>
                  )}
                </h2>
                <button
                  onClick={() => setSelectedPlayerId(null)}
                  className="text-xs text-[var(--muted)] underline hover:text-[var(--text)]"
                >
                  Cerrar
                </button>
              </div>

              <Tabs
                tabs={[
                  { key: "mejoras", label: "Mejoras" },
                  { key: "prevision", label: "Previsión subidas" },
                ]}
                active={playerTab}
                onChange={setPlayerTab}
              />

              {playerLevels.isLoading && <Loading />}
              {playerLevels.isError && <ErrorState error={playerLevels.error} />}

              {playerLevels.data && playerTab === "mejoras" && (
                <>
                  <Panel title="Subidas confirmadas" meta="trainingevents.xml">
                    <Note>
                      {playerLevels.data.confirmed.length > 0
                        ? "Cada fila es una subida real que Hattrick confirmó — no una estimación."
                        : playerLevels.data.notes.join(" ") || "Sin subidas confirmadas todavía."}
                    </Note>
                  </Panel>
                  {playerLevels.data.confirmed.length > 0 && (
                    <DataTable
                      rows={playerLevels.data.confirmed}
                      columns={confirmedColumns}
                      rowKey={(r) => r.seasonWeek}
                      initialSort="seasonWeek"
                      initialDescending={false}
                      csvName="entrenamiento-mejoras"
                    />
                  )}
                </>
              )}

              {playerLevels.data && playerTab === "prevision" && (
                <>
                  <ProjectionPanel
                    title="Previsión de subidas"
                    meta={`hasta nivel 20 · ${playerLevels.data.forecast.length} nivel(es)`}
                  >
                    <Note>
                      Cadena completa desde el nivel actual: cada escalón usa la fórmula comunitaria,
                      encadenando la edad proyectada para que el siguiente nivel cueste lo que
                      realmente costaría a esa edad.
                    </Note>
                  </ProjectionPanel>
                  <DataTable
                    rows={playerLevels.data.forecast}
                    columns={forecastColumns}
                    rowKey={(r) => r.level}
                    initialSort="level"
                    initialDescending={false}
                    csvName="entrenamiento-prevision"
                  />
                </>
              )}
            </div>
          )}
        </>
      )}

      {section === "experiencia" && (
        <>
          {development.isLoading && <Loading />}
          {development.isError && <ErrorState error={development.error} />}
          {development.data && (
            <>
              <Panel
                title="Experiencia"
                meta={`${development.data.experience.length} jugadores · partidos y minutos reales`}
              >
                <Note>
                  El nivel entero viene de players.xml. La fracción suma los puntos de los partidos
                  que Lens realmente observó desde la primera lectura del nivel actual, ponderados por
                  minutos jugados; no se reconstruyen partidos anteriores ni se calibra con tu plantilla.
                </Note>
                <DataTable
                  rows={development.data.experience}
                  columns={experienceColumns}
                  rowKey={(r) => r.htPlayerId}
                  initialSort="progress"
                  csvName="entrenamiento-experiencia"
                  emptyMessage="Sin jugadores para calcular experiencia."
                />
              </Panel>
              {development.data.experience.some((row) => row.unscoredNationalMatches > 0) && (
                <Note>
                  Los partidos competitivos de selección confirmados sin competencia o ronda
                  identificable se muestran, pero no reciben un puntaje inventado.
                </Note>
              )}
            </>
          )}
        </>
      )}

      {section === "fidelidad" && (
        <>
          {development.isLoading && <Loading />}
          {development.isError && <ErrorState error={development.error} />}
          {development.data && (
            <>
              <Panel
                title="Fidelidad"
                meta={`${development.data.loyalty.length} jugadores · antigüedad real en el club`}
              >
                <Note>
                  Fidelidad se calcula solo con los días calendario desde la compra: 1 + 19 ×
                  √(días / 336), limitada al nivel 20. El nivel entero es la parte entera de esa
                  misma curva; no usa regresiones ni pops de tu cuenta.
                </Note>
                <DataTable
                  rows={development.data.loyalty}
                  columns={loyaltyColumns}
                  rowKey={(r) => r.htPlayerId}
                  initialSort="daysInClub"
                  csvName="entrenamiento-fidelidad"
                  emptyMessage="Sin jugadores para calcular fidelidad."
                />
              </Panel>
              {development.data.notes.slice(2).map((note) => <Note key={note}>{note}</Note>)}
            </>
          )}
        </>
      )}

      {section === "posteriori" && post && (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <Kpi
              label="A posteriori elegiría"
              value={recommendation?.name ?? "Sin datos"}
              hint={`Actual: ${currentName}`}
              tone={
                recommendation &&
                post.currentTraining &&
                recommendation.trainingType !== post.currentTraining.trainingType
                  ? "positive"
                  : undefined
              }
            />
            <Kpi
              label="Minutos aprovechables"
              value={`${recommendation?.equivalentMinutes.toFixed(0) ?? 0}`}
              hint="equivalentes a entrenamiento completo"
            />
            <Kpi
              label="Jugadores entrenados"
              value={`${recommendation?.trainedPlayers ?? 0}`}
              hint={`${recommendation?.fullTrainingPlayers ?? 0} con entrenamiento full`}
            />
          </div>

          <Panel
            title="Entrenamiento decidido a posteriori"
            meta="elige después de ver quién jugó y dónde"
          >
            <div className="grid gap-4 p-4 lg:grid-cols-[1.4fr_1fr]">
              <Chart
                ariaLabel="Ranking de entrenamientos por exposición post-partido"
                height={320}
                option={barOption(
                  post.options.slice(0, 8).map((o) => o.name),
                  post.options.slice(0, 8).map((o) => o.score),
                  "Score",
                )}
              />
              <div className="rounded-lg border border-[var(--border)] p-4">
                <h3 className="text-sm font-semibold">
                  {recommendation ? `Mejor opción: ${recommendation.name}` : "Sin recomendación"}
                </h3>
                <p className="mt-2 text-sm text-[var(--muted)]">
                  La app suma los minutos reales por posición y compara qué tipo de
                  entrenamiento cosecha mejor esa exposición antes del update semanal.
                </p>
                <ul className="mt-4 space-y-1 text-xs text-[var(--muted)]">
                  {(recommendation?.rationale ?? []).map((item) => (
                    <li key={item}>• {item}</li>
                  ))}
                </ul>
                <ul className="mt-4 space-y-2 text-sm">
                  {(recommendation?.topTrainees ?? []).slice(0, 5).map((p) => (
                    <li key={p.htPlayerId} className="flex items-center justify-between gap-3">
                      <PlayerLink htPlayerId={p.htPlayerId} name={p.name} />
                      <span className="text-xs tabular-nums text-[var(--muted)]">
                        {(p.exposure * 100).toFixed(0)}% · {p.weeksToPop == null ? "—" : `${p.weeksToPop.toFixed(1)} sem`}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
            <Note>{post.notes.join(" ")}</Note>
          </Panel>

          <DataTable
            rows={post.options}
            columns={optionColumns}
            rowKey={(r) => r.trainingType}
            initialSort="score"
            csvName="entrenamiento-a-posteriori"
          />
        </>
      )}
    </div>
  );
}
