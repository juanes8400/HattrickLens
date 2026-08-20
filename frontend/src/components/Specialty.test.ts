import { describe, expect, it } from "vitest";
import { specialtyIcon, specialtyLabel } from "./Specialty";

/** El mapa se indexa por la etiqueta que manda el backend, no por el número de
 *  CHPP, así que lo que puede romperlo es el texto: una tilde, una mayúscula o
 *  la forma de escribir "no tiene". Eso es lo que se fija aquí. */
describe("specialtyIcon", () => {
  it("da un icono a cada una de las siete especialidades de Hattrick", () => {
    const todas = [
      "Técnico", "Rápido", "Potente", "Imprevisible",
      "Cabeceador", "Estoico", "Influyente",
    ];
    const iconos = todas.map(specialtyIcon);
    expect(iconos.every((i) => i !== null)).toBe(true);
    // Siete iconos distintos: dos especialidades con el mismo símbolo serían
    // peor que ninguno.
    expect(new Set(iconos).size).toBe(todas.length);
  });

  it("no depende de tildes ni de mayúsculas", () => {
    expect(specialtyIcon("Tecnico")).toBe(specialtyIcon("Técnico"));
    expect(specialtyIcon("RÁPIDO")).toBe(specialtyIcon("Rápido"));
    expect(specialtyIcon("  imprevisible  ")).toBe(specialtyIcon("Imprevisible"));
  });

  it("no inventa un icono para lo que no conoce", () => {
    // Si Hattrick añade una especialidad, sale sin icono pero con su nombre —
    // nunca con el símbolo de otra.
    expect(specialtyIcon("Regateador")).toBeNull();
    expect(specialtyIcon("")).toBeNull();
    expect(specialtyIcon(null)).toBeNull();
  });
});

describe("specialtyLabel", () => {
  it("unifica las dos formas en que el backend escribe la ausencia", () => {
    // Plantilla manda "" y Saldo por jugador manda "Ninguna"; en pantalla las
    // dos tienen que leerse igual.
    expect(specialtyLabel("")).toBe("Sin especialidad");
    expect(specialtyLabel("Ninguna")).toBe("Sin especialidad");
    expect(specialtyLabel(null)).toBe("Sin especialidad");
  });

  it("deja intacto el nombre real, con su tilde", () => {
    expect(specialtyLabel("Técnico")).toBe("Técnico");
  });
});
