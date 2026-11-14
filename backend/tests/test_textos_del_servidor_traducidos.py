"""Ninguna frase del servidor llega a pantalla sin traducir (2026-11-14).

La revisión del 2026-11-10 contó 113 textos del servidor que no estaban en el
diccionario. La mitad no los ve nadie --descripciones de la API, líneas del
registro-- y `scripts/extraer_textos.py` ya los aparta por su sitio en el
código. Pero entre los que quedaban había de los que sí se ven: el progreso de
la sincronización («Mirando el mercado de transferencias...»), el feed de la
academia («Salió de la academia»), los avisos del cartel de sincronización
parcial. Un manager en inglés los leía en español.

Esta prueba es la guarda. Cada texto que el extractor encuentra tiene que
estar en los cuatro diccionarios o en `EXENTOS`, con el motivo escrito. Un
texto nuevo sin traducir hace fallar la prueba, que es justo lo que se quiere:
la decisión de no traducirlo se toma a propósito y queda apuntada aquí.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
I18N = RAIZ / "app" / "i18n"
IDIOMAS = ("en", "de", "it", "pl")

extraer_textos = importlib.import_module("scripts.extraer_textos")

#: Los que no se traducen, y por qué. El motivo es obligatorio: «no se ve» sin
#: decir por qué no se ve no vale, porque es justo lo que hay que comprobar.
_DETALLE_DE_UN_FALLO = (
    "detalle de un error HTTP que sólo sale si se pide un equipo o jugador "
    "ajeno o inexistente; la pantalla de error enseña el estado, no este texto"
)
_EXCEPCION_INTERNA = (
    "excepción de un motor que nunca llega a una respuesta: es un error de programación"
)
_CABECERA = "valor de una cabecera HTTP o de un formato de registro, no una frase"

EXENTOS: dict[str, str] = {
    # Cabeceras y formatos.
    "%(levelname)-8s %(name)s: %(message)s": _CABECERA,
    'W/"dash-{}-{}"': _CABECERA,
    'attachment; filename="uso-htlens-{}.csv"': _CABECERA,
    "private, max-age=30": _CABECERA,
    "public, max-age=31536000, immutable": _CABECERA,
    # Detalles de 404 en inglés.
    "no economy data for team {}": _DETALLE_DE_UN_FALLO,
    "no played matches for team {}": _DETALLE_DE_UN_FALLO,
    "no ratings for match {}": _DETALLE_DE_UN_FALLO,
    "no stadium history for team {}": _DETALLE_DE_UN_FALLO,
    "no standings for team {}": _DETALLE_DE_UN_FALLO,
    "player {} not found": _DETALLE_DE_UN_FALLO,
    "player {} not found in team {}": _DETALLE_DE_UN_FALLO,
    "player {} not found on team {}": _DETALLE_DE_UN_FALLO,
    "team {} not found": _DETALLE_DE_UN_FALLO,
    "team {} or player {} not found": _DETALLE_DE_UN_FALLO,
    "ventana de comparación desconocida: {}": (
        "400 de un parámetro que la pantalla elige de una lista cerrada"
    ),
    # Excepciones de los motores.
    "The HT-Tools technical formula has no mode for skill={}. "
    "Stamina uses a separate reference engine.": _EXCEPCION_INTERNA,
    "assistant_level_sum={} exceeds the formula cap of {} ({} assistants x level {}). "
    "It must be a sum of levels, not an assistant count.": _EXCEPCION_INTERNA,
    "current_sublevel must be in the interval [0, 1).": _EXCEPCION_INTERNA,
    "days must be in [0, 112)": _EXCEPCION_INTERNA,
    "skill level must be >= 0": _EXCEPCION_INTERNA,
    "sub_level must be in [0, 1)": _EXCEPCION_INTERNA,
    "unknown position: {}": _EXCEPCION_INTERNA,
    "unknown special role: {}": _EXCEPCION_INTERNA,
    "no parser registered for CHPP file '{}'": _EXCEPCION_INTERNA,
    # Lo que se cita tal cual.
    "{} | pedido: {}": (
        "lo que contestó Hattrick al rechazar una búsqueda, citado tal cual en "
        "el aviso: es lo único que sirve para reportarlo"
    ),
    "respuesta sin TransferSearch": (
        "mismo camino que el anterior: el motivo de un rechazo, citado tal cual"
    ),
    # Trozos y claves.
    "subió": "trozo de «{}: {} subió de {} a {}», que sí está traducida entera",
    "bajó": "trozo de «{}: {} bajó de {} a {}», que sí está traducida entera",
    "otra gente": ("clave del campo `kind`, que el traductor no toca: la pantalla pone su título"),
    "PIC · {}": (
        "siglas de la comunidad de Hattrick para la actitud, iguales en todos los "
        "idiomas; el hueco es el nombre del rival"
    ),
    "MOTS · {}": (
        "siglas de la comunidad de Hattrick para la actitud, iguales en todos los "
        "idiomas; el hueco es el nombre del rival"
    ),
    "HT-Tools community formula": (
        "nombre interno del motor en su ficha técnica; ninguna pantalla lo pinta"
    ),
    "Extra 1": "categoría de jugador sin ningún llamador",
    "Extra 2": "categoría de jugador sin ningún llamador",
}


def _diccionario(idioma: str) -> dict[str, str]:
    leido: dict[str, str] = json.loads((I18N / f"{idioma}.json").read_text(encoding="utf-8"))
    return leido


def test_la_lista_guardada_es_la_que_sale_del_codigo() -> None:
    """Si alguien añade un texto y no regenera la lista, esto lo dice."""
    guardada = json.loads((I18N / "textos-extraidos.json").read_text(encoding="utf-8"))
    assert guardada == extraer_textos.extraer(RAIZ), (
        "textos-extraidos.json no está al día: python scripts/extraer_textos.py"
    )


def test_cada_texto_esta_traducido_o_exento_con_su_motivo() -> None:
    textos = extraer_textos.extraer(RAIZ)
    for idioma in IDIOMAS:
        dic = _diccionario(idioma)
        faltan = [t for t in textos if t not in dic and t not in EXENTOS]
        assert not faltan, (
            f"{len(faltan)} textos del servidor sin traducir al «{idioma}». "
            "Tradúcelos con el glosario oficial, o apúntalos en EXENTOS con su "
            "motivo: " + " | ".join(faltan[:10])
        )


def test_ningun_exento_sobra() -> None:
    """Un exento que ya no sale del código es una excusa caducada: se borra.

    Y uno que además está traducido no necesita excusa.
    """
    textos = set(extraer_textos.extraer(RAIZ))
    en = _diccionario("en")
    caducados = [t for t in EXENTOS if t not in textos]
    assert not caducados, "exentos que ya no están en el código: " + " | ".join(caducados)
    traducidos = [t for t in EXENTOS if t in en]
    assert not traducidos, "exentos que ya están traducidos: " + " | ".join(traducidos)
    assert all(motivo.strip() for motivo in EXENTOS.values())


def test_los_cuatro_diccionarios_tienen_las_mismas_claves() -> None:
    claves = {idioma: set(_diccionario(idioma)) for idioma in IDIOMAS}
    for idioma in IDIOMAS[1:]:
        assert claves[idioma] == claves["en"], idioma


def test_lo_que_no_es_de_pantalla_se_aparta_por_su_sitio() -> None:
    """Las descripciones de la API y el registro no entran en la lista."""
    import ast

    codigo = """
from fastapi import Query
import logging
_log = logging.getLogger(__name__)

def f(x: "Algo | None" = Query(None, description="Filtrar por temporada a mano")) -> None:
    _log.warning("no se pudo guardar el pronóstico %s", x)
    return "Esto sí se ve en pantalla"
"""
    arbol = ast.parse(codigo)
    fuera = extraer_textos.no_son_de_pantalla(arbol)
    vistos = {
        n.value
        for n in ast.walk(arbol)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in fuera
    }
    assert "Esto sí se ve en pantalla" in vistos
    assert "Filtrar por temporada a mano" not in vistos
    assert "no se pudo guardar el pronóstico %s" not in vistos
    assert "Algo | None" not in vistos
