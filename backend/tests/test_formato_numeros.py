"""Los números que escribe el servidor siguen el idioma de la petición."""

from app.domain.value_objects.formatting import idioma_de_la_peticion, thousands

#: El espacio duro y no partible que el polaco pone entre los miles.
DURO = " "


def test_en_espanol_el_punto_separa_los_miles() -> None:
    assert thousands(9870896) == "9.870.896"
    assert thousands(1234567.89, 2) == "1.234.567,89"


def test_en_ingles_separa_con_coma() -> None:
    """«453.910» se leía como 453 con decimales en una alerta en inglés."""
    ficha = idioma_de_la_peticion.set("en")
    try:
        assert thousands(9870896) == "9,870,896"
        assert thousands(1234567.89, 2) == "1,234,567.89"
    finally:
        idioma_de_la_peticion.reset(ficha)


def test_en_polaco_los_miles_van_con_un_espacio_duro() -> None:
    """El polaco no separa los miles con punto ni con coma, sino con un
    espacio, y la coma le queda para los decimales.

    Hasta el 2026-10-03 esta función sólo sabía intercambiar el punto y la
    coma, así que el polaco habría salido con el formato español sin que
    nada fallara: un idioma mal escrito no rompe ninguna pantalla.
    """
    ficha = idioma_de_la_peticion.set("pl")
    try:
        assert thousands(9870896) == f"9{DURO}870{DURO}896"
        assert thousands(1234567.89, 2) == f"1{DURO}234{DURO}567,89"
    finally:
        idioma_de_la_peticion.reset(ficha)


def test_fuera_de_una_petición_manda_el_español() -> None:
    assert idioma_de_la_peticion.get() == "es"
    assert thousands(615000) == "615.000"
