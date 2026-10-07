/** Lo que ha costado la gente parecida a un jugador tuyo.
 *
 *  ES UNA DESCRIPCIÓN DEL MERCADO, NO UNA PREDICCIÓN. Dice qué se pagó por
 *  jugadores que se le parecen, y no lo que te darían por él: no corrige por
 *  forma, experiencia, especialidad ni bonos de club de origen. Esa distinción
 *  la decidió el usuario y gobierna todo lo que se escribe aquí.
 *
 *  Tres cosas que la pantalla está obligada a decir, y por eso ocupan sitio:
 *
 *  · **Cuántas son todavía pujas.** Una venta entra con la puja de precio
 *    hasta que su subasta cierra, y la puja se queda corta: el 2026-10-05
 *    Valerio Cataldi tenía 65.000.000 de puja y cerró en 77.720.000, un 16%
 *    más. Un número hecho de pujas tira a bajo.
 *  · **Cuánto se parecen.** Del 100% (misma edad y mismas habilidades) al 75%.
 *    No es lo mismo un número sacado de gemelos que de primos lejanos.
 *  · **De cuándo son.** Una venta sigue contando pasadas las siete semanas si
 *    no apareció nada mejor, y entonces habla de un mercado que pudo cambiar.
 *
 *  No pide nada a Hattrick: todo sale del fondo que dejó el paso semanal, así
 *  que abrir y cerrar esto es gratis.
 */
import { Panel } from "./Panels";
import { DataTable } from "./DataTable";
import type { Column } from "./DataTable";
import { Specialty } from "./Specialty";
import { dateTime, money, number } from "../hooks/useFormat";
import { usePrecioComparable } from "../hooks/useTeam";
import { tx } from "../i18n/tx";
import { terminoOficial } from "../i18n/glosario";
import type { ComparableDeMercado, RasgoVisible } from "../services/api";

/** El nombre en español de cada habilidad, que es el respaldo del glosario.
 *  Sólo las seis que cuentan: la resistencia y el balón parado no entran en
 *  el parecido. */
const EN_ESPANOL: Record<string, string> = {
  keeper: "Portería",
  defending: "Defensa",
  playmaking: "Jugadas",
  winger: "Lateral",
  passing: "Pases",
  scoring: "Anotación",
};

/** «Anotación 18 · Pases 13 · Jugadas 7».
 *
 *  El nombre sale del glosario OFICIAL de Hattrick, no de una traducción
 *  nuestra: así el jugador lee exactamente la misma palabra que ve en el
 *  juego. Se calcula en el render y no en una constante del módulo para que
 *  cambie al vuelo cuando se cambia de idioma. */
function perfilLegible(perfil: RasgoVisible[]): string {
  return perfil
    .map(
      (r) =>
        `${terminoOficial("habilidades", r.habilidad, EN_ESPANOL[r.habilidad] ?? r.habilidad)} ${r.nivel}`,
    )
    .join(" · ");
}

/** El peso en color: el verde es un parecido de verdad. */
function colorDelPeso(peso: number): string {
  if (peso >= 100) return "text-[var(--ok)]";
  if (peso >= 85) return "text-[var(--text)]";
  return "text-[var(--muted)]";
}

/** El nombre oficial de una habilidad, para la cabecera de su columna. */
function nombreDeHabilidad(clave: string): string {
  return terminoOficial("habilidades", clave, EN_ESPANOL[clave] ?? clave);
}

/** Las columnas, armadas contra la terna del jugador que pregunta.
 *
 *  No son fijas porque la terna no lo es: a un delantero se le comparan
 *  anotación, pases y jugadas, y a un defensa otras tres. Como todos los
 *  comparables comparten la terna del objetivo --esa es la definición de
 *  comparable-- `perfil[i]` es la misma habilidad en todas las filas. */
function columnasDe(perfil: RasgoVisible[]): Column<ComparableDeMercado>[] {
  return [
    {
      key: "precio",
      header: tx("Se pagó"),
      align: "right",
      value: (f) => f.precio,
      render: (f) => (
        <span className="tabular-nums">
          {money(f.precio)}
          {!f.firme && (
            <span className="ml-1 text-xs text-[var(--warn)]">
              {tx("puja")}
            </span>
          )}
        </span>
      ),
    },
    {
      key: "peso",
      header: tx("Se parece"),
      align: "right",
      value: (f) => f.peso,
      render: (f) => (
        <span className={`tabular-nums ${colorDelPeso(f.peso)}`}>
          {f.peso}%
        </span>
      ),
    },
    {
      key: "nombre",
      header: tx("Jugador"),
      align: "left",
      value: (f) => f.nombre,
    },
    {
      key: "htPlayerId",
      header: "ID",
      // En crudo: es un nombre escrito con dígitos, no una cantidad que
      // nadie sume, así que no lleva separador de miles.
      raw: true,
      align: "right",
      value: (f) => f.htPlayerId,
    },
    {
      key: "edad",
      header: tx("Edad"),
      align: "right",
      value: (f) => f.edad,
    },
    ...perfil.map((rasgo, i) => ({
      key: `habilidad${i}`,
      header: nombreDeHabilidad(rasgo.habilidad),
      align: "right" as const,
      value: (f: ComparableDeMercado) => f.perfil[i]?.nivel ?? 0,
    })),
    {
      key: "especialidad",
      header: tx("Especialidad"),
      align: "left",
      value: (f) => f.especialidad,
      render: (f) => <Specialty specialty={f.especialidad} />,
    },
    {
      key: "cierra",
      header: tx("Cierra"),
      align: "right",
      // Lo ya cerrado al final cuando se ordena por esta columna: un plazo
      // que no existe no es «hace mucho», es que ya no aplica.
      value: (f) => (f.cierra ? new Date(f.cierra).getTime() : Infinity),
      render: (f) =>
        f.cierra ? (
          <span className="tabular-nums">{dateTime(f.cierra)}</span>
        ) : (
          <span className="text-[var(--muted)]">{tx("ya cerrada")}</span>
        ),
    },
    {
      key: "semanas",
      header: tx("Antigüedad"),
      align: "right",
      optional: true,
      value: (f) => f.semanas,
      render: (f) => (
        <span className={`tabular-nums ${f.viejo ? "text-[var(--warn)]" : ""}`}>
          {tx("hace {{v0}} semanas", { v0: number(f.semanas) })}
        </span>
      ),
    },
  ];
}

