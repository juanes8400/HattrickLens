import { useEffect, useState } from "react";
import { Column, DataTable } from "../components/DataTable";
import { CanchaDelReparto } from "../components/CanchaDelReparto";
import { lecturaDeNivel } from "../utils/skillLevels";
import { Empty, ErrorState, Kpi, Loading, Note, Panel } from "../components/Panels";
import {
  useAcademy,
  useAcademySkillScores,
  useAcademyTrainingPlan,
} from "../hooks/useTeam";
import { date, decimal, htAge, money } from "../hooks/useFormat";
import type { Academy, AcademySkillScores, TrainingSlot } from "../services/api";

/** CHPP nombra las habilidades en inglés; la app habla español en todas las
 *  demás pantallas. */
const SKILL_NAMES: Record<string, string> = {
  keeper: "Portero",
  defending: "Defensa",
  playmaking: "Jugadas",
  winger: "Lateral",
  passing: "Pases",
  scoring: "Anotación",
  set_pieces: "Balón parado",
};

/** Las habilidades juveniles llegan a 8 como mucho antes de la promoción, así
 *  que ésa es la escala de la barra — no la de 0-20 del primer equipo, que
 *  dejaría a todos los canteranos pegados al suelo. */

/** Los pesos van de decenas a milésimas según la base, así que no hay un
 *  número fijo de decimales que sirva para todos: se elige por magnitud. */
const formatWeight = (w: number | undefined) =>
  w == null ? "" : w >= 10 ? w.toFixed(0) : w >= 1 ? w.toFixed(1) : w.toFixed(3);

/** Las tres vistas de la cantera. "Plantilla" abre por defecto: es la que
 *  responde "¿a quién tengo?", y las otras dos sólo tienen sentido después. */
const VIEWS = [
  { key: "squad", label: "Plantilla juvenil" },
  { key: "train", label: "Qué entrenar" },
  { key: "who", label: "A quién entrenar" },
  { key: "ceilings", label: "Techos de habilidad" },
] as const;

type ViewKey = (typeof VIEWS)[number]["key"];

const CATEGORY_TONE: Record<string, string> = {
  "sin ojear": "text-[var(--muted)]",
  crack: "text-[var(--positive)]",
  promesa: "text-[var(--positive)]",
  aceptable: "",
  vendible: "text-[var(--muted)]",
  fontanero: "text-[var(--danger)]",
};

/**
 * Juveniles. HL-110, HL-111, HL-112, HL-114, HL-115.
 *
 * Dos cosas que esta pantalla hace y Hattrick Control no: cruzar lo invertido
 * con lo ingresado (viven en pantallas distintas y nunca se encuentran), y
 * distinguir un techo *desconocido* de un techo *bajo*. Descartar a un
 * canterano porque el ojeador aún no ha mirado sería confundir ignorancia con
 * evidencia.
 */
