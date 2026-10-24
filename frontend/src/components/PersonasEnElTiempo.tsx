/** Cuánta gente distinta hay, en el tiempo.
 *
 *  2026-10-23, pedido del usuario: «número de usuarios en el tiempo (personas
 *  activas vs tiempo)». Todo lo demás de esta pantalla contesta cuánto se usa
 *  y quién; nada contestaba si eso CRECE. Con un solo número por plazo, doce
 *  personas estables y doce que llegaron la semana pasada se leen igual.
 *
 *  EL GRANO LO CALCULA EL SERVIDOR, y no es un detalle de reparto: la gente no
 *  se suma. Quien entra lunes y martes son dos renglones diarios y UNA persona
 *  en la semana, así que agrupar aquí sumando los días daría siempre más gente
 *  de la que hay --y el error crece justo con quien usa la aplicación todos los
 *  días, que es a quien más interesa ver--. Los tres granos vienen ya hechos
 *  en la misma respuesta, así que el selector no vuelve al servidor.
 *
 *  BARRAS Y NO LÍNEA. Una línea entre dos puntos afirma que hubo algo entre
 *  ellos, y aquí lo que hay entre dos días es otro día medido, no una
 *  transición. Las barras dicen «esto es lo que hubo en cada tramo» y el cero
 *  se ve como lo que es: un tramo sin nadie, no un corte en el dibujo.
 */
import { useMemo } from "react";

import { Panel } from "./Panels";
import { usePersistido } from "../hooks/usePersistido";
import type { Grano, TramoDeUso } from "../services/api";
import { tx } from "../i18n/tx";

const GRANOS = [
  { key: "day", label: tx("Por día") },
  { key: "week", label: tx("Por semana") },
  { key: "month", label: tx("Por mes") },
] as const;

/** La etiqueta de un tramo, según el grano.
 *
 *  Se parte el ISO a mano en vez de pasar por `Date`: `new Date("2026-10-05")`
 *  se interpreta en UTC y al formatear en una zona al oeste retrocede un día,
 *  así que la barra del lunes saldría rotulada como domingo.
 */
function rotulo(desde: string, grano: Grano): string {
  const [a, m, d] = desde.split("-");
  if (grano === "month") return `${m}/${a?.slice(2)}`;
  return `${d}/${m}`;
}

/** Cuántas barras caben con rótulo legible. Pasadas de ahí se rotula una de
 *  cada n: con sesenta días, sesenta fechas se solapan en una mancha gris. */
const ROTULOS_QUE_CABEN = 14;

