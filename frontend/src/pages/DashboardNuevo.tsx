import { useState } from "react";
import { Link } from "react-router-dom";
import {
  useChangesHistory,
  useCup,
  useDashboard,
  useEconomy,
  useInsights,
  useLeague,
  useLineup,
  useMatches,
} from "../hooks/useTeam";
import {
  Empty,
  ErrorState,
  Loading,
  Panel,
  SinDatos,
} from "../components/Panels";
import { BarraDePrediccion } from "../components/BarraDePrediccion";
import { SplitSelector } from "../components/SplitSelector";
import { FORMATIONS } from "../services/api";
import type { Dashboard } from "../services/api";
import { money, percent } from "../hooks/useFormat";
import { skillLevelLabel } from "../utils/skillLevels";
import { FlorDeFuerza } from "../components/FlorDeFuerza";
import { AlertsBand, BestElevenPitch, TrainingPanel } from "./DashboardPage";

/**
 * El Dashboard de la propuesta del 2026-09-13, reordenado el 2026-09-15:
 * próximo partido; la flor con las alertas; forma, moral y caja; liga y copa;
 * y el mejor once con el entrenamiento al final.
 *
 * Vive aparte de `DashboardPage` a propósito, para poder volver al de antes
 * cambiando una línea en `App.tsx`. Los paneles que no cambian (alertas, radar,
 * mejor once, entrenamiento) se importan de allí y no se copian.
 */
export function DashboardNuevo() {
  const { data, isLoading, isError, error } = useDashboard();
  const insights = useInsights();
  const [formacion, setFormacion] = useState("");
  const [centrales, setCentrales] = useState<number | undefined>(undefined);
  const [interiores, setInteriores] = useState<number | undefined>(undefined);
  const lineup = useLineup(formacion || undefined, centrales, interiores);

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return <SinDatos />;

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-semibold">{data.teamName}</h1>
        <p className="text-sm text-[var(--muted)]">
          {data.squad?.playerCount ?? 0} jugadores · edad media{" "}
          {data.squad?.avgAge ?? "-"}
        </p>
      </header>

      {/* 2026-09-15, pedido del usuario: el bloque «Importación completada ·
          Empieza por una decisión real» ya no sale nunca, ni con ?welcome=1. */}
      <ProximoPartido />

      {/* 2026-09-15, opción A elegida por el usuario: la flor y las alertas en
          la primera pantalla. La mitad de las visitas duraba menos de 25
          segundos y la flor iba en el quinto bloque, donde casi nadie llegaba.
          La flor sustituyó al radar el 2026-09-13; el radar sigue en
          components/RadarConPorque.tsx por si se quiere volver. */}
      <div className="grid gap-4 lg:grid-cols-3 [&>*]:min-w-0">
        <div className="lg:col-span-2">
          <FlorDeFuerza />
        </div>
        <AlertsBand
          insights={insights.data ?? []}
          loading={insights.isLoading}
          failed={insights.isError}
        />
      </div>

      <div className="grid gap-4 md:grid-cols-3 [&>*]:min-w-0">
        <FormaDelEquipo />
        <MoralYConfianza training={data.training} />
        {/* El Balance bisemanal vive dentro de Caja: los dos son dinero. El
            TSI de los 11 mejores ya lo enseña un pétalo de la flor. */}
        <CajaProyectada
          balanceBisemanal={data.finance?.biweeklyBalance ?? null}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-2 [&>*]:min-w-0">
        <LigaResumida />
        <CopaResumida />
      </div>

      <div className="grid gap-4 lg:grid-cols-3 [&>*]:min-w-0">
        <div className="lg:col-span-2">
          <Panel
            title="Mejor once"
            meta={
              lineup.data
                ? `${lineup.data.formation} · índice ${lineup.data.totalRating}`
                : ""
            }
          >
            <div className="flex flex-wrap items-center gap-3 border-b border-[var(--border)] px-4 py-3">
              <label className="flex items-center gap-2 text-xs text-[var(--muted)]">
                Formación
                <select
                  value={formacion}
                  onChange={(e) => {
                    setFormacion(e.target.value);
                    setCentrales(undefined);
                    setInteriores(undefined);
                  }}
                  className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-sm text-[var(--text)]"
                >
                  <option value="">Mejor formación</option>
                  {FORMATIONS.map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </select>
              </label>
              {formacion && lineup.data && (
                <>
                  <SplitSelector
                    label="Defensa central"
                    value={lineup.data.centralDefenders}
                    options={lineup.data.centralDefenderOptions}
                    onChange={setCentrales}
                  />
                  <SplitSelector
                    label="Medio central"
                    value={lineup.data.innerMidfielders}
                    options={lineup.data.innerMidfielderOptions}
                    onChange={setInteriores}
                  />
                </>
              )}
            </div>
            {lineup.data ? (
              <BestElevenPitch
                lineup={lineup.data.lineup}
                formation={lineup.data.formation}
              />
            ) : (
              <Empty>Sincroniza para calcular la alineación.</Empty>
            )}
          </Panel>
        </div>
        <div className="grid content-start gap-4">
          {data.training && <TrainingPanel training={data.training} />}
          <SubidasRecientes />
        </div>
      </div>
    </div>
  );
}

