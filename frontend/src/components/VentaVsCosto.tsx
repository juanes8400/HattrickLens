/** «Precio de venta vs costo» de un jugador, semana a semana.
 *
 *  2026-11-21, pedido y definido por el usuario para el Comparador de
 *  transferencias. Dos líneas en el mismo eje desde su llegada:
 *
 *  · el COSTO acumulado --compra o ascenso, sueldos e intentos de venta--, el
 *    mismo «Costo hasta ahora» de Plantilla actual; sube a escalones con cada
 *    sueldo;
 *  · el PRECIO DE VENTA: el precio por comparables de esa semana menos la
 *    comisión del agente de entonces. Antes de la primera lectura de precio
 *    no hay línea, y se dice.
 *
 *  Donde se cruzan está el precio de equilibrio. El hueco va en verde donde la
 *  venta supera al costo (ganarías) y en ámbar donde no (perderías).
 */
import type { EChartsOption } from "echarts";
import { Chart } from "../charts/Chart";
import { date, money } from "../hooks/useFormat";
import { useVentaVsCosto } from "../hooks/useTeam";
import { tx } from "../i18n/tx";
import { Empty } from "./Panels";
import { TerminoEquilibrio } from "./PrecioDeEquilibrio";

const COLOR_VENTA = "#378ADD";
const COLOR_GANA = "rgba(99, 153, 34, 0.28)";
const COLOR_PIERDE = "rgba(239, 159, 39, 0.3)";

