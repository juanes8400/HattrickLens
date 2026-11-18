/** Piezas que comparten las cuatro vistas de Clases de Jugador. */
import { PlayerLink } from "../PlayerLink";
import { tx } from "../../i18n/tx";
import type { JugadorDeClases } from "../../services/api";
import type { Grupo } from "./colores";

export function Punto({ color }: { color: string }) {
  return (
    <span
      aria-hidden
      className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
      style={{ background: color }}
    />
  );
}

/** El grupo de un jugador en una celda: borde y punto del color del grupo,
 *  texto en tinta normal (el color nunca va solo). */
export function Pastilla({ texto, color }: { texto: string; color: string }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border bg-[var(--surface)] px-2 py-0.5 text-xs"
      style={{ borderColor: color }}
    >
      <Punto color={color} />
      {texto}
    </span>
  );
}

/** Debajo de cada gráfica: quién va en cada grupo, para quien prefiera leer. */
export function ListaDeGrupos({
  grupos,
  detalle,
}: {
  grupos: Grupo[];
  detalle?: (j: JugadorDeClases) => string;
}) {
  return (
    <div
      className="grid gap-4"
      style={{
        gridTemplateColumns: "repeat(auto-fit, minmax(11rem, 1fr))",
      }}
    >
      {grupos.map((g) => (
        <section key={g.clave} className="min-w-0">
          <h3 className="mb-1.5 flex items-baseline gap-2 border-b border-[var(--border)] pb-1.5 text-sm font-semibold">
            <Punto color={g.color} />
            <span>
              {g.nombre}{" "}
              <span className="font-normal text-[var(--muted)]">
                · {g.jugadores.length}
              </span>
            </span>
          </h3>
          {g.jugadores.length === 0 ? (
            <p className="text-sm text-[var(--muted)]">{tx("Nadie")}</p>
          ) : (
            <ul className="space-y-1 text-sm">
              {g.jugadores.map((j) => (
                <li key={j.htPlayerId} className="flex min-w-0 gap-1.5">
                  <span className="truncate">
                    <PlayerLink htPlayerId={j.htPlayerId} name={j.name} />
                  </span>
                  <span className="shrink-0 text-[var(--muted)]">
                    {detalle ? detalle(j) : j.ageYears}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      ))}
    </div>
  );
}
