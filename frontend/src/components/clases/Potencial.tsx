/** Potencial: HTMS de hoy contra HTMS a los 28, cortado en las medianas. */
import { tx } from "../../i18n/tx";
import { number } from "../../hooks/useFormat";
import type { ClasesDeJugador } from "../../services/api";
import { COLOR, colocarEtiquetas, type Grupo } from "./colores";
import { ListaDeGrupos } from "./comun";

const W = 1000;
const H = 520;
const M = { izquierda: 64, derecha: 24, arriba: 16, abajo: 44 };

/** Un eje con margen y marcas redondas. */
function escala(min: number, max: number, paso: number) {
  const a = Math.floor(min / paso) * paso;
  const b = Math.ceil(max / paso) * paso;
  const marcas: number[] = [];
  for (let v = a; v <= b; v += paso) marcas.push(v);
  return { a, b, marcas };
}

export function Potencial({ datos }: { datos: ClasesDeJugador }) {
  const grupos: Grupo[] = [
    {
      clave: "consolidados",
      nombre: tx("Consolidados"),
      color: COLOR.azul,
      jugadores: [],
    },
    {
      clave: "veteranos",
      nombre: tx("Veteranos"),
      color: COLOR.naranja,
      jugadores: [],
    },
    {
      clave: "promesas",
      nombre: tx("Promesas"),
      color: COLOR.verde,
      jugadores: [],
    },
    {
      clave: "relleno",
      nombre: tx("Relleno"),
      color: COLOR.gris,
      jugadores: [],
    },
  ];
  const color = Object.fromEntries(grupos.map((g) => [g.clave, g.color]));
  for (const j of [...datos.players].sort((a, b) => b.htms - a.htms)) {
    grupos.find((g) => g.clave === j.potencial)?.jugadores.push(j);
  }
  const m = datos.medians;
  if (!m || datos.players.length === 0) return null;

  // El HTMS28 negativo de un veterano aplastaría a todos los demás contra el
  // techo: se nombra debajo en vez de pintarlo.
  const dentro = datos.players.filter((j) => j.htms28 >= 0);
  const fuera = datos.players.filter((j) => j.htms28 < 0);
  const ex = escala(
    Math.min(...dentro.map((j) => j.htms), m.htms),
    Math.max(...dentro.map((j) => j.htms), m.htms),
    250,
  );
  const ey = escala(
    Math.min(...dentro.map((j) => j.htms28), m.htms28),
    Math.max(...dentro.map((j) => j.htms28), m.htms28),
    100,
  );
  const X = (v: number) =>
    M.izquierda +
    ((v - ex.a) / (ex.b - ex.a || 1)) * (W - M.izquierda - M.derecha);
  const Y = (v: number) =>
    H - M.abajo - ((v - ey.a) / (ey.b - ey.a || 1)) * (H - M.arriba - M.abajo);

  const puntos = [...dentro]
    .sort((a, b) => b.htms - a.htms)
    .map((j) => ({ j, x: X(j.htms), y: Y(j.htms28), texto: j.shortName }));
  const etiquetas = colocarEtiquetas(puntos, {
    izquierda: M.izquierda,
    derecha: W - M.derecha,
  });
  const px = X(m.htms);
  const py = Y(m.htms28);
  const esquina = (
    texto: string,
    clave: string,
    x: number,
    y: number,
    anchor: "start" | "end",
  ) => (
    <text
      x={x}
      y={y}
      textAnchor={anchor}
      fontSize={13}
      fontWeight={600}
      fill={color[clave]}
    >
      {texto}
    </text>
  );

  return (
    <div className="space-y-4">
      <p className="text-sm text-[var(--muted)]">
        {tx(
          "Cortes en la mediana de la plantilla: HTMS {{h}} y HTMS28 {{f}}. Quien cae justo en la mediana cuenta arriba.",
          { h: number(m.htms), f: number(m.htms28) },
        )}
      </p>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full"
        role="img"
        aria-label={tx("HTMS de hoy frente a HTMS a los 28 de cada jugador")}
      >
        <rect
          x={px}
          y={M.arriba}
          width={W - M.derecha - px}
          height={py - M.arriba}
          fill={COLOR.azul}
          opacity={0.06}
        />
        <rect
          x={M.izquierda}
          y={M.arriba}
          width={px - M.izquierda}
          height={py - M.arriba}
          fill={COLOR.verde}
          opacity={0.06}
        />
        <rect
          x={px}
          y={py}
          width={W - M.derecha - px}
          height={H - M.abajo - py}
          fill={COLOR.naranja}
          opacity={0.06}
        />
        <rect
          x={M.izquierda}
          y={py}
          width={px - M.izquierda}
          height={H - M.abajo - py}
          fill={COLOR.gris}
          opacity={0.06}
        />
        {ex.marcas.map((v) => (
          <g key={`x${v}`}>
            <line
              x1={X(v)}
              x2={X(v)}
              y1={M.arriba}
              y2={H - M.abajo}
              stroke="var(--border)"
            />
            <text
              x={X(v)}
              y={H - M.abajo + 18}
              textAnchor="middle"
              fontSize={11}
              fill="var(--muted)"
            >
              {number(v)}
            </text>
          </g>
        ))}
        {ey.marcas.map((v) => (
          <g key={`y${v}`}>
            <line
              x1={M.izquierda}
              x2={W - M.derecha}
              y1={Y(v)}
              y2={Y(v)}
              stroke="var(--border)"
            />
            <text
              x={M.izquierda - 8}
              y={Y(v) + 4}
              textAnchor="end"
              fontSize={11}
              fill="var(--muted)"
            >
              {number(v)}
            </text>
          </g>
        ))}
        <text
          x={(M.izquierda + W - M.derecha) / 2}
          y={H - 6}
          textAnchor="middle"
          fontSize={12}
          fill="var(--muted)"
        >
          {tx("HTMS hoy")}
        </text>
        <text
          x={14}
          y={(M.arriba + H - M.abajo) / 2}
          textAnchor="middle"
          fontSize={12}
          fill="var(--muted)"
          transform={`rotate(-90 14 ${(M.arriba + H - M.abajo) / 2})`}
        >
          {tx("HTMS a los 28")}
        </text>
        <line
          x1={px}
          x2={px}
          y1={M.arriba}
          y2={H - M.abajo}
          stroke="var(--muted)"
          strokeDasharray="5 4"
        />
        <line
          x1={M.izquierda}
          x2={W - M.derecha}
          y1={py}
          y2={py}
          stroke="var(--muted)"
          strokeDasharray="5 4"
        />
        {esquina(
          tx("Consolidados"),
          "consolidados",
          W - M.derecha - 8,
          M.arriba + 16,
          "end",
        )}
        {esquina(
          tx("Promesas"),
          "promesas",
          M.izquierda + 8,
          M.arriba + 16,
          "start",
        )}
        {esquina(
          tx("Veteranos"),
          "veteranos",
          W - M.derecha - 8,
          H - M.abajo - 10,
          "end",
        )}
        {esquina(
          tx("Relleno"),
          "relleno",
          M.izquierda + 8,
          H - M.abajo - 10,
          "start",
        )}
        {puntos.map((p, i) => (
          <g key={p.j.htPlayerId}>
            <circle
              cx={p.x}
              cy={p.y}
              r={7}
              fill={color[p.j.potencial]}
              stroke="var(--surface)"
              strokeWidth={2}
            >
              <title>
                {`${p.j.name} · ${p.j.ageYears} · HTMS ${number(p.j.htms)} · HTMS28 ${number(p.j.htms28)}`}
              </title>
            </circle>
            <text
              x={etiquetas[i]?.x}
              y={etiquetas[i]?.y}
              textAnchor={etiquetas[i]?.anchor}
              fontSize={12}
              fill="var(--text)"
            >
              {p.texto}
            </text>
          </g>
        ))}
      </svg>
      {fuera.length > 0 && (
        <p className="text-xs text-[var(--muted)]">
          {tx("Fuera del gráfico, con HTMS28 negativo: {{v}}.", {
            v: fuera
              .map(
                (j) =>
                  `${j.shortName} (HTMS ${number(j.htms)}, HTMS28 ${number(j.htms28)})`,
              )
              .join(" · "),
          })}
        </p>
      )}
      <ListaDeGrupos grupos={grupos} />
    </div>
  );
}
