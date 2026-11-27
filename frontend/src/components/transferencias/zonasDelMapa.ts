/** La lógica del mapa de países de Transferencias (2026-11-27), aparte del
 *  dibujo para poder probarla: cómo se agrupan las filas, el color de cada
 *  zona y las dos proyecciones.
 *
 *  Las zonas son las que manda el servidor (`destinationRegion`,
 *  `nativeRegion`): el código ISO en minúscula, las cuatro ligas británicas
 *  por separado («gb-eng», «gb-sct», «gb-wls», «gb-nir») y Oceanía entera
 *  como una sola («oc»). */
import type { PlayerBalanceRow } from "../../services/api";

export type CampoDelMapa = "destino" | "nacionalidad";
export type ModoDelMapa = "absoluto" | "roi";

/** La clave del círculo del Atlántico: «Ninguno o sin determinar». */
export const SIN_ZONA = "__sin_zona";

/** Por debajo de esto el país se pinta rayado: su color depende de muy pocos
 *  datos (eligió la opción B el 2026-11-27). La tabla también lo exige. */
export const MINIMO_DE_VENTAS = 3;

/** Los extremos del color, fijos y saturando (regla del usuario). */
export const LIMITE = { absoluto: 8_000_000, roi: 100 } as const;

export interface JugadorDeLaZona {
  id: number;
  nombre: string;
  saldo: number;
}

export interface Zona {
  clave: string;
  n: number;
  saldo: number;
  coste: number;
  jugadores: JugadorDeLaZona[];
}

export function zonaDe(r: PlayerBalanceRow, campo: CampoDelMapa): string {
  const z =
    campo === "destino"
      ? r.isSold
        ? r.destinationRegion
        : null
      : r.nativeRegion;
  return z ?? SIN_ZONA;
}

/** Las filas que entran son las mismas que en el resto de desgloses: con
 *  saldo calculable, y en ROI además con algo invertido, porque el
 *  porcentaje se saca de los totales de cada país, nunca promediando. */
export function agruparPorZona(
  filas: PlayerBalanceRow[],
  campo: CampoDelMapa,
  modo: ModoDelMapa,
): Map<string, Zona> {
  const zonas = new Map<string, Zona>();
  for (const r of filas) {
    if (r.saldo == null) continue;
    if (modo === "roi" && r.totalCost <= 0) continue;
    const clave = zonaDe(r, campo);
    const z = zonas.get(clave) ?? {
      clave,
      n: 0,
      saldo: 0,
      coste: 0,
      jugadores: [],
    };
    z.n += 1;
    z.saldo += r.saldo;
    z.coste += r.totalCost;
    z.jugadores.push({ id: r.htPlayerId, nombre: r.name, saldo: r.saldo });
    zonas.set(clave, z);
  }
  for (const z of zonas.values()) z.jugadores.sort((a, b) => b.saldo - a.saldo);
  return zonas;
}

export function valorDeLaZona(z: Zona, modo: ModoDelMapa): number | null {
  if (modo === "absoluto") return z.saldo;
  return z.coste > 0 ? (z.saldo / z.coste) * 100 : null;
}

/** Los cuatro mejores y los cuatro peores entre los que tienen al menos
 *  `MINIMO_DE_VENTAS`; con ocho o menos, todos. `null` marca el «…». */
export function mejoresYPeores(
  zonas: Map<string, Zona>,
  modo: ModoDelMapa,
): (Zona | null)[] {
  const orden = [...zonas.values()]
    .filter(
      (z) =>
        z.clave !== SIN_ZONA &&
        z.n >= MINIMO_DE_VENTAS &&
        valorDeLaZona(z, modo) != null,
    )
    .sort((a, b) => valorDeLaZona(b, modo)! - valorDeLaZona(a, modo)!);
  if (orden.length <= 8) return orden;
  return [...orden.slice(0, 4), null, ...orden.slice(-4)];
}

// ── Color ────────────────────────────────────────────────────────────────

function hex(c: string): [number, number, number] {
  const v = parseInt(c.slice(1), 16);
  return [(v >> 16) & 255, (v >> 8) & 255, v & 255];
}

function mezcla(a: string, b: string, t: number): string {
  const [r1, g1, b1] = hex(a);
  const [r2, g2, b2] = hex(b);
  const m = (x: number, y: number) => Math.round(x + (y - x) * t);
  return `rgb(${m(r1, r2)}, ${m(g1, g2)}, ${m(b1, b2)})`;
}

export interface PaletaDelMapa {
  mar: string;
  tierra: string;
  borde: string;
  medio: string;
  pierdes: string;
  ganas: string;
  raya: string;
}

export function paletaDelMapa(isDark: boolean): PaletaDelMapa {
  return isDark
    ? {
        mar: "#17171a",
        tierra: "#26262b",
        borde: "#0a0a0b",
        medio: "#4a4a52",
        pierdes: "#e5484d",
        ganas: "#2fbf71",
        raya: "#ededef",
      }
    : {
        mar: "#eef1f5",
        tierra: "#ffffff",
        borde: "#c4c4cc",
        medio: "#dcdce0",
        pierdes: "#d1383d",
        ganas: "#1a9e5c",
        raya: "#18181b",
      };
}

