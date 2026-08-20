import {
  useExperienceModel,
  useLoyaltyModel,
  usePositionModel,
  useTrainingFormula,
} from "../hooks/useTeam";
import { ErrorState, Kpi, Loading, Note, Panel } from "../components/Panels";
import type {
  CalculationReference, ExperienceModel, LoyaltyModel, TrainingFormula,
} from "../services/api";

/**
 * Transparency screen. A manager trusting decisions to this tool deserves to
 * know where the numbers come from and how accurate they are — including the
 * ones that are still guesses.
 */
export function EnginePage() {
  const { data, isLoading, isError, error } = usePositionModel();
  const experience = useExperienceModel();
  const loyalty = useLoyaltyModel();
  const formula = useTrainingFormula();

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return null;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Motor</h1>
        <p className="text-sm text-[var(--muted)]">De dónde salen los números</p>
      </header>

      <FormulaPanel
        data={formula.data}
        isLoading={formula.isLoading}
        isError={formula.isError}
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi label="Posiciones" value={String(data.positions)} />
        <Kpi label="Roles especiales" value={String(data.specialRoles)} />
        <Kpi
          label="Matriz"
          value="Manual no Escrito"
          hint="aportes por posición y orden individual"
        />
        <Kpi label="Índice" value="Aporte total" hint="a defensa, medio y ataque" />
      </div>

      <Panel title="Motor de posiciones" meta={data.configPath}>
        <div className="space-y-3 p-4 text-xs leading-relaxed text-[var(--muted)]">
          <p>
            <b className="text-[var(--text)]">{data.source}</b> aporta la matriz numérica actual;
            <b className="text-[var(--text)]"> Hattrick Control</b> aporta los roles, entradas y
            estructura de pantalla. El resultado es un índice de aporte a sectores, no una estrella
            ni un rating oficial de Hattrick.
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
              <div key={name} className="rounded border border-[var(--border)] bg-[var(--surface-2)] p-2">
                <b className="capitalize text-[var(--text)]">{name}</b>
                <code className="mt-1 block font-mono text-[10px]">{formula}</code>
              </div>
            ))}
          </div>
          <ReferenceNote reference={data.reference} />
        </div>
      </Panel>

      <Panel title="Motor de entrenamiento" meta="fórmula comunitaria HT-Tools">
        <div className="space-y-3 p-4 text-xs leading-relaxed text-[var(--muted)]">
          <code className="block rounded bg-[var(--surface-2)] p-3 font-mono text-[11px] text-[var(--text)]">
            K = K_entrenamiento × K_entrenador × K_ayudantes × intensidad ×
            (1 − %condición) × exposición; semanas = 16 ×
            (reloj_edad⁻¹(reloj_edad + (F(siguiente) − F(actual)) ÷ K) − edad)
          </code>
          <p>
            La función <code>F</code> cambia por tramos según el nivel de habilidad. Por eso Pases
            5→6 y Pases 14→15 ya tienen costos distintos. El reloj de edad aplica la desaceleración
            propia de cada edad, en lugar de sumar un porcentaje lineal fijo.
          </p>
          <p>
            El tipo CHPP selecciona su coeficiente concreto: Pases cortos y Pases largos, por
            ejemplo, no son intercambiables. Entrenador, ayudantes, intensidad, condición y
            minutos en una posición entrenable completan el coeficiente de velocidad.
          </p>
          <p>
            Los valores del club se leen del CHPP. Los coeficientes son la estimación pública de
            HT-Tools: no son constantes oficiales de Hattrick y no se ajustan estadísticamente con
            los datos privados del manager. Los pops reales sirven únicamente para contrastarla.
          </p>
          {formula.data && <ReferenceNote reference={formula.data.reference} />}
        </div>
      </Panel>

      <ExperiencePanel
        data={experience.data}
        isLoading={experience.isLoading}
        isError={experience.isError}
      />

      <LoyaltyPanel
        data={loyalty.data}
        isLoading={loyalty.isLoading}
        isError={loyalty.isError}
      />

      <Panel title="Conflictos abiertos">
        <ul className="space-y-2 p-4 text-xs leading-relaxed text-[var(--muted)]">
          <li>
            <b className="text-[var(--text)]">Subnivel desconocido.</b> CHPP publica el nivel entero,
            pero no el avance decimal interno. Hasta observar un pop, la proyección parte de 0,0;
            por eso es una estimación conservadora, no una fecha prometida.
          </li>
          <li>
            <b className="text-[var(--text)]">Mayores de 34.</b> La tabla pública de edad termina en
            34. Lens prolonga el último tramo conocido y lo declara, sin ajustar una curva con los
            datos privados del club.
          </li>
        </ul>
      </Panel>
    </div>
  );
}

