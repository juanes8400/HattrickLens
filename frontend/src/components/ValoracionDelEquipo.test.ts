import { describe, expect, it } from "vitest";
import type { PrecioDeUnJugador } from "../services/api";
import { resumenDeLaValoracion } from "./ValoracionDelEquipo";

/** La cuenta de la valoración del equipo, 2026-11-04.
 *
 *  Pedido del usuario: «un Segment Toggle para Valoración del Equipo, con el
 *  valor de cada jugador y del total de la plantilla».
 *
 *  Lo que se fija aquí es lo que se puede equivocar SIN HACER RUIDO, que en una
 *  suma de dinero es lo peligroso: el total seguiría saliendo, sólo que mal.
 *
 *  1. Quién entra en la suma. A quien no tiene ni una venta cerrada parecida su
 *     precio le llega `null`, nunca cero; contarlo como cero daría un total
 *     correcto por casualidad y una media y una mediana falsas.
 *  2. De qué plantilla hablan el suelo y el techo. Tienen que sumarse de los
 *     MISMOS jugadores que el total, o la banda diría que el total está fuera
 *     de su propia horquilla.
 *  3. La mediana con un número PAR de jugadores es el promedio de los dos de en
 *     medio, no el de más arriba de los dos.
 */
function jugador(
  nombre: string,
  media: number | null,
  extra: Partial<PrecioDeUnJugador> = {},
): PrecioDeUnJugador {
  return {
    htPlayerId: nombre.length * 7 + (media ?? 0),
    nombre,
    edad: 25,
    tsi: 10000,
    especialidad: "",
    perfil: [],
    media,
    mediana: media,
    minimo: media == null ? null : Math.round(media * 0.8),
    maximo: media == null ? null : Math.round(media * 1.2),
    n: media == null ? 0 : 5,
    faltan: 0,
    clavadas: 0,
    avaladas: media == null ? 0 : 5,
    provisionales: 0,
    semanasDelMasViejo: 2,
    serie: [],
    ...extra,
  };
}

describe("resumenDeLaValoracion", () => {
  it("suma sólo a quien tiene precio, y dice a cuántos deja fuera", () => {
    const r = resumenDeLaValoracion([
      jugador("Con precio", 1000),
      jugador("Sin precio", null),
      jugador("Otro con precio", 500),
    ]);
    expect(r.total).toBe(1500);
    expect(r.conPrecio).toHaveLength(2);
    expect(r.sinPrecio.map((j) => j.nombre)).toEqual(["Sin precio"]);
  });

  it("no cuenta como cero a quien no tiene precio", () => {
    // El total es el mismo con y sin él --ése es el punto-- pero la mediana y
    // el reparto NO lo serían si entrara valiendo cero.
    const soloUno = resumenDeLaValoracion([jugador("Uno", 1000)]);
    const conFantasma = resumenDeLaValoracion([
      jugador("Uno", 1000),
      jugador("Fantasma", null),
    ]);
    expect(conFantasma.total).toBe(soloUno.total);
    expect(conFantasma.mediana).toBe(1000);
  });

  it("ordena de más caro a más barato, y desempata por nombre", () => {
    const r = resumenDeLaValoracion([
      jugador("Zeta", 500),
      jugador("Alfa", 500),
      jugador("Caro", 900),
    ]);
    expect(r.conPrecio.map((j) => j.nombre)).toEqual(["Caro", "Alfa", "Zeta"]);
    expect(r.tope).toBe(900);
  });

  it("el suelo y el techo salen de los MISMOS que el total", () => {
    const r = resumenDeLaValoracion([
      jugador("Con precio", 1000),
      jugador("Sin precio", null),
    ]);
    // 80 % y 120 % del único que cuenta. Si el que no tiene precio entrara, con
    // `minimo` y `maximo` nulos, el suelo y el techo saldrían descuadrados.
    expect(r.suelo).toBe(800);
    expect(r.techo).toBe(1200);
    // Y el total queda DENTRO de su horquilla, que es lo que la banda promete.
    expect(r.total).toBeGreaterThanOrEqual(r.suelo);
    expect(r.total).toBeLessThanOrEqual(r.techo);
  });

  it("la mediana de un número par es el promedio de los dos de en medio", () => {
    const r = resumenDeLaValoracion([
      jugador("A", 400),
      jugador("B", 300),
      jugador("C", 200),
      jugador("D", 100),
    ]);
    expect(r.mediana).toBe(250);
  });

  it("la mediana de un número impar es el de en medio", () => {
    const r = resumenDeLaValoracion([
      jugador("A", 400),
      jugador("B", 300),
      jugador("C", 100),
    ]);
    expect(r.mediana).toBe(300);
  });

  it("cuenta la plantilla ENTERA, no las filas que llegaron", () => {
    // 2026-11-04, lo cazó una revisión automática del PR #23: el servidor deja
    // fuera a quien todavía no tiene una foto de sus habilidades, así que
    // contar las filas devueltas anunciaba una plantilla de 30 como una de 27
    // y nadie podía verlo.
    const r = resumenDeLaValoracion(
      [jugador("Medido", 1000), jugador("Sin precio", null)],
      3,
    );
    expect(r.plantilla).toBe(5);
    expect(r.sinMedir).toBe(3);
    // Y los que no se han podido medir NO entran en la suma, igual que los que
    // no tienen comparables: no se sabe lo que valen.
    expect(r.total).toBe(1000);
  });

  it("sin nadie fuera, la plantilla son los que llegaron", () => {
    const r = resumenDeLaValoracion([
      jugador("Uno", 1000),
      jugador("Otro", null),
    ]);
    expect(r.plantilla).toBe(2);
    expect(r.sinMedir).toBe(0);
  });

  it("con la plantilla vacía no divide por cero ni inventa un total", () => {
    const r = resumenDeLaValoracion([]);
    expect(r.total).toBe(0);
    expect(r.tope).toBe(0);
    expect(r.mediana).toBeNull();
    expect(r.conPrecio).toEqual([]);
  });

  it("sin nadie con precio, la mediana es nula y no cero", () => {
    // Cero diría «el jugador mediano vale cero»; nulo dice «no se sabe», que es
    // lo que pasa, y la pantalla lo pinta como una raya.
    const r = resumenDeLaValoracion([
      jugador("Uno", null),
      jugador("Otro", null),
    ]);
    expect(r.mediana).toBeNull();
    expect(r.sinPrecio).toHaveLength(2);
  });

  it("cae de pie si falta el mínimo o el máximo de alguien", () => {
    // `minimo` y `maximo` son opcionales en el peor de los casos; entonces el
    // jugador aporta su propia media a la horquilla en vez de desaparecer de
    // ella, que dejaría la banda más estrecha que el total.
    const r = resumenDeLaValoracion([
      jugador("Sin horquilla", 1000, { minimo: null, maximo: null }),
    ]);
    expect(r.suelo).toBe(1000);
    expect(r.techo).toBe(1000);
  });
});
