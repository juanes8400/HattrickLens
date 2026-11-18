/** Rentabilidad deportiva: HTMS a los 28 contra sueldo semanal, cortado en
 *  las medianas (2026-11-17; sustituye a Potencial, HTMS hoy × HTMS28). */
import { useNavigate } from "react-router-dom";
import { tx } from "../../i18n/tx";
import { number } from "../../hooks/useFormat";
import type { ClasesDeJugador } from "../../services/api";
import { COLOR, colocarEtiquetas, type Grupo } from "./colores";
import { ListaDeGrupos } from "./comun";

const W = 1000;
const H = 520;
const M = { izquierda: 76, derecha: 24, arriba: 16, abajo: 44 };

/** Un eje con margen y marcas redondas. */
function escala(min: number, max: number, paso: number) {
  const a = Math.floor(min / paso) * paso;
  const b = Math.ceil(max / paso) * paso;
  const marcas: number[] = [];
  for (let v = a; v <= b; v += paso) marcas.push(v);
  return { a, b, marcas };
}

/** Marcas «redondas» de un eje logarítmico: 1, 2 y 5 por cada potencia de
 *  diez que caiga dentro. */
function marcasLog(min: number, max: number): number[] {
  const marcas: number[] = [];
  for (
    let p = Math.floor(Math.log10(min));
    p <= Math.ceil(Math.log10(max));
    p++
  ) {
    for (const f of [1, 2, 5]) {
      const v = f * 10 ** p;
      if (v >= min && v <= max) marcas.push(v);
    }
  }
  return marcas;
}

/** «23 mil» en vez de «23.508»: en el eje sólo importa el orden de magnitud. */
function corto(v: number): string {
  return v >= 1000
    ? tx("{{v}} mil", { v: number(Math.round(v / 1000)) })
    : number(v);
}

