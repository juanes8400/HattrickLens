"""Reúne los textos en español que el servidor manda a la pantalla.

Traducción, 2026-09-15. El servidor no se toca por dentro: sus textos se
traducen al salir, en la respuesta (ver ``app/i18n/traductor.py``). Para eso
hace falta el diccionario, y este script lista lo que hay que traducir:

* cadenas sueltas que parecen español (con tilde, o con espacio y palabras);
* plantillas de f-string, con cada hueco escrito como ``{}``:
  ``f"{nombre} está lesionado"`` queda ``"{} está lesionado"``.

No toca ningún archivo del código. Escribe la lista, ordenada y sin
repetidos, en ``app/i18n/textos-extraidos.json``.

    python scripts/extraer_textos.py
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "app" / "i18n" / "textos-extraidos.json"

ACENTO = re.compile(r"[áéíóúñ¿¡]", re.IGNORECASE)
PALABRA = re.compile(r"[a-záéíóúñ]{3}", re.IGNORECASE)
# Identificadores, rutas, SQL y formatos: nunca llegan a pantalla como frase.
TECNICO = re.compile(
    r"^(https?://|/|[a-z_]+\.[a-z_]+|SELECT |INSERT |UPDATE |DELETE |%[a-z])",
    re.IGNORECASE,
)


def parece_espanol(texto: str) -> bool:
    limpio = texto.strip()
    if len(limpio) < 2 or TECNICO.search(limpio):
        return False
    if re.fullmatch(r"[a-z0-9_.\-]+", limpio):
        return False
    return bool(ACENTO.search(limpio)) or (
        " " in limpio and bool(PALABRA.search(limpio))
    )


def docstrings(arbol: ast.AST) -> set[int]:
    ids: set[int] = set()
    for nodo in ast.walk(arbol):
        if isinstance(
            nodo, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ) and nodo.body:
            primero = nodo.body[0]
            if isinstance(primero, ast.Expr) and isinstance(
                primero.value, ast.Constant
            ):
                ids.add(id(primero.value))
    return ids


def plantilla(nodo: ast.JoinedStr) -> str | None:
    partes: list[str] = []
    for valor in nodo.values:
        if isinstance(valor, ast.Constant) and isinstance(valor.value, str):
            partes.append(valor.value.replace("{", "{{").replace("}", "}}"))
        elif isinstance(valor, ast.FormattedValue):
            partes.append("{}")
        else:
            return None
    return "".join(partes)


def main() -> None:
    textos: set[str] = set()
    for ruta in sorted((RAIZ / "app").rglob("*.py")):
        try:
            arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        omitir = docstrings(arbol)
        dentro_de_fstring: set[int] = set()
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.JoinedStr):
                for valor in nodo.values:
                    dentro_de_fstring.add(id(valor))
                texto = plantilla(nodo)
                estatico = texto.replace("{}", " ") if texto else ""
                if texto and "{}" in texto and parece_espanol(estatico):
                    textos.add(texto)
        for nodo in ast.walk(arbol):
            if (
                isinstance(nodo, ast.Constant)
                and isinstance(nodo.value, str)
                and id(nodo) not in omitir
                and id(nodo) not in dentro_de_fstring
                and parece_espanol(nodo.value)
            ):
                textos.add(nodo.value)
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(
        json.dumps(sorted(textos), ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    print(f"{len(textos)} textos -> {SALIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
