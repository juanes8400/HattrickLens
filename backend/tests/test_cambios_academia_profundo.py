"""Lo que el descubrimiento SIGNIFICA, no solo lo que cambio.

2026-08-30, pedido por el usuario: enseñar el descubrimiento de habilidades
juveniles «de manera mas profunda». Una lista de «Pases: techo 3» no contesta
la pregunta que trae el usuario --¿voy saliendo de la niebla?-- ni le dice si
ese numero cambio algo.
"""

from types import SimpleNamespace

from app.application.queries.sync_comparison import (
    YOUTH_METRICS,
    _cuantos_techos,
    _veredicto_de,
)


def foto(**techos: int) -> SimpleNamespace:
    """Una foto juvenil con los techos que se le pasen y el resto sin revelar."""
    campos: dict[str, object] = {}
    for clave, _, _ in YOUTH_METRICS:
        campos[clave] = None
        campos[f"{clave}_max"] = techos.get(clave)
        campos[f"{clave}_max_reached"] = False
    return SimpleNamespace(**campos)


def test_sin_ningun_techo_no_hay_veredicto():
    """No es «fontanero»: es que no se sabe. Confundirlos era el fallo viejo."""
    assert _veredicto_de(foto()) is None


def test_el_veredicto_sale_del_mejor_techo_revelado():
    assert _veredicto_de(foto(scoring=8)) == "crack"
    assert _veredicto_de(foto(scoring=7)) == "promesa"
    assert _veredicto_de(foto(scoring=6)) == "aceptable"
    assert _veredicto_de(foto(scoring=5)) == "vendible"
    assert _veredicto_de(foto(scoring=3)) == "fontanero"


def test_manda_el_mejor_no_el_ultimo():
    """Un techo bajo no rebaja a quien ya tiene uno alto."""
    assert _veredicto_de(foto(scoring=8, keeper=1, passing=2)) == "crack"


def test_contar_techos_mide_cuanta_niebla_queda():
    """Es la cifra que dice si «Individual» todavia rinde mas que entrenar
    una habilidad concreta."""
    assert _cuantos_techos(foto()) == 0
    assert _cuantos_techos(foto(scoring=4, passing=6)) == 2
    todas = {clave: 5 for clave, _, _ in YOUTH_METRICS}
    assert _cuantos_techos(foto(**todas)) == len(YOUTH_METRICS)


def test_un_descubrimiento_puede_mover_el_veredicto():
    """La diferencia entre «se revelo un numero» y «este chico es otra cosa»."""
    antes, despues = foto(passing=3), foto(passing=3, scoring=8)
    assert _veredicto_de(antes) == "fontanero"
    assert _veredicto_de(despues) == "crack"


def test_o_puede_no_moverlo():
    """Y entonces es un dato, no una noticia."""
    antes, despues = foto(passing=3), foto(passing=3, keeper=2)
    assert _veredicto_de(antes) == _veredicto_de(despues) == "fontanero"
