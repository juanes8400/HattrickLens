/** La gráfica del A posteriori (8.3.0, 2026-11-26): log-log, un punto por
 *  entrenamiento.
 *
 *  - Altura: aporte por casilla (Σ m·w·ΔHTMS ÷ casillas · 2 · G_ideal).
 *  - Al lado: semanas por nivel, la T media; lo rápido a la derecha.
 *  - Con los dos ejes en logaritmo, altura ÷ T es el aprovechamiento, y cada
 *    % del ideal queda en una DIAGONAL, todas paralelas. El usuario eligió esta
 *    forma frente a la lineal y a las de un solo eje logarítmico.
 *
 *  SVG a mano y no ECharts: las bandas entre diagonales no son una serie que
 *  ECharts sepa pintar en ejes logarítmicos. Lo que se sale del recuadro lo
 *  corta el `clipPath`; recortar los valores a mano aplastaba las diagonales
 *  contra el borde (lo vio el usuario en la maqueta). */
import { useId } from "react";
import type { AprovechamientoOpcion } from "../../services/api";
import { tx } from "../../i18n/tx";
import { percent } from "../../hooks/useFormat";

export const COLOR_ACTUAL = "#e8883a";
export const COLOR_MEJOR = "#8b5cf6";
export const COLOR_OTRO = "var(--text)";

/** Las diagonales: cada una vale el doble o algo más que la anterior. */
const NIVELES = [1, 0.5, 0.2, 0.1, 0.05, 0.02, 0.01];
/** Cuánto acento lleva cada banda, de la más alta a la más baja. */
const TINTA = [78, 58, 42, 28, 17, 9, 4];

const W = 360;
const H = 340;
const X0 = 36;
const X1 = W - 8;
const Y1 = 8;
const Y0 = H - 38;