/** Mismas 2.000 simulaciones que el radar: misma clave de caché, una sola
 *  petición para los tres paneles que leen la liga. */
const RUNS_DEL_DASHBOARD = 2_000;

function ProximoPartido() {
  const league = useLeague(RUNS_DEL_DASHBOARD);
  if (league.isLoading) {
    return (
      <Panel title="Próximo partido">
        <div className="p-4">
          <Loading />
        </div>
      </Panel>
    );
  }
  const nm = league.data?.nextMatch;
  if (!league.data || !nm) {
    return (
      <Panel title="Próximo partido">
        <Empty>No hay partido de liga pendiente.</Empty>
      </Panel>
    );
  }
  const fecha = league.data.fixtures.find(
    (f) =>
      f.matchRound === nm.round &&
      f.home === nm.home &&
      f.away === nm.away &&
      !f.played,
  )?.date;
  const tuNombre = nm.isHome ? nm.home : nm.away;
  const suNombre = nm.isHome ? nm.away : nm.home;
  const ordenesEnviadas = nm.sources?.own.kind === "submitted";

  return (
    <Panel
      title="Próximo partido"
      meta={`${fecha ? `${fecha} · ` : ""}Liga, jornada ${nm.round} · ${
        nm.isHome ? "en casa" : "fuera"
      }`}
    >
      <div className="space-y-3 p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <span className="text-lg">
            <span className={nm.isHome ? "font-semibold" : ""}>{nm.home}</span>
            <span className="mx-2 text-sm text-[var(--muted)]">vs</span>
            <span className={!nm.isHome ? "font-semibold" : ""}>{nm.away}</span>
          </span>
          <span className="text-xs text-[var(--muted)]">
            resultado más probable {nm.mostLikelyScore}
          </span>
        </div>
        <BarraDePrediccion
          tuLabel={tuNombre}
          tuValor={nm.isHome ? nm.homeWin : nm.awayWin}
          rivalLabel={suNombre}
          rivalValor={nm.isHome ? nm.awayWin : nm.homeWin}
          empate={nm.draw}
        />
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span
            className={`rounded px-2 py-0.5 text-xs ${
              ordenesEnviadas
                ? "bg-[var(--positive)]/15 text-[var(--positive)]"
                : "bg-[var(--warning)]/15 text-[var(--warning)]"
            }`}
          >
            {ordenesEnviadas ? "Órdenes enviadas" : "Órdenes sin enviar"}
          </span>
          <span className="flex gap-4 text-xs">
            <Link to="/lineup" className="text-[var(--accent)] hover:underline">
              Alineación →
            </Link>
            <Link to="/rivals" className="text-[var(--accent)] hover:underline">
              Estudiar al rival →
            </Link>
          </span>
        </div>
      </div>
    </Panel>
  );
}

