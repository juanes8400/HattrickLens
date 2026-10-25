/** Hooks de alineacion.
 *
 *  Sale de partir `hooks/useTeam.ts`, 601 lineas que abrian 26 de las 31
 *  pantallas. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../hooks/useTeam"` sigue valiendo igual.
 */
import { useQuery } from "@tanstack/react-query";
import { api } from "../../services/api";
import { TEAM_ID } from "./nucleo";

export const useLineup = (
  formation?: string,
  centralDefenders?: number,
  innerMidfielders?: number,
  orders?: Record<number, string>,
  exclude?: number[],
  enabled = true,
  /** Pedir el aviso del entrenamiento. Va en la clave: sin él, encenderlo no
   *  pedía nada y la pantalla seguía con lo de antes en caché. */
  entrenando = false,
) =>
  useQuery({
    queryKey: [
      "lineup",
      TEAM_ID,
      formation,
      centralDefenders ?? null,
      innerMidfielders ?? null,
      orders ?? null,
      // Ordenados en la CLAVE, no en la petición: sacar a A y luego a B es el
      // mismo once que sacar a B y luego a A, y sin ordenar serían dos
      // entradas distintas de caché para el mismo resultado.
      [...(exclude ?? [])].sort((a, b) => a - b).join(",") || null,
      entrenando,
    ],
    queryFn: () =>
      api.lineup(
        TEAM_ID,
        formation,
        centralDefenders,
        innerMidfielders,
        orders,
        exclude,
        entrenando,
      ),
    // Alineación usa este interruptor después de leer la plantilla: si hay
    // menos de once disponibles no manda al servidor un problema que no se
    // puede resolver. El resto de consumidores conserva el valor por defecto.
    enabled,
    // Mover un reparto no cambia la plantilla: se conserva el once anterior
    // mientras llega el nuevo, en vez de vaciar la pantalla entera.
    placeholderData: (previous) => previous,
  });
