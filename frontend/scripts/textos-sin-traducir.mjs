#!/usr/bin/env node
/**
 * Lista el español que todavía no pasa por `t()` ni `tx()`.
 *
 * Traducción, 2026-09-15. El extractor (`extraer-textos.mjs`) sólo toca los
 * sitios donde está seguro de que el texto se lee en pantalla. Esto enseña lo
 * que dejó: constantes de módulo, formateadores de gráficas, textos armados
 * con `+`… para revisarlos a mano. Parece español = tiene espacio, tilde o
 * empieza en mayúscula, y no está dentro de una llamada de traducción.
 *
 *   node scripts/textos-sin-traducir.mjs [archivos…]   (por defecto, todo src)
 */
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(path.resolve("package.json"));
const ts = require("typescript");

const TRADUCTORAS = new Set(["t", "tx", "i18n.t"]);

function archivosDe(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const ruta = path.join(dir, e.name);
    if (e.isDirectory()) return e.name === "i18n" ? [] : archivosDe(ruta);
    return /\.tsx?$/.test(e.name) && !/\.test\.tsx?$/.test(e.name)
      ? [ruta]
      : [];
  });
}

function pareceEspanol(s) {
  const t = s.trim();
  if (t.length < 2 || !/[a-záéíóúñ]/i.test(t)) return false;
  if (/^(https?:|\/|\.\/|#)/.test(t)) return false;
  if (/[{}[\]]/.test(t) && !/\{\{v\d\}\}/.test(t)) return false;
  if (/^[a-z]+([A-Z_0-9-][A-Za-z0-9_-]*)+$/.test(t)) return false;
  if (/^[A-Z0-9 .+/%-]+$/.test(t)) return false;
  // Clases de Tailwind y selectores.
  if (/(^|\s)(text|bg|px|py|rounded|flex|grid|border|w|h)-/.test(t))
    return false;
  return /[áéíóúñ¿¡]/i.test(t) || (/\s/.test(t) && /[a-z]{3}/.test(t));
}

function dentroDeTraduccion(nodo) {
  for (let p = nodo.parent; p; p = p.parent) {
    if (ts.isCallExpression(p) && TRADUCTORAS.has(p.expression.getText()))
      return true;
    if (ts.isImportDeclaration(p)) return true;
  }
  return false;
}

const args = process.argv.slice(2);
const archivos = args.length ? args : archivosDe("src");
let total = 0;
for (const archivo of archivos) {
  const fuente = fs.readFileSync(archivo, "utf8");
  const sf = ts.createSourceFile(
    archivo,
    fuente,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
  const hallados = [];
  const visitar = (nodo) => {
    let texto = null;
    if (ts.isJsxText(nodo)) texto = nodo.getText();
    else if (
      ts.isStringLiteral(nodo) ||
      ts.isNoSubstitutionTemplateLiteral(nodo)
    )
      texto = nodo.text;
    else if (ts.isTemplateExpression(nodo))
      texto = [
        nodo.head.text,
        ...nodo.templateSpans.map((s) => s.literal.text),
      ].join("·");
    if (texto != null && pareceEspanol(texto) && !dentroDeTraduccion(nodo)) {
      const { line } = sf.getLineAndCharacterOfPosition(nodo.getStart());
      hallados.push(
        `  ${line + 1}: ${texto.replace(/\s+/g, " ").trim().slice(0, 110)}`,
      );
    }
    ts.forEachChild(nodo, visitar);
  };
  visitar(sf);
  if (hallados.length) {
    total += hallados.length;
    console.log(`${archivo} (${hallados.length})`);
    if (args.length) console.log(hallados.join("\n"));
  }
}
console.log(`Total: ${total}`);
