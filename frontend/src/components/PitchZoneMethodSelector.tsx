/**
 * El selector de CÓMO se resumen varios partidos en un número por zona.
 *
 * Vivía dentro de la ficha de rival hasta el 2026-09-09, cuando Liga pasó a
 * ofrecer los mismos resúmenes. Sacarlo aquí no es aseo: si cada pantalla se
 * hiciera su propia lista, el día que se añada un método una se queda atrás y
 * las dos empiezan a describir los mismos partidos de maneras distintas.
 *
 * 2026-09-12: y por eso la EXPLICACIÓN vive aquí también. Hasta hoy cada
 * resumen se describía en el `title` del botón --invisible en un móvil, que
 * no tiene ratón-- y el mando salía en cinco sitios: Liga, los dos lados de
 * Copa y los dos de Rivales. Explicarlo en uno solo los habría dejado
 * contándolo distinto a los cuatro días.
 */
import type { PitchZoneMethod } from "../services/api";
import type { ResumenDeZonas } from "./pitchZoneMethods";
import { NOTA_DE_LOS_RESUMENES, PITCH_ZONE_METHODS } from "./pitchZoneMethods";

export function PitchZoneMethodSelector({
  method,
  onMethodChange,
  options = PITCH_ZONE_METHODS,
}: {
  method: PitchZoneMethod;
  onMethodChange: (v: PitchZoneMethod) => void;
  options?: ResumenDeZonas[];
}) {
  const elegido = options.find((o) => o.key === method);
  return (
    <div className="mt-2">
      <div className="flex flex-wrap overflow-hidden rounded border border-[var(--border)] text-xs">
        {options.map((o) => (
          <button
            key={o.key}
            title={o.short}
            onClick={() => onMethodChange(o.key)}
            className={`px-3 py-1 ${method === o.key ? "bg-[var(--accent)] text-white" : "bg-[var(--surface)]"}`}
          >
            {o.label}
          </button>
        ))}
      </div>
      {/* Lo que se está mirando AHORA, sin pedirlo. Que cambie al pulsar es
          media explicación por sí sola: se ve que los botones no son varias
          maneras de pintar lo mismo. */}
      {elegido && (
        <p className="prosa mt-1.5 text-[11px] leading-relaxed text-[var(--muted)]">
          {elegido.short}.
        </p>
      )}
      {/* Y el detalle, plegado: cabe en la tarjeta estrecha de Rivales, que
          lleva dos de estos mandos uno al lado del otro. */}
      <details className="mt-1 text-[11px] text-[var(--muted)]">
        <summary className="cursor-pointer select-none">
          cómo se saca cada número
        </summary>
        <dl className="prosa mt-1.5 space-y-1.5 leading-relaxed">
          {options.map((o) => (
            <div key={o.key}>
              <dt className="font-semibold text-[var(--text)]">{o.label}</dt>
              <dd>{o.long}</dd>
            </div>
          ))}
        </dl>
        <p className="prosa mt-2 leading-relaxed">{NOTA_DE_LOS_RESUMENES}</p>
      </details>
    </div>
  );
}
