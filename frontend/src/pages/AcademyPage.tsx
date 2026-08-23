import { useState } from "react";
import { Column, DataTable } from "../components/DataTable";
import { Empty, ErrorState, Kpi, Loading, Note, Panel } from "../components/Panels";
import {
  useAcademy,
  useAcademySkillScores,
  useAcademyTrainingPlan,
} from "../hooks/useTeam";
import { date, decimal, htAge, money } from "../hooks/useFormat";
import type { Academy } from "../services/api";

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
const YOUTH_SKILL_SCALE = 8;

/** Los pesos van de decenas a milésimas según la base, así que no hay un
 *  número fijo de decimales que sirva para todos: se elige por magnitud. */
const formatWeight = (w: number | undefined) =>
  w == null ? "" : w >= 10 ? w.toFixed(0) : w >= 1 ? w.toFixed(1) : w.toFixed(3);

const barWidth = (level: number) =>
  Math.min(100, Math.max(0, (level / YOUTH_SKILL_SCALE) * 100));

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
        <div className="space-y-4">
          <TrainingPlan
            data={data}
            soonMaxDays={SOON_MAX_DAYS_POR_DEFECTO}
            weightBase={WEIGHT_BASE_POR_DEFECTO}
          />
          <WhoToTrain data={data} />
        </div>
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
      render: (r) => <span className="tabular-nums">{r.potentialScore.toFixed(1)}</span>,
    },
    {
      key: "best",
      header: "Mejor habilidad",
      value: (r) => r.bestSkill,
      render: (r) =>
        // Sin ningún techo revelado no hay "mejor habilidad" que mostrar: lo
        // que había antes era el techo ASUMIDO por el motor (8 para todas),
        // presentado como si lo hubiera dicho el ojeador.
        r.bestSkill && r.bestSkillMax != null ? (
          <span>
            {SKILL_NAMES[r.bestSkill] ?? r.bestSkill}
            <span className="text-[var(--muted)]"> (techo {r.bestSkillMax})</span>
          </span>
        ) : (
          <span className="text-[var(--muted)]">sin revelar</span>
        ),
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

function WhatToTrain({ data }: { data: Academy }) {
  const [soonMaxDays, setSoonMaxDays] = useState(DEFAULT_SOON_MAX_DAYS);
  const [weightBase, setWeightBase] = useState(DEFAULT_WEIGHT_BASE);
  const [trainableMethod, setTrainableMethod] = useState("edit");
  const [trainable, setTrainable] = useState<Record<string, number>>({});
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
  const top = rows[0];
  if (!top) return null;
  const max = Math.max(...rows.map((r) => r.score), 1e-9);
  const isDefault =
    soonMaxDays === DEFAULT_SOON_MAX_DAYS &&
    weightBase === DEFAULT_WEIGHT_BASE &&
    trainableMethod === "edit" &&
    bonusWeight === null &&
    Object.values(trainable).every((n) => !n);

  return (
    <Panel title="Qué entrenar" meta="una habilidad, la reciben todos">
      <div className="border-b border-[var(--border)] px-4 py-3 text-sm">
        Ahora mismo conviene entrenar{" "}
        <b className="text-[var(--youth-known)]">{top.label}</b>.
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
                setTrainable({});
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
      title="A quién entrenar"
      meta={`${chosen.players.length} canteranos · ${chosen.label}`}
    >
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
                className="shrink-0 rounded border border-[var(--border)] px-1 text-[10px] text-[var(--muted)]"
                title={PELDAÑOS[p.priority] ?? ""}
              >
                {PELDAÑOS[p.priority] ?? "?"}
              </span>
              {p.leavesSoon && (
                <span className="shrink-0 text-[10px] text-[var(--youth-known)]" title="sale con menos de 17;038">
                  ⏱
                </span>
              )}
              {p.maxReached && (
                <span className="shrink-0 text-[10px] text-[var(--muted)]" title="ya tocó techo: entrenarlo no lo sube">
                  tope
                </span>
              )}
            </span>
            <span className="flex shrink-0 items-center gap-2">
              <div className="h-1.5 w-20 overflow-hidden rounded bg-[var(--surface-2)]">
                <div
                  className="h-full bg-[var(--youth-known)]"
                  style={{ width: `${barWidth(p.note ?? 0)}%` }}
                />
              </div>
              <b className="w-4 text-right tabular-nums">{p.note ?? "?"}</b>
            </span>
          </li>
        ))}
      </ul>

    </Panel>
  );
}

/** Los dos entrenamientos repartidos sobre el once.
 *
 * Hattrick juvenil entrena una cosa principal y otra secundaria, y cada una
 * llega a un conjunto de PUESTOS. Los puestos que reciben las dos son la plaza
 * más valiosa que hay, así que ahí van los primeros de la cola.
 */
const REGIONES: Record<string, { titulo: string; pista: string }> = {
  ambos: { titulo: "Reciben los dos", pista: "doble ración" },
  solo_principal: { titulo: "Solo el principal", pista: "" },
  solo_secundaria: { titulo: "Solo el secundario", pista: "" },
  sin_entrenamiento: { titulo: "Sin entrenamiento", pista: "ocupan sitio, no entrenan" },
};

