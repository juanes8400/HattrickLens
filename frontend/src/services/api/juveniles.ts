/** Juveniles.
 *
 *  Sale de partir `services/api.ts`, que tenia 4147 lineas y se leia entero
 *  en cada cambio del frontend. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../services/api"` sigue valiendo igual.
 */
import { request } from "./nucleo";

/** Una plaza del once juvenil y qué entrenamiento le llega ahí. */
export interface NivelLeido {
  label: string;
  current: number | null;
  maximum: number | null;
  maxReached: boolean;
}

export interface TrainingSlot {
  player: string;
  puesto: string;
  /** ambos · solo_principal · solo_secundaria · sin_entrenamiento */
  region: string;
  /** Ración efectiva; puede ser 100, 66,7, 50, 33,3 u otra combinación. */
  racionPrincipal: number;
  racionSecundaria: number;
  /** En qué peldaño de la cola venía, de 1 a 9. */
  peldano: number;
  /** Por qué habilidad se le eligió: la principal o la secundaria. */
  elegidoPor: string;
  /** El nombre de esa habilidad, que es de la que habla la columna «Nivel». */
  skillLabel: string;
  /** El nivel de las DOS habilidades que se entrenan, no sólo la que le dio
   *  la plaza. */
  mainLevel: NivelLeido;
  secondaryLevel: NivelLeido;
  /** Lo que va en cada celda de entrenamiento, linea a linea. Un entrenamiento
   *  corriente trae una sola; «Individual» trae su ruleta entera. */
  mainLines?: LineaDeEntrenamiento[];
  secondaryLines?: LineaDeEntrenamiento[];
  /** Las habilidades a las que el ojeador aún no les ha puesto techo: es lo
   *  único que queda por saber de él. */
  openCeilings: string[];
  /** Su edad hoy, en días, y lo que el ojeador dijo de esa habilidad. */
  ageDaysTotal: number;
  /** En qué se puede convertir, en HTMS28. La tabla enseña esto en vez de la
   *  edad, que va dentro del número. */
  htms28Min: number;
  htms28Max: number;
  current: number | null;
  maximum: number | null;
  maxReached: boolean;
}

export interface AcademyTrainingPlan {
  main: string;
  mainLabel: string;
  secondary: string;
  secondaryLabel: string;
  /** Multiplicador efectivo del hueco secundario: ⅔ normal o ⅓ repetido. */
  secondaryFactor: number;
  /** Principal + secundario sobre una misma base: 5/3 normal o 4/3 repetido. */
  combinedFactor: number;
  repeatedTraining: boolean;
  /** Cuántos reciben los dos entrenamientos a la vez. */
  doubleCount: number;
  /** De los que reciben doble, a cuántos no se les sabe nada de esa habilidad. */
  doubleBlind: number;
  /** Cuánto ha revelado el ojeador en toda la academia. */
  scouting: { known: number; total: number; blankPlayers: string[] };
  assignments: TrainingSlot[];
  /** El banquillo: los que no entraron, con su columna sugerida. */
  outside: (TrainingSlot & { benchColumn: string })[];
}

/** Una linea de una celda de entrenamiento juvenil.
 *
 * `probability` en null significa «esto pasa siempre», no «no se sabe»: un
 * entrenamiento corriente y «Anotación y balón parado» no sortean nada.
 * Solo «Individual» rellena este campo. */
export interface LineaDeEntrenamiento {
  skill: string;
  label: string;
  /** Lo que rinde esa habilidad en esa plaza, con el castigo del hueco
   *  secundario ya aplicado. */
  rate: number;
  /** Lo que rendiria en el hueco PRINCIPAL, sin el castigo. El mismo sorteo
   *  vale 42,5 / 28,3 / 14,2 según donde esté, así que `rate` a secas es
   *  ambiguo y la pantalla necesita poder decir de donde sale. */
  base?: number;
  /** 1 en el principal, ⅔ en el secundario, ⅓ si se repite entrenamiento. */
  penalty?: number;
  probability: number | null;
  level: {
    label: string;
    current: number | null;
    maximum: number | null;
    maxReached: boolean;
  };
}

/** Por que el metodo 8 eligio lo que eligio, CON SUS NUMEROS: la frase sola
 *  habria que creersela. */
