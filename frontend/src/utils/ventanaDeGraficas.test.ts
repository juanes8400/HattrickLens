import { describe, expect, it } from "vitest";
import { ventanaDeGraficas } from "./ventanaDeGraficas";

/** El eje tiene que cubrir TODO lo que la gráfica dibuja.
 *
 *  2026-09-01, visto por el usuario en producción: «esos puntos de compras y
 *  ventas que se van hasta por allá lejos a la izquierda». El eje se calculaba
 *  con las lecturas, los partidos y los socios, pero la gráfica pintaba además
 *  el pulso de mercado, que el backend saca con su propia ventana de ocho
 *  semanas. Seis operaciones eran anteriores al primer partido y sus puntos
 *  caían fuera del dibujo, encima de las etiquetas del eje.
 *
 *  En la copia local no se reproducía: allí el partido más antiguo (8 de
 *  julio) es anterior a la primera venta (11 de julio), así que todo caía
 *  dentro por casualidad.
 */
describe("la ventana de las gráficas", () => {
  const dentro = (dia: string, v: { from: string; to: string }) => {
    const t = new Date(`${dia}T12:00:00`).getTime();
    return t >= new Date(v.from).getTime() && t <= new Date(v.to).getTime();
  };

  it("el caso de producción: el mercado empieza antes que los partidos", () => {
    const v = ventanaDeGraficas({
      instantes: ["2026-07-12T21:40:00", "2026-08-20T15:32:33"],
      dias: ["2026-07-07", "2026-07-09", "2026-08-30"],
    });
    // El 7 de julio es anterior al primer partido y aun así entra.
    expect(dentro("2026-07-07", v)).toBe(true);
    expect(dentro("2026-07-09", v)).toBe(true);
    expect(dentro("2026-08-30", v)).toBe(true);
  });

  it("ningún día de mercado se queda fuera, venga cuando venga", () => {
    const dias = ["2026-05-01", "2026-07-07", "2026-08-30", "2026-09-15"];
    const v = ventanaDeGraficas({ instantes: ["2026-08-01T10:00:00"], dias });
    for (const d of dias) expect(dentro(d, v)).toBe(true);
  });

  it("sigue dejando un día de aire a cada lado", () => {
    // Sin él, el primer y el último punto quedan pegados al marco.
    const v = ventanaDeGraficas({
      instantes: ["2026-08-10T12:00:00"],
      dias: [],
    });
    expect(v.from.slice(0, 10)).toBe("2026-08-09");
    expect(v.to.slice(0, 10)).toBe("2026-08-11");
  });

  it("sin nada que dibujar, no revienta", () => {
    const v = ventanaDeGraficas(
      { instantes: [], dias: [] },
      () => new Date("2026-09-01T00:00:00Z"),
    );
    expect(new Date(v.from).getTime()).toBeLessThan(new Date(v.to).getTime());
  });

  it("los huecos de las series no cuentan", () => {
    const v = ventanaDeGraficas({
      instantes: [null, undefined, "2026-08-10T12:00:00"],
      dias: [],
    });
    expect(v.from.slice(0, 10)).toBe("2026-08-09");
  });
});