function ReferenceNote({ reference }: { reference: CalculationReference }) {
  return (
    <div className="rounded border border-[var(--border)] bg-[var(--surface-2)] p-3 text-[11px] leading-relaxed">
      <b className="text-[var(--text)]">Referencia: {reference.implementation}</b>{" "}
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
  if (isLoading) return <Panel title="Puntos de experiencia por nivel"><Loading /></Panel>;
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
      <div className="grid gap-4 border-b border-[var(--border)] p-4 sm:grid-cols-3">
        <Kpi
          label="Puntos por nivel"
          value={data.pointsPerLevel.toFixed(2)}
          hint={measured ? "media observada" : "especificación, aún sin datos"}
          tone={measured ? "positive" : undefined}
        />
        <Kpi
          label="Desviación estándar"
          value={data.standardDeviation === null ? ", " : data.standardDeviation.toFixed(2)}
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
            La cifra ya no viene de la especificación sino de tus jugadores: es la media de los
            puntos de partidos reales acumulados entre dos subidas observadas. El valor configurado era{" "}
            {data.configuredPointsPerLevel}. La desviación estándar dice cuánto vale fiarse de la
            media: si es pequeña, el número es real; si es grande, las subidas no cuestan siempre
            lo mismo y conviene mirar el desglose por nivel.
          </p>
        ) : (
          <p>
            Todavía se usa el valor configurado, {data.configuredPointsPerLevel}. Se sustituirá por
            la media observada en cuanto se registren {data.observationsNeeded} subidas más. Una
            media sobre una o dos observaciones no es evidencia, y presentarla como tal sería peor
            que usar el valor de partida. Sincronizaciones vistas: {data.distinctReadings} lecturas,{" "}
            {data.crossingsSeen} cruces de nivel detectados
            {data.discardedCrossings > 0 && (
              <>; {data.discardedCrossings} sin un intervalo completo de partidos y por eso excluidos.</>
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
              Si estos valores se separan, el coste por nivel no es constante y la media única deja
              de ser la respuesta correcta.
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
            Los valores resaltados están verificados: reconstruyen la columna «Suma» de Hattrick
            Control para 19 jugadores con error cero. Los demás vienen de la especificación y
            todavía no se han podido comprobar.
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
  if (isLoading) return <Panel title="Fórmula de Fidelidad"><Loading /></Panel>;
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
      <div className="grid gap-4 border-b border-[var(--border)] p-4 sm:grid-cols-3">
        <Kpi label="Nivel máximo" value={String(data.maxLevel)} />
        <Kpi label="Curva completa" value={`${data.fullDays} días`} />
        <Kpi label="Equivalencia" value={`${data.seasons} temporadas`} />
      </div>

      <div className="space-y-3 p-4 text-xs leading-relaxed text-[var(--muted)]">
        <p>
          La única entrada es la diferencia en días calendario entre hoy y la fecha de compra.
          No se usan pops, promedios ni transiciones observadas.
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
  training_type: "Tipo de entrenamiento CHPP",
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
      meta={data.allRead ? "datos CHPP completos · fórmula HT-Tools" : "faltan datos CHPP"}
    >
      <div className="border-b border-[var(--border)] p-4">
        <div
          className={
            data.allRead
              ? "inline-flex items-center gap-2 rounded-full bg-[var(--surface-2)] px-3 py-1 text-xs text-[var(--positive)]"
              : "inline-flex items-center gap-2 rounded-full bg-[var(--surface-2)] px-3 py-1 text-xs text-[var(--muted)]"
          }
        >
          {data.allRead ? "✓ valores del club leídos del CHPP" : "◐ faltan valores del club"}
        </div>
        <code className="mt-3 block rounded bg-[var(--surface-2)] p-3 font-mono text-[11px] leading-relaxed text-[var(--text)]">
          {data.formula}
        </code>
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
                title={inp.isRead ? "leído del CHPP" : "todavía un supuesto"}
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
                value={v.meanErrorWeeks == null ? ", " : `${v.meanErrorWeeks} sem`}
                tone="positive"
              />
              <Kpi
                label="Error máximo"
                value={v.maxErrorWeeks == null ? ", " : `${v.maxErrorWeeks} sem`}
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
            Todavía no hay dos subidas consecutivas en la habilidad entrenada para
            comparar. Cada sincronización con nuevas subidas la habilita.
          </p>
        )}
      </div>

      <div className="border-t border-[var(--border)] p-4 text-xs leading-relaxed text-[var(--muted)]">
        {(data.limitations ?? []).map((limitation, i) => (
          <p key={`l${i}`} className={i > 0 ? "mt-2" : ""}>
            Límite: {limitation}
          </p>
        ))}
        {data.notes.map((n, i) => (
          <p key={i} className="mt-2">
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
