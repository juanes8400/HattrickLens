import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Chart } from "../charts/Chart";
import { Column, DataTable } from "../components/DataTable";
import { ErrorState, Kpi, Loading, Note, Panel } from "../components/Panels";
import { TEAM_ID, useArena } from "../hooks/useTeam";
import { money, number } from "../hooks/useFormat";
import { api, ApiError, type Arena } from "../services/api";

/**
 * Estadio. HL-060, HL-061, HL-063, HL-064.
 *
 * Toda la pantalla gira alrededor de una distinción: lo que se vendió es un
 * hecho, lo que se habría vendido es una estimación, y sólo es estimable
 * cuando el sector NO se agotó. Un sector lleno no dice cuánta gente quería
 * entrar; dice cuántos asientos había.
 */
export function ArenaPage() {
  const [includeNonOfficial, setIncludeNonOfficial] = useState(false);
  const { data, isLoading, isError, error } = useArena(undefined, includeNonOfficial);
  const qc = useQueryClient();
  const syncDetails = useMutation({
    mutationFn: () => api.syncMatchDetails(TEAM_ID),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["arena", TEAM_ID] }),
  });

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
              <button
                onClick={() => syncDetails.mutate()}
                disabled={syncDetails.isPending}
                className="rounded-md border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--text)] hover:border-[var(--accent)] disabled:opacity-60"
              >
                {syncDetails.isPending ? "Cargando detalles de partidos…" : "Cargar detalles de partidos"}
              </button>
              {syncDetails.isError && <p className="text-[var(--danger)]">No se pudieron cargar: {String(syncDetails.error)}</p>}
              {syncDetails.isSuccess && (
                <p>
                  {syncDetails.data.matchesProcessed === 0
                    ? "No había partidos pendientes."
                    : `Procesados ${syncDetails.data.matchesProcessed} partido(s).`}
                  {syncDetails.data.errors.length > 0 && ` Errores: ${syncDetails.data.errors.join(" · ")}`}
                </p>
              )}
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
      <header className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Estadio</h1>
          <p className="text-sm text-[var(--muted)]">
            Asistencia, ocupación y demanda por sector
          </p>
        </div>
        <button
          onClick={() => setIncludeNonOfficial((v) => !v)}
          className={
            includeNonOfficial
              ? "shrink-0 rounded-md border border-[var(--accent)] px-3 py-1.5 text-xs text-[var(--accent)]"
              : "shrink-0 rounded-md border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--muted)] hover:text-[var(--text)]"
          }
        >
          {includeNonOfficial ? "Ocultar Escaleras/Duelos" : "Mostrar Escaleras/Duelos"}
        </button>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi label="Aforo" value={number(data.capacityTotal)} />
        <Kpi
          label="Ocupación media"
          value={`${data.avgOccupancy.toFixed(1)}%`}
          hint={
            data.demandIsCensored
              ? "es un suelo: hubo sectores agotados"
              : `sobre ${data.matchesAnalysed} partidos`
          }
        />
        <Kpi
          label="Ingresos"
          value={money(data.totalRevenue, data.currency)}
          hint={`${data.matchesAnalysed} partidos analizados`}
        />
        <Kpi
          label="Dejado sobre la mesa"
          value={money(data.revenueLeftOnTable, data.currency)}
          hint="con el estadio lleno en todos los partidos"
          tone={data.revenueLeftOnTable > 0 ? "danger" : "positive"}
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

      <Panel title="Ocupación por partido">
        <Chart ariaLabel="Ocupación del estadio por partido, en porcentaje"
          option={{
            xAxis: { type: "category", data: data.matches.map((m) => m.date) },
            yAxis: { type: "value", max: 100, axisLabel: { formatter: "{value}%" } },
            tooltip: { trigger: "axis" },
            series: [
              {
                name: "Ocupación",
                type: "bar",
                data: data.matches.map((m) => m.occupancy),
                itemStyle: { borderRadius: 3 },
                markLine: {
                  silent: true,
                  data: [{ yAxis: 100, lineStyle: { type: "dashed" } }],
                  label: { formatter: "lleno" },
                },
              },
            ],
          }}
          height={240}
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
      render: (r) => (
        <span className="tabular-nums">
          {r.occupancy.toFixed(1)}%{r.demandIsCensored && <span title="demanda censurada"> ↑</span>}
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
        así que la cifra mide asientos y no demanda. El asterisco marca precios que vienen de
        la especificación y no se han verificado contra tu pantalla.
      </p>
    </>
  );
}
