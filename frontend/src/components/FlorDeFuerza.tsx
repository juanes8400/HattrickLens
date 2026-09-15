import { useState } from "react";
import { Empty, Loading, Panel } from "./Panels";
import {
  useLeague,
  useLeagueComparison,
  useSectoresRecientes,
} from "../hooks/useTeam";
import { decimal, number } from "../hooks/useFormat";

/**
 * La flor de fuerza del Dashboard (2026-09-13, sustituye al radar).
 *
 * Ocho pétalos, y cada uno es, por definición del usuario,
 *
 *     (X − mínimo de la serie) / (máximo − mínimo) × 100
 *
 * es decir: 0 es el peor equipo de la serie en esa medida y 100 el mejor.
 * La posición esperada va al revés, porque en ella lo menor es lo mejor.
 *
 * De dónde sale cada X:
 *   · Ataque, Defensa, Mediocampo: media de los últimos cinco partidos
 *     oficiales de cada equipo (defensa y ataque en HatStats, la suma de sus
 *     tres sectores).
 *   · TSI, Forma, Experiencia, Condición: la comparativa de liga, sobre los
 *     11 mejores de cada equipo.
 *   · Posición: el puesto esperado de la simulación de Liga.
 *
 * Al lado va siempre abierto el porqué de un pétalo --al entrar, el más flojo--
 * y se cambia pasando el ratón o tocando otro.
 *
 * 2026-09-15, pedido del usuario: mientras sigas en la Copa, tu próximo rival
 * de Copa entra en la flor como uno más --también en la escala-- con su nombre
 * seguido de «(Copa …)». En Posición no aparece: es el puesto de tu Liga.
 */

interface Equipo {
  htTeamId: number;
  nombre: string;
  propio: boolean;
  /** El próximo rival de Copa. */
  copa?: boolean;
}

/** «Copa Cocuy Rubí» tal cual; un nombre sin «Copa» delante, con ella. */
function etiquetaDeCopa(copa: string | null | undefined): string {
  if (!copa) return "Copa";
  return /^copa\b/i.test(copa) ? copa : `Copa ${copa}`;
}

interface Petalo {
  clave: string;
  nombre: string;
  /** Crudo por equipo; `null` si ese equipo no tiene el dato. */
  valores: Map<number, number | null>;
  /** En la posición esperada lo menor es lo mejor. */
  menorEsMejor?: boolean;
  formato: (v: number) => string;
  frase: (mio: string, n: number) => string;
}

interface Normalizado {
  htTeamId: number;
  nombre: string;
  propio: boolean;
  copa: boolean;
  crudo: number;
  valor: number;
}

/** Mismas 2.000 simulaciones que el resto del Dashboard: misma caché. */
const RUNS = 2_000;

function normalizar(p: Petalo, equipos: Equipo[]): Normalizado[] {
  const con = equipos
    .map((e) => ({ ...e, crudo: p.valores.get(e.htTeamId) }))
    .filter(
      (e): e is Equipo & { crudo: number } =>
        e.crudo != null && Number.isFinite(e.crudo),
    );
  if (con.length === 0) return [];
  const min = Math.min(...con.map((e) => e.crudo));
  const max = Math.max(...con.map((e) => e.crudo));
  return con
    .map((e) => {
      const t = max === min ? 1 : (e.crudo - min) / (max - min);
      return {
        htTeamId: e.htTeamId,
        nombre: e.nombre,
        propio: e.propio,
        copa: Boolean(e.copa),
        crudo: e.crudo,
        valor: Math.round((p.menorEsMejor ? 1 - t : t) * 100),
      };
    })
    .sort((a, b) => b.valor - a.valor || a.nombre.localeCompare(b.nombre));
}

