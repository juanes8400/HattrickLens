/** Hooks de resumen.
 *
 *  Sale de partir `hooks/useTeam.ts`, 601 lineas que abrian 26 de las 31
 *  pantallas. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../hooks/useTeam"` sigue valiendo igual.
 */
import { useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";
import { TEAM_ID } from "./nucleo";

export const useTeamOverview = () =>
  useQuery({
    queryKey: ["team-overview", TEAM_ID],
    queryFn: () => api.teamOverview(TEAM_ID),
  });

/** Clases de Jugador. Sin caché por sincronización en el servidor: la etapa
 *  confirmada a mano y los grupos propios cambian sin sincronizar. */
export const usePlayerClasses = () =>
  useQuery({
    queryKey: ["player-classes", TEAM_ID],
    queryFn: () => api.playerClasses(TEAM_ID),
  });
