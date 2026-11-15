import ts from "typescript";
import { describe, expect, it } from "vitest";
import en from "./textos/en.json";
import de from "./textos/de.json";
import it_ from "./textos/it.json";
import pl from "./textos/pl.json";

/** Cada `tx("…")` del código tiene su traducción en los cuatro idiomas.
 *
 *  2026-11-15, revisión de QA. `idioma.test.ts` sólo comparaba los
 *  diccionarios entre sí; nada miraba el CÓDIGO. Así pasaron dos frases en
 *  español en todos los idiomas: la explicación de la predicción en Copa (el
 *  texto cambió el 2026-11-07 y el diccionario se quedó con el viejo) y «modelo
 *  simple por TSI, no calibrado» en la ficha del rival, sin traducir desde
 *  septiembre. El script `scripts/textos-sin-ingles.mjs` lo veía, pero no lo
 *  ejecutaba nadie.
 *
 *  El código se lee con `import.meta.glob` y no con `node:fs`, como en
 *  `utils/huecos.test.ts`: el tsconfig de la app no trae los tipos de Node.
 */

/** Todo el código de `src` salvo las pruebas y los propios diccionarios. */
const FUENTES = import.meta.glob(
  ["../**/*.{ts,tsx}", "!../**/*.test.{ts,tsx}", "!../i18n/**"],
  { query: "?raw", import: "default", eager: true },
) as Record<string, string>;

const DICCIONARIOS: Record<string, Record<string, string>> = {
  en,
  de,
  it: it_,
  pl,
};

/** Lo que se escribe igual en todos los idiomas: nombres propios, siglas y los
 *  títulos originales de las publicaciones del autor. Añadir aquí es decir
 *  «esto NO se traduce», no «ya lo traduciré». */
const INVARIABLES = new Set([
  "Log(TSI+1)",
  "HatStats",
  "PlayerID",
  "Hattrick Masters",
  "Wiki",
  "vs",
  "vs.",
  "{{v0}} vs. {{v1}}",
  "Juan Esteban de la Calle",
  "Pulgas Arrechas",
  "V.92 · Colombia",
  "· Medium",
]);

/** Las publicaciones del autor (`AutorPage`) van con su título original. */
const ES_TITULO_DE_PUBLICACION = (ruta: string) =>
  ruta.endsWith("/AutorPage.tsx");

/** El texto de un literal, uniendo las concatenaciones con `+`. */
function literal(n: ts.Node): string | null {
  if (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)) {
    return n.text;
  }
  if (
    ts.isBinaryExpression(n) &&
    n.operatorToken.kind === ts.SyntaxKind.PlusToken
  ) {
    const a = literal(n.left);
    const b = literal(n.right);
    return a != null && b != null ? a + b : null;
  }
  return null;
}

/** Todos los `tx("…")` literales del código, con el fichero donde salen. */
function textosDelCodigo(): Map<string, string> {
  const vistos = new Map<string, string>();
  for (const [ruta, codigo] of Object.entries(FUENTES)) {
    if (ES_TITULO_DE_PUBLICACION(ruta)) continue;
    const fuente = ts.createSourceFile(
      ruta,
      codigo,
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TSX,
    );
    const visitar = (n: ts.Node) => {
      if (
        ts.isCallExpression(n) &&
        ts.isIdentifier(n.expression) &&
        n.expression.text === "tx" &&
        n.arguments.length > 0
      ) {
        const texto = literal(n.arguments[0]!);
        if (texto && !vistos.has(texto)) {
          vistos.set(texto, ruta.replace(/^\.\.\//, ""));
        }
      }
      ts.forEachChild(n, visitar);
    };
    visitar(fuente);
  }
  return vistos;
}

describe("los textos del código están traducidos", () => {
  const textos = textosDelCodigo();

  it("encuentra los textos (si no, la prueba no prueba nada)", () => {
    expect(textos.size).toBeGreaterThan(2000);
  });

  for (const [idioma, dic] of Object.entries(DICCIONARIOS)) {
    it(`todos tienen ${idioma}`, () => {
      const faltan = [...textos]
        .filter(([t]) => !(t in dic) && !INVARIABLES.has(t))
        .map(([t, f]) => `${f}: ${t}`);
      expect(faltan).toEqual([]);
    });
  }
});
