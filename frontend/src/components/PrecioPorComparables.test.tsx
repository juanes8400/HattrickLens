import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { columnasDe } from "./PrecioPorComparables";
import type { ComparableDeMercado } from "../services/api/transferencias";

/** Una venta cualquiera del fondo, con lo justo para pintar una fila. */
function venta(extra: Partial<ComparableDeMercado> = {}): ComparableDeMercado {
  return {
    htPlayerId: 513118480,
    nombre: "Marcus Stigmar",
    precio: 176000,
    puja: 176000,
    peso: 100,
    avaladoPorHattrick: true,
    firme: true,
    viejo: false,
    edad: 20,
    dias: 49,
    perfil: [
      { habilidad: "defending", nivel: 10 },
      { habilidad: "playmaking", nivel: 4 },
      { habilidad: "passing", nivel: 4 },
    ],
    semanas: 1,
    cierra: "2026-11-05T12:10:31Z",
    especialidad: "",
    tsi: 6370,
    forma: -1,
    precioPedido: 0,
    sinPuja: false,
    paisCodigo: "SE",
    paisNombre: "Sverige",
    ...extra,
  };
}

function celdaDeFecha(fila: ComparableDeMercado): string {
  const columnas = columnasDe(fila.perfil, "US$");
  const fecha = columnas.find((c) => c.key === "fecha");
  if (!fecha?.render) throw new Error("la columna Fecha dejó de tener render");
  return renderToStaticMarkup(<>{fecha.render(fila)}</>);
}

describe("la marca de las 24 semanas", () => {
  it("pone el reloj de arena cuando la venta ya cumplió su vida", () => {
    const html = celdaDeFecha(venta({ viejo: true }));

    // LA FORMA, no sólo el color. El aviso era sólo la fecha en ámbar hasta
    // el 2026-11-08, y un color solo no se puede leer: ni quien no lo
    // distingue ni quien no sabe qué significa que una fecha cambie de tono.
    expect(html).toContain("<svg");
    expect(html).toContain('role="img"');
    expect(html).toContain("text-[var(--warn)]");
    // Y el porqué entero, que es lo que la forma no cabe decir.
    expect(html).toContain("sólo deja su sitio cuando la lista llega a 30");
  });

  it("no la pone cuando la venta es reciente", () => {
    const html = celdaDeFecha(venta({ viejo: false }));

    expect(html).not.toContain("<svg");
    expect(html).not.toContain("text-[var(--warn)]");
  });

  it("la fecha se lee igual en los dos casos", () => {
    for (const viejo of [true, false]) {
      expect(celdaDeFecha(venta({ viejo }))).toContain("2026");
    }
  });

  it("la fila del propio jugador no lleva fecha ni marca", () => {
    // No está en venta: una fecha ahí sería inventada, y la marca de vieja
    // todavía más.
    const html = celdaDeFecha(venta({ propio: true, viejo: true }));

    expect(html).not.toContain("<svg");
    expect(html).toContain("—");
  });
});
