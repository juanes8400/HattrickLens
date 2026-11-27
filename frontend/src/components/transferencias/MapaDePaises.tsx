/** El mapa de países de Transferencias (2026-11-27): a dónde se fueron las
 *  ventas, o de dónde son los jugadores, en ganancia o en ROI.
 *
 *  Un mapa del mundo y, debajo, Europa ampliada, porque ahí va casi todo y en
 *  el mundial no se distingue. Los países que a esta escala no se dibujan
 *  (Andorra, Malta, Comoras…) van como un punto. Lo que no tiene país, al
 *  círculo del Atlántico. Rayado: menos de tres ventas. Al tocar un país se
 *  abre debajo lo suyo, con la lista de jugadores si cabe. */
import { useEffect, useId, useMemo, useState } from "react";
import clsx from "clsx";
import "flag-icons/css/flag-icons.min.css";
import type { PlayerBalanceRow } from "../../services/api";
import { compact, decimal, money } from "../../hooks/useFormat";
import { nombreDePais } from "../../utils/countryCodes";
import { tx } from "../../i18n/tx";
import { Panel, Empty } from "../Panels";
import { PlayerLink } from "../PlayerLink";
import {
  ATLANTICO,
  LIMITE,
  MINIMO_DE_VENTAS,
  SIN_ZONA,
  agruparPorZona,
  bordeDeLaCaja,
  colorDelValor,
  conicaDeEuropa,
  decodificar,
  limites,
  mejoresYPeores,
  naturalEarth,
  paletaDelMapa,
  trazado,
  valorDeLaZona,
  type CampoDelMapa,
  type ModoDelMapa,
  type MundoCrudo,
  type PaletaDelMapa,
  type Proyeccion,
  type Zona,
  type ZonaDibujable,
} from "./zonasDelMapa";

// El mapa se baja una sola vez y sólo cuando alguien abre un desglose.
let promesaDelMundo: Promise<ZonaDibujable[]> | null = null;
let puntosDelMundo: Record<string, [number, number]> = {};
function cargarMundo(): Promise<ZonaDibujable[]> {
  promesaDelMundo ??= import("./mundo.json").then((m) => {
    const crudo = (m.default ?? m) as unknown as MundoCrudo;
    puntosDelMundo = crudo.p;
    return decodificar(crudo);
  });
  return promesaDelMundo;
}

function useMundo(): ZonaDibujable[] | null {
  const [mundo, setMundo] = useState<ZonaDibujable[] | null>(null);
  useEffect(() => {
    let vivo = true;
    void cargarMundo().then((z) => vivo && setMundo(z));
    return () => {
      vivo = false;
    };
  }, []);
  return mundo;
}

const NOMBRES_PROPIOS: Record<string, string> = {
  "gb-eng": "Inglaterra",
  "gb-sct": "Escocia",
  "gb-wls": "Gales",
  "gb-nir": "Irlanda del Norte",
  oc: "Oceanía",
};

function nombreDeLaZona(clave: string, campo: CampoDelMapa): string {
  if (clave === SIN_ZONA)
    return campo === "destino"
      ? tx("Ninguno o sin determinar")
      : tx("Sin determinar");
  const propio = NOMBRES_PROPIOS[clave];
  if (propio) return tx(propio);
  return nombreDePais(clave, null) ?? clave.toUpperCase();
}

function Bandera({ clave }: { clave: string }) {
  if (clave === SIN_ZONA || clave === "oc") return null;
  return (
    <span
      aria-hidden
      className={`fi fi-${clave} shrink-0 rounded-[2px] shadow-[0_0_0_1px_color-mix(in_srgb,var(--border)_75%,transparent)]`}
    />
  );
}

function formatoDelValor(v: number, modo: ModoDelMapa): string {
  const signo = v > 0 ? "+" : v < 0 ? "−" : "";
  return modo === "roi"
    ? `${signo}${decimal(Math.abs(v))} %`
    : `${signo}${compact(Math.abs(v))}`;
}

