"""«Precio de venta vs costo» (7.0.0) y su arreglo de la 7.0.1."""

from app.application.queries.venta_vs_costo import precio_de_la_semana

SEMANAS = [("83-12", 100), ("83-13", 120), ("83-15", 90)]


def test_cada_precio_va_en_su_semana_de_hattrick() -> None:
    """7.0.1: una semana pasada se escribe tarde, pero su precio es de su
    semana. La pestaña «Precio» y ésta tienen que decir las mismas semanas."""
    assert precio_de_la_semana(SEMANAS, "83-12") == 100
    assert precio_de_la_semana(SEMANAS, "83-13") == 120


def test_una_semana_sin_ventas_arrastra_la_anterior() -> None:
    assert precio_de_la_semana(SEMANAS, "83-14") == 120
    assert precio_de_la_semana(SEMANAS, "84-02") == 90


def test_antes_de_la_primera_semana_no_hay_precio() -> None:
    assert precio_de_la_semana(SEMANAS, "83-11") is None
    assert precio_de_la_semana(SEMANAS, None) is None


def test_el_cambio_de_temporada_se_ordena_bien() -> None:
    """«TT-ss» con ceros: el texto ordena igual que el tiempo."""
    assert precio_de_la_semana([("83-16", 5), ("84-01", 7)], "84-01") == 7
    assert precio_de_la_semana([("83-16", 5), ("84-01", 7)], "83-16") == 5
