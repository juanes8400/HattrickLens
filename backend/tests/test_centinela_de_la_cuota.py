"""Que un silencio de Hattrick no se lea como «no hay nadie».

2026-10-12, sondeando el Comparador del juego:

    «Hattrick se agoto: de cinco peticiones seguidas, UNA traia criterios y
    cuatro volvian vacias.»

Una cuota agotada no da error: devuelve vacio, igual que un jugador al que de
verdad nadie se parece. Todo lo que se prueba aqui sale de esa igualdad.
"""

from app.domain.engines.centinela_de_la_cuota import (
    EDAD_DEL_CANARIO,
    RACHA_INICIAL,
    TRAMO_DEL_CANARIO,
    Centinela,
    canario,
)
from app.infrastructure.chpp.mercado import (
    ID_DE_HABILIDAD,
    TRAMO_MAXIMO_DEL_PRIMERO,
    peticiones_de,
)

# ── El canario ───────────────────────────────────────────────────────────────


def test_el_canario_cabe_en_una_sola_peticion() -> None:
    """Si se partiera en trozos costaria mas de una, y entonces el aparato que
    vigila el gasto seria el que gasta."""
    assert len(peticiones_de(canario())) == 1


def test_el_canario_respeta_la_regla_de_los_cuatro_niveles() -> None:
    # La regla del servidor, comprobada el 2026-10-05: el primer filtro no
    # admite un tramo de mas de cuatro. El canario pide justo cuatro, que es
    # el mas ancho que se puede pedir sin que lo rechacen.
    desde, hasta = TRAMO_DEL_CANARIO
    assert hasta - desde + 1 == TRAMO_MAXIMO_DEL_PRIMERO


def test_el_canario_pide_lo_mas_poblado_del_mercado() -> None:
    """Lo que lo hace servir: que no pueda estar vacio."""
    ventana = canario()
    joven, viejo = EDAD_DEL_CANARIO
    assert (ventana.edad_minima, ventana.edad_maxima) == (joven, viejo)
    # Las otras dos habilidades no piden nada: cualquiera las cumple.
    assert (ventana.secundaria.minimo, ventana.secundaria.maximo) == (0, 20)
    assert (ventana.terciaria.minimo, ventana.terciaria.maximo) == (0, 20)


def test_las_tres_habilidades_del_canario_existen_en_chpp() -> None:
    # Un nombre mal escrito reventaria al traducir la ventana, y reventaria el
    # dia que hiciera falta el canario, que es el peor dia.
    ventana = canario()
    for franja in (ventana.primaria, ventana.secundaria, ventana.terciaria):
        assert franja.habilidad in ID_DE_HABILIDAD


def test_el_canario_no_entra_en_el_fondo() -> None:
    """Peso cero: no es un escalon de la escalera y no se guarda."""
    assert canario().peso == 0


# ── La racha, que no cuesta nada ─────────────────────────────────────────────


def test_al_empezar_se_pregunta_antes_de_gastar_nada() -> None:
    """El canario del principio es el que evita gastar el barrido entero
    contra un servidor que no contesta."""
    centinela = Centinela()
    assert centinela.hay_que_preguntar


def test_un_vacio_suelto_no_sospecha() -> None:
    # Pasa constantemente: la ventana exacta de un jugador raro no tiene a
    # nadie casi nunca. Si un vacio bastara, el canario cantaria sin parar.
    centinela = Centinela()
    centinela.canto_el_canario(40)
    centinela.vio(0)
    assert not centinela.hay_que_preguntar
    assert centinela.sigue


def test_la_racha_se_rompe_con_una_busqueda_que_trae_gente() -> None:
    centinela = Centinela()
    centinela.canto_el_canario(40)
    for _ in range(RACHA_INICIAL - 1):
        centinela.vio(0)
    centinela.vio(3)
    assert centinela.racha == 0
    assert not centinela.hay_que_preguntar


def test_al_llegar_al_umbral_se_pregunta() -> None:
    centinela = Centinela()
    centinela.canto_el_canario(40)
    for _ in range(RACHA_INICIAL):
        centinela.vio(0)
    assert centinela.hay_que_preguntar


