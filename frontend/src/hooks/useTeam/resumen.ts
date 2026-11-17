/** Hooks de resumen.
 *
 *  Sale de partir `hooks/useTeam.ts`, 601 lineas que abrian 26 de las 31
 *  pantallas. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../hooks/useTeam"` sigue valiendo igual.
 */
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api, type GrupoDeRentabilidad } from "../../services/api";
import { TEAM_ID } from "./nucleo";

/** `mirar`: un grupo de Rentabilidad deportiva en vez de la plantilla entera.
 *  Al cambiarlo se sigue enseñando lo anterior hasta que llega lo nuevo, para
 *  que la página no parpadee. */
export const useTeamOverview = (mirar: GrupoDeRentabilidad | null = null) =>
  useQuery({
    queryKey: ["team-overview", TEAM_ID, mirar ?? "plantilla"],
    queryFn: () => api.teamOverview(TEAM_ID, mirar),
    placeholderData: keepPreviousData,
  });

/** Clases de Jugador. Sin caché por sincronización en el servidor: la etapa
 *  confirmada a mano y los grupos propios cambian sin sincronizar. */
export const usePlayerClasses = () =>
  useQuery({
    queryKey: ["player-classes", TEAM_ID],
    queryFn: () => api.playerClasses(TEAM_ID),
  });
