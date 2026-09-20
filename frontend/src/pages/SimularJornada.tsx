import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Note, Panel } from "../components/Panels";
import { tx } from "../i18n/tx";
import type { League, LeagueStandingRow } from "../services/api";

/**
 * «Simular la siguiente fecha» (2026-09-20, idea del usuario).
 *
 * Escribes los resultados de la próxima jornada y la tabla se recalcula con
 * ellos. Sólo la SIGUIENTE: contestar «¿y si gano y el segundo pincha?» es una
 * pregunta de esta semana, y para el resto de la temporada ya está Proyección,
 * que lo hace con probabilidades en vez de con corazonadas.
 *
 * ES UNA MAQUETA, y por eso conviene decir lo que NO hace: nada se guarda. Los
 * marcadores viven en esta pestaña y se van al salir. Tampoco se manda nada al
 * servidor: la tabla se rehace aquí mismo, que es aritmética de sumar puntos y
 * ordenar, y así responde según se teclea.
 *
 * DOS LÍMITES QUE VIENEN DE LOS DATOS, no de pereza:
 *
 *  · El calendario nombra a los equipos, no los numera, así que cruzarlo con
 *    la clasificación se hace POR NOMBRE. Si algún nombre no casa --un equipo
 *    sustituido a mitad de temporada, por ejemplo-- ese partido se deja fuera
 *    en vez de inventarse una fila.
 *  · El desempate es el de Hattrick y sólo hasta donde llega la tabla: puntos,
 *    diferencia de goles y goles a favor. Hattrick tiene criterios más finos
 *    para el empate exacto de los tres, y aquí se resuelve dejando quieto el
 *    orden anterior, no adivinando.
 */

/** Un cruce de la jornada con lo que el usuario haya escrito. */
interface Cruce {
  indice: number;
  local: string;
  visitante: string;
}

/** Los marcadores tecleados, por índice de cruce. Cadena y no número: mientras
 *  se escribe, el campo puede estar vacío, y un `0` metido a la fuerza diría
 *  «empate a cero» cuando lo que pasa es que no has contestado todavía. */
type Marcadores = Record<number, { local: string; visitante: string }>;

function aGoles(v: string | undefined): number | null {
  if (v == null || v.trim() === "") return null;
  const n = Number(v);
  return Number.isInteger(n) && n >= 0 && n <= 99 ? n : null;
}

/** La tabla de Hattrick: puntos, luego diferencia, luego goles a favor. */
function ordenar(filas: LeagueStandingRow[]): LeagueStandingRow[] {
  return [...filas]
    .sort(
      (a, b) =>
        b.points - a.points ||
        b.goalDifference - a.goalDifference ||
        b.goalsFor - a.goalsFor ||
        // El cuarto criterio de Hattrick no está en la tabla. Antes que
        // inventarlo, se conserva el orden que ya tenían.
        a.position - b.position,
    )
    .map((f, i) => ({ ...f, position: i + 1 }));
}

/** La clasificación después de aplicar los marcadores escritos. */
function conLosResultados(
  standings: LeagueStandingRow[],
  cruces: Cruce[],
  marcadores: Marcadores,
): { filas: LeagueStandingRow[]; aplicados: number } {
  const porNombre = new Map(standings.map((f) => [f.name, { ...f }]));
  let aplicados = 0;

  for (const cruce of cruces) {
    const gl = aGoles(marcadores[cruce.indice]?.local);
    const gv = aGoles(marcadores[cruce.indice]?.visitante);
    if (gl == null || gv == null) continue;
    const local = porNombre.get(cruce.local);
    const visitante = porNombre.get(cruce.visitante);
    if (!local || !visitante) continue;

    aplicados += 1;
    for (const [equipo, propios, ajenos] of [
      [local, gl, gv],
      [visitante, gv, gl],
    ] as const) {
      equipo.played += 1;
      equipo.goalsFor += propios;
      equipo.goalsAgainst += ajenos;
      equipo.goalDifference = equipo.goalsFor - equipo.goalsAgainst;
      if (propios > ajenos) {
        equipo.won += 1;
        equipo.points += 3;
      } else if (propios === ajenos) {
        equipo.drawn += 1;
        equipo.points += 1;
      } else {
        equipo.lost += 1;
      }
    }
  }

  return { filas: ordenar([...porNombre.values()]), aplicados };
}

