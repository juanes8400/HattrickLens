import { Fragment, useEffect, useState } from "react";
import clsx from "clsx";
import { Column, DataTable } from "../components/DataTable";
import { CountryFlag } from "../components/CountryFlag";
import { EnlaceATransparencia } from "../components/EnlaceATransparencia";
import { Specialty } from "../components/Specialty";
import { Tabs } from "../components/Tabs";
import { lecturaDeNivel } from "../utils/skillLevels";
import {
  Empty,
  ErrorState,
  Kpi,
  Loading,
  Note,
  Panel,
  SinDatos,
} from "../components/Panels";
import {
  useAcademy,
  useAcademyScouts,
  useAcademyScoutsLedger,
  useAcademyComparativa,
  useAcademySkillScores,
  useAcademyTrainingPlan,
} from "../hooks/useTeam";
import { date, decimal, money, number } from "../hooks/useFormat";
import type {
  Academy,
  AcademySkillScores,
  LineaDeEntrenamiento,
  ScoutsLedger,
  TrainingSlot,
  VeredictoDeMetodo,
} from "../services/api";

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
  w == null
    ? ""
    : w >= 10
      ? w.toFixed(0)
      : w >= 1
        ? w.toFixed(1)
        : w.toFixed(3);

/** Las tres vistas de la cantera. "Plantilla" abre por defecto: es la que
 *  responde "¿a quién tengo?", y las otras dos sólo tienen sentido después. */
/** 2026-08-24: «Techos de habilidad» y «Plantilla juvenil» eran la misma
 *  pregunta contada dos veces --a quién tengo y hasta dónde puede llegar--,
 *  así que se funden. La ficha de cada canterano lleva ahora su clasificación
 *  al lado de sus siete habilidades, que es lo que la sostiene. */
const VIEWS = [
  { key: "squad", label: "Plantilla juvenil" },
  { key: "train", label: "Selección de entrenamiento" },
  // "Formación" y no "A quién entrenar": esta pestaña YA no propone un
  // reparto teorico, decide la alineacion del proximo partido.
  { key: "who", label: "Formación siguiente partido" },
  { key: "scouts", label: "Ojeadores" },
  // 2026-08-26, pedido por el usuario. Antes esta tabla se pintaba DEBAJO de
  // todas las pestañas; con la academia recien abierta eran cero filas y no
  // molestaba, pero al llenarse `former_youth_players` --43 de golpe-- se
  // convirtio en ruido permanente. Aqui esta cuando se la busca y no cuando no.
  { key: "oldies", label: "Antiguos canteranos" },
] as const;

type ViewKey = (typeof VIEWS)[number]["key"];

/** La escalera de clasificaciones, de mejor a peor.
 *
 *  Es la misma que calcula `academy_engine` por el techo revelado: crack a
 *  partir de 8, promesa 7, aceptable 6, vendible 5, y por debajo fontanero.
 *  «Sin ojear» va al final porque no es una nota, es una ausencia: el ojeador
 *  todavía no ha revelado nada y no hay con qué juzgarlo.
 *
 *  Existe para ORDENAR. Alfabéticamente, «aceptable» iría delante de «crack»,
 *  que no responde ninguna pregunta que alguien se haga mirando la tabla. */
const ESCALERA_DE_CATEGORIAS = [
  "crack",
  "promesa",
  "aceptable",
  "vendible",
  "fontanero",
  "sin ojear",
] as const;

/** Su puesto en la escalera. Lo que no reconoce va al final, no al principio:
 *  una categoría nueva no puede colarse encabezando la tabla. */
function rangoDeCategoria(categoria: string): number {
  const i = ESCALERA_DE_CATEGORIAS.indexOf(
    categoria as (typeof ESCALERA_DE_CATEGORIAS)[number],
  );
  return i === -1 ? ESCALERA_DE_CATEGORIAS.length : i;
}

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

  /** Lleva una pareja de entrenamientos a la formación y salta allí.
   *
   *  Escribe las mismas claves que lee la pestaña de formación —que se monta
   *  al entrar, así que las recoge— y borra la marca de "esto lo adoptamos
   *  nosotros": lo que se lleva a mano manda sobre la recomendación, igual
   *  que si se hubiera elegido en los selectores. */
  const llevarALaFormacion = (main: string, secondary: string) => {
    try {
      localStorage.setItem("juveniles.principal", main);
      localStorage.setItem("juveniles.secundario", secondary);
      localStorage.removeItem("juveniles.sugerenciaAdoptada");
    } catch {
      // Almacenamiento bloqueado: se salta igual, sin recordar la elección.
    }
    setView("who");
  };

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return <SinDatos />;

  const profitable = data.net > 0;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Juveniles</h1>
        <p className="text-sm text-[var(--muted)]">
          Quién merece plaza, quién se pierde pronto y si la academia sale a
          cuenta
        </p>
      </header>

      {/* La cuenta de la academia sólo pinta algo junto a la plantilla: en
          «Qué entrenar» o «A quién entrenar» no se está decidiendo dinero, y
          cuatro cifras arriba compiten con lo que sí importa allí. */}
      {view === "squad" && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 [&>*]:min-w-0">
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
      )}

      {view === "squad" &&
        !profitable &&
        data.invested > 0 &&
        data.breakEvenSales > 0 && (
          <Note>
            Harían falta {data.breakEvenSales} venta(s) más al precio medio para
            equilibrar.
          </Note>
        )}

      {/* Dos pantallas seguidas que responden preguntas distintas, y sin
          decirlo se confunden: la primera elige QUÉ se entrena, la segunda a
          QUIÉN le llega. Una línea aquí ahorra tener que deducirlo. */}
      {(view === "train" || view === "who") && (
        <p className="text-sm text-[var(--muted)]">
          {view === "train" ? (
            <>
              <b className="text-[var(--text)]">Selección de entrenamiento</b>{" "}
              puntúa cada habilidad por lo que tu cantera puede ganar en ella, y
              de ahí sale la pareja recomendada. Los mandos de abajo son tuyos:
              mueve el corte del plazo o la separación entre peldaños y el
              ranking se recalcula. El reparto adopta la recomendación solo,
              hasta que elijas otra cosa a mano en la pestaña siguiente.
            </>
          ) : (
            <>
              <b className="text-[var(--text)]">Formación siguiente partido</b>{" "}
              reparte los dos entrenamientos elegidos entre los once y el
              banquillo. Cada entrenamiento llega a unos puestos y no a otros:
              quien cae donde se cruzan los dos recibe ambos. Dentro de cada
              tramo entran primero los mejores de la cola (peldaño, techo y
              edad), así que cambiar el secundario cambia quién juega dónde. La
              barra de «Puede llegar a» es su HTMS28: relleno lo que ya tiene, y
              hasta dónde llega la barra, lo máximo que podría alcanzar.
            </>
          )}
        </p>
      )}

      {data.urgent.length > 0 && (
        <Panel
          title="Plazo a punto de vencer"
          meta="lo urgente manda sobre lo importante"
        >
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
        <SkillDetail data={data} />
      ) : view === "train" ? (
        <WhatToTrain data={data} irALaFormacion={llevarALaFormacion} />
      ) : view === "who" ? (
        <QuienEntrena data={data} />
      ) : view === "scouts" ? (
        <Ojeadores />
      ) : (data.allGraduates ?? []).length > 0 ? (
        <Panel
          title="Antiguos canteranos"
          meta={`${(data.allGraduates ?? []).length} han pasado por aquí`}
        >
          <GraduatesTable data={data} />
        </Panel>
      ) : (
        <Panel title="Antiguos canteranos">
          <Empty>
            Todavía no hay ninguno: aparecen aquí en cuanto asciendas a un
            canterano al primer equipo.
          </Empty>
        </Panel>
      )}
    </div>
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
  // «Desconocido» y no «?». El interrogante ya significa otras dos cosas en
  // esta misma pantalla --media habilidad sabida (`4/?`) y veredicto
  // provisional (`vendible ?`)--, así que como cabecera de columna no decía
  // cuál de las tres era (2026-09-01, pedido del usuario).
  ["desconocidoPronto", "Desconocido ⏱", "sin revelar, y sale joven"],
  ["desconocidoTarde", "Desconocido", "sin revelar, y sale mayor"],
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
  [
    "slots",
    "Plazas que entrena",
    "a cuántos puestos de la alineación les llega ese entrenamiento",
  ],
  [
    "attack",
    "Aporte al ataque",
    "cuánto suma esa habilidad al ataque, según los coeficientes del Manual",
  ],
  [
    "midfield",
    "Aporte al mediocampo",
    "cuánto suma esa habilidad al mediocampo",
  ],
  ["defence", "Aporte a la defensa", "cuánto suma esa habilidad a la defensa"],
  [
    "senior",
    "Igual que el primer equipo",
    "16 a lo que entrena hoy el primer equipo, 0 al resto",
  ],
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

/** Los parámetros del método sobreviven a la recarga.
 *
 * Son la opinión del usuario sobre cómo puntuar su cantera --de dónde sale el
 * bonus, cuánto separan los peldaños, cuánto pesa ese bonus--, no un estado
 * de pantalla. Tenerlos que volver a poner cada vez convertía un ajuste
 * deliberado en algo que se perdía al pestañear.
 */
function recordado<T>(clave: string, porDefecto: T): T {
  const guardado = localStorage.getItem(clave);
  if (guardado === null) return porDefecto;
  try {
    return JSON.parse(guardado) as T;
  } catch {
    return porDefecto;
  }
}

function usePersistido<T>(clave: string, porDefecto: T) {
  const [valor, setValor] = useState<T>(() => recordado(clave, porDefecto));
  useEffect(() => {
    localStorage.setItem(clave, JSON.stringify(valor));
  }, [clave, valor]);
  return [valor, setValor] as const;
}

/** Texto suelto que sobrevive a recargar. Es `usePersistido` sin el JSON:
 *  estas tres claves se guardaron siempre como texto plano y meterlas en JSON
 *  ahora dejaria sin entender lo que ya hay guardado en cada navegador. */
function usePersistidoTexto(clave: string) {
  const [valor, setValor] = useState<string>(
    () => localStorage.getItem(clave) ?? "",
  );
  useEffect(() => {
    if (valor) localStorage.setItem(clave, valor);
    else localStorage.removeItem(clave);
  }, [clave, valor]);
  return [valor, setValor] as const;
}

/** Las cuatro ventanas del selector. «Último cambio» es el estado justo
 *  antes de que la academia se moviera por última vez; el resto son semanas. */
const VENTANAS_JUVENILES = [
  { key: "cambio", label: "Último cambio" },
  { key: "1", label: "1 semana" },
  { key: "2", label: "2 semanas" },
  { key: "8", label: "8 semanas" },
];

/** Cuánto se movió un puntaje, o un punto si no se movió. */
function MovimientoDelPuntaje({ delta }: { delta: number | null }) {
  if (delta == null || delta === 0) {
    return (
      <span className="w-12 text-left text-xs text-[var(--muted)]">·</span>
    );
  }
  return (
    <span
      className={clsx(
        "w-12 text-left text-xs tabular-nums",
        delta > 0 ? "text-[var(--positive)]" : "text-[var(--danger)]",
      )}
      title="cuánto se movió el puntaje en la ventana elegida"
    >
      {delta > 0 ? "+" : "−"}
      {decimal(Math.abs(delta), 3)}
    </span>
  );
}

/** Por qué se movieron los puntajes, en una frase.
 *
 *  El número solo no sirve para decidir nada: lo accionable es saber que
 *  subió porque el ojeador reveló dos techos, no que subió 0,041. */
