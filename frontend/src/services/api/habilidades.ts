/** Habilidades de la plantilla.
 *
 *  Sale de partir `services/api.ts`, que tenia 4147 lineas y se leia entero
 *  en cada cambio del frontend. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../services/api"` sigue valiendo igual.
 */
import { request } from "./nucleo";

/** Habilidades: mapa de la plantilla, profundidad y cuello de botella. */
export type SkillsTone = "danger" | "warning" | "ok";

export interface SkillsCandidate {
  htPlayerId: number;
  name: string;
  /** Rendimiento en el puesto: el mismo índice de la pantalla Posiciones. */
  rating: number;
  /** La habilidad principal del puesto, en niveles. */
  skillLevel: number;
}

/** Un puesto de la última formación oficial y su recambio real. */
export interface SkillsDepth {
  key: string;
  label: string;
  /** Cuántos jugaron de titulares en ese puesto. */
  starters: number;
  skillLabel: string;
  best: SkillsCandidate | null;
  /** El mejor del banquillo en ese puesto. */
  substitute: SkillsCandidate | null;
  /** Quién entraría después, si el suplente ya está ocupado en otro puesto. */
  nextSubstitute: SkillsCandidate | null;
  dropPct: number | null;
  /** Otros puestos con el mismo recambio. */
  alsoCovers: string[];
  tone: SkillsTone;
}

export interface Skills {
  skills: { key: string; label: string; short: string }[];
  players: {
    htPlayerId: number;
    name: string;
    age: number;
    tsi: number;
    position: string | null;
    positionLabel: string | null;
    positionSkill: string | null;
    /** Claves en camelCase: `setPieces`, no `set_pieces`. */
    skills: Record<string, number>;
    specialty: string;
    injured: boolean;
    inLineup: boolean;
    /** Para la bandera, igual que en Posiciones. */
    countryCode: string | null;
    nativeLeagueName: string | null;
  }[];
  depth: SkillsDepth[];
  sectors: {
    key: string;
    label: string;
    rating: number;
    /** Dónde queda en la serie: 0 = el peor, 100 = el mejor. */
    seriesPosition: number;
    /** Ventaja sobre el mejor rival del sector, en %. Negativa = por detrás. */
    marginPct: number;
    bestRival: string;
    bestRivalValue: number;
    /** «Bordalás (Def 18) · Teano (Def 16)». */
    who: string;
    /** Lo mismo sin juntar: la sigla llega traducida. */
    whoItems: { player: string; sigla: string; nivel: number }[];
    tone: SkillsTone;
    verdict: string;
  }[];
  bottleneck: string | null;
  upgrades: {
    htPlayerId: number;
    player: string;
    skill: string;
    skillLabel: string;
    fromLevel: number;
    gainPct: number;
    impact: "Alto" | "Medio";
  }[];
  lastMatchDate: string | null;
  /** De qué partido salió el once. La fecha sola no lo identifica, y sin
   *  identificarlo no hay forma de juzgar si el once tiene sentido. */
  lastMatchOpponent: string | null;
  lastMatchCompetition: string | null;
  lastMatchScore: string | null;
  lastMatchIsHome: boolean | null;
  /** Cuántos jugadores tiene el once que se enseña. Menos de once quiere decir
   *  que faltó gente y no se pudo rellenar, y entonces `formation` viene a
   *  `null`: no se inventa una formación con lo que haya. */
  lineupPlayers: number;
  /** Cuántos de ellos NO jugaron ese partido: entraron a ocupar la plaza de un
   *  titular que ya no está en la plantilla. Cero es lo normal. */
  lineupReplacements: number;
  /** De dónde salió el once, de más fiable a menos: `hattrick` (la alineación
   *  real del partido, pedida a Hattrick después de jugarse), `ordenes` (las
   *  órdenes que se enviaron), `partido` (las fichas de ese partido) o
   *  `fichas` (el último partido de cada jugador, lo más frágil). */
  lineupSource: "hattrick" | "ordenes" | "partido" | "fichas" | null;
  /** `null` cuando el once no está completo: con ocho jugadores no hay
   *  formación que decir, y decía «3-5-0», que no existe. */
  formation: string | null;
  /** El reparto de la última formación oficial. */
  lastCentralDefenders: number | null;
  lastInnerMidfielders: number | null;
  /** La formación con la que se calcula Profundidad: la última o la elegida. */
  depthFormation: string | null;
  depthCentralDefenders: number | null;
  depthInnerMidfielders: number | null;
  centralDefenderOptions: number[];
  innerMidfielderOptions: number[];
}

export const apiHabilidades = {
  skills: (
    teamId: number,
    formation?: string,
    centralDefenders?: number,
    innerMidfielders?: number,
  ) => {
    const q = new URLSearchParams();
    if (formation) q.set("formation", formation);
    if (formation && centralDefenders != null)
      q.set("central_defenders", String(centralDefenders));
    if (formation && innerMidfielders != null)
      q.set("inner_midfielders", String(innerMidfielders));
    const qs = q.toString();
    return request<Skills>(`/teams/${teamId}/skills${qs ? `?${qs}` : ""}`);
  },
};
