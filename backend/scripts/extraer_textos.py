"""Reúne los textos en español que el servidor manda a la pantalla.

Traducción, 2026-09-15. El servidor no se toca por dentro: sus textos se
traducen al salir, en la respuesta (ver ``app/i18n/traductor.py``). Para eso
hace falta el diccionario, y este script lista lo que hay que traducir:

* cadenas sueltas que parecen español (con tilde, o con espacio y palabras);
* plantillas de f-string, con cada hueco escrito como ``{}``:
  ``f"{nombre} está lesionado"`` queda ``"{} está lesionado"``.

LO QUE NO ES DE PANTALLA SE APARTA AQUÍ, POR SU SITIO EN EL CÓDIGO
(2026-11-14). La lista traía 113 textos sin traducir y la mitad no los ve
nadie: la descripción de un parámetro de la API, la línea de un registro, una
anotación de tipo entre comillas. Mezclados con ellos, los que sí se ven --el
progreso de la sincronización, el feed de cambios-- pasaban por ruido. Se
apartan por dónde están escritos y no por lo que dicen, así que uno nuevo del
mismo sitio tampoco entra:

* lo que documenta la API: ``description=``, ``summary=``, ``tags=``... de
  ``Query``, ``Field``, ``router.get`` y compañía;
* lo que va al registro: ``_log.warning(...)``, ``logger.info(...)``;
* las anotaciones de tipo escritas como texto;
* las cadenas sueltas que hacen de comentario bajo un campo;
* los patrones de ``re.compile``.

Lo que quede sin traducir después de esto, o se traduce o se apunta con su
motivo en ``tests/test_textos_del_servidor_traducidos.py``, que es la prueba
que vigila esta lista.

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

#: Quien documenta la API: lo que se le pasa con los nombres de abajo acaba en
#: el esquema de la API, que es para quien programa contra ella, o en una
#: cabecera. Nunca en una pantalla.
DOCUMENTAN_LA_API = frozenset(
    {
        "Query",
        "Path",
        "Body",
        "Header",
        "Cookie",
        "Field",
        "FastAPI",
        "APIRouter",
        "include_router",
        "get",
        "post",
        "put",
        "patch",
        "delete",
        "StreamingResponse",
        "ForeignKey",
    }
)
ARGUMENTOS_DE_DOCUMENTACION = frozenset(
    {
        "description",
        "summary",
        "tags",
        "title",
        "response_description",
        "media_type",
        "ondelete",
    }
)
#: Los métodos de un registro. Sólo cuentan si cuelgan de algo que se llama
#: como un registro: `resultado.error(...)` no es una línea de log.
METODOS_DE_REGISTRO = frozenset(
    {"debug", "info", "warning", "error", "exception", "critical", "log"}
)
NOMBRES_DE_REGISTRO = frozenset({"_log", "log", "logger", "_logger", "logging"})


def parece_espanol(texto: str) -> bool:
    limpio = texto.strip()
    if len(limpio) < 2 or TECNICO.search(limpio):
        return False
    if re.fullmatch(r"[a-z0-9_.\-]+", limpio):
        return False
    return bool(ACENTO.search(limpio)) or (" " in limpio and bool(PALABRA.search(limpio)))


def _todo_lo_de_dentro(nodo: ast.AST) -> set[int]:
    return {id(n) for n in ast.walk(nodo)}


def _nombre_de_la_llamada(nodo: ast.Call) -> tuple[str, str]:
    """De quién cuelga y cómo se llama: `_log.warning` es ("_log", "warning")."""
    funcion = nodo.func
    if isinstance(funcion, ast.Attribute):
        duenno = funcion.value.id if isinstance(funcion.value, ast.Name) else ""
        return duenno, funcion.attr
    if isinstance(funcion, ast.Name):
        return "", funcion.id
    return "", ""


def no_son_de_pantalla(arbol: ast.AST) -> set[int]:
    """Los nodos que, por dónde están escritos, nadie ve en una pantalla."""
    fuera: set[int] = set()
    for nodo in ast.walk(arbol):
        # Docstrings y cadenas sueltas: una expresión que es sólo un texto no
        # hace nada, sea la primera del cuerpo o el comentario de un campo.
        if isinstance(nodo, ast.Expr) and isinstance(nodo.value, ast.Constant | ast.JoinedStr):
            fuera |= _todo_lo_de_dentro(nodo.value)
        # Anotaciones de tipo escritas como texto.
        elif (isinstance(nodo, ast.arg) and nodo.annotation is not None) or isinstance(
            nodo, ast.AnnAssign
        ):
            fuera |= _todo_lo_de_dentro(nodo.annotation)
        elif isinstance(nodo, ast.Call):
            duenno, nombre = _nombre_de_la_llamada(nodo)
            if (
                (nombre in METODOS_DE_REGISTRO and duenno in NOMBRES_DE_REGISTRO)
                # Los patrones de una expresión regular.
                or (duenno == "re" and nombre == "compile")
            ):
                fuera |= _todo_lo_de_dentro(nodo)
            elif nombre in DOCUMENTAN_LA_API:
                for argumento in nodo.keywords:
                    if argumento.arg in ARGUMENTOS_DE_DOCUMENTACION:
                        fuera |= _todo_lo_de_dentro(argumento.value)
        if isinstance(nodo, ast.FunctionDef | ast.AsyncFunctionDef) and nodo.returns:
            fuera |= _todo_lo_de_dentro(nodo.returns)
    return fuera


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


def extraer(raiz: Path = RAIZ) -> list[str]:
    """Los textos de pantalla del servidor, ordenados y sin repetidos."""
    textos: set[str] = set()
    for ruta in sorted((raiz / "app").rglob("*.py")):
        try:
            arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        omitir = no_son_de_pantalla(arbol)
        dentro_de_fstring: set[int] = set()
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.JoinedStr):
                for valor in nodo.values:
                    dentro_de_fstring.add(id(valor))
                if id(nodo) in omitir:
                    continue
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
    return sorted(textos)


def main() -> None:
    textos = extraer()
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(
        json.dumps(textos, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    print(f"{len(textos)} textos -> {SALIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