export interface VeredictoDeMetodo {
  /** doblar · segunda · descubrir */
  path: string;
  why: string;
  /** Por encima de esto un puntaje es ignorancia y preferencia, no evidencia. */
  threshold: number;
  main: {
    score: number;
    /** Que parte del puntaje NO es respaldo --gente sin revelar mas el bonus
     *  puesto a mano--, de 0 a 1. */
    unbacked: number;
    /** Cuantos canteranos tiene en el peldano 4 o mejor. */
    backed: number;
  };
  /** La prueba que separa «un grupo» de «un chico con buen puntaje»: se le
   *  quita su mejor canterano y se mira si aguanta en cabeza. */
  robustness: {
    removedRung: string | null;
    scoreWithout: number;
    held: boolean;
    /** Quien lo adelanta al quitarselo. `null` si aguanta. */
    overtakenBy: string | null;
  };
  second: {
    label: string;
    unbacked: number | null;
    backed: number | null;
  } | null;
}

/** "Qué entrenar" recalculado con los parámetros que elija el usuario. El
 *  método es fijo; estos tres números son opiniones. */
/** El movimiento de la academia dentro de la ventana elegida. */
export interface AcademyComparativa {
  window: string;
  /** Desde cuándo se compara. `null` si no hay con qué. */
  since: string | null;
  /** `false` cuando la ventana empieza antes del primer dato guardado: no se
   *  compara nada y la pantalla lo dice, en vez de inventar una comparación. */
  hasBaseline: boolean;
  scores: {
    skill: string;
    score: number;
    delta: number | null;
    counts: Record<string, number>;
    /** Cuántos entraron o salieron de cada cubo. `null` si no hay con qué
     *  comparar. */
    countDeltas: Record<string, number> | null;
  }[];
  players: {
    htYouthPlayerId: number;
    name: string;
    isNew: boolean;
    skills: Record<
      string,
      {
        current: number | null;
        max: number | null;
        /** El nivel de antes, sólo si subió. */
        before: number | null;
        /** El techo se reveló dentro de la ventana: no mueve el nivel pero sí
         *  el puntaje. */
        maxNewlyKnown: boolean;
      }
    >;
  }[];
  summary: {
    skillsUp: number;
    ceilingsRevealed: number;
    arrivals: number;
    departures: number;
    /** Lo que tiene que sumar la fila de movimientos de cualquier habilidad:
     *  altas menos bajas. La pantalla lo dice en una nota. */
    rowDelta: number;
  };
}

export interface AcademySkillScores {
  soonMaxDays: number;
  weightBase: number;
  trainableMethod: string;
  /** El peso que la base da a cada cubo, se pinta sobre su columna. */
  weights: Record<string, number>;
  /** El que sugiere la escalera (peldaño -2 de la base). */
  suggestedTrainableWeight: number;
  /** La pareja sugerida: la que mas puntua y, de la segunda, la FORMA que
   *  mas solapa con la primera. `null` si no hay dos habilidades. */
  suggestion: {
    main: string;
    mainLabel: string;
    secondary: string;
    secondaryLabel: string;
    secondarySkill: string;
    /** Cuantos recibirian las dos cosas con esa pareja. */
    bothCount: number;
    /** Por que el metodo 8 eligio esto. Puede faltar en un backend viejo. */
    method?: VeredictoDeMetodo;
  } | null;
  /** Las plazas que entrena cada habilidad, para sembrar el modo manual. */
  /** Todos los entrenamientos, variantes incluidas. */
  trainings: { code: string; label: string; skill: string }[];
  slotCounts: Record<string, number>;
  /** El que de verdad se usó: el sugerido, o el que fijó el usuario. */
  trainableWeight: number;
  skillScores: Academy["skillScores"];
}

/** La cuenta de cada ojeador. */
export interface ScoutsLedger {
  weeklyCost: number;
  currency: string;
  scouts: {
    htScoutId: number;
    name: string;
    region: string | null;
    hiredAt: string | null;
    goneAt: string | null;
    stillHired: boolean;
    weeks: number;
    cost: number;
    income: number;
    balance: number;
    found: number;
    sold: number;
    /** Lo que ha costado cada canterano traído. `null` si no trajo ninguno. */
    costPerFind: number | null;
    daysSinceLastFind: number | null;
    players: {
      name: string;
      net: number;
      resale: number;
      stillHere: boolean;
      arrivedAt: string | null;
      /** El mejor techo revelado. `null` = aún no se sabe, que no es malo. */
      ceiling: number | null;
    }[];
  }[];
  totals: {
    cost: number;
    income: number;
    balance: number;
    scouts: number;
    found: number;
  } | null;
  /** Canteranos cuyo dinero NO está en la cuenta porque no se pudo enlazar. */
  unlinked: string[];
}

