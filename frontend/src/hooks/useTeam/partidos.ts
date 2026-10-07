/** Hooks de partidos.
 *
 *  Sale de partir `hooks/useTeam.ts`, 601 lineas que abrian 26 de las 31
 *  pantallas. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../hooks/useTeam"` sigue valiendo igual.
 */
import { useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";
import { TEAM_ID } from "./nucleo";

export const useMatches = (includeFriendlies = false, season?: number | null) =>
  useQuery({
    queryKey: ["matches", TEAM_ID, includeFriendlies, season ?? null],
    queryFn: () => api.matches(TEAM_ID, includeFriendlies, season),
  });

export const useMatchDetail = (htMatchId: number | null) =>
  useQuery({
    queryKey: ["match", TEAM_ID, htMatchId],
    queryFn: () => api.matchDetail(TEAM_ID, htMatchId as number),
    enabled: htMatchId != null,
  });

/** El parte del último partido jugado, contra lo que dijimos antes de jugarlo.
 *  Encabeza Cambios. Devuelve `null` mientras no haya ningún partido jugado. */
export const useLastMatchReport = () =>
  useQuery({
    queryKey: ["last-match-report", TEAM_ID],
    queryFn: () => api.lastMatchReport(TEAM_ID),
  });
