/** Titularidad: la cancha de cada formación con más experiencia, con su
 *  mejor once (Titular) o el de los que quedan (Suplencia). */
import { useState } from "react";
import { usePersistido } from "../../hooks/usePersistido";
import { Tabs } from "../Tabs";
import {
  OrientacionDeLaCancha,
  PITCH_CARD_CLASS,
  PitchField,
  PitchGrid,
} from "../PitchField";
import { PlayerLink } from "../PlayerLink";
import { tx } from "../../i18n/tx";
import type {
  CasillaDeOnce,
  ClasesDeJugador,
  JugadorDeClases,
  OnceDeFormacion,
} from "../../services/api";
import { COLOR, type Grupo } from "./colores";
import { ListaDeGrupos } from "./comun";
import { puesto } from "./frases";

/** Las cuatro filas que pide `PitchGrid`, con el portero al final. */
function filas(casillas: CasillaDeOnce[]): CasillaDeOnce[][] {
  const orden = [...casillas].sort((a, b) => a.slot - b.slot);
  const de = (...bases: string[]) =>
    orden.filter((c) => bases.includes(c.base));
  return [
    de("forward"),
    de("winger", "inner_midfield"),
    de("wingback", "central_defender"),
    de("keeper"),
  ];
}

/** La misma cancha que Alineación, Equipo y la Comparativa de liga
 *  (2026-11-17, pedido del usuario): verde, tarjetas de vidrio y el portero
 *  donde cada uno lo haya puesto. */
function Cancha({
  once,
  jugadores,
}: {
  once: OnceDeFormacion;
  jugadores: Map<number, JugadorDeClases>;
}) {
  return (
    <PitchField
      ariaLabel={tx("Mejor once en formación {{formacion}}", {
        formacion: once.formation,
      })}
      className="rounded-lg"
    >
      <PitchGrid
        rows={filas(once.slots)}
        isFlank={(c) => c.base === "winger" || c.base === "wingback"}
        render={(c) => {
          const j =
            c.htPlayerId != null ? jugadores.get(c.htPlayerId) : undefined;
          if (!j) {
            return (
              <div
                key={c.slot}
                className={`${PITCH_CARD_CLASS} border-dashed !bg-black/10`}
              >
                <div className="truncate text-[9px] uppercase tracking-wide text-white/60">
                  {puesto(c.base)}
                </div>
                <div className="truncate text-[11px] italic text-white/60">
                  {tx("hueco")}
                </div>
              </div>
            );
          }
          return (
            <div key={c.slot} className={PITCH_CARD_CLASS}>
              <div className="truncate text-[9px] uppercase tracking-wide text-white/70">
                {c.label}
              </div>
              <div className="truncate text-[11px] font-semibold text-white">
                <PlayerLink htPlayerId={j.htPlayerId} name={j.name} onDark />
              </div>
              <div className="tabular-nums text-sm font-semibold text-amber-300">
                {c.rating != null ? c.rating.toFixed(2) : ""}
              </div>
            </div>
          );
        }}
      />
    </PitchField>
  );
}

export function Titularidad({ datos }: { datos: ClasesDeJugador }) {
  const [equipo, setEquipo] = useState<"titular" | "suplencia">("titular");
  const jugadores = new Map(datos.players.map((j) => [j.htPlayerId, j]));
  const onces = equipo === "titular" ? datos.starters : datos.substitutes;
  const [formacion, setFormacion] = usePersistido(
    "clases-de-jugador.formacion",
    "",
  );
  const once = onces.find((o) => o.formation === formacion) ?? onces[0];

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
      {/* Una cancha a la vez y a tamaño completo, como en el resto de la app:
          tres en fila las dejaba en tarjetas de tres letras. */}
      <div className="flex flex-wrap items-end justify-between gap-2">
        <Tabs
          modo="filtro"
          label={tx("Formación")}
          tabs={onces.map((o) => ({
            key: o.formation,
            label: `${o.formation} · ${tx("experiencia {{v}}", {
              v: datos.experience[o.formation] ?? 0,
            })}`,
          }))}
          active={once?.formation ?? ""}
          onChange={setFormacion}
        />
        <OrientacionDeLaCancha />
      </div>
      {once && <Cancha once={once} jugadores={jugadores} />}
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
