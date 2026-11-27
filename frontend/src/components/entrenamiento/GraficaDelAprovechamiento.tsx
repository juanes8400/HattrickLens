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
 *  contra el borde (lo vio el usuario en la maqueta).
 *
 *  8.3.1 (2026-11-27, pedido del usuario): las bandas se oscurecen hacia
 *  arriba hasta casi negro, «para que se lea que arriba vale más», y como
 *  mucho hay tres puntos --el actual, el mejor y uno que se elige--, cada uno
 *  con su color y su nombre entero. Con más, los nombres largos se pisaban y
 *  los añadidos salían todos del mismo color. */
import { useId } from "react";
import type { AprovechamientoOpcion } from "../../services/api";
import { tx } from "../../i18n/tx";
import { percent } from "../../hooks/useFormat";

export const COLOR_ACTUAL = "#e8883a";
export const COLOR_MEJOR = "#8b5cf6";
/** El tercero, el que se elige para comparar. */
export const COLOR_ELEGIDO = "#0f9d8a";

/** Las diagonales: cada una vale el doble o algo más que la anterior. */
const NIVELES = [1, 0.5, 0.2, 0.1, 0.05, 0.02, 0.01];
/** El color de cada banda, de la más alta (casi negra: lo que más vale) a la
 *  más baja, y el fondo por debajo del 1 %. Fijos y no del tema: es una escala
 *  de valor, y se lee igual en claro y en oscuro. */
const BANDAS = [
  "#071224",
  "#132b57",
  "#2a4f8c",
  "#5578b5",
  "#8ba6d3",
  "#bfd0ea",
  "#e2e9f5",
];
const FONDO = "#f5f7fb";

const W = 360;
const H = 340;
const X0 = 36;
const X1 = W - 8;
const Y1 = 8;
const Y0 = H - 38;

export function GraficaDelAprovechamiento({
  opciones,
  activos,
  nombre,
  color,
}: {
  /** Todas: fijan los ejes, para que no salten al activar o quitar uno. */
  opciones: AprovechamientoOpcion[];
  activos: AprovechamientoOpcion[];
  /** El nombre que se escribe junto a cada punto. */
  nombre: (o: AprovechamientoOpcion) => string;
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
        ? // Primero la esquina izquierda: la diagonal va de derecha (rápido)
          // a izquierda, y en el otro orden el polígono se cruzaba y dejaba
          // clara la esquina de arriba a la derecha, la que más vale.
          [
            [X0 - 60, Y1 - 60],
            [X1 + 60, Y1 - 60],
          ]
        : [...recta(NIVELES[b - 1]!)].reverse();
    return {
      puntos: [...abajo, ...arriba].map((p) => p.join(",")).join(" "),
      fill: BANDAS[b]!,
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

  // Las etiquetas: el nombre entero y su %. Se prueban varios sitios --a la
  // derecha, a la izquierda, arriba y abajo, éstos dos metidos dentro del
  // recuadro-- y se queda el que menos pisa otros puntos, otras etiquetas y
  // el borde. Con tres puntos casi siempre hay uno limpio; si no, el menos malo.
  const puntos = activos
    .filter((o) => o.semanasPorNivel && o.aportePorCasilla > 0)
    .map((o) => ({
      o,
      cx: sx(o.semanasPorNivel as number),
      cy: sy(o.aportePorCasilla),
      r: radio(o),
    }));
  type Caja = [number, number, number, number];
  const cajas: Caja[] = [];
  const solape = (a: Caja, b: Caja) =>
    Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0])) *
    Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1]));
  const coste = (c: Caja) => {
    const fuera =
      Math.max(0, X0 - c[0]) +
      Math.max(0, c[2] - X1) +
      Math.max(0, Y1 - c[1]) +
      Math.max(0, c[3] - Y0);
    return (
      fuera * 1000 +
      cajas.reduce((s_, b) => s_ + solape(c, b) * 4, 0) +
      puntos.reduce(
        (s_, p) =>
          s_ + solape(c, [p.cx - p.r, p.cy - p.r, p.cx + p.r, p.cy + p.r]) * 4,
        0,
      )
    );
  };
  const dentro = (x: number, w: number) =>
    Math.min(Math.max(x, X0 + 2), X1 - w - 2);
  const etiquetas = [...puntos]
    .sort((a, b) => b.o.aprovechado - a.o.aprovechado)
    .map(({ o, cx, cy, r }) => {
      const texto = `${nombre(o)} ${percent(o.aprovechado * 100)}`;
      const w = texto.length * 5.7;
      const h = 12;
      const sitios: Caja[] = [
        [cx + r + 5, cy - h / 2],
        [cx - r - 5 - w, cy - h / 2],
        [dentro(cx - w / 2, w), cy - r - 4 - h],
        [dentro(cx - w / 2, w), cy + r + 4],
        [dentro(cx - w / 2, w), cy - r - 4 - 2 * h],
        [dentro(cx - w / 2, w), cy + r + 4 + h],
      ].map(([x, y]) => [x!, y!, x! + w, y! + h] as Caja);
      const mejor = sitios.reduce((a, b) => (coste(b) < coste(a) ? b : a));
      cajas.push(mejor);
      return { o, x: mejor[0], y: mejor[3] - 2.5, texto };
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
        <rect x={X0} y={Y1} width={X1 - X0} height={Y0 - Y1} fill={FONDO} />
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
              stroke="#fff"
              strokeOpacity={0.5}
              strokeWidth={1}
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
          fill={r.b < 4 ? "#fff" : "#123f7a"}
        >
          {percent(r.c * 100, 0)}
        </text>
      ))}
      <text
        x={sx(tDiag)}
        y={sy(cDiag * tDiag) - 5}
        fontSize={9.5}
        fontStyle="italic"
        fill="#123f7a"
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
            stroke="#fff"
            strokeWidth={1.5}
          >
            <title>{`${o.name}: ${percent(o.aprovechado * 100)}`}</title>
          </circle>
        ))}
      {etiquetas.map(({ o, x, y, texto }) => (
        <text
          key={o.trainingType}
          x={x}
          y={y}
          fontSize={10}
          fontWeight={650}
          fill="#1f1e1c"
          paintOrder="stroke"
          stroke="#fff"
          strokeWidth={3.2}
        >
          {texto}
        </text>
      ))}
    </svg>
  );
}

/** El tamaño del punto: las casillas que entrenan, sobre el total. */
function radio(o: AprovechamientoOpcion) {
  const ocupacion = o.casillas > 0 ? o.casillasQueEntrenan / o.casillas : 0;
  return 4 + 8 * Math.sqrt(Math.min(1, ocupacion));
}
