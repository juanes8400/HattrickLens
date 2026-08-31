import { useSearchParams } from "react-router-dom";
import {
  useCalculos,
  useExperienceModel,
  useLoyaltyModel,
  usePositionModel,
  useTrainingFormula,
} from "../hooks/useTeam";
import { ErrorState, Kpi, Loading, Note, Panel } from "../components/Panels";
import { Tabs } from "../components/Tabs";
import type {
  CalculationReference,
  Calculo,
  ExperienceModel,
  LoyaltyModel,
  PositionModel,
  TablaDeCalculo,
  TrainingFormula,
} from "../services/api";

/**
 * Transparencia: como se calcula cada numero de la herramienta.
 *
 * Absorbio a «Motor» el 2026-08-31. Motor ya hacia esto para entrenamiento y
 * posiciones, y tener dos pantallas que contestan «de donde sale esto?»
 * obligaba al usuario a adivinar en cual de las dos mirar. Sus cuatro paneles
 * vivos siguen aqui enteros, cada uno colgado del calculo que explica.
 *
 * La navegacion es de dos pisos --seccion, luego calculo-- y no una lista
 * larga: el catalogo crece con cada motor nuevo, y una pagina que se hace mas
 * dificil de leer cuanto mas honesta es se acaba cerrando.
 */
export function TransparencyPage() {
  const catalogo = useCalculos();
  const positions = usePositionModel();
  const experience = useExperienceModel();
  const loyalty = useLoyaltyModel();
  const formula = useTrainingFormula();

  // La selección vive en la URL, no en el estado. Transparencia es una
  // pantalla de consulta: desde cualquier sitio de la app se querrá enlazar a
  // UN cálculo concreto --«cómo se calcula el ROI»-- y con estado local ese
  // enlace no existía. De paso, la vuelta atrás del navegador funciona y la
  // dirección se puede copiar (2026-08-31).
  const [params, setParams] = useSearchParams();
  const seccionId = params.get("s");
  const calculoId = params.get("c");
  const irA = (s: string | null, c: string | null) => {
    const siguiente = new URLSearchParams(params);
    if (s) siguiente.set("s", s);
    if (c) siguiente.set("c", c);
    else siguiente.delete("c");
    setParams(siguiente, { replace: true });
  };

  if (catalogo.isLoading) return <Loading />;
  if (catalogo.isError) return <ErrorState error={catalogo.error} />;
  const secciones = catalogo.data ?? [];
  if (secciones.length === 0) return null;

  // Sin seleccion manda el primero de cada nivel. Se guarda el id y no el
  // indice: asi cambiar el catalogo no mueve al usuario de calculo.
  const seccion = secciones.find((s) => s.id === seccionId) ?? secciones[0];
  if (!seccion) return null;
  // Una sección sin cálculos no se pinta vacía: no existe todavía.
  const calculo =
    seccion.calcs.find((c) => c.id === calculoId) ?? seccion.calcs[0];
  if (!calculo) return null;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Transparencia</h1>
        <p className="text-sm text-[var(--muted)]">
          Cómo se calcula cada número, con qué constantes y hasta dónde vale
        </p>
      </header>

      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-2">
        <Tabs
          tabs={secciones.map((s) => ({
            key: s.id,
            label: `${s.name} · ${s.calcs.length}`,
          }))}
          active={seccion.id}
          label="Sección"
          onChange={(id) => irA(id, null)}
        />
      </div>

      {seccion.calcs.length > 1 && (
        <Tabs
          tabs={seccion.calcs.map((c) => ({ key: c.id, label: c.name }))}
          active={calculo.id}
          label={`Cálculos de ${seccion.name}`}
          onChange={(id) => irA(seccion.id, id)}
        />
      )}

      <FichaDelCalculo calculo={calculo} />

      {/* El panel vivo del calculo, si lo tiene: los valores leidos de TU club
          y el contraste contra lo que de verdad paso. La formula de arriba
          dice como se calcula; esto dice con que y cuanto acierta. */}
      {calculo.live === "trainingFormula" && (
        <FormulaPanel
          data={formula.data}
          isLoading={formula.isLoading}
          isError={formula.isError}
        />
      )}
      {calculo.live === "experienceModel" && (
        <ExperiencePanel
          data={experience.data}
          isLoading={experience.isLoading}
          isError={experience.isError}
        />
      )}
      {calculo.live === "loyaltyModel" && (
        <LoyaltyPanel
          data={loyalty.data}
          isLoading={loyalty.isLoading}
          isError={loyalty.isError}
        />
      )}
      {calculo.live === "positionModel" && (
        <PositionsPanel
          data={positions.data}
          isLoading={positions.isLoading}
          isError={positions.isError}
        />
      )}
    </div>
  );
}

