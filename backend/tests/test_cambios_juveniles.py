"""Cambios en la academia: las cuatro noticias que un juvenil puede dar.

2026-08-26. En mayores una habilidad es un numero y un cambio es una resta.
En juveniles son DOS numeros --lo que tiene y hasta donde puede llegar-- que
se revelan por separado, y de ahi salen casos que la comparacion de mayores no
sabe expresar. Lo que se fija aqui es justo eso: que cada uno se cuente como
lo que es y no se confunda con otro.
"""

from types import SimpleNamespace

from app.application.queries.sync_comparison import YOUTH_METRICS, _cambio_juvenil


def _foto(**campos: object) -> SimpleNamespace:
    """Una foto juvenil con las siete habilidades a cero de informacion."""
    base: dict[str, object] = {}
    for clave, _, _ in YOUTH_METRICS:
        base[clave] = None
        base[f"{clave}_max"] = None
        base[f"{clave}_max_reached"] = False
    base.update(campos)
    return SimpleNamespace(**base)


def _cambio(antes: SimpleNamespace, ahora: SimpleNamespace) -> dict[str, object] | None:
    return _cambio_juvenil("winger", "Lateral", "LA", antes, ahora)


def test_las_siete_habilidades_y_solo_esas():
    """Ni TSI ni salario ni forma: un canterano no tiene nada de eso."""
    claves = {c for c, _, _ in YOUTH_METRICS}
    assert claves == {
        "keeper",
        "defending",
        "playmaking",
        "winger",
        "passing",
        "scoring",
        "set_pieces",
    }


def test_sin_movimiento_no_hay_noticia():
    assert _cambio(_foto(winger=4, winger_max=7), _foto(winger=4, winger_max=7)) is None


def test_subir_de_nivel_es_verde():
    c = _cambio(_foto(winger=3, winger_max=7), _foto(winger=4, winger_max=7))
    assert c is not None
    assert (c["before"], c["current"], c["delta"]) == (3, 4, 1)
    assert c["direction"] == "up"
    assert c["isReveal"] is False


def test_revelar_el_nivel_no_es_subir():
    """El chico no ha crecido: lo que cambio es que ahora lo vemos.

    Pintarlo de verde diria que progreso, y no es verdad. Por eso `direction`
    se queda en neutro y `delta` en None aunque haya un numero nuevo.
    """
    c = _cambio(_foto(), _foto(winger=4))
    assert c is not None
    assert c["before"] is None
    assert c["current"] == 4
    assert c["delta"] is None
    assert c["direction"] == "neutral"
    assert c["isReveal"] is True


def test_descubrir_solo_el_techo_tambien_es_noticia():
    """El caso que no existe en mayores: sabemos hasta donde llega y no en que
    esta. Sin esto, el desbloqueo de habilidades no se veria en ningun sitio.
    """
    c = _cambio(_foto(), _foto(winger_max=6))
    assert c is not None
    assert c["current"] is None  # el nivel sigue oculto
    assert c["max"] == 6
    assert c["maxIsNew"] is True
    assert c["delta"] is None


def test_los_dos_a_la_vez():
    c = _cambio(_foto(), _foto(winger=3, winger_max=6))
    assert c is not None
    assert c["isReveal"] is True
    assert c["maxIsNew"] is True
    assert (c["current"], c["max"]) == (3, 6)


def test_topar_se_anuncia_una_vez():
    """`IsMaxReached` puede llegar con el techo aun oculto: se sabe que no
    sube, sin saber en que numero se paro."""
    c = _cambio(_foto(winger=5), _foto(winger=5, winger_max_reached=True))
    assert c is not None
    assert c["maxJustReached"] is True
    assert c["maxReached"] is True

    # Y a la semana siguiente ya no vuelve a contarse.
    ya = _foto(winger=5, winger_max_reached=True)
    assert _cambio(ya, ya) is None


def test_un_techo_que_se_corrige_tambien_se_ve():
    c = _cambio(_foto(winger=4, winger_max=6), _foto(winger=4, winger_max=7))
    assert c is not None
    assert (c["maxBefore"], c["max"]) == (6, 7)
    assert c["maxIsNew"] is False  # no es nuevo: se movio


def test_bajar_de_nivel_es_rojo():
    c = _cambio(_foto(winger=5), _foto(winger=4))
    assert c is not None
    assert c["direction"] == "down"
    assert c["delta"] == -1
