import { afterEach, describe, expect, it } from "vitest";

import i18n from "../i18n";
import { lecturaDeNivel, skillLevelLabel } from "./skillLevels";

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

  it("sabiendo sólo el nivel, el techo es al menos ese nivel", () => {
    // 2026-09-19: antes decía «5/?», y el interrogante escondía lo que sí se
    // sabe. Un techo nunca está por debajo del nivel de hoy.
    expect(lecturaDeNivel(5, null, false).numeros).toBe("5/≥5");
  });

  it("sin nivel y sin techo el interrogante sigue siendo lo honesto", () => {
    // Aquí no hay suelo que enseñar: no se sabe nada de esa habilidad.
    expect(lecturaDeNivel(null, null, false).numeros).toBe("");
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

/** Las 21 palabras tal cual estaban escritas a mano antes del glosario. */
const NIVELES_QUE_YA_SE_VEIAN = [
  "nulo",
  "desastroso",
  "horrible",
  "pobre",
  "débil",
  "insuficiente",
  "aceptable",
  "bueno",
  "excelente",
  "formidable",
  "destacado",
  "brillante",
  "magnífico",
  "clase mundial",
  "sobrenatural",
  "titánico",
  "extraterrestre",
  "mítico",
  "mágico",
  "utópico",
  "divino",
];

describe("skillLevelLabel con el glosario oficial (2026-09-15)", () => {
  afterEach(async () => {
    await i18n.changeLanguage("es");
  });

  it("en español dice exactamente lo que ya se veía", () => {
    expect(NIVELES_QUE_YA_SE_VEIAN.map((_, i) => skillLevelLabel(i))).toEqual(
      NIVELES_QUE_YA_SE_VEIAN,
    );
    expect(skillLevelLabel(8, true)).toBe("Excelente");
    expect(skillLevelLabel(22)).toBe("divino+2");
  });

  it("en inglés usa las palabras de Hattrick", async () => {
    await i18n.changeLanguage("en");
    expect(skillLevelLabel(7)).toBe("solid");
    expect(skillLevelLabel(20)).toBe("divine");
    expect(skillLevelLabel(21)).toBe("divine+1");
  });
});
