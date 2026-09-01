import clsx from "clsx";
import { Empty, Panel } from "./Panels";
import type {
  YouthComparisonChange,
  YouthComparisonRow,
  YouthSummary,
} from "../services/api";

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
    <span
      className={clsx(
        "tabular-nums",
        change.maxIsNew && "text-[var(--youth-known)]",
      )}
    >
      techo {change.max}
      {change.maxIsNew && " ✦"}
    </span>
  );
}

function Linea({ change }: { change: YouthComparisonChange }) {
  if (change.key === "arrival") {
    return (
      <span className="font-semibold text-[var(--positive)]">
        Llegó a la academia
      </span>
    );
  }
  if (change.key === "promotable") {
    return (
      <span className="font-semibold text-[var(--positive)]">
        Ya puede ascender
      </span>
    );
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
        {change.delta != null &&
          ` (${change.delta > 0 ? "+" : ""}${change.delta})`}
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
      <header className="mb-2 border-b border-[var(--border)] pb-2">
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-sm font-semibold">{fila.name}</span>
          <span className="shrink-0 text-xs tabular-nums text-[var(--muted)]">
            {fila.age}
          </span>
        </div>
        {/* Lo que se piensa de él AHORA, y si esto lo movió. Un techo suelto
            no dice nada; que el chico haya pasado de «fontanero» a «promesa»
            sí. */}
        {fila.verdict && (
          <div className="mt-1 text-[11px]">
            <span
              className={
                fila.verdictBefore
                  ? "text-[var(--youth-known)]"
                  : "text-[var(--muted)]"
              }
            >
              {fila.verdictBefore ? (
                <>
                  ahora es <b className="font-medium">{fila.verdict}</b>
                  {fila.verdictBefore !== fila.verdict && (
                    <> · antes {fila.verdictBefore}</>
                  )}
                </>
              ) : (
                <>sigue siendo {fila.verdict}</>
              )}
            </span>
          </div>
        )}
      </header>
      <ul className="space-y-1.5 text-xs">
        {fila.changes.map((change, i) => (
          <li
            key={`${change.key}-${i}`}
            className="flex items-center justify-between gap-3"
          >
            <span className="text-[var(--muted)]">{change.label}</span>
            <Linea change={change} />
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Una cifra del resumen, con su lectura debajo. */
function Cifra({ n, de, hint }: { n: string; de: string; hint?: string }) {
  return (
    <div
      className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2"
      title={hint}
    >
      <div className="text-lg font-semibold tabular-nums leading-none">{n}</div>
      <div className="mt-1 text-[11px] leading-tight text-[var(--muted)]">
        {de}
      </div>
    </div>
  );
}

export function YouthChanges({
  rows,
  summary,
}: {
  rows: YouthComparisonRow[];
  summary?: YouthSummary;
}) {
  const revelaciones =
    summary?.revelations ??
    rows.reduce(
      (t, f) => t + f.changes.filter((c) => c.isReveal || c.maxIsNew).length,
      0,
    );
  const salidas = summary?.left ?? [];
  const veredictos = summary?.verdictChanges ?? [];
  const conocidos = summary?.ceilingsNow ?? 0;
  const lecturas = summary?.readings ?? 0;
  const aCiegas =
    lecturas > 0 ? Math.round((100 * (lecturas - conocidos)) / lecturas) : null;
  const hayAlgo = rows.length > 0 || salidas.length > 0;

  return (
    <Panel
      title="La cantera"
      meta={
        hayAlgo
          ? `${revelaciones} ${revelaciones === 1 ? "revelación" : "revelaciones"}` +
            (salidas.length > 0
              ? ` · ${salidas.length} se ${salidas.length === 1 ? "fue" : "fueron"}`
              : "")
          : "sin novedades"
      }
    >
      {/* LO QUE SIGNIFICA, antes que el detalle. Una lista de «Pases: techo 3»
          no contesta la pregunta que trae el usuario --¿voy saliendo de la
          niebla?-- y esa se contesta con dos números. */}
      {lecturas > 0 && (
        <div className="grid grid-cols-2 gap-2 border-b border-[var(--border)] p-4 md:grid-cols-4">
          <Cifra
            n={String(revelaciones)}
            de={
              revelaciones === 1
                ? "techo nuevo esta vez"
                : "techos nuevos esta vez"
            }
            hint="Habilidades cuyo nivel o techo se descubrió en esta comparación"
          />
          <Cifra
            n={`${conocidos}/${lecturas}`}
            de="techos conocidos"
            hint="De todas las lecturas jugador × habilidad de la academia"
          />
          {aCiegas != null && (
            <Cifra
              n={`${aCiegas}%`}
              de="sigue a ciegas"
              hint="Mientras esto sea alto, «Individual» rinde más que cualquier habilidad concreta"
            />
          )}
          {veredictos.length > 0 && (
            <Cifra
              n={String(veredictos.length)}
              de={
                veredictos.length === 1
                  ? "cambió de veredicto"
                  : "cambiaron de veredicto"
              }
              hint="El descubrimiento movió lo que se piensa del canterano"
            />
          )}
        </div>
      )}

      {/* Irse de la academia es el cambio MÁS GRANDE que le puede pasar a un
          canterano, así que va antes que cualquier techo revelado. Hasta el
          2026-08-30 no se decía en ningún sitio. */}
      {salidas.length > 0 && (
        <div className="border-b border-[var(--border)] px-4 py-3 text-sm">
          <span className="font-medium">
            {salidas.length === 1 ? "Dejó la academia" : "Dejaron la academia"}:
          </span>{" "}
          <span className="text-[var(--muted)]">
            {salidas.map((x) => x.name).join(" · ")}
          </span>
        </div>
      )}

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
