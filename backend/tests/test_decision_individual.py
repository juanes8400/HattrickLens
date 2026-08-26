"""Las dos reglas que deciden si se entrena «Individual».

Dictadas por el usuario el 2026-08-26. Lo que se fija aquí es el
COMPORTAMIENTO en los bordes, que es donde una regla escrita en una frase se
vuelve ambigua: los dos umbrales son estrictos, y B manda sobre A.
"""

from app.domain.engines.decision_individual import (
    DESVIACION_MAXIMA,
    HABILIDADES_DE_PUESTO,
    INDIVIDUAL,
    RAZON_MINIMA,
    cola_de_descubrimiento,
    decidir,
)
from app.domain.engines.youth_skill_score import PlayerNote
from app.domain.engines.youth_training_plan import ENTRENAMIENTOS, cupos_de

#: La academia del usuario el 2026-08-26: un extremo bueno y seis habilidades
#: empatadas en pura ignorancia. Es el caso que originó las reglas.
REAL = [
    ("winger", 1.92),
    ("keeper", 0.28),
    ("defending", 0.28),
    ("playmaking", 0.28),
    ("set_pieces", 0.28),
    ("passing", 0.28),
    ("scoring", 0.24),
]


def test_regla_a_con_los_datos_reales():
    d = decidir(REAL)
    assert d is not None
    assert d.regla == "A"
    assert d.principal == "winger"
    assert d.secundario == INDIVIDUAL
    assert round(d.razon or 0, 2) == 6.86
    assert d.descubre


def test_regla_b_cuando_nada_destaca():
    d = decidir([(f"h{i}", 0.30) for i in range(7)])
    assert d is not None
    assert d.regla == "B"
    assert d.principal == INDIVIDUAL
    assert d.secundario == INDIVIDUAL


def test_b_manda_cuando_las_dos_se_disparan():
    """Líder claro sobre un conjunto diminuto: razón 4,5 y desviación 0,245.

    Las dos reglas dicen cosas distintas y el usuario zanjó que mande B: si el
    mejor apenas roza 0,9, ese liderazgo es sobre nada.
    """
    caso = [("lider", 0.9)] + [(f"h{i}", 0.2) for i in range(6)]
    d = decidir(caso)
    assert d is not None
    assert d.razon is not None and d.razon > RAZON_MINIMA
    assert d.desviacion < DESVIACION_MAXIMA
    assert d.regla == "B"
    assert d.principal == INDIVIDUAL


def test_sin_individual_cuando_hay_dos_habilidades_de_verdad():
    d = decidir([("a", 2.0), ("b", 1.5), ("c", 0.9), ("d", 0.4), ("e", 0.3)])
    assert d is not None
    assert d.regla is None
    assert (d.principal, d.secundario) == ("a", "b")
    assert not d.descubre


def test_los_dos_umbrales_son_estrictos():
    """Exactamente 4x y exactamente 0,25 NO disparan: «más de», «menor que»."""
    justo_cuatro = [("a", 4.0), ("b", 1.0), ("c", 1.0)]
    d = decidir(justo_cuatro)
    assert d is not None and d.razon == RAZON_MINIMA and d.regla is None

    # Dos valores a distancia 0,25 del centro dan desviación 0,25 clavada.
    d2 = decidir([("a", 0.5), ("b", 0.0)])
    assert d2 is not None and d2.desviacion == DESVIACION_MAXIMA
    assert d2.regla == "A"  # no dispara B; sí A, porque el segundo es cero


def test_segundo_en_cero_es_lider_infinito():
    d = decidir([("a", 9.0), ("b", 0.0), ("c", 0.0)])
    assert d is not None
    assert d.razon == float("inf")
    assert d.regla == "A"
    assert d.secundario == INDIVIDUAL


def test_todo_a_cero_descubre():
    """Academia recién abierta: no se sabe nada de nadie. Desviación 0."""
    d = decidir([(f"h{i}", 0.0) for i in range(7)])
    assert d is not None
    assert d.regla == "B"
    assert d.razon is None


def test_sin_dos_habilidades_no_hay_veredicto():
    assert decidir([]) is None
    assert decidir([("a", 1.0)]) is None


# --------------------------------------------------------------------------
# «Individual» como entrenamiento normal del motor de siempre.
# --------------------------------------------------------------------------


def test_individual_es_un_entrenamiento_mas():
    """Vive en la misma tabla, así que los selectores lo ofrecen solos."""
    e = ENTRENAMIENTOS[INDIVIDUAL]
    assert e.label == "Individual"
    # Llega a los seis puestos: es lo que le deja tocar cinco habilidades de
    # una pasada en vez de una.
    assert {c.puesto for c in cupos_de(INDIVIDUAL)} == {
        "keeper",
        "central_defender",
        "wingback",
        "inner_midfield",
        "winger",
        "forward",
    }


def test_cada_puesto_sube_su_habilidad():
    """El mapa dictado por el usuario. Es lo que dice la barrita del once."""
    e = ENTRENAMIENTOS[INDIVIDUAL]
    assert e.skill_en("keeper") == "keeper"
    assert e.skill_en("central_defender") == "defending"
    assert e.skill_en("wingback") == "defending"
    assert e.skill_en("inner_midfield") == "playmaking"
    assert e.skill_en("winger") == "winger"
    assert e.skill_en("forward") == "scoring"


def test_un_entrenamiento_normal_ignora_el_puesto():
    """`skill_en` es uniforme: quien pregunta no necesita saber cuál es cual."""
    for codigo in ("keeper", "defending", "passing", "set_pieces"):
        e = ENTRENAMIENTOS[codigo]
        assert e.skill_en("winger") == e.skill_en("forward") == e.skill


def test_individual_no_alcanza_pases_ni_balon_parado():
    """Ningún puesto las entrena, así que Individual no las descubre nunca.

    Se fija a propósito: es el precio de la Regla B y no debe perderse en un
    refactor silencioso.
    """
    e = ENTRENAMIENTOS[INDIVIDUAL]
    alcanzadas = set((e.skill_por_puesto or {}).values())
    assert alcanzadas == set(HABILIDADES_DE_PUESTO)
    assert "passing" not in alcanzadas
    assert "set_pieces" not in alcanzadas


def _nota(nombre: str, *, pronto: bool = False, techo: int = 0) -> PlayerNote:
    return PlayerNote(
        name=nombre,
        note=None,
        bucket="desconocido_tarde",
        leaves_soon=pronto,
        max_reached=False,
        htms28_max=techo,
    )


def test_la_cola_pone_delante_a_quien_mas_ilumina():
    notas = [_nota("leido"), _nota("tapado"), _nota("medio")]
    orden = cola_de_descubrimiento(notas, {"leido": 0, "tapado": 5, "medio": 2})
    assert [n.name for n in orden] == ["tapado", "medio", "leido"]


def test_entre_igual_de_tapados_manda_el_que_se_va():
    """O lo miras ahora o no lo miras: el que se queda tendrá su turno."""
    notas = [_nota("se_queda"), _nota("se_va", pronto=True)]
    orden = cola_de_descubrimiento(notas, {"se_queda": 3, "se_va": 3})
    assert [n.name for n in orden] == ["se_va", "se_queda"]


def test_y_luego_el_de_mas_potencial():
    notas = [_nota("flojo", techo=100), _nota("crack", techo=900)]
    orden = cola_de_descubrimiento(notas, {"flojo": 3, "crack": 3})
    assert [n.name for n in orden] == ["crack", "flojo"]
