"""2026-08-15: helper que evita que mensajes generados a mano se cuelen con
el formato de miles de EE. UU. (coma) en vez del de la app (punto)."""
from app.domain.value_objects.formatting import thousands


def test_thousands_no_decimals() -> None:
    assert thousands(615000) == "615.000"


def test_thousands_millions() -> None:
    assert thousands(1234567) == "1.234.567"


def test_thousands_with_decimals_uses_comma() -> None:
    assert thousands(1234567.89, 2) == "1.234.567,89"


def test_thousands_negative() -> None:
    assert thousands(-3200) == "-3.200"


def test_thousands_zero() -> None:
    assert thousands(0) == "0"


def test_thousands_below_one_thousand_has_no_separator() -> None:
    assert thousands(950) == "950"
