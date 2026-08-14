import { useState } from "react";
import { Link } from "react-router-dom";
import { Column, DataTable } from "../components/DataTable";
import { ErrorState, Kpi, Loading, Note, Panel, ProjectionPanel } from "../components/Panels";
import { Tabs } from "../components/Tabs";
import { useCup, useRivalScouting } from "../hooks/useTeam";
import { date, money, number } from "../hooks/useFormat";
import type {
  Cup,
  CupHistoryRow,
  CupLadderStep,
  CupNextMatch,
  CupPenaltyCandidate,
  CupPrizeStage,
} from "../services/api";

type CupSection = "resumen" | "preparacion" | "historial";

export function CupPage() {
  const { data, isLoading, isError, error } = useCup();
  const nextOpponentId = data?.nextMatches[0]?.opponentHtTeamId ?? null;
  const probability = useRivalScouting(nextOpponentId, false, true, false);
  const [section, setSection] = useState<CupSection>("resumen");

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return null;

  const next = data.nextMatches[0];
  const statusTone = data.status.stillInCup ? "positive" : "danger";

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-semibold">Copa</h1>
            <Badge tone={data.status.stillInCup ? "positive" : "muted"}>
              {data.status.stillInCup ? "En competencia" : "Participación cerrada"}
            </Badge>
            <Badge>{data.status.scopeLabel}</Badge>
            <Badge>{data.status.tierLabel}</Badge>
          </div>
          <p className="mt-1 text-sm text-[var(--muted)]">
            {data.currentCupName ?? "Historial de Copa"}
          </p>
        </div>
        <div className="text-right text-xs text-[var(--muted)]">
          <div>Estado: {data.status.source === "teamdetails" ? "CHPP · teamdetails" : "calendario"}</div>
          {data.status.nextCupMatchDate && <div>Jornada de Copa: {date(data.status.nextCupMatchDate)}</div>}
        </div>
      </header>

      <Tabs
        tabs={[
          { key: "resumen", label: "Resumen" },
          { key: "preparacion", label: "Preparación" },
          { key: "historial", label: "Historial" },
        ]}
        active={section}
        onChange={setSection}
      />

      {section === "resumen" && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <Kpi
              label="Estado"
              value={data.status.stillInCup ? "Seguimos" : "Eliminado"}
              hint={data.status.cupName ?? "sin Copa activa"}
              tone={statusTone}
            />
            <Kpi
              label="Instancia actual"
              value={data.status.stageLabel ?? "—"}
              hint={
                data.status.officialRound != null
                  ? `ronda oficial ${data.status.officialRound}`
                  : "ronda oficial pendiente de sincronizar"
              }
            />
            <Kpi
              label="Camino al título"
              value={data.goal.winsToTitle != null ? `${data.goal.winsToTitle} victorias` : "—"}
              hint="desde la instancia actual"
            />
            <Kpi
              label="Premio mínimo actual"
              value={
                data.goal.trophyOnly
                  ? "Trofeo"
                  : data.goal.securedAmount > 0
                    ? money(data.goal.securedAmount, data.currency)
                    : "Aún ninguno"
              }
              hint="si la participación terminara en esta instancia"
            />
            <Kpi
              label="Próximo cruce"
              value={next?.opponent ?? "—"}
              hint={next ? `${date(next.date)} · ${next.venueLabel}` : "sin partido programado"}
            />
          </div>

          {data.prizeTable.length > 0 && (
            <Panel title="Camino hacia la meta">
              <PrizeRoad stages={data.prizeTable} currency={data.currency} />
            </Panel>
          )}

          {data.scenarios && (
            <Panel title="Qué ocurre con el próximo resultado">
              <ResultRoutes data={data} />
            </Panel>
          )}

          {nextOpponentId != null ? (
            <ProjectionPanel
              title={`Probabilidad de avanzar vs. ${next?.opponent ?? "el rival"}`}
              meta="modelo simple por TSI, no calibrado"
            >
              {probability.isError ? (
                <div className="p-4">
                  <div className="text-lg font-semibold">No disponible en esta sesión</div>
                  <p className="mt-2 text-xs leading-relaxed text-[var(--muted)]">
                    El scouting del rival necesita una sesión CHPP activa. La fecha y el rival de
                    arriba siguen siendo datos sincronizados; aquí no se sustituye la probabilidad
                    faltante por un valor sintético.
                  </p>
                </div>
              ) : probability.data ? (
                <div className="p-4">
                  <div className="flex items-center gap-4">
                    <div className="text-3xl font-semibold tabular-nums text-[var(--accent)]">
                      {(probability.data.winProbability.ownProbability * 100).toFixed(0)}%
                    </div>
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-[var(--surface-2)]">
                      <div
                        className="h-full rounded-full bg-[var(--accent)]"
                        style={{ width: `${probability.data.winProbability.ownProbability * 100}%` }}
                      />
                    </div>
                  </div>
                  <p className="mt-3 text-xs leading-relaxed text-[var(--muted)]">
                    Estimación {probability.data.winProbability.confidence}. TSI de los dos onces de
                    referencia: {number(probability.data.winProbability.ownTsiTotal)} contra{" "}
                    {number(probability.data.winProbability.rivalTsiTotal)}.
                  </p>
                </div>
              ) : (
                <p className="p-4 text-xs text-[var(--muted)]">Calculando…</p>
              )}
            </ProjectionPanel>
          ) : (
            <Panel title="Probabilidad de avanzar" meta="sin rival confirmado">
              <Note>Se activará cuando CHPP publique el próximo cruce.</Note>
            </Panel>
          )}

          <Panel title="Impacto del tipo de Copa" meta="reglas aplicadas a esta competición">
            <div className="grid gap-px bg-[var(--border)] sm:grid-cols-3">
              <ImpactFact
                label="Experiencia"
                value={`${data.impact.experienceMultiplierVsLeague}× Liga`}
                detail={`${data.impact.experiencePointsPer90} puntos por 90 minutos`}
              />
              <ImpactFact
                label="Club"
                value={data.impact.affectsClubMood ? "Efecto completo" : "Como amistoso"}
                detail="espíritu, confianza y aficionados"
              />
              <ImpactFact label="Lesiones" value="Impacto completo" detail={data.impact.injuryEffect} />
            </div>
          </Panel>
        </>
      )}

      {section === "preparacion" && (
        <>
          <Panel title="Próximo partido" meta="fecha y rival confirmados por CHPP">
            <NextMatchesPanel matches={data.nextMatches} />
          </Panel>

          <div className="grid items-start gap-4 xl:grid-cols-2">
            <ProjectionPanel title="Preparación para 120 minutos" meta="elige el once de referencia">
              <StaminaReadiness data={data} />
            </ProjectionPanel>
            <ProjectionPanel title="Orden orientativo de penaltis">
              <PenaltyOrder candidates={data.readiness.penaltyCandidates} data={data} />
            </ProjectionPanel>
          </div>
        </>
      )}

      {section === "historial" && (
        <>
          <div className="grid items-start gap-4 xl:grid-cols-2">
            <Panel title="Economía observada de Copa" meta="asistencia real · ingreso derivado">
              <div className="grid gap-3 p-4 sm:grid-cols-2">
                <MiniMetric
                  label="Taquilla bruta observada"
                  value={money(data.economy.observedGrossGate, data.currency)}
                  detail={`${data.economy.observedHomeMatches} partido(s) de local medidos`}
                />
                <MiniMetric
                  label="Participación histórica estimada"
                  value={money(data.economy.estimatedHistoricalShare, data.currency)}
                  detail="67% de la taquilla bruta observada"
                />
              </div>
              <Note>{data.economy.qualityNote}</Note>
            </Panel>

            <ProjectionPanel title="Ingreso del próximo partido" meta="separado de la caja real">
              <div className="p-4">
                <div className="text-3xl font-semibold tabular-nums text-[var(--accent)]">
                  {data.economy.nextGateProjection == null
                    ? "No calculable"
                    : money(data.economy.nextGateProjection, data.currency)}
                </div>
                {data.economy.nextGateProjection != null && data.economy.estimatedHistoricalShare > 0 && (
                  <div className="mt-3 h-2 overflow-hidden rounded-full bg-[var(--surface-2)]">
                    <div
                      className="h-full rounded-full bg-[var(--accent)]"
                      style={{
                        width: `${Math.min(
                          100,
                          (data.economy.nextGateProjection / data.economy.estimatedHistoricalShare) * 100,
                        )}%`,
                      }}
                    />
                  </div>
                )}
                <p className="mt-3 text-xs leading-relaxed text-[var(--muted)]">
                  {data.economy.projectionBasis}
                </p>
              </div>
            </ProjectionPanel>
          </div>

          {data.ladder.length > 0 && (
            <Panel title="Trayectoria de la temporada" meta="copas y partidos realmente sincronizados">
              <Ladder steps={data.ladder} />
            </Panel>
          )}

          <Panel title="Historial" meta={`${data.history.length} partido(s) jugados esta temporada`}>
            <HistoryTable data={data} />
          </Panel>
        </>
      )}
    </div>
  );
}

