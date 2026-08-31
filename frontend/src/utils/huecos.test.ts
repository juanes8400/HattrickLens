import { describe, expect, it } from "vitest";

/**
 * Un hueco se dibuja con una raya, nunca con una coma.
 *
 * El descuido apareció dos veces con dos formas distintas: primero como
 * ternario (`value == null ? ", " : …`), nueve casos arreglados el
 * 2026-08-30; después como elemento JSX (`<span>, </span>`), catorce más el
 * 2026-08-31. En pantalla se ve como una coma suelta en la celda, y nadie lo
 * lee como «no hay dato»: se lee como que la interfaz está rota.
 *
 * Buscar la tercera forma a mano no funcionaría, así que se vigila el
 * síntoma —una coma sola como contenido visible— y no cada sintaxis.
 *
 * El código fuente se lee con `import.meta.glob` de Vite y no con `node:fs`:
 * el tsconfig de esta app no trae los tipos de Node, y añadir una dependencia
 * para un test de higiene sería pagar de más.
 */

const FUENTES = import.meta.glob("../**/*.{ts,tsx}", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

/** Las formas en que la coma se ha colado hasta ahora. */
const SOSPECHOSAS = [
  />,\s*<\/span>/, // <span>, </span>
  /\?\s*", "\s*:/, //  cond ? ", " : algo
  /:\s*", "\s*\}/, //  { …: ", " }
  /return\s+", "/, //  return ", "  ← la que estaba en el formateador
];

describe("los huecos no se pintan con una coma", () => {
  it("ningún fichero usa una coma suelta como valor ausente", () => {
    const culpables: string[] = [];
    for (const [ruta, texto] of Object.entries(FUENTES)) {
      if (/\.test\.tsx?$/.test(ruta)) continue;
      texto.split("\n").forEach((linea, i) => {
        if (SOSPECHOSAS.some((r) => r.test(linea))) {
          culpables.push(`${ruta.replace(/^\.\.\//, "")}:${i + 1}`);
        }
      });
    }
    expect(culpables, `usa «—» en vez de una coma:\n${culpables.join("\n")}`).toEqual([]);
  });

  it("el guardián sabe reconocer las tres formas", () => {
    // Sin esto, el test de arriba pasaría igual con las expresiones rotas.
    expect(SOSPECHOSAS.some((r) => r.test('<span className="x">, </span>'))).toBe(true);
    expect(SOSPECHOSAS.some((r) => r.test('{v == null ? ", " : v}'))).toBe(true);
    expect(SOSPECHOSAS.some((r) => r.test('{ hueco: ", " }'))).toBe(true);
    expect(SOSPECHOSAS.some((r) => r.test('  if (!iso) return ", ";'))).toBe(true);
    expect(SOSPECHOSAS.some((r) => r.test('<span>—</span>'))).toBe(false);
  });
});
