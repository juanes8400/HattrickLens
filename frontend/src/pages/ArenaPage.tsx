import { useState } from "react";
import { Link } from "react-router-dom";
import { Tabs } from "../components/Tabs";
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
import { money, number } from "../hooks/useFormat";
import { ApiError, type Arena, type ArenaTipo } from "../services/api";

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
  const [tipo, setTipo] = useState<ArenaTipo>("todos");
  const [season, setSeason] = useState<number | null>(null);
  const { data, isLoading, isError, error } = useArena(undefined, tipo, season);
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

  // LOS ÚLTIMOS TRES, EN PARALELO A LA MEDIA (2026-09-14, pedido del usuario):
  // la media de muchas temporadas tapa si el estadio se está llenando ahora.
  // Mismo cálculo --ocupación sobre el aforo total--, sólo con los tres
  // partidos más recientes del filtro elegido, que llegan en orden de fecha.
  const RECIENTES = 3;
  const recientes = data.matches.slice(-RECIENTES);
  const desdeRecientes = data.matches.length - recientes.length;
  const ocupacionReciente = recientes.length
    ? recientes.reduce((t, m) => t + m.occupancy, 0) / recientes.length
    : 0;
  const llenosRecientes = recientes.filter((m) => m.sold >= m.capacity).length;
  const diferencia = ocupacionReciente - data.avgOccupancy;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Estadio</h1>
        <p className="text-sm text-[var(--muted)]">
          Cuánta gente entra en cada partido, y si compensa ampliar
        </p>
        {data.capacityChangedOn && (
          <p className="text-xs text-[var(--muted)]">
            El aforo cambió: se cuenta desde el partido del{" "}
            {data.capacityChangedOn}.
          </p>
        )}
      </header>

      <div className="flex flex-wrap items-center gap-3">
        {/* Oficiales o amistosos (2026-09-13, pedido del usuario): un amistoso
            se llena de otra manera, y mezclarlos esconde los que cuentan. */}
        <Tabs
          modo="filtro"
          label="Qué partidos se miran"
          tabs={[
            { key: "todos", label: "Todos" },
            { key: "oficiales", label: "Oficiales" },
            { key: "amistosos", label: "Amistosos" },
          ]}
          active={tipo}
          onChange={(v) => setTipo(v as ArenaTipo)}
        />
        {/* Por temporada, el mismo selector que Partidos (2026-09-14). */}
        <select
          aria-label="Filtrar el estadio por temporada"
          value={season ?? "all"}
          onChange={(e) =>
            setSeason(e.target.value === "all" ? null : Number(e.target.value))
          }
          className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5 text-xs text-[var(--text)]"
        >
          <option value="all">Todas las temporadas</option>
          {data.availableSeasons.map((s) => (
            <option key={s} value={s}>
              {s === data.currentSeason
                ? `Temporada actual (${s})`
                : `Temporada ${s}`}
            </option>
          ))}
        </select>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5 [&>*]:min-w-0">
        <Kpi label="Aforo" value={number(data.capacityTotal)} />
        <Kpi
          label="Ocupación media"
          value={`${data.avgOccupancy.toFixed(1)}%`}
          hint={`sobre ${data.matchesAnalysed} partidos`}
        />
        {recientes.length > 0 && (
          <Kpi
            label={`Ocupación últimos ${recientes.length}`}
            value={`${ocupacionReciente.toFixed(1)}%`}
            hint={`${llenosRecientes} de ${recientes.length} llenos · ${
              diferencia >= 0 ? "+" : "−"
            }${Math.abs(diferencia).toFixed(1)} pp sobre la media`}
            tone={
              Math.abs(diferencia) < 0.05
                ? undefined
                : diferencia > 0
                  ? "positive"
                  : "danger"
            }
            ayuda="El mismo porcentaje de ocupación que la media, pero sólo con los tres partidos en casa más recientes del filtro elegido. Sus barras van en ámbar en la gráfica."
          />
        )}
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
                  m.tournament,
                  m.date,
                  `Ocupación: <b>${m.occupancy.toFixed(1)}%</b>`,
                  `${number(m.sold)} de ${number(m.capacity)} asientos`,
                  ...(i != null && i >= desdeRecientes
                    ? [`Uno de los últimos ${recientes.length}`]
                    : []),
                ].join("<br/>");
              },
            },
            series: [
              {
                name: "Ocupación",
                type: "bar",
                // Antes se pintaba de otro color el partido con algún sector
                // agotado, y eso era enseñar el desglose por sector con un
                // color en vez de con un número. El único color distinto que
                // queda es el de los tres últimos partidos (2026-09-14): dice
                // CUÁNDO se jugó, no quién se sentó dónde.
                data: data.matches.map((m, i) => ({
                  value: m.occupancy,
                  itemStyle: {
                    color: i >= desdeRecientes ? tonos.warning : tonos.accent,
                    borderRadius: 3,
                  },
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
                    ...(recientes.length > 0
                      ? [
                          {
                            yAxis: Number(ocupacionReciente.toFixed(1)),
                            lineStyle: {
                              type: "dashed" as const,
                              color: tonos.warning,
                            },
                            label: {
                              formatter: `últimos ${recientes.length}`,
                              position: "insideStartTop" as const,
                              color: tonos.warning,
                            },
                          },
                        ]
                      : []),
                  ],
                },
              },
            ],
          }}
          height={260}
        />
      </Panel>

      {/* Al final (2026-09-13): primero lo que pasa en cada partido, y
          después la decisión que se toma con eso. */}
      <CompensaAmpliar data={data} />
    </div>
  );
}

