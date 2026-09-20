import clsx from "clsx";
import { PlayerLink } from "./PlayerLink";
import { Empty } from "./Panels";
import { number, cifra, money } from "../hooks/useFormat";

import { tx } from "../i18n/tx";
/**
 * Formato "Hattrick Control" pedido 2026-08-10: jugador por jugador,
 * habilidad por habilidad, y luego un agregado del equipo desglosado POR
 * habilidad (no un total único), usado tanto por el snapshot más reciente
 * como por el histórico de la semana, para que ambas vistas se lean igual.
 */
export interface NormalizedChange {
  key: string;
  label: string;
  before: number | boolean | null;
  current: number | boolean | null;
  delta: number | null;
  direction: "up" | "down" | "neutral";
  /** El canterano LLEGÓ con esto puesto. No es un descubrimiento del ojeador
   *  ni una subida: es lo que traía en la maleta. */
  isArrival?: boolean;
  /** Sólo en el alta de un jugador del primer equipo: lo que costó, de dónde
   *  salió y lo que cobra desde hoy. Un alta sin esto es media noticia --que
   *  hay alguien nuevo-- sin la otra mitad, que es lo que vale y lo que pesa
   *  en la nómina (2026-09-20, pedido del usuario). */
  arrivalPrice?: number | null;
  fromAcademy?: boolean;
  arrivalSalary?: number | null;
  currency?: string;
}

export interface PlayerChangeGroup {
  htPlayerId: number;
  name: string;
  changes: NormalizedChange[];
  /** Un canterano. Cambia dos cosas: no se enlaza a su ficha --no la tiene en
   *  /players-- y se rotula, porque un «Pases +1» de un chico de la academia
   *  no es la misma noticia que el de un titular. */
  isYouth?: boolean;
  /** Acaba de llegar: lo que se lista no es lo que se movió, es lo que trae
   *  puesto. Sin decirlo, sus habilidades parecerían subidas de la semana. */
  isArrival?: boolean;
}

export interface AggregateMetric {
  key: string;
  label: string;
  /** Cuánto sumaron las subidas. Positivo. */
  upTotal: number;
  /** Cuánto sumaron las bajadas, como número POSITIVO, el signo lo pone el
   *  color, no la cifra. */
  downTotal: number;
}

function signed(value: number): string {
  if (value === 0) return "0";
  return `${value > 0 ? "+" : ""}${number(value)}`;
}

/** Casos sin un par before/current numérico limpio, se muestran como una
 * sola frase coloreada, sin el formato "antes ▲ ahora (delta)". */
function specialChangeLine(change: NormalizedChange): string | null {
  if (change.key === "arrival") {
    const con: string[] = [];
    if (change.arrivalPrice)
      con.push(
        tx("comprado por {{v0}}", {
          v0: money(change.arrivalPrice, change.currency ?? ""),
        }),
      );
    else if (change.fromAcademy) con.push(tx("sube de la cantera"));
    if (change.arrivalSalary)
      con.push(
        tx("sueldo {{v0}}", {
          v0: money(change.arrivalSalary, change.currency ?? ""),
        }),
      );
    // Sin ninguna de las dos --un fichaje que el libro de transferencias aún
    // no trae-- se queda como estaba. Inventar un cero diría «gratis».
    return con.length > 0
      ? `${tx("Nuevo jugador")}: ${con.join(", ")}`
      : tx("Nuevo jugador");
  }
  // UN DESCUBRIMIENTO NO TIENE ANTES. Es de la cantera: el ojeador miró una
  // habilidad que estaba en blanco y ahora se sabe. Pintarlo con el formato
  // «antes ▲ ahora (+n)» obligaría a inventar un cero de partida y una
  // subida que nunca ocurrió, así que se dice lo único cierto: el número que
  // ahora se conoce.
  if (change.before == null && change.delta == null) {
    // Un recién llegado no «descubre» nada: viene con lo que viene, y decirlo
    // de la otra manera sugeriría que el ojeador acaba de mirarle algo.
    return change.isArrival
      ? tx("llega con {{v0}}", { v0: cifra(change.current) })
      : tx("descubierto: {{v0}}", { v0: cifra(change.current) });
  }
  if (change.key === "market")
    return change.current ? tx("Puesto en venta") : tx("Retirado del mercado");
  if (change.key === "injury") {
    if (change.current === -1) return tx("Recuperado");
    if (change.before === -1)
      return tx("Lesión (nivel {{v0}})", { v0: change.current });
    return tx("Lesión {{v0}} → {{v1}}", {
      v0: change.before,
      v1: change.current,
    });
  }
  return null;
}

/** Formato pedido 2026-08-11: "antes ▲ ahora (delta)", sólo el valor
 * nuevo, la flecha y el delta llevan color; "antes" queda en tono neutro
 * para que el ojo vaya directo a lo que cambió. */