function LigaResumida() {
  const league = useLeague(RUNS_DEL_DASHBOARD);
  if (league.isLoading) {
    return (
      <Panel title="Liga">
        <div className="p-4">
          <Loading />
        </div>
      </Panel>
    );
  }
  const data = league.data;
  if (!data || data.standings.length === 0) {
    return (
      <Panel title="Liga">
        <Empty>Todavía no hay clasificación de tu serie.</Empty>
      </Panel>
    );
  }
  const tabla = data.standings;
  const mio = tabla.findIndex((s) => s.isOwnTeam);
  // Tu fila y las de alrededor: arriba del todo, los tres primeros; abajo del
  // todo, los tres últimos; en medio, el de arriba y el de abajo.
  const desde = Math.max(0, Math.min(mio - 1, tabla.length - 3));
  const filas = tabla.slice(desde, desde + 3);
  const titulo = new Map(
    data.outlook.map((o) => [o.htTeamId, o.titleProbability]),
  );
  const jornadas = data.roundsPlayed + data.roundsRemaining;

  return (
    <Panel
      title={`Liga · ${data.seriesName ?? ""}`}
      meta={`jornada ${data.roundsPlayed} de ${jornadas}`}
    >
      <div className="p-4">
        <div className="mb-1 grid grid-cols-[1fr_auto_auto] gap-x-6 text-xs text-[var(--muted)]">
          <span>Equipo</span>
          <span className="text-right">Pts</span>
          <span className="w-12 text-right">Título</span>
        </div>
        {filas.map((s) => (
          <div
            key={s.htTeamId}
            className={`grid grid-cols-[1fr_auto_auto] gap-x-6 rounded px-2 py-1.5 text-sm ${
              s.isOwnTeam ? "bg-[var(--accent-soft)] font-semibold" : ""
            }`}
          >
            <span className="truncate">
              {s.position} {s.name}
            </span>
            <span className="text-right tabular-nums">{s.points}</span>
            <span className="w-12 text-right tabular-nums">
              {percent((titulo.get(s.htTeamId) ?? 0) * 100, 0)}
            </span>
          </div>
        ))}
        <div className="mt-3 flex items-center justify-between text-xs text-[var(--muted)]">
          <span>
            {data.ownOutlook
              ? `Puntos esperados al final: ${data.ownOutlook.expectedPoints.toLocaleString("es", { maximumFractionDigits: 1 })}`
              : ""}
          </span>
          <Link to="/league" className="text-[var(--accent)] hover:underline">
            Ver Liga →
          </Link>
        </div>
      </div>
    </Panel>
  );
}

/** Copa y, si lo juegas, Hattrick Masters. Si no sigues vivo en ninguno, el
 *  panel lo dice en una línea en vez de ocupar media fila con ceros. */
function CopaResumida() {
  const cup = useCup();
  if (cup.isLoading) {
    return (
      <Panel title="Copa">
        <div className="p-4">
          <Loading />
        </div>
      </Panel>
    );
  }
  const data = cup.data;
  const masters = (data?.mastersRivals ?? []).filter((r) => !r.played);
  const proximoMasters = masters.sort((a, b) =>
    a.date.localeCompare(b.date),
  )[0];
  if (!data || (!data.status.stillInCup && !proximoMasters)) {
    return (
      <Panel title="Copa">
        <Empty>
          {data?.currentCupName
            ? `Quedaste fuera de la ${data.currentCupName} esta temporada.`
            : "Ya no sigues en ninguna copa esta temporada."}
        </Empty>
      </Panel>
    );
  }
  const proximo = data.nextMatches[0];
  const avance =
    data.goal.titleAmount > 0
      ? Math.min(100, (data.goal.securedAmount / data.goal.titleAmount) * 100)
      : 0;

  return (
    <Panel
      title="Copa"
      meta={
        data.status.stillInCup ? (
          <span className="rounded bg-[var(--positive)]/15 px-2 py-0.5 text-[var(--positive)]">
            sigues vivo
          </span>
        ) : undefined
      }
    >
      <div className="space-y-3 p-4 text-sm">
        {data.status.stillInCup && (
          <div>
            <div className="font-medium">
              {data.currentCupName ?? "Copa"}
              {data.status.stageLabel ? ` · ${data.status.stageLabel}` : ""}
            </div>
            <div className="text-xs text-[var(--muted)]">
              {proximo
                ? `próximo: ${proximo.date} vs ${proximo.opponent}`
                : "sin cruce sorteado todavía"}
            </div>
            {data.goal.titleAmount > 0 && (
              <>
                <div className="mt-2 h-2 overflow-hidden rounded bg-[var(--surface-2)]">
                  <div
                    className="h-full rounded bg-[var(--accent)]"
                    style={{ width: `${avance}%` }}
                  />
                </div>
                <div className="mt-1 flex justify-between text-xs text-[var(--muted)]">
                  <span>
                    Asegurado {money(data.goal.securedAmount)} {data.currency}
                  </span>
                  <span>
                    Título {money(data.goal.titleAmount)} {data.currency}
                  </span>
                </div>
              </>
            )}
          </div>
        )}
        {proximoMasters && (
          <div>
            <div className="font-medium">Hattrick Masters</div>
            <div className="text-xs text-[var(--muted)]">
              próximo: {proximoMasters.date} vs {proximoMasters.opponent}
            </div>
          </div>
        )}
        <div className="text-right text-xs">
          <Link to="/cup" className="text-[var(--accent)] hover:underline">
            Ver Copa →
          </Link>
        </div>
      </div>
    </Panel>
  );
}

