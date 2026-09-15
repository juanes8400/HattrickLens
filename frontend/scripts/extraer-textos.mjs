#!/usr/bin/env node
/**
 * Envuelve los textos en español de una pantalla con `tx("…")`.
 *
 * Traducción, 2026-09-15. Con miles de textos por traducir, ponerles clave a
 * mano uno por uno no terminaba nunca. Esto hace el trabajo mecánico y deja
 * el español EXACTAMENTE igual en pantalla: `tx` devuelve el propio texto
 * cuando no hay traducción.
 *
 * Sólo toca textos en sitios que se leen en pantalla:
 *   · el texto suelto dentro de JSX;
 *   · atributos de texto (`title`, `aria-label`, `placeholder`, `meta`…);
 *   · cualquier atributo de un componente propio, si parece una frase;
 *   · propiedades de objeto que son rótulos (`label`, `header`, `title`…);
 *   · y dentro de esos sitios, las ramas de un `?:`, de `??`, `||`, `&&` y el
 *     cuerpo de una flecha (`render: (r) => "…"`).
 *
 * Nunca toca comparaciones, claves, rutas, clases ni argumentos de funciones.
 * Lo que no sabe hacer lo deja como está y lo lista con `--pendientes`.
 *
 *   node scripts/extraer-textos.mjs src/pages/X.tsx [--dry]
 *
 * Escribe la lista de textos nuevos en `scripts/.textos-extraidos.json`.
 */
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(path.resolve("package.json"));
const ts = require("typescript");

const args = process.argv.slice(2);
const seco = args.includes("--dry");
const archivos = args.filter((a) => !a.startsWith("--"));

const ATRIBUTOS_DE_TEXTO = new Set([
  "title",
  "aria-label",
  "ariaLabel",
  "placeholder",
  "alt",
  "label",
  "meta",
  "ayuda",
  "hint",
  "texto",
  "emptyMessage",
  "filterPlaceholder",
  "equilibriumLabel",
  "eventsLabel",
  "tuLabel",
  "rivalLabel",
]);

const ATRIBUTOS_EXCLUIDOS = new Set([
  "className",
  "key",
  "to",
  "href",
  "id",
  "htmlFor",
  "csvName",
  "grupo",
  "seccion",
  "calculo",
  "type",
  "name",
  "role",
  "initialSort",
  "modo",
  "tone",
  "variant",
  "size",
  "align",
  "color",
  "active",
  "activa",
  "severity",
  "kind",
  "position",
  "code",
  "country",
  "specialty",
  "fallback",
  "stroke",
  "fill",
]);

const PROPIEDADES_DE_TEXTO = new Set([
  "label",
  "header",
  "title",
  "meta",
  "ayuda",
  "hint",
  "texto",
  "detail",
  "emptyMessage",
  "filterPlaceholder",
  "placeholder",
  "render",
  "titulo",
  "pista",
  "cause",
  "mensaje",
  "descripcion",
  "subtitulo",
  "resumen",
]);

