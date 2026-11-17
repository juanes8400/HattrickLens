/** Titularidad: las canchas de las formaciones con más experiencia, con su
 *  mejor once (Titular) o el de los que quedan (Suplencia). */
import { useState } from "react";
import { Tabs } from "../Tabs";
import { tx } from "../../i18n/tx";
import type {
  CasillaDeOnce,
  ClasesDeJugador,
  JugadorDeClases,
  OnceDeFormacion,
} from "../../services/api";
import { COLOR, type Grupo } from "./colores";
import { ListaDeGrupos } from "./comun";

const LINEA: Record<string, "portero" | "defensa" | "medio" | "ataque"> = {
  keeper: "portero",
  wingback: "defensa",
  central_defender: "defensa",
  winger: "medio",
  inner_midfield: "medio",
  forward: "ataque",
};

/** Altura de cada línea en la cancha, del ataque (arriba) al portero. */
const ALTURA = { ataque: 13, medio: 38, defensa: 64, portero: 88 };

/** La orden, corta, debajo del nombre. Sin orden (la normal), nada. */
function orden(posicion: string | null): string {
  if (!posicion) return "";
  if (posicion.endsWith("_defensive")) return tx("def.");
  if (posicion.endsWith("_offensive")) return tx("of.");
  if (posicion.endsWith("_towards_wing")) return tx("hacia lat.");
  if (posicion.endsWith("_towards_middle")) return tx("hacia medio");
  return "";
}

/** Los de cada línea, de izquierda a derecha: los de banda en los bordes. */
function porLineas(casillas: CasillaDeOnce[]) {
  const lineas = { ataque: [], medio: [], defensa: [], portero: [] } as Record<
    keyof typeof ALTURA,
    CasillaDeOnce[]
  >;
  for (const c of [...casillas].sort((a, b) => a.slot - b.slot)) {
    lineas[LINEA[c.base] ?? "medio"].push(c);
  }
  const bordes = (l: CasillaDeOnce[], banda: string) => {
    const deBanda = l.filter((c) => c.base === banda);
    const centro = l.filter((c) => c.base !== banda);
    return [...deBanda.slice(0, 1), ...centro, ...deBanda.slice(1)];
  };
  lineas.medio = bordes(lineas.medio, "winger");
  lineas.defensa = bordes(lineas.defensa, "wingback");
  return lineas;
}

function Cancha({
  once,
  experiencia,
  jugadores,
  color,
}: {
  once: OnceDeFormacion;
  experiencia: number;
  jugadores: Map<number, JugadorDeClases>;
  color: string;
}) {
  const lineas = porLineas(once.slots);
  return (
    <figure className="mx-auto w-full min-w-0 max-w-[20rem]">
      <figcaption className="mb-1.5 flex items-baseline justify-between gap-2">
        <span className="text-base font-semibold">{once.formation}</span>
        <span className="text-xs text-[var(--muted)]">
          {tx("experiencia {{v}}", { v: experiencia })}
        </span>
      </figcaption>
      <div
        className="relative w-full overflow-hidden rounded-lg border"
        style={{
          aspectRatio: "3 / 4",
          background: "color-mix(in srgb, var(--positive) 10%, var(--surface))",
          borderColor: "color-mix(in srgb, var(--positive) 25%, var(--border))",
        }}
      >
        <div
          aria-hidden
          className="absolute inset-x-0 top-1/2 border-t"
          style={{
            borderColor: "color-mix(in srgb, var(--positive) 25%, transparent)",
          }}
        />
        {(Object.keys(ALTURA) as (keyof typeof ALTURA)[]).flatMap((linea) =>
          lineas[linea].map((c, i, todos) => {
            const j =
              c.htPlayerId != null ? jugadores.get(c.htPlayerId) : undefined;
            const izquierda = ((i + 1) / (todos.length + 1)) * 100;
            return (
              <div
                key={c.slot}
                className="absolute flex w-[22%] -translate-x-1/2 -translate-y-1/2 flex-col items-center text-center"
                style={{ left: `${izquierda}%`, top: `${ALTURA[linea]}%` }}
                title={
                  j
                    ? `${j.name} · ${c.label ?? ""} · ${c.rating ?? ""}`
                    : undefined
                }
              >
                {j ? (
                  <>
                    <span
                      className="flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-semibold text-white"
                      style={{ background: color }}
                    >
                      {c.rating != null ? Math.round(c.rating) : ""}
                    </span>
                    <span className="mt-0.5 w-full truncate text-[11px] leading-tight">
                      {j.shortName}
                    </span>
                    {orden(c.position) && (
                      <span className="text-[10px] leading-tight text-[var(--muted)]">
                        {orden(c.position)}
                      </span>
                    )}
                  </>
                ) : (
                  <>
                    <span className="h-6 w-6 rounded-full border border-dashed border-[var(--muted)] bg-[var(--surface)]" />
                    <span className="mt-0.5 text-[11px] italic text-[var(--muted)]">
                      {tx("hueco")}
                    </span>
                  </>
                )}
              </div>
            );
          }),
        )}
      </div>
    </figure>
  );
}