function explicaElMovimiento(r: {
  skillsUp: number;
  ceilingsRevealed: number;
  arrivals: number;
}): string {
  const partes: string[] = [];
  if (r.skillsUp) partes.push(`${r.skillsUp} habilidad(es) subieron de nivel`);
  if (r.ceilingsRevealed)
    partes.push(`el ojeador reveló ${r.ceilingsRevealed} techo(s)`);
  if (r.arrivals) partes.push(`llegaron ${r.arrivals} canterano(s)`);
  if (partes.length === 0)
    return "Nada se movió en la academia en esa ventana.";
  return `${partes.join(", ")}. Eso es lo que movió los puntajes.`;
}

function WhatToTrain({
  data,
  irALaFormacion,
}: {
  data: Academy;
  irALaFormacion: (main: string, secondary: string) => void;
}) {
  const [soonMaxDays, setSoonMaxDays] = usePersistido(
    "juveniles.soonMaxDays",
    DEFAULT_SOON_MAX_DAYS,
  );
  const [weightBase, setWeightBase] = usePersistido(
    "juveniles.weightBase",
    DEFAULT_WEIGHT_BASE,
  );
  const [trainableMethod, setTrainableMethod] = usePersistido(
    "juveniles.trainableMethod",
    "edit",
  );
  // Arranca en las plazas que de verdad entrena cada cosa, no en ceros: son
  // números que la aplicación ya sabe, y hacérselos teclear era pedirle al
  // usuario que copiara una tabla nuestra a mano.
  const [trainable, setTrainable] = usePersistido<Record<string, number>>(
    "juveniles.trainable",
    {},
  );
  const [sembrado, setSembrado] = useState(false);
  // El peso del bonus es INDEPENDIENTE de la escalera (pedido del usuario,
  // 2026-09-01: «cuando muevo la barra de Separación entre peldaños se mueve
  // automáticamente Peso del bonus personalizado, eso es incorrecto»).
  //
  // Antes `null` significaba «que lo sugiera la escalera», y como la
  // sugerencia se recalcula con la base, arrastrar un mando movía el otro
  // delante de tus ojos. La escalera describe a la cantera; este peso
  // describe cuánto quieres que cuente TU criterio. No tienen por qué
  // moverse juntos.
  //
  // `null` sigue existiendo pero sólo hasta la primera respuesta: se siembra
  // con la sugerencia y a partir de ahí es un número tuyo que no se mueve
  // solo. El enlace «volver al sugerido» sigue ahí para pedirla a propósito.
  const [bonusWeight, setBonusWeight] = usePersistido<number | null>(
    "juveniles.bonusWeight",
    null,
  );
  // Contra qué se compara el puntaje. La misma clave la lee la tabla de la
  // plantilla, que es otra pestaña y por tanto se remonta al abrirla: así las
  // dos hablan de la misma ventana sin tener que subir el estado a la página
  // (2026-09-04, pedido del usuario).
  const [ventana, setVentana] = usePersistido("juveniles.ventana", "cambio");
  const tuned = useAcademySkillScores({
    soonMaxDays,
    weightBase,
    trainableMethod,
    trainable,
    trainableWeight: bonusWeight,
  });
  // Los MISMOS parámetros: un puntaje de antes calculado con otra opinión no
  // se puede restar del de ahora.
  const movimiento = useAcademyComparativa({
    ventana,
    soonMaxDays,
    weightBase,
    trainableMethod,
    trainable,
    trainableWeight: bonusWeight,
  });
  const deltas = new Map(
    (movimiento.data?.scores ?? []).map((x) => [x.skill, x.delta]),
  );
  const resumen = movimiento.data?.summary;
  const sinBase = movimiento.data ? !movimiento.data.hasBaseline : false;

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
  // Sembrar es para la PRIMERA vez. Si ya hay algo guardado, es lo que el
  // usuario tecleó y no se pisa.
  //
  // Se ajusta durante el renderizado en vez de en un efecto: es el patrón que
  // React documenta para "corregir el estado cuando cambian los datos", y un
  // efecto aquí provocaba un renderizado en cascada --pintar, medir, volver a
  // pintar-- que además es lo que avisaba el linter.
  if (!sembrado && Object.keys(plazas).length > 0) {
    setSembrado(true);
    if (Object.keys(trainable).length === 0) setTrainable(plazas);
  }
  // `null` significa «adopta la sugerencia», y en cuanto se sabe cuál es, se
  // convierte en un número propio que la escalera ya no empuja.
  //
  // Se siembra desde `suggestedWeight` y NO desde `trainableWeight`: al pulsar
  // «usar el sugerido» el estado pasa a `null` y esto corre en el mismo
  // renderizado, cuando `trainableWeight` todavía trae el valor ANTERIOR. Con
  // él, el enlace se quedaba inerte --sembraba de vuelta lo mismo que acababas
  // de descartar-- (visto al probarlo, 2026-09-01).
  if (bonusWeight === null && suggestedWeight != null) {
    setBonusWeight(suggestedWeight);
  }
  const top = rows[0];
  if (!top) return null;
  const max = Math.max(...rows.map((r) => r.score), 1e-9);
  // «Está en los valores originales» ya no puede mirar si el peso del bonus
  // es `null`: desde que se siembra nunca vuelve a serlo. Lo que importa es
  // si COINCIDE con el que sugiere la escalera.
  const bonusEsElSugerido =
    bonusWeight === null ||
    suggestedWeight == null ||
    Math.abs(bonusWeight - suggestedWeight) < 1e-6;
  const isDefault =
    soonMaxDays === DEFAULT_SOON_MAX_DAYS &&
    weightBase === DEFAULT_WEIGHT_BASE &&
    trainableMethod === "edit" &&
    bonusEsElSugerido &&
    plazasIguales(trainable, plazas);

  return (
    <Panel
      title="Selección de entrenamiento"
      meta={
        <span className="flex items-center gap-2">
          una habilidad, la reciben todos
          <EnlaceATransparencia seccion="juveniles" calculo="puntaje" />
        </span>
      }
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border)] px-4 py-2">
        <span className="text-xs text-[var(--muted)]">
          Cuánto se movió cada puntaje desde
        </span>
        <Tabs
          modo="filtro"
          label="Desde cuándo se compara el puntaje"
          tabs={VENTANAS_JUVENILES}
          active={ventana}
          onChange={setVentana}
        />
      </div>
      {/* Las DOS, no una. Y la segunda con apellido: la misma habilidad se
          entrena por caminos distintos y cada uno llega a gente distinta.
          Con «Defensa» arriba, «Pases» a secas no toca a ningún defensa y
          nadie recibiría las dos cosas; la variante de defensas deja cinco. */}
      {(sinBase || resumen) && (
        <div className="border-b border-[var(--border)] px-4 py-2 text-xs leading-relaxed text-[var(--muted)]">
          {sinBase ? (
            <>No hay histórico tan atrás: los puntajes se enseñan quietos.</>
          ) : (
            <>{explicaElMovimiento(resumen!)}</>
          )}
        </div>
      )}

      <div className="border-b border-[var(--border)] px-4 py-3 text-sm">
        {sugerencia ? (
          <>
            Ahora mismo conviene entrenar{" "}
            <b className="text-[var(--youth-known)]">{sugerencia.mainLabel}</b>,
            y de secundario{" "}
            <b className="text-[var(--youth-known)]">
              {sugerencia.secondaryLabel}
            </b>
            .
            {sugerencia.bothCount > 0 ? (
              <span className="text-[var(--muted)]">
                {" "}
                Así {sugerencia.bothCount}{" "}
                {sugerencia.bothCount === 1 ? "recibe" : "reciben"} las dos
                cosas.
              </span>
            ) : (
              <span className="text-[var(--muted)]">
                {" "}
                No hay ningún puesto que reciba las dos.
              </span>
            )}
            {/* El botón va PEGADO a la recomendación, no en otra pantalla:
                el momento de llevársela es justo cuando se acaba de leer. */}
            <button
              onClick={() =>
                irALaFormacion(sugerencia.main, sugerencia.secondary)
              }
              data-track="Juveniles: llevar sugerencia a la formación"
              className="ml-2 rounded-md border border-[var(--accent)] px-2 py-1 text-xs font-medium text-[var(--accent)]"
            >
              Llevar a la formación
            </button>
          </>
        ) : (
          <>
            Ahora mismo conviene entrenar{" "}
            <b className="text-[var(--youth-known)]">{top.label}</b>.
          </>
        )}
        {/* El porqué, en números. El método entero está en el enlace de la
            cabecera del panel. */}
        {sugerencia?.method && <PorQue m={sugerencia.method} />}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-[var(--muted)]">
              <th className="px-4 py-2 text-left font-medium">Habilidad</th>
              {BUCKETS.map(([key, short, long]) => (
                <th
                  key={key}
                  className="px-2 py-2 text-right font-medium"
                  title={long}
                >
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
                    {r.counts[key] ? (
                      r.counts[key]
                    ) : (
                      <span className="text-[var(--muted)]">·</span>
                    )}
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
                        setTrainable((t) => ({
                          ...t,
                          [r.skill]: Number(e.target.value) || 0,
                        }))
                      }
                      className="w-12 rounded border border-[var(--border)] bg-[var(--surface)] px-1 py-0.5 text-right tabular-nums"
                    />
                  ) : (
                    <span className="tabular-nums">
                      {/* Con decimales: los métodos por bloque reparten
                          fracciones y redondear empataría habilidades que la
                          fórmula sí distingue. */}
                      {r.trainableCount ? (
                        decimal(r.trainableCount, 2)
                      ) : (
                        <span className="text-[var(--muted)]">·</span>
                      )}
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
                    {/* Un punto cuando no se movió, nunca «+0.000»: siete
                        filas de ceros esconden las dos que sí cambiaron. */}
                    <MovimientoDelPuntaje delta={deltas.get(r.skill) ?? null} />
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

        <div className="grid gap-4 md:grid-cols-3 [&>*]:min-w-0">
          <label className="block">
            <div className="text-xs">
              Salen de menos de 17 años y{" "}
              <b className="tabular-nums text-[var(--youth-known)]">
                {soonMaxDays}
              </b>{" "}
              días
            </div>
            <input
              type="range"
              min={0}
              max={112}
              step={1}
              value={soonMaxDays}
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
              type="range"
              min={1}
              max={4}
              step={0.5}
              value={weightBase}
              onChange={(e) => setWeightBase(Number(e.target.value))}
              className="mt-1 w-full accent-[var(--youth-known)]"
            />
          </label>
          <label className="block">
            <div className="flex items-baseline justify-between gap-2 text-xs">
              <span className="truncate">Peso del bonus personalizado</span>
              <b className="shrink-0 tabular-nums">
                {formatWeight(trainableWeight)}
              </b>
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
            {/* La escalera SUGIERE un peso, pero no lo mueve: este mando es
                independiente y sólo cambia si lo cambias tú o si pides la
                sugerencia a propósito. */}
            <div className="text-[10px] text-[var(--muted)]">
              {bonusEsElSugerido ? (
                <>coincide con lo que sugiere la escalera</>
              ) : (
                <button
                  type="button"
                  onClick={() => setBonusWeight(null)}
                  className="underline"
                >
                  usar el sugerido ({formatWeight(suggestedWeight)})
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
  compact = false,
}: {
  current: number | null;
  maximum: number | null;
  maxReached: boolean;
  compact?: boolean;
}) {
  const { palabra, numeros, ancho, crece } = lecturaDeNivel(
    current,
    maximum,
    maxReached,
  );
  const color =
    ancho === 0 ? "transparent" : crece ? "var(--positive)" : "var(--danger)";

  // En la tabla dinámica el nivel numérico es la evidencia que más se
  // compara entre filas. Va primero y como una pequeña pastilla: si quedaba
  // después de palabra + barra, el extremo derecho de la tabla hacía que
  // `4/?` pareciera ausente aunque estuviera en el DOM.
  if (compact) {
    return (
      <span
        className="flex items-center gap-2"
        title={`${palabra} · ${numeros}`}
      >
        <span className="w-3 shrink-0 text-center leading-none">
          {maxReached ? (
            <span title="ya tocó techo: no sube más">🔒</span>
          ) : null}
        </span>
        <span className="min-w-10 shrink-0 rounded bg-[var(--surface-2)] px-1.5 py-0.5 text-center text-xs font-semibold tabular-nums text-[var(--text)]">
          {numeros}
        </span>
        <span className="w-20 shrink-0 text-xs">{palabra}</span>
        <span className="h-1.5 w-12 shrink-0 overflow-hidden rounded bg-[var(--surface-2)]">
          <span
            className="block h-full"
            style={{ width: `${ancho}%`, background: color }}
          />
        </span>
      </span>
    );
  }

  return (
    <span className="flex items-center gap-2">
      {/* El candado va PRIMERO y en un hueco de ancho fijo: al final de la
          fila desplazaba el resto y las filas quedaban desalineadas entre sí,
          unas con candado y otras sin él. */}
      <span className="w-4 shrink-0 text-center leading-none">
        {maxReached ? <span title="ya tocó techo: no sube más">🔒</span> : null}
      </span>
      <span className="w-24 shrink-0 text-sm">{palabra}</span>
      <span className="h-1.5 w-16 shrink-0 overflow-hidden rounded bg-[var(--surface-2)]">
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
 *
 * Los nombres NO son inventados: cada corte del motor cae justo en un nivel
 * de Hattrick y lleva la palabra que el juego le da —excelente es 8, bueno
 * 7, aceptable 6, insuficiente 5—. Por eso el último dice «débil o menos» y
 * no «el resto»: recoge de nulo a débil, cinco niveles que ninguna palabra
 * suelta cubre, y nombrarlo por su techo es lo único que sigue la regla.
 * Si algún día se mueve un corte en `youth_skill_score`, la palabra de aquí
 * se mueve con él.
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
  9: "débil o menos",
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
          <li
            key={p.name}
            className="flex items-center justify-between gap-3 px-4 py-2 text-sm"
          >
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
                <span
                  className="shrink-0 text-[10px] text-[var(--youth-known)]"
                  title="sale con menos de 17;038"
                >
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

/** Las cuatro regiones del diagrama de Venn, en el orden en que se llenan.
 *
 * Los puestos que reciben los dos entrenamientos son la plaza más valiosa que
 * hay, así que ahí van los primeros de la cola. El banquillo se llena después
 * con el mismo orden.
 */
const REGIONES: Record<string, { titulo: string; pista: string }> = {
  ambos: { titulo: "Reciben los dos entrenamientos", pista: "" },
  solo_principal: { titulo: "Solo el principal", pista: "" },
  solo_secundaria: { titulo: "Solo el secundario", pista: "" },
  sin_entrenamiento: {
    titulo: "Sin entrenamiento",
    pista: "no les llega ninguno de los dos",
  },
};

/** `15;028`, el formato de Hattrick. */
function edadCorta(dias: number): string {
  return `${Math.floor(dias / 112)};${String(dias % 112).padStart(3, "0")}`;
}

/** Los nombres oficiales de Hattrick, los mismos que usa Alineación. */
const PUESTOS: Record<string, string> = {
  keeper: "Portero",
  wingback: "Defensa Lateral",
  central_defender: "Defensa Central",
  winger: "Extremo",
  inner_midfield: "Mediocentro",
  forward: "Delantero",
};

/** El nombre corto de un entrenamiento, para una cabecera de columna.
 *
 * «Pases (defensas y centro del campo completo)» no cabe en una columna, y
 * repetido en cada fila tapaba la tabla entera. En la cabecera va la parte
 * corta y el nombre completo en el título. */
function nombreCorto(etiqueta: string): string {
  const parentesis = etiqueta.indexOf(" (");
  return parentesis > 0 ? etiqueta.slice(0, parentesis) : etiqueta;
}

/** En qué se puede convertir, de lo peor a lo mejor.
 *
 * La barra va de cero al HTMS28 MÁXIMO —así su largo dice hasta dónde puede
 * llegar— y se rellena hasta el MÍNIMO. Lo relleno es lo que ya tiene
 * asegurado; el hueco que queda hasta el final es lo que el ojeador todavía
 * no ha dicho, y se encoge solo según va hablando.
 *
 * Todas las filas se miden contra el mismo tope: si cada una se midiera a sí
 * misma, dos barras del mismo largo dirían cosas distintas.
 */
function Horquilla({
  min,
  max,
  tope,
}: {
  min: number;
  max: number;
  tope: number;
}) {
  const pct = (n: number) => (tope > 0 ? Math.min(100, (n / tope) * 100) : 0);
  return (
    <span
      className="flex h-4 items-center justify-end gap-2"
      title={`Entre ${min} y ${max} puntos HTMS28. Lo relleno es lo que ya tiene; el resto, lo que aún no se sabe de él.`}
    >
      <span className="tabular-nums text-[var(--muted)]">{min}</span>
      <span className="relative h-1.5 w-16 shrink-0">
        <span
          className="absolute inset-y-0 left-0 rounded bg-[var(--surface-2)]"
          style={{ width: `${pct(max)}%` }}
        />
        <span
          className="absolute inset-y-0 left-0 rounded bg-[var(--accent)]"
          style={{ width: `${pct(min)}%` }}
        />
      </span>
      <span className="tabular-nums">{max}</span>
    </span>
  );
}

/** `66,7%`, con coma y sin decimal cuando es redondo. */
function porcentaje(n: number): string {
  return `${n % 1 === 0 ? n : n.toFixed(1).replace(".", ",")}%`;
}

/** Lo que recibe un canterano de UN entrenamiento: «Lateral: 100% ███».
 *
 * El nombre va dentro de la celda y no en la cabecera: la cabecera dice qué
 * hueco es --principal o secundario-- y la celda dice qué le toca ahí.
 *
 * El número ya viene con el castigo del hueco secundario aplicado, así que
 * es lo que de verdad recibe, no la casilla de la tabla de ritmos. */
/** Una línea de entrenamiento dentro de su propia fila de tabla.
 *
 * Antes era un numero. Con «Individual» ese numero pasaba a ser una MEDIA, y
 * una media aqui engaña: mezcla un 66,7% de Pases con un 28,3% de Lateral como
 * si valieran lo mismo, y esconde lo mas util de saber -que en un extremo la
 * habilidad MAS probable es la que PEOR entrena-.
 *
 * `probability` en null significa «esto pasa siempre», no «no se sabe»: es la
 * diferencia entre un sorteo y un entrenamiento que sube dos cosas a la vez.
 * Por eso «Anotación y balón parado» sale con sus dos lineas y sin «(proba:)».
 *
 * Un entrenamiento corriente trae UNA línea. Individual trae varias y la
 * tabla repite filas, no el nombre del jugador: así velocidad, probabilidad y
 * nivel de cada habilidad siguen estando alineados horizontalmente.
 */
function Celda({
  linea,
  muestraVacio = false,
}: {
  linea?: LineaDeEntrenamiento;
  muestraVacio?: boolean;
}) {
  if (!linea) {
    return muestraVacio ? <span className="text-[var(--muted)]">·</span> : null;
  }
  return (
    <span
      className="grid grid-cols-[auto_auto] items-center justify-start gap-2 whitespace-nowrap"
      /* El porcentaje ya lleva descontado el castigo del hueco. Con guardas:
         `base` y `penalty` pueden faltar en una respuesta antigua cacheada. */
      title={
        linea.base == null || linea.penalty == null || linea.penalty >= 1
          ? `${linea.label}: ${porcentaje(linea.rate)}`
          : `${linea.label} rinde ${porcentaje(linea.base)} de principal; aquí, de ` +
            `secundario, ${porcentaje(linea.rate)}`
      }
    >
      <Racion cuanto={linea.rate} etiqueta={linea.label} />
      {linea.probability != null && (
        <span className="shrink-0 text-[11px] tabular-nums text-[var(--muted)]">
          (proba: {linea.probability}%)
        </span>
      )}
    </span>
  );
}

/** Compatibilidad con una respuesta cacheada anterior a `mainLines`: no
 * inventa habilidades para Individual, pero mantiene visible el entrenamiento
 * corriente que el contrato antiguo sí describía con una sola ración. */
function lineasDe(
  asignacion: TrainingSlot,
  hueco: "principal" | "secundario",
  etiqueta: string,
): LineaDeEntrenamiento[] {
  const recibidas =
    hueco === "principal" ? asignacion.mainLines : asignacion.secondaryLines;
  if (recibidas?.length) return recibidas;

  const rate =
    hueco === "principal"
      ? asignacion.racionPrincipal
      : asignacion.racionSecundaria;
  if (rate <= 0) return [];
  const level =
    hueco === "principal" ? asignacion.mainLevel : asignacion.secondaryLevel;
  return [
    {
      skill: `${hueco}-legacy`,
      label: etiqueta,
      rate,
      probability: null,
      level,
    },
  ];
}

/** El nombre de cada peldaño, para poder decir QUÉ se quitó en la prueba de
 *  robustez. Son las claves que manda el motor. */
const PELDANOS: Record<string, string> = {
  excelente: "excelente",
  bueno_pronto: "bueno joven",
  bueno_tarde: "bueno",
  aceptable_pronto: "aceptable joven",
  aceptable_tarde: "aceptable",
  desconocido_pronto: "sin revelar joven",
  desconocido_tarde: "sin revelar",
};

/** Por qué se recomienda lo que se recomienda, con los números detrás.
 *
 * Aquí vivía además una frase que narraba el veredicto --«X se cae por detrás
 * de Y si le quitas su mejor canterano, así que doblarla concentraría en uno
 * solo…»--. Fuera el 2026-09-01, no le gustaba al usuario, y con razón: contaba
 * con palabras lo que los cuatro números de debajo ya dicen, y lo contaba en
 * tres líneas que había que leer enteras para llegar a lo mismo.
 *
 * Los números se quedan, que son los que de verdad deciden --el respaldo, el
 * no-respaldo y la prueba de quitar al mejor--: verlos permite discutir con la
 * recomendación en vez de obedecerla. Y el método completo está a un clic, en
 * el enlace del panel.
 */
function PorQue({ m }: { m: VeredictoDeMetodo }) {
  const pct = (x: number) => `${Math.round(x * 100)}%`;
  const dato = (k: string, v: string, ayuda: string) => (
    <span key={k} className="whitespace-nowrap" title={ayuda}>
      <span className="text-[var(--muted)]">{k} </span>
      <b className="font-medium tabular-nums text-[var(--text)]">{v}</b>
    </span>
  );
  const quitado = m.robustness.removedRung
    ? (PELDANOS[m.robustness.removedRung] ?? m.robustness.removedRung)
    : null;
  return (
    <div className="mt-1 space-y-1">
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px]">
        {dato(
          "puntaje",
          m.main.score.toFixed(2),
          "El de la habilidad principal",
        )}
        {dato(
          "respaldo",
          `${m.main.backed} en peldaño alto`,
          "Canteranos en «aceptable joven» o mejor. Con cero, la habilidad cede el hueco a Individual",
        )}
        {dato(
          "no es respaldo",
          pct(m.main.unbacked),
          `Gente sin revelar más el bonus puesto a mano. Desde ${pct(m.threshold)} la habilidad queda descartada`,
        )}
        {quitado &&
          dato(
            "sin su mejor",
            `${m.robustness.scoreWithout.toFixed(2)} ${m.robustness.held ? "· aguanta" : `· lo adelanta ${m.robustness.overtakenBy ?? "otra"}`}`,
            `Se le quita un «${quitado}» y se vuelve a ordenar. Si aguanta en cabeza su fuerza es un grupo y se dobla; si se cae, era un solo chico`,
          )}
        {m.second &&
          dato(
            `2.ª (${m.second.label})`,
            `${m.second.backed ?? 0} en peldaño alto${m.second.unbacked == null ? "" : ` · ${pct(m.second.unbacked)} no es respaldo`}`,
            "La segunda del ranking: entra al hueco secundario solo si tiene respaldo",
          )}
      </div>
    </div>
  );
}

/** Los tres tramos del rendimiento, elegidos con el usuario el 2026-08-30.
 *  Son del ENTRENAMIENTO que llega a esa plaza, no del nivel del canterano. */
function colorDeRacion(cuanto: number): string {
  if (cuanto >= 80) return "var(--positive)";
  if (cuanto >= 30) return "var(--warning)";
  return "var(--danger)";
}

function Racion({ cuanto, etiqueta }: { cuanto: number; etiqueta: string }) {
  if (cuanto === 0) return <span className="text-[var(--muted)]">·</span>;
  const color = colorDeRacion(cuanto);
  return (
    /* Rejilla, no flex: la barra tiene que empezar en la MISMA x en todas las
       líneas de la celda. Con flex la empujaba la etiqueta de delante --que
       mide distinto en «Lateral» y en «Balón parado»-- y las barras parecían
       de anchos distintos cuando siempre midieron lo mismo. */
    <span
      className="grid grid-cols-[8.5rem_2.5rem] items-center gap-2"
      title={etiqueta}
    >
      <span className="truncate" style={{ color }}>
        {nombreCorto(etiqueta)}:{" "}
        <span className="tabular-nums">{porcentaje(cuanto)}</span>
      </span>
      {/* La PISTA y el RELLENO llevan la misma forma de pastilla. Con la
          curva solo en la pista, un relleno corto quedaba mordido por ella
          --en 11 px de ancho la curva se come casi la mitad-- y se leia mas
          bajo que uno largo aunque los dos midan 6 px clavados. Y un minimo
          de ancho para que un porcentaje diminuto siga siendo una barra y no
          un punto. */}
      <span className="h-1.5 overflow-hidden rounded-full bg-[var(--surface-2)]">
        {/* Topeada en 100 aunque el número pase: Balón parado da 125 al
            portero, y una barra desbordada no dice más que una llena. */}
        <span
          className="block h-full rounded-full"
          style={{
            width: `${Math.max(15, Math.min(100, cuanto))}%`,
            background: color,
          }}
        />
      </span>
    </span>
  );
}

/** El reparto como tabla: una columna por entrenamiento, y el nombre del
 *  entrenamiento UNA vez, en la cabecera. Antes cada fila repetía las dos
 *  etiquetas enteras y no había forma de comparar dos jugadores de un
 *  vistazo, que es justo para lo que sirve una tabla. */
function TablaDelReparto({
  titulo,
  pie,
  filas,
  mainLabel,
  secondaryLabel,
}: {
  titulo: string;
  pie?: string;
  filas: TrainingSlot[];
  mainLabel: string;
  secondaryLabel: string;
}) {
  if (filas.length === 0) return null;
  //  Todas las barras contra la misma escala; si cada fila se midiera a si
  //  misma, dos horquillas del mismo largo dirian cosas distintas.
  const topeDeHorquilla = Math.max(...filas.map((a) => a.htms28Max), 1);
  const th = "px-3 py-2 text-xs font-medium text-[var(--muted)]";
  const td = "overflow-hidden px-3 py-1.5 whitespace-nowrap";

  return (
    <div className="p-4">
      <div className="flex items-baseline gap-2">
        <h3 className="text-sm font-medium">{titulo}</h3>
        <span className="text-xs text-[var(--muted)]">
          {filas.length}
          {pie && ` · ${pie}`}
        </span>
      </div>

      <div className="mt-2 overflow-x-auto">
        {/* Anchos fijos e iguales en las dos tablas: si cada una se mide a
            su contenido, «El once» y «El banquillo» no cuadran en vertical. */}
        <table className="w-full min-w-[104rem] table-fixed text-sm">
          <colgroup>
            {/* Identidad y contexto ocupan lo justo; el 75% queda para la
                decisión real: qué entrena y en qué nivel está cada habilidad. */}
            <col className="w-[11%]" />
            <col className="w-[4%]" />
            <col className="w-[10%]" />
            <col className="w-[18%]" />
            <col className="w-[15%]" />
            <col className="w-[22%]" />
            <col className="w-[20%]" />
          </colgroup>
          <thead className="bg-[var(--surface-2)]">
            <tr>
              <th scope="col" className={`${th} text-left`}>
                Jugador
              </th>
              <th scope="col" className={`${th} text-right`}>
                Edad
              </th>
              <th
                scope="col"
                className={`${th} text-right`}
                title="en qué se puede convertir, en HTMS28: entre lo que ya tiene y lo que puede llegar a tener"
              >
                {/* La unidad va escrita, no solo en el `title`: la barra sola
                    no dice qué mide, y descubrirlo exige pasar el ratón por
                    encima y saber que hay algo que descubrir. */}
                HTMS28
              </th>
              <th scope="col" className={`${th} text-left`} title={mainLabel}>
                Entrenamiento habilidad primaria
              </th>
              <th scope="col" className={`${th} text-left`}>
                Nivel habilidad primaria
              </th>
              <th
                scope="col"
                className={`${th} border-l border-[var(--border)] pl-5 text-left`}
                title={`${secondaryLabel}: los porcentajes ya llevan descontado el castigo del hueco secundario`}
              >
                {/* El aviso de que el castigo ya está descontado vive solo en
                    el `title`: el mismo sorteo vale 42,5 % de principal y
                    28,3 % de secundario, así que hace falta decirlo, pero
                    repetirlo bajo la cabecera cargaba la tabla. */}
                Entrenamiento habilidad secundaria
              </th>
              <th scope="col" className={`${th} pr-6 text-left`}>
                Nivel habilidad secundaria
              </th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(REGIONES).map(([clave, { titulo: t, pista }]) => {
              const suyas = filas.filter((a) => a.region === clave);
              if (suyas.length === 0) return null;
              return (
                <Fragment key={clave}>
                  <tr>
                    <th
                      scope="colgroup"
                      colSpan={7}
                      className="border-t border-[var(--border)] px-3 pb-1 pt-3 text-left text-xs font-normal text-[var(--muted)]"
                    >
                      {t}
                      {pista && ` · ${pista}`}
                    </th>
                  </tr>
                  {suyas.map((a) => {
                    const principales = lineasDe(a, "principal", mainLabel);
                    const secundarias = lineasDe(
                      a,
                      "secundario",
                      secondaryLabel,
                    );
                    const cuantas = Math.max(
                      1,
                      principales.length,
                      secundarias.length,
                    );
                    return (
                      <Fragment key={a.player}>
                        {Array.from({ length: cuantas }, (_, indice) => {
                          const primera = indice === 0;
                          const lineaPrincipal = principales[indice];
                          const lineaSecundaria = secundarias[indice];
                          return (
                            <tr
                              key={`${a.player}-${indice}`}
                              className={
                                primera
                                  ? "h-10 border-t border-[var(--border)]"
                                  : "h-10 border-t border-dashed border-[var(--border)]/60"
                              }
                            >
                              <td className={`${td} text-left`}>
                                {primera && (
                                  <>
                                    <span className="font-medium">
                                      {a.player}
                                    </span>
                                    <span className="block text-xs text-[var(--muted)]">
                                      {PUESTOS[a.puesto] ?? a.puesto ?? ""}
                                    </span>
                                  </>
                                )}
                              </td>
                              <td
                                className={`${td} text-right tabular-nums text-[var(--muted)]`}
                              >
                                {primera ? edadCorta(a.ageDaysTotal) : null}
                              </td>
                              <td className={`${td} text-right`}>
                                {primera && (
                                  <Horquilla
                                    min={a.htms28Min}
                                    max={a.htms28Max}
                                    tope={topeDeHorquilla}
                                  />
                                )}
                              </td>
                              <td className={`${td} text-left`}>
                                <Celda
                                  linea={lineaPrincipal}
                                  muestraVacio={
                                    primera && principales.length === 0
                                  }
                                />
                              </td>
                              <td className={`${td} text-left`}>
                                {lineaPrincipal && (
                                  <NivelDeHabilidad
                                    current={lineaPrincipal.level.current}
                                    maximum={lineaPrincipal.level.maximum}
                                    maxReached={lineaPrincipal.level.maxReached}
                                    compact
                                  />
                                )}
                              </td>
                              <td
                                className={`${td} border-l border-[var(--border)] pl-5 text-left`}
                              >
                                <Celda
                                  linea={lineaSecundaria}
                                  muestraVacio={
                                    primera && secundarias.length === 0
                                  }
                                />
                              </td>
                              <td className={`${td} pr-6 text-left`}>
                                {lineaSecundaria && (
                                  <NivelDeHabilidad
                                    current={lineaSecundaria.level.current}
                                    maximum={lineaSecundaria.level.maximum}
                                    maxReached={
                                      lineaSecundaria.level.maxReached
                                    }
                                    compact
                                  />
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </Fragment>
                    );
                  })}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
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
      .sort((x, y) => x.ageDaysTotal - y.ageDaysTotal);
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
  const [main, setMain] = usePersistidoTexto("juveniles.principal");
  const [secondary, setSecondary] = usePersistidoTexto("juveniles.secundario");
  //  Cuál fue la última recomendación que adoptamos nosotros. Distinguirlo de
  //  una elección suya es lo que hace que el reparto siga a la recomendación
  //  sin pisar lo que él ponga a mano.
  const [adoptado, setAdoptado] = usePersistidoTexto(
    "juveniles.sugerenciaAdoptada",
  );
  const principal = main || opciones[0]?.code || habilidades[0]?.skill || "";
  const secundaria = secondary || opciones[1]?.code || principal;

  // El reparto sigue a la recomendación SOLO, sin botón que pulsar.
  //
  // Pero una elección a mano manda sobre ella: se recuerda cuál fue la última
  // recomendación adoptada, y sólo se adopta la nueva si lo que hay puesto
  // sigue siendo esa. Si el usuario cambió un selector, su elección se queda
  // hasta que la vuelva a cambiar él.
  const sugerencia = tuned?.suggestion ?? null;
  // Se ajusta durante el renderizado, no en un efecto: es el patrón que React
  // documenta para "corregir el estado cuando cambian los datos". Con efecto,
  // la pantalla se pintaba con la elección vieja y volvía a pintarse con la
  // nueva —un parpadeo, y el renderizado en cascada que avisaba el linter—.
  //
  // Lo que se guarda va aparte, en `usePersistido`: aquí sólo se toca estado,
  // que es lo que mantiene puro el renderizado.
  if (sugerencia) {
    const puesto = `${main}|${secondary}`;
    const nueva = `${sugerencia.main}|${sugerencia.secondary}`;
    // `puesto === adoptado` = lo que hay puesto lo pusimos nosotros, no él.
    // Si tocó un selector, `eligeAMano` borra la marca y esto deja de entrar.
    if (nueva !== puesto && (puesto === "|" || puesto === adoptado)) {
      setMain(sugerencia.main);
      setSecondary(sugerencia.secondary);
      setAdoptado(nueva);
    }
  }

  //  Cambiar un selector a mano rompe el seguimiento hasta nueva orden: al
  //  borrar la marca, lo que hay puesto deja de ser "lo que pusimos nosotros".
  const eligeAMano = (poner: (v: string) => void) => (v: string) => {
    poner(v);
    setAdoptado("");
  };

  const plan = useAcademyTrainingPlan({
    main: principal,
    secondary: secundaria,
    soonMaxDays,
    weightBase,
  });

  if (opciones.length === 0 && habilidades.length === 0) return null;

  const selector = (
    valor: string,
    onChange: (v: string) => void,
    etiqueta: string,
    recuerdo: string,
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
        {/* El principal SI puede repetirse de secundario: Hattrick lo permite
            y lo castiga bajando el hueco secundario de dos tercios a un
            tercio, para un total de 133,3%. Quitarlo de la
            lista escondia una jugada legitima. */}
        {opciones.map((o) => (
          <option key={o.code} value={o.code}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <Panel
      title="Cómo repartir los dos entrenamientos"
      meta="principal y secundario"
    >
      <div className="flex flex-wrap gap-3 border-b border-[var(--border)] p-4">
        {selector(
          principal,
          eligeAMano(setMain),
          "Entrenamiento principal",
          "juveniles.principal",
        )}
        {selector(
          secundaria,
          eligeAMano(setSecondary),
          "Entrenamiento secundario",
          "juveniles.secundario",
        )}
      </div>

      {plan.data?.repeatedTraining && (
        <div className="border-b border-[var(--border)] bg-[var(--surface-2)] px-4 py-2.5 text-sm text-[var(--text)]">
          <span className="font-medium">Entrenamiento repetido:</span> 100%
          principal + {porcentaje(plan.data.secondaryFactor * 100)} secundario
          {" = "}
          <strong>{porcentaje(plan.data.combinedFactor * 100)}</strong> del
          efecto de una sesión. El secundario normal de 66,7% recibe el castigo
          por repetición.
        </div>
      )}

      {plan.isError && (
        <p className="p-4 text-sm text-[var(--danger)]">
          No se pudo calcular el reparto.
        </p>
      )}

      {plan.data && (
        <div className="divide-y divide-[var(--border)]">
          <TablaDelReparto
            titulo="El once"
            filas={plan.data.assignments}
            mainLabel={plan.data.mainLabel}
            secondaryLabel={plan.data.secondaryLabel}
          />
          <TablaDelReparto
            titulo="El banquillo"
            pie="lo que recibirían si entran"
            filas={plan.data.outside.filter((a) => a.puesto)}
            mainLabel={plan.data.mainLabel}
            secondaryLabel={plan.data.secondaryLabel}
          />
          {plan.data.outside.filter((a) => !a.puesto).length > 0 && (
            <p className="p-4 text-xs text-[var(--muted)]">
              Sin sitio ni en el banquillo:{" "}
              {plan.data.outside
                .filter((a) => !a.puesto)
                .map((a) => `${a.player} ${edadCorta(a.ageDaysTotal)}`)
                .join(" · ")}
              .
            </p>
          )}
          <div className="p-4">
            {plan.data.scouting.total > 0 && (
              <p className="mt-3 text-xs text-[var(--muted)]">
                {plan.data.doubleBlind > 0 && (
                  <>
                    <b className="text-[var(--text)]">
                      {plan.data.doubleBlind === plan.data.doubleCount
                        ? `Los ${plan.data.doubleCount}`
                        : `${plan.data.doubleBlind} de los ${plan.data.doubleCount}`}
                    </b>{" "}
                    que reciben los dos entrenamientos van a entrenar una
                    habilidad que el ojeador no ha revelado. Es a propósito:
                    entrenarlos es lo que la revela.{" "}
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
        </div>
      )}
    </Panel>
  );
}

type Canterano = Academy["players"][number];

/** Cuánto le queda por ganar: la suma de `techo − nivel` allí donde se saben
 *  los dos números. No es lo bueno que es, sino lo que el entrenamiento
 *  todavía puede añadirle. */
function margenPorGanar(p: Canterano): number {
  return p.skills.reduce(
    (total, s) =>
      s.current != null && s.maximum != null && !s.maxReached
        ? total + Math.max(0, s.maximum - s.current)
        : total,
    0,
  );
}

/** Las columnas de la plantilla juvenil.
 *
 *  2026-09-01, pedido del usuario: esta vista era una rejilla de tarjetas y
 *  ahora es la misma tabla que «Jugadores» --con orden por columna, columnas
 *  que se muestran u ocultan, buscador y exportación--. Con eso desaparece el
 *  «Ordenar por» que había: la cabecera de cada columna ya ordena, y mantener
 *  los dos habría dejado un desplegable que no hacía nada, porque la tabla
 *  ordena por su cuenta.
 *
 *  Los filtros de arriba se quedan: no son orden, son preguntas --a quién le
 *  queda algo por revelar, a quién le llega el entrenamiento de hoy-- que la
 *  tabla no sabe contestar sola.
 */
/** Qué cuenta como «pronto» para poder ascender.
 *
 *  Cuatro semanas de Hattrick. Es el horizonte en el que una decisión ya se
 *  puede tomar --con qué habilidad terminarlo, si vale la pena seguir
 *  entrenándolo-- sin que sea todavía urgente. */
const ASCIENDE_PRONTO_DIAS = 28;

/** No le queda nada por ganar en lo que de verdad se sabe de él.
 *
 *  Exige al menos UNA habilidad con nivel Y techo conocidos. Sin esa
 *  condición el filtro mentía: `margenPorGanar` suma sólo los pares
 *  completos, así que a un canterano del que se conocen techos pero ningún
 *  nivel de hoy le sale margen cero -- y su margen no es cero, es desconocido.
 *  De los dieciocho de la academia, diez caían en ese cajón. */
function agotado(p: Canterano): boolean {
  const medibles = p.skills.filter(
    (s) => s.current != null && s.maximum != null,
  );
  return medibles.length > 0 && margenPorGanar(p) === 0;
}

/** Lo que se movió, por canterano y habilidad, dentro de la ventana. */
type Movimiento = Map<
  number,
  Record<string, { before: number | null; maxNewlyKnown: boolean }>
>;

/** El nivel de una habilidad, diciendo qué se movió desde la ventana elegida.
 *
 *  Dos cosas distintas se ven aquí, y hasta el 2026-09-04 no se veía ninguna:
 *
 *  * el NIVEL subió, y entonces se enseña de dónde viene: `4 ▲ 5 / 7`;
 *  * el TECHO se acaba de revelar, y va en negrilla. No mueve el nivel pero
 *    sí mueve el puntaje de «qué entrenar», así que sin marcarlo la cifra de
 *    arriba subía sin ninguna flecha que lo explicara.
 *
 *  Sin movimiento se pinta exactamente lo de antes: con 26 canteranos por 7
 *  habilidades, poner el estado anterior en las 182 celdas ensancharía la
 *  tabla para no decir nada.
 */
function NivelConMovimiento({
  current,
  maximum,
  numeros,
  movida,
}: {
  current: number | null;
  maximum: number | null;
  numeros: string;
  movida?: { before: number | null; maxNewlyKnown: boolean };
}) {
  const subio = movida?.before != null && current != null;
  const techoNuevo = movida?.maxNewlyKnown === true && maximum != null;
  if (!subio && !techoNuevo) return <>{numeros || "Desconocido"}</>;

  return (
    <span
      title={
        subio
          ? `subió de ${movida!.before} a ${current} en la ventana elegida`
          : "techo recién revelado por el ojeador"
      }
    >
      {subio && (
        <>
          <span className="text-[var(--muted)]">{movida!.before}</span>{" "}
          <span className="text-[var(--positive)]">▲</span>{" "}
        </>
      )}
      <span className={clsx(subio && "font-semibold")}>{current ?? "?"}</span>
      <span className="text-[var(--muted)]">{" / "}</span>
      <span className={clsx(techoNuevo && "font-semibold")}>
        {maximum ?? "?"}
      </span>
    </span>
  );
}

function columnasDeCanteranos(
  pais: {
    code: string;
    name: string;
  },
  movimiento: Movimiento,
): Column<Canterano>[] {
  const columnas: Column<Canterano>[] = [
    {
      key: "nombre",
      header: "Nombre",
      align: "left",
      value: (p) => p.name,
      // La bandera es la MISMA para todos y va aquí, pegada al nombre, en vez
      // de en una columna propia: Hattrick no publica nacionalidad de un
      // juvenil porque todos salen de la cantera de tu país, así que una
      // columna entera repetiría dieciocho veces el mismo dato y encima se
      // podría ordenar por él, que no significaría nada.
      render: (p) => (
        <span className="flex items-center gap-1.5 whitespace-nowrap">
          <CountryFlag code={pais.code} country={pais.name} />
          {p.name}
        </span>
      ),
    },
    {
      key: "edad",
      header: "Edad",
      align: "right",
      // `15;068`, como en el resto del módulo. `htAge` da «15.68», sin ceros,
      // y dos formatos de edad en la misma página se leen como dos datos
      // distintos.
      value: (p) => p.ageYears * 112 + p.ageDays,
      render: (p) => edadCorta(p.ageYears * 112 + p.ageDays),
    },
    {
      key: "clase",
      header: "Clasificación",
      align: "left",
      // Ordena por RANGO, no por alfabeto: «vendible» antes que «crack» sería
      // un orden inútil. Que el buscador no encuentre «crack» escribiéndolo
      // no es una pérdida: para eso están los botones de clasificación, que
      // además dicen cuántos hay de cada.
      value: (p) => rangoDeCategoria(p.category),
      render: (p) => (
        <span
          className={`whitespace-nowrap ${CATEGORY_TONE[p.category] ?? ""}`}
        >
          {p.category}
          {/* El interrogante avisa de que el veredicto es provisional. Con
              «sin ojear» sobra: la etiqueta ya dice justo eso. */}
          {p.verdictIsProvisional && p.revealedSkills > 0 && (
            <span title="pocos techos revelados: provisional"> ?</span>
          )}
        </span>
      ),
    },
    {
      key: "especialidad",
      header: "Especialidad",
      align: "left",
      // Como en «Jugadores»: `value` en texto plano --es lo que ordena, lo que
      // filtra el buscador y lo que va al CSV-- y el icono sólo en `render`.
      //
      // Aquí gana todavía más que en el primer equipo: la especialidad llega
      // desde el primer día, así que un canterano sin ojear --sin una sola
      // habilidad revelada-- ya tiene algo por lo que compararse.
      value: (p) => p.specialty,
      render: (p) => (
        <span className="whitespace-nowrap">
          <Specialty specialty={p.specialty} />
        </span>
      ),
    },
    {
      key: "puedeLlegar",
      header: "Puede llegar a (HTMS28)",
      align: "right",
      value: (p) => p.htms28Max,
      render: (p) => (
        <span title="en qué se puede convertir, en HTMS28: entre lo que ya tiene y lo que puede llegar a tener">
          {number(p.htms28Min)} – {number(p.htms28Max)}
        </span>
      ),
    },
    {
      key: "yaTiene",
      header: "Ya tiene (HTMS28)",
      align: "right",
      optional: true,
      value: (p) => p.htms28Min,
    },
    {
      key: "porSaber",
      header: "Por saber (HTMS28)",
      align: "right",
      optional: true,
      // La horquilla: cuánto depende todavía del ojeador.
      value: (p) => p.htms28Max - p.htms28Min,
    },
    {
      key: "techos",
      header: "Techos",
      align: "right",
      value: (p) => p.revealedSkills,
      render: (p) => `${p.revealedSkills}/${p.skills.length}`,
    },
    {
      key: "mejorTecho",
      header: "Mejor techo",
      align: "right",
      // Sin techo revelado no hay número que comparar: al final de la lista,
      // no al principio.
      value: (p) => p.bestSkillMax ?? -1,
      render: (p) => (p.bestSkillMax == null ? "Desconocido" : p.bestSkillMax),
    },
  ];

  // Una columna por habilidad. Son el motivo de esta pantalla, así que salen
  // todas de entrada; lo accesorio es lo que va escondido.
  for (const [clave, nombre] of Object.entries(SKILL_NAMES)) {
    columnas.push({
      key: `skill-${clave}`,
      header: nombre,
      align: "right",
      // Ordena por TECHO y cae al nivel actual cuando el techo aún no se
      // sabe: ordenar por lo que juega hoy pondría delante al que ya no sube.
      value: (p) => {
        const s = p.skills.find((x) => x.skill === clave);
        return s?.maximum ?? s?.current ?? -1;
      },
      // La barra mide el NIVEL sobre la escala juvenil, nunca lo lleno que
      // está respecto a su propio techo --un 4 que ya no sube es un 4-- y el
      // color dice si puede crecer. Misma lectura que las otras tres vistas
      // del módulo; aquí sólo va más apretada.
      render: (p) => {
        const s = p.skills.find((x) => x.skill === clave);
        if (!s) return "—";
        const { palabra, numeros, ancho, crece } = lecturaDeNivel(
          s.current,
          s.maximum,
          s.maxReached,
        );
        return (
          <span
            className="flex items-center justify-end gap-1.5 whitespace-nowrap"
            title={`${nombre}: ${palabra}`}
          >
            <span className="tabular-nums">
              {s.maxReached && (
                <span title="ya tocó techo: no sube más">🔒 </span>
              )}
              <NivelConMovimiento
                current={s.current}
                maximum={s.maximum}
                numeros={numeros}
                movida={movimiento.get(p.htYouthPlayerId)?.[clave]}
              />
            </span>
            <span className="h-1.5 w-10 shrink-0 overflow-hidden rounded bg-[var(--surface-2)]">
              <span
                className="block h-full"
                style={{
                  width: `${ancho}%`,
                  background:
                    ancho === 0
                      ? "transparent"
                      : crece
                        ? "var(--positive)"
                        : "var(--danger)",
                }}
              />
            </span>
          </span>
        );
      },
    });
  }

  columnas.push(
    {
      key: "sube",
      header: "Puede subir",
      align: "right",
      // Los que ya pueden subir van primero: 0 días es lo más urgente, así que
      // se ordena de menos a más y quien no tiene fecha queda al final.
      value: (p) => p.canBePromotedIn ?? 9999,
      render: (p) => enDias(p.canBePromotedIn).texto,
    },
    {
      key: "edadAlSubir",
      header: "Edad al subir",
      align: "right",
      // Rescatada de «Siguiente promoción», que esta tabla sustituye. Dice
      // cuál de los dos relojes le frena: 17;000 es que le frena la EDAD --lo
      // antes posible--, y más que eso, que le frena el plazo de 112 días en
      // la academia. Esos días de más son academia pagada de balde.
      value: (p) => edadAlSubir(p),
      render: (p) => edadCorta(edadAlSubir(p)),
    },
    {
      key: "limite",
      header: "Se va en",
      align: "right",
      optional: true,
      value: (p) => p.daysUntilDeadline,
      render: (p) => `${p.daysUntilDeadline} d`,
    },
    {
      key: "minutos",
      header: "Últ. partido",
      align: "right",
      optional: true,
      value: (p) => p.minutesLastMatch,
      render: (p) =>
        p.minutesLastMatch > 0 ? `${p.minutesLastMatch} min` : "No jugó",
    },
    {
      key: "margen",
      header: "Margen por ganar",
      align: "right",
      optional: true,
      value: (p) => margenPorGanar(p),
    },
    {
      key: "consejo",
      header: "Consejo",
      align: "left",
      optional: true,
      value: (p) => p.promoteAdvice,
      // La única columna que es una frase. Se le pone tope para que no
      // estire la tabla ella sola; el texto completo queda en el title.
      render: (p) => (
        <span className="block max-w-64 truncate" title={p.promoteAdvice}>
          {p.promoteAdvice}
        </span>
      ),
    },
  );
  return columnas;
}

const CLASIFICACIONES = [
  "crack",
  "promesa",
  "aceptable",
  "vendible",
  "fontanero",
  "sin ojear",
];

/** Un botón de filtro que se enciende y se apaga. */
function Chip({
  activo,
  onClick,
  children,
  title,
}: {
  activo: boolean;
  onClick: () => void;
  children: React.ReactNode;
  title?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className={`rounded-full border px-2.5 py-0.5 text-xs ${
        activo
          ? "border-[var(--accent)] text-[var(--accent)]"
          : "border-[var(--border)] text-[var(--muted)] hover:border-[var(--accent)]"
      }`}
    >
      {children}
    </button>
  );
}

function SkillDetail({ data }: { data: Academy }) {
  // La MISMA ventana que eligió el usuario en «Selección de entrenamiento».
  // Las dos secciones son pestañas excluyentes, así que ésta se remonta al
  // abrirla y lee el valor recién guardado (2026-09-04).
  const [ventana] = usePersistido("juveniles.ventana", "cambio");
  // Sin parámetros de puntaje: aquí no se enseñan puntajes, sólo qué se movió
  // en cada canterano, y eso no depende de las opiniones de la fórmula.
  const movida = useAcademyComparativa({
    ventana,
    soonMaxDays: DEFAULT_SOON_MAX_DAYS,
    weightBase: DEFAULT_WEIGHT_BASE,
    trainableMethod: "edit",
    trainable: {},
  });
  const movimiento: Movimiento = new Map(
    (movida.data?.players ?? []).map((j) => [
      j.htYouthPlayerId,
      Object.fromEntries(
        Object.entries(j.skills).map(([skill, v]) => [
          skill,
          { before: v.before, maxNewlyKnown: v.maxNewlyKnown },
        ]),
      ),
    ]),
  );

  //  El orden y la clasificación se recuerdan; los filtros de "sólo los
  //  que…" no, porque son preguntas de un momento, no una preferencia.
  const [clases, setClases] = usePersistido<string[]>(
    "juveniles.filtroClases",
    [],
  );
  const [soloRevelable, setSoloRevelable] = useState(false);
  const [soloAlTope, setSoloAlTope] = useState(false);
  const [habilidad, setHabilidad] = useState("");
  const [techoMinimo, setTechoMinimo] = useState(0);
  const [sinOjear, setSinOjear] = useState(false);
  const [yaAsciende, setYaAsciende] = useState(false);
  const [ascPronto, setAscPronto] = useState(false);
  const [conEspecialidad, setConEspecialidad] = useState(false);
  const [especialidad, setEspecialidad] = useState("");
  const [sinMargen, setSinMargen] = useState(false);
  const [jugoUltimo, setJugoUltimo] = useState(false);
  const [htmsMinimo, setHtmsMinimo] = useState(0);

  //  El único cruce con algo de fuera de esta tabla: a quién le queda algo
  //  por revelar. Lo dice el juego, no lo suponemos.
  const informes = useAcademyScouts();
  const conRevelacion = new Set(
    (informes.data?.players ?? [])
      .filter((x) => x.mayUnlock.length > 0)
      .map((x) => x.name),
  );

  //  Las especialidades que de verdad hay en la academia. El desplegable no
  //  ofrece las siete: una opción que no deja a nadie es una promesa falsa.
  const especialidades = [
    ...new Set(data.players.map((p) => p.specialty).filter(Boolean)),
  ].sort((a, b) => a.localeCompare(b, "es"));

  const alterna = (lista: string[], valor: string) =>
    lista.includes(valor)
      ? lista.filter((x) => x !== valor)
      : [...lista, valor];

  const filtrados = data.players.filter((p) => {
    if (clases.length > 0 && !clases.includes(p.category)) return false;
    if (soloRevelable && !conRevelacion.has(p.name)) return false;
    if (soloAlTope && !p.skills.some((x) => x.maxReached)) return false;
    // Con todo por descubrir: ni una habilidad revelada. Son los que hay que
    // mandar al ojeador antes de decidir nada sobre ellos.
    if (sinOjear && p.revealedSkills > 0) return false;
    if (yaAsciende && (p.canBePromotedIn ?? 9999) > 0) return false;
    if (ascPronto && (p.canBePromotedIn ?? 9999) > ASCIENDE_PRONTO_DIAS)
      return false;
    if (conEspecialidad && !p.specialty) return false;
    if (especialidad && p.specialty !== especialidad) return false;
    if (sinMargen && !agotado(p)) return false;
    if (jugoUltimo && p.minutesLastMatch <= 0) return false;
    if (htmsMinimo > 0 && p.htms28Max < htmsMinimo) return false;
    if (habilidad) {
      const x = p.skills.find((y) => y.skill === habilidad);
      if (!x || (x.current == null && x.maximum == null)) return false;
      if (techoMinimo > 0 && (x.maximum ?? 0) < techoMinimo) return false;
    }
    return true;
  });

  const hayFiltro =
    clases.length > 0 ||
    soloRevelable ||
    soloAlTope ||
    sinOjear ||
    yaAsciende ||
    ascPronto ||
    conEspecialidad ||
    Boolean(especialidad) ||
    sinMargen ||
    jugoUltimo ||
    htmsMinimo > 0 ||
    Boolean(habilidad);

  const limpiarFiltros = () => {
    setClases([]);
    setSoloRevelable(false);
    setSoloAlTope(false);
    setSinOjear(false);
    setYaAsciende(false);
    setAscPronto(false);
    setConEspecialidad(false);
    setEspecialidad("");
    setSinMargen(false);
    setJugoUltimo(false);
    setHtmsMinimo(0);
    setHabilidad("");
    setTechoMinimo(0);
  };

  //  Cuántos deja cada filtro, para poder decirlo en el propio botón. Se mide
  //  sobre la plantilla ENTERA y no sobre lo ya filtrado: un contador que
  //  cambia al pulsar otro botón no sirve para decidir cuál pulsar.
  const cuantos = (cumple: (p: Canterano) => boolean) =>
    data.players.filter(cumple).length;

  const control =
    "rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-xs text-[var(--text)]";

  return (
    <Panel
      title="Plantilla juvenil"
      meta={
        <span className="flex items-center gap-2">
          {hayFiltro
            ? `${filtrados.length} de ${data.players.length}`
            : `${data.players.length}`}
          {/* Tres columnas de esta tabla están en HTMS28, que no es un dato
              de Hattrick sino una cuenta nuestra. */}
          <EnlaceATransparencia seccion="htms" calculo="htms28" />
        </span>
      }
    >
      <div className="space-y-2 border-b border-[var(--border)] p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Chip
            activo={soloRevelable}
            onClick={() => setSoloRevelable((v) => !v)}
            title="al ojeador todavía le queda algo por revelarles; lo dice el juego, no lo suponemos"
          >
            Puede revelar algo
            {informes.data ? ` (${conRevelacion.size})` : ""}
          </Chip>
          <Chip
            activo={soloAlTope}
            onClick={() => setSoloAlTope((v) => !v)}
            title="tienen alguna habilidad que ya no sube"
          >
            Con algo al tope (
            {cuantos((p) => p.skills.some((x) => x.maxReached))})
          </Chip>
          <Chip
            activo={sinOjear}
            onClick={() => setSinOjear((v) => !v)}
            title="ni una habilidad revelada: no hay nada que decidir sobre ellos hasta ojearlos"
          >
            Sin ojear ({cuantos((p) => p.revealedSkills === 0)})
          </Chip>
          <Chip
            activo={sinMargen}
            onClick={() => setSinMargen((v) => !v)}
            title="no les queda nada por ganar en lo que ya se sabe de ellos; uno sin ojear no cuenta, su margen es desconocido, no cero"
          >
            Sin margen de mejora ({cuantos(agotado)})
          </Chip>

          <span className="mx-1 h-4 w-px bg-[var(--border)]" />

          <Chip
            activo={yaAsciende}
            onClick={() => setYaAsciende((v) => !v)}
            title="ya cumplen las dos reglas de Hattrick: puedes subirlos hoy"
          >
            Ya puede ascender (
            {cuantos((p) => (p.canBePromotedIn ?? 9999) <= 0)})
          </Chip>
          <Chip
            activo={ascPronto}
            onClick={() => setAscPronto((v) => !v)}
            title={`podrán subir dentro de ${ASCIENDE_PRONTO_DIAS} días o menos`}
          >
            Puede ascender pronto (
            {cuantos(
              (p) => (p.canBePromotedIn ?? 9999) <= ASCIENDE_PRONTO_DIAS,
            )}
            )
          </Chip>
          <Chip
            activo={jugoUltimo}
            onClick={() => setJugoUltimo((v) => !v)}
            title="tuvieron minutos en el último partido juvenil"
          >
            Jugó el último partido ({cuantos((p) => p.minutesLastMatch > 0)})
          </Chip>

          <span className="mx-1 h-4 w-px bg-[var(--border)]" />

          <Chip
            activo={conEspecialidad}
            onClick={() => setConEspecialidad((v) => !v)}
            title="tienen alguna especialidad; se sabe desde el primer día, aunque no estén ojeados"
          >
            Con especialidad ({cuantos((p) => Boolean(p.specialty))})
          </Chip>
          {/* Sólo si hay alguna: un desplegable vacío es un control que no
              hace nada, y en una academia sin especialidades no la hay. */}
          {especialidades.length > 0 ? (
            <select
              aria-label="Filtrar los canteranos por especialidad"
              value={especialidad}
              onChange={(e) => setEspecialidad(e.target.value)}
              className={control}
            >
              <option value="">Cualquier especialidad</option>
              {especialidades.map((e) => (
                <option key={e} value={e}>
                  {e}
                </option>
              ))}
            </select>
          ) : null}
          <label className="flex items-center gap-1 text-xs text-[var(--muted)]">
            HTMS28 mínimo
            <input
              type="number"
              min={0}
              step={100}
              value={htmsMinimo}
              onChange={(e) => setHtmsMinimo(Number(e.target.value) || 0)}
              title="sobre «puede llegar a»: el techo del canterano, no lo que ya tiene"
              className="w-20 rounded border border-[var(--border)] bg-[var(--surface)] px-1 py-0.5 text-right tabular-nums"
            />
          </label>

          <span className="mx-1 h-4 w-px bg-[var(--border)]" />

          <select
            aria-label="Filtrar los canteranos por habilidad"
            value={habilidad}
            onChange={(e) => setHabilidad(e.target.value)}
            className={control}
          >
            <option value="">Cualquier habilidad</option>
            {Object.entries(SKILL_NAMES).map(([clave, nombre]) => (
              <option key={clave} value={clave}>
                Con algo en {nombre}
              </option>
            ))}
          </select>
          {habilidad ? (
            <label className="flex items-center gap-1 text-xs text-[var(--muted)]">
              techo mínimo
              <input
                type="number"
                min={0}
                max={8}
                value={techoMinimo}
                onChange={(e) => setTechoMinimo(Number(e.target.value) || 0)}
                className="w-12 rounded border border-[var(--border)] bg-[var(--surface)] px-1 py-0.5 text-right tabular-nums"
              />
            </label>
          ) : null}
          {hayFiltro ? (
            <button
              type="button"
              onClick={limpiarFiltros}
              className="text-xs text-[var(--muted)] underline hover:text-[var(--text)]"
            >
              Quitar filtros
            </button>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-[var(--muted)]">Clasificación</span>
          {CLASIFICACIONES.map((c) => {
            const cuantos = data.players.filter((p) => p.category === c).length;
            if (cuantos === 0) return null;
            return (
              <Chip
                key={c}
                activo={clases.includes(c)}
                onClick={() => setClases(alterna(clases, c))}
              >
                {c} ({cuantos})
              </Chip>
            );
          })}
        </div>
      </div>

      <DataTable
        rows={filtrados}
        columns={columnasDeCanteranos(
          {
            code: data.countryCode,
            name: data.countryName,
          },
          movimiento,
        )}
        rowKey={(p) => p.htYouthPlayerId}
        // Lo mismo que ordenaba antes por omisión el desplegable que había
        // aquí: en qué se puede convertir, de mayor a menor.
        initialSort="puedeLlegar"
        filterPlaceholder="Buscar por nombre…"
        csvName="canteranos"
        emptyMessage="Ningún canterano cumple ese filtro."
      />
    </Panel>
  );
}

/** «en 88 días» / «hoy mismo», y la fecha entre paréntesis. */
function enDias(dias: number | null): { texto: string; urgente: boolean } {
  if (dias == null) return { texto: "—", urgente: false };
  if (dias <= 0) return { texto: "ya", urgente: false };
  return { texto: `${dias} d`, urgente: dias <= 21 };
}

/** Qué edad tendrá el día que por fin pueda subir.
 *
 *  Se suma a su edad de hoy lo que Hattrick dice que le falta, en vez de
 *  recalcular las dos reglas aquí: ese número ya lo manda el juego y no puede
 *  desincronizarse con él. Si sale 17;000 es que le frena la edad; más que eso,
 *  que le frena el plazo en la academia —y esos días de más son academia
 *  gastada sin necesidad—. */
function edadAlSubir(p: {
  ageYears: number;
  ageDays: number;
  canBePromotedIn: number | null;
}) {
  return p.ageYears * 112 + p.ageDays + Math.max(0, p.canBePromotedIn ?? 0);
}

function esOjeadorDeVerdad(nombre: string, id: number | null): boolean {
  return Boolean(id) && nombre.trim().length > 0;
}

/** Quién trajo a cada canterano y qué dijo de él.
 *
 * CHPP no publica una lista de ojeadores —`youthscouts`, `youthscoutlist` y
 * `scouts` devuelven 401—, así que «mis ojeadores» se reconstruye por lo
 * único que sí existe: la llamada con la que cada chico llegó. El texto va
 * literal, tal como lo escribió el ojeador, porque el dato destilado
 * (habilidad, nivel, techo) ya vive en las otras pestañas.
 */
/** La cuenta de cada ojeador: lo que cuesta contra lo que ha traído.
 *
 *  2026-08-26, pedido por el usuario. Lo difícil de esta pantalla es que al
 *  principio TODOS los ojeadores están en números rojos y no hay ninguna venta
 *  todavía: sus canteranos siguen en el club. Un panel que sólo enseñara el
 *  saldo diría «-15.000» tres veces y no serviría para nada.
 *
 *  Por eso las dos columnas del medio: **cuánto ha costado cada canterano que
 *  trajo** y **cuánto lleva sin traer ninguno**. Ésas comparan a un ojeador con
 *  otro desde el primer día, mucho antes de que alguien se venda.
 */
/** Techo de cada canterano, por nombre.
 *
 *  Viene de la cuenta y no del listado de informes, que no trae habilidades.
 *  Cruzar por nombre vale aquí: son los canteranos de UNA academia, no hay dos
 *  con el mismo. */
/** La región donde busca cada ojeador, por su nombre.
 *
 *  Un número de región no le dice nada a nadie: «1717» es Huila. El nombre
 *  viene en `youthteamdetails`, que es de donde sale la cuenta; el listado de
 *  informes solo trae el identificador. */
function regionesPorOjeador(
  ledger: ScoutsLedger | undefined,
): Map<string, string> {
  const mapa = new Map<string, string>();
  for (const o of ledger?.scouts ?? []) {
    if (o.region) mapa.set(o.name, o.region);
  }
  return mapa;
}

function techosPorNombre(
  ledger: ScoutsLedger | undefined,
): Map<string, number> {
  const mapa = new Map<string, number>();
  for (const o of ledger?.scouts ?? []) {
    for (const p of o.players) {
      if (p.ceiling != null) mapa.set(p.name, p.ceiling);
    }
  }
  return mapa;
}

function CuentaDeOjeadores({ ledger }: { ledger: ScoutsLedger }) {
  const th = "px-3 py-2 text-xs font-medium text-[var(--muted)]";
  const td = "px-3 py-2 text-sm";
  const { scouts, totals, currency } = ledger;
  if (scouts.length === 0) return null;

  const moneda = (n: number) => `${money(n)} ${currency}`;
  // La escala de las barras: el mayor movimiento manda, para que se comparen
  // entre sí y no contra un máximo inventado.
  const tope = Math.max(...scouts.map((o) => Math.max(o.cost, o.income)), 1);

  return (
    <Panel
      title="La cuenta de cada ojeador"
      meta={
        totals
          ? `${totals.scouts} ojeadores · ${moneda(ledger.weeklyCost)}/semana cada uno`
          : ""
      }
    >
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-[var(--surface-2)]">
            <tr>
              <th scope="col" className={`${th} text-left`}>
                Ojeador
              </th>
              <th scope="col" className={`${th} text-left`}>
                Busca en
              </th>
              <th
                scope="col"
                className={`${th} text-right`}
                title="semanas completas desde que lo contrataste"
              >
                Semanas
              </th>
              <th scope="col" className={`${th} text-right`}>
                Ha costado
              </th>
              <th scope="col" className={`${th} text-right`}>
                Trajo
              </th>
              <th
                scope="col"
                className={`${th} text-right`}
                title="lo que te ha costado cada canterano que te trajo: es lo que compara a un ojeador con otro antes de que haya ninguna venta"
              >
                Cada uno
              </th>
              <th
                scope="col"
                className={`${th} text-right`}
                title="días desde su último fichaje; si nunca trajo nada, desde que lo contrataste"
              >
                Sin traer
              </th>
              <th scope="col" className={`${th} text-right`}>
                Ha dado
              </th>
              <th scope="col" className={`${th} text-right`}>
                Saldo
              </th>
            </tr>
          </thead>
          <tbody>
            {scouts.map((o) => (
              <tr key={o.htScoutId} className="border-t border-[var(--border)]">
                <td className={`${td} font-medium`}>
                  {o.name}
                  {!o.stillHired && (
                    <span className="ml-2 text-xs text-[var(--muted)]">
                      despedido
                    </span>
                  )}
                </td>
                <td className={`${td} text-[var(--muted)]`}>
                  {o.region ?? "—"}
                </td>
                <td className={`${td} text-right tabular-nums`}>{o.weeks}</td>
                <td
                  className={`${td} text-right tabular-nums text-[var(--danger)]`}
                >
                  {moneda(o.cost)}
                </td>
                <td className={`${td} text-right tabular-nums`}>
                  {o.found}
                  {o.sold > 0 && (
                    <span className="text-xs text-[var(--muted)]">
                      {" "}
                      · {o.sold} vendidos
                    </span>
                  )}
                </td>
                <td className={`${td} text-right tabular-nums`}>
                  {o.costPerFind == null ? "—" : moneda(o.costPerFind)}
                </td>
                {/* Un ojeador que lleva semanas sin traer nada está cobrando
                    por no hacer nada, y eso hay que poder verlo de un vistazo. */}
                <td
                  className={`${td} text-right tabular-nums`}
                  style={{
                    color:
                      (o.daysSinceLastFind ?? 0) > 21
                        ? "var(--warning)"
                        : "var(--muted)",
                  }}
                >
                  {o.daysSinceLastFind == null
                    ? "—"
                    : `${o.daysSinceLastFind} d`}
                </td>
                <td className={`${td} text-right tabular-nums`}>
                  {o.income > 0 ? (
                    <span className="text-[var(--positive)]">
                      {moneda(o.income)}
                    </span>
                  ) : (
                    <span className="text-[var(--muted)]">todavía nada</span>
                  )}
                </td>
                <td className={`${td} text-right`}>
                  <span
                    className="tabular-nums font-medium"
                    style={{
                      color:
                        o.balance >= 0 ? "var(--positive)" : "var(--danger)",
                    }}
                  >
                    {moneda(o.balance)}
                  </span>
                  <span className="mt-1 block h-1 w-full rounded bg-[var(--surface-2)]">
                    <span
                      className="block h-full rounded"
                      style={{
                        width: `${(Math.max(o.cost, o.income) / tope) * 100}%`,
                        background:
                          o.balance >= 0 ? "var(--positive)" : "var(--danger)",
                      }}
                    />
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
          {totals && (
            <tfoot>
              <tr className="border-t-2 border-[var(--border)] font-medium">
                <td className={td} colSpan={3}>
                  Total
                </td>
                <td
                  className={`${td} text-right tabular-nums text-[var(--danger)]`}
                >
                  {moneda(totals.cost)}
                </td>
                <td className={`${td} text-right tabular-nums`}>
                  {totals.found}
                </td>
                <td className={td} colSpan={2} />
                <td className={`${td} text-right tabular-nums`}>
                  {totals.income > 0 ? moneda(totals.income) : "—"}
                </td>
                <td
                  className={`${td} text-right tabular-nums`}
                  style={{
                    color:
                      totals.balance >= 0 ? "var(--positive)" : "var(--danger)",
                  }}
                >
                  {moneda(totals.balance)}
                </td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
      {ledger.unlinked.length > 0 && (
        <p className="px-4 py-2 text-xs text-[var(--warning)]">
          Sin enlazar con su ficha de mayores, así que su dinero no está en esta
          cuenta: {ledger.unlinked.join(", ")}.
        </p>
      )}
    </Panel>
  );
}

function Ojeadores() {
  const informes = useAcademyScouts();
  // La cuenta va aparte: si falla, los informes se siguen viendo.
  const cuenta = useAcademyScoutsLedger();
  const techos = techosPorNombre(cuenta.data);
  const regiones = regionesPorOjeador(cuenta.data);
  if (informes.isLoading) return <Loading />;
  if (informes.isError) return <ErrorState error={informes.error} />;
  const data = informes.data;
  if (!data || data.players.length === 0) {
    return (
      <Panel title="Ojeadores">
        <Empty>
          Sincroniza para traer el informe del ojeador de cada canterano.
        </Empty>
      </Panel>
    );
  }

  const ojeadores = data.scouts.filter((o) =>
    esOjeadorDeVerdad(o.scoutName, o.scoutId),
  );
  const traidos = data.players.filter((p) =>
    esOjeadorDeVerdad(p.scoutName, p.scoutId),
  );
  const deCasa = data.players.filter(
    (p) => !esOjeadorDeVerdad(p.scoutName, p.scoutId),
  );
  const porRevelar = data.players.filter((p) => p.mayUnlock.length > 0);

  //  Agrupado por quien lo trajo, y los de la academia al final: son el grupo
  //  grande y no tienen nada que contar.
  const th = "px-3 py-2 text-xs font-medium text-[var(--muted)]";
  const td = "overflow-hidden whitespace-nowrap px-3 py-1.5";
  const grupos = new Map<string, typeof data.players>();
  for (const p of data.players) {
    const clave = esOjeadorDeVerdad(p.scoutName, p.scoutId)
      ? p.scoutName
      : "Vinieron con la academia";
    grupos.set(clave, [...(grupos.get(clave) ?? []), p]);
  }
  const porOjeador = [...grupos.entries()].sort(
    (a, b) =>
      Number(a[0] === "Vinieron con la academia") -
        Number(b[0] === "Vinieron con la academia") ||
      b[1].length - a[1].length ||
      a[0].localeCompare(b[0]),
  );

  return (
    <div className="space-y-4">
      {/* La cuenta primero: es la pregunta que se hace uno al abrir esta
          pestaña --¿me sale a cuenta cada ojeador?-- y el resto es el detalle
          de quién trajo a quién. */}
      {cuenta.data && <CuentaDeOjeadores ledger={cuenta.data} />}
      <Panel
        title="Ojeadores"
        meta={`${ojeadores.length} · ${traidos.length} de ${data.players.length} canteranos`}
      >
        <div className="flex flex-wrap gap-3 p-4">
          {ojeadores.map((o) => (
            <div
              key={o.scoutId}
              className="rounded-lg border border-[var(--border)] px-3 py-2"
            >
              <p className="text-sm font-medium">{o.scoutName}</p>
              <p className="text-xs text-[var(--muted)]">
                {o.players} {o.players === 1 ? "canterano" : "canteranos"}
                {regiones.get(o.scoutName)
                  ? ` · ${regiones.get(o.scoutName)}`
                  : o.regionIds.length > 0
                    ? ` · región ${o.regionIds.join(", ")}`
                    : ""}
              </p>
            </div>
          ))}
          {deCasa.length > 0 && (
            <div className="rounded-lg border border-dashed border-[var(--border)] px-3 py-2">
              <p className="text-sm">Vinieron con la academia</p>
              <p className="text-xs text-[var(--muted)]">
                {deCasa.length} canteranos · nadie salió a buscarlos
              </p>
            </div>
          )}
        </div>
      </Panel>

      {porRevelar.length > 0 && (
        <Panel
          title="Todavía se les puede revelar algo"
          meta={`${porRevelar.length} · lo dice el juego, no lo suponemos`}
        >
          <ul className="space-y-1 p-4 text-sm">
            {porRevelar.map((p) => (
              <li key={p.htYouthPlayerId} className="flex flex-wrap gap-x-2">
                <span>{p.name}</span>
                <span className="text-[var(--muted)]">
                  {p.mayUnlock.join(" · ")}
                </span>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      <Panel
        title="Quién trajo a quién"
        meta={`${data.players.length} canteranos`}
      >
        <div className="overflow-x-auto p-4">
          <table className="w-full min-w-[42rem] table-fixed text-sm">
            <colgroup>
              <col className="w-[26%]" />
              <col className="w-[10%]" />
              <col className="w-[26%]" />
              <col className="w-[18%]" />
              <col className="w-[20%]" />
            </colgroup>
            <thead className="bg-[var(--surface-2)]">
              <tr>
                <th scope="col" className={`${th} text-left`}>
                  Ojeador
                </th>
                <th scope="col" className={`${th} text-right`}>
                  Región
                </th>
                <th scope="col" className={`${th} text-left`}>
                  Canterano
                </th>
                <th scope="col" className={`${th} text-right`}>
                  Llegó
                </th>
                {/* «Queda por revelar» se quito el 2026-08-26: el usuario lo
                    llamo irrelevante y tenia razon --dice cuanto ignoramos,
                    no cuanto vale--. Lo que juzga a un ojeador es el TECHO de
                    lo que trae. */}
                <th
                  scope="col"
                  className={`${th} text-right`}
                  title="el mejor techo que el ojeador ya ha revelado de él; vacío = todavía no ha revelado nada"
                >
                  Techo
                </th>
              </tr>
            </thead>
            <tbody>
              {porOjeador.map(([quien, suyos]) =>
                suyos.map((p, i) => (
                  <tr
                    key={p.htYouthPlayerId}
                    className="h-9 border-t border-[var(--border)]"
                  >
                    {/* El nombre del ojeador una vez por bloque: repetirlo en
                        cada fila haria leer catorce veces "vinieron con la
                        academia" para saber que son un grupo. */}
                    <td
                      className={`${td} truncate text-left`}
                      title={quien}
                      style={{ color: i === 0 ? undefined : "transparent" }}
                    >
                      {i === 0 ? quien : "·"}
                    </td>
                    {/* La región es donde el ojeador estaba mirando. A los
                        que vinieron con la academia no los buscó nadie, así
                        que enseñar una región ahí sería inventar un origen. */}
                    <td className={`${td} text-right text-[var(--muted)]`}>
                      {i === 0 && esOjeadorDeVerdad(p.scoutName, p.scoutId)
                        ? (regiones.get(p.scoutName) ??
                          p.scoutingRegionId ??
                          "")
                        : ""}
                    </td>
                    <td className={`${td} truncate text-left`} title={p.name}>
                      {p.name}
                    </td>
                    <td
                      className={`${td} text-right text-xs text-[var(--muted)]`}
                    >
                      {p.arrivedAt ? date(p.arrivedAt) : "—"}
                    </td>
                    {/* El techo revelado. Sin nada revelado se dice «sin
                        ojear», no «0»: no saberlo no es que sea malo. */}
                    <td className={`${td} text-right text-xs tabular-nums`}>
                      {techos.get(p.name) == null ? (
                        <span className="text-[var(--muted)]">sin ojear</span>
                      ) : (
                        <span
                          style={{
                            color:
                              (techos.get(p.name) ?? 0) >= 7
                                ? "var(--positive)"
                                : undefined,
                          }}
                        >
                          {techos.get(p.name)}
                        </span>
                      )}
                    </td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

function GraduatesTable({ data }: { data: Academy }) {
  type Row = Academy["graduates"][number];
  // TODOS, no solo los de la academia actual: aqui la pregunta es "quien salio
  // de aqui", y de que academia salio no la acota. El ROI si los filtra.
  // : si el backend no manda el campo --servidor viejo, despliegue a
  // medias-- se ve una tabla vacia, no la pagina en blanco. Paso.
  const filas = data.allGraduates ?? [];
  const columns: Column<Row>[] = [
    { key: "name", header: "Nombre", align: "left", value: (r) => r.name },
    {
      key: "arrived",
      header: "En su club desde",
      // Se llamaba «Promocionado» y no lo era: guarda cuándo llegó al club
      // donde está HOY. Por eso salía después de la venta en las 43 filas.
      value: (r) =>
        r.arrivedAtCurrentTeam
          ? new Date(r.arrivedAtCurrentTeam).getTime()
          : -Infinity,
      render: (r) => date(r.arrivedAtCurrentTeam),
    },
    {
      key: "sold",
      header: "Vendido",
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
          <span className="text-[var(--muted)]">—</span>
        ) : (
          <span className="tabular-nums">
            {money(r.soldFor, data.currency)}
          </span>
        ),
    },
    {
      key: "team",
      header: "Equipo actual",
      value: (r) => r.currentTeam ?? "-",
    },
    {
      key: "tsi",
      header: "TSI",
      align: "right",
      value: (r) => r.currentTsi ?? 0,
      optional: true,
    },
  ];
  return (
    <>
      <DataTable
        emptyMessage="Ningún canterano encaja con lo que has pedido."
        rows={filas}
        columns={columns}
        rowKey={(r) => r.name}
        csvName="canteranos"
        filterPlaceholder="Filtrar…"
      />
    </>
  );
}
