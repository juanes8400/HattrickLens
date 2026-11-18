/** Hooks de resumen.
 *
 *  Sale de partir `hooks/useTeam.ts`, 601 lineas que abrian 26 de las 31
 *  pantallas. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../hooks/useTeam"` sigue valiendo igual.
 */
import { keepPreviousData, useQueries, useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";
import { TEAM_ID } from "./nucleo";

export const useTeamOverview = () =>
  useQuery({
    queryKey: ["team-overview", TEAM_ID],
    queryFn: () => api.teamOverview(TEAM_ID),
  });

/** «Mirar a»: las medias semanales de cada grupo marcado, una petición por
 *  grupo. La clave son sus jugadores, ordenados: si alguien cambia de grupo,
 *  la petición es otra. Mientras llega lo nuevo se enseña lo anterior. */
export const useSeriesDeGrupos = (grupos: number[][]) =>
  useQueries({
    queries: grupos.map((ids) => {
      const orden = [...ids].sort((a, b) => a - b);
      return {
        queryKey: ["overview-series", TEAM_ID, orden.join(",")],
        queryFn: () => api.teamOverviewSeries(TEAM_ID, orden),
        placeholderData: keepPreviousData,
      };
    }),
  });

/** Clases de Jugador. Sin caché por sincronización en el servidor: la etapa
 *  confirmada a mano y los grupos propios cambian sin sincronizar. */
export const usePlayerClasses = () =>
  useQuery({
    queryKey: ["player-classes", TEAM_ID],
    queryFn: () => api.playerClasses(TEAM_ID),
  });

/** Quién cambió de clase desde la sincronización anterior, para Cambios.
 *  La primera petición tras sincronizar guarda la lectura de ese sync. */
export const usePlayerClassChanges = () =>
  useQuery({
    queryKey: ["player-class-changes", TEAM_ID],
    queryFn: () => api.playerClassChanges(TEAM_ID),
  });
