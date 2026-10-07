/** El resumen del equipo.
 *
 *  Sale de partir `services/api.ts`, que tenia 4147 lineas y se leia entero
 *  en cada cambio del frontend. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../services/api"` sigue valiendo igual.
 */
import { request } from "./nucleo";

/**
 * Sección Equipo: la plantilla promediada por grupos. Cada grupo dice con
 * qué forma se PUEDE dibujar, `radar` sólo cuando todas sus métricas
 * comparten escala; si no, barras con el techo propio de cada una.
 */
export interface TeamOverviewMetric {
  key: string;
  label: string;
  value: number;
  scaleMax: number;
  display: "level" | "money" | "number" | "count" | "ratio";
  valueLabel: string | null;
}

export interface TeamOverviewSeries {
  key: string;
  label: string;
  /** Un valor por semana, alineado con `weeks`. `null` = semana sin lectura;
   *  nunca se rellena con ceros ni se interpola. */
  values: (number | null)[];
  /** "decimal" es un número con decimales que no es dinero ni un nivel de 0 a
   *  20: la edad media de la plantilla, por ejemplo. */
  display: "level" | "money" | "number" | "count" | "ratio" | "decimal";
}

/** Una gráfica dentro de un grupo. Un grupo lleva varias cuando sus series no
 *  comparten escala, juntarlas en un eje daría a entender que se comparan. */
export interface TeamOverviewChart {
  key: string;
  title: string;
  scaleMin: number | null;
  scaleMax: number | null;
  /** Sombrea el hueco entre las dos series. El backend solo lo marca cuando
   *  ambas miden lo MISMO sobre poblaciones distintas (plantilla contra el
   *  once de más TSI), de modo que el área entre ellas es una cantidad real. */
  band: boolean;
  series: TeamOverviewSeries[];
}

/**
 * Una línea de la cancha, con dos lecturas que NO son la misma población:
 * `bestRating`/`topPlayer`/`bestVariantLabel` salen de evaluar a TODA la
 * plantilla en las variantes de esa línea, mientras que `count` y
 * `averageRating` miran solo a quienes la tienen como su mejor puesto.
 * `count` puede ser 0 y aun así haber un mejor rating, una línea que nadie
 * ocupa de forma natural pero alguien podría cubrir. Se pintan en bloques
 * separados justamente para no confundirlas.
 */
export interface TeamOverviewPitchSlot {
  key: string;
  label: string;
  count: number;
  bestRating: number | null;
  topPlayer: string | null;
  bestVariantLabel: string | null;
  averageRating: number | null;
}

/** Capitán y lanzador de faltas: recomendaciones de rol, no puestos. Su
 *  `rating` NO está en la escala 0-20 de las posiciones, el motor los puntúa
 *  con otra fórmula, , así que se muestra como número pelado, sin barra. */
export interface TeamOverviewSpecialRole {
  key: string;
  label: string;
  topPlayer: string | null;
  rating: number | null;
}

export interface TeamOverviewGroup {
  key: string;
  label: string;
  /** `pending` = la pestaña existe pero su contenido está por definir. */
  chart: "line" | "bars" | "pitch" | "pending";
  pitch: TeamOverviewPitchSlot[];
  specialRoles: TeamOverviewSpecialRole[];
  note: string;
  weeks: string[];
  charts: TeamOverviewChart[];
  metrics: TeamOverviewMetric[];
}

export interface TeamOverview {
  teamName: string;
  playerCount: number;
  currency: string;
  groups: TeamOverviewGroup[];
}

export const apiResumen = {
  teamOverview: (teamId: number) =>
    request<TeamOverview>(`/teams/${teamId}/overview`),
};
