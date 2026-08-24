import { describe, expect, it } from "vitest";

import { lecturaDeNivel } from "./skillLevels";

describe("cómo se lee una habilidad juvenil", () => {
  it("sabiendo nivel y techo, la barra mide el nivel", () => {
    const r = lecturaDeNivel(5, 8, false);
    expect(r.palabra).toBe("insuficiente");
    expect(r.numeros).toBe("5/8");
    expect(r.ancho).toBeCloseTo(62.5);
    expect(r.crece).toBe(true);
  });

  it("sabiendo sólo el techo, la palabra es la del techo", () => {
    expect(lecturaDeNivel(null, 4, false)).toMatchObject({
      palabra: "débil",
      numeros: "?/4",
    });
  });

  it("sabiendo sólo el nivel, el techo queda en interrogante", () => {
    expect(lecturaDeNivel(5, null, false).numeros).toBe("5/?");
  });

  it("un 4 que ya no sube es un 4, no una barra llena", () => {
    const r = lecturaDeNivel(4, 4, true);
    expect(r.numeros).toBe("4/4");
    expect(r.ancho).toBeCloseTo(50);
    expect(r.crece).toBe(false);
  });

  it("topada con el nivel oculto: candado, pero no un cero inventado", () => {
    // CHPP publica `IsMaxReached` aunque el nivel siga sin revelar. Decir
    // «nulo 0/0» ahí seria afirmar algo que nadie ha dicho.
    const r = lecturaDeNivel(null, null, true);
    expect(r.palabra).toBe("desconocido");
    expect(r.numeros).toBe("");
    expect(r.ancho).toBe(0);
    expect(r.crece).toBe(false);
  });

  it("sin nada revelado, no hay número que enseñar", () => {
    expect(lecturaDeNivel(null, null, false)).toMatchObject({
      palabra: "desconocido",
      numeros: "",
    });
  });
});
