/** Qué clasificación propia se está mirando. La comparten «Mis
 *  clasificaciones» y «Personalizar»: la que creas en una es la que ves al
 *  pasar a la otra. */
import { usePersistido } from "../../hooks/usePersistido";

export const useClasificacionPropiaElegida = () =>
  usePersistido<number | null>("clasificacion.propia-elegida", null);
