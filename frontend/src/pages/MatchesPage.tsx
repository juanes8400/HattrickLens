import { EnlaceATransparencia } from "../components/EnlaceATransparencia";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Chart } from "../charts/Chart";
import {
  facingBarsOption,
  radarOption,
  resultsPieOption,
} from "../charts/chartOptions";
import { Column, DataTable } from "../components/DataTable";
import { MatchSectorMap } from "../components/MatchSectorMap";
import {
  Empty,
  ErrorState,
  Kpi,
  Loading,
  Note,
  Panel,
  SinDatos,
} from "../components/Panels";
import { useMatchDetail, useMatches } from "../hooks/useTeam";
import type {
  BestRating,
  HomeAwayRow,
  MatchRow,
  Matches,
  RatingSeriesPoint,
} from "../services/api";

function renderStatOrDash(v: number | null) {
  return v == null ? (
    <span className="text-[var(--muted)]">—</span>
  ) : (
    <span>{v}</span>
  );
}

/**
 * Partidos. HL-071, HL-072, HL-073, HL-075, HL-076.
 *
 * El eje de la pantalla es separar generación de definición. «Llegamos nueve
 * veces y metimos una» y «llegamos tres y metimos dos» son el mismo 1-2 y
 * piden decisiones opuestas: la primera pide un delantero, la segunda pide
 * mediocampo. Un marcador solo no distingue las dos situaciones.
 *
 * Escaleras/Duelos/Torneos/Preparación no aparecen aquí ni en ningún otro
 * lugar de la herramienta — no son partidos oficiales y no hay botón que los
 * reactive (2026-08-12, pedido explícito). El botón que antes los mostraba
 * ahora controla los Amistosos, que sí son partidos reales.
 */
export function MatchesPage() {
  const [includeFriendlies, setIncludeFriendlies] = useState(false);
  const [season, setSeason] = useState<number | null>(null);
  const { data, isLoading, isError, error } = useMatches(
    includeFriendlies,
    season,
  );
  const [selected, setSelected] = useState<number | null>(null);

  const missingDetails =
    data?.matches.filter((r) => r.hatstats == null).length ?? 0;

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return <SinDatos />;

  return (
    <div className="space-y-4">
      {/* La cabecera envuelve en pantalla estrecha. Antes los controles
          llevaban `shrink-0` dentro de una fila que no envolvía: en un móvil
          sobresalían 110 px y arrastraban la página de lado (2026-08-31). */}
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Partidos</h1>
          <p className="text-sm text-[var(--muted)]">
            Por qué se ganó o se perdió
          </p>
          <EnlaceATransparencia seccion="partidos" calculo="hatstats" />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            aria-label="Filtrar los partidos por temporada"
            value={season ?? "all"}
            onChange={(e) =>
              setSeason(
                e.target.value === "all" ? null : Number(e.target.value),
              )
            }
            className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5 text-xs text-[var(--text)]"
          >
            <option value="all">Todas las temporadas</option>
            {data.availableSeasons.map((s) => (
              <option key={s} value={s}>
                {s === data.currentSeason
                  ? `Temporada actual (${s})`
                  : `Temporada ${s}`}
              </option>
            ))}
          </select>
          <button
            onClick={() => setIncludeFriendlies((v) => !v)}
            className={
              includeFriendlies
                ? "rounded-md border border-[var(--accent)] px-3 py-1.5 text-xs text-[var(--accent)]"
                : "rounded-md border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--muted)] hover:text-[var(--text)]"
            }
          >
            {includeFriendlies ? "Ocultar amistosos" : "Mostrar amistosos"}
          </button>
          {missingDetails > 0 && (
            // 2026-08-15: la carga se dispara desde Sincronización, no desde
            // aquí. Esta pantalla sólo avisa de que faltan datos.
            <Link
              to="/sync"
              className="rounded-md border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--muted)] hover:border-[var(--accent)] hover:text-[var(--text)]"
            >
              {missingDetails} sin ratings · cargar en Sincronización
            </Link>
          )}
        </div>
      </header>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 [&>*]:min-w-0">
        <Kpi
          label="Jugados"
          value={String(data.matchesPlayed)}
          hint={`${data.record} · ${data.seasonLabel}`}
        />
        <Kpi
          label="Goles"
          value={`${data.goalsFor} : ${data.goalsAgainst}`}
          hint={`a favor y en contra · ${data.seasonLabel}`}
          tone={data.goalsFor >= data.goalsAgainst ? "positive" : "danger"}
        />
        <Kpi
          label="HatStats medio"
          value={data.avgHatstats == null ? "—" : data.avgHatstats.toFixed(1)}
          hint={
            data.avgHatstats == null
              ? "faltan ratings"
              : `mediocampo pesa triple · ${data.seasonLabel}`
          }
        />
        <Kpi
          label="Mejor partido"
          value={data.bestMatch ? String(data.bestMatch.hatstats) : "-"}
          hint={
            data.bestMatch
              ? `vs ${data.bestMatch.opponent} · ${data.seasonLabel}`
              : undefined
          }
          tone={data.bestMatch ? "positive" : undefined}
        />
      </div>

      {data.notes.map((n, i) => (
        <Note key={i}>{n}</Note>
      ))}

      <Panel title="Resumen" meta="local/visitante y mejores marcas">
        <ResumenPanel data={data} />
      </Panel>

      <Panel title="Conversión" meta="generación frente a definición">
        <ConversionPanel data={data} />
      </Panel>

      {data.ratingSeries.length > 0 && (
        <Panel
          title="Evolución de los ratings"
          meta={`${data.ratingSeries.length} partidos · tt-ss`}
        >
          <RatingSeriesChart points={data.ratingSeries} />
        </Panel>
      )}

      <Panel title="Historial" meta="pulsa un partido para analizarlo">
        <MatchTable data={data} onSelect={setSelected} selected={selected} />
      </Panel>

      {selected != null && <MatchDetailPanel htMatchId={selected} />}
    </div>
  );
}

