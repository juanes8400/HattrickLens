/**
 * Qué significa cada abreviatura de columna.
 *
 * Las tablas de plantilla usan códigos de dos letras para que quepan doce
 * habilidades sin scroll horizontal. El precio es que el usuario tiene que
 * acordarse de doce claves, y las columnas no venían con nada que las
 * explicara: ni título, ni etiqueta accesible, ni leyenda. Reconocer en vez
 * de recordar (2026-08-31).
 *
 * Vive aparte de las páginas a propósito: `DataTable` lo consulta solo, así
 * que cualquier tabla que use estos códigos queda explicada sin tocarla, y
 * una columna nueva sólo tiene que añadir su entrada aquí.
 */
export const NOMBRE_DE_ABREVIATURA: Record<string, string> = {
  // Las siete habilidades del juego.
  PO: "Portería",
  DE: "Defensa",
  JU: "Jugadas",
  LA: "Lateral",
  PA: "Pases",
  AN: "Anotación",
  BP: "Balón parado",
  // Lo que no es habilidad pero se mide igual.
  FO: "Forma",
  EX: "Experiencia",
  CO: "Condición",
  FI: "Fidelidad",
  LI: "Liderazgo",
};

/** El nombre largo de una cabecera, o `undefined` si no es una abreviatura. */
export function nombreLargo(header: string): string | undefined {
  return NOMBRE_DE_ABREVIATURA[header.trim()];
}
