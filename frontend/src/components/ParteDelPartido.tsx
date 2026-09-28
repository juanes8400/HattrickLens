import type { LastMatchReport } from "../services/api";
import { date, decimal, percent } from "../hooks/useFormat";
import { tx } from "../i18n/tx";

/** El parte del último partido, al lado de lo que dijimos antes de jugarlo.
 *
 *  2026-09-27, pedido del usuario: encabeza Cambios. La gracia no es repetir
 *  el resultado, que ya está en Partidos, sino ponerlo contra la terna que
 *  dábamos ANTES, que es lo único que permite decir si acertamos.
 *
 *  TODA LA FRASE SE ESCRIBE AQUÍ. El servidor manda números y claves; si
 *  mandara la frase hecha, el traductor recibiría una cadena distinta por
 *  cada resultado posible y no podría casar ninguna. Por eso cada trozo de
 *  texto de este fichero pasa por `tx()` y los números entran aparte.
 */

type Resultado = "home" | "draw" | "away";

const resultadoDe = (golesLocal: number, golesVisitante: number): Resultado =>
  golesLocal > golesVisitante
    ? "home"
    : golesLocal < golesVisitante
      ? "away"
      : "draw";

/** Los tres tramos de la barra, SIEMPRE en el mismo orden que el marcador:
 *  local, empate, visitante. No se reordenan por tamaño ni se pone primero al
 *  equipo propio, porque la barra tiene que leerse contra el resultado que
 *  está justo encima. */
const TRAMOS: readonly Resultado[] = ["home", "draw", "away"];

function etiquetaDe(tramo: Resultado, parte: LastMatchReport): string {
  if (tramo === "draw") return tx("Empate");
  return tramo === "home" ? parte.home : parte.away;
}

