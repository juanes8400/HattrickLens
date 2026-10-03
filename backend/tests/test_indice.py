"""El índice de `docs/INDICE.md` no puede envejecer en silencio.

Es lo que mató a los documentos de arquitectura escritos a mano: `05-frontend.md`
sigue describiendo un Next.js que nunca se construyó, y nadie se enteró porque
nada falla cuando un documento miente. Aquí sí falla.

Y de paso cae un fallo de verdad: que el frontend pida una ruta que el backend
ya no sirve. Eso no lo ve ni el compilador --la ruta es una cadena-- ni los
tests de cada lado por separado; se ve en producción, como un 404.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
indice = importlib.import_module("scripts.indice")


def test_toda_ruta_que_pide_el_frontend_la_sirve_el_backend() -> None:
    pref = indice.prefijos()
    declaradas: set[str] = set()
    for p in sorted((indice.BACK / "api" / "v1" / "endpoints").glob("*.py")):
        arbol = indice.arbol(indice.modulo_de(p))
        if arbol is None:
            continue
        for nodo in arbol.body:
            if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in nodo.decorator_list:
                if not isinstance(dec, ast.Call):
                    continue
                fn = dec.func
                if not (isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name)):
                    continue
                if fn.value.id != "router" or not dec.args:
                    continue
                arg = dec.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    declaradas.add(indice.normalizar(pref.get(p.stem, "") + arg.value))

    pedidas: set[str] = set()
    for rutas in indice.api_a_rutas().values():
        pedidas.update(indice.normalizar(ruta) for ruta in rutas)
    huerfanas = sorted(pedidas - declaradas)
    assert not huerfanas, (
        "services/api.ts pide rutas que ningún endpoint declara, o sea 404 en "
        f"producción: {huerfanas}"
    )


def test_cada_pantalla_de_la_aplicacion_tiene_su_fichero() -> None:
    comp2f = indice.fichero_de_componente()
    sueltas = [
        (ruta, comp)
        for ruta, comp in indice.rutas_de_app()
        if not comp2f.get(comp, Path("x")).exists()
    ]
    assert not sueltas, f"rutas de App.tsx cuya página no se encuentra: {sueltas}"


def test_el_indice_esta_al_dia() -> None:
    doc = RAIZ / "docs" / "INDICE.md"
    assert doc.exists(), "falta docs/INDICE.md: correr `python backend/scripts/indice.py`"
    texto = doc.read_text(encoding="utf-8")
    faltan = [ruta for ruta, _ in indice.rutas_de_app() if f"### `/{ruta}`" not in texto]
    assert not faltan, (
        "hay pantallas que no están en docs/INDICE.md; correr "
        f"`python backend/scripts/indice.py`: {faltan}"
    )
