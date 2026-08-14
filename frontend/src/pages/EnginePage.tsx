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

      <Panel title="Motor de entrenamiento" meta="perfil compatible HTC">
        <div className="space-y-3 p-4 text-xs leading-relaxed text-[var(--muted)]">
          <code className="block rounded bg-[var(--surface-2)] p-3 font-mono text-[11px] text-[var(--text)]">
            semanas = base[habilidad] ÷ (1 + Σniveles_de_máx_2_ayudantes × 3,5%) ×
            (1 + 6% × (edad − 17)) × (1 + 10% × max(7 − nivel_entrenador, 0) − 5% si es excelente)
            × (1 − 1% × (intensidad − 100)) ÷ (1 − %condición)
          </code>
          <p>
            Hattrick Control confirma las entradas y que cada tipo tiene su propio control de
            semanas, pero esta extracción no contiene su <code>Defaults.dat</code> ni la rutina
            auxiliar que une los modificadores. Por eso los coeficientes siguen siendo un perfil
            visible y calibrable, no una fórmula oficial escondida.
          </p>
          <p>
            Los ayudantes aportan velocidad y por eso reducen las semanas. En sentido contrario,
            dedicar parte del entrenamiento a condición deja menos capacidad para la habilidad
            primaria y aumenta las semanas: ahora se divide por la capacidad restante, no se la
            multiplica.
          </p>
          <p>
            Los valores del club —ayudantes, intensidad, condición y entrenador— sí se leen del
            CHPP. La confianza de cada previsión sube solamente cuando los pops reales permiten
            validar el perfil completo.
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
            <b className="text-[var(--text)]">Forma del factor de edad.</b> Es la manera en que el
            tiempo de entrenamiento crece con la edad. El perfil actual la describe{" "}
            <i>lineal</i>: cada año suma un 6% fijo sobre el tiempo base, así que de 17 a 27 años
            el tiempo se multiplica por 1,60. El ajuste sobre las 18 observaciones prefiere una{" "}
            <i>exponencial</i>: cada año multiplica por 1,0463, de modo que el recargo se acumula
            sobre el del año anterior y crece más despacio al principio y más rápido al final. En
            el rango de edades del plantel casi coinciden; se separan en los extremos. Se usa la
            lineal como perfil visible, y la exponencial queda disponible en configuración hasta
            poder contrastarla con la rutina auxiliar de Hattrick Control.
          </li>
          <li>
            <b className="text-[var(--text)]">Escala del entrenador.</b> Es lo único que queda por
            reconciliar en la fórmula: el CHPP entrega el nivel del entrenador en escala 1–5
            (stafflist) mientras que el perfil usa una escala nominal 7/8. La
            correspondencia vive en configuración marcada como provisional, y el panel de arriba
            la muestra en la nota del entrenador en vez de esconderla.
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
          value={data.standardDeviation === null ? "—" : data.standardDeviation.toFixed(2)}
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

/**
 * Días reales por transición de Fidelidad. A diferencia de Experiencia, no
 * hay ningún valor configurado de partida: Hattrick nunca publicó esta
 * fórmula, así que cada transición de nivel (N→N+1) solo existe aquí una
 * vez que se ha visto una subida limpia real — la tabla se rellena sola,
 * transición por transición, a medida que se sincroniza.
 */
