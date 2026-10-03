/** Hooks de economia.
 *
 *  Sale de partir `hooks/useTeam.ts`, 601 lineas que abrian 26 de las 31
 *  pantallas. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../hooks/useTeam"` sigue valiendo igual.
 */
import { useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";
import { TEAM_ID } from "./nucleo";

/** `conSeries = false` se salta la proyección por series de tiempo, que es lo
 *  más caro de la consulta: para quien sólo enseña la estructural. */
export const useEconomy = (horizonWeeks = 52, conSeries = true) =>
  useQuery({
    queryKey: ["economy", TEAM_ID, horizonWeeks, conSeries],
    queryFn: () => api.economy(TEAM_ID, horizonWeeks, conSeries),
  });
