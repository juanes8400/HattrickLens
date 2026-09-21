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


def test_gana_la_plantilla_mas_especifica_cuando_empatan() -> None:
    """Dos plantillas que empiezan igual y se separan al final.

    2026-09-20, visto con el alta de un jugador: «{} se unió a la plantilla:
    comprado por {}» y «... comprado por {}, sueldo {}» comparten su trozo
    literal más largo, así que el orden las dejaba empatadas y el desempate
    era el del diccionario, o sea el azar. Ganaba la corta y el sueldo se
    quedaba en español dentro de una frase inglesa.
    """
    from app.i18n.traductor import Traductor

    tr = Traductor(
        {
            "{} se unió a la plantilla: comprado por {}": "{} joined: bought for {}",
            "{} se unió a la plantilla: comprado por {}, sueldo {}":
                "{} joined: bought for {}, wage {}",
        }
    )
    assert tr.texto("Fulano se unió a la plantilla: comprado por 100, sueldo 5") == (
        "Fulano joined: bought for 100, wage 5"
    )
    # Y la corta sigue funcionando para lo suyo.
    assert tr.texto("Fulano se unió a la plantilla: comprado por 100") == (
        "Fulano joined: bought for 100"
    )


def test_un_campo_de_doble_uso_se_decide_por_la_forma_del_valor() -> None:
    """`position` lleva una clave o una frase segun quien responda.

    2026-09-20, visto por el usuario: en la plantilla de un rival decia
    «Mediocentro medio» con la aplicacion en ingles. Estaba en la lista de
    intocables porque en el once del Panel vale «keeper» y ALLI el frontend lo
    compara: traducirlo rompia la pantalla. La forma del valor separa los dos
    casos sin partir el campo en dos.
    """
    from app.i18n.traductor import traductor

    tr = traductor("en")
    assert tr is not None
    assert tr.json({"position": "keeper"}) == {"position": "keeper"}
    assert tr.json({"position": "forward_defensive"}) == {"position": "forward_defensive"}
    assert tr.json({"position": "Mediocentro medio"})["position"] != "Mediocentro medio"


def test_la_especialidad_sigue_intocable() -> None:
    """Y esto es lo que impide ampliar la regla sin pensarlo.

    `specialty` parece el mismo caso que `position` y no lo es: el frontend
    casa el nombre ESPANOL contra el glosario oficial de Hattrick para sacar
    su icono. Traducirla aqui dejaria a todas las especialidades sin icono.
    """
    from app.i18n.traductor import traductor

    tr = traductor("en")
    assert tr is not None
    assert tr.json({"specialty": "Técnico"}) == {"specialty": "Técnico"}
