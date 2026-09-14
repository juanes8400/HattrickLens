import { Fragment, useState } from "react";
import { Link } from "react-router-dom";
import { Tabs } from "../components/Tabs";
import {
  ErrorState,
  Kpi,
  Loading,
  Note,
  Panel,
  SinDatos,
} from "../components/Panels";
import { useSkills } from "../hooks/useTeam";
import { skillLevelLabel } from "../utils/skillLevels";
import { Specialty, specialtyIcon } from "../components/Specialty";
import { SplitSelector } from "../components/SplitSelector";
import { FORMATIONS } from "../services/api";
import type { SkillsCandidate, SkillsTone } from "../services/api";

/**
 * Habilidades (2026-09-14, pedido del usuario): la plantilla entera, habilidad
 * por habilidad. Responde qué tiene, dónde le falta y qué subida rinde más.
 *
 * El cuello de botella es el sector que peor queda frente a la serie, con los
 * ratings reales de los últimos partidos oficiales; lo que se estima con la
 * tabla de contribución por puesto es sólo cuánto aporta un nivel más de cada
 * jugador del once titular.
 */

type Vista = "once" | "todos" | "sanos";

/** El rótulo de cada grupo de filas del mapa, por la sigla del puesto. */
const GRUPO: Record<string, string> = {
  POR: "Porteros",
  DC: "Defensas Centrales",
  LAT: "Defensas Laterales",
  INT: "Mediocentros",
  EXT: "Extremos",
  DEL: "Delanteros",
};

const COLOR: Record<SkillsTone, string> = {
  danger: "var(--danger)",
  warning: "var(--warning)",
  ok: "var(--positive)",
};

/** Las claves de `skills` llegan en camelCase: `set_pieces` es `setPieces`. */
const clave = (k: string) =>
  k.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());

function Pastilla({
  tone,
  children,
}: {
  tone: SkillsTone;
  children: React.ReactNode;
}) {
  return (
    <span
      className="whitespace-nowrap rounded-md px-2 py-0.5 text-xs"
      style={{
        background: `color-mix(in srgb, ${COLOR[tone]} 14%, transparent)`,
        color: COLOR[tone],
      }}
    >
      {children}
    </span>
  );
}

/** «+82%», «−12%», «0%»: la ventaja sobre el mejor rival del sector. */
function ventaja(pct: number) {
  const n = Math.round(pct);
  return n > 0 ? `+${n}%` : n < 0 ? `−${Math.abs(n)}%` : "0%";
}

/** 16,8 · 211: con coma decimal y sin ceros sobrantes. */
function decimal(n: number | undefined) {
  // Tolera un dato guardado en el navegador con la forma de antes: la página
  // no puede romperse porque llegue un campo que todavía no existía.
  return (n ?? 0).toLocaleString("es", { maximumFractionDigits: 1 });
}

/** «Bordalás» y debajo «rendimiento 17,9 · Defensa 18 (mágico)». */
function Nombrado({
  candidato,
  habilidad,
}: {
  candidato: SkillsCandidate | null;
  habilidad: string;
}) {
  if (!candidato) return <span className="text-[var(--muted)]">nadie</span>;
  return (
    <span>
      <Link to={`/players/${candidato.htPlayerId}`} className="hover:underline">
        {candidato.name}
      </Link>
      <span className="block text-xs text-[var(--muted)]">
        rendimiento {decimal(candidato.rating)} · {habilidad}{" "}
        {candidato.skillLevel} ({skillLevelLabel(candidato.skillLevel)})
      </span>
    </span>
  );
}

/** El fondo de una celda: más nivel, más color. 18 (mágico) ya es el tope. */
function intensidad(nivel: number) {
  return Math.round(Math.min(95, Math.max(6, (nivel / 18) * 100)));
}

