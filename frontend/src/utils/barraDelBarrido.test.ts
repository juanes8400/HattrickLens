import { describe, expect, it } from "vitest";
import {
  anchoDeLaMarca,
  anchuraDelFrente,
  motivosEnPalabras,
  sitioDeLaMarca,
} from "./barraDelBarrido";

const relleno = (
  mapa: { total: number; done: number[]; front: number } | null,
) => ({
  mapa,
  hechos: 5,
  total: 100,
  quedan: 95,
});

describe("la barra del barrido de comisiones", () => {
  it("mide el bloque con el frente, no con cuántos se atendieron", () => {
    // Once atendidos pero sólo tres seguidos desde la izquierda: el bloque
    // vale tres. Es lo que distingue el avance del picoteo.
    expect(
      anchuraDelFrente(
        relleno({ total: 100, done: [0, 1, 2, 40, 61], front: 3 }),
      ),
    ).toBe(3);
  });

  it("deja el bloque a cero cuando el azar aún no ha tocado la cabeza", () => {
    expect(
      anchuraDelFrente(relleno({ total: 100, done: [40], front: 0 })),
    ).toBe(0);
  });

  it("cae al porcentaje de siempre mientras no llegue el mapa", () => {
    expect(anchuraDelFrente(relleno(null))).toBe(5);
  });

  it("llena la barra cuando no queda nadie", () => {
    expect(anchuraDelFrente({ ...relleno(null), quedan: 0 })).toBe(100);
  });

  it("no se pasa del 100 aunque el mapa venga raro", () => {
    expect(anchuraDelFrente(relleno({ total: 10, done: [], front: 99 }))).toBe(
      100,
    );
  });

  it("un eje vacío no divide por cero", () => {
    expect(
      Number.isFinite(
        anchuraDelFrente(relleno({ total: 0, done: [], front: 0 })),
      ),
    ).toBe(true);
  });

  it("coloca las marcas dentro de la barra, incluida la última", () => {
    expect(sitioDeLaMarca(0, 191)).toBe(0);
    expect(sitioDeLaMarca(95, 190)).toBe(50);
    // La última casilla acaba justo en el borde, sin salirse.
    const total = 191;
    expect(
      sitioDeLaMarca(total - 1, total) + anchoDeLaMarca(total),
    ).toBeCloseTo(100);
  });

  it("una marca mide exactamente lo mismo que un paso del frente", () => {
    // Estaba clavada a 3 px mientras un paso del frente medía 7,19 px con 176
    // en cola: un salto al azar se veía a menos de la mitad de tamaño que un
    // avance, aunque los dos son un jugador atendido.
    const total = 176;
    const unPaso = anchuraDelFrente(relleno({ total, done: [0], front: 1 }));
    expect(anchoDeLaMarca(total)).toBeCloseTo(unPaso);
  });

  it("siguen midiendo igual con la cola muy larga", () => {
    // Aqui es donde fallaba: un suelo de 2 px hacia que con 900 en cola la
    // marca (2 px) fuera casi el doble que un paso del frente (1,05 px).
    for (const total of [20, 176, 458, 900, 5000]) {
      const unPaso = anchuraDelFrente(relleno({ total, done: [0], front: 1 }));
      expect(anchoDeLaMarca(total)).toBeCloseTo(unPaso, 10);
    }
  });

  it("el frente de N casillas mide N marcas", () => {
    const total = 176;
    expect(
      anchuraDelFrente(relleno({ total, done: [0, 1, 2], front: 3 })),
    ).toBeCloseTo(anchoDeLaMarca(total) * 3);
  });

  it("un eje vacío no da un ancho absurdo", () => {
    expect(anchoDeLaMarca(0)).toBe(0);
    expect(sitioDeLaMarca(5, 0)).toBe(0);
  });
});

describe("los motivos de cierre en palabras", () => {
  it("los ordena de más a menos y concuerda el plural", () => {
    expect(motivosEnPalabras({ revendido: 2, despedido: 1 })).toBe(
      "2 revendidos, 1 despedido",
    );
  });

  it("dice en castellano qué significa cada motivo", () => {
    expect(motivosEnPalabras({ sin_comprador: 1, entrenador: 3 })).toBe(
      "3 ahora son entrenadores, 1 se fue sin comprador",
    );
  });

  it("ignora los motivos en cero", () => {
    expect(motivosEnPalabras({ revendido: 1, despedido: 0 })).toBe(
      "1 revendido",
    );
  });

  it("sin cierres devuelve cadena vacía", () => {
    expect(motivosEnPalabras({})).toBe("");
  });

  it("un motivo que no conoce no rompe la frase", () => {
    expect(motivosEnPalabras({ loquesea: 2 })).toBe("2 loquesea");
  });
});