function ResumenPanel({ data }: { data: Matches }) {
  const homeAwayColumns: Column<HomeAwayRow>[] = [
    { key: "label", header: "Ámbito", value: (r) => r.label },
    {
      key: "played",
      header: "Partidos",
      align: "right",
      value: (r) => r.played,
    },
    { key: "won", header: "Ganados", align: "right", value: (r) => r.won },
    {
      key: "drawn",
      header: "Empatados",
      align: "right",
      value: (r) => r.drawn,
    },
    { key: "lost", header: "Perdidos", align: "right", value: (r) => r.lost },
    { key: "gf", header: "Gf", align: "right", value: (r) => r.goalsFor },
    { key: "ga", header: "Gc", align: "right", value: (r) => r.goalsAgainst },
  ];
  const bestColumns: Column<BestRating>[] = [
    { key: "label", header: "Métrica", value: (r) => r.label },
    {
      key: "value",
      header: "Mejor valor",
      align: "right",
      value: (r) => r.value,
    },
    { key: "date", header: "Fecha", value: (r) => r.date },
    {
      key: "opponent",
      header: "Partido",
      value: (r) => r.opponent,
      render: (r) => <span>vs {r.opponent}</span>,
    },
  ];

  return (
    <div className="grid gap-4 p-4 lg:grid-cols-2 [&>*]:min-w-0">
      <div className="space-y-4">
        <DataTable
          emptyMessage="Sin partidos jugados como local ni como visitante."
          rows={data.homeAway}
          columns={homeAwayColumns}
          rowKey={(r) => r.scope}
          csvName="local-visitante"
          initialSort="label"
          initialDescending={false}
          filterPlaceholder="Filtrar…"
        />
        <Chart
          ariaLabel="Distribución de resultados: ganados, empatados y perdidos"
          option={resultsPieOption(
            data.resultsPie.won,
            data.resultsPie.drawn,
            data.resultsPie.lost,
          )}
          height={220}
        />
      </div>
      <div>
        <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
          Mejores calificaciones
        </h3>
        {data.bestRatings.length ? (
          <DataTable
            emptyMessage="Sin valoraciones guardadas todavía."
            rows={data.bestRatings}
            columns={bestColumns}
            rowKey={(r) => r.metric}
            csvName="mejores-calificaciones"
            initialSort="value"
            filterPlaceholder="Filtrar…"
          />
        ) : (
          <p className="text-xs text-[var(--muted)]">
            Todavía no hay ratings por sector sincronizados.
          </p>
        )}
      </div>
    </div>
  );
}

