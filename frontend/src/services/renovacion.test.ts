import { describe, expect, it } from "vitest";
import { leerRenovacion } from "./api";

/** Cuando renovar la sesión falla, ¿fue el servidor diciendo que no, o fue
 *  que no había servidor? (2026-09-19)
 *
 *  Lo reportó el usuario: «se desconecta y se va para render a veces». La
 *  aplicación trataba cualquier fallo de la renovación como sesión muerta y
 *  te echaba a la pantalla de entrada, con recarga de página entera. Si lo
 *  que pasaba era que el servidor se estaba reiniciando, esa recarga es
 *  justo la peor idea: la pide al servidor que no está, y quien contesta es
 *  la pantalla de error del proveedor.
 *
 *  Se prueba la decisión, no el navegador: es donde estaba el error.
 */
describe("renovar la sesión", () => {
  it("un 2xx es una sesión viva", () => {
    expect(leerRenovacion(200)).toBe("viva");
    expect(leerRenovacion(204)).toBe("viva");
  });

  it("solo 401 y 403 matan la sesión", () => {
    expect(leerRenovacion(401)).toBe("muerta");
    expect(leerRenovacion(403)).toBe("muerta");
  });

  it("el servidor caído o reiniciándose no es una sesión caducada", () => {
    for (const estado of [500, 502, 503, 504, 429, 404]) {
      expect(leerRenovacion(estado)).toBe("sin-respuesta");
    }
  });

  it("sin respuesta ninguna tampoco", () => {
    expect(leerRenovacion(null)).toBe("sin-respuesta");
  });
});
