import type { CSSProperties } from "react";
import type { MatchDetail } from "../services/api";

import { tx } from "../i18n/tx";
/**
 * Mapa de sectores de un partido jugado, como una cancha.
 *
 * 2026-09-13, pedido del usuario: tenía que verse con la misma calidad que los
 * «Duelos por zona de la cancha» de Rivales. Antes era una rejilla de nueve
 * tarjetas que comparaba cada sector contra EL MISMO sector del rival --tu
 * defensa izquierda contra su defensa izquierda--, que no es un duelo: en la
 * cancha tu defensa izquierda se enfrenta a su ataque derecho.
 *
 * Ahora son los mismos siete duelos que Rivales, con la misma regla:
 *
 *   · en tu campo, tu defensa contra su ataque reflejado,
 *   · en su campo, tu ataque contra su defensa reflejada,
 *   · y el medio campo contra el medio campo.
 *
 * El % es la misma contienda simple, rating / (rating + rating).
 */

// Los mismos dos colores que Rivales, para que una cancha se lea igual en las
// dos pantallas.
const OWN_COLOR = "#4f7cff";
const RIVAL_COLOR = "#8b5cf6";

type Zona = "left" | "central" | "right";

const ETIQUETA: Record<Zona, string> = {
  left: "Izquierda",
  central: "Centro",
  right: "Derecha",
};

/** Qué sector propio se enfrenta a qué sector del rival. */
const EN_TU_CAMPO: Record<Zona, [string, string]> = {
  left: ["left_def", "right_att"],
  central: ["central_def", "central_att"],
  right: ["right_def", "left_att"],
};
const EN_SU_CAMPO: Record<Zona, [string, string]> = {
  left: ["left_att", "right_def"],
  central: ["central_att", "central_def"],
  right: ["right_att", "left_def"],
};

interface Duelo {
  propio: number;
  rival: number;
  pct: number;
}

function Celda({
  duelo,
  etiqueta,
  detalle,
  style,
}: {
  duelo: Duelo;
  etiqueta: string;
  detalle: string;
  style?: CSSProperties;
}) {
  const propio = Math.round(duelo.pct * 100);
  const rival = 100 - propio;
  return (
    <div
      className="flex flex-col overflow-hidden rounded border border-[var(--border)]"
      style={style}
      title={detalle}
    >
      <div className="bg-[var(--surface-2)] px-1 py-0.5 text-center text-[9px] uppercase text-[var(--muted)]">
        {etiqueta}
      </div>
      <div className="flex flex-1 text-white">
        {propio > 0 && (
          <div
            className="flex flex-col items-center justify-center px-0.5 py-1.5"
            style={{ width: `${propio}%`, background: OWN_COLOR }}
          >
            <span className="text-xs font-bold tabular-nums">{propio}%</span>
            <span className="text-[9px] tabular-nums opacity-80">
              ({duelo.propio})
            </span>
          </div>
        )}
        {rival > 0 && (
          <div
            className="flex flex-col items-center justify-center px-0.5 py-1.5"
            style={{ width: `${rival}%`, background: RIVAL_COLOR }}
          >
            <span className="text-xs font-bold tabular-nums">{rival}%</span>
            <span className="text-[9px] tabular-nums opacity-80">
              ({duelo.rival})
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

export function MatchSectorMap({ data }: { data: MatchDetail }) {
  const propio = new Map(data.sectors.map((s) => [s.sector, s.own]));
  const suyo = new Map(data.sectors.map((s) => [s.sector, s.opponent]));
  const duelo = ([mio, del_rival]: [string, string]): Duelo => {
    const a = propio.get(mio) ?? 0;
    const b = suyo.get(del_rival) ?? 0;
    return { propio: a, rival: b, pct: a + b > 0 ? a / (a + b) : 0.5 };
  };
  // Frases escritas y no armadas con las etiquetas del sector: «Ataque
  // derecha» pegado detrás de «su» salía «su ataque derecha».
  const COMO_SE_DICE: Record<string, string> = {
    left_def: "defensa por la izquierda",
    central_def: "defensa por el centro",
    right_def: "defensa por la derecha",
    left_att: "ataque por la izquierda",
    central_att: "ataque por el centro",
    right_att: "ataque por la derecha",
  };
  const detalle = ([mio, del_rival]: [string, string]) =>
    `Tu ${COMO_SE_DICE[mio] ?? mio} contra su ${COMO_SE_DICE[del_rival] ?? del_rival}`;

  const zonas: Zona[] = ["left", "central", "right"];
  const medio = duelo(["midfield", "midfield"]);

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] p-4">
      <div className="mb-3 flex items-center justify-between gap-2 text-xs text-[var(--muted)]">
        <span>{tx("Mapa de sectores")}</span>
        <span>{tx("tu defensa contra su ataque, y al revés")}</span>
      </div>
      <div className="mb-1.5 grid grid-cols-[1fr_0.7fr_1fr] gap-1.5 text-center text-[10px] uppercase text-[var(--muted)]">
        <div className="flex items-center justify-center gap-1.5">
          <span
            className="h-2 w-2 rounded-full"
            style={{ background: OWN_COLOR }}
          />
          {tx("Tu campo")}
        </div>
        <div>{tx("Medio")}</div>
        <div className="flex items-center justify-center gap-1.5">
          {tx("Campo rival")}
          <span
            className="h-2 w-2 rounded-full"
            style={{ background: RIVAL_COLOR }}
          />
        </div>
      </div>
      {/* El fondo va con el tema, igual que en Rivales: un verde de cancha fijo
          se leía como franjas negras entre las celdas en modo día. */}
      <div
        className="grid gap-1.5 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-2"
        style={{
          gridTemplateColumns: "1fr 0.7fr 1fr",
          gridTemplateRows: "repeat(3, minmax(52px, auto))",
        }}
      >
        {zonas.map((z, i) => (
          <Celda
            key={`tu-${z}`}
            duelo={duelo(EN_TU_CAMPO[z])}
            etiqueta={ETIQUETA[z]}
            detalle={detalle(EN_TU_CAMPO[z])}
            style={{ gridColumn: 1, gridRow: i + 1 }}
          />
        ))}
        <Celda
          duelo={medio}
          etiqueta={tx("Medio campo")}
          detalle={tx("Tu medio campo contra el suyo")}
          style={{ gridColumn: 2, gridRow: "1 / span 3" }}
        />
        {zonas.map((z, i) => (
          <Celda
            key={`su-${z}`}
            duelo={duelo(EN_SU_CAMPO[z])}
            etiqueta={ETIQUETA[z]}
            detalle={detalle(EN_SU_CAMPO[z])}
            style={{ gridColumn: 3, gridRow: i + 1 }}
          />
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-3 text-[11px] text-[var(--muted)]">
        <span className="inline-flex items-center gap-1">
          <span className="h-2 w-4 rounded" style={{ background: OWN_COLOR }} />{" "}
          {tx("Nosotros")}
        </span>
        <span className="inline-flex items-center gap-1">
          <span
            className="h-2 w-4 rounded"
            style={{ background: RIVAL_COLOR }}
          />{" "}
          {data.opponent}
        </span>
      </div>
    </div>
  );
}
