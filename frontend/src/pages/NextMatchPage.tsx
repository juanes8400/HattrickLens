import { Link } from "react-router-dom";
import { DataTable, type Column } from "../components/DataTable";
import { Empty, ErrorState, Kpi, Loading, Note, Panel, ProjectionPanel } from "../components/Panels";
import { number, relative } from "../hooks/useFormat";
import { useNextMatchAnalysis } from "../hooks/useTeam";
import type { NextMatchAnalysis } from "../services/api";

type RivalStarter = NonNullable<NextMatchAnalysis["rival"]>["probableLineup"][number];

function dateTime(iso: string): string {
  return new Intl.DateTimeFormat("es-CO", {
    weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  }).format(new Date(iso));
}

function Comparison({
  label,
  own,
  rival,
}: {
  label: string;
  own: number | null;
  rival: number | null;
}) {
  const difference = own != null && rival != null ? own - rival : null;
  return (
    <div className="rounded-md border border-[var(--border)] p-3">
      <div className="text-xs text-[var(--muted)]">{label}</div>
      <div className="mt-2 grid grid-cols-3 items-baseline gap-2 text-center">
        <div><b className="tabular-nums">{own?.toFixed(1) ?? "—"}</b><div className="text-[10px] text-[var(--muted)]">tu XI</div></div>
        <div className="text-xs text-[var(--muted)]">
          {difference == null ? "—" : `${difference > 0 ? "+" : ""}${difference.toFixed(1)}`}
        </div>
        <div><b className="tabular-nums">{rival?.toFixed(1) ?? "—"}</b><div className="text-[10px] text-[var(--muted)]">rival</div></div>
      </div>
    </div>
  );
}