interface Dibujo {
  zonas: { zona: string; d: string }[];
  caja: { x: number; y: number; ancho: number; alto: number };
  p: Proyeccion;
}

function dibujar(
  mundo: ZonaDibujable[],
  p: Proyeccion,
  europa: boolean,
): Dibujo {
  const enEuropa = (z: ZonaDibujable) =>
    z.anillos.some((a) =>
      a.some(([lon, lat]) => lon > -40 && lon < 70 && lat > 25 && lat < 85),
    );
  const zonas = (europa ? mundo.filter(enEuropa) : mundo).map((z) => ({
    zona: z.zona,
    d: trazado(z.anillos, p),
  }));
  const caja = europa
    ? limites(bordeDeLaCaja(), p)
    : limites(
        mundo.flatMap((z) => z.anillos.flat()),
        p,
      );
  const margen = europa ? 0 : 4;
  return {
    zonas,
    caja: {
      x: caja.x - margen,
      y: caja.y - margen,
      ancho: caja.ancho + 2 * margen,
      alto: caja.alto + 2 * margen,
    },
    p,
  };
}

function Lamina({
  dibujo,
  datos,
  modo,
  paleta,
  activa,
  onEncima,
  onToca,
  conCirculo,
  campo,
  etiqueta,
}: {
  dibujo: Dibujo;
  datos: Map<string, Zona>;
  modo: ModoDelMapa;
  paleta: PaletaDelMapa;
  activa: string | null;
  onEncima: (clave: string | null) => void;
  onToca: (clave: string) => void;
  conCirculo: boolean;
  campo: CampoDelMapa;
  etiqueta: string;
}) {
  const rayas = useId().replace(/:/g, "");
  const { caja, p } = dibujo;
  const relleno = (clave: string) => {
    const z = datos.get(clave);
    const v = z ? valorDeLaZona(z, modo) : null;
    return v == null ? paleta.tierra : colorDelValor(v, modo, paleta);
  };
  const pocas = (clave: string) => {
    const z = datos.get(clave);
    return z != null && z.n < MINIMO_DE_VENTAS;
  };
  const eventos = (clave: string) =>
    datos.has(clave)
      ? {
          onMouseEnter: () => onEncima(clave),
          onMouseLeave: () => onEncima(null),
          onClick: () => onToca(clave),
          style: { cursor: "pointer" },
        }
      : {};
  const escala = caja.ancho / 560;
  const sinZona = datos.get(SIN_ZONA);
  const [ax, ay] = p(...ATLANTICO);
  const radio = sinZona ? (6 + Math.sqrt(sinZona.n) * 1.4) * escala : 0;

  return (
    <svg
      role="img"
      aria-label={etiqueta}
      viewBox={`${caja.x} ${caja.y} ${caja.ancho} ${caja.alto}`}
      className={clsx(
        "block h-auto w-full rounded-md",
        // Europa es casi cuadrada: a todo lo ancho, en una sola columna, se
        // comería la pantalla.
        !conCirculo && "mx-auto max-w-[32rem]",
      )}
      style={{ background: paleta.mar }}
    >
      <defs>
        <pattern
          id={rayas}
          width={4 * escala}
          height={4 * escala}
          patternUnits="userSpaceOnUse"
          patternTransform="rotate(45)"
        >
          <line
            x1="0"
            y1="0"
            x2="0"
            y2={4 * escala}
            stroke={paleta.raya}
            strokeOpacity={0.45}
            strokeWidth={1.1 * escala}
          />
        </pattern>
      </defs>
      {dibujo.zonas.map((z, i) => (
        <path
          key={i}
          d={z.d}
          fill={relleno(z.zona)}
          stroke={
            activa != null && z.zona === activa ? paleta.raya : paleta.borde
          }
          strokeWidth={activa != null && z.zona === activa ? 1.4 : 0.4}
          vectorEffect="non-scaling-stroke"
          fillRule="evenodd"
          {...eventos(z.zona)}
        />
      ))}
      {dibujo.zonas
        .filter((z) => pocas(z.zona))
        .map((z, i) => (
          <path
            key={`r${i}`}
            d={z.d}
            fill={`url(#${rayas})`}
            fillRule="evenodd"
            pointerEvents="none"
          />
        ))}
      {Object.entries(puntosDelMundo)
        .filter(([clave]) => datos.has(clave))
        .map(([clave, [lon, lat]]) => {
          const [x, y] = p(lon, lat);
          return (
            <g key={clave} {...eventos(clave)}>
              <circle cx={x} cy={y} r={9 * escala} fill="transparent" />
              <circle
                cx={x}
                cy={y}
                r={3.4 * escala}
                fill={relleno(clave)}
                stroke={paleta.raya}
                strokeWidth={clave === activa ? 1.6 : 0.7}
                vectorEffect="non-scaling-stroke"
              />
            </g>
          );
        })}
      {conCirculo && sinZona && (
        <g {...eventos(SIN_ZONA)}>
          <circle
            cx={ax}
            cy={ay}
            r={radio}
            fill={relleno(SIN_ZONA)}
            stroke={paleta.raya}
            strokeWidth={activa === SIN_ZONA ? 1.8 : 1}
            strokeDasharray="3 2"
            vectorEffect="non-scaling-stroke"
          />
          <text
            x={ax}
            y={ay + 3.5 * escala}
            textAnchor="middle"
            fontSize={10 * escala}
            fontWeight={700}
            fill={paleta.raya}
          >
            {sinZona.n}
          </text>
          <text
            x={ax}
            y={ay + radio + 11 * escala}
            textAnchor="middle"
            fontSize={9 * escala}
            fill={paleta.raya}
            stroke={paleta.mar}
            strokeWidth={3 * escala}
            paintOrder="stroke"
          >
            {nombreDeLaZona(SIN_ZONA, campo)}
          </text>
        </g>
      )}
    </svg>
  );
}

