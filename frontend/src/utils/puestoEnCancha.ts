/**
 * Dónde cae en la pantalla cada puesto de una alineación de Hattrick.
 *
 * Los códigos son los de `matchlineup` normalizados (RoleID − 99 de CHPP):
 *
 *    1 portero
 *    2 lateral derecho      3 central derecho    4 central del medio
 *    5 central izquierdo    6 lateral izquierdo
 *    7 extremo derecho      8 interior derecho   9 interior del medio
 *   10 interior izquierdo  11 extremo izquierdo
 *   12 delantero derecho   13 delantero del medio  14 delantero izquierdo
 *
 * EL LADO, BIEN PUESTO EN LAS DOS ORIENTACIONES (2026-11-22, pedido del
 * usuario: «saber el lado exacto es muy importante»). La derecha de un equipo
 * depende de cómo se le mire:
 *
 *   · Portero ARRIBA: el equipo ataca hacia abajo, hacia quien mira, y se le
 *     ve DE FRENTE. Su derecha queda a la IZQUIERDA de la pantalla, igual que
 *     la mano derecha de alguien que está de cara.
 *   · Portero ABAJO: ataca hacia arriba, alejándose, y se le ve POR LA
 *     ESPALDA. Su derecha queda a la DERECHA de la pantalla.
 *
 * Hasta hoy sólo se daban la vuelta las filas, así que con el portero abajo la
 * cancha salía en espejo: el lateral derecho seguía a la izquierda.
 */

/** Línea (0 delanteros … 3 portero) y columna (1-5, de derecha a izquierda
 *  del propio equipo) de cada puesto de campo; `null` si no es de campo. */
function casillaDelPuesto(
  codigo: number,
): { linea: number; lado: number } | null {
  if (codigo === 1) return { linea: 3, lado: 3 };
  if (codigo >= 2 && codigo <= 6) return { linea: 2, lado: codigo - 1 };
  if (codigo >= 7 && codigo <= 11) return { linea: 1, lado: codigo - 6 };
  if (codigo >= 12 && codigo <= 14) return { linea: 0, lado: codigo - 10 };
  return null;
}

/** Fila (1-4, de arriba abajo) y columna (1-5, de izquierda a derecha DE LA
 *  PANTALLA) donde se pinta un puesto, según la orientación elegida. */
export function puestoEnPantalla(
  codigo: number,
  porteroArriba: boolean,
): { fila: number; columna: number } | null {
  const casilla = casillaDelPuesto(codigo);
  if (!casilla) return null;
  return porteroArriba
    ? // De frente: el portero en la fila de arriba y la derecha del equipo
      // a la izquierda de la pantalla.
      { fila: 4 - casilla.linea, columna: casilla.lado }
    : // Por la espalda: el portero abajo y la derecha del equipo a la
      // derecha de la pantalla.
      { fila: casilla.linea + 1, columna: 6 - casilla.lado };
}