export function Titularidad({ datos }: { datos: ClasesDeJugador }) {
  const [equipo, setEquipo] = useState<"titular" | "suplencia">("titular");
  const jugadores = new Map(datos.players.map((j) => [j.htPlayerId, j]));
  const onces = equipo === "titular" ? datos.starters : datos.substitutes;
  const color = equipo === "titular" ? COLOR.azul : COLOR.verde;

  /** En cuántas de las formaciones entra cada uno. */
  const veces = new Map<number, number>();
  for (const o of [...datos.starters, ...datos.substitutes]) {
    for (const c of o.slots) {
      if (c.htPlayerId != null)
        veces.set(c.htPlayerId, (veces.get(c.htPlayerId) ?? 0) + 1);
    }
  }
  const de = (clase: string) =>
    datos.players
      .filter((j) => j.titularidad === clase)
      .sort(
        (a, b) =>
          (veces.get(b.htPlayerId) ?? 0) - (veces.get(a.htPlayerId) ?? 0),
      );
  const grupos: Grupo[] = [
    {
      clave: "titular",
      nombre: tx("Titular"),
      color: COLOR.azul,
      jugadores: de("titular"),
    },
    {
      clave: "suplencia",
      nombre: tx("Suplencia"),
      color: COLOR.verde,
      jugadores: de("suplencia"),
    },
    {
      clave: "reserva",
      nombre: tx("Reserva"),
      color: COLOR.gris,
      jugadores: de("reserva"),
    },
  ];
  const total = datos.formations.length;

  if (total === 0) {
    return (
      <p className="text-sm text-[var(--muted)]">
        {tx(
          "Sincroniza para leer la experiencia del equipo en cada formación.",
        )}
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-[var(--muted)]">
        {tx(
          "Titular: quien sale en el mejor once de alguna de las formaciones con más experiencia del equipo. Suplencia: lo mismo sin los titulares; si no llegan a once, quedan huecos. Reserva: los demás. Los lesionados cuentan como sanos.",
        )}
      </p>
      <Tabs
        modo="filtro"
        label={tx("Qué once se ve en las canchas")}
        tabs={[
          { key: "titular", label: tx("Titular") },
          {
            key: "suplencia",
            label: tx("Suplencia"),
            disabled: datos.substitutes.length === 0,
          },
        ]}
        active={equipo}
        onChange={setEquipo}
      />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {onces.map((o) => (
          <Cancha
            key={o.formation}
            once={o}
            experiencia={datos.experience[o.formation] ?? 0}
            jugadores={jugadores}
            color={color}
          />
        ))}
      </div>
      <p className="text-xs text-[var(--muted)]">
        {tx("El número del círculo es su valoración en ese puesto.")}
      </p>
      <ListaDeGrupos
        grupos={grupos}
        detalle={(j) =>
          j.titularidad === "reserva"
            ? String(j.ageYears)
            : tx("{{n}} de {{total}}", {
                n: veces.get(j.htPlayerId) ?? 0,
                total,
              })
        }
      />
    </div>
  );
}
