/** Transferencias y saldo por jugador.
 *
 *  Sale de partir `services/api.ts`, que tenia 4147 lineas y se leia entero
 *  en cada cambio del frontend. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../services/api"` sigue valiendo igual.
 */
import { request } from "./nucleo";

export interface TransferAttemptRow {
  /** "483141997_2": el segundo intento de ese jugador. */
  key: string;
  id: number;
  attemptNumber: number;
  htPlayerId: number | null;
  name: string;

  detectedAt: string;
  /** Cuando cerro la puja. En un intento fallido no hay fecha de venta. */
  closedAt: string | null;
  open: boolean;
  sold: boolean;

  askingPrice: number | null;
  highestBid: number | null;
  salePrice: number | null;
  /** Solo en los exitosos. */
  agentPct: number | "?";
  timesSeen: number | null;
  asked: boolean;

  tsi: number | "?";
  age: string;
  skills: Record<string, number | "?">;
  specialty: string;
  character: string;
  nativeCountry: string;
  /** Para pintar la bandera. */
  nativeCountryCode: string | null;
  snapshotAt: string | null;
  /** La foto esta lejos del cierre: no leerla como exacta. */
  stale: boolean;

  fromAcademy: boolean;
  purchasedAt: string | null;
  purchasePrice: number | "?";
  ageAtPurchase: string;
  daysSincePurchase: number | "?";
  salaryToDate: number | "?";
  trainingThatWeek: string;
}

export interface TransferAttempts {
  currency: string;
  rows: TransferAttemptRow[];
  /** Los que terminaron y siguen sin respuesta. */
  pendingQuestion: TransferAttemptRow[];
}

export interface TransfersHistorySyncResult {
  status: string;
  pagesFetched: number;
  transfersSeen: number;
  transfersNew: number;
  snapshotsWritten: number;
  errors: string[];
}

