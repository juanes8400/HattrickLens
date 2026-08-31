/** Qué debe enseñar el panel de alertas del Panel.
 *
 *  Vive aquí y no dentro de la página para poder probarlo sin arrastrar la
 *  aplicación entera --`useTeam` lee `localStorage` al cargarse y en el
 *  entorno de pruebas eso no existe--.
 *
 *  Cero alertas y cero respuesta se veían igual: el panel recibía
 *  `data ?? []` y no sabía si la petición había fallado, así que con las
 *  alertas caídas afirmaba «Nada requiere tu atención» a alguien con un
 *  jugador lesionado y la caja en déficit (2026-08-31). Es el mismo principio
 *  que el proyecto ya aplica a los salarios y a los techos juveniles: un cero
 *  que en realidad es ignorancia hay que declararlo.
 */
export function estadoDeAlertas({
  loading,
  failed,
  cuantas,
}: {
  loading: boolean;
  failed: boolean;
  cuantas: number;
}): "cargando" | "fallo" | "vacio" | "lista" {
  if (loading) return "cargando";
  // El fallo manda sobre el vacío: si no sabemos, no se puede tranquilizar.
  if (failed) return "fallo";
  return cuantas === 0 ? "vacio" : "lista";
}
