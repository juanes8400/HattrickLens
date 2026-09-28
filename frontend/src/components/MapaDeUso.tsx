import { useState } from "react";
import {
  ALTO_DEL_MUNDO,
  ANCHO_DEL_MUNDO,
  CENTROS_DE_PAIS,
  PAISES_DEL_MUNDO,
} from "../data/paisesDelMundo";
import { CountryFlag } from "./CountryFlag";
import { Panel } from "./Panels";
import { nombreDePais } from "../utils/countryCodes";
import { cifra } from "../hooks/useFormat";
import { tx } from "../i18n/tx";

/** De dónde es la gente y cuánto usa la aplicación, sobre el mapa.
 *
 *  2026-09-28, pedido del usuario. HT Lens se anuncia en foros de países muy
 *  distintos y no había forma de saber a cuáles llegó de verdad: la tabla de
 *  personas da nombres, no procedencias, y un nombre de Hattrick no dice el
 *  país. El país sale de la liga del club, que Hattrick ya publica; aquí no se
 *  mira de dónde viene la conexión ni se pregunta nada.
 *
 *  El color va por CLICS, que es lo que el usuario pidió: no por personas ni
 *  por tiempo. Un país con cuatro managers que abren y cierran colorea menos
 *  que uno con dos que trabajan dentro, y eso es justo la diferencia que la
 *  pantalla viene a enseñar.
 */

export interface UsoPorPais {
  code: string;
  name: string;
  users: number;
  sessions: number;
  pages: number;
  clicks: number;
  minutes: number;
}

/** Los cinco tonos del mapa: UN solo color, de claro a oscuro.
 *
 *  Una escala de magnitud no se pinta con colores distintos --eso dice
 *  «categorías», no «más y menos»--, así que son cinco mezclas del acento de la
 *  aplicación sobre el fondo. Se escriben con `color-mix` para que el tema
 *  oscuro salga solo: el acento y el fondo ya cambian con él.
 */
const TONOS = [20, 38, 56, 74, 92] as const;
const tono = (paso: number) =>
  `color-mix(in srgb, var(--accent) ${TONOS[paso]}%, var(--surface-2))`;

/** En qué tono cae un país.
 *
 *  Sobre la RAÍZ de los clics, no sobre los clics. El reparto está siempre muy
 *  torcido --el país del autor multiplica por diez al segundo-- y en escala
 *  lineal todo lo demás cae en el primer tono y el mapa queda en blanco y
 *  negro, que es no decir nada.
 */
function pasoDeColor(clics: number, maximo: number): number {
  if (maximo <= 0 || clics <= 0) return 0;
  const parte = Math.sqrt(clics) / Math.sqrt(maximo);
  return Math.min(TONOS.length - 1, Math.floor(parte * TONOS.length));
}

/** Los cortes de clics de cada tono, para poder rotular la leyenda con números
 *  y no con «poco / mucho». Es la operación de arriba al revés. */
function corteDeTono(paso: number, maximo: number): number {
  return Math.ceil(((paso / TONOS.length) * Math.sqrt(maximo)) ** 2);
}

