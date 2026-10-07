/** Hooks de liga.
 *
 *  Sale de partir `hooks/useTeam.ts`, 601 lineas que abrian 26 de las 31
 *  pantallas. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../hooks/useTeam"` sigue valiendo igual.
 */
import { useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";
import type {
  Formation,
  League,
  LeaguePitchZoneMethod,
} from "../../services/api";
import { TEAM_ID, soloSiEsElMismo } from "./nucleo";

/** Diez mil. Se probó a subirlo: con cincuenta mil los números se quedan más
 *  quietos --en el peor caso, el 4º y el 5º puesto salen al 49,1 % y al 48,9 %
 *  y con diez mil se cruzan entre dos cargas-- pero la pantalla pasaba de dos
 *  segundos y no compensa. Por eso la frase de cambio no habla de «el suelo
 *  pasó de 5º a 4º», que es justo lo que ese cruce vuelve poco fiable. */
export const useLeague = (
  runs = 10_000,
  pitchZoneMethod: LeaguePitchZoneMethod = "average",
) =>
  useQuery({
    queryKey: ["league", TEAM_ID, runs, pitchZoneMethod],
    queryFn: () => api.league(TEAM_ID, runs, pitchZoneMethod),
    // Cambiar de resumen no cambia de sujeto --sigue siendo la misma serie--,
    // así que la pantalla no debe vaciarse mientras se rehacen las cuentas.
    // El equipo sí es identidad: si cambia, no se conserva nada.
    placeholderData: soloSiEsElMismo<League>(1, TEAM_ID),
  });

export const useLeagueTeamOfWeek = (
  scope: "week" | "season",
  formation: Formation,
  round?: number,
  centralDefenders?: number,
  innerMidfielders?: number,
) =>
  useQuery({
    queryKey: [
      "league-team-of-week",
      TEAM_ID,
      scope,
      formation,
      round,
      centralDefenders ?? null,
      innerMidfielders ?? null,
    ],
    queryFn: () =>
      api.leagueTeamOfWeek(
        TEAM_ID,
        scope,
        formation,
        round,
        centralDefenders,
        innerMidfielders,
      ),
    // Mover un reparto no cambia qué partidos se leen: se conserva el once
    // anterior mientras llega el nuevo en vez de vaciar el panel.
    placeholderData: (previous) => previous,
  });

// La comparativa de TSI de liga pide las plantillas de 7-8 rivales a CHPP
// carga sola al entrar a /league (2026-08-08: revertido el arranque
// colapsado del 2026-08-05). `enabled` queda disponible por si otro caller
// necesita retrasar el fetch, pero por defecto en `true`.
export const useLeagueComparison = (
  logTsi: boolean,
  top11: boolean,
  enabled = true,
  incluirCopa = false,
) =>
  useQuery({
    queryKey: ["league-comparison", TEAM_ID, logTsi, top11, incluirCopa],
    queryFn: () => api.leagueComparison(TEAM_ID, logTsi, top11, incluirCopa),
    enabled,
    // Los mandos de esta pantalla son post-proceso sobre los mismos XML: al
    // cambiarlos se conserva lo que ya está pintado mientras llega lo nuevo.
    // Sin esto la página entera se vaciaba y volvía, que es lo que se siente
    // como "tarda un montón" aunque la respuesta tarde medio segundo.
    placeholderData: (previous) => previous,
  });

/** Los sectores de cada equipo de la serie, para la flor del Dashboard. Sólo
 *  lee la base, así que es barato. */
export const useSectoresRecientes = () =>
  useQuery({
    queryKey: ["sectores-recientes", TEAM_ID],
    queryFn: () => api.sectoresRecientes(TEAM_ID),
  });
