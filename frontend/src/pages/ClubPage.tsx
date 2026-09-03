import { useState } from "react";
import { Chart } from "../charts/Chart";
import { timelineOption } from "../charts/chartOptions";
import {
  DateRangeFilter,
  useDateRangeFilter,
} from "../components/DateRangeFilter";
import {
  Empty,
  ErrorState,
  Kpi,
  Loading,
  Note,
  Panel,
  SinDatos,
} from "../components/Panels";
import { SerieConCausas } from "../components/SerieConCausas";
import type { Suceso } from "../components/SerieConCausas";
import { StaffRoleCard } from "../components/StaffRoleCard";
import { Tabs, PanelDePestanas } from "../components/Tabs";
import { useClub } from "../hooks/useTeam";
import { date, number } from "../hooks/useFormat";
import {
  trainerTrainingSpeedPct,
  trainingStaffLevelColor,
} from "../utils/staffEffects";
import { skillLevelLabel } from "../utils/skillLevels";
import { ventanaDeGraficas } from "../utils/ventanaDeGraficas";
import type { Club, PsychologyMatch } from "../services/api";

/**
 * Club y cuerpo técnico, en tres pestañas.
 *
 * Antes era una página corrida que mezclaba tres asuntos sin relación entre
 * sí: el ánimo del vestuario, quién trabaja en el club y cuánta gente va al
 * campo. Cada uno se mira en un momento distinto y por un motivo distinto.
 *
 * «Psicología» sustituye a la vieja gráfica «Ánimo competitivo», que ponía
 * espíritu y confianza sobre un mismo eje —con escalas distintas, 0-10 y
 * 0-9— y no decía por qué se movía ninguno de los dos.
 */

// Tokens y no colores fijos: el gris que había aquí medía 2,61 de
// contraste en modo CLARO, también por debajo del mínimo.
const VERDE = "var(--positive)";
const GRIS = "var(--muted)";
const ROJO = "var(--danger)";

type Seccion = "psicologia" | "tecnico" | "socios";

export function ClubPage() {
  const { data, isLoading, isError, error } = useClub();
  const [seccion, setSeccion] = useState<Seccion>("psicologia");

  // Timestamps ISO reales (no el "dd/mm/yyyy" de `date()`) para que el filtro
  // de rango compare fechas correctamente.
  const staffTimestamps = (data?.staffHistory ?? []).map((i) => i.capturedAt);
  const staffRange = useDateRangeFilter(staffTimestamps);

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return <SinDatos />;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Club y cuerpo técnico</h1>
        <p className="text-sm text-[var(--muted)]">
          Estado actual e histórico real de {data.teamName}.
        </p>
      </header>

      <Tabs
        grupo="club"
        label="Secciones de Club"
        tabs={[
          { key: "psicologia", label: "Psicología" },
          { key: "tecnico", label: "Cuerpo técnico" },
          { key: "socios", label: "Socios" },
        ]}
        active={seccion}
        onChange={(k) => setSeccion(k as Seccion)}
      />

      <PanelDePestanas grupo="club" activa={seccion} className="space-y-4">
        {seccion === "psicologia" && <Psicologia data={data} />}
        {seccion === "tecnico" && (
          <CuerpoTecnico data={data} rango={staffRange} />
        )}
        {seccion === "socios" && <Socios data={data} />}
      </PanelDePestanas>

      {/* Las notas son de la pantalla, no de una sección: van fuera. */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)]">
        {data.notes.map((note) => (
          <Note key={note}>{note}</Note>
        ))}
      </div>
    </div>
  );
}

/** La ventana que cubren las gráficas: el ancho real de los datos.
 *
 *  El cálculo vive en `ventanaDeGraficas` para poder probarlo sin montar la
 *  pantalla; aquí sólo se dice QUÉ series entran. Los días de mercado están
 *  en la lista a propósito: la gráfica los dibuja, así que el eje tiene que
 *  cubrirlos (ver el módulo). */