export function MapaDeUso({ paises }: { paises: UsoPorPais[] }) {
  const [encima, setEncima] = useState<string | null>(null);

  // Sin código no hay sitio en el mapa: son las ligas internacionales y quien
  // se registró sin sincronizar nunca. Se cuentan aparte, no se esconden.
  const situados = paises.filter((p) => p.code);
  const sinSitio = paises.find((p) => !p.code);
  const porCodigo = new Map(situados.map((p) => [p.code, p]));
  const maximo = Math.max(...situados.map((p) => p.clicks), 0);

  if (situados.length === 0) {
    return (
      <Panel title={tx("De dónde es la gente")}>
        <p className="p-4 text-sm text-[var(--muted)]">
          {tx(
            "Todavía no consta el país de nadie: sale de la liga del club, así que aparece en cuanto alguien sincroniza.",
          )}
        </p>
      </Panel>
    );
  }

  const señalado = encima ? porCodigo.get(encima) : undefined;

  return (
    <Panel
      title={tx("De dónde es la gente")}
      meta={
        // Con un solo país «1 países» canta, y el sistema de textos traduce
        // frases enteras, no plurales.
        situados.length === 1
          ? tx("1 país · color por clics")
          : tx("{{v0}} países · color por clics", { v0: situados.length })
      }
      ayuda={tx(
        "El país no se pregunta ni se deduce de la conexión: es el de la liga del club, que Hattrick ya publica. Quien lleva varios clubes cuenta por el principal.",
      )}
    >
      <div className="p-4">
        <div className="overflow-x-auto">
          <svg
            viewBox={`0 0 ${ANCHO_DEL_MUNDO} ${ALTO_DEL_MUNDO}`}
            role="img"
            aria-label={tx(
              "Mapa del mundo con los países de donde son los usuarios, más oscuros cuantos más clics",
            )}
            className="block h-auto w-full min-w-[520px]"
            onMouseLeave={() => setEncima(null)}
          >
            {PAISES_DEL_MUNDO.map((pais, i) => {
              const dato = pais.code ? porCodigo.get(pais.code) : undefined;
              return (
                <path
                  key={`${pais.code}-${i}`}
                  d={pais.d}
                  fill={
                    dato
                      ? tono(pasoDeColor(dato.clicks, maximo))
                      : "var(--surface-2)"
                  }
                  stroke="var(--surface)"
                  strokeWidth={0.4}
                  onMouseEnter={dato ? () => setEncima(pais.code) : undefined}
                  className={dato ? "cursor-help" : undefined}
                >
                  {dato && (
                    <title>{`${nombreDePais(dato.code, dato.name) ?? dato.name}: ${dato.clicks} ${tx("clics")}`}</title>
                  )}
                </path>
              );
            })}

            {/* Un punto en cada país con gente. No es adorno: a esta escala
                veinte de los países de Hattrick --Malta, Singapur, Hong Kong,
                las islas del Caribe-- no llegan a un píxel y no tienen silueta
                que pintar, y otros tantos son tan pequeños que el color no se
                distingue. El anillo del color del fondo los separa cuando dos
                caen casi encima. */}
            {situados.map((p) => {
              const centro = CENTROS_DE_PAIS[p.code];
              if (!centro) return null;
              return (
                <circle
                  key={p.code}
                  cx={centro[0]}
                  cy={centro[1]}
                  r={encima === p.code ? 6 : 4}
                  fill={tono(Math.max(2, pasoDeColor(p.clicks, maximo)))}
                  stroke="var(--surface)"
                  strokeWidth={1.5}
                  onMouseEnter={() => setEncima(p.code)}
                  className="cursor-help"
                >
                  <title>{`${nombreDePais(p.code, p.name) ?? p.name}: ${p.clicks} ${tx("clics")}`}</title>
                </circle>
              );
            })}
          </svg>
        </div>

        {/* La leyenda con los números que separan cada tono: «claro a oscuro»
            sin cifras no deja comparar dos mapas ni saber qué es «mucho». */}
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-[var(--muted)]">{tx("Clics")}</span>
            {TONOS.map((_, paso) => (
              <span key={paso} className="flex items-center gap-1">
                <span
                  aria-hidden
                  className="inline-block h-3 w-6 rounded-sm border border-[var(--border)]"
                  style={{ background: tono(paso) }}
                />
                <span className="text-xs tabular-nums text-[var(--muted)]">
                  {corteDeTono(paso, maximo)}+
                </span>
              </span>
            ))}
          </div>
          {/* Lo que el mapa no puede colocar, dicho y no escondido. */}
          {sinSitio && (
            <span className="text-xs text-[var(--muted)]">
              {tx("{{v0}} sin país conocido ({{v1}} clics)", {
                v0: sinSitio.users,
                v1: sinSitio.clicks,
              })}
            </span>
          )}
        </div>

        {/* La fila de detalle vive AQUÍ y no flotando sobre el mapa: un globo
            que sigue al ratón tapa justo el país de al lado, y en un móvil no
            hay ratón al que seguir. */}
        <p className="mt-2 min-h-[1.25rem] text-sm">
          {señalado ? (
            <span className="inline-flex items-center gap-2">
              <CountryFlag code={señalado.code} country={señalado.name} />
              <span className="font-medium">
                {nombreDePais(señalado.code, señalado.name) ?? señalado.name}
              </span>
              <span className="tabular-nums text-[var(--muted)]">
                {señalado.users === 1
                  ? tx("1 persona · {{v1}} clics · {{v2}} páginas", {
                      v1: cifra(señalado.clicks),
                      v2: cifra(señalado.pages),
                    })
                  : tx("{{v0}} personas · {{v1}} clics · {{v2}} páginas", {
                      v0: señalado.users,
                      v1: cifra(señalado.clicks),
                      v2: cifra(señalado.pages),
                    })}
              </span>
            </span>
          ) : (
            <span className="text-xs text-[var(--muted)]">
              {tx("Pasa el ratón por un país para ver su detalle.")}
            </span>
          )}
        </p>
      </div>

      {/* La misma información en tabla. No es un duplicado por gusto: un mapa
          no se lee con el teclado ni con un lector de pantalla, y con dos
          países del mismo tono los números son la única forma de ordenarlos. */}
      <div className="overflow-x-auto border-t border-[var(--border)]">
        <table className="w-full">
          <thead className="bg-[var(--surface-2)]">
            <tr>
              <th
                scope="col"
                className="px-3 py-2 text-left text-xs font-medium text-[var(--muted)]"
              >
                {tx("País")}
              </th>
              <th
                scope="col"
                className="px-3 py-2 text-right text-xs font-medium text-[var(--muted)]"
              >
                {tx("Personas")}
              </th>
              <th
                scope="col"
                className="px-3 py-2 text-right text-xs font-medium text-[var(--muted)]"
              >
                {tx("Sesiones")}
              </th>
              <th
                scope="col"
                className="px-3 py-2 text-right text-xs font-medium text-[var(--muted)]"
              >
                {tx("Páginas")}
              </th>
              <th
                scope="col"
                className="px-3 py-2 text-right text-xs font-medium text-[var(--muted)]"
              >
                {tx("Clics")}
              </th>
            </tr>
          </thead>
          <tbody>
            {paises.map((p) => (
              <tr
                key={p.code || "sin-pais"}
                onMouseEnter={() => setEncima(p.code || null)}
                className={`border-t border-[var(--border)] ${
                  encima && encima === p.code ? "bg-[var(--surface-2)]" : ""
                }`}
              >
                <td className="px-3 py-2 text-sm">
                  <span className="inline-flex items-center gap-2">
                    {p.code && <CountryFlag code={p.code} country={p.name} />}
                    {p.code
                      ? (nombreDePais(p.code, p.name) ?? p.name)
                      : tx("Sin país conocido")}
                  </span>
                </td>
                <td className="px-3 py-2 text-right text-sm tabular-nums">
                  {p.users}
                </td>
                <td className="px-3 py-2 text-right text-sm tabular-nums">
                  {p.sessions}
                </td>
                <td className="px-3 py-2 text-right text-sm tabular-nums">
                  {cifra(p.pages)}
                </td>
                <td className="px-3 py-2 text-right text-sm tabular-nums">
                  {cifra(p.clicks)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
