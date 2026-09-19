"""Los números que escribe el servidor siguen el idioma de la petición."""

from app.domain.value_objects.formatting import idioma_de_la_peticion, thousands


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


def test_fuera_de_una_petición_manda_el_español() -> None:
    assert idioma_de_la_peticion.get() == "es"
    assert thousands(615000) == "615.000"