export function AcademyPage() {
  const { data, isLoading, isError, error } = useAcademy();
  const [view, setView] = useState<ViewKey>("squad");

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return null;

  const profitable = data.net > 0;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Juveniles</h1>
        <p className="text-sm text-[var(--muted)]">
          Quién merece plaza, quién se pierde pronto y si la academia sale a cuenta
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi label="Canteranos" value={String(data.squadSize)} />
        <Kpi
          label="Invertido"
          value={money(data.invested, data.currency)}
          hint={`${money(data.weeklyCost, data.currency)} por semana · ${
            data.seasons >= 1
              ? `${data.seasons} temporada${data.seasons === 1 ? "" : "s"}`
              : `${data.weeks} semana${data.weeks === 1 ? "" : "s"}`
          }`}
        />
        <Kpi
          label="Ingresado"
          value={money(data.earned, data.currency)}
          hint="ventas de canteranos"
        />
        <Kpi
          label="Neto"
          value={money(data.net, data.currency)}
          hint={data.roiVerdict}
          tone={profitable ? "positive" : "danger"}
        />
      </div>

      {!profitable && data.invested > 0 && data.breakEvenSales > 0 && (
        <Note>
          Harían falta {data.breakEvenSales} venta(s) más al precio medio para equilibrar.
        </Note>
      )}

      {data.urgent.length > 0 && (
        <Panel title="Plazo a punto de vencer" meta="lo urgente manda sobre lo importante">
          <ul className="space-y-1 p-4 text-xs">
            {data.urgent.map((u, i) => (
              <li key={i} className="text-[var(--danger)]">
                {u}
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {data.notes.map((n, i) => (
        <Note key={i}>{n}</Note>
      ))}

      {/* Las tres vistas de la cantera son la MISMA plantilla mirada de tres
          manerasquién es quién, qué entrenar, cuánto le queda a cada
          habilidad, no tres cosas distintas. Apiladas obligaban a bajar y
          bajar; en pestañas se comparan de un clic. */}
      <div className="flex flex-wrap gap-1 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-1">
        {VIEWS.map((v) => (
          <button
            key={v.key}
            onClick={() => setView(v.key)}
            className={
              v.key === view
                ? "rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white"
                : "rounded-md px-3 py-1.5 text-sm text-[var(--muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text)]"
            }
          >
            {v.label}
          </button>
        ))}
      </div>

      {data.squadSize === 0 ? (
        <Panel title={VIEWS.find((v) => v.key === view)?.label ?? ""}>
          <Empty>Sin canteranos sincronizados todavía.</Empty>
        </Panel>
      ) : view === "squad" ? (
        <Panel title="Plantilla juvenil" meta="ordenada por potencial, no por nivel actual">
          <YouthTable data={data} />
        </Panel>
      ) : view === "train" ? (
        <WhatToTrain data={data} />
      ) : view === "who" ? (
        <QuienEntrena data={data} />
      ) : (
        <SkillDetail data={data} />
      )}

      {data.graduates.length > 0 && (
        <Panel title="Canteranos que pasaron por aquí" meta={`${data.graduates.length}`}>
          <GraduatesTable data={data} />
        </Panel>
      )}
    </div>
  );
}

function YouthTable({ data }: { data: Academy }) {
  type Row = Academy["players"][number];
  const columns: Column<Row>[] = [
    { key: "name", header: "Nombre", value: (r) => r.name },
    {
      key: "age",
      header: "Edad",
      align: "right",
      value: (r) => r.ageYears * 112 + r.ageDays,
      render: (r) => <span className="tabular-nums">{htAge(r.ageYears, r.ageDays)}</span>,
    },
    {
      key: "category",
      header: "Categoría",
      value: (r) => r.category,
      render: (r) => (
        <span className={CATEGORY_TONE[r.category] ?? ""}>
          {r.category}
          {r.verdictIsProvisional && (
            <span title="pocos techos revelados: provisional"> ?</span>
          )}
        </span>
      ),
    },
    {
      key: "potential",
      header: "Potencial",
      align: "right",
      value: (r) => r.potentialScore,
      render: (r) => (
        <span
          className={`tabular-nums${
            r.revealedSkills === 0 ? " text-[var(--muted)]" : ""
          }`}
          title={
            r.revealedSkills === 0
              ? "sin ningún techo revelado: este número sale entero del supuesto, no de datos"
              : undefined
          }
        >
          {r.potentialScore.toFixed(1)}
          {r.revealedSkills === 0 && " ·"}
        </span>
      ),
    },
    {
      key: "best",
      header: "Mejor habilidad",
      value: (r) => r.bestSkill,
      render: (r) => {
        // Sin ningún techo revelado no hay "mejor habilidad" que mostrar: lo
        // que había antes era el techo ASUMIDO por el motor (8 para todas),
        // presentado como si lo hubiera dicho el ojeador.
        if (!r.bestSkill || r.bestSkillMax == null) {
          return <span className="text-[var(--muted)]">sin revelar</span>;
        }
        const s = r.skills.find((x) => x.skill === r.bestSkill);
        return (
          <span className="flex items-center gap-2">
            <span className="w-24 shrink-0">
              {SKILL_NAMES[r.bestSkill] ?? r.bestSkill}
            </span>
            <NivelDeHabilidad
              current={s?.current ?? null}
              maximum={s?.maximum ?? r.bestSkillMax}
              maxReached={s?.maxReached ?? false}
            />
          </span>
        );
      },
    },
    {
      key: "revealed",
      header: "Techos revelados",
      align: "right",
      value: (r) => r.revealedSkills,
      render: (r) => (
        <span className="tabular-nums">
          {r.revealedSkills}/{r.skills.length}
        </span>
      ),
    },
    {
      key: "deadline",
      header: "Plazo",
      align: "right",
      value: (r) => r.daysUntilDeadline,
      render: (r) => (
        <span
          className={
            r.daysUntilDeadline <= 21
              ? "tabular-nums text-[var(--danger)]"
              : "tabular-nums"
          }
        >
          {r.weeksUntilDeadline} sem.
        </span>
      ),
    },
    {
      key: "exposure",
      header: "Aprovechamiento",
      align: "right",
      value: (r) => r.trainingExposure,
      render: (r) => (
        <span className="tabular-nums">{(r.trainingExposure * 100).toFixed(0)}%</span>
      ),
      optional: true,
    },
    { key: "advice", header: "Consejo", value: (r) => r.promoteAdvice },
  ];
  return (
    <>
      <DataTable
        rows={data.players}
        columns={columns}
        rowKey={(r) => r.htYouthPlayerId}
        csvName="juveniles"
        filterPlaceholder="Filtrar canteranos…"
      />
    </>
  );
}

/** Cubos de `AuxiJuveniles`, de más a menos peso. El nombre corto es para la
 *  tabla; el largo explica el corte. */
const BUCKETS: [string, string, string][] = [
  ["excelente", "Excelente", "nota 8 o más, cuenta aunque salga ya"],
  // Claves en camelCase: el serializador del backend camelCasea también las
  // claves de `counts`, no sólo los nombres de campo.
  // El reloj marca a los que se promocionan JÓVENES —por debajo del umbral de
  // edad de abajo—, no a los que se van dentro de poco. Sale joven quiere
  // decir que llega al primer equipo con margen para seguir entrenándolo.
  ["buenoPronto", "Bueno ⏱", "nota 7, y sale joven"],
  ["buenoTarde", "Bueno", "nota 7, y sale mayor"],
  ["aceptablePronto", "Acept. ⏱", "nota 6, y sale joven"],
  ["aceptableTarde", "Aceptable", "nota 6, y sale mayor"],
  ["desconocidoPronto", "? ⏱", "sin revelar, y sale joven"],
  ["desconocidoTarde", "?", "sin revelar, y sale mayor"],
];

/**
 * Qué habilidad entrenar. En la academia no se entrena a un jugador: se
 * entrena una habilidad y la reciben todos, así que la pregunta útil no es
 * "quién es mi mejor canterano" sino "dónde tengo más que ganar".
 *
 * El puntaje viene del backend con la fórmula de la hoja del usuario: pesos en
 * potencias de 3, de modo que un solo canterano excelente pesa más que todos
 * los "buenos" juntos. No es una media — es un desempate por niveles escrito
 * como suma.
 */
/** Los tres mandos. El MÉTODO es fijo —la nota por habilidad, los cubos, la
 *  escalera de potencias— y lo que se mueve son los números que son una
 *  opinión: dónde cae el corte del plazo, cuánto separa un peldaño del
 *  siguiente, y a cuántos les llega de verdad cada entrenamiento. */
const DEFAULT_SOON_MAX_DAYS = 38;
const DEFAULT_WEIGHT_BASE = 3;

/** De dónde sale el número de «entrenables». El método 1 es el único que no se
 *  deriva —depende de la alineación juvenil, que CHPP no entrega aquí— y por
 *  eso es el único que deja escribir. Los de bloque salen de los coeficientes
 *  del Manual que ya usa el motor de posiciones. */
const TRAINABLE_METHODS: [string, string, string][] = [
  ["slots", "Plazas que entrena", "a cuántos puestos de la alineación les llega ese entrenamiento"],
  ["attack", "Aporte al ataque", "cuánto suma esa habilidad al ataque, según los coeficientes del Manual"],
  ["midfield", "Aporte al mediocampo", "cuánto suma esa habilidad al mediocampo"],
  ["defence", "Aporte a la defensa", "cuánto suma esa habilidad a la defensa"],
  ["senior", "Igual que el primer equipo", "16 a lo que entrena hoy el primer equipo, 0 al resto"],
  ["edit", "Editar a mano", "lo escribes tú, habilidad por habilidad"],
];

/** `set_pieces` → `setPieces`.
 *
 * El serializador del backend camelCasea también las CLAVES de los
 * diccionarios, no sólo los nombres de campo (ver `BUCKETS`). Las habilidades
 * viajan en snake dentro de cada fila y en camel dentro de `slotCounts`, así
 * que hay que traducir para cruzarlas.
 */
function aCamel(skill: string): string {
  return skill.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());
}

/** Las plazas de cada habilidad, con las claves que usan las filas. */
function plazasPorHabilidad(
  filas: { skill: string }[],
  plazas: Record<string, number> | undefined,
): Record<string, number> {
  if (!plazas) return {};
  return Object.fromEntries(
    filas.map((f) => [f.skill, plazas[aCamel(f.skill)] ?? 0]),
  );
}

/** ¿La tabla manual sigue en las plazas de origen, sin tocar? */
function plazasIguales(
  actual: Record<string, number>,
  origen: Record<string, number>,
): boolean {
  const claves = Object.keys(origen);
  if (claves.length === 0) return Object.values(actual).every((n) => !n);
  return claves.every((k) => (actual[k] ?? 0) === origen[k]);
}

function WhatToTrain({ data }: { data: Academy }) {
  const [soonMaxDays, setSoonMaxDays] = useState(DEFAULT_SOON_MAX_DAYS);
  const [weightBase, setWeightBase] = useState(DEFAULT_WEIGHT_BASE);
  const [trainableMethod, setTrainableMethod] = useState("edit");
  // Arranca en las plazas que de verdad entrena cada cosa, no en ceros: son
  // números que la aplicación ya sabe, y hacérselos teclear era pedirle al
  // usuario que copiara una tabla nuestra a mano.
  const [trainable, setTrainable] = useState<Record<string, number>>({});
  const [sembrado, setSembrado] = useState(false);
  // `null` = que lo sugiera la escalera (el peldaño -2 de la base). En cuanto
  // el usuario lo toca deja de seguirla: es el único sumando que no describe a
  // la cantera sino cuánto quiere pesar él ese criterio.
  const [bonusWeight, setBonusWeight] = useState<number | null>(null);
  const tuned = useAcademySkillScores({
    soonMaxDays, weightBase, trainableMethod, trainable, trainableWeight: bonusWeight,
  });

  // Los pesos que la base reparte por columna. El usuario juega con potencias
  // y quiere verlas encima de cada cubo, no deducirlas de la base.
  const weights = tuned.data?.weights ?? {};
  const trainableWeight = tuned.data?.trainableWeight;
  const suggestedWeight = tuned.data?.suggestedTrainableWeight;
  const isManual = trainableMethod === "edit";

  // Mientras llega la primera respuesta se pinta lo que ya trajo /academy con
  // los valores por defecto: la tabla nunca aparece vacía.
  const rows = tuned.data?.skillScores ?? data.skillScores ?? [];
  const sugerencia = tuned.data?.suggestion ?? null;
  const plazas = plazasPorHabilidad(rows, tuned.data?.slotCounts);
  useEffect(() => {
    if (sembrado || Object.keys(plazas).length === 0) return;
    setTrainable(plazas);
    setSembrado(true);
  }, [plazas, sembrado]);
  const top = rows[0];
  if (!top) return null;
  const max = Math.max(...rows.map((r) => r.score), 1e-9);
  const isDefault =
    soonMaxDays === DEFAULT_SOON_MAX_DAYS &&
    weightBase === DEFAULT_WEIGHT_BASE &&
    trainableMethod === "edit" &&
    bonusWeight === null &&
    plazasIguales(trainable, plazas);

  return (
    <Panel title="Qué entrenar" meta="una habilidad, la reciben todos">
      {/* Las DOS, no una. Y la segunda con apellido: la misma habilidad se
          entrena por caminos distintos y cada uno llega a gente distinta.
          Con «Defensa» arriba, «Pases» a secas no toca a ningún defensa y
          nadie recibiría las dos cosas; la variante de defensas deja cinco. */}
      <div className="border-b border-[var(--border)] px-4 py-3 text-sm">
        {sugerencia ? (
          <>
            Ahora mismo conviene entrenar{" "}
            <b className="text-[var(--youth-known)]">{sugerencia.mainLabel}</b>, y de
            secundario{" "}
            <b className="text-[var(--youth-known)]">{sugerencia.secondaryLabel}</b>.
            {sugerencia.bothCount > 0 ? (
              <span className="text-[var(--muted)]">
                {" "}
                Así {sugerencia.bothCount}{" "}
                {sugerencia.bothCount === 1 ? "recibe" : "reciben"} las dos cosas,{" "}
                {sugerencia.bothWeeks} semanas de entrenamiento doble en total.
              </span>
            ) : (
              <span className="text-[var(--muted)]">
                {" "}
                No hay ningún puesto que reciba las dos.
              </span>
            )}
            <button
              type="button"
              onClick={() => {
                localStorage.setItem("juveniles.principal", sugerencia.main);
                localStorage.setItem("juveniles.secundario", sugerencia.secondary);
                window.dispatchEvent(new Event("juveniles:sugerencia"));
              }}
              className="ml-2 rounded-md border border-[var(--border)] px-2 py-0.5 text-xs text-[var(--accent)] hover:border-[var(--accent)]"
            >
              Ponerlo en el reparto
            </button>
          </>
        ) : (
          <>
            Ahora mismo conviene entrenar{" "}
            <b className="text-[var(--youth-known)]">{top.label}</b>.
          </>
        )}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-[var(--muted)]">
              <th className="px-4 py-2 text-left font-medium">Habilidad</th>
              {BUCKETS.map(([key, short, long]) => (
                <th key={key} className="px-2 py-2 text-right font-medium" title={long}>
                  <div className="tabular-nums text-[var(--youth-known)]">
                    {formatWeight(weights[key])}
                  </div>
                  <div>{short}</div>
                </th>
              ))}
              <th className="px-2 py-2 text-right font-medium">
                <div className="tabular-nums text-[var(--youth-known)]">
                  {formatWeight(trainableWeight)}
                </div>
                <div>Bonus personalizado</div>
              </th>
              <th className="px-4 py-2 text-right font-medium">Puntaje</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.skill} className="border-t border-[var(--border)]">
                <td className="px-4 py-2 font-medium">{r.label}</td>
                {BUCKETS.map(([key]) => (
                  <td key={key} className="px-2 py-2 text-right tabular-nums">
                    {r.counts[key] ? r.counts[key] : <span className="text-[var(--muted)]">·</span>}
                  </td>
                ))}
                <td className="px-2 py-2 text-right">
                  {isManual ? (
                    // El único método que no se deriva: se escribe.
                    <input
                      type="number"
                      min={0}
                      max={16}
                      value={trainable[r.skill] ?? 0}
                      onChange={(e) =>
                        setTrainable((t) => ({ ...t, [r.skill]: Number(e.target.value) || 0 }))
                      }
                      className="w-12 rounded border border-[var(--border)] bg-[var(--surface)] px-1 py-0.5 text-right tabular-nums"
                    />
                  ) : (
                    <span className="tabular-nums">
                      {/* Con decimales: los métodos por bloque reparten
                          fracciones y redondear empataría habilidades que la
                          fórmula sí distingue. */}
                      {r.trainableCount
                        ? decimal(r.trainableCount, 2)
                        : <span className="text-[var(--muted)]">·</span>}
                    </span>
                  )}
                </td>
                <td className="px-4 py-2 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <div className="h-1.5 w-16 overflow-hidden rounded bg-[var(--surface-2)]">
                      <div
                        className="h-full bg-[var(--youth-known)]"
                        style={{ width: `${(r.score / max) * 100}%` }}
                      />
                    </div>
                    <span className="tabular-nums">{decimal(r.score, 3)}</span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="border-t border-[var(--border)] p-4">
        <div className="mb-3 flex items-baseline justify-between gap-3">
          <span className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
            Parámetros
          </span>
          {!isDefault && (
            <button
              onClick={() => {
                setBonusWeight(null);
                setSoonMaxDays(DEFAULT_SOON_MAX_DAYS);
                setWeightBase(DEFAULT_WEIGHT_BASE);
                setTrainable(plazas ?? {});
              }}
              className="text-xs text-[var(--accent)] hover:underline"
            >
              Volver a los valores originales
            </button>
          )}
        </div>
        <label className="mb-4 block">
          <div className="text-xs">De dónde sale el bonus</div>
          <select
            value={trainableMethod}
            onChange={(e) => setTrainableMethod(e.target.value)}
            className="mt-1 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5 text-sm text-[var(--text)] md:w-auto"
          >
            {TRAINABLE_METHODS.map(([key, label, hint]) => (
              <option key={key} value={key} title={hint}>
                {label}
              </option>
            ))}
          </select>
        </label>

        <div className="grid gap-4 md:grid-cols-3">
          <label className="block">
            <div className="text-xs">
              Salen de menos de 17 años y{" "}
              <b className="tabular-nums text-[var(--youth-known)]">{soonMaxDays}</b> días
            </div>
            <input
              type="range" min={0} max={112} step={1} value={soonMaxDays}
              onChange={(e) => setSoonMaxDays(Number(e.target.value))}
              className="mt-1 w-full accent-[var(--youth-known)]"
            />
          </label>
          <label className="block">
            <div className="flex items-baseline justify-between text-xs">
              <span>Separación entre peldaños</span>
              <b className="tabular-nums">×{decimal(weightBase, 1)}</b>
            </div>
            <input
              type="range" min={1} max={4} step={0.5} value={weightBase}
              onChange={(e) => setWeightBase(Number(e.target.value))}
              className="mt-1 w-full accent-[var(--youth-known)]"
            />
          </label>
          <label className="block">
            <div className="flex items-baseline justify-between gap-2 text-xs">
              <span className="truncate">Peso del bonus personalizado</span>
              <b className="shrink-0 tabular-nums">{formatWeight(trainableWeight)}</b>
            </div>
            <input
              type="range"
              min={0}
              max={1}
              step={0.001}
              value={trainableWeight ?? 0}
              onChange={(e) => setBonusWeight(Number(e.target.value))}
              className="mt-1 w-full accent-[var(--youth-known)]"
            />
            {/* Lo propone la escalera; en cuanto se mueve, deja de seguirla. */}
            <div className="text-[10px] text-[var(--muted)]">
              {bonusWeight === null ? (
                <>sugerido por la escalera</>
              ) : (
                <button type="button" onClick={() => setBonusWeight(null)} className="underline">
                  volver al sugerido ({formatWeight(suggestedWeight)})
                </button>
              )}
            </div>
          </label>
        </div>
      </div>

    </Panel>
  );
}

/**
 * A quién dar los minutos, una vez elegida la habilidad.
 *
 * Ordena a TODA la cantera por lo que saca en esa habilidad, no sólo a los
 * buenos: un canterano sin revelar es la única forma de descubrir si vale, y
 * los minutos son lo que lo revela. Por eso van al final pero van.
 */
//: Los mismos valores por defecto que trae «Qué entrenar». El reparto no tiene
//: mandos propios: mover el corte del plazo ahí y aquí por separado daría dos
//: colas distintas para la misma cantera.
const SOON_MAX_DAYS_POR_DEFECTO = 38;
const WEIGHT_BASE_POR_DEFECTO = 3;

/** El nivel de una habilidad, como en Hattrick.
 *
 * Cuatro casos y un color cada uno. La barra va LIMPIA: la palabra del nivel
 * es texto aparte, nunca dentro de la barra.
 *
 *   ya tocó techo        la palabra del nivel · barra roja llena · `2/2`
 *   sé el actual         la palabra del actual · barra verde     · `5/?`
 *   sé sólo el techo     la palabra del techo  · barra vacía     · `?/4`
 *   no sé nada           «desconocido»         · barra vacía     · —
 */
function NivelDeHabilidad({
  current,
  maximum,
  maxReached,
}: {
  current: number | null;
  maximum: number | null;
  maxReached: boolean;
}) {
  const { palabra, numeros, ancho, crece } = lecturaDeNivel(
    current, maximum, maxReached,
  );
  const color = ancho === 0
    ? "transparent"
    : crece
      ? "var(--positive)"
      : "var(--danger)";

  return (
    <span className="flex items-center gap-2">
      {/* El candado va PRIMERO y en un hueco de ancho fijo: al final de la
          fila desplazaba el resto y las filas quedaban desalineadas entre sí,
          unas con candado y otras sin él. */}
      <span className="w-4 shrink-0 text-center leading-none">
        {maxReached ? <span title="ya tocó techo: no sube más">🔒</span> : null}
      </span>
      <span className="w-24 shrink-0 text-sm">{palabra}</span>
      <span className="h-1.5 w-20 shrink-0 overflow-hidden rounded bg-[var(--surface-2)]">
        <span
          className="block h-full"
          style={{ width: `${ancho}%`, background: color }}
        />
      </span>
      <span className="w-10 shrink-0 text-right text-sm tabular-nums text-[var(--muted)]">
        {numeros}
      </span>
    </span>
  );
}

/** Los nueve peldaños de la cola, para etiquetar cada fila.
 *
 * «Sale joven» es sale con MENOS de 17;038. No es «se va pronto»: lo que
 * decide es la edad a la que sale, no cuánto le queda.
 */
const PELDAÑOS: Record<number, string> = {
  1: "excelente",
  2: "bueno · sale joven",
  3: "bueno",
  4: "aceptable · sale joven",
  5: "aceptable",
  6: "sin descubrir · sale joven",
  7: "sin descubrir",
  8: "insuficiente",
  9: "el resto",
};

function WhoToTrain({ data }: { data: Academy }) {
  const rows = data.skillScores ?? [];
  const [skill, setSkill] = useState<string | null>(null);
  const chosen = rows.find((r) => r.skill === skill) ?? rows[0];
  if (!chosen) return null;

  // La cola llega ordenada por los nueve peldaños. Partirla en "con nota" y
  // "sin revelar" deshacía justo eso: mandaba al final a los que no se sabe
  // qué dan, cuando darles minutos es lo único que los revela — y si además
  // se van pronto, es ahora o nunca. Se pinta en el orden en que llega.

  return (
    <Panel
      title="La cola de cada habilidad"
      meta={`${chosen.players.length} canteranos · ${chosen.label}`}
    >
      <p className="border-b border-[var(--border)] px-4 py-2 text-xs text-[var(--muted)]">
        De aquí sale el reparto de arriba: se va tomando por orden hasta llenar
        cada región.
      </p>
      <label className="block border-b border-[var(--border)] p-4">
        <span className="text-xs text-[var(--muted)]">Habilidad</span>
        <select
          value={chosen.skill}
          onChange={(e) => setSkill(e.target.value)}
          className="mt-1 block w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5 text-sm text-[var(--text)] md:w-auto"
        >
          {rows.map((r) => (
            <option key={r.skill} value={r.skill}>
              {r.label}
            </option>
          ))}
        </select>
      </label>

      <ul className="divide-y divide-[var(--border)]">
        {chosen.players.map((p, i) => (
          <li key={p.name} className="flex items-center justify-between gap-3 px-4 py-2 text-sm">
            <span className="flex min-w-0 items-center gap-2">
              <span className="w-5 shrink-0 text-right text-xs tabular-nums text-[var(--muted)]">
                {i + 1}
              </span>
              <span className="truncate">{p.name}</span>
              <span
                className="shrink-0 rounded border border-[var(--border)] bg-[var(--surface-2)] px-1.5 py-0.5 text-sm text-[var(--text)]"
                title={`Peldaño ${p.priority} de 9`}
              >
                {PELDAÑOS[p.priority] ?? "?"}
              </span>
              {p.leavesSoon && (
                <span className="shrink-0 text-[10px] text-[var(--youth-known)]" title="sale con menos de 17;038">
                  ⏱
                </span>
              )}

            </span>
            <span className="shrink-0">
              {/* La misma pieza que en Techos y en la plantilla: una sola
                  forma de pintar un nivel en toda la pantalla. */}
              <NivelDeHabilidad
                current={p.current}
                maximum={p.maximum}
                maxReached={p.maxReached}
              />
            </span>
          </li>
        ))}
        {/* Los que ya tocaron techo van DESPUÉS de la cola y sin número: no
            compiten por estos minutos, pero verlos con su candado explica el
            hueco mejor que una frase. */}
        {chosen.atMax.map((p) => (
          <li
            key={p.name}
            className="flex items-center justify-between gap-3 px-4 py-2 text-sm opacity-60"
          >
            <span className="flex min-w-0 items-center gap-2">
              <span className="w-5 shrink-0" />
              <span className="truncate">{p.name}</span>
              {/* La misma etiqueta que llevan los de la cola, para que la fila
                  mida lo mismo y la lista no dé un salto al llegar aquí. */}
              <span className="shrink-0 rounded border border-[var(--border)] bg-[var(--surface-2)] px-1.5 py-0.5 text-sm text-[var(--text)]">
                al tope
              </span>
              {p.leavesSoon && (
                <span
                  className="shrink-0 text-[10px] text-[var(--youth-known)]"
                  title="sale con menos de 17;038"
                >
                  ⏱
                </span>
              )}
            </span>
            <span className="shrink-0">
              <NivelDeHabilidad
                current={p.current}
                maximum={p.maximum}
                maxReached={p.maxReached}
              />
            </span>
          </li>
        ))}
      </ul>

    </Panel>
  );
}

/** La pestaña de «A quién entrenar»: el reparto y la cola de cada habilidad.
 *
 * La lista de entrenamientos se pide UNA vez aquí y baja a los dos paneles:
 * pedirla dos veces daría dos respuestas distintas si el usuario mueve los
 * mandos de la otra pestaña entre medias.
 */
function QuienEntrena({ data }: { data: Academy }) {
  const tuned = useAcademySkillScores({
    soonMaxDays: SOON_MAX_DAYS_POR_DEFECTO,
    weightBase: WEIGHT_BASE_POR_DEFECTO,
    trainableMethod: "slots",
    trainable: {},
  });
  return (
    <div className="space-y-4">
      <TrainingPlan
        data={data}
        tuned={tuned.data}
        soonMaxDays={SOON_MAX_DAYS_POR_DEFECTO}
        weightBase={WEIGHT_BASE_POR_DEFECTO}
      />
      <WhoToTrain data={data} />
    </div>
  );
}

/** Los canteranos de los que el ojeador no ha dicho absolutamente nada.
 *
 * El numero solo no sirve: lo que decide es DONDE cae cada uno. Un perfil en
 * blanco en el once recibe entrenamiento y se va revelando; el mismo perfil
 * en el banquillo se queda igual de oscuro una semana mas, y son semanas que
 * no vuelven. Por eso van primero los del banquillo.
 */
function SinRevelar({
  nombres,
  dentro,
  fuera,
}: {
  nombres: string[];
  dentro: TrainingSlot[];
  fuera: TrainingSlot[];
}) {
  if (nombres.length === 0) return null;
  const enBlanco = new Set(nombres);
  const suyos = (de: TrainingSlot[]) =>
    de
      .filter((a) => enBlanco.has(a.player))
      .sort((x, y) => (y.weeksLeft ?? 0) - (x.weeksLeft ?? 0));
  const banquillo = suyos(fuera);
  const once = suyos(dentro);

  const chip = (a: TrainingSlot, entrena: boolean) => (
    <span
      key={a.player}
      className="rounded border px-2 py-1 text-xs"
      style={{
        borderColor: entrena ? "var(--border)" : "#f87171",
        color: entrena ? "var(--text)" : "#fca5a5",
      }}
    >
      {a.player}{" "}
      <span className="tabular-nums text-[var(--muted)]">
        {Math.floor(a.ageDaysTotal / 112)};
        {String(a.ageDaysTotal % 112).padStart(3, "0")}
        {a.weeksLeft != null && ` · ${a.weeksLeft} sem`}
      </span>
    </span>
  );

  return (
    <div className="mt-4 rounded-md border border-[var(--border)] p-3">
      <p className="text-sm text-[var(--text)]">
        Sin revelar todavía{" "}
        <span className="text-[var(--muted)]">
          · el ojeador no ha dicho nada de estos {nombres.length}
        </span>
      </p>
      {banquillo.length > 0 && (
        <>
          <p className="mt-2 text-xs text-[var(--muted)]">
            No entrenan esta semana, así que siguen igual de oscuros
          </p>
          <div className="mt-1 flex flex-wrap gap-2">
            {banquillo.map((a) => chip(a, false))}
          </div>
        </>
      )}
      {once.length > 0 && (
        <>
          <p className="mt-3 text-xs text-[var(--muted)]">
            Entrenan, que es lo que hace que se revelen
          </p>
          <div className="mt-1 flex flex-wrap gap-2">
            {once.map((a) => chip(a, true))}
          </div>
        </>
      )}
    </div>
  );
}

function TrainingPlan({
  data,
  tuned,
  soonMaxDays,
  weightBase,
}: {
  data: Academy;
  tuned: AcademySkillScores | undefined;
  soonMaxDays: number;
  weightBase: number;
}) {
  // Las opciones son los ENTRENAMIENTOS, no las habilidades: «Pases» y
  // «Pases (defensas y centro del campo completo)» suben lo mismo pero llegan
  // a gente distinta, y esa diferencia es todo el asunto.
  const opciones = tuned?.trainings ?? [];
  const habilidades = data.skillScores ?? [];
  // La eleccion sobrevive a recargar: son dos decisiones que el usuario toma
  // una vez por semana, no en cada visita.
  const [main, setMain] = useState<string>(
    () => localStorage.getItem("juveniles.principal") ?? "",
  );
  const [secondary, setSecondary] = useState<string>(
    () => localStorage.getItem("juveniles.secundario") ?? "",
  );
  const principal = main || opciones[0]?.code || habilidades[0]?.skill || "";
  const secundaria = secondary || opciones[1]?.code || principal;

  // El boton de «Ponerlo en el reparto» escribe la eleccion y avisa; sin
  // esto habria que recargar para verla, que es justo lo contrario de lo que
  // el boton promete.
  useEffect(() => {
    const aplicar = () => {
      setMain(localStorage.getItem("juveniles.principal") ?? "");
      setSecondary(localStorage.getItem("juveniles.secundario") ?? "");
    };
    window.addEventListener("juveniles:sugerencia", aplicar);
    return () => window.removeEventListener("juveniles:sugerencia", aplicar);
  }, []);

  const plan = useAcademyTrainingPlan({
    main: principal,
    secondary: secundaria,
    soonMaxDays,
    weightBase,
  });

  if (opciones.length === 0 && habilidades.length === 0) return null;

  // Cuántos recibirían doble ración con cada alternativa. Va pegado a la
  // opción, no en una tabla aparte: la pregunta «¿y si pongo esta otra?» se
  // hace CON el desplegable abierto, y allí es donde tiene que estar la
  // respuesta.
  const dobleCon = new Map(
    (plan.data?.alternatives ?? []).map((a) => [
      a.code,
      { cuantos: a.bothCount, semanas: a.bothWeeks },
    ]),
  );

  const selector = (
    valor: string,
    onChange: (v: string) => void,
    etiqueta: string,
    recuerdo: string,
    conCuenta = false,
  ) => (
    <label className="flex-1">
      <span className="text-xs text-[var(--muted)]">{etiqueta}</span>
      <select
        value={valor}
        onChange={(e) => {
          onChange(e.target.value);
          localStorage.setItem(recuerdo, e.target.value);
        }}
        className="mt-1 block w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5 text-sm text-[var(--text)]"
      >
        {opciones
          .filter((o) => !conCuenta || o.code !== principal)
          .map((o) => {
          const n = conCuenta ? dobleCon.get(o.code) : undefined;
          return (
            <option key={o.code} value={o.code}>
              {o.label}
              {n && n.cuantos > 0
                ? ` · ${n.cuantos} con doble, ${n.semanas} sem`
                : n
                  ? " · nadie recibe doble"
                  : ""}
            </option>
          );
        })}
      </select>
    </label>
  );


  return (
    <Panel
      title="Cómo repartir los dos entrenamientos"
      meta={
        plan.data
          ? `${plan.data.doubleCount} reciben doble ración · ${plan.data.doubleWeeks} semanas`
          : "principal y secundario"
      }
    >
      <div className="flex flex-wrap gap-3 border-b border-[var(--border)] p-4">
        {selector(principal, setMain, "Entrenamiento principal", "juveniles.principal")}
        {selector(secundaria, setSecondary, "Entrenamiento secundario", "juveniles.secundario", true)}
      </div>

      {plan.isError && (
        <p className="p-4 text-sm text-[var(--danger)]">
          No se pudo calcular el reparto.
        </p>
      )}

      {plan.data && (
        <div className="p-4">
          <CanchaDelReparto
            assignments={plan.data.assignments}
            outside={plan.data.outside}
            mainLabel={plan.data.mainLabel}
            secondaryLabel={plan.data.secondaryLabel}
          />
          {plan.data.scouting.total > 0 && (
            <p className="mt-3 text-xs text-[var(--muted)]">
              {plan.data.doubleBlind > 0 && (
                <>
                  <b className="text-[var(--text)]">
                    {plan.data.doubleBlind === plan.data.doubleCount
                      ? `Los ${plan.data.doubleCount} que reciben`
                      : `${plan.data.doubleBlind} de los ${plan.data.doubleCount} que reciben`}
                  </b>{" "}
                  doble ración entrenan una habilidad que el ojeador no ha
                  revelado — es a propósito: entrenarlos es lo que la revela.{" "}
                </>
              )}
              El ojeador lleva {plan.data.scouting.known} lecturas de{" "}
              {plan.data.scouting.total}
              {plan.data.scouting.blankPlayers.length > 0 && (
                <>
                  , y {plan.data.scouting.blankPlayers.length} canteranos sin
                  nada revelado todavía
                </>
              )}
              .
            </p>
          )}
          <SinRevelar
            nombres={plan.data.scouting.blankPlayers}
            dentro={plan.data.assignments}
            fuera={plan.data.outside}
          />
        </div>
      )}
    </Panel>
  );
}

function SkillDetail({ data }: { data: Academy }) {
  return (
    <Panel title="Techos de habilidad" meta="lo alcanzado frente a lo revelado">
      <div className="grid gap-4 p-4 md:grid-cols-2 xl:grid-cols-3">
        {data.players.map((p) => (
          <div key={p.htYouthPlayerId} className="rounded-lg border border-[var(--border)] p-3">
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-medium">{p.name}</span>
              <span className={`text-xs ${CATEGORY_TONE[p.category] ?? ""}`}>{p.category}</span>
            </div>
            <div className="mt-3 space-y-2">
              {p.skills.map((s) => (
                <div key={s.skill} className="flex items-center gap-3 text-xs">
                  <span className="w-28 shrink-0 text-[var(--muted)]">
                    {SKILL_NAMES[s.skill] ?? s.skill}
                  </span>
                  <NivelDeHabilidad
                    current={s.current}
                    maximum={s.maximum}
                    maxReached={s.maxReached}
                  />
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function GraduatesTable({ data }: { data: Academy }) {
  type Row = Academy["graduates"][number];
  const columns: Column<Row>[] = [
    { key: "name", header: "Nombre", value: (r) => r.name },
    {
      key: "promoted", header: "Promocionado",
      value: (r) => (r.promotedAt ? new Date(r.promotedAt).getTime() : -Infinity),
      render: (r) => date(r.promotedAt),
    },
    {
      key: "sold", header: "Vendido",
      value: (r) => (r.soldAt ? new Date(r.soldAt).getTime() : -Infinity),
      render: (r) => date(r.soldAt),
    },
    {
      key: "price",
      header: "Precio",
      align: "right",
      value: (r) => r.soldFor ?? 0,
      render: (r) =>
        r.soldFor == null ? (
          <span className="text-[var(--muted)]">, </span>
        ) : (
          <span className="tabular-nums">{money(r.soldFor, data.currency)}</span>
        ),
    },
    { key: "team", header: "Equipo actual", value: (r) => r.currentTeam ?? "-" },
    { key: "tsi", header: "TSI", align: "right", value: (r) => r.currentTsi ?? 0, optional: true },
  ];
  return (
    <>
      <DataTable
        rows={data.graduates}
        columns={columns}
        rowKey={(r) => r.name}
        csvName="canteranos"
        filterPlaceholder="Filtrar…"
      />
    </>
  );
}
