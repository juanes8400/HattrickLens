/** Hooks de juveniles.
 *
 *  Sale de partir `hooks/useTeam.ts`, 601 lineas que abrian 26 de las 31
 *  pantallas. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../hooks/useTeam"` sigue valiendo igual.
 */
import { useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";
import { TEAM_ID } from "./nucleo";

export const useAcademy = () =>
  useQuery({
    queryKey: ["academy", TEAM_ID],
    queryFn: () => api.academy(TEAM_ID),
  });

/** Quién trajo a cada canterano. Va aparte de `useAcademy` porque son datos
 *  que sólo mira la pestaña de Ojeadores. */
export const useAcademyScouts = () =>
  useQuery({
    queryKey: ["academy-scouts", TEAM_ID],
    queryFn: () => api.academyScouts(TEAM_ID),
  });

/** La cuenta de cada ojeador: coste semanal contra lo que trajo. */
export const useAcademyScoutsLedger = () =>
  useQuery({
    queryKey: ["academy-scouts-ledger", TEAM_ID],
    queryFn: () => api.academyScoutsLedger(TEAM_ID),
  });

export const useAcademyTrainingPlan = (params: {
  main: string;
  secondary: string;
  soonMaxDays: number;
  weightBase: number;
}) =>
  useQuery({
    queryKey: ["academy-training-plan", TEAM_ID, params],
    queryFn: () => api.academyTrainingPlan(TEAM_ID, params),
    enabled: Boolean(params.main && params.secondary),
    // Los multiplicadores forman parte del cálculo, no son una foto que
    // convenga conservar. Una pestaña abierta durante una actualización no
    // debe seguir mostrando el antiguo 50% ni mezclar por un instante el
    // reparto anterior con los selectores nuevos.
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: "always",
  });

export const useAcademySkillScores = (params: {
  soonMaxDays: number;
  weightBase: number;
  trainableMethod: string;
  trainable: Record<string, number>;
  trainableWeight?: number | null;
}) =>
  useQuery({
    queryKey: ["academy-skill-scores", TEAM_ID, params],
    queryFn: () => api.academySkillScores(TEAM_ID, params),
    // Al mover un deslizador se conserva la tabla anterior mientras llega la
    // nueva: parpadear a vacío en cada píxel haría el mando inusable.
    placeholderData: (previous) => previous,
  });

/** Qué se movió en la academia dentro de la ventana elegida.
 *
 *  Va aparte de `useAcademySkillScores` porque responde otra pregunta --qué
 *  cambió, no qué entrenar-- y porque la ventana la elige el usuario con su
 *  propio selector. */
export const useAcademyComparativa = (params: {
  ventana: string;
  soonMaxDays: number;
  weightBase: number;
  trainableMethod: string;
  trainable: Record<string, number>;
  trainableWeight?: number | null;
}) =>
  useQuery({
    queryKey: ["academy-comparativa", TEAM_ID, params],
    queryFn: () => api.academyComparativa(TEAM_ID, params),
    // Igual que los puntajes: al mover un mando se conserva lo anterior en
    // vez de parpadear a vacío.
    placeholderData: (previous) => previous,
  });
