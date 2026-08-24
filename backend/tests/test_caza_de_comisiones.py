"""Cuando buscar una reventa, y en que orden mirar. Disenado el 2026-08-24."""
import random

from app.domain.engines.caza_de_comisiones import (
    Comisiones,
    Vigilancia,
    orden_de_busqueda,
    revisar_el_dinero,
)

QUIETO = Vigilancia(vista_en_curso=0, vista_cerrada=0, cazando=False)


def test_sin_comision_nueva_no_se_caza() -> None:
    """La mayoria de las semanas no pasa nada, y gastar llamadas en
    confirmarlo es justo lo que se queria dejar de hacer."""
    d = revisar_el_dinero(QUIETO, Comisiones(en_curso=0, semana_cerrada=0))
    assert d.cazando is False
    assert d.empieza is False


def test_la_comision_de_la_semana_en_curso_abre_la_caceria() -> None:
    d = revisar_el_dinero(QUIETO, Comisiones(en_curso=153_500, semana_cerrada=0))
    assert d.empieza is True
    assert d.cazando is True
    assert d.vista_en_curso == 153_500


def test_la_misma_comision_no_vuelve_a_abrirla() -> None:
    """Se sincroniza cinco veces el mismo dia; el dinero es el mismo."""
    ya = Vigilancia(vista_en_curso=153_500, vista_cerrada=0, cazando=False)
    d = revisar_el_dinero(ya, Comisiones(en_curso=153_500, semana_cerrada=0))
    assert d.empieza is False


def test_una_segunda_comision_en_la_misma_semana_si_la_reabre() -> None:
    ya = Vigilancia(vista_en_curso=153_500, vista_cerrada=0, cazando=False)
    d = revisar_el_dinero(ya, Comisiones(en_curso=200_000, semana_cerrada=0))
    assert d.empieza is True
    assert d.vista_en_curso == 200_000


def test_el_dinero_de_una_semana_que_no_se_sincronizo_no_se_pierde() -> None:
    """El caso que obliga a mirar las dos cifras: la de "en curso" ya volvio
    a cero y el dinero solo queda en la cerrada."""
    d = revisar_el_dinero(QUIETO, Comisiones(en_curso=0, semana_cerrada=153_500))
    assert d.empieza is True
    assert d.vista_cerrada == 153_500


def test_lo_ya_cazado_no_se_reabre_al_cerrar_la_semana() -> None:
    """Se vio el dinero mientras corria la semana; al cerrarse aparece el
    mismo importe en la otra cifra y NO es dinero nuevo."""
    ya = Vigilancia(vista_en_curso=153_500, vista_cerrada=0, cazando=False)
    d = revisar_el_dinero(ya, Comisiones(en_curso=0, semana_cerrada=153_500))
    assert d.empieza is False
    assert d.vista_cerrada == 153_500
    assert d.vista_en_curso == 0, "la cifra en curso vuelve a empezar"


def test_tras_cerrar_la_semana_una_comision_pequena_se_nota() -> None:
    """Sin reiniciar la cifra en curso, una comision de 600 despues de una de
    153.500 no superaria la marca y pasaria desapercibida."""
    ya = Vigilancia(vista_en_curso=153_500, vista_cerrada=0, cazando=False)
    cerrada = revisar_el_dinero(ya, Comisiones(en_curso=0, semana_cerrada=153_500))
    siguiente = revisar_el_dinero(
        Vigilancia(cerrada.vista_en_curso, cerrada.vista_cerrada, cerrada.cazando),
        Comisiones(en_curso=600, semana_cerrada=153_500),
    )
    assert siguiente.empieza is True


# ── El orden de busqueda ────────────────────────────────────────────────────

RECIENTES = [10, 20, 30, 40, 50, 60, 70, 80]


def test_alterna_reciente_y_azar() -> None:
    elegidos = orden_de_busqueda(RECIENTES, set(), 6, azar=random.Random(1))
    # Las posiciones impares salen de la cabeza de la cola de recientes.
    assert elegidos[0] == 10
    assert elegidos[2] in (20, 30, 40, 50, 60, 70, 80)
    assert elegidos[2] == min(x for x in RECIENTES if x not in elegidos[:2])
    assert len(elegidos) == 6
    assert len(set(elegidos)) == 6, "nadie dos veces en la misma tanda"


def test_no_repite_a_quien_ya_se_probo_en_esta_caceria() -> None:
    elegidos = orden_de_busqueda(RECIENTES, {10, 20, 30}, 4, azar=random.Random(2))
    assert not ({10, 20, 30} & set(elegidos))
    assert elegidos[0] == 40, "el mas reciente de los que quedan"


def test_cuando_no_queda_nadie_devuelve_vacio() -> None:
    assert orden_de_busqueda(RECIENTES, set(RECIENTES), 5) == []


def test_pide_mas_de_los_que_hay() -> None:
    elegidos = orden_de_busqueda([1, 2, 3], set(), 10, azar=random.Random(3))
    assert sorted(elegidos) == [1, 2, 3]


def test_el_azar_de_verdad_reparte() -> None:
    """Dos semillas distintas no pueden dar siempre la misma segunda
    eleccion: si la dieran, la mitad aleatoria no estaria explorando nada."""
    segundos = {
        orden_de_busqueda(RECIENTES, set(), 2, azar=random.Random(s))[1]
        for s in range(30)
    }
    assert len(segundos) > 1
