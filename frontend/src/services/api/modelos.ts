/** Modelos y calculos que la aplicacion ensena por transparencia.
 *
 *  Sale de partir `services/api.ts`, que tenia 4147 lineas y se leia entero
 *  en cada cambio del frontend. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../services/api"` sigue valiendo igual.
 */
import type { CalculationReference } from "./comun";
import { request } from "./nucleo";

/** Points per experience level, measured rather than declared. `source` says
 *  whether the figure comes from observation or is still the configured prior. */
export interface ExperienceModel {
  pointsPerLevel: number;
  configuredPointsPerLevel: number;
  observedMean: number | null;
  standardDeviation: number | null;
  observations: number;
  source: "configured" | "observed" | "blended";
  confidenceInterval: [number, number] | null;
  byLevel: Record<string, number>;
  matchPoints: Record<string, number>;
  verified: string[];
  fromSpec: string[];
  observationsNeeded: number;
  crossingsSeen: number;
  discardedCrossings: number;
  distinctReadings: number;
  levelUps: {
    player: string;
    fromLevel: number;
    toLevel: number;
    pointsAccumulated: number;
  }[];
  reference: CalculationReference;
}

/** Fórmula de Fidelidad basada únicamente en días desde la compra. */
export interface LoyaltyModel {
  formula: string;
  maxLevel: number;
  fullDays: number;
  seasons: number;
  thresholds: { level: number; day: number }[];
  reference: CalculationReference;
}

/** Una constante de una fórmula, con su valor REAL leído del motor. */
export type ConstanteDeCalculo = {
  symbol: string;
  value: string;
  what: string;
};

/** Una tabla de números que la fórmula consulta en vez de calcular.
 *
 *  Enseñar sólo los extremos --«la tabla va de 17 a 36»-- contesta a medias:
 *  quien abre esta pantalla quiere ver la fila que le toca a SU jugador. */
export type TablaDeCalculo = {
  title: string;
  columns: string[];
  rows: string[][];
  note: string;
};

/** De dónde sale un dato que entra en una fórmula. */
export type FuenteDeCalculo = {
  what: string;
  origin: string;
};

/** Un cálculo de la herramienta, tal como lo publica Transparencia. */
export type Calculo = {
  id: string;
  name: string;
  /** La pregunta que contesta. Va antes que la fórmula: quien abre esto
   *  quiere saber qué mira, no qué se multiplica. */
  answers: string;
  formula: string;
  /** El CUERPO, en parrafos. Sólo lo llevan los cálculos que hay que CONTAR
   *  --por qué esta forma y no otra, qué se probó y se descartó, cómo se
   *  comprobó-- y no basta con enseñar su fórmula. Vacío en casi todos. */
  body: string[];
  /** Los datos que entran, con su procedencia. Sin esto la fórmula dice
   *  cómo se hace la cuenta pero no de dónde salen los sumandos. */
  sources: FuenteDeCalculo[];
  constants: ConstanteDeCalculo[];
  /** Los parámetros que no caben en una lista: coeficientes por
   *  entrenamiento, el reloj de edad, la tabla de resistencia. */
  tables: TablaDeCalculo[];
  /** La cuenta hecha con numeros de verdad, linea a linea. Una formula se
   *  entiende, pero no se comprueba: el paso a paso deja repetirla. */
  steps: string[];
  limits: string[];
  note: string;
  /** Panel VIVO que la pantalla pinta debajo, con los valores de tu club.
   *  `null` cuando el cálculo no tiene más que su fórmula. */
  live: string | null;
};

export type SeccionDeCalculos = {
  id: string;
  name: string;
  calcs: Calculo[];
};

export const apiModelos = {
  calculos: () => request<SeccionDeCalculos[]>(`/teams/calculos`),
  experienceModel: (teamId: number) =>
    request<ExperienceModel>(`/teams/${teamId}/experience/calibration`),
  loyaltyModel: (teamId: number) =>
    request<LoyaltyModel>(`/teams/${teamId}/loyalty/model`),
};