# ── El canario resuelve ──────────────────────────────────────────────────────


def test_si_el_canario_calla_el_barrido_se_acaba() -> None:
    centinela = Centinela()
    centinela.canto_el_canario(0)
    assert centinela.agotada
    assert not centinela.sigue


def test_un_canario_mudo_no_se_vuelve_a_preguntar() -> None:
    """Ya es toda la prueba que hay, y preguntar otra vez seria gastar la
    cuota que se acaba de ver que no esta."""
    centinela = Centinela()
    centinela.canto_el_canario(0)
    assert not centinela.hay_que_preguntar


def test_si_el_canario_canta_los_vacios_de_antes_eran_de_verdad() -> None:
    centinela = Centinela()
    centinela.canto_el_canario(40)
    for _ in range(RACHA_INICIAL):
        centinela.vio(0)
    centinela.canto_el_canario(40)
    assert centinela.sigue
    assert centinela.racha == 0


def test_el_umbral_se_dobla_cuando_el_canario_DESMIENTE_una_racha() -> None:
    """Sin esto, una plantilla rara pagaria un canario cada seis jugadores."""
    centinela = Centinela()
    centinela.canto_el_canario(40)
    for _ in range(RACHA_INICIAL):
        centinela.vio(0)
    centinela.canto_el_canario(40)
    assert centinela.umbral == RACHA_INICIAL * 2


def test_el_canario_DE_APERTURA_no_dobla_el_umbral() -> None:
    """No ha desmentido nada: no hay racha todavia.

    Si contara, la primera sospecha del barrido necesitaria doce vacios en vez
    de seis, y una cuota muerta a mitad tardaria el doble en notarse.
    """
    centinela = Centinela()
    centinela.canto_el_canario(40)
    assert centinela.umbral == RACHA_INICIAL


def test_un_barrido_entero_en_blanco_cuesta_pocos_canarios() -> None:
    """La cuenta que justifica el doblado.

    Ciento veinte busquedas, TODAS vacias y con el mercado contestando --una
    plantilla de rarezas, el peor caso honrado-- y el aparato que vigila el
    gasto no se convierte en el que gasta.
    """
    centinela = Centinela()
    for _ in range(120):
        if centinela.hay_que_preguntar:
            centinela.canto_el_canario(40)
        centinela.vio(0)
    assert centinela.canarios <= 5, centinela.canarios
    assert centinela.sigue


def test_una_cuota_que_muere_a_mitad_se_nota_antes_de_acabar() -> None:
    """El caso que el canario del principio no puede cubrir.

    Sesenta busquedas con gente y de golpe el silencio: el barrido tiene que
    pararse solo, sin llegar al final dando el dia por medido.
    """
    centinela = Centinela()
    hechas = 0
    for vuelta in range(120):
        if centinela.hay_que_preguntar:
            centinela.canto_el_canario(0 if vuelta >= 60 else 40)
        if not centinela.sigue:
            break
        centinela.vio(0 if vuelta >= 60 else 4)
        hechas += 1
    assert not centinela.sigue
    assert hechas < 120, "el barrido llego al final con la cuota muerta"


# ── Las cuentas, que son lo que se ensena despues ────────────────────────────


def test_lleva_la_cuenta_de_llenas_y_vacias() -> None:
    centinela = Centinela()
    centinela.canto_el_canario(40)
    centinela.vio(0)
    centinela.vio(7)
    centinela.vio(0)
    assert (centinela.llenas, centinela.vacias) == (1, 2)


def test_se_cuentan_resultados_y_no_comparables() -> None:
    """Un jugador que llega y luego se descarta por no parecerse demuestra que
    el servidor contesto igual de bien que uno que se queda. Lo que mide esto
    es el servidor, no el parecido."""
    centinela = Centinela()
    centinela.canto_el_canario(40)
    centinela.vio(52)  # la busqueda real del 2026-10-05: 52 resultados, 4 utiles
    assert centinela.llenas == 1
    assert centinela.racha == 0