function FormaDelEquipo() {
  const matches = useMatches(false);
  if (matches.isLoading) {
    return (
      <Panel title="Forma">
        <div className="p-4">
          <Loading />
        </div>
      </Panel>
    );
  }
  const ultimos = [...(matches.data?.matches ?? [])]
    .sort((a, b) => a.date.localeCompare(b.date))
    .slice(-5);
  if (ultimos.length === 0) {
    return (
      <Panel title="Forma">
        <Empty>Todavía no hay partidos oficiales jugados.</Empty>
      </Panel>
    );
  }
  // 2026-09-13, pedido del usuario: la línea suelta de HatStats no se
  // reconocía. Ahora es una columna por partido: su HatStats encima, la barra
  // del color del resultado y, debajo, el resultado, el marcador y el rival.
  // Las barras arrancan en cero para que la altura compare de verdad.
  const color = (r: string) =>
    r === "V"
      ? "var(--positive)"
      : r === "D"
        ? "var(--danger)"
        : "var(--muted)";
  const max = Math.max(1, ...ultimos.map((m) => m.hatstats ?? 0));

  return (
    <Panel title="Forma" meta="últimos 5 oficiales · HatStats">
      <div className="p-4">
        <div className="grid grid-cols-5 items-end gap-2">
          {ultimos.map((m) => (
            <div
              key={m.htMatchId}
              title={`${m.date} · ${m.isHome ? "en casa" : "fuera"} vs ${m.opponent} · ${m.goalsFor}-${m.goalsAgainst}`}
              className="flex min-w-0 flex-col items-center"
            >
              <span className="text-xs tabular-nums text-[var(--muted)]">
                {m.hatstats ?? "-"}
              </span>
              <div className="mt-1 flex h-16 w-full items-end">
                <div
                  className="w-full rounded-t"
                  style={{
                    height: `${((m.hatstats ?? 0) / max) * 100}%`,
                    minHeight: 2,
                    background: color(m.result),
                    opacity: 0.75,
                  }}
                />
              </div>
              <span
                className="mt-1 text-sm font-semibold"
                style={{ color: color(m.result) }}
              >
                {m.result}
              </span>
              <span className="text-xs tabular-nums">
                {m.goalsFor}-{m.goalsAgainst}
              </span>
              <span className="w-full truncate text-center text-[11px] text-[var(--muted)]">
                {m.opponent}
              </span>
            </div>
          ))}
        </div>
        <div className="mt-2 flex justify-between text-[11px] text-[var(--muted)]">
          <span>← más antiguo</span>
          <span>más reciente →</span>
        </div>
      </div>
    </Panel>
  );
}

