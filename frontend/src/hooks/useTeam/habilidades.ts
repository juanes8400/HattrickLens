/** Hooks de habilidades.
 *
 *  Sale de partir `hooks/useTeam.ts`, 601 lineas que abrian 26 de las 31
 *  pantallas. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../hooks/useTeam"` sigue valiendo igual.
 */
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";
import { TEAM_ID } from "./nucleo";

export const useSkills = (
  formation?: string,
  centralDefenders?: number,
  innerMidfielders?: number,
) =>
  useQuery({
    queryKey: [
      "skills",
      TEAM_ID,
      formation ?? null,
      centralDefenders ?? null,
      innerMidfielders ?? null,
    ],
    queryFn: () =>
      api.skills(TEAM_ID, formation, centralDefenders, innerMidfielders),
    // Al cambiar la formación se sigue viendo la anterior mientras llega la
    // nueva, en vez de vaciar la pantalla entera.
    placeholderData: keepPreviousData,
  });
