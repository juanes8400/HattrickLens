"""El índice de `docs/INDICE.md` no puede envejecer en silencio.

Es lo que mató a los documentos de arquitectura escritos a mano: `05-frontend.md`
sigue describiendo un Next.js que nunca se construyó, y nadie se enteró porque
nada falla cuando un documento miente. Aquí sí falla.

Y de paso cae un fallo de verdad: que el frontend pida una ruta que el backend
ya no sirve. Eso no lo ve ni el compilador --la ruta es una cadena-- ni los
tests de cada lado por separado; se ve en producción, como un 404.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
indice = importlib.import_module("scripts.indice")


def test_toda_ruta_que_pide_el_frontend_la_sirve_el_backend() -> None:
    # La lista de rutas declaradas se le pide al indexador en vez de volver a
    # recorrer los decoradores aquí: tener dos copias ya salió mal una vez, al
    # partir `analysis.py` en un paquete el índice aprendió a entrar y esta
    # copia no, y el test falló por su propia cuenta.
    declaradas, _ = indice.rutas_declaradas()

    pedidas: set[str] = set()
    for rutas in indice.api_a_rutas().values():
        pedidas.update(indice.normalizar(ruta) for ruta in rutas)
    huerfanas = sorted(pedidas - set(declaradas))
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


def test_el_indice_ve_a_traves_de_las_fachadas() -> None:
    """Si una pantalla usa la capa de datos, el indice tiene que verlo.

    Al partir `services/api.ts` y `useTeam.ts` quedo una fachada que solo
    reexporta --`export { useClub } from "./club"`--, y el recorrido se paraba
    ahi: once pantallas pasaron a figurar como que no piden datos a nadie.
    Compilaba, los tests pasaban y el indice mentia.
    """
    comp2f = indice.fichero_de_componente()
    api = indice.api_a_rutas()
    ciegas = []
    for ruta, comp in indice.rutas_de_app():
        f = comp2f.get(comp)
        if not f or not f.exists():
            continue
        # Lo que delata que una pantalla PIDE datos es que importe un hook
        # `use…` de useTeam o que llame a `api.`. `ConnectedPage` importa
        # `setActiveTeamId`, que escribe en localStorage y no pide nada: no
        # tiene por que figurar, y exigirselo seria exigir una mentira.
        fuentes = indice.leer(f)
        pide = bool(re.search(r"\bapi\.\w", fuentes)) or any(
            re.search(r"\buse[A-Z]\w*", " ".join(nombres))
            for nombres, modulo in indice.importaciones(fuentes)
            if modulo.endswith(("hooks/useTeam", "services/api"))
        )
        if not pide:
            continue
        miembros, _ = indice.alcance(f)
        if not (miembros & set(api)):
            ciegas.append((ruta, f.name))
    assert not ciegas, (
        "pantallas que usan la capa de datos y el indice no ve que pidan nada; "
        f"suele ser una fachada que reexporta y que `alcance` no sigue: {ciegas}"
    )