function MoralYConfianza({ training }: { training: Dashboard["training"] }) {
  if (!training || (training.morale == null && training.confidence == null)) {
    return (
      <Panel title="Moral">
        <Empty>Sin dato de espíritu ni confianza.</Empty>
      </Panel>
    );
  }
  // Las escalas de Hattrick: espíritu de 0 a 10, confianza de 0 a 9.
  const barras = [
    {
      label: "Espíritu del equipo",
      nombre: training.moraleName,
      valor: training.morale,
      max: 10,
    },
    {
      label: "Confianza",
      nombre: training.confidenceName,
      valor: training.confidence,
      max: 9,
    },
  ];
  return (
    <Panel title="Moral">
      <div className="space-y-4 p-4">
        {barras.map((b) => {
          const pct = b.valor == null ? 0 : (b.valor / b.max) * 100;
          const color =
            pct >= 60
              ? "var(--positive)"
              : pct >= 35
                ? "var(--warning)"
                : "var(--danger)";
          return (
            <div key={b.label}>
              <div className="flex items-baseline justify-between text-sm">
                <span>{b.label}</span>
                <span className="text-xs text-[var(--muted)]">
                  {b.nombre}
                  {b.valor != null ? ` (${b.valor})` : ""}
                </span>
              </div>
              <div className="mt-1 h-2 overflow-hidden rounded bg-[var(--surface-2)]">
                <div
                  className="h-full rounded"
                  style={{ width: `${pct}%`, background: color }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

/** La caja de las semanas cerradas y, a continuación, la proyección SIN
 *  compraventa: la misma línea discontinua de Economía. */
function CajaProyectada({
  balanceBisemanal,
}: {
  balanceBisemanal: number | null;
}) {
  // Sin la proyección por series de tiempo: aquí no se enseña y es lo más
  // caro de la consulta (2026-09-14).
  const economy = useEconomy(52, false);
  if (economy.isLoading) {
    return (
      <Panel title="Caja">
        <div className="p-4">
          <Loading />
        </div>
      </Panel>
    );
  }
  const data = economy.data;
  if (!data) {
    return (
      <Panel title="Caja">
        <Empty>Sin cierres semanales sincronizados.</Empty>
      </Panel>
    );
  }
  const historia = data.series.slice(-8).map((s) => s.cash);
  const proyeccion = data.structuralForecast.p50;
  const semanaCero = proyeccion.findIndex((v) => v <= 0);
  const valores = [...historia, ...proyeccion, 0];
  const min = Math.min(...valores);
  const max = Math.max(...valores);
  const total = historia.length + proyeccion.length;
  const x = (i: number) => (total <= 1 ? 0 : (i / (total - 1)) * 196 + 2);
  const y = (v: number) =>
    max === min ? 30 : 56 - ((v - min) / (max - min)) * 52;
  const linea = (vals: number[], desde: number) =>
    vals.map((v, i) => `${x(desde + i)},${y(v)}`).join(" ");
  const ultimoReal = historia.length - 1;

  return (
    <Panel title="Caja" meta={data.currency}>
      <div className="space-y-2 p-4">
        <div className="text-2xl font-semibold tabular-nums">
          {money(data.cash)}
        </div>
        <div className="flex items-baseline justify-between gap-2 text-xs">
          <span className="text-[var(--muted)]">Balance bisemanal</span>
          <span
            className="font-medium tabular-nums"
            style={{
              color:
                balanceBisemanal == null
                  ? "var(--muted)"
                  : balanceBisemanal < 0
                    ? "var(--danger)"
                    : "var(--positive)",
            }}
          >
            {balanceBisemanal == null
              ? "hacen falta dos cierres semanales"
              : money(balanceBisemanal)}
          </span>
        </div>
        <svg
          viewBox="0 0 200 60"
          className="h-16 w-full"
          role="img"
          aria-label="Caja de las últimas semanas y proyección sin compraventa"
        >
          <line
            x1="0"
            x2="200"
            y1={y(0)}
            y2={y(0)}
            stroke="var(--danger)"
            strokeWidth="1"
            strokeDasharray="3 3"
          />
          <polyline
            points={linea(historia, 0)}
            fill="none"
            stroke="var(--accent)"
            strokeWidth="2"
          />
          {ultimoReal >= 0 && (
            <polyline
              points={linea([historia[ultimoReal]!, ...proyeccion], ultimoReal)}
              fill="none"
              stroke="var(--accent)"
              strokeWidth="2"
              strokeDasharray="4 3"
            />
          )}
        </svg>
        <div
          className="text-xs"
          style={{
            color: semanaCero >= 0 ? "var(--warning)" : "var(--muted)",
          }}
        >
          {/* 2026-09-13, pedido del usuario: «sin compraventa, no llega a
              cero en 52 semanas» no se entendía. Se dice con cuánto se queda. */}
          {semanaCero >= 0
            ? `Si no compras ni vendes jugadores, te quedas sin caja en unas ${data.structuralForecast.weeks[semanaCero]} semanas.`
            : `Si no compras ni vendes jugadores, dentro de ${proyeccion.length} semanas tendrías ${money(proyeccion[proyeccion.length - 1] ?? 0)} ${data.currency}.`}
        </div>
        <div className="text-right text-xs">
          <Link to="/economy" className="text-[var(--accent)] hover:underline">
            Ver Economía →
          </Link>
        </div>
      </div>
    </Panel>
  );
}

/** Las subidas de habilidad de la última semana, de más reciente a más vieja. */
function SubidasRecientes() {
  const cambios = useChangesHistory(null, 1);
  if (cambios.isLoading) {
    return (
      <Panel title="Subidas recientes">
        <div className="p-4">
          <Loading />
        </div>
      </Panel>
    );
  }
  const subidas = (cambios.data?.skillChanges ?? [])
    .filter((c) => (c.delta ?? 0) > 0 && !c.isYouth)
    .sort((a, b) => b.capturedAt.localeCompare(a.capturedAt))
    .slice(0, 5);
  return (
    <Panel title="Subidas recientes" meta="última semana">
      {subidas.length === 0 ? (
        <Empty>Ninguna subida esta semana.</Empty>
      ) : (
        <ul className="divide-y divide-[var(--border)]">
          {subidas.map((c) => (
            <li
              key={`${c.htPlayerId}-${c.key}-${c.capturedAt}`}
              className="flex items-baseline justify-between gap-2 px-4 py-2 text-sm"
            >
              <Link
                to={`/players/${c.htPlayerId}`}
                className="truncate hover:text-[var(--accent)] hover:underline"
              >
                <span className="text-[var(--positive)]">▲</span> {c.name}
              </Link>
              <span className="shrink-0 text-xs text-[var(--muted)]">
                {c.label} ·{" "}
                {c.before != null ? `${skillLevelLabel(c.before)} → ` : ""}
                {skillLevelLabel(c.current)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