export function PersonasEnElTiempo({
  series,
}: {
  series: Record<Grano, TramoDeUso[]>;
}) {
  // Persistido, igual que el plazo: es una forma de mirar, no un estado de
  // pantalla.
  const [grano, setGrano] = usePersistido<Grano>("uso.tiempo.grano", "day");

  const tramos = series[grano] ?? [];
  const maximo = Math.max(...tramos.map((t) => t.users), 1);
  const cadaCuantos = Math.ceil(tramos.length / ROTULOS_QUE_CABEN);

  // La cifra que el gráfico NO puede dar, y que es la que se quiere: cuánta
  // gente distinta hay en total. No es la suma de los tramos ni el máximo de
  // ellos --por lo mismo de siempre, la gente no se suma-- así que se dice la
  // punta y se dice que es la punta.
  const punta = useMemo(
    () => tramos.reduce((max, t) => Math.max(max, t.users), 0),
    [tramos],
  );
  const estrenos = useMemo(
    () => tramos.reduce((n, t) => n + t.newUsers, 0),
    [tramos],
  );

  if (tramos.length === 0) {
    return (
      <Panel title={tx("Personas en el tiempo")}>
        <p className="p-4 text-sm text-[var(--muted)]">
          {tx("Todavía no hay tramos que enseñar en este plazo.")}
        </p>
      </Panel>
    );
  }

  return (
    <Panel
      title={tx("Personas en el tiempo")}
      meta={
        estrenos > 0
          ? tx("máximo {{v0}} a la vez · {{v1}} estrenos", {
              v0: punta,
              v1: estrenos,
            })
          : tx("máximo {{v0}} a la vez", { v0: punta })
      }
      ayuda={tx(
        "Personas DISTINTAS con actividad en cada tramo. No se suman entre tramos: quien entra lunes y martes es una sola persona en la semana. El tramo relleno más oscuro son las que aparecen por primera vez.",
      )}
      acciones={
        <div
          className="flex items-center gap-1"
          role="group"
          aria-label={tx("Grano de la serie")}
        >
          {GRANOS.map((g) => (
            <button
              key={g.key}
              onClick={() => setGrano(g.key)}
              aria-pressed={grano === g.key}
              data-track={`Uso: personas por ${g.key}`}
              className={`rounded-md border px-2 py-1 text-xs ${
                grano === g.key
                  ? "border-[var(--accent)] text-[var(--accent)]"
                  : "border-[var(--border)] text-[var(--muted)]"
              }`}
            >
              {g.label}
            </button>
          ))}
        </div>
      }
    >
      <div className="p-4">
        <div className="overflow-x-auto">
          <div
            className="flex h-40 items-end gap-[2px]"
            style={{ minWidth: `${Math.max(1, tramos.length) * 10}px` }}
          >
            {tramos.map((t) => {
              const alto = (t.users / maximo) * 100;
              const nuevos = t.users > 0 ? (t.newUsers / t.users) * alto : 0;
              return (
                <div
                  key={t.from}
                  className="flex h-full flex-1 flex-col justify-end"
                  title={detalle(t, grano)}
                >
                  {/* Dos tramos apilados en una barra, no dos barras: los
                      estrenos son PARTE de los activos, no gente aparte, y
                      ponerlos al lado invitaría a sumarlos. El hueco de 1px
                      los separa sin inventar un borde de color. */}
                  {t.newUsers > 0 && (
                    <span
                      className="w-full rounded-t bg-[var(--accent)]"
                      style={{ height: `${nuevos}%` }}
                    />
                  )}
                  <span
                    className={`w-full ${t.newUsers > 0 ? "mt-[1px]" : "rounded-t"} ${
                      t.users > 0
                        ? "bg-[var(--accent)] opacity-40"
                        : "bg-[var(--border)]"
                    }`}
                    style={{
                      height: `${Math.max(t.users > 0 ? 2 : 1, alto - nuevos)}%`,
                    }}
                  />
                </div>
              );
            })}
          </div>

          {/* Los rótulos van en su propia fila con el mismo reparto que las
              barras, no dentro de cada una: metidos en la barra la empujan
              hacia arriba y el cero deja de poder pintarse. */}
          <div
            className="mt-1 flex gap-[2px]"
            style={{ minWidth: `${Math.max(1, tramos.length) * 10}px` }}
          >
            {tramos.map((t, i) => (
              <span
                key={t.from}
                className="flex-1 overflow-hidden whitespace-nowrap text-center text-[10px] tabular-nums text-[var(--muted)]"
              >
                {i % cadaCuantos === 0 ? rotulo(t.from, grano) : ""}
              </span>
            ))}
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[var(--muted)]">
          <span className="flex items-center gap-1.5">
            <span
              aria-hidden
              className="inline-block h-3 w-3 rounded-sm bg-[var(--accent)] opacity-40"
            />
            {tx("Ya venían")}
          </span>
          <span className="flex items-center gap-1.5">
            <span
              aria-hidden
              className="inline-block h-3 w-3 rounded-sm bg-[var(--accent)]"
            />
            {tx("Primera vez")}
          </span>
          <span>
            {tx(
              "«Primera vez» es la primera de siempre, no la primera dentro del plazo.",
            )}
          </span>
        </div>
      </div>

      {/* La misma serie en tabla, de lo más nuevo a lo más viejo. Un gráfico de
          barras no se lee con el teclado ni con un lector de pantalla, y dos
          tramos de alto parecido sólo se distinguen por el número. Se enseñan
          los doce últimos: la tabla es para comparar lo reciente, el dibujo
          para ver la forma de todo. */}
      <div className="overflow-x-auto border-t border-[var(--border)]">
        <table className="w-full">
          <thead className="bg-[var(--surface-2)]">
            <tr>
              {[
                tx("Desde"),
                tx("Personas"),
                tx("Primera vez"),
                tx("Sesiones"),
                tx("Páginas"),
                tx("Clics"),
              ].map((h, i) => (
                <th
                  key={h}
                  scope="col"
                  className={`px-3 py-2 text-xs font-medium text-[var(--muted)] ${
                    i === 0 ? "text-left" : "text-right"
                  }`}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[...tramos]
              .reverse()
              .slice(0, 12)
              .map((t) => (
                <tr
                  key={t.from}
                  className={`border-t border-[var(--border)] ${
                    t.users === 0 ? "text-[var(--muted)]" : ""
                  }`}
                >
                  <td className="px-3 py-2 text-sm tabular-nums">{t.from}</td>
                  <td className="px-3 py-2 text-right text-sm tabular-nums">
                    {t.users}
                  </td>
                  <td className="px-3 py-2 text-right text-sm tabular-nums">
                    {t.newUsers > 0 ? t.newUsers : "-"}
                  </td>
                  <td className="px-3 py-2 text-right text-sm tabular-nums">
                    {t.sessions}
                  </td>
                  <td className="px-3 py-2 text-right text-sm tabular-nums">
                    {t.pages}
                  </td>
                  <td className="px-3 py-2 text-right text-sm tabular-nums">
                    {t.clicks}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

/** El globo de una barra. Con el tramo vacío dice que está vacío en vez de
 *  enseñar una fila de ceros, que se lee como un fallo. */
function detalle(t: TramoDeUso, grano: Grano): string {
  const cuando = grano === "month" ? t.from.slice(0, 7) : t.from;
  if (t.users === 0) return `${cuando}: ${tx("nadie")}`;
  const gente =
    t.users === 1
      ? tx("1 persona")
      : tx("{{v0}} personas", { v0: String(t.users) });
  const nuevas =
    t.newUsers > 0 ? ` · ${tx("{{v0}} nuevas", { v0: String(t.newUsers) })}` : "";
  return `${cuando}: ${gente}${nuevas} · ${t.clicks} ${tx("clics")}`;
}
