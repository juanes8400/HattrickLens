/** Hooks de entrenamiento.
 *
 *  Sale de partir `hooks/useTeam.ts`, 601 lineas que abrian 26 de las 31
 *  pantallas. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../hooks/useTeam"` sigue valiendo igual.
 */
import { useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";
import { TEAM_ID } from "./nucleo";

export const useTrainingForecast = () =>
  useQuery({
    queryKey: ["training", TEAM_ID],
    queryFn: () => api.trainingForecast(TEAM_ID),
  });

/** El parte del último entrenamiento. Se pide sólo con su pestaña abierta:
 *  es una pregunta puntual, no parte de la pantalla. */
export const useUltimoEntrenamiento = (enabled = true) =>
  useQuery({
    queryKey: ["ultimo-entrenamiento", TEAM_ID],
    queryFn: () => api.ultimoEntrenamiento(TEAM_ID),
    enabled,
    // Una sincronización desde otra pestaña cambia la respuesta.
    refetchOnMount: "always",
  });

export const usePostMatchTraining = () =>
  useQuery({
    queryKey: ["post-match-training", TEAM_ID],
    queryFn: () => api.postMatchTraining(TEAM_ID),
    // El porcentaje/tipo de entrenamiento puede haber cambiado mediante un
    // sync hecho en otra pestaña. Al volver a Entrenamiento no debe sobrevivir
    // la configuración anterior durante el staleTime global.
    refetchOnMount: "always",
    refetchOnWindowFocus: "always",
  });

export const useTrainingFormula = () =>
  useQuery({
    queryKey: ["training-formula", TEAM_ID],
    queryFn: () => api.trainingFormula(TEAM_ID),
    refetchOnMount: "always",
    refetchOnWindowFocus: "always",
  });

export const useTrainingSquad = (
  skill?: string | null,
  includeThisWeek = true,
) =>
  useQuery({
    queryKey: ["training-squad", TEAM_ID, skill ?? "default", includeThisWeek],
    queryFn: () => api.trainingSquad(TEAM_ID, skill, includeThisWeek),
    refetchOnMount: "always",
    refetchOnWindowFocus: "always",
  });

export const useTrainingDevelopment = (enabled = true) =>
  useQuery({
    queryKey: ["training-development", TEAM_ID],
    queryFn: () => api.trainingDevelopment(TEAM_ID),
    enabled,
    // La tabla Ocerin depende de la configuración de training.xml. Una
    // pestaña ya abierta debe volver a calcularla después de que otro tab
    // sincronice un nuevo % de condición.
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: "always",
  });