export function FlorDeFuerza() {
  const league = useLeague(RUNS);
  const comparison = useLeagueComparison(false, true, true, true);
  const sectores = useSectoresRecientes();
  const [elegido, setElegido] = useState<string | null>(null);

  if (league.isLoading || comparison.isLoading || sectores.isLoading) {
    return (
      <Panel title="Fuerza en la serie">
        <div className="p-4">
          <Loading />
        </div>
      </Panel>
    );
  }
  const liga = league.data;
  if (!liga || liga.standings.length < 2) {
    return (
      <Panel title="Fuerza en la serie">
        <Empty>Todavía no hay clasificación de tu serie.</Empty>
      </Panel>
    );
  }

  const serie = liga.seriesName ?? "la serie";
  const equipos: Equipo[] = liga.standings.map((s) => ({
    htTeamId: s.htTeamId,
    nombre: s.name,
    propio: s.isOwnTeam,
  }));
  // El próximo rival de Copa: sus sectores y su plantilla llegan aparte, y
  // basta con que llegue uno de los dos para que entre en la flor.
  const copaSect = sectores.data?.equipos.find((e) => e.esCopa);
  const copaComp = comparison.data?.cupRival ?? null;
  const rivalDeCopa = copaSect
    ? {
        htTeamId: copaSect.htTeamId,
        nombre: copaSect.nombre,
        copa: copaSect.copa ?? null,
      }
    : copaComp
      ? {
          htTeamId: copaComp.teamHtId,
          nombre: copaComp.teamName,
          copa: copaComp.cupName,
        }
      : null;
  if (
    rivalDeCopa &&
    !equipos.some((e) => e.htTeamId === rivalDeCopa.htTeamId)
  ) {
    equipos.push({
      htTeamId: rivalDeCopa.htTeamId,
      nombre: `${rivalDeCopa.nombre} (${etiquetaDeCopa(rivalDeCopa.copa)})`,
      propio: false,
      copa: true,
    });
  }
  const hayCopa = equipos.some((e) => e.copa);
  const ranking = new Map(
    [...(comparison.data?.ranking ?? []), ...(copaComp ? [copaComp] : [])].map(
      (t) => [t.teamHtId, t],
    ),
  );
  const sect = new Map(
    (sectores.data?.equipos ?? []).map((e) => [e.htTeamId, e]),
  );
  const mioSect = sectores.data?.equipos.find((e) => e.esPropio);
  const partidos = mioSect?.partidos ?? 0;
  const deComparativa = (
    f: (
      t: NonNullable<ReturnType<typeof ranking.get>>,
    ) => number | null | undefined,
  ) =>
    new Map(
      equipos.map((e) => {
        const t = ranking.get(e.htTeamId);
        return [e.htTeamId, t ? (f(t) ?? null) : null];
      }),
    );
  const deSectores = (clave: "medio" | "defensa" | "ataque") =>
    new Map(
      equipos.map((e) => [e.htTeamId, sect.get(e.htTeamId)?.[clave] ?? null]),
    );
  const uno = (v: number) => decimal(v, 1);

  const petalos: Petalo[] = [
    {
      clave: "ataque",
      nombre: "Ataque",
      valores: deSectores("ataque"),
      formato: uno,
      frase: (mio, n) =>
        `Tu ataque suma ${mio} de HatStats de media en tus últimos ${n} partidos oficiales.`,
    },
    {
      clave: "defensa",
      nombre: "Defensa",
      valores: deSectores("defensa"),
      formato: uno,
      frase: (mio, n) =>
        `Tu defensa suma ${mio} de HatStats de media en tus últimos ${n} partidos oficiales.`,
    },
    {
      clave: "medio",
      nombre: "Mediocampo",
      valores: deSectores("medio"),
      formato: uno,
      frase: (mio, n) =>
        `Tu medio campo promedia ${mio} en tus últimos ${n} partidos oficiales.`,
    },
    {
      clave: "tsi",
      nombre: "TSI",
      valores: deComparativa((t) => t.totalTsi),
      formato: (v) => number(v),
      frase: (mio) => `Tus 11 mejores suman ${mio} de TSI.`,
    },
    {
      clave: "forma",
      nombre: "Forma",
      valores: deComparativa((t) => t.avgForm),
      formato: uno,
      frase: (mio) => `La forma media de tus 11 mejores es ${mio}.`,
    },
    {
      clave: "experiencia",
      nombre: "Experiencia",
      valores: deComparativa((t) => t.avgExperience),
      formato: uno,
      frase: (mio) => `La experiencia media de tus 11 mejores es ${mio}.`,
    },
    {
      clave: "condicion",
      nombre: "Resistencia",
      valores: deComparativa((t) => t.avgStamina),
      formato: uno,
      frase: (mio) => `La resistencia media de tus 11 mejores es ${mio}.`,
    },
    {
      clave: "posicion",
      nombre: "Posición",
      valores: new Map(
        liga.outlook.map((o) => [o.htTeamId, o.expectedPosition]),
      ),
      menorEsMejor: true,
      formato: (v) => `${decimal(v, 2)}º`,
      frase: (mio) => `En la simulación de Liga acabas, de media, ${mio}.`,
    },
  ];

  const filas = petalos.map((p) => ({ p, lista: normalizar(p, equipos) }));
  const valorPropio = (lista: Normalizado[]) =>
    lista.find((x) => x.propio)?.valor ?? null;
  // Al entrar se abre el pétalo más flojo: es el que más dice.
  const masFlojo = filas
    .filter((f) => valorPropio(f.lista) != null)
    .sort((a, b) => valorPropio(a.lista)! - valorPropio(b.lista)!)[0]?.p.clave;
  const activo =
    filas.find((f) => f.p.clave === (elegido ?? masFlojo)) ?? filas[0]!;

  return (
    <Panel
      title="Fuerza en la serie"
      meta={`0 = el peor de ${hayCopa ? `${serie} y tu rival de Copa` : serie} · 100 = el mejor`}
    >
      <div className="grid items-center gap-4 p-4 md:grid-cols-[300px_1fr]">
        <Flor
          filas={filas.map((f) => ({
            clave: f.p.clave,
            nombre: f.p.nombre,
            valor: valorPropio(f.lista),
          }))}
          activo={activo.p.clave}
          onElegir={setElegido}
        />
        <Porque
          petalo={activo.p}
          lista={activo.lista}
          serie={serie}
          partidos={partidos}
        />
      </div>
    </Panel>
  );
}