function ConversionPanel({ data }: { data: Matches }) {
  const c = data.conversion;
  if (!c.ownChances && !c.opponentChances) {
    return (
      <p className="p-4 text-xs text-[var(--muted)]">
        Todavía no hay ocasiones por zona sincronizadas, así que no se puede
        calcular la conversión. Llegan con el detalle del partido.
      </p>
    );
  }
  return (
    <div className="space-y-4 p-4">
      <div className="grid gap-4 sm:grid-cols-2 [&>*]:min-w-0">
        <div className="rounded-lg border border-[var(--border)] p-3">
          <div className="text-xs text-[var(--muted)]">Nosotros</div>
          <div
            className={
              c.isReliable
                ? "mt-2 text-2xl font-semibold tabular-nums"
                : "mt-2 text-2xl font-semibold tabular-nums text-[var(--muted)]"
            }
          >
            {(c.ownConversion * 100).toFixed(0)}%
          </div>
          <div className="mt-1 text-xs text-[var(--muted)]">
            {c.ownGoals} de {c.ownChances} ocasiones
            {!c.isReliable && (
              <span className="block text-[var(--danger)]">
                muestra corta: es ruido
              </span>
            )}
          </div>
        </div>
        <div className="rounded-lg border border-[var(--border)] p-3">
          <div className="text-xs text-[var(--muted)]">Rival</div>
          <div
            className={
              c.isReliable
                ? "mt-2 text-2xl font-semibold tabular-nums"
                : "mt-2 text-2xl font-semibold tabular-nums text-[var(--muted)]"
            }
          >
            {(c.opponentConversion * 100).toFixed(0)}%
          </div>
          <div className="mt-1 text-xs text-[var(--muted)]">
            {c.opponentGoals} de {c.opponentChances} ocasiones
          </div>
        </div>
      </div>
      <div>
        <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
          Ocasiones por zona
        </h3>
        {/* Barras enfrentadas desde el centro: por dónde atacas tú a la
            izquierda, por dónde te atacan a la derecha. Antes eran dos barras
            sueltas por zona escaladas al mismo máximo, y comparar obligaba a
            medir dos longitudes separadas y restarlas de cabeza. */}
        <Chart
          ariaLabel="Ocasiones generadas y concedidas por zona de la cancha"
          height={Math.max(150, c.zones.length * 42)}
          option={facingBarsOption(
            c.zones.map((z) => z.label),
            c.zones.map((z) => z.own),
            c.zones.map((z) => z.opponent),
            "Generadas",
            "Concedidas",
          )}
        />
      </div>
    </div>
  );
}

