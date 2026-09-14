/**
 * La barra de tres tramos que enseña una predicción de partido.
 *
 * Nació en la pantalla de Liga y se extrajo aquí el 2026-09-08, pedido
 * explícitamente, para que Copa y Rivales enseñen la MISMA barra: el mismo
 * motor detrás tiene que verse igual en las tres, o el usuario tiene que
 * volver a aprender a leerla en cada pantalla.
 *
 * SIEMPRE DESDE TU LADO. Antes la barra iba coloreada por local y visitante:
 * verde el de casa, rojo el de fuera. Jugando de visitante, el verde era el
 * rival y el rojo eras tú, así que el color decía lo contrario de lo que
 * parecía. Aquí el verde eres tú y el rojo es el otro, juegues donde juegues.
 *
 * EL EMPATE ES OPCIONAL. En Copa no existe --hay prórroga y penaltis, alguien
 * pasa-- y pasar `empate` sin valor quita el tramo gris entero en vez de
 * pintarlo a cero, que dejaría un hueco raro con una etiqueta invisible.
 */
export type TramoDePrediccion = {
  label: string;
  value: number;
  color: string;
  tuyo: boolean;
};

export function BarraDePrediccion({
  tuLabel,
  tuValor,
  rivalLabel,
  rivalValor,
  empate,
}: {
  tuLabel: string;
  tuValor: number;
  rivalLabel: string;
  rivalValor: number;
  /** Sin esto no se pinta tramo de empate, el caso de Copa. */
  empate?: number;
}) {
  const tramos: TramoDePrediccion[] = [
    { label: tuLabel, value: tuValor, color: "var(--positive)", tuyo: true },
    ...(empate === undefined
      ? []
      : [
          {
            label: "Empate",
            value: empate,
            color: "var(--muted)",
            tuyo: false,
          },
        ]),
    {
      label: rivalLabel,
      value: rivalValor,
      color: "var(--danger)",
      tuyo: false,
    },
  ];

  return (
    <>
      <div className="flex h-6 overflow-hidden rounded">
        {tramos.map((b) => (
          <div
            key={b.label}
            className="flex items-center justify-center text-[10px] font-medium text-white"
            style={{ width: `${b.value * 100}%`, background: b.color }}
            title={`${b.label}: ${(b.value * 100).toFixed(1)}%`}
          >
            {/* Por debajo del 12 % el número no cabe dentro del tramo y sale
                cortado o encima del de al lado; la leyenda de abajo lo dice
                igual, así que aquí se calla. */}
            {b.value > 0.12 ? `${(b.value * 100).toFixed(0)}%` : ""}
          </div>
        ))}
      </div>

      {/* La leyenda no es adorno: sin ella los porcentajes se asocian a su
          equipo sólo por posición, y «Empate» no aparecía en ninguna parte
          salvo dentro del tooltip. */}
      <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs">
        {tramos.map((b) => (
          <span key={b.label} className="inline-flex items-baseline gap-1.5">
            <i
              className="inline-block h-2 w-2 shrink-0 translate-y-[-1px] rounded-full"
              style={{ background: b.color }}
            />
            <span className={b.tuyo ? "font-medium" : "text-[var(--muted)]"}>
              {b.label}
              {b.tuyo && <span className="text-[var(--muted)]"> (tú)</span>}
            </span>
            <b className="tabular-nums">{(b.value * 100).toFixed(0)}%</b>
          </span>
        ))}
      </div>
    </>
  );
}
