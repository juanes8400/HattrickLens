/** Estadio.
 *
 *  Sale de partir `services/api.ts`, que tenia 4147 lineas y se leia entero
 *  en cada cambio del frontend. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../services/api"` sigue valiendo igual.
 */
import { request } from "./nucleo";

/** El estadio, con lo que Hattrick hace público y nada más.
 *
 *  Hasta el 2026-09-01 esto traía el desglose de asistencia POR SECTOR --lo
 *  vendido en cada uno, su ocupación, cuántas veces se agotó y la demanda
 *  censurada--. Es una función de HT Supporter y las reglas de CHPP prohíben
 *  replicarla, así que ni se pide ni se guarda ni se enseña.
 *
 *  Queda lo que ve cualquiera en la página de un partido: cuánta gente entró
 *  en total y cuánto se recaudó. */
export interface Arena {
  teamName: string;
  currency: string;
  /** Selector de temporada, igual que Partidos. `selectedSeason` null = todas. */
  availableSeasons: number[];
  currentSeason: number | null;
  selectedSeason: number | null;
  /** Si cambió el aforo, el día desde el que se cuenta todo. */
  capacityChangedOn: string | null;
  capacityTotal: number;
  matchesAnalysed: number;
  avgOccupancy: number;
  totalRevenue: number;
  matches: {
    date: string;
    /** Contra quién se jugó: es lo que rotula el eje, no la fecha. */
    rival: string;
    matchType: number;
    /** El torneo en palabras: «Liga», «Copa», «Amistoso»... */
    tournament: string;
    capacity: number;
    sold: number;
    occupancy: number;
    revenue: number;
    emptySeats: number;
  }[];
  expansionOptions: {
    /** Sólo el nombre del tamaño: «Ampliación pequeña». El desglose de dónde
     *  van los asientos lo compone la pantalla con `addedSeats`. */
    label: string;
    addedSeats: Record<string, number>;
    buildCost: number;
    addedWeeklyMaintenance: number;
    addedRevenuePerMatch: number;
    netPerSeason: number;
    paybackSeasons: number | null;
    verdict: string;
  }[];
  notes: string[];
  tipo: ArenaTipo;
  /** Aforo de hoy por sector: general, preferentes, tribunas, palcos. */
  composition: Record<string, number>;
  /** El reparto que se da por óptimo, en fracciones que suman 1. */
  recommendedShares: Record<string, number>;
}

/** Qué partidos mira Estadio. */
export type ArenaTipo = "todos" | "oficiales" | "amistosos";

// ── Partidos ────────────────────────────────────────────────────────────────

export const apiEstadio = {
  arena: (
    teamId: number,
    fillRate?: number,
    tipo: ArenaTipo = "todos",
    season?: number | null,
  ) => {
    const q = new URLSearchParams();
    if (fillRate != null) q.set("fill_rate", String(fillRate));
    if (tipo !== "todos") q.set("tipo", tipo);
    if (season != null) q.set("season", String(season));
    const qs = q.toString();
    return request<Arena>(`/teams/${teamId}/arena${qs ? `?${qs}` : ""}`);
  },
};