// Aquí vivía `SectorTable`: la tabla de sectores con lo vendido de media, su
// ocupación, las veces que se agotó y el precio de la entrada. Se retiró el
// 2026-09-01 porque el desglose de asistencia por sector es una función de HT
// Supporter y las reglas de CHPP prohíben replicarla. No se sustituye por una
// versión con totales: la tabla ERA el desglose.

/** ¿Compensa ampliar? El subtítulo lo prometía y la página no lo contestaba,
 *  aunque el servidor ya evaluaba tres ampliaciones (2026-09-13). Arriba el
 *  veredicto; debajo, las cuentas de cada opción. */
function CompensaAmpliar({ data }: { data: Arena }) {
  const opciones = data.expansionOptions;
  const composicion = data.composition ?? {};
  const aforo = Object.values(composicion).reduce((a, b) => a + b, 0);
  if (opciones.length === 0 && aforo === 0) return null;
  const sectores: [string, string][] = [
    ["general", "General"],
    ["preferentes", "Preferentes"],
    ["tribunas", "Tribunas"],
    ["palcos", "Palcos"],
  ];
  const viables = opciones
    .filter((o) => o.netPerSeason > 0 && o.paybackSeasons != null)
    .sort((a, b) => (a.paybackSeasons ?? 0) - (b.paybackSeasons ?? 0));
  const mejor = viables[0];
  const vacios = Math.round(
    data.matches.reduce((t, m) => t + m.emptySeats, 0) /
      (data.matches.length || 1),
  );
  const cur = data.currency;
  return (
    <Panel title="Ampliación del estadio" meta="estimado con tu llenado medio">
      <p className="prosa px-4 pt-4 text-sm">
        {mejor ? (
          <>
            <b>Sí, con matices:</b> {mejor.label} se amortizaría en unas{" "}
            {mejor.paybackSeasons!.toFixed(1)} temporadas.
          </>
        ) : (
          <>
            <b>No compensa ampliar.</b> Con un {data.avgOccupancy.toFixed(1)}%
            de ocupación sobran {number(vacios)} asientos de media, y ninguna
            ampliación paga siquiera su mantenimiento.
          </>
        )}
      </p>
      {aforo > 0 && (
        <div className="overflow-x-auto px-4 pt-4">
          <h3 className="mb-1 text-xs font-medium text-[var(--muted)]">
            Tu reparto de asientos frente al recomendado
          </h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-[var(--muted)]">
                <th className="py-1 pr-3 font-medium">Sector</th>
                <th className="py-1 pr-3 text-right font-medium">Asientos</th>
                <th className="py-1 pr-3 text-right font-medium">Tu reparto</th>
                <th className="py-1 pr-3 text-right font-medium">
                  Recomendado
                </th>
                <th className="py-1 pr-3 text-right font-medium">
                  Para cuadrarlo
                </th>
              </tr>
            </thead>
            <tbody>
              {sectores.map(([clave, nombre]) => {
                const tiene = composicion[clave] ?? 0;
                const parte = data.recommendedShares?.[clave] ?? 0;
                const diferencia = Math.round(parte * aforo - tiene);
                return (
                  <tr key={clave} className="border-t border-[var(--border)]">
                    <td className="py-1.5 pr-3">{nombre}</td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">
                      {number(tiene)}
                    </td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">
                      {((tiene / aforo) * 100).toFixed(1)}%
                    </td>
                    <td className="py-1.5 pr-3 text-right tabular-nums text-[var(--muted)]">
                      {(parte * 100).toFixed(1)}%
                    </td>
                    <td
                      className={`py-1.5 pr-3 text-right tabular-nums ${
                        Math.abs(diferencia) < aforo * 0.01
                          ? "text-[var(--muted)]"
                          : diferencia > 0
                            ? "text-[var(--positive)]"
                            : "text-[var(--danger)]"
                      }`}
                    >
                      {Math.abs(diferencia) < aforo * 0.01
                        ? "en su sitio"
                        : `${diferencia > 0 ? "+" : ""}${number(diferencia)}`}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <div className="overflow-x-auto p-4">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-[var(--muted)]">
              <th className="py-1 pr-3 font-medium">Opción</th>
              <th className="py-1 pr-3 text-right font-medium">Obra</th>
              <th className="py-1 pr-3 text-right font-medium">
                Mantenimiento/sem
              </th>
              <th className="py-1 pr-3 text-right font-medium">
                Ingreso extra/partido
              </th>
              <th className="py-1 pr-3 text-right font-medium">
                Neto por temporada
              </th>
            </tr>
          </thead>
          <tbody>
            {opciones.map((o) => (
              <tr key={o.label} className="border-t border-[var(--border)]">
                <td className="py-1.5 pr-3">{o.label}</td>
                <td className="py-1.5 pr-3 text-right tabular-nums">
                  {money(o.buildCost, cur)}
                </td>
                <td className="py-1.5 pr-3 text-right tabular-nums">
                  {money(o.addedWeeklyMaintenance, cur)}
                </td>
                <td className="py-1.5 pr-3 text-right tabular-nums">
                  {money(o.addedRevenuePerMatch, cur)}
                </td>
                <td
                  className={`py-1.5 pr-3 text-right tabular-nums ${
                    o.netPerSeason > 0
                      ? "text-[var(--positive)]"
                      : "text-[var(--danger)]"
                  }`}
                >
                  {money(o.netPerSeason, cur)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