/** Divergente: rojo (pierdes) · gris · verde (ganas), recortado en el límite
 *  y con raíz cuadrada, para que lo modesto ya se distinga del gris. */
export function colorDelValor(
  v: number,
  modo: ModoDelMapa,
  paleta: PaletaDelMapa,
): string {
  const t = Math.max(-1, Math.min(1, v / LIMITE[modo]));
  return mezcla(
    paleta.medio,
    t < 0 ? paleta.pierdes : paleta.ganas,
    Math.sqrt(Math.abs(t)),
  );
}

// ── Geometría ────────────────────────────────────────────────────────────

/** `mundo.json`: Natural Earth 110 m («map units», dominio público), sin la
 *  Antártida, en décimas de grado y con cada anillo en diferencias. */
export interface MundoCrudo {
  z: [string, number[][]][];
  p: Record<string, [number, number]>;
}

export interface ZonaDibujable {
  zona: string;
  anillos: [number, number][][];
}

export function decodificar(mundo: MundoCrudo): ZonaDibujable[] {
  return mundo.z.map(([zona, anillos]) => ({
    zona,
    anillos: anillos.map((plano) => {
      const puntos: [number, number][] = [];
      let x = 0;
      let y = 0;
      for (let i = 0; i < plano.length; i += 2) {
        x += plano[i]!;
        y += plano[i + 1]!;
        puntos.push([x / 10, y / 10]);
      }
      return puntos;
    }),
  }));
}

export type Proyeccion = (lon: number, lat: number) => [number, number];

const RAD = Math.PI / 180;

/** Natural Earth I, la del mundo. La `y` sale ya hacia abajo, como en SVG. */
export const naturalEarth: Proyeccion = (lon, lat) => {
  const l = lon * RAD;
  const f = lat * RAD;
  const f2 = f * f;
  const f4 = f2 * f2;
  const x =
    l *
    (0.8707 -
      0.131979 * f2 +
      f4 * (-0.013791 + f4 * (0.003971 * f2 - 0.001529 * f4)));
  const y =
    f *
    (1.007226 +
      f2 * (0.015085 + f4 * (-0.044475 + 0.028874 * f2 - 0.005916 * f4)));
  return [x * 100, -y * 100];
};

/** Cónica conforme de Lambert centrada en Europa, la del recuadro ampliado:
 *  ahí van casi todas las ventas, y en el mapa mundial no se distinguen. */
export const conicaDeEuropa: Proyeccion = (() => {
  const f1 = 40 * RAD;
  const f2 = 60 * RAD;
  const l0 = 10 * RAD;
  const t = (f: number) => Math.tan(Math.PI / 4 + f / 2);
  const n = Math.log(Math.cos(f1) / Math.cos(f2)) / Math.log(t(f2) / t(f1));
  const F = (Math.cos(f1) * Math.pow(t(f1), n)) / n;
  const rho = (f: number) => F / Math.pow(t(f), n);
  const r0 = rho(52 * RAD);
  return (lon: number, lat: number): [number, number] => {
    const r = rho(lat * RAD);
    const a = n * (lon * RAD - l0);
    return [r * Math.sin(a) * 400, -(r0 - r * Math.cos(a)) * 400];
  };
})();

/** El recuadro de Europa, en grados: de Islandia y Canarias al Cáucaso. */
export const CAJA_DE_EUROPA = { oeste: -25, este: 45, sur: 34, norte: 71 };

export function trazado(anillos: [number, number][][], p: Proyeccion): string {
  let d = "";
  for (const anillo of anillos) {
    anillo.forEach(([lon, lat], i) => {
      const [x, y] = p(lon, lat);
      d += `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    });
    d += "Z";
  }
  return d;
}

export function limites(
  puntos: [number, number][],
  p: Proyeccion,
): { x: number; y: number; ancho: number; alto: number } {
  let x0 = Infinity;
  let y0 = Infinity;
  let x1 = -Infinity;
  let y1 = -Infinity;
  for (const [lon, lat] of puntos) {
    const [x, y] = p(lon, lat);
    x0 = Math.min(x0, x);
    y0 = Math.min(y0, y);
    x1 = Math.max(x1, x);
    y1 = Math.max(y1, y);
  }
  return { x: x0, y: y0, ancho: x1 - x0, alto: y1 - y0 };
}

/** El borde de la caja de Europa, muestreado: en la cónica los paralelos
 *  son curvos y las cuatro esquinas no bastan para encuadrarla. */
export function bordeDeLaCaja(): [number, number][] {
  const { oeste, este, sur, norte } = CAJA_DE_EUROPA;
  const puntos: [number, number][] = [];
  for (let i = 0; i <= 20; i++) {
    const lon = oeste + ((este - oeste) * i) / 20;
    puntos.push([lon, sur], [lon, norte]);
  }
  for (let i = 0; i <= 10; i++) {
    const lat = sur + ((norte - sur) * i) / 10;
    puntos.push([oeste, lat], [este, lat]);
  }
  return puntos;
}

/** El círculo del Atlántico, en mitad del océano: lejos de Cabo Verde y del
 *  Caribe, que llevan su punto, y de la costa de Brasil. */
export const ATLANTICO: [number, number] = [-46, 30];