export function NextMatchPage() {
  const { data, isLoading, isError, error } = useNextMatchAnalysis();

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data?.match) return <Empty>{data?.message ?? "No hay próximo partido sincronizado."}</Empty>;

  const { match, rival, own } = data;
  if (!rival || !own) return <Empty>No se pudo preparar el análisis del rival.</Empty>;
  const rivalCondition = rival.condition;
  const ownCondition = own.condition;
  const starterColumns: Column<RivalStarter>[] = [
    {
      key: "name", header: "Titular probable", value: (row) => row.name,
      render: (row) => (
        <div>
          <div>{row.name}</div>
          <div className="text-xs text-[var(--muted)]">{row.line}</div>
        </div>
      ),
    },
    { key: "starts", header: "Titularidades", align: "right", value: (row) => row.startsInSample,
      render: (row) => <span className="tabular-nums">{row.startsInSample}/{row.sampleSize}</span> },
    { key: "stamina", header: "Resistencia", align: "right", value: (row) => row.stamina ?? -1,
      render: (row) => row.stamina == null
        ? <span className="text-[var(--muted)]">—</span>
        : <span className={row.stamina <= 5 ? "font-medium text-[var(--danger)]" : "tabular-nums"}>{row.stamina}</span> },
    { key: "form", header: "Forma", align: "right", value: (row) => row.form ?? -1,
      render: (row) => <span className="tabular-nums">{row.form ?? "—"}</span> },
    { key: "experience", header: "Experiencia", align: "right", value: (row) => row.experience ?? -1,
      render: (row) => <span className="tabular-nums">{row.experience ?? "—"}</span> },
    { key: "tsi", header: "TSI", align: "right", value: (row) => row.tsi,
      render: (row) => <span className="tabular-nums">{number(row.tsi)}</span> },
  ];

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-xs font-medium uppercase tracking-wide text-[var(--accent)]">Próximo partido</div>
          <h1 className="mt-1 text-xl font-semibold">{match.home} <span className="text-[var(--muted)]">vs.</span> {match.away}</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            {dateTime(match.date)} · {match.matchTypeLabel} · {match.isHome ? "juegas en casa" : "juegas de visita"}
          </p>
        </div>
        <Link className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm hover:border-[var(--accent)]" to={`/rivals/${match.rivalHtTeamId}`}>
          Ficha completa del rival
        </Link>
      </header>

      <div className="grid gap-4 sm:grid-cols-3">
        <Kpi label="Resistencia rival" value={rivalCondition.staminaAvg?.toFixed(1) ?? "—"} hint={rivalCondition.staminaAvailable ? `mediana ${rivalCondition.staminaMedian?.toFixed(1) ?? "—"} · XI probable` : "CHPP no entregó StaminaSkill"} />
        <Kpi label="Forma rival" value={rivalCondition.formAvg?.toFixed(1) ?? "—"} hint="lectura actual" />
        <Kpi label="Experiencia rival" value={rivalCondition.experienceAvg?.toFixed(1) ?? "—"} hint={rivalCondition.staminaAvailable ? `${rivalCondition.lowStaminaCount} con resistencia ≤ 5` : "Resistencia no disponible por CHPP"} tone={rivalCondition.staminaAvailable && rivalCondition.lowStaminaCount > 3 ? "positive" : undefined} />
      </div>

      <Panel title="Lectura actual: tu XI vs. el probable rival" meta="campos vigentes expuestos por CHPP">
        <div className="grid gap-3 p-4 md:grid-cols-3">
          <Comparison label="Resistencia media" own={ownCondition.staminaAvg} rival={rivalCondition.staminaAvg} />
          <Comparison label="Forma media" own={ownCondition.formAvg} rival={rivalCondition.formAvg} />
          <Comparison label="Experiencia media" own={ownCondition.experienceAvg} rival={rivalCondition.experienceAvg} />
        </div>
        <Note>
          Esta comparación no convierte esos atributos en un marcador estimado. Son las lecturas vigentes de ambos onces en este momento; el once rival sigue siendo una proyección.
        </Note>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Resistencia por línea rival" meta={`${rivalCondition.players} jugadores probables`}>
          <div className="divide-y divide-[var(--border)]">
            {rivalCondition.byLine.map((line) => (
              <div key={line.line} className="grid grid-cols-4 gap-2 px-4 py-3 text-sm">
                <span>{line.line} <span className="text-xs text-[var(--muted)]">({line.players})</span></span>
                <span className="text-right tabular-nums">R {line.staminaAvg?.toFixed(1) ?? "—"}</span>
                <span className="text-right tabular-nums">F {line.formAvg?.toFixed(1) ?? "—"}</span>
                <span className="text-right tabular-nums">E {line.experienceAvg?.toFixed(1) ?? "—"}</span>
              </div>
            ))}
          </div>
        <Note>R = resistencia, F = forma, E = experiencia. “—” significa que CHPP no entregó el campo; no equivale a nivel cero. No es una estimación de caída futura durante el partido.</Note>
        </Panel>

        <ProjectionPanel title="Secuencia para decidir la formación" meta="flujo de partido">
          <ol className="space-y-3 p-4 text-sm">
            <li><b>1. Sincroniza.</b> Actualiza plantilla y calendario desde la barra superior.</li>
            <li><b>2. Lee al rival.</b> Esta vista consulta en vivo sus datos actuales y sus últimos {rival.matchesAnalysed} oficiales.</li>
            <li><b>3. Prueba tu once.</b> <Link className="text-[var(--accent)] underline" to="/lineup">Abre Alineación</Link> para comparar formaciones y clima.</li>
            <li><b>4. Decide.</b> El siguiente paso será conservar el escenario elegido y contrastarlo con el partido real tras la siguiente sincronización.</li>
          </ol>
        </ProjectionPanel>
      </div>

      {own.submittedOrders && (
        <Panel
          title="Tu alineación enviada"
          meta={`CHPP · minuto 0 · táctica ${own.submittedOrders.tacticType ?? "—"} · nivel ${own.submittedOrders.tacticSkill ?? "—"}`}
        >
          <div className="grid gap-px bg-[var(--border)] sm:grid-cols-2 lg:grid-cols-4">
            {own.submittedOrders.lineup.map((player) => (
              <div key={player.htPlayerId} className="bg-[var(--surface)] px-4 py-3">
                <div className="truncate text-sm font-medium">{player.name}</div>
                <div className="text-xs text-[var(--muted)]">
                  {player.position} · {player.behaviourLabel}
                </div>
                <div className="mt-1 text-xs tabular-nums">
                  R {player.stamina} · F {player.form} · E {player.experience}
                </div>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-px border-t border-[var(--border)] bg-[var(--border)] sm:grid-cols-4 lg:grid-cols-7">
            {([
              ["Medio", own.submittedOrders.ratings.midfield],
              ["Def. der.", own.submittedOrders.ratings.rightDef],
              ["Def. centro", own.submittedOrders.ratings.centralDef],
              ["Def. izq.", own.submittedOrders.ratings.leftDef],
              ["Ataq. der.", own.submittedOrders.ratings.rightAtt],
              ["Ataq. centro", own.submittedOrders.ratings.centralAtt],
              ["Ataq. izq.", own.submittedOrders.ratings.leftAtt],
            ] as const).map(([label, value]) => (
              <div key={label} className="bg-[var(--surface)] px-3 py-2 text-center">
                <div className="text-[10px] uppercase text-[var(--muted)]">{label}</div>
                <div className="text-lg font-semibold tabular-nums">{value ?? "—"}</div>
              </div>
            ))}
          </div>
          <Note>
            Esta es la orden realmente guardada en Hattrick. Los sectores son una predicción
            oficial de inicio, no el promedio que aparecerá en el informe final.
          </Note>
        </Panel>
      )}

      {own.formation && (
        <Panel
          title={own.submittedOrders ? "Alternativa recomendada por Hattrick Lens" : "Tu once recomendado ahora"}
          meta={`${own.formation.formation} · índice ${own.formation.totalRating.toFixed(2)}`}
        >
          <div className="grid gap-px bg-[var(--border)] sm:grid-cols-2 lg:grid-cols-4">
            {own.formation.lineup.map((player) => (
              <div key={player.htPlayerId} className="bg-[var(--surface)] px-4 py-3">
                <div className="truncate text-sm font-medium">{player.name}</div>
                <div className="text-xs text-[var(--muted)]">{player.position}</div>
                <div className="mt-1 text-xs tabular-nums">R {player.stamina} · F {player.form} · E {player.experience}</div>
              </div>
            ))}
          </div>
        </Panel>
      )}

      <Panel title="Once probable del rival" meta={`${rival.matchesAnalysed} partidos oficiales recientes`}>
        <DataTable
          rows={rival.probableLineup}
          columns={starterColumns}
          rowKey={(row) => row.htPlayerId}
          initialSort="starts"
          csvName={`once-probable-${rival.name}`}
          emptyMessage="No se identificaron titulares rivales en los partidos públicos disponibles."
        />
        <Note>{rival.selectionMethod}</Note>
      </Panel>

      {data.notes && (
        <Panel title="Alcance del análisis">
          <div className="space-y-1 p-4 text-xs text-[var(--muted)]">
            {data.notes.map((note) => <p key={note}>{note}</p>)}
            {data.dataFreshness && <p>Consulta realizada {relative(data.dataFreshness)}.</p>}
          </div>
        </Panel>
      )}
    </div>
  );
}
