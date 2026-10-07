/** Economia.
 *
 *  Sale de partir `services/api.ts`, que tenia 4147 lineas y se leia entero
 *  en cada cambio del frontend. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../services/api"` sigue valiendo igual.
 */
import { request } from "./nucleo";

export interface ForecastBand {
  weeks: number[];
  p10: number[];
  p50: number[];
  p90: number[];
  model: string;
  backtestMae: number | null;
  candidates: Record<string, number>;
  /** "TT-ss" (temporada-semana, p. ej. "83-05") por cada entrada de `weeks`.
   * Null en cada una si el equipo todavía no sincronizó worlddetails.xml. */
  weekLabels: (string | null)[];
}

/** Desglose de Detalles al estilo Hattrick Control, SubTotal es lo
 * recurrente/estructural de la semana, Otros lo ligado a compraventa de
 * jugadores o algo puntual. Cualquier campo puede ser null: "sin dato",
 * nunca un 0 fabricado (p. ej. el primer sync de un club no trae desglose
 * de la semana ya cerrada). */
export interface IncomeBreakdown {
  spectators: number | null; // Aficionados
  sponsors: number | null; // Patrocinados (incl. bono en la semana en curso)
  financial: number | null; // Financieros
  subtotal: number | null;
  other: number | null; // Venta de jugadores + comisión + temporal
  total: number | null;
}

export interface CostsBreakdown {
  arena: number | null; // Estadio (mantenimiento)
  players: number | null; // Jugadores (sueldos)
  financial: number | null; // Financieros (lo más parecido a "Intereses" de HC)
  staff: number | null; // Empleados
  youth: number | null; // Canteranos
  subtotal: number | null;
  other: number | null; // Compra de jugadores + construcción + temporal
  total: number | null;
}

export interface WeeklyBreakdownRow {
  seasonWeek: string | null;
  date: string;
  /** La semana en curso todavía no cerró, Hattrick puede seguir sumando ahí. */
  isCurrent: boolean;
  income: IncomeBreakdown;
  costs: CostsBreakdown;
}

export interface SeasonBreakdownTotals {
  season: number;
  income: IncomeBreakdown;
  costs: CostsBreakdown;
}

export interface Economy {
  teamName: string;
  currency: string;
  cash: number;
  expectedCash: number;
  weeklyBalance: number;
  structuralBalance: number;
  /** Balance semanal medio de la ventana elegida, sin contar compraventa y
   *  contándola. `null` mientras no haya ni un cierre con desglose. */
  balanceSinTransferencias: number | null;
  balanceConTransferencias: number | null;
  balanceSemanasUsadas: number;
  weeksOfHistory: number;
  series: {
    date: string;
    /** "TT-ss" (temporada-semana, p. ej. "83-05"), null si el equipo
     * todavía no sincronizó worlddetails.xml. */
    seasonWeek: string | null;
    cash: number;
    income: number;
    costs: number;
    balance: number;
    isAnomaly: boolean;
  }[];
  /** La semana en curso, con lo acumulado hasta ahora. Va fuera de `series`
   * porque esa lista son semanas cerradas y alimenta balances y pronóstico. */
  currentWeek: Economy["series"][number] | null;
  weeklyFinance: {
    /** `previous`: la misma partida en la semana cerrada anterior. */
    income: {
      code: string;
      label: string;
      amount: number | null;
      previous: number | null;
    }[];
    costs: {
      code: string;
      label: string;
      amount: number | null;
      previous: number | null;
    }[];
    incomeTotal: number;
    costsTotal: number;
    expectedBalance: number;
    previousIncomeTotal: number | null;
    previousCostsTotal: number | null;
  };
  /** Mismas categorías que `weeklyFinance`, sumando la semana en curso con
   * cada vez más semanas ya cerradas, para el Sankey de varias semanas. */
  sankeyWindows: {
    weeks: number;
    weeksAvailable: number;
    income: { code: string; label: string; amount: number | null }[];
    costs: { code: string; label: string; amount: number | null }[];
  }[];
  balanceWindows: {
    label: string;
    weeksRequested: number;
    weeksAvailable: number;
    income: number | null;
    costs: number | null;
    balance: number | null;
    /** Ingresos − gastos sin compraventa de jugadores. Null si falta el
     * desglose de alguna semana del tramo. */
    balanceExclTransfers: number | null;
  }[];
  structuralForecast: ForecastBand;
  /** Null hasta que haya serie suficiente para validar un modelo temporal. */
  timeseriesForecast: ForecastBand | null;
  recommendedModel: string;
  /** El mismo modelo, ya en la lengua de la pantalla. Lo resuelve el servidor
   *  para que no haya una segunda lista de nombres aquí. */
  recommendedModelLabel: string;
  recommendationReason: string;
  anomalies: string[];
  /** Detalles: más reciente primero (al revés que `series`, que va
   * ascendente porque alimenta gráficos). */
  weeklyBreakdown: WeeklyBreakdownRow[];
  seasonBreakdownTotals: SeasonBreakdownTotals[];
  /** Umbral real para activar el modelo de series de tiempo, usar este
   * valor para el teaser de progreso en Proyección, no copiarlo a mano. */
  minWeeksForTimeseries: number;
  /** Nómina de la plantilla de hoy, con el recargo del 20% por extranjero ya
   *  despejado. Es `null` cuando no se sabe de dónde es ningún jugador. */
  wageBill: {
    total: number;
    players: number;
    foreignPlayers: number;
    foreignSalary: number;
    surcharge: number;
    country: string;
    unknownCountry: number;
    average: number;
    topSalary: number;
    topPlayer: string;
    /** Sueldo semanal por cada 1.000 de TSI. */
    perThousandTsi: number | null;
    /** Lo que se paga a quien no jugó el último partido competitivo. */
    idleSalary: number;
    idlePlayers: number;
    /** Lo que se paga fuera del once ideal. `null` si no se pudo resolver. */
    benchSalary: number | null;
    benchPlayers: number | null;
  } | null;
  /** Semanas que se pidieron y las que de verdad había guardadas. */
  windowRequested: number;
  windowUsed: number;
  /** La compraventa dentro de la ventana. */
  market: {
    weeks: number;
    sold: number;
    bought: number;
    net: number;
    commission: number;
    arrivals: number;
    departures: number;
    shareOfCashPct: number | null;
  };
  /** De dónde sale lo que entra, dentro de la ventana. */
  incomeKpis: {
    weeks: number;
    homeMatches: number;
    gateTotal: number;
    gatePerHomeMatch: number | null;
    sponsorSharePct: number | null;
    fanClubSize: number;
    gatePerMember: number | null;
  };
  /** Lo recurrente de una semana, que es contra lo que hay que medir un gasto
   *  fijo: la semana en curso puede llevar una venta dentro. */
  weeklyStructure: {
    salaries: number;
    staff: number;
    arenaMaintenance: number;
    sponsors: number;
    /** La taquilla de UN partido en casa, que es lo que sortea la
     *  simulación. Para sumarla a un ingreso semanal va `weeklyGate`. */
    baseGate: number;
    /** La misma taquilla ya repartida entre todas las semanas. */
    weeklyGate: number;
    otherFixed: number;
  };
}

// ── Estadio ─────────────────────────────────────────────────────────────────

export const apiEconomia = {
  economy: (teamId: number, horizonWeeks = 52, conSeries = true) =>
    request<Economy>(
      `/teams/${teamId}/economy?horizon_weeks=${horizonWeeks}&con_series=${conSeries}`,
    ),
};
