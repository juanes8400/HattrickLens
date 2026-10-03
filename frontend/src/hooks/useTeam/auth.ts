/** Hooks de auth.
 *
 *  Sale de partir `hooks/useTeam.ts`, 601 lineas que abrian 26 de las 31
 *  pantallas. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../hooks/useTeam"` sigue valiendo igual.
 */
import { useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";

export const useSessionProfile = () =>
  useQuery({
    queryKey: ["session-profile"],
    queryFn: api.sessionProfile,
    staleTime: 5 * 60_000,
  });
