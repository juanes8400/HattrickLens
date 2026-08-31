"""La horquilla de HTMS28 de un canterano.

Los numeros salen de la tabla real (`docs/reference/htms_formulas_hattrick.html`)
y el caso guia es Ireneo Rodriguez, tal como lo planteo el usuario el
2026-08-24.
"""
from app.domain.engines import htms
from app.domain.engines.youth_htms import (
    TOPE_JUVENIL,
    Lectura,
    niveles,
    rango_htms28,
)


def test_lo_que_dijo_el_ojeador_marca_cada_punta() -> None:
    # «Defensa 5/?»: se sabe que ya juega a 5, asi que el suelo no es cero.
    assert niveles(Lectura(current=5, maximum=None)) == (5, TOPE_JUVENIL)
    # «Lateral ?/7»: se sabe hasta donde llega, pero no de donde parte.
    assert niveles(Lectura(current=None, maximum=7)) == (0, 7)
    # Con las dos, no hay nada que suponer.
    assert niveles(Lectura(current=3, maximum=6)) == (3, 6)
    # Sin nada, la horquilla es toda la escala juvenil.
    assert niveles(Lectura()) == (0, TOPE_JUVENIL)


def test_al_tope_no_tiene_horquilla() -> None:
    """El juego confirma las dos puntas: ahi no puede crecer."""
    assert niveles(Lectura(current=4, maximum=4, max_reached=True)) == (4, 4)
    # Y aunque el techo siga oculto: `IsMaxReached` ya dice que se paro ahi.
    assert niveles(Lectura(current=4, maximum=None, max_reached=True)) == (4, 4)


def test_el_caso_de_ireneo_punto_por_punto() -> None:
    """Defensa 5/? y Lateral ?/7; las otras cinco, en blanco. 16;041."""
    lecturas = {
        "defending": Lectura(current=5),
        "winger": Lectura(maximum=7),
    }
    h = rango_htms28(lecturas, 16, 41)

    # Ability minima: solo aporta la Defensa que ya juega.
    assert h.ability_minima == htms.TABLA[5][1] == 98
    # Ability maxima: Defensa 8, Lateral 7, y las otras cinco a 8.
    esperada = (
        htms.TABLA[TOPE_JUVENIL][0]   # Porteria
        + htms.TABLA[TOPE_JUVENIL][1]  # Defensa
        + htms.TABLA[TOPE_JUVENIL][2]  # Jugadas
        + htms.TABLA[7][3]             # Lateral, con techo revelado
        + htms.TABLA[TOPE_JUVENIL][4]  # Pases
        + htms.TABLA[TOPE_JUVENIL][5]  # Anotacion
        + htms.TABLA[TOPE_JUVENIL][6]  # Balon parado
    )
    assert h.ability_maxima == esperada == 1046

    # Y encima, el termino de la edad, el mismo para las dos puntas.
    bono = htms.potential(0, 16, 41)
    assert h.minimo == 98 + bono
    assert h.maximo == 1046 + bono
    assert h.anchura == 1046 - 98


def test_el_termino_de_edad_no_estrecha_la_horquilla() -> None:
    """Suma igual a las dos puntas: sube en bloque, no cambia de anchura."""
    lecturas = {"defending": Lectura(current=5)}
    joven = rango_htms28(lecturas, 15, 0)
    mayor = rango_htms28(lecturas, 17, 0)
    assert joven.anchura == mayor.anchura
    assert joven.minimo > mayor.minimo, "al mas joven le quedan mas semanas"


def test_sin_nada_revelado_la_horquilla_es_toda_la_escala() -> None:
    h = rango_htms28({}, 16, 0)
    assert h.ability_minima == 0
    assert h.ability_maxima == htms.ability(**dict.fromkeys(("keeper", "defending", "playmaking", "winger", "passing", "scoring", "set_pieces"), TOPE_JUVENIL))
    assert h.ability_maxima == 1073


def test_un_techo_bajo_confirmado_recorta_el_maximo() -> None:
    """Es el punto: saber que no puede pasar de ahi vale tanto como saber
    que si puede."""
    sin_saber = rango_htms28({}, 16, 0)
    con_techo = rango_htms28({"defending": Lectura(maximum=2)}, 16, 0)
    assert con_techo.maximo < sin_saber.maximo
    assert con_techo.minimo == sin_saber.minimo, "el suelo no cambia: sigue sin saberse"
