import { describe, expect, it } from "vitest";
import {
  ATRIBUTO,
  SIGUIENTE_TEMA,
  normalizarTema,
  type Tema,
} from "./useTheme";

/** El tema tiene TRES estados, y el tercero es el que faltaba.
 *
 *  Lo que se vigila aquí es lo que estaba roto el 2026-08-31: el botón
 *  volteaba `data-theme` en el DOM, nada lo guardaba y cada recarga devolvía
 *  al claro; y como el HTML estampaba el atributo a mano, «sigue al sistema»
 *  no existía. Se prueba la decisión, no el DOM: el proyecto no tiene entorno
 *  de navegador en los tests y esto no merece una dependencia nueva.
 */
describe("el tema", () => {
  it("lo que no sea uno de los tres es «sistema»", () => {
    expect(normalizarTema(null)).toBe("sistema");
    expect(normalizarTema(undefined)).toBe("sistema");
    expect(normalizarTema("")).toBe("sistema");
    expect(normalizarTema("fucsia")).toBe("sistema");
    expect(normalizarTema("dark")).toBe("sistema"); // el valor del atributo, no el del tema
  });

  it("los tres válidos se conservan", () => {
    for (const t of ["sistema", "claro", "oscuro"] as Tema[]) {
      expect(normalizarTema(t)).toBe(t);
    }
  });

  it("«sistema» NO estampa atributo; los otros dos sí", () => {
    // Es la línea que separa «sigue a tu sistema» de «te impongo el claro».
    expect(ATRIBUTO.sistema).toBeNull();
    expect(ATRIBUTO.claro).toBe("light");
    expect(ATRIBUTO.oscuro).toBe("dark");
  });

  it("el ciclo del botón vuelve a «sistema»", () => {
    // Sin este regreso, el primer clic deja al usuario encerrado fuera de la
    // preferencia de su sistema operativo para siempre.
    expect(SIGUIENTE_TEMA.sistema).toBe("claro");
    expect(SIGUIENTE_TEMA.claro).toBe("oscuro");
    expect(SIGUIENTE_TEMA.oscuro).toBe("sistema");

    let t: Tema = "sistema";
    const vistos = new Set<Tema>();
    for (let i = 0; i < 3; i++) {
      vistos.add(t);
      t = SIGUIENTE_TEMA[t];
    }
    expect(vistos.size).toBe(3); // los tres son alcanzables
    expect(t).toBe("sistema"); // y se vuelve al principio
  });
});
