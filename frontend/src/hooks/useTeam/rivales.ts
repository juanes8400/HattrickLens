/** Hooks de rivales.
 *
 *  Sale de partir `hooks/useTeam.ts`, 601 lineas que abrian 26 de las 31
 *  pantallas. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../hooks/useTeam"` sigue valiendo igual.
 */
import { useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";
import type { PitchZoneMethod } from "../../services/api";
import { TEAM_ID, soloSiEsElMismo } from "./nucleo";

export const useRivalScouting = (
  rivalHtTeamId: number | null,
  logTsi: boolean,
  top11: boolean,
  includeCompetitive = true,
  includeFriendlies = false,
  pitchZoneMethodOwn: PitchZoneMethod = "submitted",
  pitchZoneMethodRival: PitchZoneMethod = "average",
) =>
  useQuery({
    queryKey: [
      "rival-scouting",
      TEAM_ID,
      rivalHtTeamId,
      logTsi,
      top11,
      includeCompetitive,
      includeFriendlies,
      pitchZoneMethodOwn,
      pitchZoneMethodRival,
    ],
    queryFn: () =>
      api.rivalScouting(
        TEAM_ID,
        rivalHtTeamId as number,
        logTsi,
        top11,
        includeCompetitive,
        includeFriendlies,
        pitchZoneMethodOwn,
        pitchZoneMethodRival,
      ),
    enabled: rivalHtTeamId != null,
    // Los mandos de vista --método de zonas, TSI logarítmico, once/plantilla--
    // no piden datos nuevos, así que la ficha no debe desaparecer mientras se
    // recalculan. Cambiar de RIVAL sí es otro sujeto: ahí no se conserva nada.
    placeholderData: soloSiEsElMismo(2, rivalHtTeamId),
  });