const PUESTOS: Record<string, string> = {
  keeper: "Portero",
  wingback: "Lateral",
  central_defender: "Defensa central",
  winger: "Extremo",
  inner_midfield: "Medio centro",
  forward: "Delantero",
};

function TrainingPlan({
  data,
  soonMaxDays,
  weightBase,
}: {
  data: Academy;
  soonMaxDays: number;
  weightBase: number;
}) {
  const habilidades = data.skillScores ?? [];
  const [main, setMain] = useState<string>("");
  const [secondary, setSecondary] = useState<string>("");
  const principal = main || habilidades[0]?.skill || "";
  const secundaria = secondary || habilidades[1]?.skill || principal;

  const plan = useAcademyTrainingPlan({
    main: principal,
    secondary: secundaria,
    soonMaxDays,
    weightBase,
  });

  if (habilidades.length === 0) return null;

  const selector = (
    valor: string,
    onChange: (v: string) => void,
    etiqueta: string,
  ) => (
    <label className="flex-1">
      <span className="text-xs text-[var(--muted)]">{etiqueta}</span>
      <select
        value={valor}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 block w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5 text-sm text-[var(--text)]"
      >
        {habilidades.map((h) => (
          <option key={h.skill} value={h.skill}>
            {h.label}
          </option>
        ))}
      </select>
    </label>
  );

  const porRegion = (region: string) =>
    (plan.data?.assignments ?? []).filter((a) => a.region === region);

  return (
    <Panel
      title="Cómo repartir los dos entrenamientos"
      meta={
        plan.data
          ? `${plan.data.doubleCount} reciben doble ración`
          : "principal y secundario"
      }
    >
      <div className="flex flex-wrap gap-3 border-b border-[var(--border)] p-4">
        {selector(principal, setMain, "Entrenamiento principal")}
        {selector(secundaria, setSecondary, "Entrenamiento secundario")}
      </div>

      {plan.isError && (
        <p className="p-4 text-sm text-[var(--danger)]">
          No se pudo calcular el reparto.
        </p>
      )}

      {plan.data && (
        <div className="divide-y divide-[var(--border)]">
          {Object.entries(REGIONES).map(([clave, { titulo, pista }]) => {
            const filas = porRegion(clave);
            if (filas.length === 0) return null;
            return (
              <div key={clave} className="p-4">
                <div className="flex items-baseline gap-2">
                  <h3 className="text-sm font-medium">{titulo}</h3>
                  <span className="text-xs text-[var(--muted)]">
                    {filas.length}
                    {pista && ` · ${pista}`}
                  </span>
                </div>
                <ul className="mt-2 space-y-1">
                  {filas.map((a) => (
                    <li
                      key={a.player}
                      className="flex flex-wrap items-baseline gap-x-2 text-sm"
                    >
                      <span>{a.player}</span>
                      {a.puesto && (
                        <span className="text-xs text-[var(--muted)]">
                          {PUESTOS[a.puesto] ?? a.puesto}
                        </span>
                      )}
                      {/* Una plaza a media ración entrena, pero la mitad. */}
                      {(a.racionPrincipal === 50 || a.racionSecundaria === 50) && (
                        <span className="text-xs text-[var(--warning)]">
                          media ración
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
          {plan.data.outside.length > 0 && (
            <p className="p-4 text-xs text-[var(--muted)]">
              Fuera de los once ({plan.data.outside.length}):{" "}
              {plan.data.outside.join(" · ")}
            </p>
          )}
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
                <div key={s.skill} className="text-xs">
                  <div className="flex justify-between text-[var(--muted)]">
                    {/* El mapa de nombres existía y esta línea no lo usaba:
                        se leía "set_pieces" en una pantalla en español. */}
                    <span>{SKILL_NAMES[s.skill] ?? s.skill}</span>
                    <span className="tabular-nums">
                      {s.isCurrentKnown ? s.current : "?"}
                      {s.isMaxKnown ? ` / ${s.maximum}` : " / ?"}
                    </span>
                  </div>
                  <div className="mt-1 flex h-1.5 overflow-hidden rounded bg-[var(--surface-2)]">
                    {/* Amarillo = lo que el ojeador YA midió de este chico.
                        Sólo se pinta si el nivel actual se conoce; un nivel
                        sin revelar deja la barra vacía en vez de fingir un 0,
                        que es lo que hacía antes. */}
                    {s.isCurrentKnown && (
                      <div
                        className="h-full bg-[var(--youth-known)]"
                        style={{ width: `${barWidth(s.current ?? 0)}%` }}
                      />
                    )}
                    {/* El tramo hasta el techo, cuando el techo se conoce: es
                        recorrido pendiente, no habilidad que ya tenga. */}
                    {s.isMaxKnown && (
                      <div
                        className="h-full bg-[var(--youth-headroom)]"
                        style={{
                          width: `${Math.max(
                            0,
                            barWidth(s.maximum ?? 0) - barWidth(s.isCurrentKnown ? s.current ?? 0 : 0),
                          )}%`,
                        }}
                      />
                    )}
                  </div>
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
