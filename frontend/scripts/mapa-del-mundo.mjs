/** Genera `src/data/paisesDelMundo.ts`: la silueta de cada país, ya proyectada.
 *
 *  2026-09-28. La pantalla de Uso enseña de dónde es la gente sobre un mapa, y
 *  un mapa necesita geometría de verdad. Ésta viene de Natural Earth (dominio
 *  público) por medio de `world-atlas`, y de `world-countries` sale el código
 *  ISO de dos letras, que es con lo que HT Lens guarda los países.
 *
 *  Se genera A MANO y el resultado se versiona: el despliegue no puede depender
 *  de que un CDN conteste, y la geometría de los países no cambia entre
 *  compilaciones. Para rehacerlo:
 *
 *      node scripts/mapa-del-mundo.mjs
 *
 *  Proyección equirectangular, recortada al norte de la Antártida: es la que no
 *  hincha las latitudes altas hasta lo ridículo (Groenlandia como África) y la
 *  única que se puede deshacer con una resta, que es lo que hace falta para
 *  colocar un punto sobre el mapa.
 */

import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const AQUI = dirname(fileURLToPath(import.meta.url));
const SALIDA = join(AQUI, "..", "src", "data", "paisesDelMundo.ts");

const MAPA = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";
const CODIGOS =
  "https://cdn.jsdelivr.net/npm/world-countries@5.0.0/countries.json";

/** El lienzo. El alto sale del trozo de mundo que se dibuja, no al revés: así
 *  un grado de latitud mide lo mismo que uno de longitud y nada se estira. */
const ANCHO = 1000;
//: Por el sur se corta en el cabo de Hornos, y la Antártida se deja fuera: es
//: media pantalla de blanco donde no vive nadie. Por el norte, 84° cubre
//: Groenlandia entera.
const LAT_MAX = 84;
const LAT_MIN = -56;
const ALTO = Math.round((ANCHO * (LAT_MAX - LAT_MIN)) / 360);

//: Una isla más pequeña que esto, ya proyectada, es menos de un píxel: dibujarla
//: sólo engorda el fichero.
const MINIMO_DIBUJABLE = 0.9;

