/** Las etapas de carrera, con su nombre en pantalla. Una sola lista para la
 *  ficha del jugador (que deja confirmarlas a mano) y para Clases de Jugador
 *  (2026-11-16): antes eran dos copias de los mismos nombres. */
import { tx } from "../i18n/tx";
import type { EtapaDeCarrera } from "../services/api";

export const ETAPAS_DE_CARRERA: {
  clave: EtapaDeCarrera;
  nombre: () => string;
  /** Se puede elegir a mano en la ficha. «Sin historial» no: es un hecho. */
  confirmable: boolean;
}[] = [
  {
    clave: "promesa",
    nombre: () => tx("Promesa en desarrollo"),
    confirmable: true,
  },
  { clave: "pico", nombre: () => tx("En su pico"), confirmable: true },
  {
    clave: "rotacion",
    nombre: () => tx("Pieza de rotación"),
    confirmable: true,
  },
  {
    clave: "veterano",
    nombre: () => tx("Veterano estable"),
    confirmable: true,
  },
  { clave: "declive", nombre: () => tx("En declive"), confirmable: true },
  {
    clave: "sin_historial",
    nombre: () => tx("Sin historial suficiente"),
    confirmable: false,
  },
];

export const nombreDeEtapa = (clave: string): string =>
  ETAPAS_DE_CARRERA.find((e) => e.clave === clave)?.nombre() ?? clave;
