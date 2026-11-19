/** «Alineación enviada» TACHADA cuando todavía no se ha mandado ninguna
 *  (2026-11-19, pedido del usuario): se ve que existe y qué falta. */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { PitchZoneMethodSelector } from "./PitchZoneMethodSelector";
import { PITCH_ZONE_METHODS, SUBMITTED_METHOD } from "./pitchZoneMethods";

const opciones = [SUBMITTED_METHOD, ...PITCH_ZONE_METHODS];

function botonDeEnviada(html: string): string {
  const fin = html.indexOf(SUBMITTED_METHOD.label);
  return html.slice(html.lastIndexOf("<button", fin), fin);
}

describe("PitchZoneMethodSelector", () => {
  it("tacha la alineación enviada si no se ha mandado", () => {
    const html = renderToStaticMarkup(
      <PitchZoneMethodSelector
        method="average"
        onMethodChange={() => {}}
        options={opciones}
        noDisponibles={["submitted"]}
      />,
    );
    expect(botonDeEnviada(html)).toContain("line-through");
    expect(html).toContain(
      "Todavía no has enviado la alineación de este partido.",
    );
  });

  it("con la alineación enviada, no tacha nada", () => {
    const html = renderToStaticMarkup(
      <PitchZoneMethodSelector
        method="submitted"
        onMethodChange={() => {}}
        options={opciones}
      />,
    );
    expect(html).not.toContain("line-through");
  });
});
