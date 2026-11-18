import { useState } from "react";
import { useTranslation } from "react-i18next";
import i18n from "../i18n";
import { Chart } from "../charts/Chart";
import {
  bandBetween,
  lineasDeUnGrupo,
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
import {
  clasificaciones,
  type ClaveDeClasificacion,
} from "../components/clases/clasificaciones";
import { COLOR } from "../components/clases/colores";
import { EnlaceATransparencia } from "../components/EnlaceATransparencia";
import {
  datosDeHabilidades,
  pestanaComparada,
  pestanaEnRejilla,
  pestanaDeLaPlantilla,
  pestanaDeUnGrupo,
  PLANTILLA,
  seriesDeLaPlantilla,
  type PestanaDibujada,
  type Poblacion,
} from "../components/habilidades/graficasPorGrupo";
import { HABILIDADES_EN_REJILLA } from "../config/flags";
import { SelectorMirarA } from "../components/habilidades/MirarA";
import {
  usePlayerClasses,
  useSeriesDeGrupos,
  useTeamOverview,
} from "../hooks/useTeam";
import { decimal, money, number } from "../hooks/useFormat";
import { usePersistido } from "../hooks/usePersistido";
import { tx } from "../i18n/tx";
import type { TeamOverviewGroup, TeamOverviewMetric } from "../services/api";

/**
 * Equipo, la plantilla promediada, semana a semana.
 *
 * Cuántas gráficas lleva cada grupo lo decide el backend (`charts`), porque
 * depende de si sus series comparten escala. Habilidades lleva dos: lo que se
 * mide de 0 a 20 arriba, y Resistencia y Forma, escalas mucho más cortas
 * aparte. TSI y Salario también, por ser un índice y dinero. Juntarlas en un
 * eje daría a entender que se comparan.
 *
 * «MIRAR A» (6.9.0 y 6.10.0): las pestañas con series pueden mirar a uno o
 * varios grupos de Clases de Jugador; ver `components/habilidades`.
 */
//: El grupo que ya no se pinta aquí, sino en Equipo (ver MejorPosicion).
const GRUPO_EN_EQUIPO = "best_position";

/** El color de un grupo en el lienzo de la gráfica, que no entiende
 *  `var(--…)`: se lee el valor del tema activo. Un grupo gris va en el color
 *  del texto, porque el gris es el de la plantilla entera de referencia. */
function colorDeLaLinea(css: string): string | undefined {
  const variable = /^var\((--[^)]+)\)$/.exec(
    css === COLOR.gris ? "var(--text)" : css,
  )?.[1];
  if (!variable) return css;
  if (typeof document === "undefined") return undefined;
  return (
    getComputedStyle(document.documentElement)
      .getPropertyValue(variable)
      .trim() || undefined
  );
}

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

