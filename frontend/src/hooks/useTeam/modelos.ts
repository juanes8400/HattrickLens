/** Hooks de modelos.
 *
 *  Sale de partir `hooks/useTeam.ts`, 601 lineas que abrian 26 de las 31
 *  pantallas. La fachada `index.ts` lo reexporta, asi que
 *  `import { ... } from "../hooks/useTeam"` sigue valiendo igual.
 */
import { useQuery } from "@tanstack/react-query";
import i18n from "../../i18n";
import { api } from "../../services/api";
import { TEAM_ID } from "./nucleo";

/** El catálogo de cálculos. Describe los motores, que son iguales para
 *  todos, así que no lleva equipo ni se invalida al sincronizar.
 *
 *  SÍ LLEVA EL IDIOMA (2026-11-08), y sin eso Transparencia se quedaba en
 *  español para siempre. El catálogo lo escribe el servidor en español y lo
 *  traduce AL SALIR, según la cabecera `Accept-Language` de cada petición
 *  --ver `app/i18n/traductor.py`--. O sea que la respuesta DEPENDE del idioma,
 *  y una clave sin idioma dentro dice lo contrario.
 *
 *  Lo que pasaba, y se vio en pantalla: el cambio de idioma es asíncrono
 *  --hay que cargar su diccionario antes de activarlo-- así que la primera
 *  petición sale con el idioma viejo. Con esta clave eso ya no importa: al
 *  activarse el nuevo, la clave cambia y se vuelve a pedir. Antes no, porque
 *  este catálogo es el único que nunca se invalida, y encima la caché guardada
 *  lo rehidrataba traducido al idioma anterior.
 *
 *  No multiplica el gasto: son cinco idiomas como mucho, una petición cada
 *  uno, y el catálogo no cambia entre sincronizaciones. */
export const useCalculos = () =>
  useQuery({
    queryKey: ["calculos", i18n.language],
    queryFn: api.calculos,
  });

export const useExperienceModel = () =>
  useQuery({
    queryKey: ["experience-model", TEAM_ID],
    queryFn: () => api.experienceModel(TEAM_ID),
  });

export const useLoyaltyModel = () =>
  useQuery({
    queryKey: ["loyalty-model", TEAM_ID],
    queryFn: () => api.loyaltyModel(TEAM_ID),
  });
