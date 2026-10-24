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
import {
  leyendaDe,
  pasoDeColor,
  tono,
  valorDe,
} from "../utils/mapaDeUso";
import type { Magnitud, UsoPorPais } from "../utils/mapaDeUso";
import { usePersistido } from "../hooks/usePersistido";
import { tx } from "../i18n/tx";

/** De dónde es la gente y cuánto usa la aplicación, sobre el mapa.
 *
 *  2026-09-28, pedido del usuario. HT Lens se anuncia en foros de países muy
 *  distintos y no había forma de saber a cuáles llegó de verdad: la tabla de
 *  personas da nombres, no procedencias, y un nombre de Hattrick no dice el
 *  país. El país sale de la liga del club, que Hattrick ya publica; aquí no se
 *  mira de dónde viene la conexión ni se pregunta nada.
 *
 *  2026-10-23, pedido del usuario: EL COLOR VA POR PERSONAS. Nació por clics y
 *  la razón de entonces sigue siendo verdad --un país con cuatro managers que
 *  abren y cierran colorea menos que uno con dos que trabajan dentro-- pero no
 *  es la pregunta que este mapa contesta. «¿A qué países llegó HT Lens?» se
 *  contesta con gente; con clics, el país del autor se come el mapa entero y
 *  los demás quedan en el primer tono, porque una sola persona muy activa
 *  acumula más clics que cinco recién llegadas.
 *
 *  Las dos lecturas siguen estando, porque las dos eran buenas: el selector
 *  cambia lo que colorea. Lo que cambió es cuál sale al entrar.
 */

/** Se reexporta para que quien ya importaba el tipo de aquí siga igual; la
 *  aritmética del color vive en `utils/mapaDeUso`, donde se puede probar sin
 *  montar un mapa del mundo. */
export type { UsoPorPais } from "../utils/mapaDeUso";

/** Las dos lecturas, con su rótulo. Los rótulos se quedan aquí --y no en el
 *  módulo de aritmética-- porque son texto de pantalla, no cuentas. */
const MAGNITUDES = [
  { key: "users", label: tx("Personas") },
  { key: "clicks", label: tx("Clics") },
] as const;

export function MapaDeUso({ paises }: { paises: UsoPorPais[] }) {
  const [encima, setEncima] = useState<string | null>(null);
  // Persistido, como el plazo y «sin mis visitas»: es una forma de mirar, no
  // un estado de pantalla, y quien viene a ver personas las quiere ver manana
  // tambien.
  const [magnitud, setMagnitud] = usePersistido<Magnitud>(
    "uso.mapa.magnitud",
    "users",
  );
  const comoPersonas = magnitud === "users";

  // Sin código no hay sitio en el mapa: son las ligas internacionales y quien
  // se registró sin sincronizar nunca. Se cuentan aparte, no se esconden.
  const situados = paises.filter((p) => p.code);
  const sinSitio = paises.find((p) => !p.code);
  const porCodigo = new Map(situados.map((p) => [p.code, p]));
  const maximo = Math.max(...situados.map((p) => valorDe(p, magnitud)), 0);

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
  const leyenda = leyendaDe(situados, magnitud, maximo);
  // La tabla se ordena por LO MISMO que colorea el mapa. El servidor la manda
  // por clics; si el mapa pinta personas y la tabla ordena por clics, las dos
  // mitades del panel dicen cosas distintas sobre el mismo dato.
  const enOrden = [...paises].sort(
    (a, b) => valorDe(b, magnitud) - valorDe(a, magnitud) || b.users - a.users,
  );

  return (
    <Panel
      title={tx("De dónde es la gente")}
      meta={
        // Con un solo país «1 países» canta, y el sistema de textos traduce
        // frases enteras, no plurales.
        situados.length === 1 ? tx("1 país") : tx("{{v0}} países", { v0: situados.length })
      }
      acciones={
        // El selector va en la cabecera y no sobre el dibujo: encima del mapa
        // taparía un país, y aquí se lee antes de mirar, que es el orden en
        // que hace falta saber qué colorea.
        <div className="flex items-center gap-1" role="group" aria-label={tx("Qué colorea el mapa")}>
          {MAGNITUDES.map((m) => (
            <button
              key={m.key}
              onClick={() => setMagnitud(m.key)}
              aria-pressed={magnitud === m.key}
              data-track={`Uso: mapa por ${m.key}`}
              className={`rounded-md border px-2 py-1 text-xs ${
                magnitud === m.key
                  ? "border-[var(--accent)] text-[var(--accent)]"
                  : "border-[var(--border)] text-[var(--muted)]"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
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
            aria-label={
              comoPersonas
                ? tx(
                    "Mapa del mundo con los países de donde son los usuarios, más oscuros cuanta más gente",
                  )
                : tx(
                    "Mapa del mundo con los países de donde son los usuarios, más oscuros cuantos más clics",
                  )
            }
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
                      ? tono(pasoDeColor(valorDe(dato, magnitud), maximo))
                      : "var(--surface-2)"
                  }
                  stroke="var(--surface)"
                  strokeWidth={0.4}
                  onMouseEnter={dato ? () => setEncima(pais.code) : undefined}
                  className={dato ? "cursor-help" : undefined}
                >
                  {dato && (
                    <title>{`${nombreDePais(dato.code, dato.name) ?? dato.name}: ${valorDe(dato, magnitud)} ${comoPersonas ? tx("personas") : tx("clics")}`}</title>
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
                  fill={tono(Math.max(2, pasoDeColor(valorDe(p, magnitud), maximo)))}
                  stroke="var(--surface)"
                  strokeWidth={1.5}
                  onMouseEnter={() => setEncima(p.code)}
                  className="cursor-help"
                >
                  <title>{`${nombreDePais(p.code, p.name) ?? p.name}: ${valorDe(p, magnitud)} ${comoPersonas ? tx("personas") : tx("clics")}`}</title>
                </circle>
              );
            })}
          </svg>
        </div>

        {/* La leyenda con los números que separan cada tono: «claro a oscuro»
            sin cifras no deja comparar dos mapas ni saber qué es «mucho». */}
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-[var(--muted)]">
              {comoPersonas ? tx("Personas") : tx("Clics")}
            </span>
            {leyenda.map(([paso, desde]) => (
              <span key={paso} className="flex items-center gap-1">
                <span
                  aria-hidden
                  className="inline-block h-3 w-6 rounded-sm border border-[var(--border)]"
                  style={{ background: tono(paso) }}
                />
                <span className="text-xs tabular-nums text-[var(--muted)]">
                  {desde}+
                </span>
              </span>
            ))}
          </div>
          {/* Lo que el mapa no puede colocar, dicho y no escondido. */}
          {sinSitio && (
            <span className="text-xs text-[var(--muted)]">
              {tx("{{v0}} sin país conocido ({{v1}} clics)", {
                v0: sinSitio.users,
                v1: cifra(sinSitio.clicks),
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
            {enOrden.map((p) => (
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
