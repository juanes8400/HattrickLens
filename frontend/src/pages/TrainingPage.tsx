import { useState } from "react";
import { Link } from "react-router-dom";
import {
  usePlayerTrainingLevels,
  usePostMatchTraining,
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
  ConfirmedLevelUp,
  LevelForecastMilestone,
  PostMatchTrainingOption,
  TrainingSquadPlayerRow,
  TrainingSquadWeeklyLogEntry,
} from "../services/api";

type TrainingSection = "plantilla" | "posteriori";
type PlayerTab = "mejoras" | "prevision";

const squadColumns: Column<TrainingSquadPlayerRow>[] = [
  {
    key: "nativeCountry",
    header: "País",
    align: "left",
    optional: true,
    value: (r) => r.nativeCountry ?? "",
  },
  {
    key: "player",
    header: "Jugador",
    align: "left",
    value: (r) => r.name,
    render: (r) => <PlayerLink htPlayerId={r.htPlayerId} name={r.name} />,
  },
  { key: "age", header: "Edad", value: (r) => parseFloat(r.age) },
  {
    key: "level",
    header: "Nivel",
    value: (r) => r.level,
    render: (r) => (
      <span>
        <b className="tabular-nums">{r.level}</b>{" "}
        <span className="text-[var(--muted)]">· {r.levelName}</span>
      </span>
    ),
  },
  {
    key: "weeks",
    header: "Semanas",
    value: (r) => r.weeksElapsed ?? -1,
    render: (r) => (
      <span className="tabular-nums">
        {r.hasReference ? r.weeksElapsed : <span className="text-[var(--muted)]">—</span>}
        <span className="text-[var(--muted)]"> / {r.weeksTotal.toFixed(1)}</span>
      </span>
    ),
  },
  {
    key: "progress",
    header: "% Progreso",
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
  const [section, setSection] = useState<TrainingSection>("plantilla");
  const [selectedSkill, setSelectedSkill] = useState<string | null>(null);
  const [includeThisWeek, setIncludeThisWeek] = useState(true);
  const [selectedPlayerId, setSelectedPlayerId] = useState<number | null>(null);
  const [playerTab, setPlayerTab] = useState<PlayerTab>("mejoras");

  const squad = useTrainingSquad(selectedSkill, includeThisWeek);
  const postMatch = usePostMatchTraining();
  const formula = useTrainingFormula();
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
          { key: "plantilla", label: "Plantilla" },
          { key: "posteriori", label: "A posteriori" },
        ]}
        active={section}
        onChange={setSection}
      />

      {section === "plantilla" && (
        <>
          <div>
            <h2 className="mb-2 text-sm font-semibold">Configuración de entrenamiento actual</h2>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              <Kpi label="Tipo" value={currentName} />
              <Kpi label="Intensidad" value={`${data.setup.intensity}%`} />
              <Kpi
                label="Condición"
                value={`${data.setup.staminaShare}%`}
                hint="parte de resistencia"
              />
              <Kpi
                label="Entrenador"
                value={`Nivel ${data.setup.coachLevel}`}
                hint={data.setup.coachIsExcellent ? "Excelente" : "Normal"}
              />
              <Kpi
                label="Ayudantes"
                value={`suma ${data.setup.assistantLevelSum}`}
                hint="niveles combinados"
              />
            </div>
          </div>

          {data.weeklyLog.length > 0 && (
            <>
              <Panel
                title="Historial de configuración semanal"
                meta={`${data.weeklyLog.length} semana(s) registradas`}
              >
                <Note>
                  Cada fila es una lectura real de training.xml al momento de una sincronización —
                  no un valor interpolado.
                </Note>
              </Panel>
              <DataTable
                rows={data.weeklyLog}
                columns={weeklyLogColumns}
                rowKey={(r) => r.date}
                initialSort="date"
                csvName="entrenamiento-historial-semanal"
              />
            </>
          )}

          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-sm font-semibold">Plantilla — {data.skillLabel}</h2>
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
            columns={squadColumns}
            rowKey={(r) => r.htPlayerId}
            initialSort="progress"
            csvName="entrenamiento-plantilla"
            selectedRowKey={selectedPlayerId}
            onRowClick={(r) => setSelectedPlayerId(r.htPlayerId)}
            emptyMessage="Sin jugadores en la plantilla."
          />
          <Note>
            Las semanas transcurridas se cuentan en semanas de temporada completas desde la última
            subida confirmada — no con la precisión de días que muestra Hattrick Control, porque HT
            Lens sincroniza bajo pedido y no corre en segundo plano.
            {data.notes.length > 0 ? ` ${data.notes.join(" ")}` : ""}
          </Note>

          {validation && (
            <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-xs text-[var(--muted)]">
              {validation.observations > 0 ? (
                <>
                  Precisión del modelo: error medio de{" "}
                  <b className="text-[var(--text)]">
                    {validation.meanErrorWeeks == null ? "—" : `${validation.meanErrorWeeks} sem`}
                  </b>{" "}
                  sobre {validation.observations} subida(s) confirmada(s) de {formula.data?.trainedSkill}.
                </>
              ) : (
                <>Todavía no hay dos subidas seguidas de {formula.data?.trainedSkill} para validar el modelo.</>
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
                      Cadena completa desde el nivel actual: cada escalón usa la fórmula validada,
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
                        {(p.exposure * 100).toFixed(0)}% · {p.weeksToPop.toFixed(1)} sem
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