function RatingSeriesChart({ points }: { points: RatingSeriesPoint[] }) {
  // Dos renglones por partido: la fecha corta arriba y contra quién debajo.
  // Antes el eje traía solo la semana de temporada, y para saber a qué partido
  // correspondía un pico había que abrir el tooltip uno por uno.
  const labels = points.map((p) => {
    const fecha = p.date.slice(5).replace("-", "/");
    return `${fecha}
${p.opponent.length > 14 ? `${p.opponent.slice(0, 13)}…` : p.opponent}`;
  });
  return (
    <Chart
      ariaLabel="Evolución de los ratings de mediocampo, defensa y ataque por partido"
      option={{
        xAxis: {
          type: "category",
          data: labels,
          axisLabel: {
            fontSize: 10,
            lineHeight: 13,
            interval: 0,
            hideOverlap: true,
          },
        },
        yAxis: { type: "value", splitLine: { lineStyle: { opacity: 0.15 } } },
        tooltip: {
          trigger: "axis",
          formatter: (params: unknown) => {
            const arr = params as { dataIndex: number }[];
            const idx = arr[0]?.dataIndex;
            if (idx == null) return "";
            const p = points[idx];
            if (!p) return "";
            const label = p.seasonWeek ?? p.date;
            return [
              `<b>${label} · vs ${p.opponent}</b>`,
              `${p.result} ${p.goalsFor}-${p.goalsAgainst} · ${p.date}`,
              `Medio: ${p.midfield} · Defensa: ${p.defence} · Ataque: ${p.attack}`,
              `HatStats: ${p.hatstats}`,
            ].join("<br/>");
          },
        },
        legend: { bottom: 0 },
        // `symbol` explícito: cada partido es una observación, no un punto
        // interpolado de una curva continua, y verlos marcados evita leer un
        // tramo recto como si hubiera datos intermedios.
        series: [
          {
            name: "Mediocampo",
            type: "line",
            data: points.map((p) => p.midfield),
            smooth: true,
            symbol: "circle",
            symbolSize: 7,
            showSymbol: true,
          },
          {
            name: "Defensa",
            type: "line",
            data: points.map((p) => p.defence),
            smooth: true,
            symbol: "circle",
            symbolSize: 7,
            showSymbol: true,
          },
          {
            name: "Ataque",
            type: "line",
            data: points.map((p) => p.attack),
            smooth: true,
            symbol: "circle",
            symbolSize: 7,
            showSymbol: true,
          },
        ],
      }}
      height={320}
    />
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
    // Propio antes que rival, y los dos juntos: la comparación que interesa es
    // entre esas dos cifras, y con "Resultado" en medio había que saltársela.
    {
      key: "hatstats",
      header: "HatStats propio",
      align: "right",
      value: (r) => r.hatstats ?? -1,
      render: (r) => renderStatOrDash(r.hatstats),
    },
    {
      key: "hatstatsOpponent",
      header: "HatStats rival",
      align: "right",
      value: (r) => r.hatstatsOpponent ?? -1,
      render: (r) => renderStatOrDash(r.hatstatsOpponent),
    },
  ];
  return (
    <DataTable
      emptyMessage="Ningún partido jugado. Sincroniza para traer el historial."
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
  if (isLoading)
    return (
      <Panel title="Análisis del partido">
        <Loading />
      </Panel>
    );
  if (isError || !data) {
    return (
      <Panel title="Análisis del partido">
        <Empty>Sin ratings por sector.</Empty>
      </Panel>
    );
  }

  const indicators = data.sectors.map((s) => ({
    name: s.label,
    max: Math.max(...data.sectors.flatMap((x) => [x.own, x.opponent])) + 4,
  }));

  const hasChances =
    data.ownChances.total > 0 || data.opponentChances.total > 0;

  return (
    <Panel
      title={`${data.isHome ? "vs" : "@"} ${data.opponent} · ${data.score}`}
      meta={data.date}
    >
      <div className="grid gap-4 p-4 lg:grid-cols-2 [&>*]:min-w-0">
        <div className="space-y-4">
          <MatchSectorMap data={data} />
          <Chart
            ariaLabel="Comparativa de ratings por sector frente al rival"
            option={radarOption(indicators, [
              { name: "Nosotros", value: data.sectors.map((s) => s.own) },
              {
                name: data.opponent,
                value: data.sectors.map((s) => s.opponent),
              },
            ])}
            height={280}
          />
        </div>
        <div className="space-y-3 text-xs leading-relaxed text-[var(--muted)]">
          <p className="text-sm font-medium text-[var(--text)]">
            {data.verdict}
          </p>
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
            {hasChances && (
              <div>
                <div className="text-[var(--muted)]">Conversión</div>
                <div className="text-lg tabular-nums text-[var(--text)]">
                  {(data.ownChances.conversion * 100).toFixed(0)}%{" "}
                  <span className="text-[var(--muted)]">vs</span>{" "}
                  {(data.opponentChances.conversion * 100).toFixed(0)}%
                </div>
                <div className="text-[10px] text-[var(--muted)]">
                  {data.ownChances.goals}/{data.ownChances.total} ocasiones
                  propias · {data.opponentChances.goals}/
                  {data.opponentChances.total} rivales
                </div>
              </div>
            )}
          </div>
          {data.strengths.length > 0 && (
            <p>
              <b className="text-[var(--positive)]">Dominamos:</b>{" "}
              {data.strengths.join(", ")}.
            </p>
          )}
          {data.weaknesses.length > 0 && (
            <p>
              <b className="text-[var(--danger)]">Nos superaron en:</b>{" "}
              {data.weaknesses.join(", ")}.
            </p>
          )}
          {!data.strengths.length && !data.weaknesses.length && (
            <p>
              Ningún sector se decidió por más de 10 puntos: partido
              equilibrado.
            </p>
          )}
        </div>
      </div>
    </Panel>
  );
}