function LoyaltyPanel({
  data,
  isLoading,
  isError,
}: {
  data?: LoyaltyModel;
  isLoading: boolean;
  isError: boolean;
}) {
  if (isLoading) return <Panel title="Días por nivel de Fidelidad"><Loading /></Panel>;
  if (isError || !data) {
    return (
      <Panel title="Días por nivel de Fidelidad">
        <Note>No se pudo leer la calibración de fidelidad.</Note>
      </Panel>
    );
  }

  return (
    <Panel
      title="Días por nivel de Fidelidad"
      meta={
        data.transitions.length > 0
          ? `${data.transitions.length} transición(es) calibrada(s)`
          : "sin transiciones calibradas todavía"
      }
    >
      <div className="grid gap-4 border-b border-[var(--border)] p-4 sm:grid-cols-3">
        <Kpi
          label="Transiciones calibradas"
          value={String(data.transitions.length)}
          hint="de hasta 20 posibles (0→1 … 19→20)"
        />
        <Kpi label="Subidas observadas (limpias)" value={String(data.totalObservations)} />
        <Kpi
          label="Cruces vistos"
          value={String(data.crossingsSeen)}
          hint={
            data.discardedCrossings > 0
              ? `${data.discardedCrossings} descartado(s): salto de más de un nivel o sin ancla`
              : undefined
          }
        />
      </div>

      <div className="space-y-3 p-4 text-xs leading-relaxed text-[var(--muted)]">
        <p>
          Hattrick y Hattrick Control no publican ninguna fórmula para Fidelidad. El intervalo
          real parece constante entre jugadores para una misma transición de nivel, pero no
          entre niveles distintos — subir de 1 a 2 es rápido, subir de 19 a 20 puede tardar
          temporadas. Por eso aquí se calibra una tabla, transición por transición, en vez de un
          solo número como en Experiencia.
        </p>

        {data.transitions.length > 0 ? (
          <div>
            <b className="text-[var(--text)]">Días reales por transición</b>
            <div className="mt-2 flex flex-wrap gap-2">
              {data.transitions.map((t) => (
                <span
                  key={t.fromLevel}
                  className="rounded bg-[var(--surface-2)] px-2 py-1 font-mono text-[11px] text-[var(--text)]"
                  title={
                    t.stdDev != null
                      ? `${t.observations} observación(es) · desviación ${t.stdDev.toFixed(1)} días`
                      : `${t.observations} observación(es)`
                  }
                >
                  {t.fromLevel} → {t.toLevel}: {t.avgDays.toFixed(1)} días ({t.observations})
                </span>
              ))}
            </div>
            <p className="mt-2">
              La ficha de cada jugador usa esta tabla para mostrar un progreso decimal real
              dentro de su nivel actual — solo cuando su transición ya está aquí.
            </p>
          </div>
        ) : (
          <p>
            Todavía no se ha observado ninguna subida limpia de fidelidad en esta cuenta. Cada
            sincronización que capture una subida real añade la primera fila de la tabla.
          </p>
        )}

        <ReferenceNote reference={data.reference} />

        {data.levelUps.length > 0 && (
          <div>
            <b className="text-[var(--text)]">Subidas registradas</b>
            <ul className="mt-2 space-y-1 font-mono text-[11px]">
              {data.levelUps.map((lu, i) => (
                <li key={i}>
                  {lu.player}: {lu.fromLevel} → {lu.toLevel} en {lu.daysElapsed} días
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Panel>
  );
}

const INPUT_LABELS: Record<string, string> = {
  assistant_level_sum: "Ayudantes (suma de niveles)",
  intensity: "Intensidad",
  stamina_share: "% condición",
  coach_level: "Nivel del entrenador",
};

/**
 * Cierre de la fórmula de entrenamiento. Esta es la pantalla que responde
 * «¿de dónde sale este número?» sin dejar ningún valor puesto a mano
 * escondido: cada término muestra si se lee del CHPP o sigue siendo un
 * supuesto, y la fórmula se valida contra subidas que Hattrick confirma.
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
      meta={data.allRead ? "datos CHPP completos · perfil HTC estructural" : "faltan datos CHPP"}
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
            Validación contra subidas confirmadas
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
                value={v.meanErrorWeeks == null ? "—" : `${v.meanErrorWeeks} sem`}
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
            Todavía no hay dos subidas consecutivas en la habilidad entrenada para
            comparar. Cada sincronización con nuevas subidas la habilita.
          </p>
        )}
      </div>

      <div className="border-t border-[var(--border)] p-4 text-xs leading-relaxed text-[var(--muted)]">
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
