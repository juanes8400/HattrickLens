/** «Cambios de clase» en Cambios (2026-11-18, pedido del usuario: «Esto
 *  sería espectacular»): quién cambió de clase desde la sincronización
 *  anterior, y la frase que explica dónde está ahora, para ver si lo movió
 *  el jugador o el corte (otro que sube, la mediana que se mueve).
 *
 *  Sólo las tres clasificaciones de la app: lo que mueves a mano en las
 *  tuyas no es noticia. */
import { Link } from "react-router-dom";
import { Panel } from "../Panels";
import { PlayerLink } from "../PlayerLink";
import { usePlayerClassChanges, usePlayerClasses } from "../../hooks/useTeam";
import { tx } from "../../i18n/tx";
import type { CambioDeClase } from "../../services/api";
import {
  fraseDeEtapa,
  fraseDeRentabilidad,
  fraseDeTitularidad,
  nombreDeGrupo,
} from "./frases";

const NOMBRE = {
  titularidad: () => tx("Titularidad"),
  rentabilidad: () => tx("Rentabilidad deportiva"),
  etapa: () => tx("Etapa de carrera"),
} as const;

export function CambiosDeClase() {
  const cambios = usePlayerClassChanges();
  const clases = usePlayerClasses();
  // Es un añadido de Cambios: mientras llega, o si falla, no estorba.
  if (!cambios.data || cambios.data.syncId == null) return null;
  const { changes, previousSyncId } = cambios.data;

  const ahora = (c: CambioDeClase): string | null => {
    const d = clases.data;
    const j = d?.players.find((p) => p.htPlayerId === c.htPlayerId);
    if (!d || !j) return null;
    const p =
      c.classification === "titularidad"
        ? fraseDeTitularidad(d, j)
        : c.classification === "rentabilidad"
          ? fraseDeRentabilidad(d, j)
          : fraseDeEtapa(d, j);
    return p?.frase ?? null;
  };

  return (
    <Panel
      title={tx("Cambios de clase")}
      meta={
        <Link
          to="/classes"
          className="underline decoration-[var(--border)] underline-offset-2 hover:text-[var(--accent)]"
        >
          {tx("Ver en Clasificación de jugadores")}
        </Link>
      }
    >
      {previousSyncId == null ? (
        <p className="px-4 py-3 text-sm text-[var(--muted)]">
          {tx(
            "Las clases de hoy quedan guardadas. Desde la próxima sincronización verás aquí quién cambió de clase.",
          )}
        </p>
      ) : changes.length === 0 ? (
        <p className="px-4 py-3 text-sm text-[var(--muted)]">
          {tx("Nadie cambió de clase desde la sincronización anterior.")}
        </p>
      ) : (
        <ul className="divide-y divide-[var(--border)]">
          {changes.map((c) => (
            <li
              key={`${c.htPlayerId}-${c.classification}`}
              className="space-y-0.5 px-4 py-2.5 text-sm"
            >
              <p>
                <span className="font-medium">
                  <PlayerLink htPlayerId={c.htPlayerId} name={c.playerName} />
                </span>
                <span className="text-[var(--muted)]">
                  {" · "}
                  {NOMBRE[c.classification]()}
                  {": "}
                </span>
                {nombreDeGrupo(c.classification, c.before)}
                {" → "}
                <span className="font-medium">
                  {nombreDeGrupo(c.classification, c.after)}
                </span>
              </p>
              {ahora(c) && (
                <p className="text-xs text-[var(--muted)]">{ahora(c)}</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