export function GraficaDelAprovechamiento({
  opciones,
  activos,
  rango,
  color,
}: {
  /** Todas: fijan los ejes, para que no salten al activar o quitar uno. */
  opciones: AprovechamientoOpcion[];
  activos: AprovechamientoOpcion[];
  /** El número de cada activo en la mini tabla. */
  rango: Map<number, number>;
  color: (o: AprovechamientoOpcion) => string;
}) {
  const id = useId().replace(/:/g, "");
  const conPunto = opciones.filter(
    (o) => o.semanasPorNivel && o.aportePorCasilla > 0,
  );
  const ts = conPunto.map((o) => o.semanasPorNivel as number);
  const ys = conPunto.map((o) => o.aportePorCasilla);
  const tMin = Math.min(3, ...ts.map((t) => t / 1.3));
  const tMax = Math.max(30, ...ts.map((t) => t * 1.3));
  const yMin = Math.min(0.3, ...ys.map((y) => y / 1.6));
  const yMax = Math.max(6, ...ys.map((y) => y * 1.8));
  const L = Math.log10;
  const sx = (t: number) =>
    X1 - ((L(t) - L(tMin)) / (L(tMax) - L(tMin))) * (X1 - X0);
  const sy = (v: number) =>
    Y0 - ((L(v) - L(yMin)) / (L(yMax) - L(yMin))) * (Y0 - Y1);
  const recta = (c: number) =>
    [
      [sx(tMin), sy(c * tMin)],
      [sx(tMax), sy(c * tMax)],
    ] as const;

  const bandas = NIVELES.map((lo, b) => {
    const abajo = recta(lo);
    const arriba =
      b === 0
        ? [
            [X1 + 60, Y1 - 60],
            [X0 - 60, Y1 - 60],
          ]
        : [...recta(NIVELES[b - 1]!)].reverse();
    return {
      puntos: [...abajo, ...arriba].map((p) => p.join(",")).join(" "),
      fill: `color-mix(in srgb, var(--accent) ${TINTA[b]}%, var(--surface))`,
    };
  });

  // Rótulo de cada diagonal: arriba, donde entra, o en el borde izquierdo.
  const rotulos = NIVELES.flatMap((c, b) => {
    const tArriba = yMax / c;
    if (tArriba <= tMax && tArriba >= tMin) {
      const x = sx(tArriba) - 14;
      return x > X0 + 18 ? [{ x, y: Y1 + 11, c, b }] : [];
    }
    const y = sy(c * tMax) + 3;
    return y < Y0 - 4 && y > Y1 + 8 ? [{ x: X0 + 18, y, c, b }] : [];
  });

  const ang =
    (Math.atan2(sy(0.05 * tMin) - sy(0.05 * tMax), sx(tMin) - sx(tMax)) * 180) /
    Math.PI;
  const cDiag = 0.03;
  const tDiag = Math.sqrt(tMin * tMax) * 1.6;

  const marcasX = [3, 4, 5, 7, 10, 15, 20, 30, 50].filter(
    (t) => t >= tMin && t <= tMax,
  );
  const marcasY = [0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20].filter(
    (v) => v >= yMin && v <= yMax,
  );

  // Las etiquetas: el número de la mini tabla y su %. A la derecha del punto,
  // salvo junto al borde, y bajando si pisan a otra.
  const usadas: [number, number, number][] = [];
  const etiquetas = [...activos]
    .filter((o) => o.semanasPorNivel && o.aportePorCasilla > 0)
    .sort((a, b) => sy(a.aportePorCasilla) - sy(b.aportePorCasilla))
    .map((o) => {
      const cx = sx(o.semanasPorNivel as number);
      const cy = sy(o.aportePorCasilla);
      const r = radio(o);
      const izq = cx > X1 - 70;
      const lx = cx + (izq ? -(r + 4) : r + 4);
      const texto = `${rango.get(o.trainingType) ?? ""} · ${percent(o.aprovechado * 100)}`;
      const ancho = texto.length * 5.6;
      let ly = cy + 3.5;
      for (let k = 0; k < 8; k++) {
        const [a1, a2] = izq ? [lx - ancho, lx] : [lx, lx + ancho];
        if (
          !usadas.some(
            ([u1, u2, uy]) => Math.abs(uy - ly) < 11 && a1 < u2 && a2 > u1,
          )
        )
          break;
        ly += 11;
      }
      usadas.push(izq ? [lx - ancho, lx, ly] : [lx, lx + ancho, ly]);
      return { o, cx, cy, lx, ly, izq, texto };
    });

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="h-auto w-full max-w-[480px]"
      role="img"
      aria-label={tx(
        "Aprovechamiento de cada entrenamiento: aporte por casilla contra semanas por nivel, en escala logarítmica",
      )}
    >
      <defs>
        <clipPath id={`recuadro-${id}`}>
          <rect x={X0} y={Y1} width={X1 - X0} height={Y0 - Y1} />
        </clipPath>
      </defs>
      <g clipPath={`url(#recuadro-${id})`}>
        <rect
          x={X0}
          y={Y1}
          width={X1 - X0}
          height={Y0 - Y1}
          fill="var(--surface)"
        />
        {bandas.map((b, i) => (
          <polygon key={i} points={b.puntos} fill={b.fill} />
        ))}
        {NIVELES.map((c) => {
          const [[x1, y1], [x2, y2]] = recta(c);
          return (
            <line
              key={c}
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              stroke="var(--surface)"
              strokeWidth={1.2}
            />
          );
        })}
      </g>
      {rotulos.map((r) => (
        <text
          key={r.c}
          x={r.x}
          y={r.y}
          textAnchor="middle"
          fontSize={9}
          fontWeight={600}
          fill={r.b < 3 ? "#fff" : "var(--text)"}
        >
          {percent(r.c * 100, 0)}
        </text>
      ))}
      <text
        x={sx(tDiag)}
        y={sy(cDiag * tDiag) - 5}
        fontSize={9.5}
        fontStyle="italic"
        fill="var(--text)"
        transform={`rotate(${ang} ${sx(tDiag)} ${sy(cDiag * tDiag) - 5})`}
      >
        {tx("misma diagonal = mismo % del ideal")}
      </text>
      {marcasX.map((t) => (
        <g key={t}>
          <line
            x1={sx(t)}
            x2={sx(t)}
            y1={Y0}
            y2={Y0 + 4}
            stroke="var(--muted)"
          />
          <text
            x={sx(t)}
            y={Y0 + 15}
            textAnchor="middle"
            fontSize={10}
            fill="var(--muted)"
          >
            {t}
          </text>
        </g>
      ))}
      <text
        x={(X0 + X1) / 2}
        y={H - 6}
        textAnchor="middle"
        fontSize={10.5}
        fill="var(--muted)"
      >
        {tx("← más lento · semanas por nivel (media) · más rápido →")}
      </text>
      {marcasY.map((v) => (
        <text
          key={v}
          x={X0 - 5}
          y={sy(v) + 3.5}
          textAnchor="end"
          fontSize={10}
          fill="var(--muted)"
        >
          {v}
        </text>
      ))}
      <text
        transform={`translate(10,${(Y0 + Y1) / 2}) rotate(-90)`}
        textAnchor="middle"
        fontSize={10.5}
        fill="var(--muted)"
      >
        {tx("aporte por casilla →")}
      </text>
      {[...activos]
        .filter((o) => o.semanasPorNivel && o.aportePorCasilla > 0)
        .map((o) => (
          <circle
            key={o.trainingType}
            cx={sx(o.semanasPorNivel as number)}
            cy={sy(o.aportePorCasilla)}
            r={radio(o)}
            fill={color(o)}
            stroke="var(--surface)"
            strokeWidth={1.5}
          >
            <title>{`${o.name}: ${percent(o.aprovechado * 100)}`}</title>
          </circle>
        ))}
      {etiquetas.map(({ o, cx, cy, lx, ly, izq, texto }) => (
        <g key={o.trainingType}>
          {Math.abs(ly - (cy + 3.5)) > 2 && (
            <line
              x1={cx}
              y1={cy}
              x2={lx + (izq ? 2 : -2)}
              y2={ly - 3}
              stroke="var(--text)"
              strokeOpacity={0.35}
              strokeWidth={0.7}
            />
          )}
          <text
            x={lx}
            y={ly}
            textAnchor={izq ? "end" : "start"}
            fontSize={10}
            fontWeight={600}
            fill="var(--text)"
            paintOrder="stroke"
            stroke="var(--surface)"
            strokeWidth={3}
          >
            {texto}
          </text>
        </g>
      ))}
    </svg>
  );
}

/** El tamaño del punto: las casillas que entrenan, sobre el total. */
function radio(o: AprovechamientoOpcion) {
  const ocupacion = o.casillas > 0 ? o.casillasQueEntrenan / o.casillas : 0;
  return 4 + 8 * Math.sqrt(Math.min(1, ocupacion));
}
