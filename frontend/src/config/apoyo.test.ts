import { describe, expect, it } from "vitest";
import { VIAS_DE_APOYO, viasPara } from "./apoyo";

/**
 * El orden de las vías de apoyo según el país del club.
 *
 * Existe por un fallo real del 2026-09-05: la primera versión agrupaba en DOS
 * --«las del país» y «el resto»-- y el resto conservaba el orden declarado, así
 * que a alguien de Suecia le salía una llave de pagos colombiana como primera
 * opción. Justo lo que el orden por país existía para evitar. Se había
 * comprobado sólo con Colombia, que era el caso que sí funcionaba.
 */

const ids = (pais: string | null | undefined) =>
  viasPara(pais).map((v) => v.id);

describe("viasPara", () => {
  it("a un club colombiano le pone delante lo que le llega íntegro", () => {
    // Bre-B no tiene comisión de plataforma; cualquier pasarela se lleva
    // entre el 5 y el 9 %. Por eso va primero, y Mercado Pago detrás.
    expect(ids("Colombia").slice(0, 2)).toEqual(["bre-b", "mercadopago"]);
  });

  it("a un club de fuera NO le enseña primero una llave colombiana", () => {
    const suecia = ids("Sweden");
    expect(suecia[0]).toBe("paypal");
    expect(suecia.indexOf("bre-b")).toBeGreaterThan(
      suecia.indexOf("buymeacoffee"),
    );
  });

  it("sin país conocido se comporta como con un país de fuera", () => {
    // Pasa mientras el panel todavía no ha respondido. Enseñar la llave
    // colombiana en ese hueco sería adivinar, y adivinar hacia el país del
    // autor es lo más fácil de hacer mal.
    expect(ids(null)[0]).toBe("paypal");
    expect(ids(undefined)[0]).toBe("paypal");
  });

  it("las enseña TODAS siempre: es un orden, no un filtro", () => {
    // Un colombiano que vive fuera y prefiere pagar con tarjeta internacional
    // no puede quedarse sin su opción por dónde esté su club.
    for (const pais of ["Colombia", "Sweden", null]) {
      expect(viasPara(pais)).toHaveLength(VIAS_DE_APOYO.length);
      expect(new Set(ids(pais)).size).toBe(VIAS_DE_APOYO.length);
    }
  });

  it("cada vía lleva enlace o llave, nunca las dos ni ninguna", () => {
    // La pantalla decide entre pintar un botón «Abrir» o una llave copiable
    // mirando `llave`. Una vía con las dos cosas, o con ninguna, sale rota.
    for (const v of VIAS_DE_APOYO) {
      expect(Boolean(v.enlace) !== Boolean(v.llave)).toBe(true);
      expect(v.porQue.length).toBeGreaterThan(0);
    }
  });
});