function ventana(data: Club): { from: string; to: string } {
  const psi = data.psychology;
  return ventanaDeGraficas({
    instantes: [
      ...psi.spirit.readings.map((r) => r.at),
      ...psi.confidence.readings.map((r) => r.at),
      ...psi.matches.map((m) => m.playedAt),
      ...data.supporterHistory.map((s) => s.capturedAt),
    ],
    dias: [...psi.sellDays, ...psi.buyDays].map((d) => d.day),
  });
}

function marcador(m: PsychologyMatch): string {
  return `${m.goalsFor}-${m.goalsAgainst}`;
}

function Psicologia({ data }: { data: Club }) {
  const psi = data.psychology;
  const { from, to } = ventana(data);
  const { current } = data;

  // Cada gráfica lleva SÓLO sus causas. Al espíritu lo mueve la actitud del
  // partido; a la confianza, el resultado. El manual las separa y mezclarlas
  // invitaría a leer una causa donde no la hay.
  const porActitud: Suceso[] = psi.matches.map((m) => ({
    at: m.playedAt,
    chip: m.attitudeLabel,
    color: m.attitude === -1 ? VERDE : m.attitude === 1 ? ROJO : GRIS,
    detail: `<b>${m.attitudeLabel ?? "actitud no leída"}</b> · ${m.rival} ${marcador(m)}`,
  }));
  const porResultado: Suceso[] = psi.matches.map((m) => ({
    at: m.playedAt,
    chip: null,
    color: m.result === "win" ? VERDE : m.result === "loss" ? ROJO : GRIS,
    detail:
      `<b>${m.result === "win" ? "Victoria" : m.result === "loss" ? "Derrota" : "Empate"} ` +
      `${marcador(m)}</b> · ${m.rival}`,
  }));

  const pic = psi.matches.filter((m) => m.attitude === -1).length;
  const normal = psi.matches.filter((m) => m.attitude === 0).length;
  const mots = psi.matches.filter((m) => m.attitude === 1).length;
  const ventas = psi.sellDays.reduce((t, d) => t + d.count, 0);
  const compras = psi.buyDays.reduce((t, d) => t + d.count, 0);

  return (
    <div className="space-y-4">
      <Panel
        title="Espíritu"
        meta="lo mueven la actitud del partido, el mercado y el % de entrenamiento"
      >
        <div className="flex flex-wrap items-baseline gap-4 border-b border-[var(--border)] px-4 py-3">
          <Kpi
            label="Ahora"
            value={
              current.spirit
                ? `${current.spirit.label} (${current.spirit.level})`
                : "Sin dato"
            }
          />
        </div>
        <div className="p-4">
          <SerieConCausas
            readings={psi.spirit.readings}
            movements={psi.spirit.movements}
            scale={psi.spirit.scale}
            equilibrium={psi.spirit.equilibrium}
            equilibriumLabel="tiende aquí"
            events={porActitud}
            eventsLabel="partidos"
            ariaLabel="Evolución del espíritu del equipo"
            buyDays={psi.buyDays}
            sellDays={psi.sellDays}
            height={190}
            from={from}
            to={to}
          />
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-[var(--border)] px-4 py-3 text-[11px] text-[var(--muted)]">
          <Punto color={VERDE} texto={`PIC · ${pic}`} />
          <Punto color={GRIS} texto={`Normal · ${normal}`} />
          <Punto color={ROJO} texto={`MOTS · ${mots}`} />
          <Punto color="var(--mercado-venta)" texto={`${ventas} ventas`} />
          <Punto color="var(--mercado-compra)" texto={`${compras} compras`} />
          <span className="italic">
            {psi.intensityDrops.length === 0
              ? "% de entrenamiento: sin bajarlo en el período"
              : `% de entrenamiento: ${psi.intensityDrops.length} bajada(s)`}
          </span>
        </div>
      </Panel>

      <Panel
        title="Confianza"
        meta="la mueven los resultados y los goles marcados"
      >
        <div className="flex flex-wrap items-baseline gap-4 border-b border-[var(--border)] px-4 py-3">
          <Kpi
            label="Ahora"
            value={
              current.confidence
                ? `${current.confidence.label} (${current.confidence.level})`
                : "Sin dato"
            }
          />
        </div>
        <div className="p-4">
          <SerieConCausas
            readings={psi.confidence.readings}
            movements={psi.confidence.movements}
            scale={psi.confidence.scale}
            equilibrium={psi.confidence.equilibrium}
            events={porResultado}
            eventsLabel="resultados"
            ariaLabel="Evolución de la confianza del equipo"
            color="var(--mercado-venta)"
            height={165}
            from={from}
            to={to}
          />
        </div>
      </Panel>
    </div>
  );
}

