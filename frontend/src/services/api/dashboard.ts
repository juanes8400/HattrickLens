/** El panel de inicio.
 *
 *  Sale de partir `services/api.ts`, que tenia 4147 lineas y se leia entero
 *  en cada cambio del frontend. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../services/api"` sigue valiendo igual.
 */
import type { Dashboard } from "./comun";
import { request } from "./nucleo";

export const apiDashboard = {
  dashboard: (teamId: number) =>
    request<Dashboard>(`/teams/${teamId}/dashboard`),
};
