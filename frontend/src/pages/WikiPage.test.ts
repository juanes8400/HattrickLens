import { describe, expect, it } from "vitest";

import { ARTICULOS, GRUPOS } from "./wiki/contenido";
import en from "../i18n/textos/en.json";
// El FUENTE del contenido, no los datos ya evaluados: en tiempo de ejecución
// un literal en crudo y una cadena traducida son indistinguibles, y lo que
// hay que cazar es justamente la llamada que falta.
import fuente from "./wiki/contenido.ts?raw";

/**
 * La Wiki tiene que salir entera en CUALQUIER idioma.
 *
 * 2026-09-28, reportado por el usuario: «a la Wiki le falta traducir a
 * English». No le faltaba traducción. Cada artículo guardaba su grupo YA
 * TRADUCIDO --`grupo: tx("Desarrollo")`-- y el índice tenía la lista de grupos
 * en español a secas. En inglés el artículo decía «Development» y la lista
 * «Desarrollo», la comparación fallaba y el grupo entero desaparecía de la
 * pantalla. Sobrevivía «Club», que se escribe igual en los dos idiomas: la
 * Wiki enseñaba 7 artículos de 30 y parecía a medio traducir.
 *
 * El fallo no se ve en español --ahí la traducción es la identidad-- ni lo caza
 * ningún guardián de textos, porque no falta ninguna traducción: lo que sobra
 * es comparar por el texto traducido. De ahí estas pruebas.
 */

const CLAVES = GRUPOS.map((g) => g.clave);

describe("los grupos de la Wiki se comparan por clave, no por texto", () => {
  it("ningún artículo queda huérfano de grupo", () => {
    const huerfanos = ARTICULOS.filter((a) => !CLAVES.includes(a.grupo));
    expect(huerfanos.map((a) => `${a.id} → ${a.grupo}`)).toEqual([]);
  });

  it("ningún grupo del índice se queda sin artículos", () => {
    // Un grupo vacío no da error: simplemente no se pinta, y la sección
    // desaparece sin que nadie se entere. Que es justo lo que pasó.
    const vacios = CLAVES.filter(
      (clave) => !ARTICULOS.some((a) => a.grupo === clave),
    );
    expect(vacios).toEqual([]);
  });

  it("la clave de un grupo no es un texto que se traduzca", () => {
    // ESTA es la prueba que impide que vuelva a pasar. Mientras la clave no
    // esté en ningún diccionario, ningún idioma puede cambiarla, y la
    // comparación aguanta para todos los que se añadan.
    const traducibles = CLAVES.filter((clave) => clave in en);
    expect(traducibles).toEqual([]);
  });

  it("todos los artículos siguen ahí", () => {
    // El número no es decoración: el fallo se manifestaba como «faltan
    // artículos», y sin contarlos una pérdida pasa desapercibida.
    expect(ARTICULOS).toHaveLength(30);
    expect(new Set(ARTICULOS.map((a) => a.id)).size).toBe(ARTICULOS.length);
  });
});

describe("ningún texto de la Wiki se salta la traducción", () => {
  it("ninguna fórmula ni texto queda como literal suelto", () => {
    // 2026-09-28. `formula:` de «Semanas hasta el próximo nivel» era un
    // literal sin `tx()`, así que salía en español con la app en inglés y en
    // italiano. No lo cazaba ningún guardián de textos: los guardianes
    // comprueban que cada `tx()` tenga traducción, y aquí lo que faltaba era
    // el `tx()`.
    const literales = [...fuente.matchAll(/(tx\(\s*)?"((?:[^"\\]|\\.)*)"/g)]
      .filter(([, conTx]) => !conTx)
      .map(([, , crudo]) => JSON.parse(`"${crudo}"`))
      // Fuera lo que NO es texto de pantalla: la ruta del import, los `id` y
      // las claves de grupo (minúsculas y guiones), y las rutas de la app.
      .filter(
        (s) =>
          s.length >= 4 &&
          !/^[a-z0-9-]+$/.test(s) &&
          !s.startsWith("/") &&
          !s.startsWith("../"),
      )
      // Nombres propios que se escriben igual en todos los idiomas.
      .filter((s) => !/^HTMS(28)?$/.test(s));

    expect(literales).toEqual([]);
  });
});
