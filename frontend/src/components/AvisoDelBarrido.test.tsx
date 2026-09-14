import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { AvisoDelBarrido } from "./AvisoDelBarrido";

const base = {
  commissions: 0,
  histories: 0,
  closedTotal: 0,
  open: 221,
  stopped: false,
};

const pintar = (datos: Partial<typeof base>) =>
  renderToStaticMarkup(
    <AvisoDelBarrido datos={{ ...base, ...datos }} onClose={() => {}} />,
  );

describe("aviso del barrido de comisiones", () => {
  it("nombra las comisiones encontradas", () => {
    const html = pintar({ commissions: 3, closedTotal: 12 });
    expect(html).toContain("3 comisiones");
    expect(html).toContain("221 jugadores");
    expect(html).toContain("12 jugadores quedaron zanjados");
  });

  it("usa el singular con una sola comisión", () => {
    expect(pintar({ commissions: 1 })).toContain("1 comisión de club anterior");
  });

  it("cuenta también los historiales, que antes no se veían en ningún sitio", () => {
    // 2026-09-10: «me dice "Historial por construir: 13 jugadores" y luego no
    // hay nada». El censo sí trabajaba; lo que faltaba era decirlo.
    const html = pintar({ histories: 13 });
    expect(html).toContain("historial de partidos reconstruido a 13 jugadores");
    // Y se explica que reconstruir no es cobrar, para que 13 sin dinero no se
    // lea como un fallo.
    expect(html).toContain("no da dinero por sí solo");
  });

  it("dice que fue parado cuando el usuario lo paró", () => {
    expect(pintar({ commissions: 2, stopped: true })).toContain(
      "Lo que alcanzó a encontrar",
    );
    expect(pintar({ commissions: 2 })).toContain("Esto encontró el barrido");
  });

  it("es un diálogo de verdad y trae con qué cerrarlo", () => {
    const html = pintar({ commissions: 1 });
    expect(html).toContain('role="dialog"');
    expect(html).toContain('aria-modal="true"');
    expect(html).toContain('aria-label="Cerrar"');
  });
});
