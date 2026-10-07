/** Hooks de sincronizacion.
 *
 *  Sale de partir `hooks/useTeam.ts`, 601 lineas que abrian 26 de las 31
 *  pantallas. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../hooks/useTeam"` sigue valiendo igual.
 */
import { useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";
import { TEAM_ID, soloSiEsElMismo } from "./nucleo";

export const useSyncChanges = (syncId?: number | null) =>
  useQuery({
    queryKey: ["sync-changes", TEAM_ID, syncId ?? null],
    queryFn: () => api.syncChanges(TEAM_ID, syncId),
    // Al cambiar de fecha se mantiene la tabla anterior mientras llega la
    // nueva, en vez de parpadear a vacío en cada selección.
    placeholderData: soloSiEsElMismo(2, syncId ?? null),
  });

export const useChangesHistory = (
  playerId?: number | null,
  weeks?: number,
  enabled = true,
) =>
  useQuery({
    queryKey: ["changes-history", TEAM_ID, playerId ?? null, weeks ?? null],
    queryFn: () => api.changesHistory(TEAM_ID, playerId, weeks),
    enabled,
    // Al cambiar de ventana se conserva la tabla anterior mientras llega la
    // nueva, en vez de parpadear a vacío en cada clic.
    placeholderData: soloSiEsElMismo(2, playerId ?? null),
  });
