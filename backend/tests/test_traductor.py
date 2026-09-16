"""Traducción de las respuestas: exacta, por plantilla y sin tocar las claves."""

from app.i18n.traductor import Traductor, idioma_de

DICCIONARIO = {
    "Encantados": "satisfied",
    "Pases": "Passing",
    "{} está lesionado": "{} is injured",
    "{} de {} en total": "{} of {} in total",
    "{} de {}": "{} of {}",
    "Subió {} en {}": "{1}: {0} went up",
}


def test_idioma_de_la_cabecera() -> None:
    assert idioma_de("en-GB,en;q=0.9") == "en"
    assert idioma_de("es-CO") == "es"
    assert idioma_de("fr,de") == "es"
    assert idioma_de(None) == "es"


def test_exacto_y_sin_encaje() -> None:
    tr = Traductor(DICCIONARIO)
    assert tr.texto("Encantados") == "satisfied"
    assert tr.texto("Pulgas Arrechas") == "Pulgas Arrechas"
    assert tr.texto("-") == "-"


def test_plantilla_y_huecos_traducidos() -> None:
    tr = Traductor(DICCIONARIO)
    assert tr.texto("Luis Bango está lesionado") == "Luis Bango is injured"
    # La plantilla más larga gana a la corta que también encajaría.
    assert tr.texto("3 de 8 en total") == "3 of 8 in total"
    assert tr.texto("Subió Pases en Bordalás") == "Bordalás: Passing went up"


def test_lista_separada_por_comas() -> None:
    """Un hueco con varias cosas dentro: «Técnico, Rápido» en una alerta."""
    tr = Traductor(DICCIONARIO)
    assert tr.texto("Encantados, Pases") == "satisfied, Passing"
    # Si una pieza no está, se deja la lista entera en español.
    assert tr.texto("Encantados, Pulgas Arrechas") == "Encantados, Pulgas Arrechas"
    # El mismo caso con el separador de Uso: «módulo · sección».
    assert tr.texto("Encantados · Pases") == "satisfied · Passing"


def test_campos_intocables() -> None:
    tr = Traductor(DICCIONARIO)
    dato = {
        "module": "Pases",
        "title": "Luis Bango está lesionado",
        "items": [{"label": "Encantados", "category": "Encantados"}],
    }
    assert tr.json(dato) == {
        "module": "Pases",
        "title": "Luis Bango is injured",
        "items": [{"label": "satisfied", "category": "Encantados"}],
    }


def test_objeto_bajo_campo_intocable_se_traduce_por_dentro() -> None:
    tr = Traductor(DICCIONARIO)
    dato = {"type": {"code": "Pases", "texto": "Pases"}, "status": ["Pases"]}
    assert tr.json(dato) == {"type": {"code": "Pases", "texto": "Passing"}, "status": ["Pases"]}
