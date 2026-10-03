/** La plantilla.
 *
 *  Sale de partir `services/api.ts`, que tenia 4147 lineas y se leia entero
 *  en cada cambio del frontend. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../services/api"` sigue valiendo igual.
 */
import type { SquadPlayer } from "./comun";
import { request } from "./nucleo";

export interface Squad {
  teamId: number;
  teamName: string;
  currency: string;
  position: string | null;
  playerCount: number;
  totals: {
    averageAge: number;
    averageForm: number;
    averageExperience: number;
    averageTsi: number;
    totalTsi: number;
    /** Los once de más TSI. */
    top11Tsi: number;
    averageSalary: number;
    totalSalary: number;
  };
  comparison: {
    mode: "previous_change" | "snapshot";
    baselineSyncId: number | null;
    baselineCapturedAt: string | null;
  };
  /** Las ventanas de comparación, con la que no se puede usar todavía
   *  marcada: el servidor resuelve contra qué cierre compara cada una, así
   *  que la cuenta de fechas está en un solo sitio. */
  comparisonWindows: { key: VentanaDeComparacion; available: boolean }[];
  history: { syncId: number; capturedAt: string; snapshots: number }[];
  players: SquadPlayer[];
}

/** Contra qué se miran las diferencias de la plantilla. `change` es el
 *  último cambio de cada jugador; `all`, el cierre más antiguo guardado. */
export type VentanaDeComparacion =
  "change" | "w1" | "w2" | "w4" | "w8" | "w16" | "all";

export const apiPlantilla = {
  squad: (
    teamId: number,
    position?: string,
    comparisonWindow?: VentanaDeComparacion,
  ) => {
    const query = new URLSearchParams();
    if (position) query.set("position", position);
    if (comparisonWindow) query.set("comparison_window", comparisonWindow);
    const suffix = query.toString();
    return request<Squad>(
      `/teams/${teamId}/squad${suffix ? `?${suffix}` : ""}`,
    );
  },
};
