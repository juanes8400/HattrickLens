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
) =>
  useQuery({
    queryKey: ["squad", TEAM_ID, position, comparisonWindow ?? "change"],
    queryFn: () => api.squad(TEAM_ID, position, comparisonWindow),
  });