function ChangeValue({ change }: { change: NormalizedChange }) {
  const toneClass = clsx(
    "font-semibold tabular-nums",
    change.direction === "up" && "text-[var(--positive)]",
    change.direction === "down" && "text-[var(--danger)]",
    change.direction === "neutral" && "text-[var(--muted)]",
  );
  const special = specialChangeLine(change);
  if (special != null) {
    return <span className={toneClass}>{special}</span>;
  }
  return (
    <span className="tabular-nums">
      <span className="text-[var(--text)]">{cifra(change.before)}</span>{" "}
      <span className={toneClass}>
        {change.direction === "up" && "▲ "}
        {change.direction === "down" && "▼ "}
        {cifra(change.current)} ({signed(change.delta ?? 0)})
      </span>
    </span>
  );
}

function PlayerChangeCard({ group }: { group: PlayerChangeGroup }) {
  return (
    <section className="rounded-lg border border-[var(--border)] bg-[var(--bg)] p-3">
      <header className="mb-2 flex items-baseline justify-between gap-2 border-b border-[var(--border)] pb-2 text-sm font-semibold">
        {group.isYouth ? (
          <span>{group.name}</span>
        ) : (
          <PlayerLink htPlayerId={group.htPlayerId} name={group.name} />
        )}
        {group.isArrival && (
          <span className="shrink-0 rounded-full bg-[var(--accent-soft)] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-[var(--accent)]">
            {tx("acaba de llegar")}
          </span>
        )}
      </header>
      <ul className="space-y-1.5 text-xs">
        {group.changes.map((change, index) => (
          <li
            key={`${change.key}-${index}`}
            className="flex items-center justify-between gap-3"
          >
            <span className="text-[var(--muted)]">{change.label}</span>
            <ChangeValue change={change} />
          </li>
        ))}
      </ul>
    </section>
  );
}

function AggregateCard({ metric }: { metric: AggregateMetric }) {
  // Las tres líneas miden LO MISMO: cuánto se movió, no cuánta gente se movió.
  // Subidas suma lo que ganaron los que subieron, Bajadas lo que perdieron los
  // que bajaron, y el balance es la resta, así los tres números cuadran a
  // simple vista, que es lo que se espera de una lista de tres cifras.
  //
  // Contar cabezas en vez de puntos escondía el tamaño de cada movimiento: un
  // jugador que cae tres niveles pesaba igual que uno que cae uno. Y en TSI y
  // Salario, donde la unidad son puntos de índice y dinero, el conteo no decía
  // nada de lo que de verdad ganó o perdió el club.
  //
  // Las bajadas se escriben en positivo; el signo lo pone el color. El balance
  // sí lo lleva, y en cero se queda con el color de texto normal, un empate no
  // es buena noticia ni mala.
  const balance = metric.upTotal - metric.downTotal;
  return (
    <section className="rounded-lg border border-[var(--border)] bg-[var(--bg)] p-3">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
        {metric.label}
      </div>
      <dl className="space-y-1 text-sm">
        {metric.upTotal > 0 && (
          <div className="flex items-center justify-between">
            <dt className="text-[var(--muted)]">{tx("Subidas")}</dt>
            <dd className="font-semibold tabular-nums text-[var(--positive)]">
              {number(metric.upTotal)}
            </dd>
          </div>
        )}
        {metric.downTotal > 0 && (
          <div className="flex items-center justify-between">
            <dt className="text-[var(--muted)]">{tx("Bajadas")}</dt>
            <dd className="font-semibold tabular-nums text-[var(--danger)]">
              {number(metric.downTotal)}
            </dd>
          </div>
        )}
        <div className="flex items-center justify-between border-t border-[var(--border)] pt-1">
          <dt className="text-[var(--muted)]">{tx("Balance")}</dt>
          <dd
            className={clsx(
              "font-semibold tabular-nums",
              balance > 0 && "text-[var(--positive)]",
              balance < 0 && "text-[var(--danger)]",
            )}
          >
            {signed(balance)}
          </dd>
        </div>
      </dl>
    </section>
  );
}

export function GroupedPlayerChanges({
  groups,
  aggregate,
  emptyMessage,
}: {
  groups: PlayerChangeGroup[];
  aggregate: AggregateMetric[];
  emptyMessage: string;
}) {
  const visibleAggregate = aggregate.filter(
    (metric) => metric.upTotal > 0 || metric.downTotal > 0,
  );

  if (groups.length === 0) {
    return <Empty>{emptyMessage}</Empty>;
  }

  return (
    <div className="space-y-5 p-4">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {groups.map((group) => (
          <PlayerChangeCard key={group.htPlayerId} group={group} />
        ))}
      </div>

      {visibleAggregate.length > 0 && (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
            {tx("Total equipo")}
          </h3>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {visibleAggregate.map((metric) => (
              <AggregateCard key={metric.key} metric={metric} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
