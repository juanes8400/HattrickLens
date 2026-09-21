import { Suspense, lazy } from "react";
import type { EChartsOption } from "echarts";

/**
 * La misma `Chart` de siempre, pero su motor de dibujo ya no viaja en el
 * paquete principal (2026-09-20).
 *
 * MEDIDO ANTES DE TOCAR NADA: el paquete común pesaba 1.711 kB (573 kB
 * comprimido) y la librería de gráficas era la mayor parte. Ese paquete lo
 * descarga TODO EL MUNDO antes de ver un solo píxel, incluso quien entra a
 * una pantalla sin una sola gráfica, porque el Panel importaba `Chart` y con
 * él la librería entera.
 *
 * Ahora la librería es su propio trozo y se pide cuando de verdad aparece una
 * gráfica. La pantalla pinta primero y la gráfica llega un momento después,
 * que es el orden correcto: el número que hay al lado ya se puede leer.
 *
 * `import type` no cuenta: TypeScript lo borra al compilar, así que los tipos
 * de la librería siguen disponibles en todas partes sin arrastrar su código.
 *
 * El hueco se reserva con la ALTURA EXACTA de la gráfica que viene. Sin eso,
 * la página daría un salto al llegar el trozo y lo que se estaba leyendo se
 * movería de sitio.
 */
const Motor = lazy(() =>
  import("./ChartECharts").then((m) => ({ default: m.ChartECharts })),
);

export function Chart(props: {
  option: EChartsOption;
  height?: number;
  /** Overrides theme auto-detection; normally left unset. */
  dark?: boolean;
  ariaLabel: string;
  /** Event handlers passed to ECharts (for example, clickable data points). */
  onEvents?: Record<string, (...args: unknown[]) => void>;
}) {
  return (
    <Suspense
      fallback={
        <div
          role="img"
          aria-label={props.ariaLabel}
          aria-busy="true"
          style={{ height: props.height ?? 280 }}
        />
      }
    >
      <Motor {...props} />
    </Suspense>
  );
}