function Punto({ color, texto }: { color: string; texto: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <i
        className="inline-block h-2 w-2 rounded-full"
        style={{ background: color }}
      />
      {texto}
    </span>
  );
}

function CuerpoTecnico({
  data,
  rango,
}: {
  data: Club;
  rango: ReturnType<typeof useDateRangeFilter>;
}) {
  const { staff } = data;
  const hayHistorico = data.staffHistory.length > 1;
  const pick = <T,>(items: T[], indices: number[]) =>
    indices.map((i) => items[i] as T);

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 [&>*]:min-w-0">
        <Kpi
          label="Inversión juvenil"
          value={
            staff?.youthInvestment != null
              ? `${number(staff.youthInvestment)} ${staff.youthInvestmentCurrency}`.trim()
              : "Sin dato"
          }
          hint={
            staff?.youthInvestment != null
              ? `por semana · nivel juvenil ${staff.youthLevel}`
              : undefined
          }
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(18rem,0.72fr)] [&>*]:min-w-0">
        <Panel
          title="Cuerpo técnico"
          meta={staff ? `lectura ${date(staff.capturedAt)}` : "sin dato"}
        >
          {staff ? (
            <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3">
              {staff.roles.map((role) => (
                <StaffRoleCard key={role.key} role={role} />
              ))}
            </div>
          ) : (
            <Note>
              Sincroniza el club para ver el cuerpo técnico y su distribución.
            </Note>
          )}
        </Panel>

        <Panel title="Entrenador">
          {staff ? (
            <dl className="space-y-3 p-4 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-[var(--muted)]">Tipo</dt>
                <dd>{staff.trainer.typeLabel}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-[var(--muted)]">Nivel</dt>
                <dd
                  className={`font-semibold ${trainingStaffLevelColor(staff.trainer.skillLevel)}`}
                >
                  {staff.trainer.skillLevel}/5
                </dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-[var(--muted)]">Liderazgo</dt>
                <dd>
                  {skillLevelLabel(staff.trainer.leadership, true)} (
                  {staff.trainer.leadership})
                </dd>
              </div>
              <div className="flex justify-between gap-4 border-t border-[var(--border)] pt-3">
                <dt className="text-[var(--muted)]">
                  Velocidad de entrenamiento
                </dt>
                <dd className="font-medium text-[var(--positive)]">
                  {trainerTrainingSpeedPct(staff.trainer.skillLevel)}%
                </dd>
              </div>
            </dl>
          ) : (
            <Note>Sin datos de entrenador todavía.</Note>
          )}
        </Panel>
      </div>

      {hayHistorico && staff && (
        <Panel
          title="Evolución del staff"
          meta={`${data.staffHistory.length} lecturas`}
        >
          <div className="border-b border-[var(--border)] px-4 py-2">
            <DateRangeFilter
              range={rango.range}
              onChange={rango.setRange}
              min={rango.min}
              max={rango.max}
            />
          </div>
          <Chart
            ariaLabel="Evolución observada de niveles del cuerpo técnico, eje temporada-semana"
            option={timelineOption(
              pick(
                data.staffHistory.map(
                  (i) => i.seasonWeek ?? date(i.capturedAt),
                ),
                rango.indices,
              ),
              staff.roles.map((role) => ({
                name: role.label,
                values: pick(
                  data.staffHistory.map(
                    (i) => i.roles.find((r) => r.key === role.key)?.level ?? 0,
                  ),
                  rango.indices,
                ),
              })),
            )}
            height={280}
          />
        </Panel>
      )}
    </div>
  );
}