function Leyenda({
  modo,
  paleta,
}: {
  modo: ModoDelMapa;
  paleta: PaletaDelMapa;
}) {
  const pasos = Array.from({ length: 11 }, (_, i) =>
    colorDelValor(((i - 5) / 5) * LIMITE[modo], modo, paleta),
  );
  const extremo = modo === "roi" ? "100 %" : compact(LIMITE[modo]);
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[var(--muted)]">
      <div className="flex items-center gap-1.5">
        <span className="tabular-nums">≤ −{extremo}</span>
        <span
          className="h-2.5 w-28 rounded-sm"
          style={{
            background: `linear-gradient(to right, ${pasos.join(",")})`,
          }}
        />
        <span className="tabular-nums">≥ +{extremo}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span
          className="h-2.5 w-4 rounded-sm border border-[var(--border)]"
          style={{
            background: `repeating-linear-gradient(45deg, ${paleta.medio} 0 2px, color-mix(in srgb, ${paleta.raya} 45%, ${paleta.medio}) 2px 3px)`,
          }}
        />
        {tx("menos de {{v0}}", { v0: MINIMO_DE_VENTAS })}
      </div>
    </div>
  );
}

function Detalle({
  zona,
  campo,
  modo,
  moneda,
}: {
  zona: Zona | null;
  campo: CampoDelMapa;
  modo: ModoDelMapa;
  moneda: string;
}) {
  if (!zona)
    return (
      <p className="rounded-md border border-dashed border-[var(--border)] px-3 py-2 text-xs text-[var(--muted)]">
        {tx("Toca un país para ver sus jugadores.")}
      </p>
    );
  const roi = valorDeLaZona(zona, "roi");
  const VISIBLES = 8;
  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-sm">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="flex items-center gap-1.5 font-semibold">
          <Bandera clave={zona.clave} />
          {nombreDeLaZona(zona.clave, campo)}
        </span>
        <span className="text-xs text-[var(--muted)]">
          {campo === "destino"
            ? tx("{{v0}} ventas", { v0: zona.n })
            : tx("{{v0}} jugadores", { v0: zona.n })}
        </span>
        <span
          className="text-xs font-medium tabular-nums"
          style={{
            color: zona.saldo >= 0 ? "var(--positive)" : "var(--danger)",
          }}
        >
          {tx("Ganancia")} {money(zona.saldo, moneda)}
        </span>
        {roi != null && (
          <span
            className="text-xs font-medium tabular-nums"
            style={{ color: roi >= 0 ? "var(--positive)" : "var(--danger)" }}
          >
            ROI {formatoDelValor(roi, "roi")}
          </span>
        )}
      </div>
      <ul className="mt-1.5 grid gap-x-4 gap-y-0.5 text-xs sm:grid-cols-2">
        {zona.jugadores.slice(0, VISIBLES).map((j, i) => (
          <li
            key={`${j.id}-${i}`}
            className="flex min-w-0 justify-between gap-2"
          >
            <span className="truncate">
              <PlayerLink htPlayerId={j.id} name={j.nombre} />
            </span>
            <span
              className="shrink-0 tabular-nums"
              style={{
                color: j.saldo >= 0 ? "var(--positive)" : "var(--danger)",
              }}
            >
              {formatoDelValor(j.saldo, "absoluto")}
            </span>
          </li>
        ))}
      </ul>
      {zona.jugadores.length > VISIBLES && (
        <p className="mt-1 text-xs text-[var(--muted)]">
          {tx("y {{v0}} más", { v0: zona.jugadores.length - VISIBLES })}
        </p>
      )}
      {modo === "roi" && (
        <p className="mt-1 text-[11px] text-[var(--muted)]">
          {tx("Sólo cuentan los que costaron algo: sin inversión no hay ROI.")}
        </p>
      )}
    </div>
  );
}

