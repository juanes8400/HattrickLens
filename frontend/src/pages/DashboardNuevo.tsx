import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
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
import { nivelOficial } from "../i18n/glosario";

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
  const { t } = useTranslation();
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
          {t("dashboard.plantilla", "{{n}} jugadores · edad media {{edad}}", {
            n: data.squad?.playerCount ?? 0,
            edad: data.squad?.avgAge ?? "-",
          })}
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
            title={t("dashboard.mejorOnce", "Mejor once")}
            meta={
              lineup.data
                ? t(
                    "dashboard.mejorOnceMeta",
                    "{{formacion}} · índice {{indice}}",
                    {
                      formacion: lineup.data.formation,
                      indice: lineup.data.totalRating,
                    },
                  )
                : ""
            }
          >
            <div className="flex flex-wrap items-center gap-3 border-b border-[var(--border)] px-4 py-3">
              <label className="flex items-center gap-2 text-xs text-[var(--muted)]">
                {t("dashboard.formacion", "Formación")}
                <select
                  value={formacion}
                  onChange={(e) => {
                    setFormacion(e.target.value);
                    setCentrales(undefined);
                    setInteriores(undefined);
                  }}
                  className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-sm text-[var(--text)]"
                >
                  <option value="">
                    {t("dashboard.mejorFormacion", "Mejor formación")}
                  </option>
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
                    label={t("comun.defensaCentral", "Defensa central")}
                    value={lineup.data.centralDefenders}
                    options={lineup.data.centralDefenderOptions}
                    onChange={setCentrales}
                  />
                  <SplitSelector
                    label={t("comun.medioCentral", "Medio central")}
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
              <Empty>
                {t(
                  "dashboard.sincronizaAlineacion",
                  "Sincroniza para calcular la alineación.",
                )}
              </Empty>
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
  const { t } = useTranslation();
  const league = useLeague(RUNS_DEL_DASHBOARD);
  const titulo = t("dashboard.proximoPartido", "Próximo partido");
  if (league.isLoading) {
    return (
      <Panel title={titulo}>
        <div className="p-4">
          <Loading />
        </div>
      </Panel>
    );
  }
  const nm = league.data?.nextMatch;
  if (!league.data || !nm) {
    return (
      <Panel title={titulo}>
        <Empty>
          {t("dashboard.sinPartidoLiga", "No hay partido de liga pendiente.")}
        </Empty>
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
      title={titulo}
      meta={`${fecha ? `${fecha} · ` : ""}${t(
        "dashboard.metaPartido",
        "Liga, jornada {{jornada}} · {{sede}}",
        {
          jornada: nm.round,
          sede: nm.isHome
            ? t("comun.enCasa", "en casa")
            : t("comun.fuera", "fuera"),
        },
      )}`}
    >
      <div className="space-y-3 p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <span className="text-lg">
            <span className={nm.isHome ? "font-semibold" : ""}>{nm.home}</span>
            <span className="mx-2 text-sm text-[var(--muted)]">vs</span>
            <span className={!nm.isHome ? "font-semibold" : ""}>{nm.away}</span>
          </span>
          <span className="text-xs text-[var(--muted)]">
            {t("dashboard.masProbable", "resultado más probable {{marcador}}", {
              marcador: nm.mostLikelyScore,
            })}
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
            {ordenesEnviadas
              ? t("dashboard.ordenesEnviadas", "Órdenes enviadas")
              : t("dashboard.ordenesSinEnviar", "Órdenes sin enviar")}
          </span>
          <span className="flex gap-4 text-xs">
            <Link to="/lineup" className="text-[var(--accent)] hover:underline">
              {t("dashboard.irAlineacion", "Alineación →")}
            </Link>
            <Link to="/rivals" className="text-[var(--accent)] hover:underline">
              {t("dashboard.estudiarRival", "Estudiar al rival →")}
            </Link>
          </span>
        </div>
      </div>
    </Panel>
  );
}

