/** El color del mapa de uso, y la leyenda que lo explica.
 *
 *  Lo que estas pruebas vigilan no es estética: es que el panel no se
 *  contradiga a sí mismo. Hay dos formas de que lo haga, y las dos habían
 *  pasado desapercibidas porque ninguna rompe nada visible:
 *
 *   · que la leyenda rotule tonos que no aparecen en el mapa, o le ponga la
 *     misma etiqueta a dos tonos distintos --que es lo que hacía al colorear
 *     por PERSONAS, donde el máximo es un número pequeño--;
 *   · que un país con más valor que otro salga más claro.
 */
import { describe, expect, it } from "vitest";

import {
  TONOS,
  leyendaDe,
  pasoDeColor,
  tono,
  valorDe,
} from "./mapaDeUso";
import type { UsoPorPais } from "./mapaDeUso";

function pais(code: string, users: number, clicks: number): UsoPorPais {
  return { code, name: code, users, sessions: 0, pages: 0, clicks, minutes: 0 };
}

describe("qué se colorea", () => {
  it("lee la magnitud elegida, no la que venga primero", () => {
    const p = pais("es", 3, 400);
    expect(valorDe(p, "users")).toBe(3);
    expect(valorDe(p, "clicks")).toBe(400);
  });
});

describe("el tono de un país", () => {
  it("más valor nunca es más claro", () => {
    // La propiedad que de verdad importa: la escala puede ser la que sea, pero
    // no puede invertirse en ningún tramo.
    //
    // Se recorre todo y se afirma UNA vez. Con un `expect` por vuelta el
    // mismo recorrido tardaba dos segundos y medio --quinientas aserciones
    // cuestan más que los quinientos cálculos-- y era la prueba más lenta de
    // todo el frontend para comprobar una sola propiedad.
    const pasos = Array.from({ length: 501 }, (_, v) => pasoDeColor(v, 500));
    const bajadas = pasos.filter((p, i) => i > 0 && p < (pasos[i - 1] ?? 0));
    expect(bajadas).toEqual([]);
  });

  it("el cero y lo negativo caen en el tono más claro", () => {
    // Negativo no debería llegar nunca, pero viene de una suma del servidor y
    // un índice negativo saldría como `undefined` en el `color-mix`.
    expect(pasoDeColor(0, 100)).toBe(0);
    expect(pasoDeColor(-5, 100)).toBe(0);
  });

  it("sin máximo no revienta", () => {
    expect(pasoDeColor(0, 0)).toBe(0);
    expect(pasoDeColor(7, 0)).toBe(0);
  });

  it("el máximo cae en el tono más oscuro y no se sale del índice", () => {
    expect(pasoDeColor(100, 100)).toBe(TONOS.length - 1);
    // Por encima del máximo no debería haber nada, pero si lo hubiera no puede
    // pedir un tono que no existe.
    expect(pasoDeColor(1000, 100)).toBe(TONOS.length - 1);
  });

  it("todos los tonos son un color de verdad", () => {
    for (let paso = 0; paso < TONOS.length; paso++) {
      expect(tono(paso)).toMatch(/^color-mix\(in srgb, var\(--accent\) \d+%/);
    }
  });

  it("no es una escala lineal, y por eso el mapa dice algo", () => {
    // El reparto real está muy torcido. En lineal, con un país de 400 clics y
    // el resto por debajo de 40, TODO lo demás caería en el primer tono. Sobre
    // la raíz, un país con la décima parte del máximo ya se distingue.
    expect(pasoDeColor(40, 400)).toBeGreaterThan(0);
  });
});

describe("la leyenda", () => {
  it("no repite etiqueta, que es el fallo que las personas sacaron a la luz", () => {
    // Cinco países con 1..5 personas: con la fórmula invertida de antes salían
    // dos «1+» iguales. Dos swatches distintos con el mismo número no explican
    // nada.
    const paises = [1, 2, 3, 4, 5].map((n) => pais(`p${n}`, n, 0));
    const leyenda = leyendaDe(paises, "users", 5);
    const etiquetas = leyenda.map(([, desde]) => desde);
    expect(new Set(etiquetas).size).toBe(etiquetas.length);
  });

  it("no rotula tonos que no salen en el mapa", () => {
    // El otro lado del mismo fallo: con máximo 5 los tonos 0 y 1 no le tocan a
    // nadie, y la leyenda los enseñaba igual.
    const paises = [1, 2, 3, 4, 5].map((n) => pais(`p${n}`, n, 0));
    const usados = new Set(paises.map((p) => pasoDeColor(p.users, 5)));
    for (const [paso] of leyendaDe(paises, "users", 5)) {
      expect(usados.has(paso)).toBe(true);
    }
  });

  it("enseña TODOS los tonos que sí salen", () => {
    const paises = [1, 4, 9, 40, 100].map((n) => pais(`p${n}`, n, 0));
    const usados = new Set(paises.map((p) => pasoDeColor(p.users, 100)));
    const rotulados = new Set(leyendaDe(paises, "users", 100).map(([p]) => p));
    expect(rotulados).toEqual(usados);
  });

  it("rotula cada tono con el valor MÁS BAJO que cae en él", () => {
    // «3+» tiene que significar «desde 3», así que si en ese tono hay un 3 y
    // un 5, la etiqueta es 3. Con el 5 el rótulo excluiría a un país que está
    // pintado de ese color.
    const paises = [pais("a", 9, 0), pais("b", 10, 0), pais("c", 100, 0)];
    const leyenda = leyendaDe(paises, "users", 100);
    for (const [paso, desde] of leyenda) {
      const enEseTono = paises
        .filter((p) => pasoDeColor(p.users, 100) === paso)
        .map((p) => p.users);
      expect(desde).toBe(Math.min(...enEseTono));
    }
  });

  it("va de claro a oscuro", () => {
    const paises = [1, 4, 9, 40, 100].map((n) => pais(`p${n}`, n, 0));
    const pasos = leyendaDe(paises, "users", 100).map(([p]) => p);
    expect(pasos).toEqual([...pasos].sort((a, b) => a - b));
  });

  it("un país con cero sale en la leyenda, no desaparece", () => {
    // Pasa de verdad al colorear por clics: alguien registrado, con país
    // conocido, que mira y no toca nada. Está pintado, así que su tono tiene
    // que estar explicado.
    const paises = [pais("a", 2, 0), pais("b", 2, 50)];
    const leyenda = leyendaDe(paises, "clicks", 50);
    expect(leyenda.some(([, desde]) => desde === 0)).toBe(true);
  });

  it("sin países no hay leyenda", () => {
    expect(leyendaDe([], "users", 0)).toEqual([]);
  });

  it("con un solo país la leyenda tiene un renglón", () => {
    // No cinco: cuatro de ellos no corresponderían a nada.
    expect(leyendaDe([pais("es", 3, 9)], "users", 3)).toHaveLength(1);
  });

  it("cambiar de magnitud cambia la leyenda", () => {
    // La prueba de que las dos lecturas son de verdad dos, y no la misma con
    // otro rótulo.
    const paises = [pais("a", 1, 500), pais("b", 5, 10)];
    const porGente = leyendaDe(paises, "users", 5);
    const porClics = leyendaDe(paises, "clicks", 500);
    expect(porGente).not.toEqual(porClics);
  });

  it("nunca tiene más renglones que tonos", () => {
    const muchos = Array.from({ length: 200 }, (_, i) => pais(`p${i}`, i + 1, 0));
    expect(leyendaDe(muchos, "users", 200).length).toBeLessThanOrEqual(
      TONOS.length,
    );
  });
});
