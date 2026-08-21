"""Cuándo se deja de vigilar a un ex-jugador.

Las reglas las fijó el usuario el 2026-08-21. Lo que se protege aquí es la
asimetría entre un jugador cualquiera y un canterano: confundirlas cuesta
dinero de verdad en un sentido (dejar de mirar a un canterano que seguirá
pagando) y cuota de Hattrick en el otro (seguir preguntando por alguien del
que ya no puede salir nada).
"""
from app.domain.engines import ex_player_watch as v


def test_a_normal_player_is_done_once_he_is_resold() -> None:
    """La comisión de club anterior es de la SIGUIENTE venta, y solo de esa."""
    assert v.motivo_de_cierre(
        canterano=False, revendido=True, desaparecido=False, salio_sin_comprador=False
    ) == "revendido"


def test_an_academy_player_keeps_paying_on_every_future_sale() -> None:
    """Al canterano una reventa NO lo cierra: cobramos en la siguiente, y en
    la siguiente. Cerrarlo aquí sería dejar de cobrar."""
    assert v.motivo_de_cierre(
        canterano=True, revendido=True, desaparecido=False, salio_sin_comprador=False
    ) is None


def test_disappearing_from_hattrick_closes_anyone() -> None:
    """Despedido o retirado: ya no hay jugador que vender. Cierra igual al
    canterano, que es el único caso que lo cierra."""
    for canterano in (True, False):
        assert v.motivo_de_cierre(
            canterano=canterano, revendido=False, desaparecido=True,
            salio_sin_comprador=False,
        ) == "despedido"


def test_leaving_without_a_buyer_closes_from_the_start() -> None:
    """A quien despedimos nosotros nunca lo compró nadie, así que no hay club
    anterior al que pagarle: nace cerrado."""
    assert v.motivo_de_cierre(
        canterano=False, revendido=False, desaparecido=False, salio_sin_comprador=True
    ) == "sin_comprador"


def test_a_player_still_out_there_unsold_stays_under_watch() -> None:
    assert v.motivo_de_cierre(
        canterano=False, revendido=False, desaparecido=False, salio_sin_comprador=False
    ) is None


def test_the_error_code_of_a_player_who_no_longer_exists() -> None:
    """Verificado en vivo contra la cuenta del usuario: playerdetails.xml
    responde ErrorCode 56 cuando el jugador ya no existe."""
    assert v.desaparecio_de_hattrick(56) is True
    assert v.desaparecio_de_hattrick(None) is False
    assert v.desaparecio_de_hattrick(0) is False


def test_home_grown_is_decided_by_the_mother_club_id() -> None:
    assert v.es_canterano(537758, 537758) is True
    assert v.es_canterano(999999, 537758) is False
    assert v.es_canterano(None, 537758) is False
    assert v.es_canterano(0, 537758) is False


def test_a_commission_already_recorded_still_counts_as_resold() -> None:
    """Caso real (Adrian-Ioan Burlac, 442649968): no es canterano, se lo
    revendieron en 2020 y su comisión de 234.090 lleva años guardada. Aun así
    seguía abierto y se revisaba en cada pulsación.

    La causa era confundir dos cosas: la función que busca la reventa devuelve
    "sí" solo cuando ACABA DE ESCRIBIR una comisión nueva, y eso se estaba
    leyendo como "existe una reventa". Para la regla de cierre lo que importa
    es lo segundo.
    """
    from app.domain.engines import ex_player_watch as v

    # Con la reventa ya registrada, la regla tiene que cerrarlo igual.
    assert v.motivo_de_cierre(
        canterano=False, revendido=True, desaparecido=False, salio_sin_comprador=False
    ) == "revendido"
