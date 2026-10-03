/** Alertas.
 *
 *  Sale de partir `services/api.ts`, que tenia 4147 lineas y se leia entero
 *  en cada cambio del frontend. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../services/api"` sigue valiendo igual.
 */
import { request } from "./nucleo";

export interface Insight {
  key: string;
  severity: "info" | "opportunity" | "warning" | "danger";
  title: string;
  detail: string;
  action: string;
  module: string;
  evidence: Record<string, unknown>;
}

/**
 * Una alerta que el usuario mandó al buzón. Conserva el texto tal como estaba
 * cuando la archivó, así que se sigue leyendo aunque la condición ya no se
 * cumpla; `stillActive` distingue justamente esos dos casos.
 */
export interface ArchivedInsight extends Insight {
  dismissedAt: string;
  stillActive: boolean;
}

export const apiAlertas = {
  insights: (teamId: number) => request<Insight[]>(`/teams/${teamId}/insights`),
  archivedInsights: (teamId: number) =>
    request<ArchivedInsight[]>(`/teams/${teamId}/insights/archived`),
  archiveInsight: (teamId: number, key: string) =>
    request<{ key: string; archived: boolean }>(
      `/teams/${teamId}/insights/${encodeURIComponent(key)}/archive`,
      { method: "POST" },
    ),
  restoreInsight: (teamId: number, key: string) =>
    request<{ key: string; archived: boolean }>(
      `/teams/${teamId}/insights/${encodeURIComponent(key)}/archive`,
      { method: "DELETE" },
    ),
};
