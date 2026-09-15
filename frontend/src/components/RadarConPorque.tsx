import { useRef, useState } from "react";
import { Chart } from "../charts/Chart";
import { radarOption } from "../charts/chartOptions";
import { Empty, Loading, Note, Panel } from "./Panels";
import { useLeague, useLeagueComparison } from "../hooks/useTeam";
import { decimal, number } from "../hooks/useFormat";

import { tx } from "../i18n/tx";
/**
 * El radar de fuerza con un porqué en cada eje (2026-09-13, opción A + C).
 *
 * Al pasar por el nombre de un eje sale un globo con dos cosas: una frase que
 * dice de dónde sale ese valor, con los goles o el TSI que lo producen, y el
 * puesto entre los equipos de la serie en ese mismo eje. Los ejes y sus
 * escalas son los del radar de siempre (`ClubRadar`); lo único nuevo es el
 * globo.
 */

type Eje = "Ataque" | "Posición esperada" | "Defensa" | "TSI en la liga";

interface Fila {
  htTeamId: number;
  nombre: string;
  valor: number;
  propio: boolean;
}

interface Porque {
  valor: number;
  puesto: number;
  frase: string;
  filas: Fila[];
}

const clamp = (v: number) => Math.max(0, Math.min(100, v));

/** Mismas 2.000 simulaciones que el resto del Dashboard: misma caché. */
const RUNS = 2_000;

/** Alto del gráfico. El centro del radar está a la mitad: con él se sabe de
 *  qué eje es la bolita que se toca. */
const ALTO = 300;

