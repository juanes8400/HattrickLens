"""Un sync a medias se explica, no se descifra (2026-09-20).

La regla de la casa es vieja y está en la memoria del proyecto: en pantalla
nunca se nombra ni la interfaz de Hattrick ni sus ficheros; una fuente se
nombra por la PANTALLA de Hattrick de la que sale. El aviso de sincronización
parcial era lo último que se la saltaba, y se la saltaba en el peor sitio:
justo cuando algo ha fallado y hay que entender qué.

Esto no prueba una frase concreta --cambiarán-- sino que ningún nombre interno
se cuela por el camino de los avisos.
"""

from __future__ import annotations

import re

from app.application.commands.sync_team import FILE_LABELS, _nombre_legible

#: Los nombres internos que NO pueden aparecer en un aviso.
JERGA = (
    "players",
    "training",
    "economy",
    "teamdetails",
    "leaguedetails",
    "leaguefixtures",
    "matchesarchive",
    "matchdetails",
    "playerdetails",
    "transfersteam",
    "transfersplayer",
    "arenadetails",
    "regiondetails",
    "youthplayerlist",
    "youthplayerdetails",
    "youthteamdetails",
    "matchorders",
    "trainingevents",
    "currentbids",
    "worlddetails",
    "stafflist",
    "viewOldies",
)


def test_cada_fuente_tiene_un_nombre_que_se_puede_leer() -> None:
    for interno in JERGA:
        assert interno in FILE_LABELS, f"falta el nombre legible de «{interno}»"
        assert FILE_LABELS[interno] != interno


def test_el_identificador_se_conserva_y_el_nombre_se_traduce() -> None:
    """«matchdetails:38291» dice CUÁL falló, y eso sí sirve. Lo que sobra es la
    primera mitad."""
    assert _nombre_legible("matchdetails:38291") == "detalle de un partido 38291"
    assert _nombre_legible("players") == "plantilla (jugadores)"


def test_lo_desconocido_pasa_tal_cual_en_vez_de_desaparecer() -> None:
    """Un nombre que nadie tradujo sale como esté. Es feo y es a propósito:
    callarlo dejaría un aviso sin sujeto, que es peor que uno con jerga."""
    assert _nombre_legible("loquesea") == "loquesea"


def test_ningun_aviso_del_sync_empieza_por_un_nombre_interno() -> None:
    """Lee el código: cada `errors.append` tiene que pasar por el traductor de
    nombres o empezar por texto normal. Es la guarda contra el caso fácil de
    olvidar, que es añadir un `except` nuevo copiando el de al lado."""
    import inspect

    from app.application.commands import sync_team

    fuente = inspect.getsource(sync_team)
    sospechosas: list[str] = []
    for linea in re.findall(r"result\.errors\.append\(\s*\n?\s*(f?\"[^\"]*\")", fuente):
        texto = linea.strip('f"')
        primero = texto.split(":")[0].split(" ")[0]
        if primero in JERGA:
            sospechosas.append(linea)
    assert not sospechosas, "avisos que empiezan por un nombre interno: " + ", ".join(
        sospechosas
    )


#: Lo que tampoco puede salir en un aviso: la jerga de quien escribió el
#: modelo, no la de quien lo lee.
JERGA_ESTADISTICA = ("prior", "encogimiento", "shrinkage", "posterior", "LeagueLevel")


def _textos_de_avisos() -> list[tuple[str, str]]:
    """Cada texto que se añade a una lista de avisos (`caveats`), en todo `app`.

    POR QUÉ LA PRUEBA DE ARRIBA NO VIO «PESO DE PRIOR» (2026-11-14). Sólo
    lee `result.errors.append` dentro de la sincronización, y sólo busca
    nombres de ficheros. Los avisos de la simulación de liga van por
    `caveats.append`, en un motor, y su jerga era estadística: no los miraba
    nadie. Esto los lee todos, estén donde estén.
    """
    import ast
    from pathlib import Path

    app = Path(__file__).resolve().parents[1] / "app"
    salida: list[tuple[str, str]] = []
    for ruta in sorted(app.rglob("*.py")):
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if not (
                isinstance(nodo, ast.Call)
                and isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr == "append"
                and isinstance(nodo.func.value, ast.Name)
                and nodo.func.value.id.endswith("caveats")
            ):
                continue
            for trozo in ast.walk(nodo):
                if isinstance(trozo, ast.Constant) and isinstance(trozo.value, str):
                    salida.append((f"{ruta.name}:{nodo.lineno}", trozo.value))
    return salida


def test_ningun_aviso_lleva_jerga_ni_nombres_internos() -> None:
    textos = _textos_de_avisos()
    assert textos, "no se encontró ningún aviso: la búsqueda se ha roto"
    sospechosos = [
        f"{donde}: {texto[:60]}"
        for donde, texto in textos
        for palabra in (*JERGA_ESTADISTICA, *JERGA)
        if re.search(rf"{re.escape(palabra)}", texto, re.IGNORECASE)
        and palabra not in {"players", "training", "economy"}
    ]
    assert not sospechosos, "avisos con jerga: " + " | ".join(sospechosos)
