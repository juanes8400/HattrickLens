import clsx from "clsx";
import { number } from "../hooks/useFormat";
import type { NationalMatchAppearance } from "../services/api";
import { Empty, Panel } from "./Panels";
import type { ClubComparisonChange } from "../services/api";

const ECONOMY_KEYS = [
  "cash",
  "income_sum",
  "costs_sum",
  "fan_club_size",
  "supporters_popularity",
];

function signed(value: number | null): string {
  if (value == null) return ", ";
  if (value === 0) return "0";
  return `${value > 0 ? "+" : ""}${number(value)}`;
}

function EconomyCard({ change }: { change: ClubComparisonChange }) {
  return (
    <section
      className={clsx(
        "rounded-lg border p-4",
        change.isGood === true &&
          "border-[var(--positive)]/40 bg-[var(--positive)]/5",
        change.isGood === false &&
          "border-[var(--danger)]/40 bg-[var(--danger)]/5",
        change.isGood == null && "border-[var(--border)] bg-[var(--bg)]",
      )}
    >
      <div className="text-xs text-[var(--muted)]">{change.label}</div>
      <div className="mt-2 text-lg font-semibold tabular-nums">
        {change.currentDisplay ?? "-"}
      </div>
      <div className="mt-1 flex items-center justify-between gap-2 text-xs">
        <span className="text-[var(--muted)]">
          antes: {change.beforeDisplay ?? "-"}
        </span>
        {change.changed && change.delta != null && (
          <span
            className={clsx(
              "font-semibold tabular-nums",
              change.isGood === true && "text-[var(--positive)]",
              change.isGood === false && "text-[var(--danger)]",
              change.isGood == null && "text-[var(--muted)]",
            )}
          >
            {change.isGood === true && "▲ "}
            {change.isGood === false && "▼ "}
            {signed(change.delta)}
          </span>
        )}
      </div>
    </section>
  );
}

/** Punto 3 pedido 2026-08-10: la economía debe verse mucho más arriba de la
 * página y en colores — verde cuando sube algo bueno (caja, ingresos,
 * socios, afición), rojo cuando sube algo malo (gastos). */
export function EconomySection({
  changes,
}: {
  changes: ClubComparisonChange[];
}) {
  const items = ECONOMY_KEYS.map((key) =>
    changes.find((c) => c.key === key),
  ).filter((c): c is ClubComparisonChange => c != null);
  if (items.length === 0) return null;
  return (
    <Panel
      title="Economía"
      meta="antes → ahora, cierre semanal contra cierre semanal"
    >
      <div className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-5">
        {items.map((change) => (
          <EconomyCard key={change.key} change={change} />
        ))}
      </div>
    </Panel>
  );
}

/** Lo que queda del comparativo de club una vez la economía se sube a su
 * propia sección: sólo espíritu del equipo y confianza. */
/** Lo que trae el entrenamiento: qué se entrena, con qué intensidad y cuánta
 *  resistencia. Panel propio desde 2026-08-22, reportado por el usuario: había
 *  cambiado el tipo de entrenamiento y no aparecía en Cambios por ninguna
 *  parte. Y no cabe en "Moral del equipo": el tipo de entrenamiento no es un
 *  estado de ánimo. */
const TRAINING_KEYS = ["training_type", "training_level", "stamina_part"];

function TarjetasDeCambio({ items }: { items: ClubComparisonChange[] }) {
  return (
    <div className="grid gap-3 p-4 md:grid-cols-2">
      {items.map((change) => (
        <section
          key={change.key}
          className={clsx(
            "rounded-lg border p-4",
            change.changed
              ? "border-[var(--accent)] bg-[var(--accent-soft)]"
              : "border-[var(--border)] bg-[var(--bg)]",
          )}
        >
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs text-[var(--muted)]">{change.label}</span>
            <span
              className={clsx(
                "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                change.changed
                  ? "bg-[var(--accent)] text-white"
                  : "bg-[var(--surface-2)] text-[var(--muted)]",
              )}
            >
              {change.changed ? "Cambió" : "Igual"}
            </span>
          </div>
          <div className="mt-4 grid grid-cols-[1fr_auto_1fr] items-center gap-3">
            <div>
              <div className="text-[10px] uppercase tracking-wide text-[var(--muted)]">
                Antes
              </div>
              <div className="mt-1 text-sm font-medium">
                {change.beforeDisplay ?? "-"}
              </div>
            </div>
            <span aria-hidden className="text-[var(--muted)]">
              →
            </span>
            <div className="text-right">
              <div className="text-[10px] uppercase tracking-wide text-[var(--muted)]">
                Ahora
              </div>
              <div className="mt-1 text-sm font-semibold">
                {change.currentDisplay ?? "-"}
              </div>
            </div>
          </div>
        </section>
      ))}
    </div>
  );
}

export function TrainingSection({ changes }: { changes: ClubComparisonChange[] }) {
  const items = TRAINING_KEYS.map((key) => changes.find((c) => c.key === key)).filter(
    (c): c is ClubComparisonChange => c !== undefined,
  );
  return (
    <Panel title="Entrenamiento" meta="qué se entrena y con cuánta intensidad">
      {items.length === 0 ? (
        <Empty>Aún no hay dos semanas de entrenamiento que comparar.</Empty>
      ) : (
        <TarjetasDeCambio items={items} />
      )}
    </Panel>
  );
}

export function ClubMoraleSection({
  changes,
}: {
  changes: ClubComparisonChange[];
}) {
  const items = changes.filter(
    (c) => !ECONOMY_KEYS.includes(c.key) && !TRAINING_KEYS.includes(c.key),
  );
  return (
    <Panel
      title="Moral del equipo"
      meta="espíritu y confianza, cierre semanal contra cierre semanal"
    >
      {items.length === 0 ? (
        <Empty>Aún no hay dos estados del club que se puedan comparar.</Empty>
      ) : (
        <TarjetasDeCambio items={items} />
      )}
    </Panel>
  );
}


/** Quién jugó con su selección y cuántos minutos.
 *
 * Esos partidos no están en el archivo de ningún club, así que no aparecían
 * por ningún lado: un jugador se iba el martes, volvía con un partido más de
 * experiencia, y en Cambios no se veía nada.
 */
export function NationalTeamSection({
  appearances,
}: {
  appearances: NationalMatchAppearance[];
}) {
  if (appearances.length === 0) return null;
  return (
    <Panel
      title="Con su selección"
      meta={`${appearances.length} ${appearances.length === 1 ? "partido" : "partidos"} desde el informe anterior`}
    >
      <ul className="divide-y divide-[var(--border)]">
        {appearances.map((a) => (
          <li key={`${a.htPlayerId}-${a.playedAt}`} className="px-4 py-3 text-sm">
            <span className="font-medium">{a.name}</span> jugó{" "}
            <span className="tabular-nums font-medium">{a.minutes} min</span> en{" "}
            {a.match || a.competition}
            {a.rating ? (
              <span className="text-[var(--muted)]"> · {a.rating} estrellas</span>
            ) : null}
          </li>
        ))}
      </ul>
    </Panel>
  );
}
