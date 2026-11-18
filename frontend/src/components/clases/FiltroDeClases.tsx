/** «Ver sólo: [clasificación] [grupo]». Primero se elige la clasificación y
 *  después uno de sus grupos; la tabla de abajo se queda con esos jugadores. */
import { tx } from "../../i18n/tx";
import type { ClasesDeJugador } from "../../services/api";
import {
  clasificacionesElegibles,
  SIN_FILTRO,
  type ValorDelFiltro,
} from "./filtro";

const SELECT =
  "rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-sm";

export function FiltroDeClases({
  datos,
  valor,
  onChange,
  id,
}: {
  datos: ClasesDeJugador;
  valor: ValorDelFiltro;
  onChange: (v: ValorDelFiltro) => void;
  /** Para atar las etiquetas a sus desplegables; uno por pantalla. */
  id: string;
}) {
  const lista = clasificacionesElegibles(datos);
  const elegida = lista.find((c) => c.clave === valor.clasificacion);
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <label htmlFor={`${id}-clasificacion`} className="text-[var(--muted)]">
        {tx("Ver sólo")}
      </label>
      <select
        id={`${id}-clasificacion`}
        className={SELECT}
        value={elegida ? elegida.clave : ""}
        onChange={(e) =>
          onChange(
            e.target.value
              ? { clasificacion: e.target.value, grupo: "" }
              : SIN_FILTRO,
          )
        }
      >
        <option value="">{tx("Todos los jugadores")}</option>
        {lista.map((c) => (
          <option key={c.clave} value={c.clave}>
            {c.nombre}
          </option>
        ))}
      </select>
      {elegida && (
        <select
          aria-label={tx("Grupo de {{clasificacion}}", {
            clasificacion: elegida.nombre,
          })}
          className={SELECT}
          value={
            elegida.grupos.some((g) => g.clave === valor.grupo)
              ? valor.grupo
              : ""
          }
          onChange={(e) =>
            onChange({ clasificacion: elegida.clave, grupo: e.target.value })
          }
        >
          <option value="">{tx("Cualquier grupo")}</option>
          {/* Sin los grupos vacíos: elegir uno dejaría la tabla en blanco. */}
          {elegida.grupos
            .filter((g) => g.jugadores.length > 0)
            .map((g) => (
              <option key={g.clave} value={g.clave}>
                {`${g.nombre} (${g.jugadores.length})`}
              </option>
            ))}
        </select>
      )}
      {valor.clasificacion && (
        <button
          type="button"
          className="text-xs text-[var(--muted)] underline underline-offset-2 hover:text-[var(--accent)]"
          onClick={() => onChange(SIN_FILTRO)}
        >
          {tx("Quitar filtro")}
        </button>
      )}
    </div>
  );
}