function Flor({
  filas,
  activo,
  onElegir,
}: {
  filas: { clave: string; nombre: string; valor: number | null }[];
  activo: string;
  onElegir: (clave: string) => void;
}) {
  const cx = 150;
  const cy = 145;
  const R = 92;
  const n = filas.length;
  const paso = (2 * Math.PI) / n;
  const P = (a: number, r: number) =>
    [cx + Math.cos(a) * r, cy + Math.sin(a) * r] as const;

  return (
    <svg
      viewBox="0 0 300 290"
      className="mx-auto w-full max-w-[300px]"
      role="img"
      aria-label="Flor de fuerza: un pétalo por medida, de 0 (el peor de la serie) a 100 (el mejor)"
    >
      {[25, 50, 75, 100].map((v) => (
        <circle
          key={v}
          cx={cx}
          cy={cy}
          r={(R * v) / 100}
          fill="none"
          stroke="var(--border)"
          strokeWidth={0.6}
        />
      ))}
      {filas.map((f, i) => {
        const centro = -Math.PI / 2 + i * paso;
        const a0 = centro - paso / 2 + 0.04;
        const a1 = centro + paso / 2 - 0.04;
        const valor = f.valor ?? 0;
        const r = Math.max(R * 0.06, (R * valor) / 100);
        const [x0, y0] = P(a0, r);
        const [x1, y1] = P(a1, r);
        const on = f.clave === activo;
        const [nx, ny] = P(centro, r * 0.72);
        const [lx, ly] = P(centro, R + 16);
        const anchor =
          Math.abs(lx - cx) < 6 ? "middle" : lx > cx ? "start" : "end";
        return (
          <g
            key={f.clave}
            onMouseEnter={() => onElegir(f.clave)}
            onClick={() => onElegir(f.clave)}
            className="cursor-pointer"
          >
            {/* Un sector entero invisible detrás: el pétalo corto también se
                puede señalar sin apuntar a un píxel. */}
            <path
              d={`M${cx} ${cy} L${P(a0, R)[0]} ${P(a0, R)[1]} A${R} ${R} 0 0 1 ${P(a1, R)[0]} ${P(a1, R)[1]} Z`}
              fill="transparent"
            />
            <path
              d={`M${cx} ${cy} L${x0} ${y0} A${r} ${r} 0 0 1 ${x1} ${y1} Z`}
              fill="var(--accent)"
              fillOpacity={on ? 0.9 : 0.25}
              stroke="var(--accent)"
              strokeWidth={on ? 1.5 : 0.5}
            />
            {f.valor != null && r > 18 && (
              <text
                x={nx}
                y={ny + 4}
                textAnchor="middle"
                fontSize={12}
                fill={on ? "white" : "var(--text)"}
              >
                {f.valor}
              </text>
            )}
            <text
              x={lx}
              y={ly + 4}
              textAnchor={anchor}
              fontSize={12}
              fontWeight={on ? 600 : 400}
              fill={on ? "var(--text)" : "var(--muted)"}
            >
              {f.nombre}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function Porque({
  petalo,
  lista,
  serie,
  partidos,
}: {
  petalo: Petalo;
  lista: Normalizado[];
  serie: string;
  partidos: number;
}) {
  const mio = lista.find((x) => x.propio);
  if (!mio) {
    return (
      <div className="rounded-lg border border-[var(--border)] p-3 text-sm text-[var(--muted)]">
        {petalo.nombre}: todavía no hay dato de tu equipo.
      </div>
    );
  }
  const puesto = lista.findIndex((x) => x.propio) + 1;
  const mejor = lista[0]!;
  const peor = lista[lista.length - 1]!;
  const nombreDe = (x: Normalizado) => (x.propio ? "tú" : x.nombre);
  // Con el rival de Copa dentro, «el mejor de la serie» ya no sería verdad.
  const ambito = lista.some((x) => x.copa)
    ? `${serie} y tu rival de Copa`
    : serie;
  const extremos = mejor.propio
    ? `Eres el mejor de ${ambito}; el peor es ${peor.nombre} (${petalo.formato(peor.crudo)}).`
    : peor.propio
      ? `Eres el peor de ${ambito}; el mejor es ${mejor.nombre} (${petalo.formato(mejor.crudo)}).`
      : `El mejor de ${ambito} es ${nombreDe(mejor)} (${petalo.formato(mejor.crudo)}) y el peor, ${nombreDe(peor)} (${petalo.formato(peor.crudo)}).`;

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 text-sm">
      <div className="mb-1 flex items-baseline justify-between font-semibold">
        <span>
          {petalo.nombre} · {puesto}º de {lista.length}
        </span>
        <span className="tabular-nums">{mio.valor}</span>
      </div>
      <p className="mb-2 text-xs leading-5 text-[var(--muted)]">
        {petalo.frase(petalo.formato(mio.crudo), partidos)} {extremos}
      </p>
      <div className="mb-0.5 grid grid-cols-[7.5rem_1fr_4.5rem_2rem] gap-2 text-[11px] text-[var(--muted)]">
        <span />
        <span />
        <span className="text-right">dato</span>
        <span className="text-right">flor</span>
      </div>
      <ul className="space-y-0.5">
        {lista.map((x) => (
          <li
            key={x.htTeamId}
            className={`grid grid-cols-[7.5rem_1fr_4.5rem_2rem] items-center gap-2 text-xs ${
              x.propio ? "font-semibold" : "text-[var(--muted)]"
            }`}
          >
            <span className="truncate" title={x.nombre}>
              {x.nombre}
            </span>
            <span className="h-1.5 overflow-hidden rounded bg-[var(--surface-2)]">
              <span
                className="block h-full rounded"
                style={{
                  width: `${Math.max(1, x.valor)}%`,
                  background: x.propio ? "var(--accent)" : "var(--border)",
                }}
              />
            </span>
            <span className="truncate text-right tabular-nums">
              {petalo.formato(x.crudo)}
            </span>
            <span className="text-right tabular-nums">{x.valor}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