function LigaResumida() {
  const { t, i18n } = useTranslation();
  const league = useLeague(RUNS_DEL_DASHBOARD);
  const titulo = t("dashboard.liga", "Liga");
  if (league.isLoading) {
    return (
      <Panel title={titulo}>
        <div className="p-4">
          <Loading />
        </div>
      </Panel>
    );
  }
  const data = league.data;
  if (!data || data.standings.length === 0) {
    return (
      <Panel title={titulo}>
        <Empty>
          {t(
            "dashboard.sinClasificacion",
            "Todavía no hay clasificación de tu serie.",
          )}
        </Empty>
      </Panel>
    );
  }
  const tabla = data.standings;
  const mio = tabla.findIndex((s) => s.isOwnTeam);
  // Tu fila y las de alrededor: arriba del todo, los tres primeros; abajo del
  // todo, los tres últimos; en medio, el de arriba y el de abajo.
  const desde = Math.max(0, Math.min(mio - 1, tabla.length - 3));
  const filas = tabla.slice(desde, desde + 3);
  const tituloProb = new Map(
    data.outlook.map((o) => [o.htTeamId, o.titleProbability]),
  );
  const jornadas = data.roundsPlayed + data.roundsRemaining;

  return (
    <Panel
      title={`${titulo} · ${data.seriesName ?? ""}`}
      meta={t("dashboard.jornadaDe", "jornada {{n}} de {{total}}", {
        n: data.roundsPlayed,
        total: jornadas,
      })}
    >
      <div className="p-4">
        <div className="mb-1 grid grid-cols-[1fr_auto_auto] gap-x-6 text-xs text-[var(--muted)]">
          <span>{t("dashboard.equipo", "Equipo")}</span>
          <span className="text-right">{t("dashboard.pts", "Pts")}</span>
          <span className="w-12 text-right">
            {t("dashboard.titulo", "Título")}
          </span>
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
              {percent((tituloProb.get(s.htTeamId) ?? 0) * 100, 0)}
            </span>
          </div>
        ))}
        <div className="mt-3 flex items-center justify-between text-xs text-[var(--muted)]">
          <span>
            {data.ownOutlook
              ? t(
                  "dashboard.puntosEsperados",
                  "Puntos esperados al final: {{puntos}}",
                  {
                    puntos: data.ownOutlook.expectedPoints.toLocaleString(
                      i18n.language,
                      { maximumFractionDigits: 1 },
                    ),
                  },
                )
              : ""}
          </span>
          <Link to="/league" className="text-[var(--accent)] hover:underline">
            {t("dashboard.verLiga", "Ver Liga →")}
          </Link>
        </div>
      </div>
    </Panel>
  );
}

/** Copa y, si lo juegas, Hattrick Masters. Si no sigues vivo en ninguno, el
 *  panel lo dice en una línea en vez de ocupar media fila con ceros. */
