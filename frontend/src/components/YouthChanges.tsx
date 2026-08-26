import clsx from "clsx";
import { Empty, Panel } from "./Panels";
import type { YouthComparisonChange, YouthComparisonRow } from "../services/api";

/**
 * Los cambios de la academia, con el mismo formato que los de la plantilla
 * —una tarjeta por chico, una línea por habilidad— porque el usuario los
 * quiere leer igual.
 *
 * Lo que NO se puede copiar de mayores es el fondo: en un juvenil cada
 * habilidad son DOS números, lo que tiene hoy y hasta dónde puede llegar, y
 * los dos se revelan por separado. De ahí salen cuatro noticias distintas que
 * un `antes → ahora` a secas no sabe contar:
 *
 *   - subió de nivel            → entrenamiento dando fruto
 *   - se reveló el nivel        → no ha crecido; ahora lo vemos
 *   - se reveló el techo        → ya sabemos hasta dónde llega
 *   - topó                      → no crecerá más, aunque el techo siga oculto
 *
 * Y una regla de color que importa: **descubrir no es mejorar**. Pintar de
 * verde una revelación diría que el chico progresó cuando lo único que cambió
 * es lo que sabemos de él.
 */

function Techo({ change }: { change: YouthComparisonChange }) {
  if (change.max == null) {
    // Un techo que sigue oculto se dice, no se calla: es la diferencia entre
    // «no llega más alto» y «todavía no sabemos hasta dónde llega».
    return <span className="text-[var(--muted)]">techo sin revelar</span>;
  }
  return (
    <span className={clsx("tabular-nums", change.maxIsNew && "text-[var(--youth-known)]")}>
      techo {change.max}
      {change.maxIsNew && " ✦"}
    </span>
  );
}

function Linea({ change }: { change: YouthComparisonChange }) {
  if (change.key === "arrival") {
    return <span className="font-semibold text-[var(--positive)]">Llegó a la academia</span>;
  }
  if (change.key === "promotable") {
    return <span className="font-semibold text-[var(--positive)]">Ya puede ascender</span>;
  }

  // «Topó» va de sufijo, nunca sustituyendo a la línea: un canterano puede
  // revelarse Y topar en la misma comparación —pasa cuando el nivel aparece ya
  // igualado a su techo— y contar sólo lo segundo se come la noticia de que
  // por fin lo vemos.
  const topo = change.maxJustReached ? (
    <span className="font-semibold text-[var(--muted)]"> · topó</span>
  ) : null;

  // Sólo se movió el techo: el nivel sigue sin saberse. Es el caso que no
  // existe en mayores y el que más se pierde si se fuerza el formato de allí.
  if (change.delta == null && change.current == null) {
    return (
      <span className="tabular-nums">
        <span className="font-semibold text-[var(--youth-known)]">
          techo descubierto: {change.max}
        </span>
        {topo}
      </span>
    );
  }

  if (change.isReveal) {
    return (
      <span className="tabular-nums">
        <span className="font-semibold text-[var(--youth-known)]">
          descubierto: {change.current}
        </span>{" "}
        <span className="text-[var(--muted)]">
          · <Techo change={change} />
        </span>
        {topo}
      </span>
    );
  }

  if (change.maxJustReached && change.delta == null) {
    return (
      <span className="font-semibold tabular-nums text-[var(--muted)]">
        topó{change.current != null ? ` en ${change.current}` : ""}
      </span>
    );
  }

  const tono = clsx(
    "font-semibold tabular-nums",
    change.direction === "up" && "text-[var(--positive)]",
    change.direction === "down" && "text-[var(--danger)]",
    change.direction === "neutral" && "text-[var(--muted)]",
  );
  return (
    <span className="tabular-nums">
      <span className="text-[var(--text)]">{change.before}</span>{" "}
      <span className={tono}>
        {change.direction === "up" && "▲ "}
        {change.direction === "down" && "▼ "}
        {change.current}
        {change.delta != null && ` (${change.delta > 0 ? "+" : ""}${change.delta})`}
      </span>{" "}
      <span className="text-[var(--muted)]">
        · <Techo change={change} />
      </span>
    </span>
  );
}

function Tarjeta({ fila }: { fila: YouthComparisonRow }) {
  return (
    <section className="rounded-lg border border-[var(--border)] bg-[var(--bg)] p-3">
      <header className="mb-2 flex items-baseline justify-between gap-2 border-b border-[var(--border)] pb-2">
        <span className="text-sm font-semibold">{fila.name}</span>
        <span className="shrink-0 text-xs tabular-nums text-[var(--muted)]">{fila.age}</span>
      </header>
      <ul className="space-y-1.5 text-xs">
        {fila.changes.map((change, i) => (
          <li key={`${change.key}-${i}`} className="flex items-center justify-between gap-3">
            <span className="text-[var(--muted)]">{change.label}</span>
            <Linea change={change} />
          </li>
        ))}
      </ul>
    </section>
  );
}

export function YouthChanges({ rows }: { rows: YouthComparisonRow[] }) {
  // Cuántas revelaciones trajo el informe. Es la cifra que dice si la academia
  // se está destapando o sigue a oscuras, y no se deduce mirando las tarjetas
  // una a una.
  const revelaciones = rows.reduce(
    (total, fila) =>
      total + fila.changes.filter((c) => c.isReveal || c.maxIsNew).length,
    0,
  );

  return (
    <Panel
      title="Cambios en la academia"
      meta={
        rows.length === 0
          ? "sin novedades"
          : `${rows.length} canterano${rows.length === 1 ? "" : "s"}` +
            (revelaciones > 0
              ? ` · ${revelaciones} ${revelaciones === 1 ? "revelación" : "revelaciones"}`
              : "")
      }
    >
      {rows.length === 0 ? (
        <Empty>
          Ningún canterano se movió en esta comparación. En juveniles es lo
          normal: las habilidades tardan semanas en asomar.
        </Empty>
      ) : (
        <div className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-3">
          {rows.map((fila) => (
            <Tarjeta key={fila.htYouthPlayerId} fila={fila} />
          ))}
        </div>
      )}
    </Panel>
  );
}