export interface Academy {
  teamName: string;
  currency: string;
  /** El país del club, para la bandera de la tabla. Viaja una vez y no por
   *  canterano a propósito: Hattrick no publica la nacionalidad de un juvenil
   *  --su fichero no la trae-- porque salen todos de la cantera de tu propio
   *  país. Vacío mientras no esté sincronizado el contexto del mundo. */
  countryCode: string;
  countryName: string;
  squadSize: number;
  players: {
    htYouthPlayerId: number;
    name: string;
    ageYears: number;
    ageDays: number;
    potentialScore: number;
    /** En qué se puede convertir, en HTMS28, con lo que el ojeador ha dicho.
     *  Sustituye a `potentialScore` en pantalla. */
    htms28Min: number;
    htms28Max: number;
    category: string;
    bestSkill: string;
    bestSkillMax: number | null;
    daysUntilDeadline: number;
    weeksUntilDeadline: number;
    /** Días que faltan para PODER subirlo al primer equipo. Distinto del
     *  plazo para no perderlo por edad: entre las dos fechas está la ventana
     *  en la que hay que decidir. */
    canBePromotedIn: number | null;
    revealedSkills: number;
    verdictIsProvisional: boolean;
    promoteAdvice: string;
    trainingExposure: number;
    /** Minutos del último partido oficial. */
    minutesLastMatch: number;
    /** La especialidad, ya traducida --el mismo texto que manda la plantilla
     *  principal, para pintarla con el mismo componente--. Es lo único de un
     *  canterano sin ojear que ya dice algo: llega desde el primer día, cuando
     *  ninguna habilidad se ha revelado todavía. */
    specialty: string;
    skills: {
      skill: string;
      /** Nivel al que juega hoy. `null` = el ojeador aún no lo ha dicho, que
       *  NO es lo mismo que jugar a nivel 0. */
      current: number | null;
      /** Techo. Se revela por separado del nivel actual. */
      maximum: number | null;
      isCurrentKnown: boolean;
      isMaxKnown: boolean;
      headroom: number;
      /** Ya tocó su techo: no sube más. Hattrick lo pinta con un candado. */
      maxReached: boolean;
    }[];
  }[];
  /** Qué habilidad conviene entrenar, de mayor a menor. Portado de la hoja
   *  del usuario (`AuxiJuveniles`): en juveniles se entrena una habilidad y la
   *  reciben todos, así que la pregunta no es a quién entrenar sino qué. */
  skillScores: {
    skill: string;
    label: string;
    score: number;
    counts: Record<string, number>;
    trainableCount: number;
    /** Todos los canteranos ordenados por lo que sacan en esta habilidad.
     *  `note` es `null` cuando el ojeador no ha revelado nada, y ése es
     *  justo el caso en que darle minutos sirve para revelarlo. */
    players: {
      name: string;
      note: number | null;
      bucket: string;
      leavesSoon: boolean;
      maxReached: boolean;
      /** El nivel que tiene, se entrene o no: `note` es null si está al tope. */
      level: number | null;
      /** Lo que dijo el ojeador, cada cosa por separado. */
      current: number | null;
      maximum: number | null;
      /** Su puesto en la cola de esa habilidad, de 1 a 9. */
      priority: number;
    }[];
    /** Los que ya tocaron techo: fuera de la cola, pero se enseñan al final. */
    atMax: {
      name: string;
      level: number | null;
      current: number | null;
      maximum: number | null;
      maxReached: boolean;
      leavesSoon: boolean;
    }[];
  }[];
  /** Los de la academia ACTUAL: es la lista con la que se calcula el ROI. */
  graduates: {
    name: string;
    /** Cuándo llegó a su club ACTUAL. No es la fecha de ascenso. */
    arrivedAtCurrentTeam: string | null;
    soldAt: string | null;
    soldFor: number | null;
    currentTeam: string | null;
    currentTsi: number | null;
  }[];
  /** TODOS los que han pasado por el club, de cualquier academia. */
  allGraduates: Academy["graduates"];
  invested: number;
  earned: number;
  net: number;
  seasons: number;
  weeks: number;
  weeklyCost: number;
  breakEvenSales: number;
  roiVerdict: string;
  urgent: string[];
  notes: string[];
}

