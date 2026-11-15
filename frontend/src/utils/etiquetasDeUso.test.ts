import { describe, expect, it } from "vitest";
import { fusionarPulsados, inversoDe } from "./etiquetasDeUso";

/** 2026-11-15, revisión de QA: en Uso › Adopción salía «Players» dos veces
 *  (uno guardado en inglés y otro guardado en español y traducido por el
 *  servidor) y el resto se quedaba en el idioma en que se pulsó. */
describe("los pulsados, uno por botón", () => {
  const inverso = inversoDe([
    { Jugadores: "Players", Logarítmica: "Logarithmic" },
    { Jugadores: "Spieler", Logarítmica: "Logarithmisch" },
  ]);
  const enIngles = (es: string) =>
    ({ Jugadores: "Players", Logarítmica: "Logarithmic" })[es] ?? es;

  it("junta el mismo botón pulsado en tres idiomas y lo enseña en el de la app", () => {
    const r = fusionarPulsados(
      [
        { label: "Players", clicks: 8 },
        { label: "Jugadores", clicks: 3 },
        { label: "Spieler", clicks: 1 },
        { label: "Logarítmica", clicks: 2 },
      ],
      inverso,
      enIngles,
    );
    expect(r).toEqual([
      { label: "Players", clicks: 12 },
      { label: "Logarithmic", clicks: 2 },
    ]);
  });

  it("no repite fila aunque dos etiquetas acaben enseñándose igual", () => {
    // Lo que contestaba el servidor: «Jugadores» ya traducido a «Players»,
    // junto al «Players» que se guardó en inglés.
    const r = fusionarPulsados(
      [
        { label: "Players", clicks: 8 },
        { label: "Players", clicks: 3 },
      ],
      {},
      (x) => x,
    );
    expect(r).toEqual([{ label: "Players", clicks: 11 }]);
  });

  it("las compuestas «Pantalla · botón» se traducen parte por parte", () => {
    const r = fusionarPulsados(
      [
        { label: "Jugadores · Logarítmica", clicks: 2 },
        { label: "Spieler · Logarithmisch", clicks: 1 },
      ],
      inverso,
      enIngles,
    );
    expect(r).toEqual([{ label: "Players · Logarithmic", clicks: 3 }]);
  });

  it("el diccionario sobrevive a la caché, que lo guarda como JSON", () => {
    const vuelta = JSON.parse(JSON.stringify(inverso)) as typeof inverso;
    const r = fusionarPulsados(
      [{ label: "Spieler", clicks: 1 }],
      vuelta,
      enIngles,
    );
    expect(r).toEqual([{ label: "Players", clicks: 1 }]);
  });

  it("lo que no está en ningún diccionario se queda como llegó", () => {
    const r = fusionarPulsados(
      [{ label: "Abrir menú", clicks: 4 }],
      inverso,
      enIngles,
    );
    expect(r).toEqual([{ label: "Abrir menú", clicks: 4 }]);
  });
});