export function SkillsPage() {
  const [vista, setVista] = useState<Vista>("once");
  // La formación de Profundidad: vacía = la del último partido oficial.
  const [formacion, setFormacion] = useState("");
  const [centrales, setCentrales] = useState<number | undefined>(undefined);
  const [medios, setMedios] = useState<number | undefined>(undefined);
  const { data, isLoading, isError, error } = useSkills(
    formacion || undefined,
    centrales,
    medios,
  );

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return <SinDatos />;

  const hayOnce = data.players.some((p) => p.inLineup);
  const vistaReal: Vista = vista === "once" && !hayOnce ? "todos" : vista;
  const jugadores = data.players.filter((p) =>
    vistaReal === "once"
      ? p.inLineup
      : vistaReal === "sanos"
        ? !p.injured
        : true,
  );

  // Sin suplente cuenta como la peor caída posible.
  // SÓLO FILAS CON LA FORMA ACTUAL. El navegador guarda las respuestas entre
  // visitas, y una guardada con la forma de antes (por habilidad, sin
  // `alsoCovers`) dejaba la página en blanco al leer un campo que no existía
  // (2026-09-14, visto por el usuario). Mejor una tabla vacía un momento que
  // una pantalla rota: la respuesta nueva llega enseguida.
  const profundidadVigente = (data.depth ?? []).filter(
    (d) => Array.isArray(d.alsoCovers) && typeof d.starters === "number",
  );
  const esLaUltima =
    data.depthFormation === data.formation &&
    data.depthCentralDefenders === data.lastCentralDefenders &&
    data.depthInnerMidfielders === data.lastInnerMidfielders;
  const caida = (d: { dropPct: number | null }) => d.dropPct ?? 100;
  const porCaida = [...profundidadVigente].sort((a, b) => caida(a) - caida(b));
  const mejorCubierto = porCaida[0];
  const hueco = porCaida.length > 1 ? porCaida[porCaida.length - 1] : undefined;
  const cuello = data.sectors.find((s) => s.label === data.bottleneck);
  // Qué puestos de Profundidad son el sector cuello de botella (2026-09-14,
  // pedido del usuario): se marcan con 🍾 para leer las dos tablas juntas.
  const PUESTOS_DEL_SECTOR: Record<string, string[]> = {
    // El portero también sostiene la defensa (2026-09-14, pedido del usuario).
    defensa: ["keeper", "central_defender", "wingback"],
    mediocampo: ["inner_midfield"],
    // Los extremos también sostienen el ataque (2026-09-14, pedido del usuario).
    ataque: ["winger", "forward"],
  };
  const puestosDelCuello = new Set(
    cuello ? (PUESTOS_DEL_SECTOR[cuello.key] ?? []) : [],
  );
  const especialistas = data.players.filter((p) => p.specialty);
  const porEspecialidad = Object.entries(
    especialistas.reduce<Record<string, number>>((acc, p) => {
      acc[p.specialty] = (acc[p.specialty] ?? 0) + 1;
      return acc;
    }, {}),
  )
    .sort((a, b) => b[1] - a[1])
    .map(([e, n]) => `${specialtyIcon(e) ?? ""} ${e} ${n}`.trim())
    .join(" · ");

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Habilidades (Profundidad)</h1>
        <p className="text-sm text-[var(--muted)]">
          Qué tiene la plantilla, dónde le falta y qué subida rinde más
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 [&>*]:min-w-0">
        <Kpi
          label="Mejor cubierto"
          value={mejorCubierto?.label ?? "-"}
          hint={
            mejorCubierto?.substitute && mejorCubierto.dropPct != null
              ? `entra ${mejorCubierto.substitute.name} y pierdes un ${Math.round(mejorCubierto.dropPct)} %`
              : undefined
          }
          ayuda="El puesto de la formación elegida en Profundidad donde menos se nota que falte el mejor titular: el suplente del banquillo rinde casi igual."
        />
        <Kpi
          label="Hueco más serio"
          value={hueco?.label ?? "-"}
          hint={
            hueco
              ? hueco.best && hueco.substitute && hueco.dropPct != null
                ? `si falta ${hueco.best.name}, entra ${hueco.substitute.name} y pierdes un ${Math.round(hueco.dropPct)} %`
                : "no hay nadie en el banquillo"
              : undefined
          }
          tone={hueco?.tone === "danger" ? "danger" : undefined}
          ayuda="El puesto de la formación elegida en Profundidad donde más rendimiento pierdes si falta el mejor titular y entra el mejor del banquillo."
        />
        <Kpi
          label="Cuello de botella"
          value={data.bottleneck ?? "-"}
          hint={
            cuello
              ? `${ventaja(cuello.marginPct)} frente a ${cuello.bestRival}`
              : "hace falta un partido oficial con ratings"
          }
          tone={cuello?.tone === "danger" ? "danger" : undefined}
          ayuda="El sector con menos ventaja sobre el mejor rival de tu serie en ese sector, con la media de los últimos 5 partidos oficiales de cada equipo. Si vas por detrás, es donde más pierdes."
        />
        <Kpi
          label="Especialistas"
          value={`${especialistas.length} de ${data.players.length}`}
          hint={porEspecialidad || "ninguno"}
        />
      </div>

      <Panel
        title="Mapa de la plantilla"
        meta="pasa el cursor por un número para ver su nivel"
      >
        <div className="px-4 pt-3">
          <Tabs
            modo="filtro"
            label="Qué jugadores se miran"
            tabs={[
              ...(hayOnce ? [{ key: "once", label: "Último once" }] : []),
              { key: "todos", label: "Toda la plantilla" },
              { key: "sanos", label: "Sin lesionados" },
            ]}
            active={vistaReal}
            onChange={(v) => setVista(v as Vista)}
          />
        </div>
        {/* LEGIBLE ANTES QUE ANCHA (2026-09-14, pedido del usuario): a todo
            el ancho, los nombres quedaban lejísimos de sus números y no se
            sabía qué fila era de quién. La tabla ocupa lo que necesita, las
            filas van agrupadas por puesto y la fila se resalta al pasar. */}
        <div className="overflow-x-auto px-4 pb-2 pt-3">
          <table className="w-[57.5rem] table-fixed border-separate border-spacing-x-0.5 border-spacing-y-0.5 text-xs">
            <thead>
              <tr className="text-[var(--muted)]">
                <th className="sticky left-0 z-10 w-[12rem] bg-[var(--surface)] pr-3 text-right font-normal">
                  Jugador
                </th>
                {data.skills.map((s) => (
                  <th
                    key={s.key}
                    className="w-[5.5rem] whitespace-nowrap px-1 pb-1 font-normal"
                  >
                    {s.label}
                  </th>
                ))}
                <th className="w-[7rem] pl-3 text-left font-normal">
                  Especialidad
                </th>
              </tr>
            </thead>
            <tbody>
              {jugadores.map((p, i) => {
                const grupo = GRUPO[p.position ?? ""] ?? "Sin puesto reciente";
                const empiezaGrupo =
                  i === 0 ||
                  (GRUPO[jugadores[i - 1]?.position ?? ""] ??
                    "Sin puesto reciente") !== grupo;
                return (
                  <Fragment key={p.htPlayerId}>
                    {empiezaGrupo && (
                      <tr>
                        <td
                          colSpan={data.skills.length + 2}
                          className="sticky left-0 pb-1 pt-3 text-[11px] font-medium text-[var(--muted)]"
                        >
                          {grupo}
                        </td>
                      </tr>
                    )}
                    <tr className="group">
                      <td className="sticky left-0 z-10 truncate rounded bg-[var(--surface)] py-1 pl-2 pr-3 text-right group-hover:bg-[var(--accent-soft)]">
                        <Link
                          to={`/players/${p.htPlayerId}`}
                          className="hover:underline"
                        >
                          {p.name}
                        </Link>
                        {p.injured && (
                          <span className="ml-1.5 text-[var(--danger)]">
                            lesionado
                          </span>
                        )}
                      </td>
                      {data.skills.map((s) => {
                        const nivel = p.skills[clave(s.key)] ?? 0;
                        const pct = intensidad(nivel);
                        const delPuesto = p.positionSkill === s.key;
                        return (
                          <td
                            key={s.key}
                            title={`${p.name} · ${s.label}: ${skillLevelLabel(nivel)} (${nivel})`}
                            className="rounded py-1 text-center tabular-nums"
                            style={{
                              background: `color-mix(in srgb, var(--accent) ${pct}%, transparent)`,
                              color: pct > 55 ? "#fff" : "var(--text)",
                              boxShadow: delPuesto
                                ? "inset 0 0 0 1.5px var(--text)"
                                : undefined,
                            }}
                          >
                            {nivel}
                          </td>
                        );
                      })}
                      <td className="whitespace-nowrap rounded pl-3 text-[var(--muted)] group-hover:bg-[var(--accent-soft)]">
                        {p.specialty ? (
                          <Specialty specialty={p.specialty} />
                        ) : (
                          "-"
                        )}
                      </td>
                    </tr>
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 pb-4 text-xs text-[var(--muted)]">
          {[4, 8, 12, 15, 18].map((n) => (
            <span key={n} className="flex items-center gap-1.5">
              <span
                className="inline-block h-3 w-5 rounded-sm"
                style={{
                  background: `color-mix(in srgb, var(--accent) ${intensidad(n)}%, transparent)`,
                }}
              />
              {n} {skillLevelLabel(n)}
            </span>
          ))}
          <span className="flex items-center gap-1.5">
            <span
              className="inline-block h-3 w-5 rounded-sm"
              style={{ boxShadow: "inset 0 0 0 1.5px var(--text)" }}
            />
            habilidad de su puesto
          </span>
        </div>
      </Panel>

      {/* PROFUNDIDAD POR PUESTO (2026-09-14, pedido del usuario): no se
          compara al mejor con el segundo mejor --que suele ser titular
          también--, sino con el mejor del BANQUILLO en ese puesto, que es
          quien entraría de verdad. Ordenados por rendimiento en el puesto. */}
      <Panel title="Profundidad" meta="sin contar lesionados">
        {profundidadVigente.length === 0 ? (
          <Note>
            Aparece cuando haya un partido oficial con su alineación: de ahí
            salen los puestos y cuántos jugaron de cada uno.
          </Note>
        ) : (
          <>
            {/* LA FORMACIÓN SE ESCOGE (2026-09-14, pedido del usuario), con
                los mismos mandos que Alineación. Arranca en la del último
                partido oficial y siempre dice cuál fue. */}
            <div className="flex flex-wrap items-center gap-3 border-b border-[var(--border)] px-4 py-3">
              {/* Los mismos mandos que el mejor once del Dashboard: rótulo
                  «Formación» con su lista y, al lado, cuántos por dentro. */}
              <label className="flex items-center gap-2 text-xs text-[var(--muted)]">
                Formación
                <select
                  aria-label="Formación para calcular la profundidad"
                  value={data.depthFormation ?? ""}
                  onChange={(e) => {
                    const elegida = e.target.value;
                    setFormacion(elegida === data.formation ? "" : elegida);
                    setCentrales(undefined);
                    setMedios(undefined);
                  }}
                  className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-sm text-[var(--text)]"
                >
                  {FORMATIONS.map((f) => (
                    <option key={f} value={f}>
                      {f === data.formation ? `${f} · la última oficial` : f}
                    </option>
                  ))}
                </select>
              </label>
              <SplitSelector
                label="Defensas Centrales"
                value={data.depthCentralDefenders ?? undefined}
                options={data.centralDefenderOptions ?? []}
                onChange={(v) => {
                  setFormacion(data.depthFormation ?? "");
                  setCentrales(v);
                  setMedios(data.depthInnerMidfielders ?? undefined);
                }}
              />
              <SplitSelector
                label="Mediocentros"
                value={data.depthInnerMidfielders ?? undefined}
                options={data.innerMidfielderOptions ?? []}
                onChange={(v) => {
                  setFormacion(data.depthFormation ?? "");
                  setCentrales(data.depthCentralDefenders ?? undefined);
                  setMedios(v);
                }}
              />
              {!esLaUltima && (
                <button
                  type="button"
                  onClick={() => {
                    setFormacion("");
                    setCentrales(undefined);
                    setMedios(undefined);
                  }}
                  className="rounded-md border border-[var(--border)] px-3 py-1.5 text-xs hover:border-[var(--accent)]"
                >
                  Volver a la última oficial
                </button>
              )}
            </div>
            {data.formation && (
              <p className="px-4 pt-2 text-sm">
                <span
                  className={
                    esLaUltima ? "text-[var(--accent)]" : "text-[var(--muted)]"
                  }
                >
                  {esLaUltima
                    ? "Estás viendo tu última formación oficial"
                    : "Tu última formación oficial"}
                  {data.lastMatchDate ? ` (${data.lastMatchDate})` : ""}:{" "}
                </span>
                <b>{data.formation}</b> con {data.lastCentralDefenders}{" "}
                {data.lastCentralDefenders === 1
                  ? "Defensa Central"
                  : "Defensas Centrales"}{" "}
                y {data.lastInnerMidfielders}{" "}
                {data.lastInnerMidfielders === 1
                  ? "Mediocentro"
                  : "Mediocentros"}
              </p>
            )}
            <p className="prosa px-4 pt-2 text-sm text-[var(--muted)]">
              Si falta el mejor titular de un puesto (por lesión, venta o
              sanción), quién del banquillo entraría y cuánto rendimiento
              perderías. El rendimiento es el mismo de la pantalla Posiciones:
              tiene en cuenta todas las habilidades del puesto, la forma y la
              experiencia.
            </p>
            <div className="overflow-x-auto px-4 pb-4 pt-2">
              <table className="w-full min-w-[40rem] text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)] text-left text-xs text-[var(--muted)]">
                    <th className="py-2 pr-3 font-normal">Puesto</th>
                    <th className="py-2 pr-3 font-normal">Mejor titular</th>
                    <th className="py-2 pr-3 font-normal">
                      Si falta, entra del banquillo
                    </th>
                    <th className="py-2 pr-3 text-right font-normal">
                      Pierdes
                    </th>
                    <th className="py-2 font-normal">Estado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {profundidadVigente.map((d) => (
                    <tr key={d.key} className="align-top">
                      <td className="py-2 pr-3">
                        {d.label}
                        {puestosDelCuello.has(d.key) && cuello && (
                          <span
                            className="ml-1.5"
                            title={`Cuello de botella: el ${cuello.label.toLowerCase()} es el sector donde menos ventaja le sacas a tu serie`}
                            aria-label="Cuello de botella"
                          >
                            🍾
                          </span>
                        )}
                        <span className="block text-xs text-[var(--muted)]">
                          {d.starters}{" "}
                          {d.starters === 1 ? "titular" : "titulares"}
                        </span>
                      </td>
                      <td className="py-2 pr-3">
                        <Nombrado candidato={d.best} habilidad={d.skillLabel} />
                      </td>
                      <td className="py-2 pr-3">
                        <Nombrado
                          candidato={d.substitute}
                          habilidad={d.skillLabel}
                        />
                        {d.alsoCovers.length > 0 && (
                          <span
                            className="block text-xs text-[var(--warning)]"
                            title={`También es el primer recambio de: ${d.alsoCovers.join(", ")}`}
                          >
                            {d.alsoCovers.length === 1
                              ? `también es el recambio de ${d.alsoCovers[0]}`
                              : `y de ${d.alsoCovers.length} puestos más`}
                          </span>
                        )}
                        {d.alsoCovers.length > 0 && d.nextSubstitute && (
                          <span className="block text-xs text-[var(--muted)]">
                            si ya está ocupado, entra {d.nextSubstitute.name}{" "}
                            (rendimiento {decimal(d.nextSubstitute.rating)})
                          </span>
                        )}
                      </td>
                      <td className="py-2 pr-3 text-right tabular-nums">
                        {d.dropPct == null
                          ? "-"
                          : d.dropPct < 0.5
                            ? "nada"
                            : `${Math.round(d.dropPct)} %`}
                      </td>
                      <td className="py-2">
                        <span
                          title={
                            d.tone === "danger"
                              ? "Pierdes un 30 % o más, o no hay nadie en el banquillo."
                              : d.tone === "warning"
                                ? "Pierdes entre un 15 y un 30 %."
                                : "Pierdes menos de un 15 %."
                          }
                        >
                          <Pastilla tone={d.tone}>
                            {d.tone === "danger"
                              ? "🚨 Hueco"
                              : d.tone === "warning"
                                ? "⚠️ Cuidado"
                                : "✅ Cubierto"}
                          </Pastilla>
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {cuello && puestosDelCuello.size > 0 && (
                <p className="pt-2 text-xs text-[var(--muted)]">
                  🍾 cuello de botella: el {cuello.label.toLowerCase()}, donde
                  menos ventaja le sacas a tu serie
                </p>
              )}
            </div>
          </>
        )}
      </Panel>

      <Panel title="Cuello de botella">
        {data.sectors.length === 0 ? (
          <Note>
            Aparece cuando haya partidos oficiales con sus ratings y la
            alineación del último.
          </Note>
        ) : (
          <div className="space-y-5 px-4 py-4">
            <p className="prosa text-sm text-[var(--muted)]">
              Cada sector de tu equipo frente al mejor rival de tu serie en ese
              mismo sector, con la media de los últimos 5 partidos oficiales. El
              cuello de botella es donde menos ventaja le sacas.
            </p>

            <div className="grid gap-4 md:grid-cols-3">
              {data.sectors.map((s) => {
                const tope = Math.max(s.rating, s.bestRivalValue ?? 0) || 1;
                return (
                  <div
                    key={s.key}
                    className="rounded-lg border border-[var(--border)] p-3"
                    style={
                      s.label === data.bottleneck
                        ? { borderColor: COLOR[s.tone] }
                        : undefined
                    }
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium">{s.label}</span>
                      <Pastilla tone={s.tone}>{s.verdict}</Pastilla>
                    </div>
                    <div className="mt-3 space-y-1.5 text-xs">
                      {[
                        { quien: "Tú", valor: s.rating, color: COLOR[s.tone] },
                        {
                          quien: s.bestRival,
                          valor: s.bestRivalValue ?? 0,
                          color: "var(--muted)",
                        },
                      ].map((b) => (
                        <div
                          key={b.quien}
                          className="grid grid-cols-[minmax(0,6rem)_minmax(0,1fr)_2.5rem] items-center gap-2"
                        >
                          <span className="truncate" title={b.quien}>
                            {b.quien}
                          </span>
                          <span className="h-2 rounded bg-[var(--border)]">
                            <span
                              className="block h-2 rounded"
                              style={{
                                width: `${(b.valor / tope) * 100}%`,
                                background: b.color,
                              }}
                            />
                          </span>
                          <span className="text-right tabular-nums">
                            {decimal(b.valor)}
                          </span>
                        </div>
                      ))}
                    </div>
                    <div className="mt-2 text-sm">
                      {s.marginPct < 0
                        ? `Vas un ${Math.round(-s.marginPct)} % por detrás`
                        : s.marginPct < 0.5
                          ? "Empatas con el mejor rival"
                          : `Le sacas un ${Math.round(s.marginPct)} % de ventaja`}
                    </div>
                    {s.who && (
                      <div className="mt-1 text-xs text-[var(--muted)]">
                        Lo sostienen: {s.who}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {data.upgrades.length > 0 && data.bottleneck && (
              <div>
                <div className="text-sm font-medium">
                  Qué subir primero para el {data.bottleneck.toLowerCase()}
                </div>
                <p className="prosa mt-0.5 text-xs text-[var(--muted)]">
                  Con tu once titular del {data.lastMatchDate}
                  {data.formation ? ` (${data.formation})` : ""}: un nivel más
                  de estas habilidades es lo que más empuja ese sector.
                </p>
                <div className="mt-2 divide-y divide-[var(--border)]">
                  {data.upgrades.map((u, i) => (
                    <div
                      key={`${u.htPlayerId}-${u.skill}`}
                      className="grid grid-cols-[1.25rem_minmax(0,1fr)_auto] items-center gap-2 py-2 text-sm"
                    >
                      <span className="text-[var(--muted)]">{i + 1}</span>
                      <span className="min-w-0">
                        {u.skillLabel} de {u.player}: {u.fromLevel} →{" "}
                        {u.fromLevel + 1}
                        <span className="block text-xs text-[var(--muted)]">
                          el {data.bottleneck?.toLowerCase()} del once sube un{" "}
                          {decimal(u.gainPct)} %
                        </span>
                      </span>
                      <Pastilla tone={u.impact === "Alto" ? "ok" : "warning"}>
                        {u.impact === "Alto" ? "Mayor efecto" : "Efecto medio"}
                      </Pastilla>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </Panel>
    </div>
  );
}