function GroupLines({
  weeks,
  pestana,
}: {
  weeks: string[];
  pestana: PestanaDibujada;
}) {
  const { t } = useTranslation();
  if (weeks.length === 0) {
    return (
      <Empty>
        {t(
          "equipo.faltaCierre",
          "Hace falta más de un cierre semanal para dibujar la evolución.",
        )}
      </Empty>
    );
  }

  const { filas } = pestana;
  return (
    <div className="space-y-4 p-4">
      {filas.length > 0 && (
        <p className="text-xs text-[var(--muted)]">
          {filas.length === 1
            ? tx(
                "Bajo cada semana, cuántos jugadores del grupo entran en la media. Punteado: entre esas dos semanas cambió quién entra, así que ese salto no es entrenamiento.",
              )
            : tx(
                "Bajo cada semana, cuántos jugadores de cada grupo entran en su media, en su color. Punteado: ese grupo cambió quién entra, así que ese salto no es entrenamiento.",
              )}{" "}
          <EnlaceATransparencia seccion="clases" calculo="rentabilidad" />
        </p>
      )}
      {pestana.rejilla && (
        <LeyendaDeLaRejilla series={pestana.charts[0]?.series ?? []} />
      )}
      <div
        className={
          pestana.rejilla
            ? "grid gap-4 sm:grid-cols-2 xl:grid-cols-3 [&>*]:min-w-0"
            : "space-y-4"
        }
      >
        {pestana.charts.map((chart) => {
          // En la rejilla siempre la misma función: es la que respeta el gris
          // de la plantilla y los colores que lleva la leyenda única.
          const base =
            filas.length > 0 || pestana.rejilla
              ? lineasDeUnGrupo(weeks, chart.series, filas)
              : timelineOption(weeks, chart.series);
          // Las gráficas cuyas dos líneas miden lo mismo sobre poblaciones
          // distintas llevan `band`: el hueco entre ellas es una cantidad y se
          // sombrea. Las auxiliares se quedan fuera de la leyenda y del tooltip.
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
                    data: chart.series.map((s) => s.name),
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
                ariaLabel={
                  filas.length > 0
                    ? tx("{{titulo}}, media del grupo por semana", {
                        titulo: chart.title,
                      })
                    : t(
                        "equipo.graficaAria",
                        "{{titulo}}, media de la plantilla por semana",
                        { titulo: chart.title },
                      )
                }
                height={
                  pestana.rejilla
                    ? 200 + 16 * filas.length
                    : pestana.charts.length > 1
                      ? 260 + 16 * filas.length
                      : 340
                }
                option={{
                  ...base,
                  ...banded,
                  // En la rejilla la leyenda va una vez, arriba, y no en cada
                  // gráfica pequeña.
                  ...(pestana.rejilla ? { legend: { show: false } } : {}),
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
    </div>
  );
}

/** La leyenda única de la rejilla: un punto del color de cada línea y su
 *  nombre en tinta normal. La plantilla entera, en el gris de la gráfica. */
function LeyendaDeLaRejilla({
  series,
}: {
  series: { name: string; color?: string; reference?: boolean }[];
}) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
      {series.map((s) => (
        <li key={s.name} className="flex items-center gap-1.5">
          <span
            aria-hidden
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{ background: s.reference ? "#94a3b8" : s.color }}
          />
          {s.name}
        </li>
      ))}
    </ul>
  );
}

export function TeamOverviewPage() {
  const { t } = useTranslation();
  const { data, isLoading, isError, error } = useTeamOverview();
  const clases = usePlayerClasses();
  const [activeKey, setActiveKey] = useState<string | null>(null);

  // «Mirar a». Cada clasificación recuerda lo que tenía marcado. La 6.9.0
  // guardaba un solo grupo de Rentabilidad deportiva: si lo hay, es lo que
  // sale marcado la primera vez.
  const [clave, setClave] = usePersistido<ClaveDeClasificacion>(
    "habilidades.clasificacion",
    "rentabilidad",
  );
  const [marcadosPor, setMarcadosPor] = usePersistido<Record<string, string[]>>(
    "habilidades.marcados",
    {},
  );
  const [deLa690] = usePersistido<string>("habilidades.mirar-a", PLANTILLA);
  const [dato, setDato] = usePersistido<string>("habilidades.dato", "passing");

  const lista = clases.data ? clasificaciones(clases.data) : [];
  const activa =
    lista.find((c) => c.clave === clave && c.grupos.length > 0) ?? lista[0];
  const guardados = activa
    ? (marcadosPor[activa.clave] ??
      (activa.clave === "rentabilidad" ? [deLa690] : [PLANTILLA]))
    : [PLANTILLA];
  const validos = guardados.filter(
    (k) =>
      k === PLANTILLA ||
      activa?.grupos.some((g) => g.clave === k && g.jugadores.length > 0),
  );
  const marcados = validos.length > 0 ? validos : [PLANTILLA];
  const gruposMarcados = (activa?.grupos ?? []).filter((g) =>
    marcados.includes(g.clave),
  );
  const series = useSeriesDeGrupos(
    gruposMarcados.map((g) => g.jugadores.map((j) => j.htPlayerId)),
  );

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
  // Clasificación de jugadores salió de aquí el 2026-11-18: es su propio
  // módulo. Se filtra también aquí porque el resumen se guarda una vez por
  // sincronización, y uno guardado antes sigue trayendo la pestaña.
  const grupos = data.groups.filter(
    (g) => g.key !== GRUPO_EN_EQUIPO && g.chart !== "classes",
  );
  const active = grupos.find((g) => g.key === activeKey) ?? grupos[0];
  if (!active) return <Empty>{sincronizaMedias}</Empty>;

  const conSelector = active.chart === "line" && activa != null;
  const marcar = (k: string) => {
    if (!activa) return;
    const siguiente = marcados.includes(k)
      ? marcados.filter((x) => x !== k)
      : [...marcados, k];
    // Siempre queda algo marcado: sin nada no hay gráfica que enseñar.
    if (siguiente.length === 0) return;
    setMarcadosPor({ ...marcadosPor, [activa.clave]: siguiente });
  };

  // Lo marcado, en el orden de la clasificación y con la plantilla primero.
  const cargando = series.some((s) => !s.data);
  const fallo = series.find((s) => s.isError);
  const poblaciones: Poblacion[] = [
    ...(marcados.includes(PLANTILLA)
      ? [{ clave: PLANTILLA, nombre: tx("Plantilla entera"), serie: null }]
      : []),
    ...gruposMarcados.map((g, i) => ({
      clave: g.clave,
      nombre: g.nombre,
      color: colorDeLaLinea(g.color),
      serie: series[i]?.data ?? null,
    })),
  ];
  const unGrupo =
    conSelector && poblaciones.length === 1 && gruposMarcados.length === 1;
  const comparando = conSelector && poblaciones.length > 1;
  const plantilla = seriesDeLaPlantilla(data);
  const datos = datosDeHabilidades(active);

  // Con la rejilla encendida, una sola forma marque lo que se marque,
  // también sólo la plantilla entera (2026-11-18, pedido del usuario).
  const enRejilla = HABILIDADES_EN_REJILLA && conSelector;
  let pestana: PestanaDibujada = pestanaDeLaPlantilla(active);
  if (!cargando && enRejilla) {
    pestana = pestanaEnRejilla(active, poblaciones, plantilla);
  } else if (!cargando && unGrupo && poblaciones[0]?.serie) {
    pestana = pestanaDeUnGrupo(
      active,
      { ...poblaciones[0], serie: poblaciones[0].serie },
      plantilla,
    );
  } else if (!cargando && comparando) {
    pestana = pestanaComparada(active, poblaciones, plantilla, dato);
  }
  const elegido = unGrupo ? gruposMarcados[0] : undefined;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">
          {t("nav.equipo", "Habilidades")}
        </h1>
        <p className="text-sm text-[var(--muted)]">
          {elegido
            ? tx(
                "{{grupo}} de {{club}}: media de sus {{n}} jugadores de hoy, semana a semana.",
                {
                  grupo: elegido.nombre,
                  club: data.teamName,
                  n: elegido.jugadores.length,
                },
              )
            : comparando
              ? tx("{{grupos}}: una línea por grupo, semana a semana.", {
                  grupos: poblaciones.map((p) => p.nombre).join(" · "),
                })
              : t(
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

      {conSelector && activa && (
        <div className="space-y-1">
          <SelectorMirarA
            clasificaciones={lista}
            activa={activa}
            onClasificacion={setClave}
            marcados={marcados}
            onMarcar={marcar}
            dato={
              comparando && active.key === "skills" && !enRejilla
                ? {
                    opciones: datos,
                    activo: datos.some((d) => d.key === dato)
                      ? dato
                      : (datos[0]?.key ?? dato),
                    onChange: setDato,
                  }
                : undefined
            }
          />
          {elegido && (
            <p className="text-xs text-[var(--muted)]">
              {tx(
                "Hoy: {{nombres}}. Cada semana cuentan los que ya estaban en el club.",
                {
                  nombres: elegido.jugadores.map((j) => j.shortName).join(", "),
                },
              )}
            </p>
          )}
        </div>
      )}

      <Panel
        title={active.label}
        meta={
          active.chart === "line"
            ? comparando
              ? tx("{{semanas}} semana(s) · {{n}} grupos", {
                  semanas: active.weeks.length,
                  n: poblaciones.length,
                })
              : t(
                  "equipo.semanasJugadores",
                  "{{semanas}} semana(s) · {{n}} jugadores",
                  {
                    semanas: active.weeks.length,
                    n: elegido ? elegido.jugadores.length : data.playerCount,
                  },
                )
            : t("comun.nJugadores", "{{n}} jugadores", {
                n: data.playerCount,
              })
        }
      >
        {active.chart === "line" ? (
          fallo && conSelector ? (
            <ErrorState error={fallo.error} />
          ) : cargando && conSelector ? (
            <Loading />
          ) : (
            <GroupLines weeks={active.weeks} pestana={pestana} />
          )
        ) : active.metrics.length === 0 ? (
          <Empty>{sincronizaMedias}</Empty>
        ) : (
          <MetricBars group={active} currency={data.currency} />
        )}
        {active.chart === "line"
          ? pestana.note && <Note>{pestana.note}</Note>
          : active.note && <Note>{active.note}</Note>}
      </Panel>
    </div>
  );
}
