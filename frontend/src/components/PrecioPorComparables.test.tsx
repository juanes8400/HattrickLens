import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { columnasDe, columnasEnEspera } from "./PrecioPorComparables";
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

describe("la tabla de stand-by", () => {
  function celda(clave: string, fila: ComparableDeMercado): string {
    const c = columnasEnEspera(fila.perfil, "US$").find((x) => x.key === clave);
    if (!c) throw new Error(`no existe la columna ${clave}`);
    return renderToStaticMarkup(
      <>{c.render ? c.render(fila) : c.value(fila)}</>,
    );
  }

  const esperando = (extra: Partial<ComparableDeMercado> = {}) =>
    venta({ firme: false, precio: 0, puja: 0, precioPedido: 0, ...extra });

  it("lleva «Precio inicial», que es el nombre que puso el usuario", () => {
    const claves = columnasEnEspera(venta().perfil, "US$").map((c) => c.key);
    expect(claves).toContain("precioPedido");
    const cabeceras = columnasEnEspera(venta().perfil, "US$").map(
      (c) => c.header,
    );
    expect(cabeceras).toContain("Precio inicial");
    // Y NO lleva «Precio»: ahí nadie ha pagado nada todavía.
    expect(claves).not.toContain("precio");
  });

  it("un precio inicial de cero es una raya, no «0 US$»", () => {
    // Cero es «no lo sabemos»: las ventas anotadas antes de la migración
    // 0112 no lo traen, y un 0 US$ diría que lo regalan.
    expect(celda("precioPedido", esperando({ precioPedido: 0 }))).toContain(
      "—",
    );
    expect(celda("precioPedido", esperando({ precioPedido: 250000 }))).toMatch(
      /250/,
    );
  });

  it("una puja de cero dice que nadie ha pujado, no que valga cero", () => {
    // La mitad de lo que hay en stand-by está a cero: confundir las dos
    // cosas sería leer un mercado vacío donde hay anuncios vivos.
    expect(celda("puja", esperando({ puja: 0 }))).toContain(
      "sin pujas todavía",
    );
    expect(celda("puja", esperando({ puja: 95000 }))).toMatch(/95/);
  });

  it("«Cierra» lleva la hora, porque un plazo son las 21:14 y no «el martes»", () => {
    const html = celda("cierra", esperando({ cierra: "2026-11-10T21:14:00Z" }));
    expect(html).toMatch(/\d{2}:\d{2}/);
  });

  it("hasta la especialidad, las mismas columnas que la tabla de arriba", () => {
    // Es la misma gente mirada en otro momento: leerla no puede pedir
    // aprender otra tabla.
    const fila = venta();
    const arriba = columnasDe(fila.perfil, "US$").map((c) => c.key);
    const abajo = columnasEnEspera(fila.perfil, "US$").map((c) => c.key);
    const hasta = arriba.indexOf("habilidad2") + 1;
    expect(abajo.slice(0, hasta)).toEqual(arriba.slice(0, hasta));
  });
});

describe("el precio de una venta cerrada", () => {
  function celdaPrecio(fila: ComparableDeMercado): string {
    const c = columnasDe(fila.perfil, "US$").find((x) => x.key === "precio");
    if (!c?.render) throw new Error("la columna Precio dejó de tener render");
    return renderToStaticMarkup(<>{c.render(fila)}</>);
  }

  it("no lleva el porcentaje verde contra la puja", () => {
    // Lo quitó el usuario el 2026-11-08. Era lo último que quedaba de la
    // columna «Puja detectada», retirada el día antes: un porcentaje contra
    // un número que ya no está en ninguna parte no se puede comprobar, y lo
    // que medía era cuándo miramos nosotros, no cuánto valía el jugador.
    const html = celdaPrecio(venta({ puja: 100000, precio: 176000 }));

    expect(html).toContain("176");
    expect(html).not.toMatch(/\+[\d,.]+%/);
    expect(html).not.toContain("--positive");
  });

  it("lleva SÓLO el precio, también cuando no le vimos puja", () => {
    // 2026-11-10, pedido del usuario: «solo el precio». La nota «sin puja
    // vista» era la última comparación con la puja en esta columna.
    for (const sinPuja of [true, false]) {
      const html = celdaPrecio(venta({ sinPuja, precio: 176000 }));
      expect(html).toContain("176");
      expect(html).not.toContain("puja");
      // Un solo elemento: el número, sin nada al lado.
      expect(html.match(/<span/g)).toHaveLength(1);
    }
  });
});