export function ParteDelPartido({ parte }: { parte: LastMatchReport }) {
  const { homeGoals, awayGoals, prediction: dicho } = parte;
  const paso = resultadoDe(homeGoals, awayGoals);
  const propio: Resultado = parte.isHome ? "home" : "away";
  const empate = paso === "draw";
  const gane = paso === propio;

  const probabilidades: Record<Resultado, number> | null = dicho
    ? { home: dicho.homeWin, draw: dicho.draw, away: dicho.awayWin }
    : null;
  // El favorito era el tramo más gordo. Se deriva aquí a propósito: el
  // servidor manda números, no veredictos.
  const favorito = probabilidades
    ? TRAMOS.reduce((a, b) => (probabilidades[b] > probabilidades[a] ? b : a))
    : null;

  const tono = empate
    ? "var(--warning)"
    : gane
      ? "var(--positive)"
      : "var(--danger)";

  return (
    <section
      aria-label={tx("Parte del último partido")}
      className="overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--surface)]"
    >
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 border-b border-[var(--border)] px-4 py-2 text-xs text-[var(--muted)]">
        <span className="font-medium text-[var(--text)]">
          {tx("Último partido")}
        </span>
        <span aria-hidden="true">·</span>
        <span>{parte.competition}</span>
        {parte.round != null && (
          <>
            <span aria-hidden="true">·</span>
            <span>
              {tx("Jornada")} {parte.round}
            </span>
          </>
        )}
        {parte.playedAt && (
          <>
            <span aria-hidden="true">·</span>
            <span>{date(parte.playedAt)}</span>
          </>
        )}
      </div>

      {/* El resultado, en grande. Es lo que el usuario busca de un vistazo y
          va antes que cualquier análisis. El color no viaja solo: el nombre
          del equipo propio va en negrita y la frase de abajo lo dice. */}
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 px-4 py-4">
        <span
          className={`text-right text-sm leading-tight ${
            parte.isHome
              ? "font-semibold text-[var(--text)]"
              : "text-[var(--muted)]"
          }`}
        >
          {parte.home}
        </span>
        <span
          className="text-4xl font-semibold tabular-nums"
          style={{ color: tono }}
        >
          {homeGoals}
          <span className="px-1 text-[var(--muted)]">-</span>
          {awayGoals}
        </span>
        <span
          className={`text-sm leading-tight ${
            parte.isHome
              ? "text-[var(--muted)]"
              : "font-semibold text-[var(--text)]"
          }`}
        >
          {parte.away}
        </span>
      </div>

      {dicho == null || probabilidades == null || favorito == null ? (
        /* EL OTRO ESTADO, y no es un error: de los partidos anteriores al
           2026-09-26 no guardamos nada, y no se rellena recalculándolo hacia
           atrás, porque eso sería lo que diríamos hoy, no lo que dijimos. */
        <p className="border-t border-[var(--border)] px-4 py-3 text-sm text-[var(--muted)]">
          {tx(
            "De este partido no guardamos ningún pronóstico, así que no hay nada que contrastar. Desde ahora se guarda lo que decimos de cada partido antes de que se juegue.",
          )}
        </p>
      ) : (
        <div className="border-t border-[var(--border)] px-4 py-3">
          <p className="mb-2 text-xs font-medium text-[var(--muted)]">
            {tx("Lo que dijimos antes de jugarlo")}
          </p>

          {/* LA BARRA. Cada tramo mide su probabilidad y el que pasó de verdad
              lleva la marca. Ni el color ni el triángulo van solos: cada tramo
              rotula su porcentaje y el que pasó lo dice en palabras debajo.

              EL TRAMO MARCADO NO SE RELLENA DEL COLOR, se subraya con él.
              Relleno, su cifra iba en blanco sobre `--positive` o sobre
              `--warning`, y eso da 3,5:1 y 3,3:1 en claro y 2,4:1 en oscuro:
              por debajo del 4,5:1 que pide un texto de 11px. Subrayado, la
              cifra se queda sobre el mismo fondo que las otras dos y se lee
              en los dos temas. */}
          <div className="flex h-7 w-full overflow-hidden rounded-md">
            {TRAMOS.map((tramo) => {
              const p = probabilidades[tramo];
              const esLoQuePaso = tramo === paso;
              return (
                <div
                  key={tramo}
                  className={`flex items-center justify-center overflow-hidden text-[11px] tabular-nums ${
                    esLoQuePaso ? "font-semibold" : "font-medium"
                  }`}
                  style={{
                    flexGrow: Math.max(p, 0.001),
                    flexBasis: 0,
                    background: "var(--surface-2)",
                    color: esLoQuePaso ? "var(--text)" : "var(--muted)",
                    // 2px del color del fondo entre tramos: sin esto dos
                    // tramos contiguos se leen como uno solo. Y, en el que
                    // pasó, 3px del color del resultado abajo.
                    boxShadow: esLoQuePaso
                      ? `inset -2px 0 0 0 var(--surface), inset 0 -3px 0 0 ${tono}`
                      : "inset -2px 0 0 0 var(--surface)",
                  }}
                  title={`${etiquetaDe(tramo, parte)} ${percent(p * 100, 0)}`}
                >
                  {p >= 0.08 ? percent(p * 100, 0) : ""}
                </div>
              );
            })}
          </div>
          <div className="mt-1 flex w-full">
            {TRAMOS.map((tramo) => (
              <div
                key={tramo}
                className="min-w-0 text-center text-[11px] leading-tight text-[var(--muted)]"
                style={{
                  flexGrow: Math.max(probabilidades[tramo], 0.001),
                  flexBasis: 0,
                }}
              >
                {tramo === paso && (
                  <span style={{ color: tono }}>
                    <span aria-hidden="true">▲ </span>
                    {tx("lo que pasó")}
                  </span>
                )}
              </div>
            ))}
          </div>

          {/* LA FRASE, armada aquí con trozos traducibles y números aparte.
              Cada `tx()` es una frase suelta y completa, y los nombres y los
              porcentajes entran fuera: así ninguna traducción depende de una
              concordancia («al empate» / «a la victoria de») que en otro
              idioma no existe. */}
          <p className="mt-3 text-sm text-[var(--text)]">
            {favorito === paso
              ? tx("Era lo más probable.")
              : tx("No era lo más probable.")}{" "}
            <span className="text-[var(--muted)]">
              {tx("Lo que pasó")}: {etiquetaDe(paso, parte)},{" "}
              {percent(probabilidades[paso] * 100, 0)}.
              {favorito !== paso && (
                <>
                  {" "}
                  {tx("Lo más probable era")}: {etiquetaDe(favorito, parte)},{" "}
                  {percent(probabilidades[favorito] * 100, 0)}.
                </>
              )}
            </span>
          </p>
          <p className="mt-1 text-xs text-[var(--muted)]">
            {dicho.mostLikelyScore === `${homeGoals}-${awayGoals}`
              ? tx("El marcador cantado fue justo éste.")
              : `${tx("Marcador cantado")}: ${dicho.mostLikelyScore}.`}{" "}
            {tx("Goles esperados")} {decimal(dicho.expectedHomeGoals, 2)}
            {" - "}
            {decimal(dicho.expectedAwayGoals, 2)}.{" "}
            {dicho.source === "zonas"
              ? tx("Salió de las alineaciones y tácticas de los dos lados.")
              : tx(
                  "Salió sólo de los goles de la temporada: no había alineaciones con las que contar, así que ignora tácticas.",
                )}
          </p>
        </div>
      )}
    </section>
  );
}
