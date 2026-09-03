import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { LineupAvailabilityNotice } from "./LineupAvailabilityNotice";

describe("aviso de plantilla insuficiente", () => {
  it("renderiza un aviso útil en lugar de romper con menos de once", () => {
    const html = renderToStaticMarkup(
      <LineupAvailabilityNotice availableCount={9} />,
    );

    expect(html).toContain('role="alert"');
    expect(html).toContain("No se puede calcular el once");
    expect(html).toContain("Hay 9 jugadores disponibles");
    expect(html).toContain("hacen falta 11");
  });
});
