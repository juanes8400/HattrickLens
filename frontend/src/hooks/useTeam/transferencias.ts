/** Hooks de transferencias.
 *
 *  Sale de partir `hooks/useTeam.ts`, 601 lineas que abrian 26 de las 31
 *  pantallas. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../hooks/useTeam"` sigue valiendo igual.
 */
import { useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";
import { TEAM_ID } from "./nucleo";

export const usePlayerBalance = (season?: string) =>
  useQuery({
    queryKey: ["player-balance", TEAM_ID, season ?? "all"],
    queryFn: () => api.playerBalance(TEAM_ID, season),
  });
