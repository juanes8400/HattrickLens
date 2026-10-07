/** Hooks de estadio.
 *
 *  Sale de partir `hooks/useTeam.ts`, 601 lineas que abrian 26 de las 31
 *  pantallas. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../hooks/useTeam"` sigue valiendo igual.
 */
import { useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";
import type { ArenaTipo } from "../../services/api";
import { TEAM_ID } from "./nucleo";

export const useArena = (
  fillRate?: number,
  tipo: ArenaTipo = "todos",
  season?: number | null,
) =>
  useQuery({
    queryKey: ["arena", TEAM_ID, fillRate ?? null, tipo, season ?? null],
    queryFn: () => api.arena(TEAM_ID, fillRate, tipo, season),
  });
