import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { conMirarA, SelectorMirarA } from "./TeamOverviewPage";
import type { MirarA } from "../services/api";

/** «Mirar a» (2026-11-17): el selector de grupos de Rentabilidad deportiva en
 *  Habilidades. */
const mirar: MirarA = {
  selected: "gangas",
  options: [
    { key: "estrellas", label: "Estrellas", count: 6 },
    { key: "gangas", label: "Gangas", count: 4 },
    { key: "caros", label: "Caros", count: 0 },
    { key: "economicos", label: "Económicos", count: 5 },
  ],
  members: ["Ece", "Guastavino", "Homeag", "Lutzki"],
};

describe("Mirar a", () => {
  it("sale en las pestañas con series y no en Clases de Jugador", () => {
    expect(conMirarA("line")).toBe(true);
    expect(conMirarA("classes")).toBe(false);
  });

  it("cada opción lleva su número de jugadores, y la plantilla entera va primera", () => {
    const html = renderToStaticMarkup(
      <SelectorMirarA mirar={mirar} activa="gangas" onChange={() => {}} />,
    );
    expect(html.indexOf("Plantilla entera")).toBeLessThan(
      html.indexOf("Estrellas · 6"),
    );
    expect(html).toContain("Gangas · 4");
    expect(html).toContain("Económicos · 5");
  });

  it("un grupo vacío se apaga en vez de desaparecer", () => {
    const html = renderToStaticMarkup(
      <SelectorMirarA mirar={mirar} activa="plantilla" onChange={() => {}} />,
    );
    const caros = html.slice(0, html.indexOf("Caros · 0"));
    expect(caros.slice(caros.lastIndexOf("<button"))).toContain("disabled");
  });
});
