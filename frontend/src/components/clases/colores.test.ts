import { describe, expect, it } from "vitest";
import { colocarEtiquetas } from "./colores";

/** Las etiquetas del cuadrante de Potencial (2026-11-16). */
describe("colocarEtiquetas", () => {
  const limites = { izquierda: 0, derecha: 1000 };

  it("pone la etiqueta a la derecha del punto cuando hay sitio", () => {
    const [e] = colocarEtiquetas([{ x: 100, y: 100, texto: "Ece" }], limites);
    expect(e).toEqual({ x: 110, y: 104, anchor: "start" });
  });

  it("dos puntos pegados no reciben la misma posición", () => {
    const [a, b] = colocarEtiquetas(
      [
        { x: 500, y: 200, texto: "Schönhueb" },
        { x: 505, y: 204, texto: "Klingler" },
      ],
      limites,
    );
    expect(a).not.toEqual(b);
  });

  it("junto al borde derecho la etiqueta se va a la izquierda", () => {
    const [e] = colocarEtiquetas([{ x: 990, y: 100, texto: "Đinh" }], limites);
    expect(e?.anchor).toBe("end");
  });
});