async function traer(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} contestó ${r.status}`);
  return r.json();
}

/** TopoJSON guarda las fronteras UNA vez y las comparte entre los dos países
 *  que las tocan; esto las devuelve a coordenadas normales. */
function arcosDe(topo) {
  const {
    scale: [sx, sy],
    translate: [tx, ty],
  } = topo.transform;
  return topo.arcs.map((arco) => {
    let x = 0;
    let y = 0;
    return arco.map(([dx, dy]) => {
      x += dx;
      y += dy;
      return [x * sx + tx, y * sy + ty];
    });
  });
}

function anillo(indices, arcos) {
  const puntos = [];
  for (const i of indices) {
    const arco = i < 0 ? [...arcos[~i]].reverse() : arcos[i];
    // El último punto de un arco es el primero del siguiente.
    for (const p of puntos.length ? arco.slice(1) : arco) puntos.push(p);
  }
  return puntos;
}

const x = (lon) => ((lon + 180) / 360) * ANCHO;
const y = (lat) =>
  ((LAT_MAX - Math.min(LAT_MAX, Math.max(LAT_MIN, lat))) /
    (LAT_MAX - LAT_MIN)) *
  ALTO;

/** Deshace los saltos de 360° dentro de un anillo.
 *
 *  Rusia y Fiyi tienen tierra a los dos lados del meridiano 180, y el fichero
 *  de origen lo escribe saltando de +179 a -179. En un mapa plano ese salto se
 *  dibuja como una LÍNEA RECTA de un extremo al otro, y eso son las dos rayas
 *  horizontales que aparecieron cruzando el mapa entero: una a la altura de
 *  Chukotka y otra a la de Fiyi.
 *
 *  Aquí cada punto se coloca en la vuelta que lo deja más cerca del anterior,
 *  así que el anillo queda continuo aunque se salga del rango -180..180. Luego
 *  se dibuja también desplazado una vuelta a cada lado, y el lienzo recorta lo
 *  que sobra: así el trozo que está «al otro lado» aparece donde le toca.
 */
function desenrollar(puntos) {
  const salida = [puntos[0]];
  for (let i = 1; i < puntos.length; i++) {
    let lon = puntos[i][0];
    const anterior = salida[i - 1][0];
    while (lon - anterior > 180) lon -= 360;
    while (anterior - lon > 180) lon += 360;
    salida.push([lon, puntos[i][1]]);
  }
  return salida;
}

function trazo(anillos) {
  const partes = [];
  for (const crudo of anillos) {
    const puntos = desenrollar(crudo);
    const lats = puntos.map(([, lat]) => lat);
    // Un anillo entero fuera de la franja que se dibuja no se recorta: se
    // aplasta contra el borde y deja un churro. Fuera del todo.
    if (Math.max(...lats) < LAT_MIN || Math.min(...lats) > LAT_MAX) continue;

    const lons = puntos.map(([lon]) => lon);
    const oeste = Math.min(...lons);
    const este = Math.max(...lons);
    for (let vuelta = -720; vuelta <= 720; vuelta += 360) {
      if (oeste + vuelta >= 180 || este + vuelta <= -180) continue;
      const xs = puntos.map(([lon]) => x(lon + vuelta));
      const ys = puntos.map(([, lat]) => y(lat));
      const ancho = Math.max(...xs) - Math.min(...xs);
      const alto = Math.max(...ys) - Math.min(...ys);
      // Las dos medidas, no el área: una isla estrecha pero larga sí se ve.
      if (ancho < MINIMO_DIBUJABLE && alto < MINIMO_DIBUJABLE) continue;
      let d = "";
      let anterior = "";
      for (let i = 0; i < puntos.length; i++) {
        const par = `${xs[i].toFixed(1)} ${ys[i].toFixed(1)}`;
        // Redondear a un decimal deja puntos repetidos seguidos: quitarlos no
        // cambia el dibujo y adelgaza el fichero a la mitad.
        if (par === anterior) continue;
        d += (d ? "L" : "M") + par;
        anterior = par;
      }
      if (d) partes.push(`${d}Z`);
    }
  }
  return partes.join("");
}

const [topo, paises] = await Promise.all([traer(MAPA), traer(CODIGOS)]);
const arcos = arcosDe(topo);
const porNumero = new Map(paises.map((p) => [p.ccn3, p]));

//: La Antártida, por su id numérico ISO. Se deja fuera de verdad y no sólo
//: recortada: es media pantalla donde no vive nadie, y recortarla la aplastaba
//: contra el borde de abajo en una franja que cruzaba el mapa entero.
const ANTARTIDA = "010";

const filas = [];
for (const g of topo.objects.countries.geometries) {
  if (String(g.id).padStart(3, "0") === ANTARTIDA) continue;
  const anillos =
    g.type === "Polygon"
      ? g.arcs.map((r) => anillo(r, arcos))
      : g.type === "MultiPolygon"
        ? g.arcs.flatMap((poly) => poly.map((r) => anillo(r, arcos)))
        : [];
  const d = trazo(anillos);
  if (!d) continue;
  const iso = porNumero.get(String(g.id).padStart(3, "0"));
  filas.push({
    // Sin código ISO se dibuja igual, en gris: es tierra que existe --Kosovo,
    // el Sáhara-- y dejar el agujero se vería como un error del mapa.
    code: iso ? iso.cca2.toLowerCase() : "",
    name: iso ? iso.name.common : g.properties?.name || "",
    d,
  });
}

filas.sort(
  (a, b) => a.code.localeCompare(b.code) || a.name.localeCompare(b.name),
);

// El centro de CADA país, tenga silueta o no. A 1:110 millones veinte de los
// países de Hattrick --Malta, Singapur, Hong Kong, las islas del Caribe-- no
// llegan a un píxel y no tienen forma que pintar; sin esto desaparecerían del
// mapa justo los sitios de los que cuesta más tener un usuario.
const centros = {};
for (const p of paises) {
  const [lat, lon] = p.latlng ?? [];
  if (typeof lat !== "number" || typeof lon !== "number") continue;
  centros[p.cca2.toLowerCase()] = [
    Number(x(lon).toFixed(1)),
    Number(y(lat).toFixed(1)),
  ];
}

const texto = `/** La silueta de cada país, proyectada y lista para un <path>.
 *
 *  GENERADO, no se edita a mano: \`node scripts/mapa-del-mundo.mjs\`.
 *
 *  Geometría de Natural Earth (dominio público) vía world-atlas, a escala
 *  1:110 millones; códigos ISO de world-countries. Proyección equirectangular
 *  entre ${LAT_MIN}° y ${LAT_MAX}° de latitud, en un lienzo de ${ANCHO}×${ALTO}.
 *
 *  \`code\` vacío es tierra sin país ISO propio (Kosovo, el Sáhara): se dibuja
 *  como fondo, porque dejar el agujero parece un fallo del mapa.
 */

export const ANCHO_DEL_MUNDO = ${ANCHO};
export const ALTO_DEL_MUNDO = ${ALTO};
export const LATITUD_MAXIMA = ${LAT_MAX};
export const LATITUD_MINIMA = ${LAT_MIN};

export interface PaisDelMundo {
  /** ISO 3166-1 alfa-2 en minúsculas, el mismo que guarda el mundo de Hattrick. */
  code: string;
  name: string;
  d: string;
}

export const PAISES_DEL_MUNDO: PaisDelMundo[] = ${JSON.stringify(filas, null, 0)};

/** El centro de cada país, en las coordenadas del lienzo.
 *
 *  A esta escala veinte de los países de Hattrick no llegan a un píxel y no
 *  tienen silueta que pintar. Ahí va un punto: desaparecer del mapa sería
 *  justamente lo contrario de lo que el mapa viene a contar.
 */
export const CENTROS_DE_PAIS: Record<string, [number, number]> = ${JSON.stringify(centros, null, 0)};
`;

mkdirSync(dirname(SALIDA), { recursive: true });
writeFileSync(SALIDA, texto, "utf8");
console.log(
  `${filas.length} países, ${(texto.length / 1024).toFixed(0)} KB → ${SALIDA}`,
);
