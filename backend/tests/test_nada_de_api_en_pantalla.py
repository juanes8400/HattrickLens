"""Ninguna referencia a la API puede llegar al usuario.

2026-08-31, orden explícita del usuario: «Cualquier referencia a CHPP no debe
ser vista por los usuarios en ningún momento. BORRAR». Cubre las dos formas en
que se colaba: el nombre de la API y el nombre de sus ficheros —`training.xml`,
`stafflist.xml`, `leaguefixtures.xml`—, que en un texto de pantalla no le dicen
nada a nadie y delatan la tubería.

Esto no vigila comentarios ni docstrings, que nadie ve. Vigila las cadenas que
de verdad se pintan, y por eso barre los ficheros que las contienen buscando
literales, no ejecutando cada motor: una alerta que sólo salta con cierta
plantilla se escaparía de una prueba que sólo mirase la salida.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"

#: Todo lo que no puede aparecer en una cadena que acabe en pantalla.
PROHIBIDO = ("CHPP", ".xml")

#: Módulos cuyas cadenas SÍ llegan al usuario: motores que redactan avisos,
#: consultas que arman etiquetas y los endpoints que las sirven.
DONDE_MIRAR = (
    "domain/engines",
    "application/queries",
    "api/v1/endpoints",
)

#: La conexión con Hattrick tiene que poder nombrar sus propias rutas: son
#: direcciones, no texto de pantalla.
SE_PERDONAN = ("auth_chpp.py", "chpp_gateway.py")


def _literales(fichero: Path) -> list[tuple[int, str]]:
    """Las cadenas del módulo. Los docstrings quedan fuera: no se pintan."""
    arbol = ast.parse(fichero.read_text(encoding="utf-8"))
    docs = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            cuerpo = getattr(nodo, "body", [])
            if (
                cuerpo
                and isinstance(cuerpo[0], ast.Expr)
                and isinstance(cuerpo[0].value, ast.Constant)
                and isinstance(cuerpo[0].value.value, str)
            ):
                docs.add(id(cuerpo[0].value))
    return [
        (n.lineno, n.value)
        for n in ast.walk(arbol)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs
    ]


def test_ninguna_cadena_de_pantalla_nombra_la_api() -> None:
    culpables: list[str] = []
    for carpeta in DONDE_MIRAR:
        for fichero in sorted((APP / carpeta).rglob("*.py")):
            if fichero.name in SE_PERDONAN:
                continue
            for linea, texto in _literales(fichero):
                # Una cadena corta sin espacios es una clave o una ruta, no
                # una frase para leer. Lo que se pinta tiene palabras.
                if " " not in texto and len(texto) < 40:
                    continue
                for prohibido in PROHIBIDO:
                    if prohibido in texto:
                        culpables.append(
                            f"{fichero.relative_to(APP)}:{linea} → {texto[:90]!r}"
                        )
    assert not culpables, "referencias a la API en texto de pantalla:\n" + "\n".join(culpables)
