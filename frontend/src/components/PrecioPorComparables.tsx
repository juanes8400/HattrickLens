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
import { money, number } from "../hooks/useFormat";
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

function Comparable({ fila }: { fila: ComparableDeMercado }) {
  return (
    <tr className="border-t border-[var(--border)]">
      <td className="py-1.5 pr-3">
        <div className="text-[var(--text)]">{fila.nombre}</div>
        <div className="text-xs text-[var(--muted)]">
          {fila.edad} · {perfilLegible(fila.perfil)}
        </div>
      </td>
      <td
        className={`py-1.5 pr-3 text-right tabular-nums ${colorDelPeso(fila.peso)}`}
      >
        {fila.peso}%
      </td>
      <td className="py-1.5 text-right tabular-nums text-[var(--text)]">
        {money(fila.precio)}
        {!fila.firme && (
          <span className="ml-1 text-xs text-[var(--warn)]">{tx("puja")}</span>
        )}
        {fila.viejo && (
          <div className="text-xs text-[var(--muted)]">
            {tx("hace {{v0}} semanas", { v0: fila.semanas })}
          </div>
        )}
      </td>
    </tr>
  );
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
                  {tx("De verdad se pagó entre")}
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
        <table className="w-full px-4 text-sm">
          <thead>
            <tr className="text-xs uppercase tracking-wide text-[var(--muted)]">
              <th className="px-4 py-1 text-left font-medium">{tx("Quién")}</th>
              <th className="py-1 pr-3 text-right font-medium">
                {tx("Se parece")}
              </th>
              <th className="px-4 py-1 text-right font-medium">
                {tx("Se pagó")}
              </th>
            </tr>
          </thead>
          <tbody className="px-4">
            {datos.comparables.map((fila) => (
              <Comparable key={fila.htPlayerId} fila={fila} />
            ))}
          </tbody>
        </table>
      )}

      <p className="px-4 py-3 text-xs leading-relaxed text-[var(--muted)]">
        {tx(
          "Esto dice lo que se pagó por otros, no lo que te darían a ti: no tiene en cuenta su forma, su experiencia, su especialidad ni el bono de club de origen del comprador.",
        )}
      </p>
    </Panel>
  );
}