/** La ficha de un calculo: que contesta, como, con que y hasta donde.
 *
 *  Las listas se leen con `?? []` a proposito. Un payload viejo en cache --o
 *  un campo que todavia no ha llegado-- no puede tumbar la pantalla entera:
 *  ya paso una vez con un tooltip, y volvio a pasar el 2026-08-31 al añadir
 *  las fuentes. Un hueco se dibuja como hueco. */
function FichaDelCalculo({ calculo }: { calculo: Calculo }) {
  return (
    <Panel title={calculo.name} meta={calculo.answers}>
      <div className="space-y-4 p-4">
        {/* `pre` y no `code` suelto: las formulas van alineadas a mano
            --sumatorios, fracciones-- y colapsar los espacios las destroza. */}
        <pre className="overflow-x-auto rounded border border-[var(--border)] bg-[var(--surface-2)] p-3 font-mono text-[11px] leading-relaxed text-[var(--text)]">
          {calculo.formula}
        </pre>

        {(calculo.sources ?? []).length > 0 && (
          <div>
            <h3 className="mb-2 text-[10px] uppercase tracking-wide text-[var(--muted)]">
              De dónde sale cada dato
            </h3>
            <table className="w-full text-xs">
              <tbody className="divide-y divide-[var(--border)]">
                {(calculo.sources ?? []).map((f) => (
                  <tr key={f.what}>
                    <td className="py-2 pr-3">{f.what}</td>
                    <td className="py-2 text-right text-[var(--muted)]">
                      {f.origin}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {(calculo.constants ?? []).length > 0 && (
          <div>
            <h3 className="mb-2 text-[10px] uppercase tracking-wide text-[var(--muted)]">
              Las constantes, leídas del motor
            </h3>
            <table className="w-full text-xs">
              <tbody className="divide-y divide-[var(--border)]">
                {(calculo.constants ?? []).map((k) => (
                  <tr key={k.symbol}>
                    <td className="py-2 pr-3 font-mono whitespace-nowrap">
                      {k.symbol}
                    </td>
                    <td className="py-2 pr-3 text-right font-mono tabular-nums text-[var(--text)]">
                      {k.value}
                    </td>
                    <td className="py-2 text-[var(--muted)]">{k.what}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {(calculo.tables ?? []).map((t) => (
          <TablaDeParametros key={t.title} tabla={t} />
        ))}

        {(calculo.steps ?? []).length > 0 && (
          <div>
            <h3 className="mb-2 text-[10px] tracking-wide text-[var(--muted)] uppercase">
              La cuenta, paso a paso
            </h3>
            {/* Numerada de verdad (`ol`): el orden es la mitad del contenido,
                y un lector de pantalla tiene que oir «paso 3 de 5». */}
            <ol className="space-y-1.5">
              {(calculo.steps ?? []).map((paso, i) => (
                <li key={paso} className="flex gap-2.5 text-xs leading-relaxed">
                  <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-[var(--surface-2)] font-mono text-[9px] tabular-nums text-[var(--muted)]">
                    {i + 1}
                  </span>
                  <span className="text-[var(--text)]">{paso}</span>
                </li>
              ))}
            </ol>
          </div>
        )}

        {(calculo.limits ?? []).length > 0 && (
          <div>
            <h3 className="mb-2 text-[10px] uppercase tracking-wide text-[var(--muted)]">
              Hasta dónde vale
            </h3>
            <ul className="list-disc space-y-1 pl-4 text-xs leading-relaxed text-[var(--muted)]">
              {(calculo.limits ?? []).map((l) => (
                <li key={l}>{l}</li>
              ))}
            </ul>
          </div>
        )}

        {calculo.note && (
          <p className="border-t border-[var(--border)] pt-3 text-[11px] leading-relaxed text-[var(--muted)]">
            {calculo.note}
          </p>
        )}
      </div>
    </Panel>
  );
}

/** Una tabla de parametros, entera.
 *
 *  Va aparte de las constantes porque no es una lista de simbolos sueltos
 *  sino una rejilla que se CONSULTA: el usuario viene a buscar la fila de su
 *  jugador --su edad, su entrenamiento-- y para eso tiene que estar toda.
 *  Scroll horizontal propio: la de resistencia tiene seis columnas y en un
 *  telefono no cabe, pero lo que se desplaza es la tabla, nunca la pagina. */
function TablaDeParametros({ tabla }: { tabla: TablaDeCalculo }) {
  return (
    <div>
      <h3 className="mb-2 text-[10px] uppercase tracking-wide text-[var(--muted)]">
        {tabla.title}
      </h3>
      <div className="overflow-x-auto rounded border border-[var(--border)]">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-[var(--surface-2)] text-[var(--muted)]">
              {tabla.columns.map((c, i) => (
                <th
                  key={c}
                  scope="col"
                  className={`px-3 py-2 font-medium whitespace-nowrap ${
                    i === 0 ? "text-left" : "text-right"
                  }`}
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {tabla.rows.map((fila, r) => (
              <tr key={`${fila[0]}-${r}`}>
                {fila.map((celda, i) => (
                  <td
                    key={`${tabla.columns[i] ?? i}`}
                    className={
                      i === 0
                        ? "px-3 py-1.5 whitespace-nowrap text-[var(--text)]"
                        : "px-3 py-1.5 text-right font-mono tabular-nums whitespace-nowrap text-[var(--text)]"
                    }
                  >
                    {celda}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {tabla.note && (
        <p className="mt-2 text-[11px] leading-relaxed text-[var(--muted)]">
          {tabla.note}
        </p>
      )}
    </div>
  );
}

/** La matriz de posiciones, tal como la ensenaba Motor. */
function PositionsPanel({
  data,
  isLoading,
  isError,
}: {
  data?: PositionModel;
  isLoading: boolean;
  isError: boolean;
}) {
  if (isLoading)
    return (
      <Panel title="La matriz">
        <Loading />
      </Panel>
    );
  if (isError || !data)
    return (
      <Panel title="La matriz">
        <Note>La matriz de posiciones no está disponible.</Note>
      </Panel>
    );
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 [&>*]:min-w-0">
        <Kpi label="Posiciones" value={String(data.positions)} />
        <Kpi label="Roles especiales" value={String(data.specialRoles)} />
        <Kpi
          label="Matriz"
          value="Manual no Escrito"
          hint="aportes por posición y orden individual"
        />
        <Kpi
          label="Índice"
          value="Aporte total"
          hint="a defensa, medio y ataque"
        />
      </div>

      <Panel title="La matriz" meta={data.configPath}>
        <div className="space-y-3 p-4 text-xs leading-relaxed text-[var(--muted)]">
          <p>
            <b className="text-[var(--text)]">{data.source}</b> aporta la matriz
            numérica actual; los diecinueve roles y sus órdenes individuales
            vienen de la práctica establecida de la comunidad. El resultado es
            un índice de aporte a sectores, no una estrella ni un rating oficial
            de Hattrick.
          </p>
          <a
            href={data.sourceUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex text-[var(--accent)] underline underline-offset-2"
          >
            Abrir la fuente del Manual
          </a>
          <div className="grid gap-2 sm:grid-cols-2">
            {Object.entries(data.adjustments).map(([name, formula]) => (
              <div
                key={name}
                className="rounded border border-[var(--border)] bg-[var(--surface-2)] p-2"
              >
                <b className="capitalize text-[var(--text)]">{name}</b>
                <code className="mt-1 block font-mono text-[10px]">
                  {formula}
                </code>
              </div>
            ))}
          </div>
          <ReferenceNote reference={data.reference} />
        </div>
      </Panel>
    </>
  );
}

function ReferenceNote({ reference }: { reference: CalculationReference }) {
  return (
    <div className="rounded border border-[var(--border)] bg-[var(--surface-2)] p-3 text-[11px] leading-relaxed">
      <b className="text-[var(--text)]">
        Referencia: {reference.implementation}
      </b>{" "}
      <span className="font-mono">[{reference.status}]</span>
      <p className="mt-1">Recuperado: {reference.recovered}</p>
      <p className="mt-1">Pendiente: {reference.pending}</p>
    </div>
  );
}

/**
 * Points per experience level. The specification says 28. This panel does not
 * repeat that as if it were settled: it shows what the squad's own level-ups
 * say, how much they scatter, and how many more are needed before the observed
 * figure replaces the configured one.
 */
function ExperiencePanel({
  data,
  isLoading,
  isError,
}: {
  data?: ExperienceModel;
  isLoading: boolean;
  isError: boolean;
}) {
  if (isLoading)
    return (
      <Panel title="Puntos de experiencia por nivel">
        <Loading />
      </Panel>
    );
  if (isError || !data) {
    return (
      <Panel title="Puntos de experiencia por nivel">
        <Note>No se pudo leer la calibración de experiencia.</Note>
      </Panel>
    );
  }

  const measured = data.source !== "configured";
  const interval = data.confidenceInterval;

  return (
    <Panel
      title="Puntos de experiencia por nivel"
      meta={measured ? "medido" : "valor configurado"}
    >
      <div className="grid gap-4 border-b border-[var(--border)] p-4 sm:grid-cols-3 [&>*]:min-w-0">
        <Kpi
          label="Puntos por nivel"
          value={data.pointsPerLevel.toFixed(2)}
          hint={measured ? "media observada" : "especificación, aún sin datos"}
          tone={measured ? "positive" : undefined}
        />
        <Kpi
          label="Desviación estándar"
          value={
            data.standardDeviation === null
              ? "—"
              : data.standardDeviation.toFixed(2)
          }
          hint={
            interval
              ? `intervalo 95%: ${interval[0].toFixed(2)} – ${interval[1].toFixed(2)}`
              : "hace falta más de una observación"
          }
        />
        <Kpi
          label="Subidas observadas"
          value={String(data.observations)}
          hint={
            data.observationsNeeded > 0
              ? `faltan ${data.observationsNeeded} para calibrar`
              : "suficientes para calibrar"
          }
        />
      </div>

      <div className="space-y-3 p-4 text-xs leading-relaxed text-[var(--muted)]">
        {measured ? (
          <p>
            La cifra ya no viene de la especificación sino de tus jugadores: es
            la media de los puntos de partidos reales acumulados entre dos
            subidas observadas. El valor configurado era{" "}
            {data.configuredPointsPerLevel}. La desviación estándar dice cuánto
            vale fiarse de la media: si es pequeña, el número es real; si es
            grande, las subidas no cuestan siempre lo mismo y conviene mirar el
            desglose por nivel.
          </p>
        ) : (
          <p>
            Todavía se usa el valor configurado, {data.configuredPointsPerLevel}
            . Se sustituirá por la media observada en cuanto se registren{" "}
            {data.observationsNeeded} subidas más. Una media sobre una o dos
            observaciones no es evidencia, y presentarla como tal sería peor que
            usar el valor de partida. Sincronizaciones vistas:{" "}
            {data.distinctReadings} lecturas, {data.crossingsSeen} cruces de
            nivel detectados
            {data.discardedCrossings > 0 && (
              <>
                ; {data.discardedCrossings} sin un intervalo completo de
                partidos y por eso excluidos.
              </>
            )}
          </p>
        )}

        {Object.keys(data.byLevel).length > 0 && (
          <div>
            <b className="text-[var(--text)]">Coste por nivel de partida</b>
            <div className="mt-2 flex flex-wrap gap-2">
              {Object.entries(data.byLevel).map(([level, value]) => (
                <span
                  key={level}
                  className="rounded bg-[var(--surface-2)] px-2 py-1 font-mono text-[11px] text-[var(--text)]"
                >
                  nivel {level} → {value.toFixed(1)}
                </span>
              ))}
            </div>
            <p className="mt-2">
              Si estos valores se separan, el coste por nivel no es constante y
              la media única deja de ser la respuesta correcta.
            </p>
          </div>
        )}

        <div>
          <b className="text-[var(--text)]">Puntos por tipo de partido</b>
          <div className="mt-2 flex flex-wrap gap-2">
            {Object.entries(data.matchPoints).map(([kind, value]) => (
              <span
                key={kind}
                className={`rounded px-2 py-1 font-mono text-[11px] ${
                  data.verified.includes(kind)
                    ? "bg-[var(--surface-2)] text-[var(--text)]"
                    : "bg-transparent text-[var(--muted)] ring-1 ring-[var(--border)]"
                }`}
              >
                {kind} {value}
              </span>
            ))}
          </div>
          <p className="mt-2">
            Los valores resaltados están verificados: reconstruyen la columna
            «Suma» de Hattrick Control para 19 jugadores con error cero. Los
            demás vienen de la especificación y todavía no se han podido
            comprobar.
          </p>
        </div>

        <ReferenceNote reference={data.reference} />

        {data.levelUps.length > 0 && (
          <div>
            <b className="text-[var(--text)]">Subidas registradas</b>
            <ul className="mt-2 space-y-1 font-mono text-[11px]">
              {data.levelUps.map((lu, i) => (
                <li key={i}>
                  {lu.player}: {lu.fromLevel} → {lu.toLevel} con{" "}
                  {lu.pointsAccumulated.toFixed(1)} puntos
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Panel>
  );
}

/** Fórmula única de Fidelidad basada en días calendario desde la compra. */
function LoyaltyPanel({
  data,
  isLoading,
  isError,
}: {
  data?: LoyaltyModel;
  isLoading: boolean;
  isError: boolean;
}) {
  if (isLoading)
    return (
      <Panel title="Fórmula de Fidelidad">
        <Loading />
      </Panel>
    );
  if (isError || !data) {
    return (
      <Panel title="Fórmula de Fidelidad">
        <Note>No se pudo leer el modelo de fidelidad.</Note>
      </Panel>
    );
  }

  return (
    <Panel
      title="Fórmula de Fidelidad"
      meta={`${data.fullDays} días · ${data.seasons} temporadas`}
    >
      <div className="grid gap-4 border-b border-[var(--border)] p-4 sm:grid-cols-3 [&>*]:min-w-0">
        <Kpi label="Nivel máximo" value={String(data.maxLevel)} />
        <Kpi label="Curva completa" value={`${data.fullDays} días`} />
        <Kpi label="Equivalencia" value={`${data.seasons} temporadas`} />
      </div>

      <div className="space-y-3 p-4 text-xs leading-relaxed text-[var(--muted)]">
        <p>
          La única entrada es la diferencia en días calendario entre hoy y la
          fecha de compra. No se usan pops, promedios ni transiciones
          observadas.
        </p>

        <code className="block rounded bg-[var(--surface-2)] p-3 font-mono text-[11px] text-[var(--text)]">
          {data.formula}
        </code>

        <div>
          <b className="text-[var(--text)]">Primer día de cada nivel</b>
          <div className="mt-2 flex flex-wrap gap-2">
            {data.thresholds.map((threshold) => (
              <span
                key={threshold.level}
                className="rounded bg-[var(--surface-2)] px-2 py-1 font-mono text-[11px] text-[var(--text)]"
              >
                N{threshold.level}: día {threshold.day}
              </span>
            ))}
          </div>
        </div>

        <ReferenceNote reference={data.reference} />
      </div>
    </Panel>
  );
}

const INPUT_LABELS: Record<string, string> = {
  training_type: "Tipo de entrenamiento",
  assistant_level_sum: "Ayudantes (suma de niveles)",
  intensity: "Intensidad",
  stamina_share: "% condición",
  coach_level: "Nivel del entrenador",
};

/**
 * Cierre de la fórmula de entrenamiento. Esta es la pantalla que responde
 * «¿de dónde sale este número?» sin dejar ningún valor puesto a mano
 * escondido: cada término muestra si se lee del CHPP o sigue siendo un
 * supuesto, y la fórmula se contrasta con subidas que Hattrick confirma.
 */
function FormulaPanel({
  data,
  isLoading,
  isError,
}: {
  data?: TrainingFormula;
  isLoading: boolean;
  isError: boolean;
}) {
  if (isLoading)
    return (
      <Panel title="Fórmula de entrenamiento">
        <Loading />
      </Panel>
    );
  if (isError || !data)
    return (
      <Panel title="Fórmula de entrenamiento">
        <Note>
          Sincroniza tu equipo (club, plantel, staff) para ver la fórmula con la
          procedencia de cada valor.
        </Note>
      </Panel>
    );

  const v = data.validation;
  return (
    <Panel
      title="Fórmula de entrenamiento"
      meta={
        data.allRead
          ? "datos del club completos · fórmula HT-Tools"
          : "faltan datos del club"
      }
    >
      <div className="border-b border-[var(--border)] p-4">
        <div
          className={
            data.allRead
              ? "inline-flex items-center gap-2 rounded-full bg-[var(--surface-2)] px-3 py-1 text-xs text-[var(--positive)]"
              : "inline-flex items-center gap-2 rounded-full bg-[var(--surface-2)] px-3 py-1 text-xs text-[var(--muted)]"
          }
        >
          {data.allRead
            ? "✓ valores del club leídos de Hattrick"
            : "◐ faltan valores del club"}
        </div>
      </div>

      <div className="grid gap-3 p-4 sm:grid-cols-2">
        {Object.entries(data.inputs).map(([key, inp]) => (
          <div
            key={key}
            className="rounded-lg border border-[var(--border)] p-3"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs text-[var(--muted)]">
                {INPUT_LABELS[key] ?? key}
              </span>
              <span
                className={
                  inp.isRead
                    ? "rounded bg-[var(--surface-2)] px-2 py-0.5 font-mono text-[10px] text-[var(--positive)]"
                    : "rounded px-2 py-0.5 font-mono text-[10px] text-[var(--muted)] ring-1 ring-[var(--border)]"
                }
                title={inp.isRead ? "leído de Hattrick" : "todavía un supuesto"}
              >
                {inp.source}
              </span>
            </div>
            <div className="mt-1 text-xl font-semibold tabular-nums text-[var(--text)]">
              {String(inp.value)}
            </div>
            <div className="mt-1 text-[11px] leading-snug text-[var(--muted)]">
              {inp.note}
            </div>
          </div>
        ))}
      </div>

      <div className="border-t border-[var(--border)] p-4">
        <div className="flex items-baseline justify-between">
          <span className="text-sm font-medium">
            Contraste con subidas confirmadas
          </span>
          <span className="text-xs text-[var(--muted)]">
            entrena: {data.trainedSkill}
          </span>
        </div>
        {v.observations > 0 ? (
          <>
            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              <Kpi label="Subidas comparadas" value={String(v.observations)} />
              <Kpi
                label="Error medio"
                value={
                  v.meanErrorWeeks == null ? "—" : `${v.meanErrorWeeks} sem`
                }
                tone="positive"
              />
              <Kpi
                label="Error máximo"
                value={v.maxErrorWeeks == null ? "—" : `${v.maxErrorWeeks} sem`}
              />
            </div>
            <table className="mt-3 w-full text-xs">
              <thead className="text-[var(--muted)]">
                <tr className="text-left">
                  <th className="py-1">Subida</th>
                  <th className="py-1 text-right">Observado</th>
                  <th className="py-1 text-right">Predicho</th>
                  <th className="py-1 text-right">Error</th>
                </tr>
              </thead>
              <tbody className="tabular-nums">
                {v.samples.map((s, i) => (
                  <tr key={i} className="border-t border-[var(--border)]">
                    <td className="py-1">
                      {s.from_level} → {s.to_level}
                    </td>
                    <td className="py-1 text-right">{s.observed_weeks} sem</td>
                    <td className="py-1 text-right">{s.predicted_weeks} sem</td>
                    <td className="py-1 text-right">{s.error_weeks}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : (
          <p className="mt-2 text-xs text-[var(--muted)]">
            Todavía no hay dos subidas consecutivas en la habilidad entrenada
            para comparar. Cada sincronización con nuevas subidas la habilita.
          </p>
        )}
      </div>

      <div className="border-t border-[var(--border)] p-4 text-xs leading-relaxed text-[var(--muted)]">
        {/* Los límites del motor NO se repiten aquí: los lista la ficha del
            cálculo, arriba, bajo «Hasta dónde vale». Lo que sí es de este
            panel son las notas y los avisos de la validación, que dependen de
            los datos de TU club y no de la fórmula. */}
        {data.notes.map((n, i) => (
          <p key={i} className={i > 0 ? "mt-2" : ""}>
            {n}
          </p>
        ))}
        {v.caveats.map((c, i) => (
          <p key={`c${i}`} className="mt-2">
            {c}
          </p>
        ))}
      </div>
    </Panel>
  );
}
