import { describe, expect, it } from "vitest";
import { NAV, agrupar, tituloDeRuta } from "./navegacion";

/** El menú se veía agrupado en cinco bloques y esa agrupación existía SÓLO en
 *  el aspecto: veinte enlaces hermanos sueltos, sin una sola lista. Quien no
 *  ve la pantalla oía veinte enlaces en fila, sin saber cuántos quedaban ni a
 *  qué bloque pertenecía cada uno (2026-08-31). */
describe("los grupos del menú", () => {
  it("cada rótulo se lleva los enlaces que van debajo", () => {
    const grupos = agrupar([
      { section: "Club" },
      { to: "/a", label: "A" },
      { to: "/b", label: "B" },
      { section: "Negocio" },
      { to: "/c", label: "C" },
    ]);
    expect(grupos.map((g) => g.titulo)).toEqual(["Club", "Negocio"]);
    expect(grupos[0]?.enlaces.map((e) => e.to)).toEqual(["/a", "/b"]);
    expect(grupos[1]?.enlaces.map((e) => e.to)).toEqual(["/c"]);
  });

  it("un grupo sin enlaces no pinta una lista vacía", () => {
    // Pasaría si alguien quita el último enlace de una sección: quedaría un
    // rótulo suelto anunciando una lista de cero elementos.
    expect(agrupar([{ section: "Vacía" }])).toEqual([]);
  });

  it("ningún enlace del menú real se pierde por el camino", () => {
    const enlacesEnNav = NAV.filter((i) => "to" in i).length;
    const enlacesAgrupados = agrupar(NAV).reduce(
      (n, g) => n + g.enlaces.length,
      0,
    );
    expect(enlacesAgrupados).toBe(enlacesEnNav);
  });

  it("el menú real se reparte en grupos, y ninguno queda huérfano", () => {
    const grupos = agrupar(NAV);
    expect(grupos.length).toBeGreaterThan(1);
    expect(grupos.every((g) => g.titulo && g.enlaces.length > 0)).toBe(true);
  });
});

describe("el título de la pestaña", () => {
  it("las pantallas del menú se titulan solas", () => {
    expect(tituloDeRuta("/economy")).toBe("Economía · HT Lens");
    expect(tituloDeRuta("/transfers/balance")).toBe("Transferencias · HT Lens");
  });

  it("las de entrada también, que eran las únicas sin nombre", () => {
    // Con «HT Lens» a secas, /welcome y /setup no se distinguían en el
    // historial ni entre pestañas — y son por las que se pasa al empezar.
    expect(tituloDeRuta("/welcome")).toBe("Conectar tu club · HT Lens");
    expect(tituloDeRuta("/setup")).toBe("Configuración de tu club · HT Lens");
  });

  it("una ruta desconocida no inventa nombre", () => {
    expect(tituloDeRuta("/inexistente")).toBe("HT Lens");
  });
});