function Badge({
  children,
  tone = "accent",
}: {
  children: React.ReactNode;
  tone?: "accent" | "positive" | "muted";
}) {
  const classes = {
    accent: "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]",
    positive: "border-[var(--positive)] bg-[color-mix(in_srgb,var(--positive)_12%,transparent)] text-[var(--positive)]",
    muted: "border-[var(--border)] bg-[var(--surface-2)] text-[var(--muted)]",
  };
  return <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${classes[tone]}`}>{children}</span>;
}

function PrizeRoad({ stages, currency }: { stages: CupPrizeStage[]; currency: string }) {
  return (
    <div className="overflow-x-auto p-4">
      <div className="flex min-w-max items-stretch gap-2">
        {stages.map((stage, index) => {
          const current = stage.status === "current";
          const passed = stage.status === "passed";
          return (
            <div key={stage.stage} className="flex items-center gap-2">
              <div
                className={`w-36 rounded-lg border p-3 ${
                  current
                    ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                    : passed
                      ? "border-[var(--positive)] bg-[color-mix(in_srgb,var(--positive)_8%,transparent)]"
                      : "border-[var(--border)] bg-[var(--surface-2)]"
                }`}
              >
                <div className={`text-[10px] font-semibold uppercase tracking-wide ${current ? "text-[var(--accent)]" : passed ? "text-[var(--positive)]" : "text-[var(--muted)]"}`}>
                  {current ? "Estás aquí" : passed ? "Superado" : stage.winsNeeded != null ? `A ${stage.winsNeeded} victoria(s)` : "Meta"}
                </div>
                <div className="mt-1 text-sm font-semibold">{stage.stage}</div>
                <div className="mt-2 text-xs tabular-nums text-[var(--muted)]">
                  {stage.trophyOnly ? "Trofeo · sin premio monetario" : money(stage.amount, currency)}
                </div>
              </div>
              {index < stages.length - 1 && <span className="text-lg text-[var(--muted)]">→</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ResultRoutes({ data }: { data: Cup }) {
  if (!data.scenarios) return null;
  return (
    <div className="grid gap-3 p-4 md:grid-cols-2">
      <div className="rounded-lg border border-[var(--positive)] bg-[color-mix(in_srgb,var(--positive)_7%,transparent)] p-4">
        <div className="text-xs font-semibold uppercase tracking-wide text-[var(--positive)]">Si ganamos</div>
        <div className="mt-2 text-lg font-semibold">{data.scenarios.win.nextStage ?? "Siguiente paso"}</div>
        <p className="mt-1 text-sm text-[var(--muted)]">{data.scenarios.win.description}</p>
        {data.scenarios.win.prizeAmount > 0 && (
          <div className="mt-3 text-xs tabular-nums text-[var(--positive)]">
            Meta económica: {money(data.scenarios.win.prizeAmount, data.currency)}
          </div>
        )}
      </div>
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-4">
        <div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">Si perdemos</div>
        <div className="mt-2 text-lg font-semibold">
          {data.scenarios.loss.continues === true
            ? data.scenarios.loss.destination
            : data.scenarios.loss.continues === false
              ? "Fin de la trayectoria"
              : "Ruta pendiente"}
        </div>
        <p className="mt-1 text-sm text-[var(--muted)]">{data.scenarios.loss.description}</p>
        {data.scenarios.loss.prizeAmount > 0 && (
          <div className="mt-3 text-xs tabular-nums text-[var(--muted)]">
            Premio de esta instancia: {money(data.scenarios.loss.prizeAmount, data.currency)}
          </div>
        )}
      </div>
    </div>
  );
}

function NextMatchesPanel({ matches }: { matches: CupNextMatch[] }) {
  if (!matches.length) return <Note>No hay ningún partido de Copa programado.</Note>;
  return (
    <ul className="divide-y divide-[var(--border)]">
      {matches.map((match) => (
        <li key={match.htMatchId} className="flex items-center justify-between gap-3 p-4">
          <div>
            <div className="font-medium">
              <Link to={`/rivals/${match.opponentHtTeamId}`} className="hover:text-[var(--accent)] hover:underline">
                {match.opponent}
              </Link>
            </div>
            <div className="mt-1 text-xs text-[var(--muted)]">
              {date(match.date)} · {match.venueLabel}
              {match.officialRound != null && ` · ronda ${match.officialRound}`}
            </div>
          </div>
          <Link
            to={`/rivals/${match.opponentHtTeamId}`}
            className="shrink-0 rounded-md border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--muted)] hover:text-[var(--text)]"
          >
            Analizar rival
          </Link>
        </li>
      ))}
    </ul>
  );
}

function ImpactFact({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="bg-[var(--surface)] p-4">
      <div className="text-xs text-[var(--muted)]">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value}</div>
      <div className="mt-1 text-xs text-[var(--muted)]">{detail}</div>
    </div>
  );
}

function MiniMetric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-lg bg-[var(--surface-2)] p-3">
      <div className="text-xs text-[var(--muted)]">{label}</div>
      <div className="mt-1 text-xl font-semibold tabular-nums">{value}</div>
      <div className="mt-1 text-[10px] text-[var(--muted)]">{detail}</div>
    </div>
  );
}

function StaminaReadiness({ data }: { data: Cup }) {
  const variants = data.readiness.referenceVariants;
  const [mode, setMode] = useState(data.readiness.defaultMode);
  const active = variants.find((v) => v.mode === mode) ?? variants[0];
  const colors = ["var(--danger)", "var(--warning)", "var(--positive)"];
  if (!active) return <Note>No hay jugadores activos para calcular la preparación.</Note>;
  const total = active.staminaBands.reduce((sum, band) => sum + band.count, 0) || 1;
  return (
    <div className="p-4">
      {variants.length > 1 && (
        <Tabs
          tabs={variants.map((v) => ({ key: v.mode, label: v.label }))}
          active={mode}
          onChange={setMode}
        />
      )}
      <div className="mt-4 flex items-end justify-between gap-3">
        <div>
          <div className="text-xs text-[var(--muted)]">Resistencia media</div>
          <div className="mt-1 text-3xl font-semibold tabular-nums">
            {active.averageStamina != null ? active.averageStamina.toFixed(1) : "—"}
            <span className="text-sm text-[var(--muted)]"> / 9</span>
          </div>
        </div>
        <div className="text-right text-xs text-[var(--muted)]">
          {active.mode === "top_tsi" ? (
            <>{active.startersCount} jugadores activos con mayor TSI</>
          ) : (
            <>
              vs. {active.sourceOpponent}
              {active.sourceDate ? <span className="block">{date(active.sourceDate)}</span> : null}
            </>
          )}
        </div>
      </div>
      <div className="mt-4 flex h-3 overflow-hidden rounded-full bg-[var(--surface-2)]">
        {active.staminaBands.map((band, index) => (
          <div key={band.label} style={{ width: `${(band.count / total) * 100}%`, background: colors[index] }} />
        ))}
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-3">
        {active.staminaBands.map((band, index) => (
          <div key={band.label} className="rounded-lg bg-[var(--surface-2)] p-3">
            <div className="text-xl font-semibold tabular-nums" style={{ color: colors[index] }}>{band.count}</div>
            <div className="text-xs text-[var(--muted)]">{band.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function PenaltyOrder({ candidates, data }: { candidates: CupPenaltyCandidate[]; data: Cup }) {
  return (
    <div>
      <ol className="divide-y divide-[var(--border)]">
        {candidates.map((player, index) => (
          <li key={player.htPlayerId} className="grid grid-cols-[2rem_1fr_auto] items-center gap-2 px-4 py-2.5">
            <span className="text-lg font-semibold tabular-nums text-[var(--accent)]">{index + 1}</span>
            <div>
              <Link to={`/players/${player.htPlayerId}`} className="text-sm font-medium hover:text-[var(--accent)] hover:underline">
                {player.name}
              </Link>
              <div className="text-[10px] text-[var(--muted)]">
                BP {player.setPieces} · Anotación {player.scoring} · Experiencia {player.experience}
                {player.technical && " · Técnico"}
              </div>
            </div>
            <span className="tabular-nums text-sm font-semibold">{player.readinessIndex.toFixed(1)}</span>
          </li>
        ))}
      </ol>
      {data.readiness.goalkeeper && (
        <div className="border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
          Portero de referencia: <Link to={`/players/${data.readiness.goalkeeper.htPlayerId}`} className="font-medium text-[var(--text)] hover:text-[var(--accent)]">{data.readiness.goalkeeper.name}</Link>
          {` · Portería ${data.readiness.goalkeeper.keeper}`}
        </div>
      )}
    </div>
  );
}

function Ladder({ steps }: { steps: CupLadderStep[] }) {
  return (
    <div className="overflow-x-auto p-4">
      <div className="flex min-w-max items-center gap-2">
        {steps.map((step, index) => (
          <div key={`${step.cupLevel}-${step.cupLevelIndex}-${step.fromDate}`} className="flex items-center gap-2">
            <div className="w-48 rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-3">
              <div className="text-sm font-medium">{step.cupName ?? `Nivel ${step.cupLevel}`}</div>
              <div className="mt-1 text-xs text-[var(--muted)]">
                {date(step.fromDate)}{step.fromDate !== step.toDate && ` – ${date(step.toDate)}`}
              </div>
              <div className="text-xs text-[var(--muted)]">{step.matches} partido(s)</div>
            </div>
            {index < steps.length - 1 && <span className="text-lg text-[var(--muted)]">→</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

function HistoryTable({ data }: { data: Cup }) {
  if (!data.history.length) return <Note>Todavía no hay partidos de Copa jugados sincronizados.</Note>;
  const columns: Column<CupHistoryRow>[] = [
    { key: "date", header: "Fecha", value: (row) => row.date, render: (row) => date(row.date) },
    {
      key: "opponent",
      header: "Rival",
      value: (row) => row.opponent,
      render: (row) => (
        <Link to={`/rivals/${row.opponentHtTeamId}`} className="hover:text-[var(--accent)] hover:underline">
          {row.isHome ? "" : "@ "}{row.opponent}
        </Link>
      ),
    },
    {
      key: "result",
      header: "Resultado",
      value: (row) => `${row.goalsFor}-${row.goalsAgainst}`,
      render: (row) => (
        <span className={row.result === "V" ? "tabular-nums text-[var(--positive)]" : row.result === "D" ? "tabular-nums text-[var(--danger)]" : "tabular-nums"}>
          {row.goalsFor}-{row.goalsAgainst}
        </span>
      ),
    },
    {
      key: "hatstats", header: "HatStats", align: "right", value: (row) => row.hatstats ?? -1,
      render: (row) => row.hatstats == null ? <span className="text-[var(--muted)]">—</span> : <span>{row.hatstats}</span>,
    },
    {
      key: "round", header: "Ronda", align: "right", value: (row) => row.round ?? -1,
      render: (row) => row.round == null ? <span className="text-[var(--muted)]">—</span> : <span>{row.round}</span>,
    },
    {
      key: "cupName", header: "Copa", value: (row) => row.cupName ?? "",
      render: (row) => <span className="text-[var(--muted)]">{row.cupName ?? "—"}</span>,
    },
  ];
  return <DataTable rows={data.history} columns={columns} rowKey={(row) => row.htMatchId} csvName="copa" filterPlaceholder="Filtrar por rival…" />;
}