// ── Saldo neto por jugador ───────────────────────────────────────────────────

/** Quién trajo a cada canterano y qué queda por revelarle.
 *
 * CHPP no publica una lista de ojeadores; lo único que existe es el
 * `ScoutCall` de cada canterano, así que «mis ojeadores» se reconstruye
 * agrupando por quién trajo a quién. */
export interface AcademyScouts {
  scouts: {
    scoutId: number | null;
    scoutName: string;
    regionIds: number[];
    players: number;
  }[];
  players: {
    name: string;
    htYouthPlayerId: number;
    arrivedAt: string | null;
    scoutId: number | null;
    scoutName: string;
    scoutingRegionId: number | null;
    /** El texto literal del informe, tal como lo escribió el ojeador. */
    comments: string[];
    /** Habilidades a las que aún les queda algo por revelar, según el juego. */
    mayUnlock: string[];
    fetchedAt: string | null;
  }[];
}

export const apiJuveniles = {
  academy: (teamId: number) => request<Academy>(`/teams/${teamId}/academy`),
  academyScouts: (teamId: number) =>
    request<AcademyScouts>(`/teams/${teamId}/academy/scouts`),
  /** La cuenta de cada ojeador: lo que cuesta y lo que ha traído. */
  academyScoutsLedger: (teamId: number) =>
    request<ScoutsLedger>(`/teams/${teamId}/academy/scouts-ledger`),
  academySkillScores: (
    teamId: number,
    params: {
      soonMaxDays: number;
      weightBase: number;
      trainableMethod: string;
      trainable: Record<string, number>;
      /** `null` = que lo sugiera la escalera. */
      trainableWeight?: number | null;
    },
  ) => {
    const q = new URLSearchParams({
      soon_max_days: String(params.soonMaxDays),
      weight_base: String(params.weightBase),
      trainable_method: params.trainableMethod,
      ...(params.trainableWeight == null
        ? {}
        : { trainable_weight: String(params.trainableWeight) }),
      trainable: Object.entries(params.trainable)
        .filter(([, n]) => n > 0)
        .map(([skill, n]) => `${skill}:${n}`)
        .join(","),
    });
    return request<AcademySkillScores>(
      `/teams/${teamId}/academy/skill-scores?${q}`,
    );
  },
  /** Qué se movió en la academia y cuánto movió cada puntaje.
   *
   *  Lleva los MISMOS parámetros que `academySkillScores` a propósito: el
   *  puntaje de antes hay que calcularlo con la misma opinión que el de
   *  ahora, o la resta no significa nada. */
  academyComparativa: (
    teamId: number,
    params: {
      ventana: string;
      soonMaxDays: number;
      weightBase: number;
      trainableMethod: string;
      trainable: Record<string, number>;
      trainableWeight?: number | null;
    },
  ) => {
    const q = new URLSearchParams({
      ventana: params.ventana,
      soon_max_days: String(params.soonMaxDays),
      weight_base: String(params.weightBase),
      trainable_method: params.trainableMethod,
      ...(params.trainableWeight == null
        ? {}
        : { trainable_weight: String(params.trainableWeight) }),
      trainable: Object.entries(params.trainable)
        .filter(([, n]) => n > 0)
        .map(([skill, n]) => `${skill}:${n}`)
        .join(","),
    });
    return request<AcademyComparativa>(
      `/teams/${teamId}/academy/comparativa?${q}`,
    );
  },
  academyTrainingPlan: (
    teamId: number,
    params: {
      main: string;
      secondary: string;
      soonMaxDays: number;
      weightBase: number;
    },
  ) => {
    const q = new URLSearchParams({
      main: params.main,
      secondary: params.secondary,
      soon_max_days: String(params.soonMaxDays),
      weight_base: String(params.weightBase),
    }).toString();
    return request<AcademyTrainingPlan>(
      `/teams/${teamId}/academy/training-plan?${q}`,
    );
  },
};