function CopaResumida() {
  const { t } = useTranslation();
  const cup = useCup();
  const titulo = t("dashboard.copa", "Copa");
  if (cup.isLoading) {
    return (
      <Panel title={titulo}>
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
      <Panel title={titulo}>
        <Empty>
          {data?.currentCupName
            ? t(
                "dashboard.fueraDeCopa",
                "Quedaste fuera de la {{copa}} esta temporada.",
                { copa: data.currentCupName },
              )
            : t(
                "dashboard.sinCopa",
                "Ya no sigues en ninguna copa esta temporada.",
              )}
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
      title={titulo}
      meta={
        data.status.stillInCup ? (
          <span className="rounded bg-[var(--positive)]/15 px-2 py-0.5 text-[var(--positive)]">
            {t("dashboard.sigueVivo", "sigues vivo")}
          </span>
        ) : undefined
      }
    >
      <div className="space-y-3 p-4 text-sm">
        {data.status.stillInCup && (
          <div>
            <div className="font-medium">
              {data.currentCupName ?? titulo}
              {data.status.stageLabel ? ` · ${data.status.stageLabel}` : ""}
            </div>
            <div className="text-xs text-[var(--muted)]">
              {proximo
                ? t(
                    "dashboard.proximoCruce",
                    "próximo: {{fecha}} vs {{rival}}",
                    {
                      fecha: proximo.date,
                      rival: proximo.opponent,
                    },
                  )
                : t("dashboard.sinCruce", "sin cruce sorteado todavía")}
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
                    {t("dashboard.asegurado", "Asegurado {{cifra}}", {
                      cifra: money(data.goal.securedAmount, data.currency),
                    })}
                  </span>
                  <span>
                    {t("dashboard.tituloCifra", "Título {{cifra}}", {
                      cifra: money(data.goal.titleAmount, data.currency),
                    })}
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
              {t("dashboard.proximoCruce", "próximo: {{fecha}} vs {{rival}}", {
                fecha: proximoMasters.date,
                rival: proximoMasters.opponent,
              })}
            </div>
          </div>
        )}
        <div className="text-right text-xs">
          <Link to="/cup" className="text-[var(--accent)] hover:underline">
            {t("dashboard.verCopa", "Ver Copa →")}
          </Link>
        </div>
      </div>
    </Panel>
  );
}

function FormaDelEquipo() {
  const { t } = useTranslation();
  const matches = useMatches(false);
  const titulo = t("dashboard.forma", "Forma");
  if (matches.isLoading) {
    return (
      <Panel title={titulo}>
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
      <Panel title={titulo}>
        <Empty>
          {t(
            "dashboard.sinPartidos",
            "Todavía no hay partidos oficiales jugados.",
          )}
        </Empty>
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
    <Panel
      title={titulo}
      meta={t("dashboard.formaMeta", "últimos 5 oficiales · HatStats")}
    >
      <div className="p-4">
        <div className="grid grid-cols-5 items-end gap-2">
          {ultimos.map((m) => (
            <div
              key={m.htMatchId}
              title={t(
                "dashboard.partidoTitle",
                "{{fecha}} · {{sede}} vs {{rival}} · {{marcador}}",
                {
                  fecha: m.date,
                  sede: m.isHome
                    ? t("comun.enCasa", "en casa")
                    : t("comun.fuera", "fuera"),
                  rival: m.opponent,
                  marcador: `${m.goalsFor}-${m.goalsAgainst}`,
                },
              )}
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
                {t(`comun.resultado.${m.result}`, m.result)}
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
          <span>{t("dashboard.masAntiguo", "← más antiguo")}</span>
          <span>{t("dashboard.masReciente", "más reciente →")}</span>
        </div>
      </div>
    </Panel>
  );
}

function MoralYConfianza({ training }: { training: Dashboard["training"] }) {
  const { t } = useTranslation();
  const titulo = t("dashboard.moral", "Moral");
  if (!training || (training.morale == null && training.confidence == null)) {
    return (
      <Panel title={titulo}>
        <Empty>
          {t("dashboard.sinMoral", "Sin dato de espíritu ni confianza.")}
        </Empty>
      </Panel>
    );
  }
  // Las escalas de Hattrick: espíritu de 0 a 10, confianza de 0 a 9.
  const barras = [
    {
      clave: "espiritu",
      label: t("dashboard.espiritu", "Espíritu del equipo"),
      nombre: nivelOficial("espiritu", training.morale) ?? training.moraleName,
      valor: training.morale,
      max: 10,
    },
    {
      clave: "confianza",
      label: t("dashboard.confianza", "Confianza"),
      nombre:
        nivelOficial("confianza", training.confidence) ?? training.confidenceName,
      valor: training.confidence,
      max: 9,
    },
  ];
  return (
    <Panel title={titulo}>
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
            <div key={b.clave}>
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
  const { t } = useTranslation();
  // Sin la proyección por series de tiempo: aquí no se enseña y es lo más
  // caro de la consulta (2026-09-14).
  const economy = useEconomy(52, false);
  const titulo = t("dashboard.caja", "Caja");
  if (economy.isLoading) {
    return (
      <Panel title={titulo}>
        <div className="p-4">
          <Loading />
        </div>
      </Panel>
    );
  }
  const data = economy.data;
  if (!data) {
    return (
      <Panel title={titulo}>
        <Empty>
          {t("dashboard.sinCierres", "Sin cierres semanales sincronizados.")}
        </Empty>
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
    <Panel title={titulo} meta={data.currency}>
      <div className="space-y-2 p-4">
        <div className="text-2xl font-semibold tabular-nums">
          {money(data.cash)}
        </div>
        <div className="flex items-baseline justify-between gap-2 text-xs">
          <span className="text-[var(--muted)]">
            {t("dashboard.balanceBisemanal", "Balance bisemanal")}
          </span>
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
              ? t(
                  "dashboard.faltanCierres",
                  "hacen falta dos cierres semanales",
                )
              : money(balanceBisemanal)}
          </span>
        </div>
        <svg
          viewBox="0 0 200 60"
          className="h-16 w-full"
          role="img"
          aria-label={t(
            "dashboard.cajaAria",
            "Caja de las últimas semanas y proyección sin compraventa",
          )}
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
            ? t(
                "dashboard.sinCajaEn",
                "Si no compras ni vendes jugadores, te quedas sin caja en unas {{semanas}} semanas.",
                { semanas: data.structuralForecast.weeks[semanaCero] },
              )
            : t(
                "dashboard.cajaDentro",
                "Si no compras ni vendes jugadores, dentro de {{semanas}} semanas tendrías {{cifra}}.",
                {
                  semanas: proyeccion.length,
                  cifra: money(
                    proyeccion[proyeccion.length - 1] ?? 0,
                    data.currency,
                  ),
                },
              )}
        </div>
        <div className="text-right text-xs">
          <Link to="/economy" className="text-[var(--accent)] hover:underline">
            {t("dashboard.verEconomia", "Ver Economía →")}
          </Link>
        </div>
      </div>
    </Panel>
  );
}

//: Cuantas subidas caben en la portada sin convertirla en una lista larga.
const SUBIDAS_EN_PORTADA = 5;

/** Las subidas de habilidad de la última semana, de más reciente a más vieja. */
function SubidasRecientes() {
  const { t } = useTranslation();
  const cambios = useChangesHistory(null, 1);
  const titulo = t("dashboard.subidas", "Subidas recientes");
  if (cambios.isLoading) {
    return (
      <Panel title={titulo}>
        <div className="p-4">
          <Loading />
        </div>
      </Panel>
    );
  }
  const todas = (cambios.data?.skillChanges ?? [])
    .filter((c) => (c.delta ?? 0) > 0 && !c.isYouth)
    .sort((a, b) => b.capturedAt.localeCompare(a.capturedAt));
  const subidas = todas.slice(0, SUBIDAS_EN_PORTADA);
  // Un entrenamiento normal deja bastante mas de cinco subidas --diecisiete
  // en la semana del 15 de septiembre--, y el panel se quedaba con cinco sin
  // decirlo: parecia que HT Lens solo traia parte de los cambios. Aqui caben
  // cinco, pero el numero entero se dice y se enlaza (2026-09-19).
  const hayMas = todas.length > subidas.length;
  return (
    <Panel
      title={titulo}
      meta={
        <span className="flex items-baseline gap-2">
          {t("dashboard.ultimaSemana", "última semana")}
          {hayMas && (
            <Link
              to="/sync"
              className="text-[var(--accent)] hover:underline"
              title={t("dashboard.verTodasLasSubidas", "ver todas las subidas")}
            >
              {t("dashboard.subidasDeTotal", "{{vistas}} de {{total}}", {
                vistas: subidas.length,
                total: todas.length,
              })}
            </Link>
          )}
        </span>
      }
    >
      {subidas.length === 0 ? (
        <Empty>
          {t("dashboard.sinSubidas", "Ninguna subida esta semana.")}
        </Empty>
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
