/** «Sus clases»: la tarjeta de la ficha con lo que es el jugador en cada
 *  clasificación y por qué, en una frase (2026-11-18, pedido del usuario).
 *  Las clases salen de `/player-classes`, la misma respuesta que la pantalla
 *  de Clasificación de jugadores: no hay cálculo propio aquí. */
import { Link } from "react-router-dom";
import { Panel } from "../Panels";
import { usePlayerClassChanges, usePlayerClasses } from "../../hooks/useTeam";
import { tx } from "../../i18n/tx";
import { nombreDeGrupo, pertenencias } from "./frases";
import { Punto } from "./comun";

export function SusClases({ htPlayerId }: { htPlayerId: number }) {
  const { data } = usePlayerClasses();
  // Lo que cambió desde la sincronización anterior (2026-11-18, pedido del
  // usuario): la línea de esa clase dice de dónde venía.
  const cambios = usePlayerClassChanges();
  const antes = (clave: string | undefined): string | null => {
    const c = cambios.data?.changes.find(
      (x) => x.htPlayerId === htPlayerId && x.classification === clave,
    );
    return c ? nombreDeGrupo(c.classification, c.before) : null;
  };
  // Mientras llega, o si falla, la ficha sigue entera: la tarjeta es un
  // añadido, no algo que deba tumbar la pantalla.
  const lista = data ? pertenencias(data, htPlayerId) : null;
  if (!lista || lista.length === 0) return null;
  return (
    <Panel
      title={tx("Sus clases")}
      meta={
        <Link
          to="/team/classes"
          className="underline decoration-[var(--border)] underline-offset-2 hover:text-[var(--accent)]"
        >
          {tx("Ver en Clasificación de jugadores")}
        </Link>
      }
    >
      <ul className="divide-y divide-[var(--border)]">
        {lista.map((p) => (
          <li
            key={p.clasificacion}
            className="grid gap-x-4 gap-y-1 px-4 py-2.5 text-sm sm:grid-cols-[12rem_1fr]"
          >
            <div className="min-w-0">
              <p className="text-xs text-[var(--muted)]">{p.clasificacion}</p>
              <span
                className="inline-flex items-center gap-1.5 rounded-full border bg-[var(--surface)] px-2.5 py-0.5"
                style={{ borderColor: p.color }}
              >
                <Punto color={p.color} />
                {p.grupo}
              </span>
            </div>
            <p className="self-center">
              {p.frase}
              {antes(p.clave) && (
                <span className="ml-1.5 text-xs text-[var(--muted)]">
                  {tx("Antes: {{grupo}}, en la sincronización anterior.", {
                    grupo: antes(p.clave),
                  })}
                </span>
              )}
            </p>
          </li>
        ))}
      </ul>
    </Panel>
  );
}