export function RadarConPorque({ teamName }: { teamName: string }) {
  const league = useLeague(RUNS);
  const comparison = useLeagueComparison(true, true);
  const caja = useRef<HTMLDivElement>(null);
  const [globo, setGlobo] = useState<{
    eje: Eje;
    x: number;
    y: number;
    ancho: number;
  } | null>(null);

  if (league.isLoading || comparison.isLoading) {
    return (
      <Panel title={tx("Radar de fuerza")}>
        <div className="p-4">
          <Loading />
        </div>
      </Panel>
    );
  }

  const data = league.data;
  const own = data?.ownOutlook;
  const n = comparison.data?.teamsInSeries ?? data?.standings.length ?? 0;
  if (!data || !own || n < 2) {
    return (
      <Panel title={tx("Radar de fuerza")}>
        <Empty>{tx("Todavía no hay clasificación de tu serie.")}</Empty>
      </Panel>
    );
  }

  const tabla = new Map(data.standings.map((s) => [s.htTeamId, s]));
  const media = data.leagueAvgGoals;
  const jornadas = data.roundsPlayed;
  const ordenar = (filas: Fila[]) =>
    [...filas].sort((a, b) => b.valor - a.valor);
  const puestoDe = (filas: Fila[]) => filas.findIndex((f) => f.propio) + 1;

  // ── Ataque ────────────────────────────────────────────────────────────
  const ataque = ordenar(
    data.outlook.map((o) => ({
      htTeamId: o.htTeamId,
      nombre: o.name,
      valor: clamp(o.attackStrength * 50),
      propio: o.isOwnTeam,
    })),
  );
  const mia = tabla.get(own.htTeamId);
  const porPartido = (goles: number, pj: number) => (pj > 0 ? goles / pj : 0);

  // ── Defensa ───────────────────────────────────────────────────────────
  const defensa = ordenar(
    data.outlook.map((o) => ({
      htTeamId: o.htTeamId,
      nombre: o.name,
      valor: clamp((2 - o.defenceStrength) * 50),
      propio: o.isOwnTeam,
    })),
  );

  // ── Posición esperada ─────────────────────────────────────────────────
  const posicion = ordenar(
    data.outlook.map((o) => ({
      htTeamId: o.htTeamId,
      nombre: o.name,
      valor: clamp((1 - (o.expectedPosition - 1) / (n - 1)) * 100),
      propio: o.isOwnTeam,
    })),
  );
  const masProbables = Object.entries(own.positionDistribution)
    .map(([p, prob]) => ({ p: Number(p), prob }))
    .filter((x) => x.prob >= 0.01)
    .sort((a, b) => b.prob - a.prob)
    .slice(0, 2)
    .map((x) =>
      tx("{{v0}}º en el {{v1}} %", { v0: x.p, v1: Math.round(x.prob * 100) }),
    );

  // ── TSI en la liga ────────────────────────────────────────────────────
  // El eje es el PUESTO en TSI, no el TSI: se deja así a propósito para ver
  // en el Dashboard cómo se lee. La frase sí da las cifras reales.
  const ranking = comparison.data?.ranking ?? [];
  const tsi: Fila[] = ranking.map((t) => ({
    htTeamId: t.teamHtId,
    nombre: t.teamName,
    valor: clamp((1 - (t.rank - 1) / (n - 1)) * 100),
    propio: t.isOwn,
  }));
  const miTsi = ranking.find((t) => t.isOwn);
  const hayTsi = miTsi != null && tsi.length > 0;
  const referencia =
    miTsi && miTsi.rank === 1
      ? ranking.find((t) => t.rank === 2)
      : ranking.find((t) => t.rank === 1);

  const porques: Record<Eje, Porque> = {
    Ataque: {
      valor: ataque.find((f) => f.propio)?.valor ?? 0,
      puesto: puestoDe(ataque),
      frase: mia
        ? tx(
            "Marcas {{v0}} goles por partido ({{v1}} en {{v2}}) y la media de {{v3}} es {{v4}}. Con {{v5}} jornadas todavía se tira hacia la media: queda en {{v6}} veces un equipo medio.",
            {
              v0: decimal(porPartido(mia.goalsFor, mia.played), 1),
              v1: mia.goalsFor,
              v2: mia.played,
              v3: data.seriesName ?? tx("la serie"),
              v4: decimal(media, 1),
              v5: jornadas,
              v6: decimal(own.attackStrength, 2),
            },
          )
        : "",
      filas: ataque,
    },
    Defensa: {
      valor: defensa.find((f) => f.propio)?.valor ?? 0,
      puesto: puestoDe(defensa),
      frase: mia
        ? tx(
            "Encajas {{v0}} por partido ({{v1}} en {{v2}}) frente a {{v3}} de media. Tirado hacia la media, {{v4}} veces lo que encaja un equipo medio.",
            {
              v0: decimal(porPartido(mia.goalsAgainst, mia.played), 1),
              v1: mia.goalsAgainst,
              v2: mia.played,
              v3: decimal(media, 1),
              v4: decimal(own.defenceStrength, 2),
            },
          )
        : "",
      filas: defensa,
    },
    "Posición esperada": {
      valor: posicion.find((f) => f.propio)?.valor ?? 0,
      puesto: puestoDe(posicion),
      frase:
        tx("En las simulaciones terminas de media {{v0}}º", {
          v0: decimal(own.expectedPosition, 2),
        }) + (masProbables.length ? `: ${masProbables.join(", ")}.` : "."),
      filas: posicion,
    },
    "TSI en la liga": {
      valor: tsi.find((f) => f.propio)?.valor ?? 0,
      puesto: miTsi?.rank ?? 0,
      frase: miTsi
        ? tx("Tus 11 mejores suman {{v0}}, ", { v0: number(miTsi.totalTsi) }) +
          (miTsi.rank === 1
            ? tx("el más alto de {{v0}}.", { v0: n })
            : tx("puesto {{v0}} de {{v1}}.", { v0: miTsi.rank, v1: n })) +
          (referencia
            ? tx(" El {{v0}}º, {{v1}}, suma {{v2}}.", {
                v0: referencia.rank,
                v1: referencia.teamName,
                v2: number(referencia.totalTsi),
              })
            : "")
        : "",
      filas: ordenar(tsi),
    },
  };

  const ejes: Eje[] = hayTsi
    ? ["Ataque", "Posición esperada", "Defensa", "TSI en la liga"]
    : ["Ataque", "Posición esperada", "Defensa"];

  // Los ejes se pintan traducidos, pero por dentro siguen siendo la clave en
  // español: el evento del radar devuelve el nombre pintado y hay que volver
  // de él a su eje.
  const ejeDeNombre = (nombre: string): Eje | undefined =>
    ejes.find((e) => tx(e) === nombre);

  const option = radarOption(
    ejes.map((e) => ({ name: tx(e), max: 100 })),
    [{ name: teamName, value: ejes.map((e) => porques[e].valor) }],
  );
  // El globo lo pinta React: el tooltip de ECharts habla de la serie entera y
  // se pisaría con este. Los nombres de los ejes emiten eventos para abrirlo.
  option.tooltip = { show: false };
  option.radar = {
    ...(option.radar as object),
    triggerEvent: true,
    axisName: { fontWeight: 500 },
  };

  const abrir = (params: unknown) => {
    const p = params as {
      componentType?: string;
      name?: string;
      event?: { offsetX: number; offsetY: number };
    };
    // Se mide aquí, en el evento, y no al pintar: leer el tamaño de la caja
    // durante el render no se vuelve a pintar cuando cambia.
    const ancho = caja.current?.clientWidth ?? 600;
    const x = Number.isFinite(p.event?.offsetX) ? p.event!.offsetX : 0;
    const y = Number.isFinite(p.event?.offsetY) ? p.event!.offsetY : 0;
    let nombre: Eje | undefined;
    if (p.componentType === "radar" && p.name) {
      nombre = ejeDeNombre(p.name);
    } else if (p.componentType === "series") {
      // LA BOLITA (2026-09-13, visto por el usuario): el punto de cada eje es
      // de la serie, y ECharts no dice de qué eje es. Se saca por el ángulo
      // desde el centro del radar: el primer eje va arriba y el resto sigue en
      // sentido antihorario, a partes iguales.
      const angulo =
        (Math.atan2(-(y - ALTO / 2), x - ancho / 2) * 180) / Math.PI;
      const paso = 360 / ejes.length;
      const desdeArriba = (((angulo - 90) % 360) + 360) % 360;
      nombre = ejes[Math.round(desdeArriba / paso) % ejes.length];
    }
    if (!nombre || !ejes.includes(nombre)) return;
    setGlobo({ eje: nombre, x, y, ancho });
  };

  const actual = globo ? porques[globo.eje] : null;

  return (
    <Panel
      title={tx("Radar de fuerza")}
      meta={tx("relativo a {{v0}}", { v0: data.seriesName ?? tx("tu liga") })}
    >
      <div ref={caja} className="relative" onMouseLeave={() => setGlobo(null)}>
        <Chart
          ariaLabel={tx(
            "Radar de fuerza del equipo, relativo a la media de la liga",
          )}
          height={ALTO}
          option={option}
          onEvents={{ mouseover: abrir, click: abrir }}
        />
        {globo && actual && (
          <div
            role="tooltip"
            className="pointer-events-none absolute z-10 w-80 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 text-sm shadow-lg"
            style={{
              left: Math.max(8, Math.min(globo.x + 12, globo.ancho - 328)),
              top: Math.max(8, Math.min(globo.y + 12, ALTO - 8)),
            }}
          >
            <div className="mb-1 flex items-baseline justify-between font-semibold">
              <span>
                {tx(globo.eje)} · {actual.puesto}
                {tx("º de")} {n}
              </span>
              <span className="tabular-nums">{Math.round(actual.valor)}</span>
            </div>
            <p className="mb-2 text-xs leading-5 text-[var(--muted)]">
              {actual.frase}
            </p>
            <ul className="space-y-0.5">
              {actual.filas.map((f) => (
                <li
                  key={f.htTeamId}
                  className={`grid grid-cols-[7.5rem_1fr_2rem] items-center gap-2 text-xs ${
                    f.propio ? "font-semibold" : "text-[var(--muted)]"
                  }`}
                >
                  <span className="truncate">{f.nombre}</span>
                  <span className="h-1.5 overflow-hidden rounded bg-[var(--surface-2)]">
                    <span
                      className="block h-full rounded"
                      style={{
                        width: `${f.valor}%`,
                        background: f.propio
                          ? "var(--accent)"
                          : "var(--border)",
                      }}
                    />
                  </span>
                  <span className="text-right tabular-nums">
                    {Math.round(f.valor)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
      <Note>
        {tx("50 es la media de")} {data.seriesName}
        {tx(
          ", 100 el mejor de la serie en ese eje. Pasa por el nombre de un eje para ver de dónde sale.",
        )}
      </Note>
    </Panel>
  );
}
