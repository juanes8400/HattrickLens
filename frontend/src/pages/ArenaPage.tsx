import { Link } from "react-router-dom";
import { Chart } from "../charts/Chart";
import { colores } from "../charts/colors";
import { useIsDarkTheme } from "../hooks/useTheme";
import { Column, DataTable } from "../components/DataTable";
import { ErrorState, Kpi, Loading, Note, Panel } from "../components/Panels";
import { useArena } from "../hooks/useTeam";
import { money, number } from "../hooks/useFormat";
import { ApiError, type Arena } from "../services/api";

/**
 * Estadio. HL-060, HL-061, HL-063, HL-064.
 *
 * Toda la pantalla gira alrededor de una distinción: lo que se vendió es un
 * hecho, lo que se habría vendido es una estimación, y sólo es estimable
 * cuando el sector NO se agotó. Un sector lleno no dice cuánta gente quería
 * entrar; dice cuántos asientos había.
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
                La sincronización normal trae calendario y resultados. Para medir asistencia,
                ocupación y demanda hay que pedir los reportes detallados de tus partidos como local.
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
  if (!data) return null;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Estadio</h1>
        <p className="text-sm text-[var(--muted)]">
          Asistencia, ocupación y demanda por sector
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi label="Aforo" value={number(data.capacityTotal)} />
        <Kpi
          label="Ocupación media"
          value={`${data.avgOccupancy.toFixed(1)}%`}
          hint={
            data.soldOutMatches > 0
              ? `suelo en ${data.soldOutMatches} de ${data.matchesAnalysed} partidos`
              : `sobre ${data.matchesAnalysed} partidos`
          }
        />
        <Kpi
          label="Ingresos"
          value={money(data.totalRevenue, data.currency)}
          hint={`${data.matchesAnalysed} partidos analizados`}
        />
        {/* 2026-08-15: aquí había "Dejado sobre la mesa" = ingreso con el
            estadio 100% lleno menos el real. Con 29% de ocupación media eso
            no es dinero perdido sino una fantasía: el límite es la demanda,
            no los asientos, y pintarlo en rojo sugería un problema que no
            existe. Se sustituye por el único hecho comprobable: en cuántos
            partidos se dejó gente fuera de verdad. */}
        <Kpi
          label="Partidos con sector agotado"
          value={`${data.soldOutMatches} de ${data.matchesAnalysed}`}
          hint={
            data.soldOutMatches > 0
              ? "ahí sí hubo demanda sin atender"
              : "nunca se llenó: sobran asientos, falta demanda"
          }
          tone={data.soldOutMatches > 0 ? "danger" : undefined}
        />
      </div>

      {data.notes.map((n, i) => (
        <Note key={i}>{n}</Note>
      ))}

      <Panel
        title="Sectores"
        meta={data.capacityIsReal ? "aforo real por sector" : "aforo derivado"}
      >
        <SectorTable data={data} />
      </Panel>

      <Panel
        title="Ocupación por partido"
        meta={`media ${data.avgOccupancy.toFixed(1)}%`}
      >
        <Chart ariaLabel="Ocupación del estadio por partido, en porcentaje"
          option={{
            grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
            xAxis: {
              type: "category",
              // Día y mes, no la fecha ISO entera: con ocho partidos el eje
              // era una fila de "2026-08-16" que nadie lee.
              data: data.matches.map((m) => m.date.slice(5).replace("-", "/")),
              axisLabel: { fontSize: 10 },
            },
            yAxis: {
              type: "value", max: 100,
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
                  `<b>${m.date}</b>`,
                  `Ocupación: <b>${m.occupancy.toFixed(1)}%</b>`,
                  `${number(m.sold)} de ${number(m.capacity)} asientos`,
                  m.soldOutSectors.length > 0
                    ? `Agotado: ${m.soldOutSectors.join(", ")}`
                    : "Ningún sector agotado",
                ].join("<br/>");
              },
            },
            series: [
              {
                name: "Ocupación",
                type: "bar",
                // Un partido con algún sector agotado se pinta distinto: ahí
                // la barra mide asientos, no demanda, y esa diferencia es
                // justo lo que decide si conviene ampliar.
                data: data.matches.map((m) => ({
                  value: m.occupancy,
                  itemStyle: {
                    color: m.soldOutSectors.length > 0
                      ? tonos.warning : tonos.accent,
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

function SectorTable({ data }: { data: Arena }) {
  type Row = Arena["sectors"][number];
  const columns: Column<Row>[] = [
    { key: "label", header: "Sector", value: (r) => r.label },
    {
      key: "capacity",
      header: "Aforo",
      align: "right",
      value: (r) => r.capacity,
      render: (r) => <span className="tabular-nums">{number(r.capacity)}</span>,
    },
    {
      key: "sold",
      header: "Vendido (media)",
      align: "right",
      value: (r) => r.soldAvg,
      render: (r) => <span className="tabular-nums">{number(r.soldAvg)}</span>,
    },
    {
      key: "occupancy",
      header: "Ocupación",
      align: "right",
      value: (r) => r.occupancy,
      // Barra dentro de la celda: comparar seis porcentajes en columna es
      // comparar seis longitudes, no leer seis números.
      render: (r) => (
        <span className="flex items-center justify-end gap-2">
          <span className="h-1.5 w-16 overflow-hidden rounded bg-[var(--surface-2)]">
            <span
              className="block h-full rounded"
              style={{
                width: `${Math.min(100, r.occupancy)}%`,
                background: r.demandIsCensored ? "var(--warning)" : "var(--accent)",
              }}
            />
          </span>
          <span className="tabular-nums">
            {r.occupancy.toFixed(1)}%{r.demandIsCensored && <span title="demanda censurada"> ↑</span>}
          </span>
        </span>
      ),
    },
    {
      key: "soldout",
      header: "Llenos",
      align: "right",
      value: (r) => r.timesSoldOut,
    },
    {
      key: "price",
      header: "Precio",
      align: "right",
      value: (r) => r.price,
      render: (r) => (
        <span className={r.priceIsVerified ? "tabular-nums" : "tabular-nums text-[var(--muted)]"}>
          {r.price}
          {!r.priceIsVerified && <span title="de la especificación, sin verificar"> *</span>}
        </span>
      ),
    },
    {
      key: "demand",
      header: "Demanda",
      value: (r) => (r.demandIsCensored ? "censurada" : "medible"),
      render: (r) =>
        r.demandIsCensored ? (
          <span className="text-[var(--danger)]">censurada</span>
        ) : (
          <span className="text-[var(--muted)]">medible</span>
        ),
    },
  ];
  return (
    <>
      <DataTable
        rows={data.sectors}
        columns={columns}
        rowKey={(r) => r.sector}
        csvName="sectores"
        filterPlaceholder="Filtrar sectores…"
      />
      <p className="border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
        La flecha ↑ marca los sectores donde la ocupación mostrada es un suelo: se agotaron,
        así que la cifra mide asientos y no demanda.
      </p>
    </>
  );
}