export function Rentabilidad({ datos }: { datos: ClasesDeJugador }) {
  const navigate = useNavigate();
  const grupos: Grupo[] = [
    {
      clave: "estrellas",
      nombre: tx("Estrellas"),
      color: COLOR.azul,
      jugadores: [],
    },
    {
      clave: "gangas",
      nombre: tx("Gangas"),
      color: COLOR.verde,
      jugadores: [],
    },
    {
      clave: "caros",
      nombre: tx("Caros"),
      color: COLOR.rojo,
      jugadores: [],
    },
    {
      clave: "economicos",
      nombre: tx("Económicos"),
      color: COLOR.gris,
      jugadores: [],
    },
  ];
  const color = Object.fromEntries(grupos.map((g) => [g.clave, g.color]));
  for (const j of [...datos.players].sort((a, b) => b.salary - a.salary)) {
    grupos.find((g) => g.clave === j.rentabilidad)?.jugadores.push(j);
  }
  const m = datos.medians;
  if (!m || datos.players.length === 0) return null;
  const moneda = datos.currency;
  const dinero = (v: number) => `${number(v)} ${moneda}`.trim();

  // El HTMS28 negativo de un veterano aplastaría a todos los demás contra la
  // derecha, y un sueldo de cero no cabe en un eje logarítmico: los dos se
  // nombran debajo en vez de pintarlos.
  const dentro = datos.players.filter((j) => j.htms28 >= 0 && j.salary > 0);
  const fuera = datos.players.filter((j) => !(j.htms28 >= 0 && j.salary > 0));
  if (dentro.length === 0) return null;
  const ex = escala(
    Math.min(...dentro.map((j) => j.htms28), m.htms28),
    Math.max(...dentro.map((j) => j.htms28), m.htms28),
    200,
  );
  // EL SUELDO EN ESCALA LOGARÍTMICA. Va de unos cientos a decenas de miles:
  // en escala normal los jóvenes quedarían aplastados contra el suelo.
  const sMin = Math.min(...dentro.map((j) => j.salary), m.salary) * 0.8;
  const sMax = Math.max(...dentro.map((j) => j.salary), m.salary) * 1.25;
  const X = (v: number) =>
    M.izquierda +
    ((v - ex.a) / (ex.b - ex.a || 1)) * (W - M.izquierda - M.derecha);
  const Y = (v: number) =>
    H -
    M.abajo -
    ((Math.log10(v) - Math.log10(sMin)) /
      (Math.log10(sMax) - Math.log10(sMin) || 1)) *
      (H - M.arriba - M.abajo);

  const puntos = [...dentro]
    .sort((a, b) => b.salary - a.salary)
    .map((j) => ({ j, x: X(j.htms28), y: Y(j.salary), texto: j.shortName }));
  const etiquetas = colocarEtiquetas(puntos, {
    izquierda: M.izquierda,
    derecha: W - M.derecha,
  });
  const px = X(m.htms28);
  const py = Y(m.salary);
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
          "Lo que cobra cada jugador frente a lo que valdrá a los 28. Cortes en la mediana de la plantilla: HTMS28 {{f}} y un sueldo de {{s}} por semana. Quien cae justo en una mediana cuenta arriba.",
          { f: number(m.htms28), s: dinero(m.salary) },
        )}
      </p>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full"
        role="img"
        aria-label={tx(
          "HTMS a los 28 frente al sueldo semanal de cada jugador",
        )}
      >
        {/* Estrellas arriba a la derecha, Gangas abajo a la derecha, Caros
            arriba a la izquierda, Económicos abajo a la izquierda. */}
        <rect
          x={px}
          y={M.arriba}
          width={W - M.derecha - px}
          height={py - M.arriba}
          fill={COLOR.azul}
          opacity={0.06}
        />
        <rect
          x={px}
          y={py}
          width={W - M.derecha - px}
          height={H - M.abajo - py}
          fill={COLOR.verde}
          opacity={0.06}
        />
        <rect
          x={M.izquierda}
          y={M.arriba}
          width={px - M.izquierda}
          height={py - M.arriba}
          fill={COLOR.rojo}
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
        {marcasLog(sMin, sMax).map((v) => (
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
              {corto(v)}
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
          {tx("HTMS a los 28")}
        </text>
        <text
          x={14}
          y={(M.arriba + H - M.abajo) / 2}
          textAnchor="middle"
          fontSize={12}
          fill="var(--muted)"
          transform={`rotate(-90 14 ${(M.arriba + H - M.abajo) / 2})`}
        >
          {tx("Sueldo semanal ({{moneda}}, escala logarítmica)", {
            moneda,
          })}
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
        {esquina(tx("Estrellas"), "estrellas", px + 8, M.arriba + 16, "start")}
        {esquina(
          tx("Gangas"),
          "gangas",
          W - M.derecha - 8,
          H - M.abajo - 10,
          "end",
        )}
        {esquina(tx("Caros"), "caros", M.izquierda + 8, M.arriba + 16, "start")}
        {esquina(
          tx("Económicos"),
          "economicos",
          M.izquierda + 8,
          py + 18,
          "start",
        )}
        {/* Cada punto y su nombre llevan a la ficha (2026-11-18, pedido del
            usuario): el resto de la app enlaza todos los nombres. Es un <a> de
            SVG, que sí abre en otra pestaña con el botón central; el clic
            normal navega sin recargar, como un Link. */}
        {puntos.map((p, i) => (
          <a
            key={p.j.htPlayerId}
            href={`/players/${p.j.htPlayerId}`}
            className="group cursor-pointer"
            onClick={(e) => {
              if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey)
                return;
              e.preventDefault();
              navigate(`/players/${p.j.htPlayerId}`);
            }}
          >
            <circle
              cx={p.x}
              cy={p.y}
              r={7}
              fill={color[p.j.rentabilidad]}
              stroke="var(--surface)"
              strokeWidth={2}
            >
              <title>
                {`${p.j.name} · ${p.j.ageYears} · HTMS28 ${number(p.j.htms28)} · ${dinero(p.j.salary)}`}
              </title>
            </circle>
            <text
              x={etiquetas[i]?.x}
              y={etiquetas[i]?.y}
              textAnchor={etiquetas[i]?.anchor}
              fontSize={12}
              fill="var(--text)"
              className="underline decoration-[var(--border)] underline-offset-2 group-hover:fill-[var(--accent)]"
            >
              {p.texto}
            </text>
          </a>
        ))}
      </svg>
      {fuera.length > 0 && (
        <p className="text-xs text-[var(--muted)]">
          {tx("Fuera del gráfico, con HTMS28 negativo o sin sueldo: {{v}}.", {
            v: fuera
              .map(
                (j) =>
                  `${j.shortName} (HTMS28 ${number(j.htms28)}, ${dinero(j.salary)})`,
              )
              .join(" · "),
          })}
        </p>
      )}
      <ListaDeGrupos grupos={grupos} detalle={(j) => dinero(j.salary)} />
    </div>
  );
}
