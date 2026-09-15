// Inventario de los textos en español del frontend (2026-09-15, traducción).
//
// La red de seguridad de la extracción: antes de sacar textos a claves se
// guarda la referencia, y después de cada pantalla se comprueba que ningún
// texto en español cambió ni se perdió por el camino.
//
// Uso (desde frontend/):
//   node scripts/inventario-de-textos.mjs --base   guarda la referencia
//   node scripts/inventario-de-textos.mjs          compara contra la referencia
//
// Regla: cada texto de la referencia tiene que seguir en el código o estar en
// src/i18n/es.json (con {{variables}} donde había ${...}). Si falta alguno,
// sale con código 1 y lo nombra.
import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

const RAIZ = path.resolve(import.meta.dirname, "..");
const SRC = path.join(RAIZ, "src");
const BASE = path.join(RAIZ, "i18n-inventario-base.json");
const ES = path.join(SRC, "i18n", "es.json");

const LETRA = /[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]/;
const NO_ASCII = /[ÁÉÍÓÚÜÑáéíóúüñ¿¡«»]/;
/** Atributos que no son texto de pantalla. */
const ATRIBUTOS_TECNICOS = new Set([
  "className",
  "key",
  "to",
  "href",
  "type",
  "id",
  "role",
  "name",
  "data-track",
  "viewBox",
  "fill",
  "stroke",
  "d",
  "src",
  "rel",
  "target",
  "inputMode",
  "autoComplete",
  "grupo",
]);

function archivos(dir) {
  const salida = [];
  for (const entrada of fs.readdirSync(dir, { withFileTypes: true })) {
    const ruta = path.join(dir, entrada.name);
    if (entrada.isDirectory()) {
      if (ruta === path.join(SRC, "i18n")) continue;
      salida.push(...archivos(ruta));
    } else if (/\.(ts|tsx)$/.test(entrada.name) && !/\.test\.(ts|tsx)$/.test(entrada.name)) {
      salida.push(ruta);
    }
  }
  return salida;
}

/** ¿Parece texto que lee una persona y no una clave, una clase o una ruta? */
function pareceTextoDePantalla(texto) {
  if (!LETRA.test(texto)) return false;
  if (/^(var\(|--|#|\/|\.\/|\.\.\/|https?:)/.test(texto)) return false;
  return texto.includes(" ") || NO_ASCII.test(texto) || /^[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+$/.test(texto);
}

function atributoPadre(nodo) {
  let actual = nodo.parent;
  while (actual && !ts.isSourceFile(actual)) {
    if (ts.isJsxAttribute(actual)) return actual.name.getText();
    if (ts.isJsxElement(actual) || ts.isJsxSelfClosingElement(actual)) return null;
    actual = actual.parent;
  }
  return null;
}

function esImportacion(nodo) {
  const padre = nodo.parent;
  return (
    ts.isImportDeclaration(padre) ||
    ts.isExportDeclaration(padre) ||
    (ts.isCallExpression(padre) && padre.expression.kind === ts.SyntaxKind.ImportKeyword)
  );
}

function textosDe(ruta) {
  const codigo = fs.readFileSync(ruta, "utf8");
  const tipo = ruta.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  const fuente = ts.createSourceFile(ruta, codigo, ts.ScriptTarget.Latest, true, tipo);
  const salida = [];
  const anotar = (nodo, texto) => {
    const limpio = texto.replace(/\s+/g, " ").trim();
    if (!limpio || !pareceTextoDePantalla(limpio)) return;
    const atributo = atributoPadre(nodo);
    if (atributo && ATRIBUTOS_TECNICOS.has(atributo)) return;
    salida.push(limpio);
  };
  const visitar = (nodo) => {
    if (ts.isJsxText(nodo)) {
      anotar(nodo, nodo.getText());
    } else if (ts.isStringLiteral(nodo) || ts.isNoSubstitutionTemplateLiteral(nodo)) {
      if (!esImportacion(nodo)) anotar(nodo, nodo.text);
    } else if (ts.isTemplateExpression(nodo)) {
      const partes = [nodo.head.text, ...nodo.templateSpans.map((s) => `{}${s.literal.text}`)];
      anotar(nodo, partes.join(""));
    }
    ts.forEachChild(nodo, visitar);
  };
  visitar(fuente);
  return salida;
}

function inventario() {
  const todos = new Set();
  for (const ruta of archivos(SRC)) for (const texto of textosDe(ruta)) todos.add(texto);
  return [...todos].sort((a, b) => a.localeCompare(b, "es"));
}

function valoresDe(objeto, salida = []) {
  for (const valor of Object.values(objeto)) {
    if (typeof valor === "string") {
      salida.push(valor.replace(/\{\{[^}]+\}\}/g, "{}").replace(/\s+/g, " ").trim());
    } else if (valor && typeof valor === "object") {
      valoresDe(valor, salida);
    }
  }
  return salida;
}

const actual = inventario();

if (process.argv.includes("--base")) {
  fs.writeFileSync(BASE, JSON.stringify(actual, null, 2) + "\n", "utf8");
  console.log(`Referencia guardada: ${actual.length} textos en ${path.relative(RAIZ, BASE)}`);
  process.exit(0);
}

const base = JSON.parse(fs.readFileSync(BASE, "utf8"));
const enCodigo = new Set(actual);
const enEs = valoresDe(JSON.parse(fs.readFileSync(ES, "utf8")));
const enEsSet = new Set(enEs);
// Un texto partido por una variable en JSX («Hola {x} adiós») queda en es.json
// como una sola frase: basta con que aparezca dentro de ella.
const cubierto = (texto) =>
  enCodigo.has(texto) || enEsSet.has(texto) || enEs.some((v) => v.includes(texto));

const perdidos = base.filter((texto) => !cubierto(texto));
const nuevos = actual.filter((texto) => !base.includes(texto));

console.log(
  `Referencia: ${base.length} · en el código: ${actual.length} · en es.json: ${enEs.length}`,
);
if (nuevos.length) console.log(`Textos nuevos desde la referencia: ${nuevos.length}`);
if (perdidos.length) {
  console.log(`\nTextos en español que cambiaron o se perdieron (${perdidos.length}):`);
  for (const texto of perdidos) console.log(`  · ${texto}`);
  process.exit(1);
}
console.log("Ningún texto en español cambió ni se perdió.");