export function VentaVsCosto({ htPlayerId }: { htPlayerId: number }) {
  const { data, isLoading, isError } = useVentaVsCosto(htPlayerId);
  if (isLoading) return <Empty>{tx("Cargando…")}</Empty>;
  if (isError || !data) {
    return <Empty>{tx("No se pudo calcular el costo de este jugador.")}</Empty>;
  }
  // UN PUNTO POR SEMANA: el de hoy y el último semanal pueden caer en la
  // misma, y el eje repetiría la etiqueta. Manda el más reciente.
  const puntos = data.puntos.filter(
    (p, i, todos) => p.semana == null || todos[i + 1]?.semana !== p.semana,
  );
  if (puntos.length === 0) {
    return (
      <Empty>
        {tx(
          "Sólo para jugadores que siguen en tu club y de los que se sabe cuándo llegaron.",
        )}
      </Empty>
    );
  }
  const hoy = puntos[puntos.length - 1]!;
  const equilibrio =
    hoy.comision != null && hoy.comision < 1
      ? Math.ceil(hoy.costo / (1 - hoy.comision))
      : null;
  const sinPrecio = puntos.findIndex((p) => p.venta != null);

  // EL EJE VA EN SEMANAS «TT-ss», como la gráfica de «Precio» (7.0.2,
  // pedido del usuario). La fecha sólo si falta el calendario.
  const fechas = puntos.map((p) => p.semana ?? date(p.fecha));
  const costo = puntos.map((p) => p.costo);
  const venta = puntos.map((p) => p.venta);
  // EL HUECO ENTRE LAS DOS LÍNEAS, un rectángulo por semana con precio: de
  // esa semana a la siguiente, entre el precio de venta y el costo. Verde si
  // la venta va por encima (ganarías), ámbar si va por debajo (perderías).
  //
  // RECTÁNGULOS Y NO UN ÁREA APILADA (7.0.2): ECharts no dibuja una serie
  // apilada que empieza con huecos, y aquí todas empiezan así --el costo
  // existe desde la llegada y el precio llega después--. En la 7.0.0 la
  // franja no salía.
  const hueco = puntos.flatMap((p, i) => {
    const siguiente = fechas[i + 1];
    if (p.venta == null || siguiente == null) return [];
    const gana = p.venta >= p.costo;
    return [
      [
        {
          xAxis: fechas[i],
          yAxis: Math.min(p.venta, p.costo),
          itemStyle: { color: gana ? COLOR_GANA : COLOR_PIERDE },
        },
        { xAxis: siguiente, yAxis: Math.max(p.venta, p.costo) },
      ],
    ];
  });
  const fmt = (v: number) => money(v, data.moneda);

  const option: EChartsOption = {
    grid: { left: 70, right: 16, top: 16, bottom: 32 },
    tooltip: {
      trigger: "axis",
      valueFormatter: (v) => (typeof v === "number" ? fmt(v) : "—"),
    },
    xAxis: { type: "category", data: fechas, boundaryGap: false },
    yAxis: {
      type: "value",
      // DESDE 0, SIEMPRE (2026-11-22, pedido del usuario): con el eje
      // recortado una diferencia pequeña entre venta y costo parecía enorme.
      min: 0,
      axisLabel: {
        formatter: (v: number) => `${(v / 1_000_000).toFixed(1)} M`,
      },
    },
    series: [
      {
        name: tx("Costo acumulado"),
        type: "line",
        step: "end",
        data: costo,
        symbol: "none",
        lineStyle: { width: 2, color: "#888780" },
        itemStyle: { color: "#888780" },
        markArea: { silent: true, data: hueco as never },
      },
      {
        name: tx("Precio de venta"),
        type: "line",
        data: venta,
        symbolSize: 8,
        lineStyle: { width: 2, color: COLOR_VENTA },
        itemStyle: { color: COLOR_VENTA },
        connectNulls: false,
      },
    ],
  };

  return (
    <div className="space-y-2">
      <div className="grid gap-3 sm:grid-cols-3 [&>*]:min-w-0">
        <div>
          <div
            className="text-xs text-[var(--muted)]"
            title={tx(
              "El precio por comparables de hoy menos la comisión que se llevaría el agente si lo vendieras ahora.",
            )}
          >
            {tx("Precio de venta hoy")}
          </div>
          <div
            className="text-lg font-medium tabular-nums"
            style={{ color: COLOR_VENTA }}
          >
            {hoy.venta != null ? fmt(hoy.venta) : "—"}
          </div>
          {hoy.precio != null && hoy.comision != null && (
            <div className="text-xs text-[var(--muted)]">
              {tx("precio {{v0}} − {{v1}}% del agente", {
                v0: fmt(hoy.precio),
                v1: Math.round(hoy.comision * 100),
              })}
            </div>
          )}
        </div>
        <div>
          <div className="text-xs text-[var(--muted)]">
            {tx("Costo hasta ahora")}
          </div>
          <div className="text-lg font-medium tabular-nums">
            {fmt(hoy.costo)}
          </div>
          <div className="text-xs text-[var(--muted)]">
            {tx("compra, sueldos e intentos de venta")}
          </div>
        </div>
        <div>
          <div className="text-xs text-[var(--muted)]">
            <TerminoEquilibrio>{tx("Precio de equilibrio")}</TerminoEquilibrio>
          </div>
          <div className="text-lg font-medium tabular-nums">
            {equilibrio != null ? fmt(equilibrio) : "—"}
          </div>
          {equilibrio != null && hoy.precio != null && (
            <div
              className="text-xs"
              style={{
                color:
                  hoy.precio >= equilibrio
                    ? "var(--positive)"
                    : "var(--warning)",
              }}
            >
              {hoy.precio >= equilibrio
                ? tx("su precio ya lo supera")
                : tx("le faltan {{v0}} de precio", {
                    v0: fmt(equilibrio - hoy.precio),
                  })}
            </div>
          )}
        </div>
      </div>
      <Chart
        height={230}
        ariaLabel={tx(
          "Precio de venta frente al costo acumulado, semana a semana",
        )}
        option={option}
      />
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--muted)]">
        <span>
          <span
            className="mr-1 inline-block h-0.5 w-3 align-middle"
            style={{ background: "#888780" }}
          />
          {tx("Costo acumulado")}
        </span>
        <span>
          <span
            className="mr-1 inline-block h-0.5 w-3 align-middle"
            style={{ background: COLOR_VENTA }}
          />
          {tx("Precio de venta")}
        </span>
        <span>
          <span
            className="mr-1 inline-block h-2.5 w-2.5 align-middle"
            style={{ background: COLOR_PIERDE }}
          />
          {tx("perderías")}
        </span>
        <span>
          <span
            className="mr-1 inline-block h-2.5 w-2.5 align-middle"
            style={{ background: COLOR_GANA }}
          />
          {tx("ganarías")}
        </span>
      </div>
      {sinPrecio !== 0 && (
        <p className="text-xs text-[var(--muted)]">
          {sinPrecio < 0
            ? tx(
                "Todavía no hay precio por comparables de este jugador: sólo se ve lo que lleva costado.",
              )
            : tx(
                "Hasta la semana {{v0}} no había precio por comparables: antes sólo se ve el costo.",
                {
                  v0:
                    puntos[sinPrecio]!.semana ?? date(puntos[sinPrecio]!.fecha),
                },
              )}
        </p>
      )}
    </div>
  );
}