export interface PlayerBalanceRow {
  htPlayerId: number;
  name: string;
  isAcademyGraduate: boolean;
  /** Ni comprado ni de cantera: el movimiento llegó sin identificador. */
  originUnknown: boolean;
  /** El identificador que se enseña es el de la transferencia. */
  htPlayerIdIsTransfer: boolean;
  /** Lo que costó ascenderlo desde la cantera, en moneda local. 0 para quien
   *  llegó fichado: ese tiene precio de compra. */
  promotionCost: number;
  isPurchasePriceManual: boolean;
  purchasePrice: number | null;
  purchasedAt: string | null;
  salePrice: number | null;
  soldAt: string | null;
  salaryTotal: number;
  /** False cuando no hay ningun salario guardado del jugador: el 0
   *  de salaryTotal es ignorancia, no un calculo. */
  /** Partidos que jugo de verdad con nosotros; "?" si aun no se conto. */
  gamesWithUs: number | string;
  salaryKnown: boolean;
  /** De dónde sale `salaryTotal`: `observado` es lo que se vio cobrar,
   *  `estimado` lo que la curva calcula para una etapa anterior a HT Lens, y
   *  `desconocido` es que no hay ni lo uno ni lo otro. */
  salarySource: "observado" | "estimado" | "desconocido";
  /** Identificador de la ETAPA. Dos filas del mismo jugador comparten
   *  htPlayerId, asi que esto es lo que las distingue. */
  stintId: number | null;
  salaryBreakdown: {
    /** Se conserva el nombre por compatibilidad; representa cobros. */
    weeks: number;
    /** Salario unitario de cada cobro del tramo. */
    salary: number;
    season: string;
    /** Subtotal: cobros por salario unitario. */
    total: number;
  }[];
  listingCount: number;
  listingAttempts: { highestBid: number | null; detectedAt: string }[];
  listingCost: number;
  agentPct: number | null;
  /** Lo que se llevaría la casa si lo vendieras HOY, para quien sigue en el
   *  club: la tabla del agente por los días que lleva, más el 5 % de
   *  siempre, o el 5 % plano si es canterano en su primera venta. `null` en
   *  cuanto la venta es real, que entonces manda `agentPct`. Lo calcula el
   *  servidor con la misma función que cobra una venta de verdad. */
  agentPctIfSoldNow: number | null;
  // HL-161, 2026-08-14: comisión de club anterior EXACTA (partidos reales
  // jugados con nosotros × tabla oficial de Hattrick), 0 si el club al
  // que se lo vendimos todavía no lo ha revendido. Reemplaza el reparto
  // heurístico "de origen desconocido" que existía antes.
  resaleBonusShare: number;
  saldo: number | null;
  isSold: boolean;
  /** Entrenamiento individual inferido por el mayor aumento de las siete
   * habilidades entre el primer snapshot y el ultimo anterior a la venta.
   * Los casos ambiguos usan niveles, jugadores y desempates de temporada. */
  derivedTrainingSkill: string | null;
  derivedTrainingLevels: number | null;
  derivedTrainingMethod:
    | "direct_maximum"
    | "season_levels"
    | "season_players"
    | "season_current_training"
    | "season_skill_priority"
    | "insufficient_evidence";
  derivedTrainingMethodLabel: string;
  /** Entrenamiento del club que estaba activo cuando se produjo la venta.
   * Se conserva como dato historico, pero no clasifica el saldo por jugador. */
  trainingAtSale: string | null;
  seasonAtSale: string | null;
  /** La semana de temporada (1-16) de cada movimiento, sin la temporada
   *  delante: las cascadas de Transferencias juntan todas las semanas 05 de
   *  cualquier temporada en la misma columna. */
  weekAtSale: number | null;
  weekAtPurchase: number | null;
  topSkillAtSale: string | null;
  bidHourAtSale: string | null;
  nativeCountry: string;
  nativeCountryCode: string | null;
  character: string;
  specialty: string;
  tsiAtPurchase: number | "?";
  tsiAtSale: number | "?";
  deltaTsi: number | "?";
  commissionAmount: number | "?";
  roiPct: number | "?";
  /** Lo invertido en la etapa. Los desgloses ROI suman esto y el saldo
   *  por grupo, y dividen al final. */
  totalCost: number;
  destinationCountry: string;
  destinationCountryCode: string | null;
  ageAtSale: number | "?";
  // 2026-08-05: tabla "Detalle" de transferencias.
  ageAtPurchase: number | "?";
  experienceAtPurchase: number | "?";
  leadershipAtPurchase: number | "?";
  formAtPurchase: number | "?";
  staminaAtPurchase: number | "?";
  keeperAtPurchase: number | "?";
  defendingAtPurchase: number | "?";
  playmakingAtPurchase: number | "?";
  wingerAtPurchase: number | "?";
  passingAtPurchase: number | "?";
  scoringAtPurchase: number | "?";
  setPiecesAtPurchase: number | "?";
  experienceAtSale: number | "?";
  formAtSale: number | "?";
  staminaAtSale: number | "?";
  keeperAtSale: number | "?";
  defendingAtSale: number | "?";
  playmakingAtSale: number | "?";
  wingerAtSale: number | "?";
  passingAtSale: number | "?";
  scoringAtSale: number | "?";
  setPiecesAtSale: number | "?";
  daysSincePurchase: number | "?";
  saldoPerDeltaTsi: number | "?";
  isDepartureWithoutSale: boolean;
}

export interface PlayerBalance {
  teamName: string;
  currency: string;
  players: PlayerBalanceRow[];
  totalSaldo: number;
  unknownPurchaseCount: number;
  byTrainingType: Record<string, number>;
  bySeason: Record<string, number>;
  byAgeBucket: Record<string, number>;
  byTopSkill: Record<string, number>;
  byBidHour: Record<string, number>;
  // HL-161, 2026-08-04: <Stats> de transfersteam.xml, TODA la historia de
  // compraventas del equipo, para los KPI de "Resumen".
  transferTotalBuys: number;
  transferTotalSales: number;
  transferNumberBuys: number;
  transferNumberSales: number;
}

// ── Cierre de la fórmula de entrenamiento ────────────────────────────────────

