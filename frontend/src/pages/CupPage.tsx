import { useState } from "react";
import { Link } from "react-router-dom";
import { BarraDePrediccion } from "../components/BarraDePrediccion";
import { EnlaceATransparencia } from "../components/EnlaceATransparencia";
import { Column, DataTable } from "../components/DataTable";
import {
  ErrorState,
  Kpi,
  Loading,
  Note,
  Panel,
  ProjectionPanel,
  SinDatos,
} from "../components/Panels";
import { Tabs, PanelDePestanas } from "../components/Tabs";
import { PitchZoneMethodSelector } from "../components/PitchZoneMethodSelector";
import {
  PITCH_ZONE_METHODS,
  SUBMITTED_METHOD,
} from "../components/pitchZoneMethods";
import { useCup, useRivalScouting } from "../hooks/useTeam";
import { date, money, number } from "../hooks/useFormat";
import type {
  Cup,
  CupHistoryRow,
  CupLadderStep,
  CupNextMatch,
  CupPenaltyCandidate,
  CupPrizeStage,
  PitchZoneMethod,
} from "../services/api";

import { tx } from "../i18n/tx";
type CupSection = "resumen" | "preparacion" | "historial";

export function CupPage() {
  // LOS MISMOS DOS SELECTORES QUE LA FICHA DE RIVAL (2026-09-09, pedido del
  // usuario: «hereda también esos selectores»). Uno por lado: lo que quieres
  // saber de ti no tiene por qué ser lo mismo que quieres saber del rival, y
  // de tu lado existe además la alineación ya enviada.
  const [metodoPropio, setMetodoPropio] =
    useState<PitchZoneMethod>("submitted");
  const [metodoRival, setMetodoRival] = useState<PitchZoneMethod>("average");
  const { data, isLoading, isError, error } = useCup(metodoPropio, metodoRival);
  const nextOpponentId = data?.nextMatches[0]?.opponentHtTeamId ?? null;
  // Oficiales, dicho a las claras. Antes iba `false` y se apoyaba en que el
  // otro toggle abría en amistosos: un rival de Copa descrito por sus
  // amistosos. Desde que los dos son un selector excluyente eso ya no se
  // sostiene solo, y tampoco debería haberse sostenido nunca.
  const probability = useRivalScouting(nextOpponentId, false, true, true);
  const [section, setSection] = useState<CupSection>("resumen");

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return <SinDatos />;

  const next = data.nextMatches[0];
  const statusTone = data.status.stillInCup ? "positive" : "danger";

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-semibold">{tx("Copa")}</h1>
            <Badge tone={data.status.stillInCup ? "positive" : "muted"}>
              {data.status.stillInCup
                ? tx("En competencia")
                : tx("Participación cerrada")}
            </Badge>
            <Badge>{data.status.scopeLabel}</Badge>
            <Badge>{data.status.tierLabel}</Badge>
          </div>
          <p className="mt-1 text-sm text-[var(--muted)]">
            {data.currentCupName ?? tx("Historial de Copa")}
          </p>
        </div>
        <div className="text-right text-xs text-[var(--muted)]">
          <div>
            {tx("Estado:")}{" "}
            {data.status.source === "teamdetails"
              ? tx("confirmado por Hattrick")
              : tx("calendario")}
          </div>
          {data.status.nextCupMatchDate && (
            <div>
              {tx("Jornada de Copa:")} {date(data.status.nextCupMatchDate)}
            </div>
          )}
        </div>
      </header>

      <Tabs
        grupo="copa"
        tabs={[
          { key: "resumen", label: tx("Resumen") },
          { key: "preparacion", label: tx("Preparación") },
          { key: "historial", label: tx("Historial") },
        ]}
        active={section}
        onChange={setSection}
      />

      <PanelDePestanas grupo="copa" activa={section} className="space-y-4">
        {section === "resumen" && (
          <>
            {/* Eliminado significa que NADA de lo que sigue está en juego.
                Hasta el 2026-08-31 la pestaña se pintaba igual estuvieras
                dentro o fuera: enseñaba el camino al título, el próximo
                cruce y una probabilidad de avanzar «que se activará cuando
                Hattrick publique el rival» --y no se iba a activar nunca--. */}
            {/* ELIMINADO: UNA TARJETA Y NADA MÁS (2026-09-13). Quedaban cinco
                tarjetas con «, », el cuadro de premios entero y una
                probabilidad de avanzar «participación cerrada»: todo lo que
                ya no está en juego, enseñado como si lo estuviera. */}
            {data.status.stillInCup ? (
              <>
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5 [&>*]:min-w-0">
                  <Kpi
                    label={tx("Estado")}
                    value={
                      data.status.stillInCup ? tx("Seguimos") : tx("Eliminado")
                    }
                    hint={data.status.cupName ?? tx("sin Copa activa")}
                    tone={statusTone}
                  />
                  <Kpi
                    label={tx("Instancia actual")}
                    value={data.status.stageLabel ?? "-"}
                    hint={
                      data.status.officialRound != null
                        ? tx("ronda oficial {{v0}}", {
                            v0: data.status.officialRound,
                          })
                        : tx("ronda oficial pendiente de sincronizar")
                    }
                  />
                  <Kpi
                    label={
                      data.status.stillInCup
                        ? tx("Camino al título")
                        : tx("Llegaste hasta")
                    }
                    value={
                      !data.status.stillInCup
                        ? (data.status.stageLabel ?? "-")
                        : data.goal.winsToTitle != null
                          ? tx("{{v0}} victorias", { v0: data.goal.winsToTitle })
                          : "-"
                    }
                    hint={
                      data.status.stillInCup
                        ? tx("desde la instancia actual")
                        : tx("la instancia donde se acabó")
                    }
                  />
                  <Kpi
                    label={
                      data.status.stillInCup
                        ? tx("Premio mínimo actual")
                        : tx("Premio conseguido")
                    }
                    value={
                      data.goal.trophyOnly
                        ? tx("Trofeo")
                        : data.goal.securedAmount > 0
                          ? money(data.goal.securedAmount, data.currency)
                          : tx("Aún ninguno")
                    }
                    hint={
                      data.status.stillInCup
                        ? tx("si la participación terminara en esta instancia")
                        : tx("lo que dejó la participación")
                    }
                  />
                  {/* Sin copa viva no hay «próximo cruce» que esperar: el hueco
                  se cambia por la fecha en que se acabó. */}
                  <Kpi
                    label={
                      data.status.stillInCup
                        ? tx("Próximo cruce")
                        : tx("Participación")
                    }
                    value={
                      data.status.stillInCup
                        ? (next?.opponent ?? "-")
                        : tx("Cerrada")
                    }
                    hint={
                      data.status.stillInCup
                        ? next
                          ? `${date(next.date)} · ${next.venueLabel}`
                          : tx("sin partido programado")
                        : tx("hasta la próxima temporada")
                    }
                  />
                </div>

                {data.prizeTable.length > 0 && (
                  <Panel
                    title={
                      data.status.stillInCup
                        ? tx("Camino hacia la meta")
                        : tx("El cuadro de premios")
                    }
                    meta={
                      data.status.stillInCup
                        ? undefined
                        : tx("referencia: ya no hay nada que recorrer")
                    }
                  >
                    <PrizeRoad
                      stages={data.prizeTable}
                      currency={data.currency}
                    />
                  </Panel>
                )}

                {data.scenarios && data.status.stillInCup && (
                  <Panel title={tx("Qué ocurre con el próximo resultado")}>
                    <ResultRoutes data={data} />
                  </Panel>
                )}

                {nextOpponentId != null ? (
                  <ProjectionPanel
                    title={tx("Probabilidad de avanzar vs. {{v0}}", {
                      v0: next?.opponent ?? "el rival",
                    })}
                    meta={
                      data.prediction
                        ? tx("modelo de zonas · sin empate: hay prórroga")
                        : tx("modelo simple por TSI, no calibrado")
                    }
                  >
                    {data.prediction ? (
                      <div className="space-y-3 p-4">
                        {/* Los dos mandos, arriba del todo: son lo que mueve la
                        barra que viene debajo. */}
                        <div className="grid gap-2 sm:grid-cols-2">
                          <div className="rounded border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2">
                            <div className="text-[10px] uppercase text-[var(--muted)]">
                              {tx("Tu fuente")}
                            </div>
                            <PitchZoneMethodSelector
                              method={data.prediction.metodoPropio}
                              onMethodChange={setMetodoPropio}
                              options={[
                                SUBMITTED_METHOD,
                                ...PITCH_ZONE_METHODS,
                              ]}
                            />
                          </div>
                          <div className="rounded border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2">
                            <div className="text-[10px] uppercase text-[var(--muted)]">
                              {tx("Fuente rival")}
                            </div>
                            <PitchZoneMethodSelector
                              method={data.prediction.metodoRival}
                              onMethodChange={setMetodoRival}
                            />
                          </div>
                        </div>
                        <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
                          <span>
                            <span className="font-medium">{data.teamName}</span>
                            <span className="mx-2 text-[var(--muted)]">
                              {tx("vs")}
                            </span>
                            <span>{next?.opponent}</span>
                          </span>
                          <span className="text-xs text-[var(--muted)]">
                            {tx("goles esperados")}{" "}
                            {data.prediction.expectedOwnGoals} –{" "}
                            {data.prediction.expectedRivalGoals}{" "}
                            {tx("· resultado más probable")}{" "}
                            {data.prediction.mostLikelyScore}
                          </span>
                        </div>
                        {/* Sin tramo de empate: en Copa hay prórroga y penaltis,
                        alguien pasa. Enseñar un empate sería enseñar algo
                        imposible, medido: 0 empates en 862 partidos. */}
                        <BarraDePrediccion
                          tuLabel={data.teamName}
                          tuValor={data.prediction.ownProbability}
                          rivalLabel={next?.opponent ?? tx("el rival")}
                          rivalValor={data.prediction.rivalProbability}
                        />
                        <p className="prosa text-xs leading-relaxed text-[var(--muted)]">
                          {tx("Comparando zona por zona")}{" "}
                          {data.prediction.indirectasPrestadas
                            ? tx("tu alineación enviada")
                            : tx(
                                "tus {{v0}} partido(s) de Copa de esta temporada",
                                { v0: data.prediction.ownMatches },
                              )}{" "}
                          {tx("contra sus")} {data.prediction.rivalMatches}{" "}
                          {tx(
                            "partido(s). El empate se reparte entre los dos porque en Copa alguien tiene que pasar. Tiene en cuenta la táctica, estimada; no sabe de bajas.",
                          )}{" "}
                          <EnlaceATransparencia
                            seccion="pronostico"
                            calculo="pronostico-resumen"
                          />
                        </p>
                        {/* El único aviso, y sólo cuando toca: Hattrick prevé
                        siete ratings para unas órdenes enviadas y no prevé las
                        acciones indirectas a balón parado. */}
                        {data.prediction.indirectasPrestadas && (
                          <p className="prosa text-xs leading-relaxed text-[var(--warning)]">
                            {tx(
                              "Hattrick no prevé las acciones indirectas a balón parado de una alineación enviada, así que esas dos van con tu promedio de Copa. Siete de los nueve duelos son la alineación que mandaste; dos son tu costumbre.",
                            )}
                          </p>
                        )}
                      </div>
                    ) : probability.isError ? (
                      <div className="p-4">
                        <div className="text-lg font-semibold">
                          {tx("No disponible en esta sesión")}
                        </div>
                        <p className="prosa mt-2 text-xs leading-relaxed text-[var(--muted)]">
                          {tx(
                            "El scouting del rival necesita una sesión de Hattrick activa. La fecha y el rival de arriba siguen siendo datos sincronizados; aquí no se sustituye la probabilidad faltante por un valor sintético.",
                          )}
                        </p>
                      </div>
                    ) : probability.data ? (
                      <div className="p-4">
                        <div className="flex items-center gap-4">
                          <div className="text-3xl font-semibold tabular-nums text-[var(--accent)]">
                            {(
                              probability.data.winProbability.ownProbability *
                              100
                            ).toFixed(0)}
                            %
                          </div>
                          <div className="h-2 flex-1 overflow-hidden rounded-full bg-[var(--surface-2)]">
                            <div
                              className="h-full rounded-full bg-[var(--accent)]"
                              style={{
                                width: `${probability.data.winProbability.ownProbability * 100}%`,
                              }}
                            />
                          </div>
                        </div>
                        {/* La reserva: cuando el rival no tiene historia de Copa
                        --su primera ronda-- el motor de zonas no puede decir
                        nada y se enseña el modelo viejo, diciendo cuál es. */}
                        <p className="prosa mt-3 text-xs leading-relaxed text-[var(--muted)]">
                          {tx(
                            "Sin partidos de Copa suficientes de alguno de los dos, así que esto es el modelo por TSI. Estimación",
                          )}{" "}
                          {probability.data.winProbability.confidence}
                          {tx(". TSI de los dos onces de referencia:")}{" "}
                          {number(probability.data.winProbability.ownTsiTotal)}{" "}
                          {tx("contra")}{" "}
                          {number(
                            probability.data.winProbability.rivalTsiTotal,
                          )}
                          .
                        </p>
                      </div>
                    ) : (
                      <p className="p-4 text-xs text-[var(--muted)]">
                        {tx("Calculando…")}
                      </p>
                    )}
                  </ProjectionPanel>
                ) : (
                  <Panel
                    title={tx("Probabilidad de avanzar")}
                    meta={
                      data.status.stillInCup
                        ? tx("sin rival confirmado")
                        : tx("participación cerrada")
                    }
                  >
                    <Note>
                      {data.status.stillInCup
                        ? tx(
                            "Se activará cuando Hattrick publique el próximo cruce.",
                          )
                        : tx(
                            "No hay más cruces: la participación terminó esta temporada.",
                          )}
                    </Note>
                  </Panel>
                )}
              </>
            ) : (
              <TarjetaDeEliminacion data={data} />
            )}

            <Panel
              title={tx("Impacto del tipo de Copa")}
              meta={tx("reglas aplicadas a esta competición")}
            >
              <div className="grid gap-px bg-[var(--border)] sm:grid-cols-3">
                <ImpactFact
                  label={tx("Experiencia")}
                  value={tx("{{v0}}× Liga", {
                    v0: data.impact.experienceMultiplierVsLeague,
                  })}
                  detail={tx("{{v0}} puntos por 90 minutos", {
                    v0: data.impact.experiencePointsPer90,
                  })}
                />
                <ImpactFact
                  label={tx("Club")}
                  value={
                    data.impact.affectsClubMood
                      ? tx("Efecto completo")
                      : tx("Como amistoso")
                  }
                  detail={tx("espíritu, confianza y aficionados")}
                />
                <ImpactFact
                  label={tx("Lesiones")}
                  value={tx("Impacto completo")}
                  detail={data.impact.injuryEffect}
                />
              </div>
            </Panel>
          </>
        )}

        {section === "preparacion" && (
          <>
            <Panel
              title={tx("Próximo partido")}
              meta={tx("fecha y rival confirmados por Hattrick")}
            >
              <NextMatchesPanel matches={data.nextMatches} />
            </Panel>

            <ReferenceElevenPanels data={data} />
          </>
        )}

        {section === "historial" && (
          <>
            <div className="grid items-start gap-4 xl:grid-cols-2">
              <Panel
                title={tx("Economía observada de Copa")}
                meta={tx("asistencia real · ingreso derivado")}
              >
                <div className="grid gap-3 p-4 sm:grid-cols-2">
                  <MiniMetric
                    label={tx("Taquilla bruta observada")}
                    value={money(data.economy.observedGrossGate, data.currency)}
                    detail={tx("{{v0}} partido(s) de local medidos", {
                      v0: data.economy.observedHomeMatches,
                    })}
                  />
                  <MiniMetric
                    label={tx("Participación histórica")}
                    value={money(
                      data.economy.estimatedHistoricalShare,
                      data.currency,
                    )}
                    detail={tx("67% de la taquilla bruta observada")}
                  />
                </div>
                <Note>{data.economy.qualityNote}</Note>
              </Panel>

              <ProjectionPanel
                title={tx("Ingreso del próximo partido")}
                meta={tx("separado de la caja real")}
              >
                <div className="p-4">
                  <div className="text-3xl font-semibold tabular-nums text-[var(--accent)]">
                    {data.economy.nextGateProjection == null
                      ? tx("No calculable")
                      : money(data.economy.nextGateProjection, data.currency)}
                  </div>
                  {data.economy.nextGateProjection != null &&
                    data.economy.estimatedHistoricalShare > 0 && (
                      <div className="mt-3 h-2 overflow-hidden rounded-full bg-[var(--surface-2)]">
                        <div
                          className="h-full rounded-full bg-[var(--accent)]"
                          style={{
                            width: `${Math.min(
                              100,
                              (data.economy.nextGateProjection /
                                data.economy.estimatedHistoricalShare) *
                                100,
                            )}%`,
                          }}
                        />
                      </div>
                    )}
                  <p className="prosa mt-3 text-xs leading-relaxed text-[var(--muted)]">
                    {data.economy.projectionBasis}
                  </p>
                </div>
              </ProjectionPanel>
            </div>

            {data.ladder.length > 0 && (
              <Panel
                title={tx("Trayectoria de la temporada")}
                meta={tx("copas y partidos realmente sincronizados")}
              >
                {/* El único aviso que sobrevive aquí: aparece sólo cuando la
                    ronda que dice Hattrick y la que sale de contar estos
                    partidos no coinciden, y explica un hueco que se VE en el
                    panel de al lado (una copa con menos partidos de los que
                    de verdad se jugaron). */}
                {data.status.countedRounds != null &&
                  data.status.officialRound != null &&
                  data.status.countedRounds !== data.status.officialRound && (
                    <p className="prosa border-b border-[var(--border)] px-4 py-3 text-xs leading-relaxed text-[var(--warning)]">
                      {tx("Vas por la ronda")} {data.status.officialRound}{" "}
                      {tx("y aquí sólo hay")} {data.status.countedRounds}
                      {tx(
                        ": faltan partidos por sincronizar y la trayectoria se queda corta hasta que la próxima sincronización los rescate.",
                      )}
                    </p>
                  )}
                <Ladder steps={data.ladder} />
              </Panel>
            )}

            <Panel
              title={tx("Historial")}
              meta={tx("{{v0}} partido(s) jugados esta temporada", {
                v0: data.history.length,
              })}
            >
              <HistoryTable data={data} />
            </Panel>
          </>
        )}
      </PanelDePestanas>
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
    accent:
      "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]",
    positive:
      "border-[var(--positive)] bg-[color-mix(in_srgb,var(--positive)_12%,transparent)] text-[var(--positive)]",
    muted: "border-[var(--border)] bg-[var(--surface-2)] text-[var(--muted)]",
  };
  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${classes[tone]}`}
    >
      {children}
    </span>
  );
}

function PrizeRoad({
  stages,
  currency,
}: {
  stages: CupPrizeStage[];
  currency: string;
}) {
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
                <div
                  className={`text-[10px] font-semibold uppercase tracking-wide ${current ? "text-[var(--accent)]" : passed ? "text-[var(--positive)]" : "text-[var(--muted)]"}`}
                >
                  {current
                    ? tx("Estás aquí")
                    : passed
                      ? tx("Superado")
                      : stage.winsNeeded != null
                        ? tx("A {{v0}} victoria(s)", { v0: stage.winsNeeded })
                        : tx("Meta")}
                </div>
                <div className="mt-1 text-sm font-semibold">{stage.stage}</div>
                <div className="mt-2 text-xs tabular-nums text-[var(--muted)]">
                  {stage.trophyOnly
                    ? tx("Trofeo · sin premio monetario")
                    : money(stage.amount, currency)}
                </div>
              </div>
              {index < stages.length - 1 && (
                <span className="text-lg text-[var(--muted)]">→</span>
              )}
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
        <div className="text-xs font-semibold uppercase tracking-wide text-[var(--positive)]">
          {tx("Si ganamos")}
        </div>
        <div className="mt-2 text-lg font-semibold">
          {data.scenarios.win.nextStage ?? tx("Siguiente paso")}
        </div>
        <p className="mt-1 text-sm text-[var(--muted)]">
          {data.scenarios.win.description}
        </p>
        {data.scenarios.win.prizeAmount > 0 && (
          <div className="mt-3 text-xs tabular-nums text-[var(--positive)]">
            {tx("Meta económica:")}{" "}
            {money(data.scenarios.win.prizeAmount, data.currency)}
          </div>
        )}
      </div>
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-4">
        <div className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
          {tx("Si perdemos")}
        </div>
        <div className="mt-2 text-lg font-semibold">
          {data.scenarios.loss.continues === true
            ? data.scenarios.loss.destination
            : data.scenarios.loss.continues === false
              ? tx("Fin de la trayectoria")
              : tx("Ruta pendiente")}
        </div>
        <p className="mt-1 text-sm text-[var(--muted)]">
          {data.scenarios.loss.description}
        </p>
        {data.scenarios.loss.prizeAmount > 0 && (
          <div className="mt-3 text-xs tabular-nums text-[var(--muted)]">
            {tx("Premio de esta instancia:")}{" "}
            {money(data.scenarios.loss.prizeAmount, data.currency)}
          </div>
        )}
      </div>
    </div>
  );
}

function NextMatchesPanel({ matches }: { matches: CupNextMatch[] }) {
  if (!matches.length)
    return <Note>{tx("No hay ningún partido de Copa programado.")}</Note>;
  return (
    <ul className="divide-y divide-[var(--border)]">
      {matches.map((match) => (
        <li
          key={match.htMatchId}
          className="flex items-center justify-between gap-3 p-4"
        >
          <div>
            <div className="font-medium">
              <Link
                to={`/rivals/${match.opponentHtTeamId}`}
                className="hover:text-[var(--accent)] hover:underline"
              >
                {match.opponent}
              </Link>
            </div>
            <div className="mt-1 text-xs text-[var(--muted)]">
              {date(match.date)} · {match.venueLabel}
              {match.officialRound != null &&
                tx(" · ronda {{v0}}", { v0: match.officialRound })}
            </div>
          </div>
          <Link
            to={`/rivals/${match.opponentHtTeamId}`}
            className="shrink-0 rounded-md border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--muted)] hover:text-[var(--text)]"
          >
            {tx("Analizar rival")}
          </Link>
        </li>
      ))}
    </ul>
  );
}

function ImpactFact({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="bg-[var(--surface)] p-4">
      <div className="text-xs text-[var(--muted)]">{label}</div>
      <div className="mt-1 text-lg font-semibold">{value}</div>
      <div className="mt-1 text-xs text-[var(--muted)]">{detail}</div>
    </div>
  );
}

function MiniMetric({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-lg bg-[var(--surface-2)] p-3">
      <div className="text-xs text-[var(--muted)]">{label}</div>
      <div className="mt-1 text-xl font-semibold tabular-nums">{value}</div>
      <div className="mt-1 text-[10px] text-[var(--muted)]">{detail}</div>
    </div>
  );
}

/**
 * Las dos tarjetas que dependen del once de referencia, con UN solo selector.
 *
 * 2026-08-19, pedido explícito: el orden de penaltis tiene que moverse con el
 * mismo toggle. Antes el estado vivía dentro de la tarjeta de resistencia y el
 * orden salía de toda la plantilla, así que podía proponer de tirador a
 * alguien que no está en el campo cuando llegan los penaltis.
 */
function ReferenceElevenPanels({ data }: { data: Cup }) {
  const variants = data.readiness.referenceVariants;
  const [mode, setMode] = useState(data.readiness.defaultMode);
  const active = variants.find((v) => v.mode === mode) ?? variants[0];
  return (
    <div className="grid items-start gap-4 xl:grid-cols-2">
      <ProjectionPanel
        title={tx("Preparación para 120 minutos")}
        meta={tx("elige el once de referencia")}
      >
        <StaminaReadiness data={data} mode={mode} onModeChange={setMode} />
      </ProjectionPanel>
      <ProjectionPanel
        title={tx("Orden orientativo de penaltis")}
        meta={active ? active.label.toLowerCase() : ""}
      >
        <PenaltyOrder
          candidates={
            active?.penaltyCandidates ?? data.readiness.penaltyCandidates
          }
          data={data}
        />
      </ProjectionPanel>
    </div>
  );
}

type ReferenceMode = Cup["readiness"]["defaultMode"];

function StaminaReadiness({
  data,
  mode,
  onModeChange,
}: {
  data: Cup;
  mode: ReferenceMode;
  onModeChange: (v: ReferenceMode) => void;
}) {
  const variants = data.readiness.referenceVariants;
  const active = variants.find((v) => v.mode === mode) ?? variants[0];
  const colors = ["var(--danger)", "var(--warning)", "var(--positive)"];
  if (!active)
    return (
      <Note>
        {tx("No hay jugadores activos para calcular la preparación.")}
      </Note>
    );
  const total =
    active.staminaBands.reduce((sum, band) => sum + band.count, 0) || 1;
  return (
    <div className="p-4">
      {/* Las dos variantes enseñan la MISMA preparación calculada contra otra
          referencia: es un parámetro, no una sección. */}
      {variants.length > 1 && (
        <Tabs
          modo="filtro"
          label={tx("Referencia de la preparación")}
          tabs={variants.map((v) => ({ key: v.mode, label: v.label }))}
          active={mode}
          onChange={(v) => onModeChange(v as ReferenceMode)}
        />
      )}
      <div className="mt-4 flex items-end justify-between gap-3">
        <div>
          <div className="text-xs text-[var(--muted)]">
            {tx("Resistencia media")}
          </div>
          <div className="mt-1 text-3xl font-semibold tabular-nums">
            {active.averageStamina != null
              ? active.averageStamina.toFixed(1)
              : "-"}
            <span className="text-sm text-[var(--muted)]"> / 9</span>
          </div>
        </div>
        <div className="text-right text-xs text-[var(--muted)]">
          {active.mode === "top_tsi" ? (
            <>
              {active.startersCount} {tx("jugadores activos con mayor TSI")}
            </>
          ) : (
            <>
              {tx("vs.")} {active.sourceOpponent}
              {active.sourceDate ? (
                <span className="block">{date(active.sourceDate)}</span>
              ) : null}
            </>
          )}
        </div>
      </div>
      <div className="mt-4 flex h-3 overflow-hidden rounded-full bg-[var(--surface-2)]">
        {active.staminaBands.map((band, index) => (
          <div
            key={band.label}
            style={{
              width: `${(band.count / total) * 100}%`,
              background: colors[index],
            }}
          />
        ))}
      </div>
      <div className="mt-4 grid gap-2 sm:grid-cols-3">
        {active.staminaBands.map((band, index) => (
          <div
            key={band.label}
            className="rounded-lg bg-[var(--surface-2)] p-3"
          >
            <div
              className="text-xl font-semibold tabular-nums"
              style={{ color: colors[index] }}
            >
              {band.count}
            </div>
            <div className="text-xs text-[var(--muted)]">{band.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function PenaltyOrder({
  candidates,
  data,
}: {
  candidates: CupPenaltyCandidate[];
  data: Cup;
}) {
  return (
    <div>
      <ol className="divide-y divide-[var(--border)]">
        {candidates.map((player, index) => (
          <li
            key={player.htPlayerId}
            className="grid grid-cols-[2rem_1fr_auto] items-center gap-2 px-4 py-2.5"
          >
            <span className="text-lg font-semibold tabular-nums text-[var(--accent)]">
              {index + 1}
            </span>
            <div>
              <Link
                to={`/players/${player.htPlayerId}`}
                className="text-sm font-medium hover:text-[var(--accent)] hover:underline"
              >
                {player.name}
              </Link>
              <div className="text-[10px] text-[var(--muted)]">
                BP {player.setPieces} {tx("· Anotación")} {player.scoring}{" "}
                {tx("· Experiencia")} {player.experience}
                {player.technical && tx(" · Técnico")}
              </div>
            </div>
            <span className="tabular-nums text-sm font-semibold">
              {player.readinessIndex.toFixed(1)}
            </span>
          </li>
        ))}
      </ol>
      {data.readiness.goalkeeper && (
        <div className="border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
          {tx("Portero de referencia:")}{" "}
          <Link
            to={`/players/${data.readiness.goalkeeper.htPlayerId}`}
            className="font-medium text-[var(--text)] hover:text-[var(--accent)]"
          >
            {data.readiness.goalkeeper.name}
          </Link>
          {tx(" · Portería {{v0}}", { v0: data.readiness.goalkeeper.keeper })}
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
          <div
            key={`${step.cupLevel}-${step.cupLevelIndex}-${step.fromDate}`}
            className="flex items-center gap-2"
          >
            <div className="w-48 rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-3">
              <div className="text-sm font-medium">
                {step.cupName ?? tx("Nivel {{v0}}", { v0: step.cupLevel })}
              </div>
              <div className="mt-1 text-xs text-[var(--muted)]">
                {date(step.fromDate)}
                {step.fromDate !== step.toDate && ` – ${date(step.toDate)}`}
              </div>
              <div className="text-xs text-[var(--muted)]">
                {step.matches} {tx("partido(s)")}
              </div>
            </div>
            {index < steps.length - 1 && (
              <span className="text-lg text-[var(--muted)]">→</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function HistoryTable({ data }: { data: Cup }) {
  if (!data.history.length)
    return (
      <Note>
        {tx("Todavía no hay partidos de Copa jugados sincronizados.")}
      </Note>
    );
  const columns: Column<CupHistoryRow>[] = [
    {
      key: "date",
      header: tx("Fecha"),
      value: (row) => row.date,
      render: (row) => date(row.date),
    },
    {
      key: "opponent",
      header: tx("Rival"),
      value: (row) => row.opponent,
      render: (row) => (
        <Link
          to={`/rivals/${row.opponentHtTeamId}`}
          className="hover:text-[var(--accent)] hover:underline"
        >
          {row.isHome ? "" : "@ "}
          {row.opponent}
        </Link>
      ),
    },
    {
      key: "result",
      header: tx("Resultado"),
      value: (row) => `${row.goalsFor}-${row.goalsAgainst}`,
      render: (row) => (
        <span
          className={
            row.result === "V"
              ? "tabular-nums text-[var(--positive)]"
              : row.result === "D"
                ? "tabular-nums text-[var(--danger)]"
                : "tabular-nums"
          }
        >
          {row.goalsFor}-{row.goalsAgainst}
        </span>
      ),
    },
    {
      key: "hatstats",
      header: tx("HatStats"),
      align: "right",
      value: (row) => row.hatstats ?? -1,
      render: (row) =>
        row.hatstats == null ? (
          <span className="text-[var(--muted)]">-</span>
        ) : (
          <span>{row.hatstats}</span>
        ),
    },
    {
      key: "round",
      header: tx("Ronda"),
      align: "right",
      value: (row) => row.round ?? -1,
      render: (row) =>
        row.round == null ? (
          <span className="text-[var(--muted)]">-</span>
        ) : (
          <span>{row.round}</span>
        ),
    },
    {
      key: "cupName",
      header: tx("Copa"),
      align: "left",
      value: (row) => row.cupName ?? "",
      render: (row) => (
        <span className="text-[var(--muted)]">{row.cupName ?? "-"}</span>
      ),
    },
  ];
  return (
    <DataTable
      emptyMessage={tx("Todavía no hay partidos de copa jugados.")}
      rows={data.history}
      columns={columns}
      rowKey={(row) => row.htMatchId}
      csvName="copa"
      filterPlaceholder={tx("Filtrar por rival…")}
    />
  );
}

/** Dónde se acabó la Copa: la ronda, el rival, el marcador y la fecha, del
 *  último partido de ESA copa en el historial. */
function TarjetaDeEliminacion({ data }: { data: Cup }) {
  const deEstaCopa = data.history
    .filter(
      (h) => data.status.cupName == null || h.cupName === data.status.cupName,
    )
    .sort((a, b) => a.date.localeCompare(b.date));
  const ultimo = deEstaCopa[deEstaCopa.length - 1] ?? null;
  return (
    <Panel
      title={tx("Eliminado de {{v0}}", {
        v0: data.status.cupName ?? "la Copa",
      })}
    >
      <div className="space-y-2 p-4 text-sm">
        {ultimo ? (
          <p>
            {tx("Eliminado")}
            {ultimo.round != null
              ? tx(" en la ronda {{v0}}", { v0: ultimo.round })
              : ""}{" "}
            {tx("contra")} <b>{ultimo.opponent}</b>,{" "}
            <b className="tabular-nums">
              {ultimo.goalsFor} - {ultimo.goalsAgainst}
            </b>{" "}
            ({ultimo.isHome ? tx("en casa") : tx("fuera")}
            {tx("), el")} {date(ultimo.date)}.
          </p>
        ) : (
          <p>{tx("No quedan cruces esta temporada.")}</p>
        )}
        {data.goal.securedAmount > 0 && (
          <p>
            {tx("Premio conseguido:")}{" "}
            <b className="tabular-nums">
              {money(data.goal.securedAmount, data.currency)}
            </b>
            .
          </p>
        )}
        <p className="text-xs text-[var(--muted)]">
          {tx(
            "No quedan cruces esta temporada. Todos los partidos están en la pestaña Historial.",
          )}
        </p>
      </div>
    </Panel>
  );
}
