/** Hooks de alertas.
 *
 *  Sale de partir `hooks/useTeam.ts`, 601 lineas que abrian 26 de las 31
 *  pantallas. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../hooks/useTeam"` sigue valiendo igual.
 */
import { useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";
import { TEAM_ID, useInsightArchiveMutation } from "./nucleo";

export const useInsights = () =>
  useQuery({
    queryKey: ["insights", TEAM_ID],
    queryFn: () => api.insights(TEAM_ID),
  });

export const useArchivedInsights = () =>
  useQuery({
    queryKey: ["insights-archived", TEAM_ID],
    queryFn: () => api.archivedInsights(TEAM_ID),
  });

export const useArchiveInsight = () =>
  useInsightArchiveMutation(api.archiveInsight);
export const useRestoreInsight = () =>
  useInsightArchiveMutation(api.restoreInsight);
