import { useState } from "react";
import { usePostMatchTraining, useTrainingForecast } from "../hooks/useTeam";
import { DataTable, type Column } from "../components/DataTable";
import { Empty, ErrorState, Kpi, Loading, Note, Panel } from "../components/Panels";
import { PlayerLink } from "../components/PlayerLink";
import { TrainingPitch } from "../components/TrainingPitch";
import { Chart } from "../charts/Chart";
import { barOption } from "../charts/chartOptions";
import type { PostMatchTrainingOption } from "../services/api";

type ForecastRow = {
  player: string;
  htPlayerId: number;
  age: string;
  currentLevel: number;
  weeksToPop: number;
};

export function TrainingPage() {
  const forecast = useTrainingForecast();
  const postMatch = usePostMatchTraining();
  const data = forecast.data;
  const post = postMatch.data;
  const [selectedTrainingType, setSelectedTrainingType] = useState<number | null>(null);

  if (forecast.isLoading || postMatch.isLoading) return <Loading />;
  if (forecast.isError) return <ErrorState error={forecast.error} />;
  if (postMatch.isError) return <ErrorState error={postMatch.error} />;
  if (!data || !data.trainedSkill) return <Empty>Sincroniza para ver el entrenamiento.</Empty>;

  const columns: Column<ForecastRow>[] = [
    {
      key: "player", header: "Jugador", align: "left", value: (r) => r.player,
      render: (r) => <PlayerLink htPlayerId={r.htPlayerId} name={r.player} />,
    },
    { key: "age", header: "Edad", value: (r) => parseFloat(r.age) },
    { key: "level", header: "Nivel", value: (r) => r.currentLevel },
    {
      key: "weeks", header: "Semanas al nivel", value: (r) => r.weeksToPop,
      render: (r) => <b className="tabular-nums">{r.weeksToPop.toFixed(1)}</b>,
    },
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

  const soonest = data.players[0];
  const slowest = data.players[data.players.length - 1];
  const recommendation = post?.recommendation ?? null;
  const currentName = post?.currentTraining?.name ?? "sin dato";
  const selectedType = selectedTrainingType ?? recommendation?.trainingType ?? post?.options[0]?.trainingType;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Entrenamiento</h1>
        <p className="text-sm text-[var(--muted)]">
          Entrenando {data.trainedSkill} · exposicion efectiva {(data.exposure * 100).toFixed(0)}%
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-3">
        <Kpi
          label="Proxima subida estimada"
          value={`~${soonest?.weeksToPop.toFixed(1)} sem`}
          hint={soonest?.player}
        />
        <Kpi
          label="Mas lento (estimado)"
          value={`~${slowest?.weeksToPop.toFixed(1)} sem`}
          hint={slowest?.player}
        />
        <Kpi label="Jugadores" value={String(data.players.length)} />
      </div>

      {post && (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <Kpi
              label="A posteriori elegiria"
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
            meta="elige despues de ver quien jugo y donde"
          >
            <div className="grid gap-4 p-4 lg:grid-cols-[1.4fr_1fr]">
              <Chart
                ariaLabel="Ranking de entrenamientos por exposicion post-partido"
                height={320}
                option={barOption(
                  post.options.slice(0, 8).map((o) => o.name),
                  post.options.slice(0, 8).map((o) => o.score),
                  "Score",
                )}
              />
              <div className="rounded-lg border border-[var(--border)] p-4">
                <h3 className="text-sm font-semibold">
                  {recommendation ? `Mejor opcion: ${recommendation.name}` : "Sin recomendacion"}
                </h3>
                <p className="mt-2 text-sm text-[var(--muted)]">
                  La app suma los minutos reales por posicion y compara que tipo de
                  entrenamiento cosecha mejor esa exposicion antes del update semanal.
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

          {selectedType != null && (
            <Panel
              title="Cancha de exposicion"
              meta="cambia el entrenamiento y mira quien recibe full/parcial"
            >
              <div className="border-b border-[var(--border)] p-3">
                <div className="flex flex-wrap gap-2">
                  {post.options.slice(0, 12).map((option) => (
                    <button
                      key={option.trainingType}
                      onClick={() => setSelectedTrainingType(option.trainingType)}
                      className={
                        option.trainingType === selectedType
                          ? "rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white"
                          : option.recommendable
                            ? "rounded-md border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--muted)] hover:text-[var(--text)]"
                            : "rounded-md border border-dashed border-[var(--border)] px-3 py-1.5 text-sm text-[var(--muted)] opacity-70 hover:text-[var(--text)]"
                      }
                    >
                      {option.name}
                      {!option.recommendable && " · ref"}
                    </button>
                  ))}
                </div>
              </div>
              <div className="p-4">
                <TrainingPitch data={post} selectedTrainingType={selectedType} />
              </div>
            </Panel>
          )}

          <DataTable
            rows={post.options}
            columns={optionColumns}
            rowKey={(r) => r.trainingType}
            initialSort="score"
            csvName="entrenamiento-a-posteriori"
          />
        </>
      )}

      <Panel title="Prevision de subidas" meta="la pestana que Hattrick Control deja vacia">
        <Chart
          ariaLabel="Semanas hasta el proximo nivel por jugador"
          height={420}
          option={barOption(
            data.players.map((p) => `${p.player} · ${p.age}`),
            data.players.map((p) => p.weeksToPop),
            "Semanas",
          )}
        />
        <Note>
          La edad manda: cumplir un ano encarece el entrenamiento alrededor de un 4,6%,
          subir un nivel apenas un 0,8%. Cada skill tiene ademas su propio tiempo base.
        </Note>
      </Panel>

      <DataTable
        rows={data.players}
        columns={columns}
        rowKey={(r) => r.htPlayerId}
        initialSort="weeks"
        csvName="entrenamiento"
      />
    </div>
  );
}
