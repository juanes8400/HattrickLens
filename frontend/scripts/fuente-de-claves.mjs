// El español de cada clave `t("clave", "respaldo")`, sacado del código.
//
// 2026-09-21, al traducir al italiano. `es.json` está vacío a propósito: el
// español de una clave vive en su respaldo, dentro del código. Para traducir
// a un idioma nuevo hace falta ESE español y no el inglés ya traducido, o se
// traduce una traducción y los errores se acumulan.
//
// Uso (desde frontend/):
//   node scripts/fuente-de-claves.mjs > ../claves-es.json
import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

const RAIZ = path.resolve(import.meta.dirname, "..");
const SRC = path.join(RAIZ, "src");

function archivos(dir) {
  const salida = [];
  for (const entrada of fs.readdirSync(dir, { withFileTypes: true })) {
    const ruta = path.join(dir, entrada.name);
    if (entrada.isDirectory()) salida.push(...archivos(ruta));
    else if (/\.(ts|tsx)$/.test(entrada.name) && !/\.test\./.test(entrada.name))
      salida.push(ruta);
  }
  return salida;
}

const literal = (nodo) =>
  nodo && (ts.isStringLiteral(nodo) || ts.isNoSubstitutionTemplateLiteral(nodo))
    ? nodo.text
    : null;

const claves = {};
for (const ruta of archivos(SRC)) {
  const fuente = ts.createSourceFile(
    ruta,
    fs.readFileSync(ruta, "utf8"),
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
  const visitar = (nodo) => {
    if (
      ts.isCallExpression(nodo) &&
      ts.isIdentifier(nodo.expression) &&
      nodo.expression.text === "t" &&
      nodo.arguments.length >= 2
    ) {
      const clave = literal(nodo.arguments[0]);
      const respaldo = literal(nodo.arguments[1]);
      if (clave && respaldo && !(clave in claves)) claves[clave] = respaldo;
    }
    ts.forEachChild(nodo, visitar);
  };
  visitar(fuente);
}

const ordenadas = Object.fromEntries(
  Object.keys(claves)
    .sort()
    .map((c) => [c, claves[c]]),
);
process.stdout.write(JSON.stringify(ordenadas, null, 2) + "\n");