export function MapaDePaises({
  filas,
  campo,
  modo,
  moneda,
  isDark,
}: {
  filas: PlayerBalanceRow[];
  campo: CampoDelMapa;
  modo: ModoDelMapa;
  moneda: string;
  isDark: boolean;
}) {
  const mundo = useMundo();
  const [encima, setEncima] = useState<string | null>(null);
  const [tocada, setTocada] = useState<string | null>(null);
  const datos = useMemo(
    () => agruparPorZona(filas, campo, modo),
    [filas, campo, modo],
  );
  const paleta = paletaDelMapa(isDark);
  const dibujos = useMemo(
    () =>
      mundo
        ? {
            mundo: dibujar(mundo, naturalEarth, false),
            europa: dibujar(mundo, conicaDeEuropa, true),
          }
        : null,
    [mundo],
  );

  const titulo =
    campo === "destino"
      ? modo === "absoluto"
        ? tx("Ganancia por país de destino")
        : tx("ROI por país de destino")
      : modo === "absoluto"
        ? tx("Ganancia por nacionalidad")
        : tx("ROI por nacionalidad");
  const ayuda =
    campo === "destino"
      ? modo === "absoluto"
        ? tx(
            "Suma el saldo de los jugadores según el país del club que los compró. El círculo del Atlántico reúne las salidas sin venta y las ventas cuyo destino no se conoce.",
          )
        : tx(
            "El saldo dividido entre lo invertido, según el país del club que compró a cada jugador. El círculo del Atlántico reúne las salidas sin venta y las ventas cuyo destino no se conoce.",
          )
      : modo === "absoluto"
        ? tx(
            "Suma el saldo según el país de nacimiento de cada jugador. El círculo del Atlántico reúne a los que no se les conoce.",
          )
        : tx(
            "El saldo dividido entre lo invertido, según el país de nacimiento de cada jugador. El círculo del Atlántico reúne a los que no se les conoce.",
          );

  if (datos.size === 0)
    return (
      <Panel title={titulo} ayuda={ayuda}>
        <Empty>{tx("Todavía no hay ventas con estos datos.")}</Empty>
      </Panel>
    );

  const activa = encima ?? tocada;
  const tocar = (clave: string) =>
    setTocada((antes) => (antes === clave ? null : clave));
  const tabla = mejoresYPeores(datos, modo);
  const sinZona = datos.get(SIN_ZONA);
  const conPais = [...datos.values()].filter((z) => z.clave !== SIN_ZONA);
  const meta =
    campo === "destino"
      ? tx("{{v0}} países · {{v1}} sin determinar", {
          v0: conPais.length,
          v1: sinZona?.n ?? 0,
        })
      : tx("{{v0}} nacionalidades · {{v1}} sin determinar", {
          v0: conPais.length,
          v1: sinZona?.n ?? 0,
        });
  const etiquetaDelValor = modo === "roi" ? tx("ROI") : tx("Ganancia");

  return (
    <Panel title={titulo} ayuda={ayuda} meta={meta}>
      <div className="space-y-3 p-4">
        {!dibujos ? (
          <div className="aspect-[2/1] w-full animate-pulse rounded-md bg-[var(--surface-2)]" />
        ) : (
          <>
            <Lamina
              dibujo={dibujos.mundo}
              datos={datos}
              modo={modo}
              paleta={paleta}
              activa={activa}
              onEncima={setEncima}
              onToca={tocar}
              conCirculo
              campo={campo}
              etiqueta={titulo}
            />
            <div>
              <p className="mb-1 text-xs text-[var(--muted)]">
                {tx("Europa, ampliada")}
              </p>
              <Lamina
                dibujo={dibujos.europa}
                datos={datos}
                modo={modo}
                paleta={paleta}
                activa={activa}
                onEncima={setEncima}
                onToca={tocar}
                conCirculo={false}
                campo={campo}
                etiqueta={tx("{{v0}}, Europa ampliada", { v0: titulo })}
              />
            </div>
          </>
        )}
        <Leyenda modo={modo} paleta={paleta} />
        <Detalle
          zona={activa ? (datos.get(activa) ?? null) : null}
          campo={campo}
          modo={modo}
          moneda={moneda}
        />
        <div>
          <p className="mb-1 text-xs text-[var(--muted)]">
            {tx("Los mejores y los peores, entre los que tienen {{v0}} o más", {
              v0: MINIMO_DE_VENTAS,
            })}
          </p>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-[var(--muted)]">
                <th className="py-1 text-left font-normal">
                  {campo === "destino" ? tx("País") : tx("Nacionalidad")}
                </th>
                <th className="py-1 text-right font-normal">
                  {campo === "destino" ? tx("Ventas") : tx("Jugadores")}
                </th>
                <th className="py-1 text-right font-normal">
                  {etiquetaDelValor}
                </th>
              </tr>
            </thead>
            <tbody>
              {[...tabla, ...(sinZona ? [sinZona] : [])].map((z, i) =>
                z == null ? (
                  <tr key={`…${i}`}>
                    <td
                      colSpan={3}
                      className="py-0.5 text-center text-[var(--muted)]"
                    >
                      …
                    </td>
                  </tr>
                ) : (
                  <tr
                    key={z.clave}
                    onClick={() => tocar(z.clave)}
                    className={clsx(
                      "cursor-pointer border-t border-[var(--border)] hover:bg-[var(--surface-2)]",
                      activa === z.clave && "bg-[var(--surface-2)]",
                    )}
                  >
                    <td className="py-1">
                      <span className="flex items-center gap-1.5">
                        <span
                          className="inline-block h-2 w-2 shrink-0 rounded-[2px]"
                          style={{
                            background: colorDelValor(
                              valorDeLaZona(z, modo) ?? 0,
                              modo,
                              paleta,
                            ),
                          }}
                        />
                        <Bandera clave={z.clave} />
                        {nombreDeLaZona(z.clave, campo)}
                      </span>
                    </td>
                    <td className="py-1 text-right tabular-nums">{z.n}</td>
                    <td className="py-1 text-right tabular-nums">
                      {valorDeLaZona(z, modo) == null
                        ? "?"
                        : formatoDelValor(valorDeLaZona(z, modo)!, modo)}
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      </div>
    </Panel>
  );
}
