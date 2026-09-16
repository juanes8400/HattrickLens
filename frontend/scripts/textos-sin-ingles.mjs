// Lo que se vería en español aunque la app esté en inglés (2026-09-16).
//
// Recorre el código y saca las dos formas de pedir un texto:
//
//   · `tx("texto en español")`   -> su traducción vive en i18n/textos/en.json
//   · `t("clave", "respaldo")`   -> vive en i18n/en.json, por su clave
//
// Y lista las que no tienen inglés: ésas caen al español por diseño, así que
// son justo las que hay que revisar.
//
// Uso (desde frontend/):  node scripts/textos-sin-ingles.mjs
import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

const RAIZ = path.resolve(import.meta.dirname, "..");
const SRC = path.join(RAIZ, "src");
const TEXTOS = JSON.parse(
  fs.readFileSync(path.join(SRC, "i18n", "textos", "en.json"), "utf8"),
);
const CLAVES = JSON.parse(
  fs.readFileSync(path.join(SRC, "i18n", "en.json"), "utf8"),
);

function archivos(dir) {
  const salida = [];
  for (const entrada of fs.readdirSync(dir, { withFileTypes: true })) {
    const ruta = path.join(dir, entrada.name);
    if (entrada.isDirectory()) {
      if (ruta === path.join(SRC, "i18n")) continue;
      salida.push(...archivos(ruta));
    } else if (/\.(ts|tsx)$/.test(entrada.name) && !/\.test\./.test(entrada.name)) {
      salida.push(ruta);
    }
  }
  return salida;
}

/** El texto de un literal, uniendo las concatenaciones con +. */
function literal(nodo) {
  if (ts.isStringLiteral(nodo) || ts.isNoSubstitutionTemplateLiteral(nodo)) {
    return nodo.text;
  }
  if (
    ts.isBinaryExpression(nodo) &&
    nodo.operatorToken.kind === ts.SyntaxKind.PlusToken
  ) {
    const izq = literal(nodo.left);
    const der = literal(nodo.right);
    return izq != null && der != null ? izq + der : null;
  }
  return null;
}

function enClaves(clave) {
  return clave.split(".").reduce((n, parte) => (n == null ? n : n[parte]), CLAVES);
}

const faltanTx = new Map();
const faltanClave = new Map();

for (const ruta of archivos(SRC)) {
  const fuente = ts.createSourceFile(
    ruta,
    fs.readFileSync(ruta, "utf8"),
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
  const relativa = path.relative(RAIZ, ruta);
  const visitar = (nodo) => {
    if (ts.isCallExpression(nodo) && ts.isIdentifier(nodo.expression)) {
      const nombre = nodo.expression.text;
      if (nombre === "tx" && nodo.arguments.length > 0) {
        const texto = literal(nodo.arguments[0]);
        if (texto && !(texto in TEXTOS)) {
          if (!faltanTx.has(texto)) faltanTx.set(texto, relativa);
        }
      }
      if (nombre === "t" && nodo.arguments.length >= 2) {
        const clave = literal(nodo.arguments[0]);
        const respaldo = literal(nodo.arguments[1]);
        if (clave && respaldo && typeof enClaves(clave) !== "string") {
          if (!faltanClave.has(clave)) faltanClave.set(clave, `${relativa} · ${respaldo}`);
        }
      }
    }
    ts.forEachChild(nodo, visitar);
  };
  visitar(fuente);
}

console.log(`tx() sin inglés: ${faltanTx.size}`);
for (const [texto, donde] of faltanTx) {
  console.log(`  · ${JSON.stringify(texto).slice(0, 110)}  (${donde})`);
}
console.log(`\nclaves t() sin inglés: ${faltanClave.size}`);
for (const [clave, donde] of faltanClave) {
  console.log(`  · ${clave}  (${donde})`);
}
process.exitCode = faltanTx.size + faltanClave.size > 0 ? 1 : 0;
