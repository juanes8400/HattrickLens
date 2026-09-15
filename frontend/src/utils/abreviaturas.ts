import i18n from "../i18n";

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
 *
 * Traducción (2026-09-15): cada código tiene su versión en cada idioma
 * (`abrev.*` y `abrev.largo.*`). Las tablas piden el código con
 * `abreviatura(clave)` y `nombreLargo` lo reconoce en el idioma que esté puesto.
 */
const ABREVIATURAS = {
  // Las siete habilidades del juego.
  keeper: ["PO", "Portería"],
  defending: ["DE", "Defensa"],
  playmaking: ["JU", "Jugadas"],
  winger: ["LA", "Lateral"],
  passing: ["PA", "Pases"],
  scoring: ["AN", "Anotación"],
  set_pieces: ["BP", "Balón parado"],
  // Lo que no es habilidad pero se mide igual.
  form: ["FO", "Forma"],
  experience: ["EX", "Experiencia"],
  stamina: ["RE", "Resistencia"],
  loyalty: ["FI", "Fidelidad"],
  leadership: ["LI", "Liderazgo"],
} as const;

export type ClaveDeAbreviatura = keyof typeof ABREVIATURAS;

/** El código corto de una habilidad o medida, en el idioma de la app. */
export function abreviatura(clave: ClaveDeAbreviatura): string {
  return i18n.t(`abrev.${clave}`, ABREVIATURAS[clave][0]);
}

/** El nombre largo de una cabecera, o `undefined` si no es una abreviatura. */
export function nombreLargo(header: string): string | undefined {
  const texto = header.trim();
  const clave = (Object.keys(ABREVIATURAS) as ClaveDeAbreviatura[]).find(
    (k) => abreviatura(k) === texto,
  );
  return clave
    ? i18n.t(`abrev.largo.${clave}`, ABREVIATURAS[clave][1])
    : undefined;
}
