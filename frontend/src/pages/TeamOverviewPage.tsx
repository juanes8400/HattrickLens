import { useState } from "react";
import { useTranslation } from "react-i18next";
import i18n from "../i18n";
import { Chart } from "../charts/Chart";
import {
  bandBetween,
  timelineOption,
  withoutBandInTooltip,
} from "../charts/chartOptions";
import {
  Empty,
  ErrorState,
  Loading,
  Note,
  Panel,
  SinDatos,
} from "../components/Panels";
import { useTeamOverview } from "../hooks/useTeam";
import { decimal, money, number } from "../hooks/useFormat";
import type {
  TeamOverviewGroup,
  TeamOverviewMetric,
} from "../services/api";

/**
 * Equipo, la plantilla promediada, semana a semana.
 *
 * Cuántas gráficas lleva cada grupo lo decide el backend (`charts`), porque
 * depende de si sus series comparten escala. Habilidades lleva dos: lo que se
 * mide de 0 a 20 arriba, y Resistencia y Forma, escalas mucho más cortas
 * aparte. TSI y Salario también, por ser un índice y dinero. Juntarlas en un
 * eje daría a entender que se comparan.
 */
//: El grupo que ya no se pinta aquí, sino en Equipo (ver MejorPosicion).
const GRUPO_EN_EQUIPO = "best_position";

function formatValue(metric: TeamOverviewMetric, currency: string): string {
  switch (metric.display) {
    case "money":
      return money(Math.round(metric.value), currency);
    case "number":
      return number(Math.round(metric.value));
    case "count":
      return metric.value === 1
        ? i18n.t("comun.unJugador", "{{n}} jugador", {
            n: Math.round(metric.value),
          })
        : i18n.t("comun.nJugadores", "{{n}} jugadores", {
            n: Math.round(metric.value),
          });
    case "ratio":
      // Céntimos por punto de índice: con menos decimales todas las semanas
      // se verían iguales.
      return `${decimal(metric.value, 3)} ${currency}`;
    default:
      return `${decimal(metric.value, 1)} / ${Math.round(metric.scaleMax)}`;
  }
}

function MetricBars({
  group,
  currency,
}: {
  group: TeamOverviewGroup;
  currency: string;
}) {
  return (
    <div className="space-y-3 p-4">
      {group.metrics.map((metric) => {
        const pct =
          metric.scaleMax > 0
            ? Math.max(0, Math.min(100, (metric.value / metric.scaleMax) * 100))
            : 0;
        return (
          <div key={metric.key}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span>{metric.label}</span>
              <span className="tabular-nums font-semibold">
                {formatValue(metric, currency)}
              </span>
            </div>
            <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-[var(--surface-2)]">
              <div
                className="h-full rounded-full bg-[var(--accent)]"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function GroupLines({ group }: { group: TeamOverviewGroup }) {
  const { t } = useTranslation();
  if (group.weeks.length === 0) {
    return (
      <Empty>
        {t(
          "equipo.faltaCierre",
          "Hace falta más de un cierre semanal para dibujar la evolución.",
        )}
      </Empty>
    );
  }

  return (
    <div className="space-y-4 p-4">
      {group.charts.map((chart) => {
        const base = timelineOption(
          group.weeks,
          chart.series.map((s) => ({ name: s.label, values: s.values })),
        );
        // El backend marca con `band` las gráficas cuyas dos líneas miden lo
        // mismo sobre poblaciones distintas: ahí el hueco entre ellas es una
        // cantidad y se sombrea. Las auxiliares se quedan fuera de la leyenda
        // (`data`) y del tooltip.
        const [first, second] = chart.series;
        const banded =
          chart.band && first && second
            ? {
                series: [
                  ...bandBetween(first.values, second.values),
                  ...(base.series as Record<string, unknown>[]),
                ],
                legend: {
                  bottom: 0,
                  type: "scroll" as const,
                  data: chart.series.map((s) => s.label),
                },
                tooltip: withoutBandInTooltip(),
              }
            : {};
        return (
          <div key={chart.key}>
            {chart.title && (
              <div className="mb-1 text-xs font-medium text-[var(--muted)]">
                {chart.title}
              </div>
            )}
            <Chart
              ariaLabel={t(
                "equipo.graficaAria",
                "{{titulo}}, media de la plantilla por semana",
                { titulo: chart.title || group.label },
              )}
              height={group.charts.length > 1 ? 260 : 340}
              option={{
                ...base,
                ...banded,
                ...(chart.scaleMax != null
                  ? {
                      yAxis: {
                        type: "value" as const,
                        min: chart.scaleMin ?? 0,
                        max: chart.scaleMax,
                        splitLine: { lineStyle: { opacity: 0.15 } },
                      },
                    }
                  : {}),
              }}
            />
          </div>
        );
      })}
    </div>
  );
}

export function TeamOverviewPage() {
  const { t } = useTranslation();
  const { data, isLoading, isError, error } = useTeamOverview();
  const [activeKey, setActiveKey] = useState<string | null>(null);

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return <SinDatos />;

  const sincronizaMedias = t(
    "equipo.sincronizaMedias",
    "Sincroniza para calcular las medias de la plantilla.",
  );
  // «Mejor posición» se mudó a Equipo (2026-09-19, pedido del usuario): allí
  // se mira a quién se tiene y para qué puesto, aquí cómo evoluciona la
  // plantilla. El servidor la sigue calculando y la sigue mandando; lo que
  // cambia es quién la pinta.
  const grupos = data.groups.filter((g) => g.key !== GRUPO_EN_EQUIPO);
  const active = grupos.find((g) => g.key === activeKey) ?? grupos[0];
  if (!active) return <Empty>{sincronizaMedias}</Empty>;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">{t("nav.equipo", "Habilidades")}</h1>
        <p className="text-sm text-[var(--muted)]">
          {t(
            "equipo.intro",
            "Media de los {{n}} jugadores de {{club}}, semana a semana.",
            { n: data.playerCount, club: data.teamName },
          )}
        </p>
      </header>

      <div className="flex flex-wrap gap-1 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-1">
        {grupos.map((group) => (
          <button
            key={group.key}
            onClick={() => setActiveKey(group.key)}
            className={
              group.key === active.key
                ? "rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white"
                : "rounded-md px-3 py-1.5 text-sm text-[var(--muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text)]"
            }
          >
            {group.label}
          </button>
        ))}
      </div>

      <Panel
        title={active.label}
        meta={
          active.chart === "pending"
            ? t("equipo.porDefinir", "por definir")
            : active.chart === "line"
              ? t(
                  "equipo.semanasJugadores",
                  "{{semanas}} semana(s) · {{n}} jugadores",
                  { semanas: active.weeks.length, n: data.playerCount },
                )
              : t("comun.nJugadores", "{{n}} jugadores", {
                  n: data.playerCount,
                })
        }
      >
        {active.chart === "pending" ? (
          <Empty>
            {t(
              "equipo.sinContenido",
              "Esta pestaña todavía no tiene contenido.",
            )}
          </Empty>
        ) : active.chart === "line" ? (
          <GroupLines group={active} />
        ) : active.metrics.length === 0 ? (
          <Empty>{sincronizaMedias}</Empty>
        ) : (
          <MetricBars group={active} currency={data.currency} />
        )}
        {active.note && <Note>{active.note}</Note>}
      </Panel>
    </div>
  );
}
