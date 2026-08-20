/**
 * Parser de compatibilidad de "Qué cambió".
 *
 * Desde 2026-08-15 los cambios NUEVOS traen `detail` con los números, y este
 * parser sólo se usa para las filas guardadas antes de esa fecha. Aun así
 * merece tests: fue exactamente el punto donde se rompió la app. El backend
 * cambió el separador de miles de coma a punto y este parser hacía
 * `Number(raw.replace(/,/g, ""))`, así que `Number("202.210")` valía 202,21 y
 * la UI mostró "TSI 202" para un jugador de 202 mil.
 */
import { describe, expect, it } from "vitest";
import { parseNumericDelta } from "./SyncChangesFeed";

describe("parseNumericDelta · separador de miles", () => {
  it("lee el formato de la app (punto de miles), que fue el que rompió", () => {
    const parsed = parseNumericDelta("TSI 198.930 -> 202.210");
    expect(parsed).not.toBeNull();
    expect(parsed?.before).toBe(198930);
    expect(parsed?.after).toBe(202210);
  });

  it("sigue leyendo el formato viejo con coma, que quedó guardado en la DB", () => {
    const parsed = parseNumericDelta("TSI 198,930 -> 202,210");
    expect(parsed?.before).toBe(198930);
    expect(parsed?.after).toBe(202210);
  });

  it("no confunde un decimal con un separador de miles", () => {
    // Sólo cuentan como miles los separadores seguidos de EXACTAMENTE 3
    // dígitos; "202,21" son 202 con 21 centésimas.
    const parsed = parseNumericDelta("Media 202,21 -> 203,45");
    expect(parsed?.before).toBeCloseTo(202.21);
    expect(parsed?.after).toBeCloseTo(203.45);
  });

  it("encadena varios grupos de miles", () => {
    const parsed = parseNumericDelta("Caja 1.234.567 -> 8.690.000");
    expect(parsed?.before).toBe(1234567);
    expect(parsed?.after).toBe(8690000);
  });

  it("números de menos de mil no llevan separador y se leen igual", () => {
    const parsed = parseNumericDelta("Socios 950 -> 980");
    expect(parsed?.before).toBe(950);
    expect(parsed?.after).toBe(980);
  });
});

describe("parseNumericDelta · formas de frase", () => {
  it("entiende 'subió de X a Y' y lo marca como bueno", () => {
    const parsed = parseNumericDelta("Defensa subió de 10 a 11");
    expect(parsed?.label).toBe("Defensa");
    expect(parsed?.before).toBe(10);
    expect(parsed?.after).toBe(11);
    expect(parsed?.good).toBe(true);
  });

  it("entiende 'bajó de X a Y' y lo marca como malo", () => {
    const parsed = parseNumericDelta("Pases bajó de 8 a 7");
    expect(parsed?.good).toBe(false);
  });

  it("una lesión que empeora no se marca como buena", () => {
    const parsed = parseNumericDelta("lesión de nivel 0 a 1");
    expect(parsed?.label).toBe("Lesión");
    expect(parsed?.good).toBe(false);
  });

  it("un salario que sube es un gasto que sube: queda neutro", () => {
    const parsed = parseNumericDelta("Salario 5.000 -> 5.500");
    expect(parsed?.good).toBeNull();
  });

  it("convierte el nombre de un nivel de espíritu a su número", () => {
    const parsed = parseNumericDelta("Espíritu del equipo: Serenos -> Calmados");
    expect(parsed?.before).toBe(4);
    expect(parsed?.after).toBe(5);
    expect(parsed?.stateLabel).toBe("Calmados");
    expect(parsed?.good).toBe(true);
  });

  it("hace lo mismo con la confianza", () => {
    const parsed = parseNumericDelta("Confianza: Alta -> Decente");
    expect(parsed?.before).toBe(6);
    expect(parsed?.after).toBe(4);
    expect(parsed?.good).toBe(false);
  });

  it("devuelve null cuando la frase no tiene par numérico", () => {
    expect(parseNumericDelta("se unió a la plantilla")).toBeNull();
    expect(parseNumericDelta("puesto en mercado")).toBeNull();
    expect(parseNumericDelta("")).toBeNull();
  });
});
