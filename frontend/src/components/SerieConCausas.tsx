import { useId, useState } from "react";
import { number } from "../hooks/useFormat";

/**
 * Una serie temporal donde cada tramo dice a qué obedece.
 *
 * La usan las tres pestañas de Club: Espíritu y Confianza en Psicología, y
 * el histórico de socios. Comparten gramática a propósito —la línea, la banda
 * de sucesos encima, la referencia punteada— porque son la misma pregunta
 * hecha sobre tres cosas distintas: qué se movió y por qué.
 *
 * Dos decisiones que se notan al leerla:
 *
 * 1. **El movimiento es el TRAMO, no el punto.** El color y el motivo van
 *    sobre la pendiente entre dos lecturas. Marcarlo en el punto de llegada
 *    sugiere que el cambio ocurrió ahí, y una lectura sólo dice dónde estaba
 *    el valor cuando se sincronizó.
 * 2. **La escala sale entera.** Se ven los once niveles de Espíritu aunque el
 *    equipo sólo haya pisado cinco: recortar el eje a lo observado hace
 *    parecer que el mínimo visto es un suelo del juego, y no lo es.
 */

export type Lectura = { at: string; level: number };
export type Movimiento = {
  at: string;
  from: number;
  to: number;
  delta: number;
  cause: string;
  buys?: number;
  sales?: number;
};
export type Peldano = { level: number; label: string };

/** Un suceso de la banda superior: un partido, con su color y su etiqueta. */
export type Suceso = {
  at: string;
  chip: string | null;
  color: string;
  detail: string;
};

/** Un día con operaciones de mercado, para el pulso de abajo. */
export type Dia = { day: string; count: number };

// Los tokens de la app, no colores fijos: se redefinen por tema y por eso
// mantienen el contraste en los dos. Los fijos que había aquí medían 2,89
// sobre fondo oscuro --por debajo del mínimo de 3:1-- (2026-08-31).
const VERDE = "var(--positive)";
const ROJO = "var(--danger)";

function ejeSemanal(desde: Date, hasta: Date): Date[] {
  const out: Date[] = [];
  for (let d = new Date(desde); d < hasta; d.setDate(d.getDate() + 1)) {
    if (d.getDay() === 0) out.push(new Date(d));
  }
  return out;
}