export const apiTransferencias = {
  /** Lo que ha costado la gente parecida a este jugador. No gasta cuota de
   *  Hattrick: sirve lo que dejo el paso semanal del mercado. */
  precioComparable: (teamId: number, htPlayerId: number) =>
    request<PrecioComparable>(
      `/teams/${teamId}/players/${htPlayerId}/precio-comparable`,
    ),
  playerBalance: (teamId: number, season?: string) => {
    const params = new URLSearchParams();
    if (season && season !== "all") params.set("season", season);
    const qs = params.toString();
    return request<PlayerBalance>(
      `/teams/${teamId}/player-balance${qs ? `?${qs}` : ""}`,
    );
  },
  syncTransfersHistory: (teamId: number) =>
    request<TransfersHistorySyncResult>(`/teams/${teamId}/transfers/sync`, {
      method: "POST",
    }),
  /** Cuantas fichas quedan por descargar. No llama a Hattrick: solo lee la base. */
  transferAttempts: (teamId: number) =>
    request<TransferAttempts>(`/teams/${teamId}/transfer-attempts`),
  /** Las firmas del libro de visitas, de la más nueva a la más vieja. */
  setTimesSeen: (
    teamId: number,
    attemptId: number,
    cambios: {
      times_seen?: number;
      asking_price?: number;
      dismissed?: boolean;
    },
  ) =>
    request<{
      id: number;
      timesSeen: number | null;
      askingPrice: number | null;
      asked: boolean;
    }>(`/teams/${teamId}/transfer-attempts/${attemptId}`, {
      method: "PATCH",
      body: JSON.stringify(cambios),
    }),
  /** Borra un intento de venta. Distinto de "no tener en cuenta". */
  deleteTransferAttempt: (teamId: number, attemptId: number) =>
    request<{ deleted: number }>(
      `/teams/${teamId}/transfer-attempts/${attemptId}`,
      { method: "DELETE" },
    ),
  /** Atribuye a mano lo que falta de una etapa cerrada, o la excluye. */
};

/** Una habilidad y su nivel, sin formatear: el nombre viene con la clave
 *  interna y lo traduce la pantalla con el glosario oficial. */
export interface RasgoVisible {
  habilidad: string;
  nivel: number;
}

/** Un comparable: una venta del mercado que se parece a tu jugador. */
export interface ComparableDeMercado {
  htPlayerId: number;
  nombre: string;
  /** El precio que cuenta: el de cierre si ya se resolvió, la puja si no. */
  precio: number;
  /** La puja con la que entró, siempre. Junto a `precio` y `firme` deja ver
   *  cuánto se quedaba corta. */
  puja: number;
  /** Si entra en el número. Falso sólo para un provisional abandonado. */
  cuenta: boolean;
  /** Cuánto se parece, del 100% al 75%. */
  peso: number;
  /** Falso mientras sea una puja en curso y no una venta cerrada. */
  firme: boolean;
  /** Ya cumplió sus siete semanas y sigue por no haber nada mejor. */
  viejo: boolean;
  edad: number;
  perfil: RasgoVisible[];
  semanas: number;
  /** Cuándo cierra su subasta, mientras sea una puja. Nulo si ya es firme. */
  cierra: string | null;
  /** El nombre, ya resuelto por el servidor. Vacío si no tiene. */
  especialidad: string;
  tsi: number;
  /** Código de dos letras para la bandera. Vacío si no se guardó. */
  paisCodigo: string;
  paisNombre: string;
}

/** Lo que ha costado la gente parecida a un jugador tuyo. */
export interface PrecioComparable {
  /** `null` mientras no haya seis ventas. */
  media: number | null;
  mediana: number | null;
  minimo: number | null;
  maximo: number | null;
  n: number;
  faltan: number;
  pesoMinimo: number;
  /** Cuántas son todavía pujas en curso y no ventas cerradas. */
  provisionales: number;
  semanasDelMasViejo: number;
  perfil: RasgoVisible[];
  /** Cómo se llama el dinero. Las cifras ya vienen en la moneda del
   *  equipo, divididas por la tasa del país. */
  moneda: string;
  comparables: ComparableDeMercado[];
}
