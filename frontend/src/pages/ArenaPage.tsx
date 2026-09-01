import { Link } from "react-router-dom";
import { Chart } from "../charts/Chart";
import { colores } from "../charts/colors";
import { useIsDarkTheme } from "../hooks/useTheme";
import {
  ErrorState,
  Kpi,
  Loading,
  Note,
  Panel,
  SinDatos,
} from "../components/Panels";
import { useArena } from "../hooks/useTeam";
import { number } from "../hooks/useFormat";
import { ApiError } from "../services/api";

/**
 * Estadio. HL-060, HL-063, HL-064.
 *
 * Sólo con lo que Hattrick hace público: cuánta gente entró en total en cada
 * partido y cuánto se recaudó.
 *
 * Hasta el 2026-09-01 la pantalla giraba alrededor del desglose POR SECTOR
 * --lo vendido en cada uno, su ocupación, cuáles se agotaron y una estimación
 * de la demanda que no cabía--. Eso es una función de HT Supporter y las
 * reglas de CHPP prohíben replicarla, así que se retiró entera: la tabla de
 * sectores, el KPI de sectores agotados, el coloreado de las barras y el aviso
 * de demanda censurada.
 *
 * Lo que sobrevive lo hace porque no necesita saber quién se sienta dónde: la
 * ocupación se mide contra el aforo total, y el simulador de ampliación sólo
 * usa los asientos que añadirías, su coste y el llenado medio.
 */
export function ArenaPage() {
  const { data, isLoading, isError, error } = useArena();
  const tonos = colores(useIsDarkTheme());

  if (isLoading) return <Loading />;
  if (isError) {
    if (error instanceof ApiError && error.status === 404) {
      return (
        <div className="space-y-4">
          <header>
            <h1 className="text-xl font-semibold">Estadio</h1>
            <p className="text-sm text-[var(--muted)]">
              Aún no hay asistencias detalladas para analizar.
            </p>
          </header>
          <Panel title="Preparar el análisis del estadio">
            <div className="space-y-3 p-4 text-sm text-[var(--muted)]">
              <p>
                La sincronización normal trae calendario y resultados. Para
                medir la asistencia y la recaudación hay que pedir los reportes
                detallados de tus partidos como local.
              </p>
              {/* 2026-08-15: la carga vive en Sincronización, junto al resto. */}
              <Link
                to="/sync"
                className="inline-block rounded-md border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--text)] hover:border-[var(--accent)]"
              >
                Cargar detalles de partidos en Sincronización
              </Link>
            </div>
          </Panel>
        </div>
      );
    }
    return <ErrorState error={error} />;
  }
  if (!data) return <SinDatos />;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Estadio</h1>
        <p className="text-sm text-[var(--muted)]">
          Cuánta gente entra en cada partido, y si compensa ampliar
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 [&>*]:min-w-0">
        <Kpi label="Aforo" value={number(data.capacityTotal)} />
        <Kpi
          label="Ocupación media"
          value={`${data.avgOccupancy.toFixed(1)}%`}
          hint={`sobre ${data.matchesAnalysed} partidos`}
        />
        {/* Aquí estaba «Ingresos». Se retiró el 2026-09-01 junto con el
            desglose por sector, porque salía ENTERO de él: se multiplicaban
            las entradas de cada sector por su precio. La taquilla por partido
            no llega por ningún otro sitio --el campo `revenue` existe pero
            nunca se rellena--, así que el KPI sólo podía decir 0 US$, que se
            lee como «no ingresaste nada» y es falso. Antes que un cero
            engañoso, nada. */}
        <Kpi
          label="Partidos analizados"
          value={String(data.matchesAnalysed)}
          hint="oficiales y amistosos; fuera torneos y preparación"
        />
        {/* Aquí estaba «Partidos con sector agotado». Se retiró el 2026-09-01
            con el resto del desglose: saber qué sector se llenó exige la
            asistencia por sector, que es función de HT Supporter. El asiento
            vacío medio sí se puede decir con totales. */}
        <Kpi
          label="Asientos vacíos de media"
          value={number(
            Math.round(
              data.matches.reduce((t, m) => t + m.emptySeats, 0) /
                (data.matches.length || 1),
            ),
          )}
          hint="sobre el aforo total"
        />
      </div>

      {data.notes.map((n, i) => (
        <Note key={i}>{n}</Note>
      ))}

      <Panel
        title="Ocupación por partido"
        meta={`media ${data.avgOccupancy.toFixed(1)}%`}
      >
        <Chart
          ariaLabel="Ocupación del estadio en cada partido como local, en porcentaje, por rival"
          option={{
            grid: {
              left: 8,
              right: 16,
              top: 16,
              bottom: 8,
              containLabel: true,
            },
            xAxis: {
              type: "category",
              // El RIVAL, no la fecha (pedido del usuario, 2026-09-01):
              // «Cauca CF» dice de qué partido hablamos y «16/08» no.
              data: data.matches.map((m) => m.rival),
              axisLabel: {
                fontSize: 10,
                // Los nombres de club son largos y desiguales. Se giran y se
                // recortan para que quepan sin pisarse; el nombre entero y la
                // fecha siguen en el tooltip.
                interval: 0,
                rotate: 35,
                width: 72,
                overflow: "truncate",
              },
            },
            yAxis: {
              type: "value",
              max: 100,
              axisLabel: { formatter: "{value}%" },
              splitLine: { lineStyle: { opacity: 0.15 } },
            },
            tooltip: {
              trigger: "axis",
              formatter: (params: unknown) => {
                const items = (Array.isArray(params) ? params : [params]) as {
                  dataIndex: number;
                }[];
                const i = items[0]?.dataIndex;
                const m = i == null ? undefined : data.matches[i];
                if (!m) return "";
                return [
                  `<b>${m.rival}</b>`,
                  m.date,
                  `Ocupación: <b>${m.occupancy.toFixed(1)}%</b>`,
                  `${number(m.sold)} de ${number(m.capacity)} asientos`,
                ].join("<br/>");
              },
            },
            series: [
              {
                name: "Ocupación",
                type: "bar",
                // Todas las barras iguales. Antes se pintaba de otro color el
                // partido con algún sector agotado, y eso era enseñar el
                // desglose por sector con un color en vez de con un número.
                data: data.matches.map((m) => ({
                  value: m.occupancy,
                  itemStyle: { color: tonos.accent, borderRadius: 3 },
                })),
                barMaxWidth: 42,
                markLine: {
                  silent: true,
                  symbol: "none",
                  data: [
                    {
                      yAxis: data.avgOccupancy,
                      lineStyle: { type: "dashed", color: tonos.muted },
                      label: { formatter: "media", position: "insideEndTop" },
                    },
                  ],
                },
              },
            ],
          }}
          height={260}
        />
      </Panel>
    </div>
  );
}

// Aquí vivía `SectorTable`: la tabla de sectores con lo vendido de media, su
// ocupación, las veces que se agotó y el precio de la entrada. Se retiró el
// 2026-09-01 porque el desglose de asistencia por sector es una función de HT
// Supporter y las reglas de CHPP prohíben replicarla. No se sustituye por una
// versión con totales: la tabla ERA el desglose.
