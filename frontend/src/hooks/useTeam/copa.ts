/** Hooks de copa.
 *
 *  Sale de partir `hooks/useTeam.ts`, 601 lineas que abrian 26 de las 31
 *  pantallas. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../hooks/useTeam"` sigue valiendo igual.
 */
import { useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";
import type { Cup, PitchZoneMethod } from "../../services/api";
import { TEAM_ID, soloSiEsElMismo } from "./nucleo";

export const useCup = (
  pitchZoneMethodOwn: PitchZoneMethod = "submitted",
  pitchZoneMethodRival: PitchZoneMethod = "average",
) =>
  useQuery({
    queryKey: ["cup", TEAM_ID, pitchZoneMethodOwn, pitchZoneMethodRival],
    queryFn: () => api.cup(TEAM_ID, pitchZoneMethodOwn, pitchZoneMethodRival),
    // Mover un selector no cambia de sujeto: la pantalla no se vacía mientras
    // se rehace la cuenta. El equipo sí lo es.
    placeholderData: soloSiEsElMismo<Cup>(1, TEAM_ID),
  });
