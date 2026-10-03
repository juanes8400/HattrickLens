/** Hooks de jugadores.
 *
 *  Sale de partir `hooks/useTeam.ts`, 601 lineas que abrian 26 de las 31
 *  pantallas. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../hooks/useTeam"` sigue valiendo igual.
 */
import { useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";
import { TEAM_ID } from "./nucleo";

export const usePlayerDetail = (htPlayerId: number) =>
  useQuery({
    queryKey: ["player", TEAM_ID, htPlayerId],
    queryFn: () => api.playerDetail(TEAM_ID, htPlayerId),
  });

export const usePositionModel = () =>
  useQuery({ queryKey: ["position-model"], queryFn: api.positionModel });

export const usePlayerTrainingLevels = (
  htPlayerId: number | null,
  skill?: string | null,
) =>
  useQuery({
    queryKey: [
      "player-training-levels",
      TEAM_ID,
      htPlayerId,
      skill ?? "default",
    ],
    queryFn: () =>
      api.playerTrainingLevels(TEAM_ID, htPlayerId as number, skill),
    enabled: htPlayerId != null,
  });
