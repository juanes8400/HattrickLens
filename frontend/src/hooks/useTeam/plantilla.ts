/** Hooks de plantilla.
 *
 *  Sale de partir `hooks/useTeam.ts`, 601 lineas que abrian 26 de las 31
 *  pantallas. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../hooks/useTeam"` sigue valiendo igual.
 */
import { useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";
import type { VentanaDeComparacion } from "../../services/api";
import { TEAM_ID } from "./nucleo";

export const useSquad = (
  position?: string,
  comparisonWindow?: VentanaDeComparacion,
  // `enabled` para quien sólo necesita la plantilla en una de sus pestañas
  // (2026-10-03). Transferencias la usa únicamente en «Plantilla actual», y
  // pedirla al abrir la pantalla era media petición de más en la pantalla
  // que ya era la más cara de la aplicación.
  opciones?: { enabled?: boolean },
) =>
  useQuery({
    queryKey: ["squad", TEAM_ID, position, comparisonWindow ?? "change"],
    queryFn: () => api.squad(TEAM_ID, position, comparisonWindow),
    enabled: opciones?.enabled ?? true,
  });
