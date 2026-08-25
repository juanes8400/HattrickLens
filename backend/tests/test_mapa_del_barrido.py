"""El mapa que pinta la barra del botón de Transferencias.

2026-08-25. Tres intentos fallaron por calcular esto en el navegador; las
pruebas fijan las tres cosas que salieron mal.
"""
from app.domain.engines.mapa_del_barrido import frente_de, mapa_de


def test_una_marca_suelta_no_empuja_el_frente() -> None:
    """Es lo que distingue el avance del picoteo: si una tirada al azar que
    cae en la casilla 40 hiciera crecer el bloque, la barra diria que se han
    hecho cuarenta cuando se ha hecho una."""
    assert frente_de({0, 1, 2, 40}) == 3
    assert frente_de({40}) == 0
    assert frente_de(set()) == 0


def test_el_frente_es_el_tramo_seguido_desde_la_izquierda() -> None:
    assert frente_de({0, 1, 2, 3}) == 4
    assert frente_de({1, 2, 3}) == 0, "sin la casilla 0 no hay bloque"


def test_el_mapa_traduce_jugadores_a_casillas() -> None:
    eje = [101, 102, 103, 104, 105]
    m = mapa_de(eje, {101, 104})
    assert m.total == 5
    assert m.hechas == [0, 3]
    assert m.frente == 1


def test_un_expediente_cerrado_conserva_su_casilla() -> None:
    """El fallo que se veia como "alumbra una parte y luego se quita".

    El eje se recalculaba en cada pulsacion contra la tabla viva: al cerrarse
    un expediente su fila desaparecia, el eje encogia, TODAS las posiciones se
    corrian una a la izquierda y las marcas ya pintadas saltaban de sitio.
    Congelado, el eje es una lista guardada y da igual lo que le pase a la
    tabla.
    """
    eje = [101, 102, 103, 104, 105]
    antes = mapa_de(eje, {101, 104})
    # 102 se cierra: ya no esta en la tabla de vigilados, pero SIGUE en el eje.
    despues = mapa_de(eje, {101, 104, 102})
    assert despues.total == antes.total, "el ancho no se mueve"
    assert despues.hechas == [0, 1, 3], "y 104 sigue en la casilla 3"
    assert despues.frente == 2


def test_quien_no_esta_en_el_eje_no_inventa_casillas() -> None:
    """Atender a alguien de otra cola --ficha, precio, censo-- no pinta nada:
    la barra es el mapa de LA VIGILANCIA DE REVENTAS, no de todo el lote."""
    m = mapa_de([101, 102], {101, 999})
    assert m.hechas == [0]
    assert m.total == 2


def test_el_barrido_terminado_llena_la_barra() -> None:
    m = mapa_de([101, 102, 103], {101, 102, 103})
    assert m.frente == m.total == 3