export function SerieConCausas({
  readings,
  movements,
  scale,
  equilibrium,
  equilibriumLabel,
  events,
  eventsLabel,
  buyDays,
  sellDays,
  color = "var(--accent)",
  height = 180,
  from,
  to,
  ariaLabel,
}: {
  readings: Lectura[];
  movements: Movimiento[];
  /** Ordinal con nombre (Espíritu, Confianza) o `null` para escala numérica. */
  scale: Peldano[] | null;
  equilibrium?: number | null;
  equilibriumLabel?: string;
  events: Suceso[];
  eventsLabel: string;
  buyDays?: Dia[];
  sellDays?: Dia[];
  color?: string;
  height?: number;
  from: string;
  to: string;
  /** Qué cuenta la gráfica, para quien no la ve. */
  ariaLabel: string;
}) {
  const [tip, setTip] = useState<{ x: number; y: number; html: string } | null>(
    null,
  );
  const uid = useId().replace(/:/g, "");

  if (readings.length < 2) return null;

  const hayMercado = (buyDays?.length ?? 0) + (sellDays?.length ?? 0) > 0;
  const W = 720;
  const L = scale ? 108 : 66;
  const R = 14;
  const T = 32;
  const B = hayMercado ? 54 : 26;
  const alto = height;
  const H = T + alto + B;

  const d0 = new Date(from).getTime();
  const d1 = new Date(to).getTime();
  const X = (iso: string) =>
    L + ((new Date(iso).getTime() - d0) / (d1 - d0)) * (W - L - R);

  const niveles = scale ? scale.map((p) => p.level) : [];
  const max = scale
    ? Math.max(...niveles)
    : Math.max(...readings.map((r) => r.level));
  const min = scale
    ? Math.min(...niveles)
    : Math.min(...readings.map((r) => r.level));
  const Y = (v: number) => T + ((max - v) / (max - min || 1)) * alto;

  const vistos = new Set(readings.map((r) => r.level));
  const porFecha = new Map(movements.map((m) => [m.at, m]));

  return (
    <div className="relative">
      {/* `role="img"` con su etiqueta: sin esto la gráfica es invisible para
          un lector de pantalla, y en Psicología es el contenido principal de
          la pantalla, no un adorno. El resumen se arma con los datos reales
          --dónde empieza, dónde acaba, cuántas lecturas-- para que diga algo
          aunque no se pueda mirar. */}
      <svg
        role="img"
        aria-label={`${ariaLabel}. ${resumenHablado(readings, scale)}`}
        viewBox={`0 0 ${W} ${H}`}
        className="block h-auto w-full overflow-visible"
      >
        {/* Rejilla. En la ordinal sale TODA la escala; el nivel nunca pisado
            va en fantasma, para que se vea cuánto recorrido queda. */}
        {(scale ?? []).map((p) => {
          const hay = vistos.has(p.level) || p.level === equilibrium;
          return (
            <g key={p.level}>
              <line
                x1={L}
                y1={Y(p.level)}
                x2={W - R}
                y2={Y(p.level)}
                stroke="var(--border)"
                opacity={hay ? 1 : 0.4}
              />
              <text
                x={L - 9}
                y={Y(p.level) + 3.2}
                textAnchor="end"
                fontSize="9.5"
                fill={hay ? "var(--muted)" : "var(--border)"}
              >
                {p.label}
              </text>
            </g>
          );
        })}
        {!scale &&
          [0, 0.5, 1].map((f) => {
            const v = min + (max - min) * f;
            return (
              <g key={f}>
                <line
                  x1={L}
                  y1={Y(v)}
                  x2={W - R}
                  y2={Y(v)}
                  stroke="var(--border)"
                />
                <text
                  x={L - 9}
                  y={Y(v) + 3.2}
                  textAnchor="end"
                  fontSize="9.5"
                  fill="var(--muted)"
                >
                  {number(v)}
                </text>
              </g>
            );
          })}

        {/* El área hasta la referencia: la distancia acumulada es la historia,
            no cada punto por separado. */}
        {equilibrium != null && (
          <>
            <polygon
              fill={color}
              opacity={0.1}
              points={
                `${X(readings[0]!.at)},${Y(equilibrium)} ` +
                readings.map((r) => `${X(r.at)},${Y(r.level)}`).join(" ") +
                ` ${X(readings[readings.length - 1]!.at)},${Y(equilibrium)}`
              }
            />
            <line
              x1={L}
              y1={Y(equilibrium)}
              x2={W - R}
              y2={Y(equilibrium)}
              stroke="var(--warning)"
              strokeWidth={1.4}
              strokeDasharray="5 3"
            />
            {equilibriumLabel && (
              <text
                x={W - R}
                y={Y(equilibrium) + 13}
                textAnchor="end"
                fontSize="9"
                fill="var(--warning)"
              >
                {equilibriumLabel}
              </text>
            )}
          </>
        )}

        {/* Banda de sucesos: tallo y punto, sin cajas encima del lienzo. */}
        <text
          x={L - 9}
          y={T - 12}
          textAnchor="end"
          fontSize="9"
          fill="var(--muted)"
        >
          {eventsLabel}
        </text>
        {events.map((s, i) => (
          <g key={`${uid}e${i}`}>
            <line
              x1={X(s.at)}
              y1={T}
              x2={X(s.at)}
              y2={T + alto}
              stroke={s.color}
              strokeWidth={1}
              opacity={0.2}
            />
            <line
              x1={X(s.at)}
              y1={T - 13}
              x2={X(s.at)}
              y2={T - 4}
              stroke={s.color}
              strokeWidth={1.5}
            />
            <circle
              cx={X(s.at)}
              cy={T - 16}
              r={5}
              fill={s.color}
              className="cursor-pointer"
              onMouseEnter={(e) =>
                setTip({ x: e.clientX, y: e.clientY, html: s.detail })
              }
              onMouseLeave={() => setTip(null)}
            />
          </g>
        ))}

        {/* Los tramos. Cada uno lleva su motivo. */}
        {readings.slice(1).map((b, i) => {
          const a = readings[i]!;
          const mv = porFecha.get(b.at);
          const col =
            b.level > a.level
              ? VERDE
              : b.level < a.level
                ? ROJO
                : "var(--muted)";
          const pts = `${X(a.at)},${Y(a.level)} ${X(b.at)},${Y(b.level)}`;
          return (
            <g key={`${uid}t${i}`}>
              <polyline
                points={pts}
                fill="none"
                stroke={col}
                strokeWidth={2.6}
                strokeLinecap="round"
              />
              {mv && (
                <polyline
                  points={pts}
                  fill="none"
                  stroke="transparent"
                  strokeWidth={15}
                  className="cursor-pointer"
                  onMouseEnter={(e) =>
                    setTip({
                      x: e.clientX,
                      y: e.clientY,
                      html:
                        `<b>${etiqueta(scale, a.level)} → ${etiqueta(scale, b.level)}</b> ` +
                        `<span style="color:var(--muted)">(${mv.delta > 0 ? "+" : ""}${mv.delta})</span><br>${mv.cause}` +
                        (mv.buys || mv.sales
                          ? `<span style="display:block;margin-top:4px;padding-top:4px;border-top:1px solid var(--border);color:var(--muted)">En el tramo: ${mv.sales ?? 0} ventas, ${mv.buys ?? 0} compras. No se les atribuye la caída.</span>`
                          : ""),
                    })
                  }
                  onMouseLeave={() => setTip(null)}
                />
              )}
            </g>
          );
        })}
        {readings.map((r, i) => (
          <circle
            key={`${uid}p${i}`}
            cx={X(r.at)}
            cy={Y(r.level)}
            r={2.6}
            fill="var(--surface)"
            stroke="var(--text)"
            strokeWidth={1.3}
          />
        ))}

        {/* El pulso del mercado: una cápsula por operación, apiladas por día. */}
        {hayMercado && (
          <>
            <line
              x1={L}
              y1={T + alto + 24}
              x2={W - R}
              y2={T + alto + 24}
              stroke="var(--border)"
            />
            <text
              x={L - 9}
              y={T + alto + 20}
              textAnchor="end"
              fontSize="9"
              fill="var(--muted)"
            >
              ventas
            </text>
            <text
              x={L - 9}
              y={T + alto + 37}
              textAnchor="end"
              fontSize="9"
              fill="var(--muted)"
            >
              compras
            </text>
            {(sellDays ?? []).flatMap((d) =>
              Array.from({ length: d.count }, (_, j) => (
                <rect
                  key={`${uid}v${d.day}${j}`}
                  x={X(`${d.day}T12:00`) - 2.5}
                  y={T + alto + 18 - j * 7}
                  width={5}
                  height={5}
                  rx={2.5}
                  fill="var(--mercado-venta)"
                  opacity={0.9}
                />
              )),
            )}
            {(buyDays ?? []).flatMap((d) =>
              Array.from({ length: d.count }, (_, j) => (
                <rect
                  key={`${uid}c${d.day}${j}`}
                  x={X(`${d.day}T12:00`) - 2.5}
                  y={T + alto + 26 + j * 7}
                  width={5}
                  height={5}
                  rx={2.5}
                  fill="var(--mercado-compra)"
                  opacity={0.9}
                />
              )),
            )}
          </>
        )}

        {ejeSemanal(new Date(from), new Date(to)).map((d, i) => (
          <text
            key={`${uid}x${i}`}
            x={X(d.toISOString())}
            y={H - 4}
            textAnchor="middle"
            fontSize="8.5"
            fill="var(--muted)"
          >
            {d.getDate()}/{d.getMonth() + 1}
          </text>
        ))}
      </svg>

      {tip && (
        <div
          className="pointer-events-none fixed z-50 max-w-[250px] rounded-md border border-[var(--border)] bg-[var(--surface)] px-2.5 py-2 text-[11px] leading-snug shadow-lg"
          style={{ left: tip.x + 12, top: tip.y - 10 }}
          dangerouslySetInnerHTML={{ __html: tip.html }}
        />
      )}
    </div>
  );
}

/** La gráfica dicha en una frase, con sus números de verdad. */
function resumenHablado(readings: Lectura[], scale: Peldano[] | null): string {
  const primera = readings[0];
  const ultima = readings[readings.length - 1];
  if (!primera || !ultima) return "sin lecturas";
  const niveles = readings.map((r) => r.level);
  return (
    `${readings.length} lecturas. Empieza en ${etiqueta(scale, primera.level)} ` +
    `y termina en ${etiqueta(scale, ultima.level)}. ` +
    `Mínimo ${etiqueta(scale, Math.min(...niveles))}, ` +
    `máximo ${etiqueta(scale, Math.max(...niveles))}.`
  );
}

function etiqueta(scale: Peldano[] | null, level: number): string {
  if (!scale) return number(level);
  return scale.find((p) => p.level === level)?.label ?? String(level);
}