export function PrecioPorComparables({
  htPlayerId,
  activo = true,
}: {
  htPlayerId: number | null;
  /** Para no pedirlo mientras la pestaña está cerrada. */
  activo?: boolean;
}) {
  const consulta = usePrecioComparable(htPlayerId, { enabled: activo });
  const datos = consulta.data;

  if (consulta.isLoading || !datos) {
    return (
      <Panel title={tx("Lo que ha costado gente como él")}>
        <p className="px-4 py-3 text-sm text-[var(--muted)]">
          {consulta.isLoading ? tx("Cargando…") : tx("Sin datos todavía.")}
        </p>
      </Panel>
    );
  }

  const hayNumero = datos.media != null;

  return (
    <Panel
      title={tx("Lo que ha costado gente como él")}
      meta={
        <span className="text-xs text-[var(--muted)]">
          {perfilLegible(datos.perfil)}
        </span>
      }
    >
      <div className="px-4 py-3">
        {hayNumero ? (
          <>
            <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
              <div>
                <div className="text-xs uppercase tracking-wide text-[var(--muted)]">
                  {tx("Media")}
                </div>
                <div className="text-2xl font-semibold tabular-nums text-[var(--text)]">
                  {money(datos.media as number)}
                </div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wide text-[var(--muted)]">
                  {tx("Mediana")}
                </div>
                <div className="text-lg tabular-nums text-[var(--text)]">
                  {money(datos.mediana as number)}
                </div>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wide text-[var(--muted)]">
                  {/* «Se pagó» sólo cuando de verdad se pagó. Con las seis
                      subastas abiertas el panel decía «DE VERDAD SE PAGÓ
                      ENTRE 10.000 – 13.260.000» mientras cada fila ponía
                      «puja» al lado del número (2026-10-07). */}
                  {datos.provisionales > 0
                    ? tx("Ahora mismo, entre")
                    : tx("De verdad se pagó entre")}
                </div>
                <div className="text-lg tabular-nums text-[var(--text)]">
                  {money(datos.minimo as number)} –{" "}
                  {money(datos.maximo as number)}
                </div>
              </div>
            </div>
            <p className="mt-2 text-sm text-[var(--muted)]">
              {tx(
                "De {{v0}} ventas de jugadores parecidos. El que menos se parece cuenta un {{v1}}%.",
                { v0: number(datos.n), v1: datos.pesoMinimo },
              )}
            </p>
          </>
        ) : (
          <p className="text-sm text-[var(--text)]">
            {tx(
              "Todavía no hay bastantes ventas de jugadores parecidos: hay {{v0}} y hacen falta {{v1}} más.",
              { v0: number(datos.n), v1: number(datos.faltan) },
            )}
          </p>
        )}

        {datos.provisionales > 0 && (
          <p className="mt-2 text-sm text-[var(--warn)]">
            {datos.provisionales === 1
              ? tx(
                  "Una de ellas es una subasta todavía abierta, así que cuenta con la puja de ahora. Una puja se queda corta, y el número subirá cuando se cierre.",
                )
              : tx(
                  "{{v0}} de ellas son subastas todavía abiertas, así que cuentan con la puja de ahora. Una puja se queda corta, y el número subirá cuando se cierren.",
                  { v0: number(datos.provisionales) },
                )}
          </p>
        )}

        {datos.semanasDelMasViejo >= 7 && (
          <p className="mt-2 text-sm text-[var(--muted)]">
            {tx(
              "La venta más antigua es de hace {{v0}} semanas: sigue contando porque no ha aparecido nada más reciente.",
              { v0: number(datos.semanasDelMasViejo) },
            )}
          </p>
        )}
      </div>

      {datos.comparables.length > 0 && (
        <div className="px-4 pb-3">
          <DataTable
            rows={datos.comparables}
            columns={columnasDe(datos.perfil)}
            rowKey={(f) => f.htPlayerId}
            initialSort="precio"
            csvName="comparables"
            emptyMessage={tx("Sin ventas de jugadores parecidos todavía.")}
          />
        </div>
      )}

      <p className="px-4 py-3 text-xs leading-relaxed text-[var(--muted)]">
        {tx(
          "Esto dice lo que se pagó por otros, no lo que te darían a ti: no tiene en cuenta su forma, su experiencia, su especialidad ni el bono de club de origen del comprador.",
        )}
      </p>
    </Panel>
  );
}
