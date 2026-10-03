/** Hooks de modelos.
 *
 *  Sale de partir `hooks/useTeam.ts`, 601 lineas que abrian 26 de las 31
 *  pantallas. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../hooks/useTeam"` sigue valiendo igual.
 */
import { useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";
import { TEAM_ID } from "./nucleo";

/** El catálogo de cálculos. Describe los motores, que son iguales para
 *  todos, así que no lleva equipo ni se invalida al sincronizar. */
export const useCalculos = () =>
  useQuery({ queryKey: ["calculos"], queryFn: api.calculos });

export const useExperienceModel = () =>
  useQuery({
    queryKey: ["experience-model", TEAM_ID],
    queryFn: () => api.experienceModel(TEAM_ID),
  });

export const useLoyaltyModel = () =>
  useQuery({
    queryKey: ["loyalty-model", TEAM_ID],
    queryFn: () => api.loyaltyModel(TEAM_ID),
  });