function Socios({ data }: { data: Club }) {
  const { from, to } = ventana(data);
  const { current } = data;
  const historia = data.supporterHistory;

  // Misma gramática que Psicología, y por el mismo motivo: la afición
  // reacciona a lo que pasa en el campo, así que la banda de arriba son los
  // resultados. Sin ellos, la línea de socios es una cifra que sube sola.
  const porResultado: Suceso[] = data.psychology.matches.map((m) => ({
    at: m.playedAt,
    chip: null,
    color: m.result === "win" ? VERDE : m.result === "loss" ? ROJO : GRIS,
    detail:
      `<b>${m.result === "win" ? "Victoria" : m.result === "loss" ? "Derrota" : "Empate"} ` +
      `${marcador(m)}</b> · ${m.rival}`,
  }));

  const socios = historia.map((h) => ({
    at: h.capturedAt,
    level: h.fanClubSize,
  }));
  const animo = historia.map((h) => ({
    at: h.capturedAt,
    level: h.supportersPopularity,
  }));

  // El motivo de cada tramo: los partidos que cayeron dentro.
  const movimientos = (serie: { at: string; level: number }[]) =>
    serie.slice(1).map((b, i) => {
      const a = serie[i]!;
      const dentro = data.psychology.matches.filter(
        (m) => m.playedAt > a.at && m.playedAt <= b.at,
      );
      return {
        at: b.at,
        from: a.level,
        to: b.level,
        delta: b.level - a.level,
        cause: dentro.length
          ? dentro
              .map(
                (m) =>
                  `${m.result === "win" ? "victoria" : m.result === "loss" ? "derrota" : "empate"} ${marcador(m)}`,
              )
              .join(", ")
              .replace(/^./, (c) => c.toUpperCase())
          : "Sin partido en medio",
      };
    });

  return (
    <div className="space-y-4">
      <Panel
        title="Socios"
        meta="la afición crece o se enfría con los resultados"
      >
        <div className="flex flex-wrap items-baseline gap-4 border-b border-[var(--border)] px-4 py-3">
          <Kpi
            label="Ahora"
            value={
              current.supporters?.fanClubSize != null
                ? number(current.supporters.fanClubSize)
                : "Sin dato"
            }
            hint={
              current.supporters
                ? `afición: ${current.supporters.popularityLabel}`
                : undefined
            }
          />
        </div>
        {historia.length > 1 ? (
          <div className="p-4">
            <SerieConCausas
              readings={socios}
              movements={movimientos(socios)}
              scale={null}
              events={porResultado}
              eventsLabel="resultados"
              ariaLabel="Evolución del número de socios"
              height={165}
              from={from}
              to={to}
            />
          </div>
        ) : (
          <Empty>Sin histórico todavía.</Empty>
        )}
      </Panel>

      <Panel
        title="Ánimo de la afición"
        meta="escala completa · de muy baja a poemas de amor"
      >
        {historia.length > 1 ? (
          <div className="p-4">
            <SerieConCausas
              readings={animo}
              movements={movimientos(animo)}
              scale={ESCALA_AFICION}
              events={porResultado}
              eventsLabel="resultados"
              ariaLabel="Evolución del ánimo de la afición"
              color="var(--mercado-compra)"
              height={175}
              from={from}
              to={to}
            />
          </div>
        ) : (
          <Empty>Sin histórico todavía.</Empty>
        )}
      </Panel>
    </div>
  );
}

/** Los diez peldaños de popularidad, con los nombres del juego. */
const ESCALA_AFICION = [
  { level: 0, label: "muy baja" },
  { level: 1, label: "furiosos" },
  { level: 2, label: "irritados" },
  { level: 3, label: "calmados" },
  { level: 4, label: "contentos" },
  { level: 5, label: "satisfechos" },
  { level: 6, label: "eufóricos" },
  { level: 7, label: "muy alta" },
  { level: 8, label: "bailando en las calles" },
  { level: 9, label: "poemas de amor" },
];