export function SimularJornada({ data }: { data: League }) {
  const [marcadores, setMarcadores] = useState<Marcadores>({});

  // La SIGUIENTE jornada es la más temprana que aún no se ha jugado. Se busca
  // así y no como «la jugada + 1» porque el calendario puede traer una
  // jornada aplazada, y entonces esos dos números no son el mismo.
  const jornada = useMemo(() => {
    const pendientes = data.fixtures.filter((f) => !f.played);
    if (pendientes.length === 0) return null;
    const numero = Math.min(...pendientes.map((f) => f.matchRound));
    const cruces: Cruce[] = data.fixtures
      .map((f, indice) => ({ f, indice }))
      .filter(({ f }) => !f.played && f.matchRound === numero)
      .map(({ f, indice }) => ({ indice, local: f.home, visitante: f.away }));
    return { numero, cruces };
  }, [data.fixtures]);

  const antes = useMemo(
    () => new Map(data.standings.map((f) => [f.htTeamId, f.position])),
    [data.standings],
  );

  const { filas, aplicados } = useMemo(
    () =>
      jornada
        ? conLosResultados(data.standings, jornada.cruces, marcadores)
        : { filas: data.standings, aplicados: 0 },
    [data.standings, jornada, marcadores],
  );

  if (!jornada) return null;

  const escribir = (indice: number, lado: "local" | "visitante", v: string) =>
    setMarcadores((m) => ({
      ...m,
      [indice]: {
        local: m[indice]?.local ?? "",
        visitante: m[indice]?.visitante ?? "",
        [lado]: v.replace(/[^0-9]/g, "").slice(0, 2),
      },
    }));

  return (
    <Panel
      title={tx("Simular la próxima jornada")}
      meta={tx("jornada {{v0}}", { v0: jornada.numero })}
    >
      <div className="space-y-4 p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <p className="max-w-prose text-sm text-[var(--muted)]">
            {tx(
              "Pon los resultados que quieras y la tabla se rehace debajo. No se guarda nada: es para mirar, no para apuntar.",
            )}
          </p>
          {aplicados > 0 && (
            <button
              type="button"
              onClick={() => setMarcadores({})}
              data-track="Liga: limpiar jornada simulada"
              className="shrink-0 rounded-md border border-[var(--border)] px-2 py-1 text-xs text-[var(--muted)] hover:text-[var(--text)]"
            >
              {tx("Borrar los resultados")}
            </button>
          )}
        </div>

        <ul className="space-y-2">
          {jornada.cruces.map((c) => {
            const m = marcadores[c.indice];
            return (
              <li
                key={c.indice}
                className="grid grid-cols-[1fr_auto_auto_auto_1fr] items-center gap-2 text-sm"
              >
                <span className="truncate text-right">{c.local}</span>
                <input
                  inputMode="numeric"
                  value={m?.local ?? ""}
                  onChange={(e) => escribir(c.indice, "local", e.target.value)}
                  aria-label={tx("Goles de {{v0}}", { v0: c.local })}
                  data-track="Liga: marcador simulado"
                  className="w-10 rounded border border-[var(--border)] bg-[var(--surface)] px-1 py-1 text-center tabular-nums outline-none focus:border-[var(--accent)]"
                />
                <span className="text-[var(--muted)]">-</span>
                <input
                  inputMode="numeric"
                  value={m?.visitante ?? ""}
                  onChange={(e) =>
                    escribir(c.indice, "visitante", e.target.value)
                  }
                  aria-label={tx("Goles de {{v0}}", { v0: c.visitante })}
                  data-track="Liga: marcador simulado"
                  className="w-10 rounded border border-[var(--border)] bg-[var(--surface)] px-1 py-1 text-center tabular-nums outline-none focus:border-[var(--accent)]"
                />
                <span className="truncate">{c.visitante}</span>
              </li>
            );
          })}
        </ul>

        <TablaSimulada filas={filas} antes={antes} aplicados={aplicados} />
      </div>
    </Panel>
  );
}

/** La tabla resultante, con el movimiento de cada equipo al lado.
 *
 *  Sin resultados escritos es la clasificación de hoy, y así se dice: una
 *  tabla vacía o escondida obligaría a adivinar si el panel funciona. */
function TablaSimulada({
  filas,
  antes,
  aplicados,
}: {
  filas: LeagueStandingRow[];
  antes: Map<number, number>;
  aplicados: number;
}) {
  return (
    <div className="space-y-2">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] text-xs text-[var(--muted)]">
              <th className="px-2 py-1.5 text-right">#</th>
              <th className="px-2 py-1.5 text-left">{tx("Equipo")}</th>
              <th className="px-2 py-1.5 text-right">PJ</th>
              <th className="px-2 py-1.5 text-right">DG</th>
              <th className="px-2 py-1.5 text-right">{tx("Pts")}</th>
            </tr>
          </thead>
          <tbody>
            {filas.map((f) => {
              const movido = (antes.get(f.htTeamId) ?? f.position) - f.position;
              return (
                <tr
                  key={f.htTeamId}
                  className={`border-b border-[var(--border)]/40 ${
                    f.isOwnTeam ? "bg-[var(--surface-2)]" : ""
                  }`}
                >
                  <td className="px-2 py-1.5 text-right tabular-nums">
                    {f.position}
                    {movido !== 0 && (
                      <span
                        className={`ml-1 text-xs ${
                          movido > 0
                            ? "text-[var(--positive)]"
                            : "text-[var(--danger)]"
                        }`}
                      >
                        {movido > 0 ? "▲" : "▼"}
                        {Math.abs(movido)}
                      </span>
                    )}
                  </td>
                  <td className="px-2 py-1.5">
                    {f.isOwnTeam ? (
                      <span className="font-medium">{f.name}</span>
                    ) : (
                      <Link
                        to={`/rivals/${f.htTeamId}`}
                        className="hover:text-[var(--accent)] hover:underline"
                      >
                        {f.name}
                      </Link>
                    )}
                  </td>
                  <td className="px-2 py-1.5 text-right tabular-nums">
                    {f.played}
                  </td>
                  <td className="px-2 py-1.5 text-right tabular-nums">
                    {f.goalDifference > 0 ? "+" : ""}
                    {f.goalDifference}
                  </td>
                  <td className="px-2 py-1.5 text-right font-medium tabular-nums">
                    {f.points}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <Note>
        {aplicados === 0
          ? tx("Todavía es la clasificación de hoy: no has puesto ningún resultado.")
          : tx("Con {{v0}} resultado(s) puesto(s) de esta jornada.", {
              v0: aplicados,
            })}
      </Note>
    </div>
  );
}
