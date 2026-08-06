import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Chart } from "../charts/Chart";
import { radarOption } from "../charts/chartOptions";
import { Column, DataTable } from "../components/DataTable";
import { MatchSectorMap } from "../components/MatchSectorMap";
import { ErrorState, Kpi, Loading, Note, Panel } from "../components/Panels";
import { TEAM_ID, useMatchDetail, useMatches } from "../hooks/useTeam";
import { api } from "../services/api";
import type { MatchRow, Matches } from "../services/api";

function renderStatOrDash(v: number | null) {
  return v == null ? <span className="text-[var(--muted)]">—</span> : <span>{v}</span>;
}

/**
 * Partidos. HL-071, HL-072, HL-073, HL-075, HL-076.
 *
 * El eje de la pantalla es separar generación de definición. «Llegamos nueve
 * veces y metimos una» y «llegamos tres y metimos dos» son el mismo 1-2 y
 * piden decisiones opuestas: la primera pide un delantero, la segunda pide
 * mediocampo. Un marcador solo no distingue las dos situaciones.
 */
export function MatchesPage() {
  const [includeNonOfficial, setIncludeNonOfficial] = useState(false);
  const { data, isLoading, isError, error } = useMatches(includeNonOfficial);
  const [selected, setSelected] = useState<number | null>(null);
  const qc = useQueryClient();

  const missingDetails = data?.matches.filter((r) => r.hatstats == null).length ?? 0;

  const syncDetails = useMutation({
    mutationFn: () => api.syncMatchDetails(TEAM_ID),
    onSuccess: () => qc.invalidateQueries(),
  });

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Partidos</h1>
          <p className="text-sm text-[var(--muted)]">Por qué se ganó o se perdió</p>
        </div>
        <div className="flex shrink-0 gap-2">
          <button
            onClick={() => setIncludeNonOfficial((v) => !v)}
            className={
              includeNonOfficial
                ? "rounded-md border border-[var(--accent)] px-3 py-1.5 text-xs text-[var(--accent)]"
                : "rounded-md border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--muted)] hover:text-[var(--text)]"
            }
          >
            {includeNonOfficial ? "Ocultar Escaleras/Duelos" : "Mostrar Escaleras/Duelos"}
          </button>
          {missingDetails > 0 && (
            <button
              onClick={() => syncDetails.mutate()}
              disabled={syncDetails.isPending}
              className="rounded-md border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--muted)] hover:text-[var(--text)]"
            >
              {syncDetails.isPending
                ? "Sincronizando…"
                : `Sincronizar detalles (${missingDetails} sin ratings)`}
            </button>
          )}
        </div>
      </header>
      {syncDetails.isSuccess && (
        <Note>
          {syncDetails.data.matchesProcessed === 0
            ? "No había partidos pendientes de detalle."
            : `Procesados ${syncDetails.data.matchesProcessed} partido(s): ` +
              `${syncDetails.data.snapshotsWritten} ratings nuevos, ` +
              `${syncDetails.data.unchanged} ya estaban.`}
          {syncDetails.data.errors.length > 0 && ` Errores: ${syncDetails.data.errors.join(" · ")}`}
        </Note>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi label="Jugados" value={String(data.matchesPlayed)} hint={data.record} />
        <Kpi
          label="Goles"
          value={`${data.goalsFor} : ${data.goalsAgainst}`}
          hint="a favor y en contra"
          tone={data.goalsFor >= data.goalsAgainst ? "positive" : "danger"}
        />
        <Kpi
          label="HatStats medio"
          value={data.avgHatstats == null ? "—" : data.avgHatstats.toFixed(1)}
          hint={data.avgHatstats == null ? "faltan ratings" : "mediocampo pesa triple"}
        />
        <Kpi
          label="Mejor partido"
          value={data.bestMatch ? String(data.bestMatch.hatstats) : "—"}
          hint={data.bestMatch ? `vs ${data.bestMatch.opponent}` : undefined}
          tone={data.bestMatch ? "positive" : undefined}
        />
      </div>

      {data.notes.map((n, i) => (
        <Note key={i}>{n}</Note>
      ))}

      <Panel title="Conversión" meta="generación frente a definición">
        <ConversionPanel data={data} />
      </Panel>

      {data.ratingSeries.length > 0 && (
        <Panel title="Evolución de los ratings" meta={`${data.ratingSeries.length} partidos`}>
          <Chart ariaLabel="Evolución de los ratings de mediocampo, defensa y ataque"
            option={{
              xAxis: { type: "category", data: data.ratingSeries.map((p) => p.date) },
              yAxis: { type: "value", splitLine: { lineStyle: { opacity: 0.15 } } },
              tooltip: { trigger: "axis" },
              legend: { bottom: 0 },
              series: [
                { name: "Mediocampo", type: "line", data: data.ratingSeries.map((p) => p.midfield), smooth: true },
                { name: "Defensa", type: "line", data: data.ratingSeries.map((p) => p.defence), smooth: true },
                { name: "Ataque", type: "line", data: data.ratingSeries.map((p) => p.attack), smooth: true },
              ],
            }}
            height={260}
          />
        </Panel>
      )}

      <Panel title="Historial" meta="pulsa un partido para analizarlo">
        <MatchTable data={data} onSelect={setSelected} selected={selected} />
      </Panel>

      {selected != null && <MatchDetailPanel htMatchId={selected} />}
    </div>
  );
}

function ConversionPanel({ data }: { data: Matches }) {
  const withChances = data.conversion.filter((c) => c.chances > 0);
  if (!withChances.length) {
    return (
      <p className="p-4 text-xs text-[var(--muted)]">
        Todavía no hay eventos de partido sincronizados, así que no se pueden contar
        ocasiones. Llegan con el detalle de partido de CHPP.
      </p>
    );
  }
  return (
    <div className="grid gap-4 p-4 sm:grid-cols-2 lg:grid-cols-4">
      {withChances.map((c) => (
        <div key={c.kind} className="rounded-lg border border-[var(--border)] p-3">
          <div className="text-xs text-[var(--muted)]">{c.label}</div>
          <div
            className={
              c.isReliable
                ? "mt-2 text-2xl font-semibold tabular-nums"
                : "mt-2 text-2xl font-semibold tabular-nums text-[var(--muted)]"
            }
          >
            {(c.rate * 100).toFixed(0)}%
          </div>
          <div className="mt-1 text-xs text-[var(--muted)]">
            {c.goals} de {c.chances}
            {!c.isReliable && (
              <span className="block text-[var(--danger)]">muestra corta: es ruido</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function MatchTable({
  data,
  onSelect,
  selected,
}: {
  data: Matches;
  onSelect: (id: number) => void;
  selected: number | null;
}) {
  const columns: Column<MatchRow>[] = [
    { key: "date", header: "Fecha", value: (r) => r.date },
    {
      key: "opponent",
      header: "Rival",
      value: (r) => r.opponent,
      render: (r) => (
        <button
          onClick={() => onSelect(r.htMatchId)}
          className={
            selected === r.htMatchId
              ? "text-left font-medium underline"
              : "text-left hover:underline"
          }
        >
          {r.isHome ? "" : "@ "}
          {r.opponent}
        </button>
      ),
    },
    {
      key: "result",
      header: "Resultado",
      value: (r) => `${r.goalsFor}-${r.goalsAgainst}`,
      render: (r) => (
        <span
          className={
            r.result === "V"
              ? "tabular-nums text-[var(--positive)]"
              : r.result === "D"
                ? "tabular-nums text-[var(--danger)]"
                : "tabular-nums"
          }
        >
          {r.goalsFor}-{r.goalsAgainst}
        </span>
      ),
    },
    {
      key: "midfield", header: "Medio", align: "right", value: (r) => r.midfield ?? -1,
      render: (r) => renderStatOrDash(r.midfield),
    },
    {
      key: "hatstats", header: "HatStats", align: "right", value: (r) => r.hatstats ?? -1,
      render: (r) => renderStatOrDash(r.hatstats),
    },
    {
      key: "rival",
      header: "HatStats rival",
      align: "right",
      value: (r) => r.hatstatsOpponent ?? -1,
      render: (r) => renderStatOrDash(r.hatstatsOpponent),
      optional: true,
    },
    {
      key: "loddar", header: "Loddar", align: "right", value: (r) => r.loddar ?? -1,
      render: (r) => renderStatOrDash(r.loddar),
      optional: true,
    },
  ];
  return (
    <DataTable
      rows={data.matches}
      columns={columns}
      rowKey={(r) => r.htMatchId}
      csvName="partidos"
      filterPlaceholder="Filtrar por rival…"
    />
  );
}

function MatchDetailPanel({ htMatchId }: { htMatchId: number }) {
  const { data, isLoading, isError } = useMatchDetail(htMatchId);
  if (isLoading) return <Panel title="Análisis del partido"><Loading /></Panel>;
  if (isError || !data) {
    return (
      <Panel title="Análisis del partido">
        <Note>Este partido no tiene ratings por sector sincronizados todavía.</Note>
      </Panel>
    );
  }

  const indicators = data.sectors.map((s) => ({
    name: s.label,
    max: Math.max(...data.sectors.flatMap((x) => [x.own, x.opponent])) + 4,
  }));

  return (
    <Panel title={`${data.isHome ? "vs" : "@"} ${data.opponent} · ${data.score}`} meta={data.date}>
      <div className="grid gap-4 p-4 lg:grid-cols-2">
        <div className="space-y-4">
          <MatchSectorMap data={data} />
          <Chart ariaLabel="Comparativa de ratings por sector frente al rival"
            option={radarOption(indicators, [
              { name: "Nosotros", value: data.sectors.map((s) => s.own) },
              { name: data.opponent, value: data.sectors.map((s) => s.opponent) },
            ])}
            height={280}
          />
        </div>
        <div className="space-y-3 text-xs leading-relaxed text-[var(--muted)]">
          <p className="text-sm font-medium text-[var(--text)]">{data.verdict}</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="text-[var(--muted)]">HatStats</div>
              <div className="text-lg tabular-nums text-[var(--text)]">
                {data.hatstats} <span className="text-[var(--muted)]">vs</span>{" "}
                {data.hatstatsOpponent}
              </div>
            </div>
            <div>
              <div className="text-[var(--muted)]">Posesión</div>
              <div className="text-lg tabular-nums text-[var(--text)]">
                {data.possession[0]}% / {data.possession[1]}%
              </div>
            </div>
          </div>
          {data.strengths.length > 0 && (
            <p>
              <b className="text-[var(--positive)]">Dominamos:</b> {data.strengths.join(", ")}.
            </p>
          )}
          {data.weaknesses.length > 0 && (
            <p>
              <b className="text-[var(--danger)]">Nos superaron en:</b>{" "}
              {data.weaknesses.join(", ")}.
            </p>
          )}
          {!data.strengths.length && !data.weaknesses.length && (
            <p>Ningún sector se decidió por más de 10 puntos: partido equilibrado.</p>
          )}
        </div>
      </div>
    </Panel>
  );
}
