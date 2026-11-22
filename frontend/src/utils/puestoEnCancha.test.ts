import { describe, expect, it } from "vitest";
import { puestoEnPantalla } from "./puestoEnCancha";

/**
 * Los catorce puestos, en las dos orientaciones, contra una tabla ESCRITA A
 * MANO desde la definición de Hattrick y no desde la fórmula (2026-11-22,
 * pedido del usuario: «verifica dos, tres, cuatro veces que la información sea
 * correcta»). «izq.» y «der.» son de LA PANTALLA.
 *
 *   Portero arriba (de frente)            Portero abajo (por la espalda)
 *   fila 1: portero                       fila 1: delanteros
 *   fila 2: LD  CD  CM  CI  LI            fila 2: EI  II  IM  ID  ED
 *   fila 3: ED  ID  IM  II  EI            fila 3: LI  CI  CM  CD  LD
 *   fila 4: DD  DM  DI (cols 2-4)         fila 4: portero
 */
const DE_FRENTE: Record<number, [number, number]> = {
  1: [1, 3], // portero, arriba en el centro
  2: [2, 1], // lateral derecho → a la izquierda de la pantalla
  3: [2, 2],
  4: [2, 3],
  5: [2, 4],
  6: [2, 5], // lateral izquierdo → a la derecha de la pantalla
  7: [3, 1], // extremo derecho → izquierda de la pantalla
  8: [3, 2],
  9: [3, 3],
  10: [3, 4],
  11: [3, 5], // extremo izquierdo → derecha de la pantalla
  12: [4, 2], // delantero derecho
  13: [4, 3],
  14: [4, 4], // delantero izquierdo
};

const POR_LA_ESPALDA: Record<number, [number, number]> = {
  1: [4, 3], // portero, abajo en el centro
  2: [3, 5], // lateral derecho → a la DERECHA de la pantalla
  3: [3, 4],
  4: [3, 3],
  5: [3, 2],
  6: [3, 1], // lateral izquierdo → a la izquierda de la pantalla
  7: [2, 5], // extremo derecho → derecha de la pantalla
  8: [2, 4],
  9: [2, 3],
  10: [2, 2],
  11: [2, 1], // extremo izquierdo → izquierda de la pantalla
  12: [1, 4], // delantero derecho
  13: [1, 3],
  14: [1, 2], // delantero izquierdo
};

describe("dónde cae cada puesto", () => {
  it.each(Object.entries(DE_FRENTE))(
    "de frente (portero arriba), el puesto %s",
    (codigo, [fila, columna]) => {
      expect(puestoEnPantalla(Number(codigo), true)).toEqual({ fila, columna });
    },
  );

  it.each(Object.entries(POR_LA_ESPALDA))(
    "por la espalda (portero abajo), el puesto %s",
    (codigo, [fila, columna]) => {
      expect(puestoEnPantalla(Number(codigo), false)).toEqual({
        fila,
        columna,
      });
    },
  );

  it("girar la cancha es un giro de media vuelta, no un espejo", () => {
    // Media vuelta: cada puesto va al punto opuesto. Un espejo dejaría la
    // columna igual, que es el fallo que había.
    for (let codigo = 1; codigo <= 14; codigo++) {
      const arriba = puestoEnPantalla(codigo, true)!;
      const abajo = puestoEnPantalla(codigo, false)!;
      expect(arriba.fila + abajo.fila).toBe(5);
      expect(arriba.columna + abajo.columna).toBe(6);
    }
  });

  it("lo que no es de campo no se pinta", () => {
    expect(puestoEnPantalla(0, true)).toBeNull();
    expect(puestoEnPantalla(17, false)).toBeNull();
  });
});
