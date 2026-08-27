"""Lo que va en la celda de entrenamiento, linea a linea.

2026-08-26, formato pedido por el usuario. Antes cada celda era un numero;
con «Individual» ese numero era una MEDIA, y una media aqui engaña -mezcla un
66,7% de Pases con un 28,3% de Lateral como si valieran lo mismo-.

Lo que se fija aqui son las tres formas que puede tomar una celda, y sobre
todo la frontera entre `lineas_en` (lo que se ENSEÑA) y `reparto_en` (las
PROBABILIDADES del sorteo): mezclarlas corrompia el sorteo.
"""

from app.domain.engines.youth_training_plan import (
    CODIGO_INDIVIDUAL,
    ENTRENAMIENTOS,
    ritmo_individual,
)


def test_un_entrenamiento_corriente_da_una_sola_linea():
    """Y sin probabilidad: no sortea nada, asi que la pantalla no cambia."""
    lineas = ENTRENAMIENTOS["winger"].lineas_en("winger")
    assert len(lineas) == 1
    assert lineas[0].skill == "winger"
    assert lineas[0].probabilidad is None


def test_anotacion_y_balon_parado_da_dos_lineas_sin_probabilidad():
    """Sube LAS DOS siempre. Un «(proba: 100%)» al lado mentiria.

    Es el fallo que se arreglo al escribir esto: `reparto_en` devolvia solo
    `{'scoring': 100}` y se comia la segunda habilidad.
    """
    lineas = ENTRENAMIENTOS["scoring_set_pieces"].lineas_en("forward")
    assert [x.skill for x in lineas] == ["scoring", "set_pieces"]
    assert all(x.probabilidad is None for x in lineas)
    # A ritmos distintos: 60 y 40. Si fueran iguales, no haria falta el campo.
    assert lineas[0].ritmo != lineas[1].ritmo


def test_individual_da_una_linea_por_casilla_con_su_probabilidad():
    lineas = ENTRENAMIENTOS[CODIGO_INDIVIDUAL].lineas_en("winger")
    assert [x.skill for x in lineas] == [
        "winger",
        "passing",
        "playmaking",
        "defending",
        "set_pieces",
    ]
    assert [x.probabilidad for x in lineas] == [34, 21, 20, 15, 10]
    assert sum(x.probabilidad or 0 for x in lineas) == 100


def test_las_lineas_bajan_de_probabilidad():
    """La pantalla las enseña en este orden y no debe reordenar nada."""
    for puesto in ("keeper", "central_defender", "wingback", "inner_midfield", "forward"):
        probs = [x.probabilidad or 0 for x in ENTRENAMIENTOS[CODIGO_INDIVIDUAL].lineas_en(puesto)]
        assert probs == sorted(probs, reverse=True), puesto


def test_al_portero_le_sale_defensa_mas_que_porteria():
    """Contraintuitivo y real: es lo que hace util enseñar la ruleta entera."""
    lineas = ENTRENAMIENTOS[CODIGO_INDIVIDUAL].lineas_en("keeper")
    assert [x.skill for x in lineas] == ["defending", "keeper", "set_pieces"]
    assert len(lineas) == 3  # la ruleta mas estrecha de las seis


def test_la_mas_probable_puede_ser_la_que_peor_rinde():
    """El extremo: Lateral sale 34 veces de 100 y es la que menos entrena.

    Es justo lo que la media escondia, y la razon de desplegar la celda.
    """
    lineas = ENTRENAMIENTOS[CODIGO_INDIVIDUAL].lineas_en("winger")
    mas_probable = lineas[0]
    assert mas_probable.skill == "winger"
    assert all(mas_probable.ritmo <= x.ritmo for x in lineas)


def test_lineas_en_no_toca_el_sorteo():
    """`reparto_en` son PROBABILIDADES y siguen sumando 100.

    Si algun dia se le añadiera la segunda habilidad de «Anotación y balón
    parado», `probabilidad_de_descubrir` devolveria numeros imposibles.
    """
    e = ENTRENAMIENTOS["scoring_set_pieces"]
    assert sum(e.reparto_en("forward").values()) == 100
    assert len(e.lineas_en("forward")) == 2  # y aun asi se enseñan las dos


def test_el_ritmo_de_cada_linea_es_el_de_su_habilidad():
    """No la media del puesto: cada casilla rinde lo suyo."""
    for linea in ENTRENAMIENTOS[CODIGO_INDIVIDUAL].lineas_en("forward"):
        assert linea.ritmo == ritmo_individual("forward", linea.skill)
