/** El equipo activo y los ayudantes que comparten los demas hooks.
 *
 *  Sale de partir `hooks/useTeam.ts`, 601 lineas que abrian 26 de las 31
 *  pantallas. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../hooks/useTeam"` sigue valiendo igual.
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";

/** Conserva la vista anterior SÓLO si el sujeto no ha cambiado.
 *
 *  `placeholderData: (previous) => previous` a secas conserva los datos ante
 *  CUALQUIER cambio de clave. Para un mando de vista --la formación, el TSI
 *  logarítmico, el reparto de zonas-- eso es lo que se quiere: no vaciar la
 *  pantalla mientras se recalcula algo que no pide datos nuevos.
 *
 *  Pero cuando la clave lleva una IDENTIDAD --qué rival, qué jugador, qué
 *  sincronización-- conservar es enseñar los datos de otro. El 2026-08-31 se
 *  comprobó en vivo: al abrir un rival distinto, la ficha seguía mostrando el
 *  informe del anterior, con su nombre en el título, durante los ~9 segundos
 *  que tarda en llegar el nuevo. Nada avisaba de que aquello era otro equipo.
 *
 *  `indice` es la posición de esa identidad dentro de `queryKey`.
 */
export const soloSiEsElMismo =
  <T>(indice: number, sujeto: unknown) =>
  (previous: T | undefined, anterior?: { queryKey: readonly unknown[] }) =>
    anterior && anterior.queryKey[indice] === sujeto ? previous : undefined;

/**
 * El equipo activo. Antes de conectar con Hattrick no hay ninguno real, así
 * que se cae al 1 sembrado en desarrollo; tras el callback OAuth,
 * `ConnectedPage` guarda el id real del equipo del usuario aquí y recarga,
 * con lo que este módulo se reevalúa con el valor correcto.
 *
 * Single team por ahora; multi-club por usuario es una vista de selección a
 * futuro (`user_teams`), no necesaria mientras cada cuenta conectada gestiona
 * un solo club.
 */
const TEAM_ID_STORAGE_KEY = "htlens_team_id";

export const TEAM_ID = Number(localStorage.getItem(TEAM_ID_STORAGE_KEY)) || 1;

/** `TEAM_ID` conserva el fallback de desarrollo para no romper las consultas
 * existentes, pero la interfaz no debe intentar usarlas hasta que OAuth haya
 * elegido un equipo real. */
export function hasActiveTeam(): boolean {
  const teamId = Number(localStorage.getItem(TEAM_ID_STORAGE_KEY));
  return Number.isInteger(teamId) && teamId > 0;
}

export function setActiveTeamId(teamId: number): void {
  localStorage.setItem(TEAM_ID_STORAGE_KEY, String(teamId));
}

export function clearActiveTeamId(): void {
  localStorage.removeItem(TEAM_ID_STORAGE_KEY);
}

/** Archivar y restaurar tocan las dos listas a la vez, una alerta que sale de
 *  la activa entra en el buzón y viceversa, así que ambas se invalidan
 *  juntas. Si solo se refrescara una, la pantalla mostraría la misma alerta en
 *  los dos sitios hasta el siguiente refresco.
 *
 *  La fila se quita AL INSTANTE, sin esperar al servidor. Medido el
 *  2026-08-31: entre el clic y la desaparición pasaban 2,2 segundos --el POST
 *  más dos refrescos, y las alertas se derivan de nuevo en cada petición--,
 *  y en todo ese rato la lista entera se quedaba inerte. Un segundo es el
 *  límite para que no se rompa el hilo de lo que estabas haciendo; con dos y
 *  pico uno vuelve a pulsar creyendo que no ha funcionado.
 *
 *  Si el servidor falla se deshace y la alerta vuelve a su sitio: es la
 *  contrapartida honesta de adelantarse a la respuesta. */
export function useInsightArchiveMutation(
  fn: (teamId: number, key: string) => Promise<unknown>,
) {
  const queryClient = useQueryClient();
  const activas = ["insights", TEAM_ID] as const;
  const buzon = ["insights-archived", TEAM_ID] as const;

  return useMutation({
    mutationFn: (key: string) => fn(TEAM_ID, key),
    onMutate: async (key: string) => {
      // Se paran los refrescos en vuelo: si uno aterriza después de quitar la
      // fila, la repone y parece que el clic no hizo nada.
      await Promise.all([
        queryClient.cancelQueries({ queryKey: activas }),
        queryClient.cancelQueries({ queryKey: buzon }),
      ]);
      const previoActivas =
        queryClient.getQueryData<{ key: string }[]>(activas);
      const previoBuzon = queryClient.getQueryData<{ key: string }[]>(buzon);
      const quitar = (lista?: { key: string }[]) =>
        lista ? lista.filter((i) => i.key !== key) : lista;
      queryClient.setQueryData(activas, quitar(previoActivas));
      queryClient.setQueryData(buzon, quitar(previoBuzon));
      return { previoActivas, previoBuzon };
    },
    onError: (_e, _key, contexto) => {
      if (contexto?.previoActivas)
        queryClient.setQueryData(activas, contexto.previoActivas);
      if (contexto?.previoBuzon)
        queryClient.setQueryData(buzon, contexto.previoBuzon);
    },
    // Pase lo que pase, la verdad la tiene el servidor.
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: activas });
      queryClient.invalidateQueries({ queryKey: buzon });
    },
  });
}