/** ¿Parece texto para leer y no un identificador? */
function esTexto(s, fuerza) {
  const t = s.trim();
  if (!t) return false;
  if (!/[A-Za-zÁÉÍÓÚÑáéíóúñü]/.test(t)) return false;
  if (/^(https?:|\/|\.\/|#)/.test(t)) return false;
  // Identificadores: camelCase, snake_case, rutas, clases de Tailwind.
  if (/^[a-z]+([A-Z_0-9-][A-Za-z0-9_-]*)+$/.test(t)) return false;
  if (/[[\]{}]/.test(t)) return false;
  // Siglas sueltas: TSI, PIC, HTMS28.
  if (/^[A-Z0-9 .+/%-]+$/.test(t)) return false;
  if (fuerza === "debil")
    return /\s/.test(t) || /[áéíóúñ¿¡]/i.test(t) || /^[A-ZÁÉÍÓÚÑ]/.test(t);
  return true;
}

function nombreDeEtiqueta(atributo) {
  const apertura = atributo.parent.parent;
  return apertura.tagName ? apertura.tagName.getText() : "";
}

/** "fuerte", "debil" o null: si el texto está en un sitio de pantalla. */
function contexto(nodo) {
  let hijo = nodo;
  let padre = nodo.parent;
  while (padre) {
    if (
      ts.isParenthesizedExpression(padre) ||
      ts.isAsExpression(padre) ||
      ts.isNonNullExpression(padre)
    ) {
      hijo = padre;
      padre = padre.parent;
      continue;
    }
    if (ts.isConditionalExpression(padre)) {
      if (hijo === padre.condition) return null;
      hijo = padre;
      padre = padre.parent;
      continue;
    }
    if (ts.isBinaryExpression(padre)) {
      const op = padre.operatorToken.kind;
      const vale =
        op === ts.SyntaxKind.QuestionQuestionToken ||
        op === ts.SyntaxKind.BarBarToken ||
        op === ts.SyntaxKind.AmpersandAmpersandToken;
      if (vale && hijo === padre.right) {
        hijo = padre;
        padre = padre.parent;
        continue;
      }
      return null;
    }
    if (ts.isArrowFunction(padre) && hijo === padre.body) {
      hijo = padre;
      padre = padre.parent;
      continue;
    }
    if (ts.isJsxExpression(padre)) {
      if (ts.isJsxAttribute(padre.parent)) {
        hijo = padre;
        padre = padre.parent;
        continue;
      }
      return "fuerte";
    }
    if (ts.isJsxAttribute(padre)) {
      const nombre = padre.name.getText();
      if (ATRIBUTOS_DE_TEXTO.has(nombre)) return "fuerte";
      if (
        /^[A-Z]/.test(nombreDeEtiqueta(padre)) &&
        !ATRIBUTOS_EXCLUIDOS.has(nombre) &&
        !nombre.startsWith("on") &&
        !nombre.startsWith("data-")
      )
        return "debil";
      return null;
    }
    if (ts.isPropertyAssignment(padre) && hijo === padre.initializer) {
      const nombre = padre.name.getText().replace(/["']/g, "");
      return PROPIEDADES_DE_TEXTO.has(nombre) ? "fuerte" : null;
    }
    return null;
  }
  return null;
}

/** El texto de JSX tal como lo pinta React: el mismo recorte de líneas. */
function limpiarJsx(crudo) {
  const lineas = crudo.split(/\r\n|\n|\r/);
  let ultima = 0;
  lineas.forEach((l, i) => {
    if (/[^ \t]/.test(l)) ultima = i;
  });
  let texto = "";
  lineas.forEach((l, i) => {
    let recorte = l.replace(/\t/g, " ");
    if (i !== 0) recorte = recorte.replace(/^[ ]+/, "");
    if (i !== lineas.length - 1) recorte = recorte.replace(/[ ]+$/, "");
    if (recorte) {
      if (i !== ultima) recorte += " ";
      texto += recorte;
    }
  });
  return texto;
}

const extraidos = new Set();
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
  const cambios = [];

  const visitar = (nodo) => {
    // JSX suelto.
    if (ts.isJsxText(nodo)) {
      const crudo = nodo.getFullText();
      if (/&[a-z#0-9]+;/i.test(crudo)) return;
      const limpio = limpiarJsx(crudo);
      const nucleo = limpio.trim();
      if (!esTexto(nucleo, "fuerte")) return;
      const antes = limpio.startsWith(" ") ? '{" "}' : "";
      const despues = limpio.endsWith(" ") ? '{" "}' : "";
      cambios.push({
        inicio: nodo.getFullStart(),
        fin: nodo.getEnd(),
        texto: `${antes}{tx(${JSON.stringify(nucleo)})}${despues}`,
      });
      extraidos.add(nucleo);
      return;
    }

    if (ts.isStringLiteral(nodo) || ts.isNoSubstitutionTemplateLiteral(nodo)) {
      const fuerza = contexto(nodo);
      if (fuerza && esTexto(nodo.text, fuerza)) {
        const llamada = `tx(${JSON.stringify(nodo.text)})`;
        const directo = ts.isJsxAttribute(nodo.parent);
        cambios.push({
          inicio: nodo.getStart(),
          fin: nodo.getEnd(),
          texto: directo ? `{${llamada}}` : llamada,
        });
        extraidos.add(nodo.text);
      }
      return;
    }

    if (ts.isTemplateExpression(nodo)) {
      const fuerza = contexto(nodo);
      const estatico = [
        nodo.head.text,
        ...nodo.templateSpans.map((s) => s.literal.text),
      ].join(" ");
      if (fuerza && esTexto(estatico, fuerza)) {
        let clave = nodo.head.text;
        const valores = [];
        nodo.templateSpans.forEach((span, i) => {
          clave += `{{v${i}}}${span.literal.text}`;
          valores.push(`v${i}: ${span.expression.getText()}`);
        });
        cambios.push({
          inicio: nodo.getStart(),
          fin: nodo.getEnd(),
          texto: `tx(${JSON.stringify(clave)}, { ${valores.join(", ")} })`,
        });
        extraidos.add(clave);
        return;
      }
    }

    ts.forEachChild(nodo, visitar);
  };
  visitar(sf);

  if (cambios.length === 0) {
    console.log(`${archivo}: nada que extraer`);
    continue;
  }
  total += cambios.length;
  let nuevo = fuente;
  for (const c of cambios.sort((a, b) => b.inicio - a.inicio)) {
    nuevo = nuevo.slice(0, c.inicio) + c.texto + nuevo.slice(c.fin);
  }
  if (!/import \{ tx \} from/.test(nuevo)) {
    const destino = path.resolve("src/i18n/tx");
    let relativa = path
      .relative(path.dirname(path.resolve(archivo)), destino)
      .replace(/\\/g, "/");
    if (!relativa.startsWith(".")) relativa = `./${relativa}`;
    const importacion = `import { tx } from "${relativa}";\n`;
    const imports = [
      ...nuevo.matchAll(/^import [\s\S]*?from ["'][^"']+["'];?\s*$/gm),
    ];
    const ultimo = imports[imports.length - 1];
    const donde = ultimo ? ultimo.index + ultimo[0].length + 1 : 0;
    nuevo = nuevo.slice(0, donde) + importacion + nuevo.slice(donde);
  }
  console.log(`${archivo}: ${cambios.length} textos`);
  if (!seco) fs.writeFileSync(archivo, nuevo, "utf8");
}

const salida = path.resolve("scripts/.textos-extraidos.json");
const previos = fs.existsSync(salida)
  ? JSON.parse(fs.readFileSync(salida, "utf8"))
  : [];
const todos = [...new Set([...previos, ...extraidos])].sort();
if (!seco) fs.writeFileSync(salida, JSON.stringify(todos, null, 2) + "\n");
console.log(`Total: ${total} cambios, ${extraidos.size} textos distintos`);
