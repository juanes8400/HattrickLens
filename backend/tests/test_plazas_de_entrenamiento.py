"""Que formaciones aprovechan todas las plazas de entrenamiento.

2026-10-25, reporte de un usuario:

    «I would also like to have "Best Training" which would exclude a formation
    that doesn't use all training spots. I'm getting the suggested Best
    Formation of 4-4-2 for my team training Scoring. I consider training to be
    critical in this phase, so will not play 442 no matter the ratings
    difference.»

UNA MEDIA RACION TAMBIEN ES UNA PLAZA: decision del usuario ese mismo dia, y
era la unica duda del encargo. De ahi sale casi todo lo que se prueba aqui.
"""

from app.domain.engines import plazas_de_entrenamiento as P
from app.domain.value_objects.formations import LINE_COUNTS
from app.domain.value_objects.ht_constants import TRAINING_TYPES

# ── El caso del reporte ──────────────────────────────────────────────────────


def test_anotacion_descarta_el_442_que_es_lo_que_se_reporto() -> None:
    """La queja, tal cual: 4-4-2 entrenando Anotacion.

    Entrenan solo los delanteros, asi que un 4-4-2 usa dos de las tres plazas.
    Esa tercera no vuelve esa semana, y por eso se descarta ANTES de mirar
    ninguna valoracion.
    """
    assert P.plazas("scoring", "4-4-2") == 2
    assert P.plazas("scoring", "4-3-3") == 3
    assert P.desperdicio("scoring", "4-4-2") == 1

    aprovechan = P.formaciones_que_lo_aprovechan("scoring")
    assert "4-4-2" not in aprovechan
    # Las cuatro con tres delanteros, ni una mas ni una menos.
    assert set(aprovechan) == {"5-2-3", "4-3-3", "3-4-3", "2-5-3"}


# ── La media racion cuenta, y lo que eso implica ─────────────────────────────


def test_el_extremo_cuenta_aunque_entrene_a_la_mitad() -> None:
    # Jugadas es {inner_midfield: 100, winger: 50}. Si el extremo no contara,
    # un 4-5-1 con tres mediocentros valdria 3; contando, vale 5.
    assert "winger" in P.puestos_que_entrena("playmaking")
    assert P.plazas("playmaking", "4-5-1") == 5


def test_con_la_media_racion_dentro_las_plazas_son_LINEAS_ENTERAS() -> None:
    """La consecuencia que simplifica el calculo, y conviene que este fijada.

    Mediocentros mas extremos son toda la linea del medio; centrales mas
    laterales, toda la de atras. Asi que en Jugadas y en Defensa las plazas NO
    dependen de como se reparta la linea: suman lo mismo se ponga como se
    ponga. Si algun dia esto deja de cumplirse, es que cambio el reparto de
    puestos y hay que volver a mirarlo todo.
    """
    for nombre, (defensas, medios, delanteros) in LINE_COUNTS.items():
        assert P.plazas("playmaking", nombre) == medios, nombre
        assert P.plazas("defending", nombre) == defensas, nombre
        assert P.plazas("scoring", nombre) == delanteros, nombre


def test_el_lateral_es_el_unico_donde_manda_el_reparto() -> None:
    """Y por eso es el unico con una advertencia en la pantalla.

    Lateral es {winger: 100, wingback: 50}: coge los extremos de una linea y
    los laterales de otra, asi que cuantos haya depende de como se reparta cada
    una.
    """
    # 4-4-2 con dos laterales y dos extremos: cuatro plazas.
    assert P.plazas("winger", "4-4-2", central_defenders=2, inner_midfielders=2) == 4
    # El mismo 4-4-2 con tres centrales y tres mediocentros: una y una.
    assert P.plazas("winger", "4-4-2", central_defenders=3, inner_midfielders=3) == 2


# ── Los bordes ───────────────────────────────────────────────────────────────


def test_balon_parado_no_descarta_a_nadie() -> None:
    # Llega a los once puestos, asi que las diez empatan y no hay nada que
    # excluir. Devolver la lista entera es lo correcto, y ademas evita que la
    # pantalla se quede sin opciones.
    assert P.plazas("set_pieces", "4-4-2") == 11
    assert len(P.formaciones_que_lo_aprovechan("set_pieces")) == len(LINE_COUNTS)


def test_un_entrenamiento_desconocido_no_filtra_en_vez_de_vaciar() -> None:
    # Si algun dia llega un codigo que este modulo no conoce, la pantalla deja
    # de filtrar. Quedarse sin formaciones seria mucho peor que no filtrar.
    assert P.puestos_que_entrena("lo-que-sea") == frozenset()
    assert P.plazas("lo-que-sea", "4-4-2") == 0
    assert len(P.formaciones_que_lo_aprovechan("lo-que-sea")) == len(LINE_COUNTS)


def test_una_formacion_inventada_vale_cero_y_no_revienta() -> None:
    assert P.plazas("scoring", "9-9-9") == 0


def test_nunca_se_devuelve_una_lista_vacia() -> None:
    """La pantalla se queda sin opciones si esto falla, en cualquier
    entrenamiento."""
    for codigo in TRAINING_TYPES:
        clave = P.entrenamiento_de_chpp(codigo)
        assert P.formaciones_que_lo_aprovechan(clave or "")


# ── El puente con los codigos de CHPP ────────────────────────────────────────


def test_TODOS_los_entrenamientos_vigentes_de_chpp_tienen_pareja() -> None:
    """La prueba que justifica que el puente sea explicito y no por texto.

    Diez de los doce casan por etiqueta, pero `ht_constants` llama al 10 «Pases
    (defensas y centrocampistas)» y la tabla de puestos lo llama «Pases
    (defensas y centro del campo completo)»: el mismo entrenamiento con dos
    redacciones, ya separadas hoy. Emparejar por el rotulo se romperia en
    silencio el dia que alguien reescriba un texto de pantalla.
    """
    obsoletos = {0, 1}  # General y Resistencia, retirados del juego
    sin_pareja = [
        (codigo, nombre)
        for codigo, nombre in TRAINING_TYPES.items()
        if codigo not in obsoletos and P.entrenamiento_de_chpp(codigo) is None
    ]
    assert not sin_pareja, f"entrenamientos de CHPP sin puesto conocido: {sin_pareja}"


def test_los_obsoletos_no_tienen_pareja_y_esta_bien() -> None:
    # Un entrenamiento retirado del juego no debe filtrar nada.
    assert P.entrenamiento_de_chpp(0) is None
    assert P.entrenamiento_de_chpp(1) is None
    assert P.entrenamiento_de_chpp(None) is None


def test_cada_pareja_apunta_a_un_entrenamiento_que_existe() -> None:
    # Una clave mal escrita en el puente daria cero plazas en todas las
    # formaciones, y eso se lee como «este entrenamiento no entrena a nadie».
    for codigo in P.DE_CHPP:
        clave = P.entrenamiento_de_chpp(codigo)
        assert clave is not None
        assert P.puestos_que_entrena(clave), f"{codigo} -> {clave} no toca ningun puesto"
